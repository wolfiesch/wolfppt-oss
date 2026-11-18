"""Theme colour and font resolution for the built-in scene renderer.

A slide inherits its palette and typefaces from its layout's master's theme
part.  This module reads that part once and turns DrawingML colour and typeface
references into concrete values, so no emitter ever has to guess a colour or
depend on an installed theme.

DrawingML transforms are evaluated in document order. RGB channel operations,
shade, tint and inverse use linear-light RGB; hue, saturation and lightness use
HSL. The sRGB transfer function converts between encoded and linear components.
``a:sysClr`` requires its stored ``lastClr`` rather than a machine palette.
Unknown color elements, transforms and malformed numeric values are refused.

Empty primary East Asian/complex slots may use a declared supplemental East
Asian script face selected from inherited language or unambiguous text. Primary
and explicit faces retain priority. Missing or ambiguous mappings stay empty
for the text resolver to refuse; font admission remains a separate check.
"""

from __future__ import annotations

import colorsys
import copy
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from typing import Any
from xml.etree import ElementTree as ET

from .render_refusals import RenderRefusal
from .xml_helpers import (
    STRICT_A_NS,
    find_ooxml,
    findall_ooxml,
    ooxml_namespace,
    ooxml_path,
    percentage_value,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

#: DrawingML aliases that name the first/second text and background colours.
#: A presentation's ``p:clrMap`` may re-point any of these aliases at another
#: theme colour, which is how a dark theme renders ``tx1`` from ``lt1``.
_SCHEME_ALIASES = {
    "text1": "dk1",
    "text2": "dk2",
    "background1": "lt1",
    "background2": "lt2",
    "tx1": "dk1",
    "tx2": "dk2",
    "bg1": "lt1",
    "bg2": "lt2",
}

#: The colour slots a presentation's ``p:clrMap`` (or ``p:clrMapOvr``) maps.
_COLOR_MAP_SLOTS = (
    "bg1",
    "tx1",
    "bg2",
    "tx2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
)


def color_map_from(element: ET.Element | None) -> Mapping[str, str] | None:
    """Read a ``p:clrMap``-shaped element into a slot map.

    The result is ``None`` when the element is absent or declares no slot, so a
    caller can tell "no mapping declared" from "a mapping that points at the
    theme's own colours".
    """
    if element is None:
        return None
    mapping = {
        slot: value
        for slot, value in ((slot, element.get(slot)) for slot in _COLOR_MAP_SLOTS)
        if value
    }
    return mapping or None


def override_color_map(
    element: ET.Element | None,
    inherited: Mapping[str, str] | None,
    *,
    master: Mapping[str, str] | None,
) -> Mapping[str, str] | None:
    """Apply one ``p:clrMapOvr`` to the colour map it inherits.

    ``a:masterClrMapping`` resets to the master's map, bypassing layout
    overrides; ``a:overrideClrMapping`` replaces the inherited map outright.
    """
    if element is None:
        return inherited
    if find_ooxml(element, f"{{{A_NS}}}masterClrMapping") is not None:
        return master
    override = find_ooxml(element, f"{{{A_NS}}}overrideClrMapping")
    if override is None:
        return inherited
    return color_map_from(override) or inherited


#: The preset colours this renderer can resolve from their canonical name.
_PRESET_COLORS = {
    "black": "000000",
    "white": "FFFFFF",
    "red": "FF0000",
    "green": "008000",
    "blue": "0000FF",
    "yellow": "FFFF00",
    "gray": "808080",
    "grey": "808080",
    "silver": "C0C0C0",
    "navy": "000080",
    "maroon": "800000",
    "purple": "800080",
    "teal": "008080",
    "lime": "00FF00",
    "aqua": "00FFFF",
    "fuchsia": "FF00FF",
    "olive": "808000",
    "darkBlue": "00008B",
    "darkRed": "8B0000",
    "darkGreen": "006400",
    "lightGray": "D3D3D3",
    "lightGrey": "D3D3D3",
}

_FILL_TAGS = ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")

#: ECMA-376 ST_PresetPatternVal values.  Keeping the schema vocabulary here
#: makes a renderer refusal explicit for malformed or future values rather than
#: treating them as a solid fill.
PRESET_PATTERN_VALUES = frozenset(
    {
        "pct5",
        "pct10",
        "pct20",
        "pct25",
        "pct30",
        "pct40",
        "pct50",
        "pct60",
        "pct70",
        "pct75",
        "pct80",
        "pct90",
        "horz",
        "vert",
        "ltHorz",
        "ltVert",
        "dkHorz",
        "dkVert",
        "narHorz",
        "narVert",
        "dashHorz",
        "dashVert",
        "cross",
        "dnDiag",
        "upDiag",
        "ltDnDiag",
        "ltUpDiag",
        "dkDnDiag",
        "dkUpDiag",
        "wdDnDiag",
        "wdUpDiag",
        "dashDnDiag",
        "dashUpDiag",
        "diagCross",
        "smCheck",
        "lgCheck",
        "smGrid",
        "lgGrid",
        "dotGrid",
        "smConfetti",
        "lgConfetti",
        "horzBrick",
        "diagBrick",
        "solidDmnd",
        "openDmnd",
        "dotDmnd",
        "plaid",
        "sphere",
        "weave",
        "divot",
        "shingle",
        "wave",
        "trellis",
        "zigZag",
    }
)

COLOR_TAGS = frozenset({"srgbClr", "scrgbClr", "hslClr", "schemeClr", "sysClr", "prstClr"})
_TRANSFORM_TAGS = frozenset(
    {
        "alpha",
        "alphaMod",
        "alphaOff",
        "hue",
        "hueMod",
        "hueOff",
        "sat",
        "satMod",
        "satOff",
        "lum",
        "lumMod",
        "lumOff",
        "red",
        "redMod",
        "redOff",
        "green",
        "greenMod",
        "greenOff",
        "blue",
        "blueMod",
        "blueOff",
        "tint",
        "shade",
        "comp",
        "inv",
        "gray",
        "gamma",
        "invGamma",
    }
)


class ThemeRefusal(RenderRefusal):
    """Raised when a theme reference cannot be resolved exactly."""


@dataclass(frozen=True)
class ResolvedColor:
    """A concrete colour with its opacity."""

    rgb: str
    alpha: float = 1.0

    def css(self) -> str:
        return f"#{self.rgb}"


def _east_asian_script(language: str | None, text: str) -> str | None:
    """Choose only an unambiguous supported supplemental script, never a face."""
    detected = None
    for character in text:
        cp = ord(character)
        script = None
        if 0x3040 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF or 0xFF66 <= cp <= 0xFF9F:
            script = "Jpan"
        elif (
            0x1100 <= cp <= 0x11FF
            or 0x3130 <= cp <= 0x318F
            or 0xAC00 <= cp <= 0xD7AF
            or 0xFFA0 <= cp <= 0xFFDC
        ):
            script = "Hang"
        elif 0x3100 <= cp <= 0x312F or 0x31A0 <= cp <= 0x31BF:
            script = "Hant"
        if script is not None:
            if detected is not None and detected != script:
                return None
            detected = script
    if detected is not None:
        return detected
    # Shared Han characters cannot distinguish Japanese, Korean, or Chinese.
    # An explicit language/script is required; never guess a locale from Han.
    parts = (language or "").lower().split("-")
    explicit_script = next((part for part in parts[1:] if len(part) == 4 and part.isalpha()), None)
    if explicit_script is not None:
        return {
            "jpan": "Jpan",
            "hang": "Hang",
            "kore": "Hang",
            "hans": "Hans",
            "hant": "Hant",
        }.get(explicit_script)
    if parts[0] == "ja":
        return "Jpan"
    if parts[0] == "ko":
        return "Hang"
    if parts[0] == "zh":
        if any(part in {"tw", "hk", "mo"} for part in parts[1:]):
            return "Hant"
        if any(part in {"cn", "sg", "my"} for part in parts[1:]):
            return "Hans"
    return None


@dataclass(frozen=True)
class ThemeFontCollection:
    """Typefaces declared for one font collection (majorFont or minorFont)."""

    latin: str = ""
    ea: str = ""
    cs: str = ""
    supplemental: Mapping[str, str] = field(default_factory=dict)

    def font_for_script(self, script: str, *, fallback_script: str | None = None) -> str:
        """Resolve a declared face, using a supplied script only for empty ea/cs."""
        script_clean = script.strip()
        script_lower = script_clean.lower()
        if script_lower in {"lt", "latin", "latn"}:
            return self.latin
        if script_lower in {"ea", "eastasia", "eastasian"}:
            if self.ea:
                return self.ea
            script_clean = fallback_script or ""
        elif script_lower in {"cs", "complexscript", "bidi"}:
            if self.cs:
                return self.cs
            script_clean = fallback_script or ""
        script_lower = script_clean.lower()
        if script_clean in self.supplemental:
            return self.supplemental[script_clean]
        for name, typeface in self.supplemental.items():
            if name.lower() == script_lower:
                return typeface
        return ""


@dataclass(frozen=True)
class ThemeScheme:
    """One theme part's colour and font scheme."""

    colors: Mapping[str, str]
    major_latin: str = ""
    minor_latin: str = ""
    color_map: Mapping[str, str] | None = None
    major_ea: str = ""
    minor_ea: str = ""
    major_cs: str = ""
    minor_cs: str = ""
    major_supplemental: Mapping[str, str] = field(default_factory=dict)
    minor_supplemental: Mapping[str, str] = field(default_factory=dict)
    color_alpha: Mapping[str, float] = field(default_factory=dict)

    @property
    def major_fonts(self) -> ThemeFontCollection:
        return ThemeFontCollection(
            latin=self.major_latin,
            ea=self.major_ea,
            cs=self.major_cs,
            supplemental=self.major_supplemental,
        )

    @property
    def minor_fonts(self) -> ThemeFontCollection:
        return ThemeFontCollection(
            latin=self.minor_latin,
            ea=self.minor_ea,
            cs=self.minor_cs,
            supplemental=self.minor_supplemental,
        )

    def scheme_color(self, name: str) -> ResolvedColor:
        # A slide's rendering uses the presentation's colour map first: the map
        # re-points the ``bg1``/``tx1``/... aliases at real theme colours, and
        # the DrawingML aliases only backstop the names the map does not state.
        key = None if self.color_map is None else self.color_map.get(name)
        if key is None:
            key = _SCHEME_ALIASES.get(name, name)
        value = self.colors.get(key)
        if value is None:
            raise ThemeRefusal(f"theme has no colour named {name!r}")
        return ResolvedColor(value, self.color_alpha.get(key, 1.0))

    def scheme_font(self, typeface: str, *, fallback_script: str | None = None) -> str:
        tf = typeface.strip()
        if tf.startswith("+mj-"):
            script = tf[4:]
            resolved = self.major_fonts.font_for_script(script, fallback_script=fallback_script)
            if (
                resolved
                or script.lower()
                in {
                    "lt",
                    "latin",
                    "latn",
                    "ea",
                    "eastasia",
                    "eastasian",
                    "cs",
                    "complexscript",
                    "bidi",
                }
                or script in self.major_supplemental
                or any(k.lower() == script.lower() for k in self.major_supplemental)
            ):
                return resolved
            raise ThemeRefusal(f"theme font reference {typeface!r} is not supported")
        if tf.startswith("+mn-"):
            script = tf[4:]
            resolved = self.minor_fonts.font_for_script(script, fallback_script=fallback_script)
            if (
                resolved
                or script.lower()
                in {
                    "lt",
                    "latin",
                    "latn",
                    "ea",
                    "eastasia",
                    "eastasian",
                    "cs",
                    "complexscript",
                    "bidi",
                }
                or script in self.minor_supplemental
                or any(k.lower() == script.lower() for k in self.minor_supplemental)
            ):
                return resolved
            raise ThemeRefusal(f"theme font reference {typeface!r} is not supported")
        raise ThemeRefusal(f"theme font reference {typeface!r} is not supported")


#: The schemes a ``a:themeOverride`` part may replace, in schema order.
THEME_SCHEME_TAGS = ("clrScheme", "fontScheme", "fmtScheme")


def theme_with_overrides(theme: ET.Element, overrides: Sequence[ET.Element | None]) -> ET.Element:
    """Return the theme one slide, layout or notes page draws with.

    ``overrides`` lists the ``a:themeOverride`` roots that apply, nearest
    first (slide, then layout).  Each scheme comes from the nearest override
    that states it, else from the master's theme; everything else (object
    defaults, extra colour schemes, extensions) stays the master theme's.
    The master theme is returned unchanged when no override applies.
    """
    present = [override for override in overrides if override is not None]
    if not present:
        return theme
    for override in present:
        if override.tag.rsplit("}", 1)[-1] != "themeOverride":
            raise ThemeRefusal("theme override part has no themeOverride root")
    effective = copy.deepcopy(theme)
    elements = find_ooxml(effective, f"{{{A_NS}}}themeElements")
    if elements is None:
        raise ThemeRefusal("theme part has no themeElements")
    for name in THEME_SCHEME_TAGS:
        replacement = next(
            (
                found
                for override in present
                if (found := find_ooxml(override, f"{{{A_NS}}}{name}")) is not None
            ),
            None,
        )
        if replacement is None:
            continue
        current = find_ooxml(elements, f"{{{A_NS}}}{name}")
        if current is None:
            raise ThemeRefusal(f"theme has no {name} for an override to replace")
        elements[list(elements).index(current)] = copy.deepcopy(replacement)
    return effective


def parse_theme_scheme(payload: bytes | ET.Element) -> ThemeScheme:
    """Read schemes from theme bytes or an already MC-selected theme tree."""
    if isinstance(payload, ET.Element):
        root = payload
    else:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ThemeRefusal("theme part is not well-formed XML") from exc
    elements = find_ooxml(root, f"{{{A_NS}}}themeElements")
    if elements is None:
        raise ThemeRefusal("theme part has no themeElements")
    color_scheme = find_ooxml(elements, f"{{{A_NS}}}clrScheme")
    if color_scheme is None:
        raise ThemeRefusal("theme part has no colour scheme")
    colors: dict[str, str] = {}
    alphas: dict[str, float] = {}
    drawing_ns = ooxml_namespace(color_scheme, A_NS)
    entries = {
        entry.tag.rsplit("}", 1)[-1]: entry
        for entry in color_scheme
        if entry.tag != f"{{{drawing_ns}}}extLst" and entry.tag.startswith(f"{{{drawing_ns}}}")
    }
    palette = ThemeScheme(colors=colors, color_alpha=alphas)
    resolving: set[str] = set()

    def resolve_entry(name: str) -> None:
        if name in colors:
            return
        if name in resolving:
            raise ThemeRefusal(f"theme colour reference cycle at {name!r}")
        entry = entries.get(name)
        if entry is None or len(entry) != 1:
            raise ThemeRefusal(f"theme colour {name!r} needs exactly one colour")
        resolving.add(name)
        child = entry[0]
        if child.tag == f"{{{drawing_ns}}}schemeClr":
            reference = child.get("val", "")
            resolve_entry(_SCHEME_ALIASES.get(reference, reference))
        resolved = resolve_color_element(child, palette)
        colors[name] = resolved.rgb
        alphas[name] = resolved.alpha
        resolving.remove(name)

    for name in entries:
        resolve_entry(name)
    font_scheme = find_ooxml(elements, f"{{{A_NS}}}fontScheme")
    major_latin = ""
    minor_latin = ""
    major_ea = ""
    minor_ea = ""
    major_cs = ""
    minor_cs = ""
    major_supplemental: dict[str, str] = {}
    minor_supplemental: dict[str, str] = {}
    if font_scheme is not None:
        major = find_ooxml(font_scheme, f"{{{A_NS}}}majorFont")
        if major is not None:
            latin_el = find_ooxml(major, f"{{{A_NS}}}latin")
            if latin_el is not None:
                major_latin = latin_el.get("typeface", "")
            ea_el = find_ooxml(major, f"{{{A_NS}}}ea")
            if ea_el is not None:
                major_ea = ea_el.get("typeface", "")
            cs_el = find_ooxml(major, f"{{{A_NS}}}cs")
            if cs_el is not None:
                major_cs = cs_el.get("typeface", "")
            for child in list(major):
                if child.tag == f"{{{drawing_ns}}}font":
                    script = child.get("script")
                    typeface = child.get("typeface")
                    if script and typeface:
                        major_supplemental[script] = typeface

        minor = find_ooxml(font_scheme, f"{{{A_NS}}}minorFont")
        if minor is not None:
            latin_el = find_ooxml(minor, f"{{{A_NS}}}latin")
            if latin_el is not None:
                minor_latin = latin_el.get("typeface", "")
            ea_el = find_ooxml(minor, f"{{{A_NS}}}ea")
            if ea_el is not None:
                minor_ea = ea_el.get("typeface", "")
            cs_el = find_ooxml(minor, f"{{{A_NS}}}cs")
            if cs_el is not None:
                minor_cs = cs_el.get("typeface", "")
            for child in list(minor):
                if child.tag == f"{{{drawing_ns}}}font":
                    script = child.get("script")
                    typeface = child.get("typeface")
                    if script and typeface:
                        minor_supplemental[script] = typeface

    return ThemeScheme(
        colors=colors,
        major_latin=major_latin,
        minor_latin=minor_latin,
        major_ea=major_ea,
        minor_ea=minor_ea,
        major_cs=major_cs,
        minor_cs=minor_cs,
        major_supplemental=major_supplemental,
        minor_supplemental=minor_supplemental,
        color_alpha=alphas,
    )


@dataclass(frozen=True)
class FontSchemeEffectiveData:
    """Resolved heading and body collections, using the renderer's font rules."""

    major: ThemeFontCollection
    minor: ThemeFontCollection


@dataclass(frozen=True)
class FormatSchemeEffectiveData:
    """Detached style collections for an explicit placeholder context.

    Existing XML collections remain source-compatible. The ``typed_*``
    collections expose read-only resolved declarations, including effects and
    3D outside renderer admission. Indices are zero-based in both views.
    They hold ``wolfppt.effective_format_shapes`` snapshots (``ThemeFillSnapshot``,
    ``ThemeLineSnapshot``, ``ThemeEffectStyleSnapshot``), which only the
    commercial edition ships; a Community install leaves them empty.
    """

    fill_styles: tuple[str, ...]
    line_styles: tuple[str, ...]
    effect_styles: tuple[str, ...]
    background_fill_styles: tuple[str, ...]
    typed_fill_styles: tuple[Any, ...] = ()
    typed_line_styles: tuple[Any, ...] = ()
    typed_effect_styles: tuple[Any, ...] = ()
    typed_background_fill_styles: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ThemeEffectiveData:
    """Detached effective schemes for one owner and explicit style placeholder."""

    color_scheme: Mapping[str, str]
    font_scheme: FontSchemeEffectiveData
    format_scheme: FormatSchemeEffectiveData
    resolver: ThemeScheme
    placeholder: str = "accent1"
    color_context: ResolvedColor | None = None


def effective_theme_data(
    root: ET.Element,
    *,
    color_map: Mapping[str, str] | None = None,
    placeholder: str = "accent1",
    color_context: ET.Element | None = None,
) -> ThemeEffectiveData:
    """Resolve effective styles through the renderer's own style/colour resolver.

    DrawingML style-matrix ``phClr`` has no value outside a shape reference.
    ``placeholder`` supplies that reference's scheme colour (default accent1).
    Alternatively, ``color_context`` supplies a DrawingML ``srgbClr`` element
    with ordered transforms, including alpha. It replaces only ``phClr``, never
    palette slots. The detached snapshot stores its resolved RGB/alpha value.
    Collections use zero-based Python indices, unlike one-based style references.
    ECMA-376 Part 1 §20.1.4.1.14 (fmtScheme) defines the four collections.
    """
    from dataclasses import replace

    from .editions import CommercialFeatureError, commercial_module

    try:
        snapshots = commercial_module("effective_format_shapes", "Typed theme styles")
    except CommercialFeatureError:
        snapshots = None

    parsed = parse_theme_scheme(root)
    scheme = replace(
        parsed,
        colors=MappingProxyType(dict(parsed.colors)),
        color_alpha=MappingProxyType(dict(parsed.color_alpha)),
        color_map=None if color_map is None else MappingProxyType(dict(color_map)),
        major_supplemental=MappingProxyType(dict(parsed.major_supplemental)),
        minor_supplemental=MappingProxyType(dict(parsed.minor_supplemental)),
    )
    if color_context is None:
        scheme.scheme_color(placeholder)
        context = ET.Element(f"{{{A_NS}}}schemeClr", {"val": placeholder})
        resolved_context = None
    else:
        if not isinstance(color_context, ET.Element) or color_context.tag not in {
            f"{{{A_NS}}}srgbClr",
            f"{{{STRICT_A_NS}}}srgbClr",
        }:
            raise ThemeRefusal("color_context must be a DrawingML srgbClr element")
        # Validate even when no style uses phClr, before any snapshot is returned.
        resolved_context = resolve_color_element(color_context, scheme)
        context = color_context

    def styles(list_name: str) -> tuple[ET.Element, ...]:
        listing = find_ooxml(
            root, f"{{{A_NS}}}themeElements/{{{A_NS}}}fmtScheme/{{{A_NS}}}{list_name}"
        )
        if listing is None:
            raise ThemeRefusal(f"theme has no {list_name}")
        result = []
        for index in range(len(listing)):
            reference = ET.Element("reference", {"idx": str(index + 1)})
            reference.append(context)
            entry = resolve_scheme_paint(root, scheme, list_name, reference)
            assert entry is not None
            # Resolve ordinary scheme colours and ordered transforms as well as
            # the placeholder colour substituted by resolve_scheme_paint.
            for element in list(entry.iter()):
                if element.tag.rsplit("}", 1)[-1] not in COLOR_TAGS:
                    continue
                color = resolve_color_element(element, scheme)
                element.tag = f"{{{ooxml_namespace(element, A_NS)}}}srgbClr"
                element.attrib.clear()
                element.set("val", color.rgb)
                element[:] = []
                if color.alpha != 1.0:
                    ET.SubElement(
                        element,
                        f"{{{ooxml_namespace(element, A_NS)}}}alpha",
                        {"val": f"{color.alpha * 100:.6f}%"},
                    )
            result.append(entry)
        return tuple(result)

    fills = styles("fillStyleLst")
    lines = styles("lnStyleLst")
    effects = styles("effectStyleLst")
    backgrounds = styles("bgFillStyleLst")

    def xml(entries: tuple[ET.Element, ...]) -> tuple[str, ...]:
        return tuple(ET.tostring(entry, encoding="unicode") for entry in entries)

    def typed(snapshot: str, entries: tuple[ET.Element, ...]) -> tuple[Any, ...]:
        if snapshots is None:
            return ()
        return tuple(getattr(snapshots, snapshot)(entry, scheme) for entry in entries)

    return ThemeEffectiveData(
        color_scheme=scheme.colors,
        font_scheme=FontSchemeEffectiveData(scheme.major_fonts, scheme.minor_fonts),
        format_scheme=FormatSchemeEffectiveData(
            xml(fills),
            xml(lines),
            xml(effects),
            xml(backgrounds),
            typed("_theme_fill_snapshot", fills),
            typed("_theme_line_snapshot", lines),
            typed("_theme_effect_snapshot", effects),
            typed("_theme_fill_snapshot", backgrounds),
        ),
        resolver=scheme,
        placeholder=placeholder,
        color_context=resolved_context,
    )


def _normalize_rgb(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().lstrip("#").upper()
    if len(candidate) != 6 or any(character not in "0123456789ABCDEF" for character in candidate):
        return None
    return candidate


def resolve_color_element(
    color_element: ET.Element,
    scheme: ThemeScheme,
    *,
    placeholder: str | None = None,
) -> ResolvedColor:
    """Resolve one DrawingML colour and its ordered standard transforms."""
    drawing_ns = ooxml_namespace(color_element, A_NS)
    tag = color_element.tag.rsplit("}", 1)[-1]
    if color_element.tag != f"{{{drawing_ns}}}{tag}" or tag not in COLOR_TAGS:
        raise ThemeRefusal(f"colour element {tag!r} is not supported")
    alpha = 1.0
    if drawing_ns == STRICT_A_NS:
        keys = ("r", "g", "b") if tag == "scrgbClr" else ("sat", "lum") if tag == "hslClr" else ()
        for key in keys:
            try:
                percentage_value(color_element, color_element.get(key, ""))
            except ValueError as exc:
                raise ThemeRefusal(f"colour {key!r}: {exc}") from exc
    if tag == "scrgbClr":
        channels = tuple(
            _linear_to_srgb(_fixed_percentage(color_element.get(key), key))
            for key in ("r", "g", "b")
        )
    elif tag == "hslClr":
        channels = colorsys.hls_to_rgb(
            _angle(color_element.get("hue"), "hue", fixed=True),
            _fixed_percentage(color_element.get("lum"), "lum"),
            _fixed_percentage(color_element.get("sat"), "sat"),
        )
    else:
        if tag == "srgbClr":
            rgb = _normalize_rgb(color_element.get("val"))
        elif tag == "schemeClr":
            name = color_element.get("val", "")
            if name == "phClr":
                rgb = _normalize_rgb(placeholder)
                if rgb is None:
                    raise ThemeRefusal("theme colour placeholder phClr has no resolved value")
            else:
                resolved = scheme.scheme_color(name)
                rgb, alpha = resolved.rgb, resolved.alpha
        elif tag == "sysClr":
            rgb = _normalize_rgb(color_element.get("lastClr"))
            if rgb is None:
                raise ThemeRefusal(
                    "system colour element stores no lastClr value; the renderer "
                    "never reads the rendering machine's system palette"
                )
        else:
            name = color_element.get("val", "")
            rgb = _PRESET_COLORS.get(name)
            if rgb is None:
                raise ThemeRefusal(f"preset colour {name!r} is not supported")
        if rgb is None:
            raise ThemeRefusal("solid colour element has no usable RGB value")
        channels = _rgb_channels(rgb)

    for transform in color_element:
        name = transform.tag.rsplit("}", 1)[-1]
        if transform.tag != f"{{{drawing_ns}}}{name}" or name not in _TRANSFORM_TAGS:
            raise ThemeRefusal(f"colour transform {name!r} is not supported")
        if len(transform):
            raise ThemeRefusal(f"colour transform {name!r} must be empty")
        raw = transform.get("val")
        if drawing_ns == STRICT_A_NS and name not in {
            "hue",
            "hueOff",
            "comp",
            "inv",
            "gray",
            "gamma",
            "invGamma",
        }:
            try:
                percentage_value(transform, raw if raw is not None else "")
            except ValueError as exc:
                raise ThemeRefusal(f"colour transform {name!r}: {exc}") from exc
        if name == "alpha":
            alpha = _fixed_percentage(raw, name)
        elif name == "alphaMod":
            alpha = _clamp(alpha * _positive_percentage(raw, name))
        elif name == "alphaOff":
            value = _percentage(raw, name)
            if not -1.0 <= value <= 1.0:
                raise ThemeRefusal("colour transform 'alphaOff' must be between -100000 and 100000")
            alpha = _clamp(alpha + value)
        elif name in {
            "hue",
            "hueMod",
            "hueOff",
            "sat",
            "satMod",
            "satOff",
            "lum",
            "lumMod",
            "lumOff",
            "comp",
        }:
            hue, lightness, saturation = colorsys.rgb_to_hls(*channels)
            if name == "comp":
                hue = (hue + 0.5) % 1.0
            elif name.startswith("hue"):
                if name == "hue":
                    hue = _angle(raw, name, fixed=True)
                elif name == "hueOff":
                    hue = (hue + _angle(raw, name)) % 1.0
                else:
                    hue = (hue * _positive_percentage(raw, name)) % 1.0
            else:
                value = _percentage(raw, name)
                current = saturation if name.startswith("sat") else lightness
                updated = _clamp(
                    current * value
                    if name.endswith("Mod")
                    else current + value
                    if name.endswith("Off")
                    else value
                )
                if name.startswith("sat"):
                    saturation = updated
                else:
                    lightness = updated
            channels = colorsys.hls_to_rgb(hue, lightness, saturation)
        elif name == "gray":
            # DrawingML compatibility weighting used by established renderers.
            gray = channels[0] * 0.22 + channels[1] * 0.72 + channels[2] * 0.06
            channels = (gray, gray, gray)
        elif name in {"gamma", "invGamma"}:
            convert = _linear_to_srgb if name == "gamma" else _srgb_to_linear
            channels = tuple(convert(channel) for channel in channels)
        else:
            linear = [_srgb_to_linear(channel) for channel in channels]
            if name == "inv":
                linear = [1.0 - channel for channel in linear]
            elif name in {"tint", "shade"}:
                value = _fixed_percentage(raw, name)
                linear = [
                    1.0 - (1.0 - channel) * value if name == "tint" else channel * value
                    for channel in linear
                ]
            else:
                value = _percentage(raw, name)
                index = 0 if name.startswith("red") else 1 if name.startswith("green") else 2
                current = linear[index]
                linear[index] = _clamp(
                    current * value
                    if name.endswith("Mod")
                    else current + value
                    if name.endswith("Off")
                    else value
                )
            channels = tuple(_linear_to_srgb(channel) for channel in linear)
    return ResolvedColor(rgb=_format_channels(channels), alpha=round(alpha, 6))


def _integer(value: str | None, name: str) -> int:
    if value is None:
        raise ThemeRefusal(f"colour transform {name!r} has no value")
    if re.fullmatch(r"[+-]?[0-9]+", value.strip()) is None:
        raise ThemeRefusal(f"colour transform {name!r} has a non-numeric value")
    try:
        number = int(value)
    except ValueError as exc:
        raise ThemeRefusal(f"colour transform {name!r} has an invalid integer") from exc
    if not -(2**31) <= number < 2**31:
        raise ThemeRefusal(f"colour transform {name!r} exceeds the signed 32-bit range")
    return number


def _percentage(value: str | None, name: str) -> float:
    if value is not None and value.strip().endswith("%"):
        raw = value.strip()
        if re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?%", raw) is None:
            raise ThemeRefusal(f"colour transform {name!r} has a non-numeric value")
        result = float(raw[:-1]) / 100.0
        if not math.isfinite(result):
            raise ThemeRefusal(f"colour transform {name!r} has a non-finite value")
        return result
    return _integer(value, name) / 100000.0


def _angle(value: str | None, name: str, *, fixed: bool = False) -> float:
    angle = _integer(value, name)
    if fixed and not 0 <= angle < 21600000:
        raise ThemeRefusal(f"colour angle {name!r} must be between 0 and 21599999")
    return angle / 21600000.0


def _fixed_percentage(value: str | None, name: str) -> float:
    """Parse DrawingML ST_PositiveFixedPercentage ([0%, 100%])."""
    percentage = _percentage(value, name)
    if not 0.0 <= percentage <= 1.0:
        raise ThemeRefusal(f"colour transform {name!r} must be between 0 and 100000")
    return percentage


def _positive_percentage(value: str | None, name: str) -> float:
    """Parse DrawingML ST_PositivePercentage ([0%, infinity))."""
    percentage = _percentage(value, name)
    if percentage < 0.0:
        raise ThemeRefusal(f"colour transform {name!r} must be non-negative")
    return percentage


def _rgb_channels(rgb: str) -> tuple[float, float, float]:
    return (
        int(rgb[0:2], 16) / 255.0,
        int(rgb[2:4], 16) / 255.0,
        int(rgb[4:6], 16) / 255.0,
    )


def _format_channels(channels: Sequence[float]) -> str:
    return "".join(f"{max(0, min(255, round(channel * 255))):02X}" for channel in channels)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _srgb_to_linear(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(value: float) -> float:
    return 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1.0 / 2.4) - 0.055


@dataclass(frozen=True)
class SolidPaint:
    """A resolved solid fill or line colour."""

    color: ResolvedColor

    @property
    def rgb(self) -> str:
        return self.color.rgb


@dataclass(frozen=True)
class GradientStop:
    """One stop of a resolved gradient fill."""

    position: float
    color: ResolvedColor


@dataclass(frozen=True)
class LinearGradientPaint:
    """A resolved linear gradient fill (ECMA-376 Part 1 §20.1.8.33 & §20.1.8.48)."""

    angle: float
    stops: tuple[GradientStop, ...]
    scaled: bool = False
    rot_with_shape: bool = True

    def endpoints(
        self,
        bounds: tuple[float, float, float, float],
        angle_offset: float = 0.0,
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Calculate start and end points in local units for the given bounds."""
        min_x, min_y, max_x, max_y = bounds
        width = max(1.0, max_x - min_x)
        height = max(1.0, max_y - min_y)
        cx = min_x + width / 2.0
        cy = min_y + height / 2.0
        effective_angle = (self.angle + angle_offset) % 360.0
        rad = math.radians(effective_angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        if self.scaled:
            length_norm = 0.5 * abs(cos_a) + 0.5 * abs(sin_a)
            start_u = 0.5 - length_norm * cos_a
            start_v = 0.5 - length_norm * sin_a
            end_u = 0.5 + length_norm * cos_a
            end_v = 0.5 + length_norm * sin_a
            return (
                (min_x + start_u * width, min_y + start_v * height),
                (min_x + end_u * width, min_y + end_v * height),
            )
        length = (width / 2.0) * abs(cos_a) + (height / 2.0) * abs(sin_a)
        return (
            (cx - length * cos_a, cy - length * sin_a),
            (cx + length * cos_a, cy + length * sin_a),
        )


@dataclass(frozen=True)
class PathGradientPaint:
    """Focus-to-edge circular or rectangular shade in the original paint bounds.

    Circle shading currently admits a point focus. Rectangular shading admits
    a non-inverted focus rectangle inside the tile. Shape-following paths and
    expanded gradient tiles require different distance fields and stay refused.
    """

    path: str
    stops: tuple[GradientStop, ...]
    focus: tuple[float, float, float, float]
    rot_with_shape: bool = True

    def position(self, x: float, y: float) -> float:
        left, top, right, bottom = self.focus
        if self.path == "circle":
            # The outer shade is the circle circumscribing the anchor, not an
            # ellipse inscribed in it. Coordinates here are relative to that
            # circle's bounding square; fillToRect uses the same square.
            dx, dy = x - left, y - top
            fx, fy = left - 0.5, top - 0.5
            remaining = 0.25 - fx * fx - fy * fy
            if remaining <= 0:
                raise ThemeRefusal("circle gradient focus must be inside the outer circle")
            projection = fx * dx + fy * dy
            distance = (
                projection + math.sqrt(projection * projection + (dx * dx + dy * dy) * remaining)
            ) / remaining
            return max(0.0, min(1.0, distance))
        dx = (left - x) / left if x < left and left else 0.0
        if x > 1 - right:
            dx = (x - (1 - right)) / right if right else 1.0
        dy = (top - y) / top if y < top and top else 0.0
        if y > 1 - bottom:
            dy = (y - (1 - bottom)) / bottom if bottom else 1.0
        distance = max(dx, dy)
        return max(0.0, min(1.0, distance))


@dataclass(frozen=True)
class PatternPaint:
    """A resolved DrawingML preset pattern with foreground and background ink."""

    preset: str
    foreground: ResolvedColor
    background: ResolvedColor


@dataclass(frozen=True)
class _PatternPrimitive:
    """One normalized operation in a preset-pattern cell.

    ``points`` contain normalized cell coordinates.  Rectangles and circles
    use two pairs (origin and extent, or centre and radius); paths use their
    natural sequence of points.  SVG and PDF scale and translate this exact
    data at emission time.
    """

    operation: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class PatternRecipe:
    """Metrics and executable cell geometry for one preset pattern."""

    kind: str
    spacing: float = 12.0
    weight: float = 1.0
    dash: tuple[float, ...] = ()
    density: float = 0.0
    primitives: tuple[_PatternPrimitive, ...] = field(
        default=(),
        compare=False,
        repr=False,
    )


def _percent_mask_rank(x: int, y: int) -> int:
    rank = 0
    for shift in (0, 1, 2):
        rank = rank * 4 + ((0, 3), (2, 1))[(y >> shift) & 1][(x >> shift) & 1]
    return rank


def _pattern_primitives(recipe: PatternRecipe) -> tuple[_PatternPrimitive, ...]:
    """Build the normalized cell operations that both output formats execute."""

    primitive = _PatternPrimitive
    kind = recipe.kind
    if kind == "percent":
        count = max(1, min(64, round(recipe.density * 64)))
        return tuple(
            primitive("fill_rect", ((x / 8, y / 8), (1 / 8, 1 / 8)))
            for x, y in sorted(
                ((x, y) for y in range(8) for x in range(8)),
                key=lambda point: _percent_mask_rank(*point),
            )[:count]
        )
    if kind == "horizontal":
        return (primitive("stroke_segments", ((0, 1), (1, 1))),)
    if kind == "vertical":
        return (primitive("stroke_segments", ((1, 0), (1, 1))),)
    if kind in {"cross", "plaid"}:
        return (primitive("stroke_segments", ((0, 1), (1, 1), (1, 0), (1, 1))),)
    if kind == "weave":
        return (
            primitive(
                "stroke_segments",
                (
                    (0, 1 / 3),
                    (1, 1 / 3),
                    (0, 2 / 3),
                    (1, 2 / 3),
                    (1 / 3, 0),
                    (1 / 3, 1),
                    (2 / 3, 0),
                    (2 / 3, 1),
                ),
            ),
        )
    if kind == "down_diagonal":
        return (primitive("stroke_segments", ((0, 1), (1, 0))),)
    if kind == "up_diagonal":
        return (primitive("stroke_segments", ((0, 0), (1, 1))),)
    if kind in {"diagonal_cross", "trellis"}:
        return (primitive("stroke_segments", ((0, 0), (1, 1), (0, 1), (1, 0))),)
    if kind == "checker":
        return (
            primitive("fill_rect", ((0, 0), (1 / 2, 1 / 2))),
            primitive("fill_rect", ((1 / 2, 1 / 2), (1 / 2, 1 / 2))),
        )
    point_radius = max(1.0, recipe.weight) / recipe.spacing
    if kind == "dot_grid":
        return (primitive("fill_circle", ((1 / 2, 1 / 2), (point_radius, 0))),)
    if kind == "confetti":
        return (
            primitive(
                "fill_rect",
                ((1 / 4, 1 / 4), (point_radius, 1 / 2)),
            ),
            primitive(
                "fill_circle",
                ((3 / 4, 3 / 4), (point_radius, 0)),
            ),
        )
    if kind == "sphere":
        return (
            primitive(
                "stroke_circle",
                ((1 / 2, 1 / 2), (1 / 2.5, 0)),
            ),
        )
    diamond = ((1 / 2, 0), (1, 1 / 2), (1 / 2, 1), (0, 1 / 2))
    if kind == "diamond":
        return (primitive("fill_polygon", diamond),)
    if kind == "open_diamond":
        return (primitive("stroke_polygon", diamond),)
    if kind == "dot_diamond":
        return (
            primitive("stroke_polygon", diamond),
            primitive("fill_circle", ((1 / 2, 1 / 2), (point_radius, 0))),
        )
    if kind == "horizontal_brick":
        return (primitive("stroke_polyline", ((0, 0), (1, 0), (1, 1 / 2), (0, 1 / 2))),)
    if kind == "diagonal_brick":
        return (primitive("stroke_segments", ((0, 1), (1, 0), (0, 1 / 2), (1, 1 / 2))),)
    if kind == "divot":
        return (primitive("stroke_polyline", ((0, 0), (1 / 2, 1 / 2), (1, 0))),)
    if kind == "shingle":
        return (
            primitive(
                "stroke_cubics",
                ((0, 1), (1 / 3, 1 / 3), (2 / 3, 1 / 3), (1, 1)),
            ),
        )
    if kind == "wave":
        return (
            primitive(
                "stroke_cubics",
                (
                    (0, 1 / 2),
                    (1 / 6, 1 / 6),
                    (1 / 3, 1 / 6),
                    (1 / 2, 1 / 2),
                    (2 / 3, 5 / 6),
                    (5 / 6, 5 / 6),
                    (1, 1 / 2),
                ),
            ),
        )
    if kind == "zigzag":
        return (primitive("stroke_polyline", ((0, 1), (1 / 2, 0), (1, 1))),)
    raise ThemeRefusal(f"preset pattern {kind!r} has no geometry")


def _pattern_recipe(
    kind: str,
    spacing: float = 12.0,
    weight: float = 1.0,
    dash: tuple[float, ...] = (),
    density: float = 0.0,
) -> PatternRecipe:
    recipe = PatternRecipe(kind, spacing, weight, dash, density)
    return PatternRecipe(
        kind,
        spacing,
        weight,
        dash,
        density,
        _pattern_primitives(recipe),
    )


def percent_pattern_cells(
    recipe: PatternRecipe,
) -> tuple[tuple[float, float, float, float], ...]:
    """Return exact-area 8×8 ordered mask cells for a percentage pattern."""

    if recipe.kind != "percent":
        return ()
    primitives = recipe.primitives or _pattern_primitives(recipe)
    return tuple(
        (origin[0], origin[1], extent[0], extent[1])
        for primitive in primitives
        if primitive.operation == "fill_rect"
        for origin, extent in (primitive.points,)
    )


@cache
def preset_pattern_recipe(preset: str) -> PatternRecipe:
    """Return the distinct DrawingML geometry recipe for one admitted preset."""

    if preset.startswith("pct"):
        return _pattern_recipe("percent", density=int(preset[3:]) / 100.0)
    recipes = {
        "horz": ("horizontal",),
        "vert": ("vertical",),
        "ltHorz": ("horizontal", 18.0),
        "ltVert": ("vertical", 18.0),
        "dkHorz": ("horizontal", 12.0, 2.5),
        "dkVert": ("vertical", 12.0, 2.5),
        "narHorz": ("horizontal", 6.0),
        "narVert": ("vertical", 6.0),
        "dashHorz": ("horizontal", 12.0, 1.0, (3.0, 3.0)),
        "dashVert": ("vertical", 12.0, 1.0, (3.0, 3.0)),
        "cross": ("cross",),
        "dnDiag": ("down_diagonal",),
        "upDiag": ("up_diagonal",),
        "ltDnDiag": ("down_diagonal", 18.0),
        "ltUpDiag": ("up_diagonal", 18.0),
        "dkDnDiag": ("down_diagonal", 12.0, 2.5),
        "dkUpDiag": ("up_diagonal", 12.0, 2.5),
        "wdDnDiag": ("down_diagonal", 24.0, 1.5),
        "wdUpDiag": ("up_diagonal", 24.0, 1.5),
        "dashDnDiag": ("down_diagonal", 12.0, 1.0, (2.0, 2.0)),
        "dashUpDiag": ("up_diagonal", 12.0, 1.0, (2.0, 2.0)),
        "diagCross": ("diagonal_cross",),
        "smCheck": ("checker", 6.0),
        "lgCheck": ("checker", 12.0),
        "smGrid": ("cross", 6.0),
        "lgGrid": ("cross", 18.0),
        "dotGrid": ("dot_grid", 12.0),
        "smConfetti": ("confetti", 6.0),
        "lgConfetti": ("confetti", 12.0),
        "horzBrick": ("horizontal_brick", 12.0),
        "diagBrick": ("diagonal_brick", 12.0),
        "solidDmnd": ("diamond", 12.0),
        "openDmnd": ("open_diamond", 12.0),
        "dotDmnd": ("dot_diamond", 12.0),
        "plaid": ("plaid", 12.0, 2.0),
        "sphere": ("sphere", 12.0),
        "weave": ("weave", 12.0),
        "divot": ("divot", 12.0),
        "shingle": ("shingle", 12.0),
        "wave": ("wave", 12.0),
        "trellis": ("trellis", 12.0),
        "zigZag": ("zigzag", 12.0),
    }
    return _pattern_recipe(*recipes[preset])


@dataclass(frozen=True)
class PaintResolution:
    """The paint of one property holder, and where it came from.

    ``source`` is ``"solid"`` when a solid fill was resolved, ``"gradient"``
    when a linear gradient fill was resolved, ``"pattern"`` when a preset
    pattern fill was resolved, ``"none"`` when the holder carried an explicit
    ``a:noFill``, and ``"absent"`` when the holder carried no paint element at
    all. A caller that must not guess uses ``"absent"`` to fall back to a theme
    style reference or to refuse.
    """

    paint: SolidPaint | LinearGradientPaint | PathGradientPaint | PatternPaint | None
    source: str

    @property
    def is_absent(self) -> bool:
        return self.source == "absent"


def resolve_scheme_paint(
    theme_root: ET.Element,
    scheme: ThemeScheme,
    list_name: str,
    reference: ET.Element,
) -> ET.Element | None:
    """Return the theme paint one format-scheme reference selects.

    ``list_name`` is one of the theme format scheme's paint lists
    (``fillStyleLst``, ``lnStyleLst``, ``effectStyleLst``, ``bgFillStyleLst``).
    The reference's colour replaces every ``phClr`` placeholder inside the
    selected entry, which is how a table border or cell fill inherits the theme
    palette, and index ``0`` selects nothing at all.
    """
    elements = find_ooxml(theme_root, f"{{{A_NS}}}themeElements")
    if elements is None:
        raise ThemeRefusal("theme has no themeElements")
    format_scheme = find_ooxml(elements, f"{{{A_NS}}}fmtScheme")
    if format_scheme is None:
        raise ThemeRefusal("theme has no format scheme for style references")
    listing = find_ooxml(format_scheme, f"{{{A_NS}}}{list_name}")
    if listing is None:
        raise ThemeRefusal(f"theme has no {list_name}")
    styles = list(listing)
    raw_index = reference.get("idx", "0")
    try:
        position = int(raw_index)
    except ValueError as exc:
        raise ThemeRefusal(f"style reference index {raw_index!r} is not numeric") from exc
    if list_name == "bgFillStyleLst" and position > 1000:
        position -= 1000
    if position <= 0:
        return None
    if position > len(styles):
        raise ThemeRefusal(
            f"style reference index {position} exceeds the theme's {list_name} "
            f"({len(styles)} entries)"
        )
    paint = copy.deepcopy(styles[position - 1])
    colors = [
        element for element in list(reference) if element.tag.rsplit("}", 1)[-1] in COLOR_TAGS
    ]
    if colors:
        _substitute_placeholder_color(paint, colors[0], scheme)
    return paint


def _substitute_placeholder_color(
    element: ET.Element, color: ET.Element, scheme: ThemeScheme
) -> None:
    """Replace ``phClr`` references inside a theme paint with a real colour."""
    resolved = resolve_color_element(color, scheme)
    for candidate in element.iter():
        if candidate.tag != ooxml_path(element, f"{{{A_NS}}}schemeClr"):
            continue
        if candidate.get("val") != "phClr":
            continue
        # The placeholder becomes a concrete sRGB colour in place, so the paint
        # stays resolvable by the ordinary colour reader and the transforms the
        # theme style applies on top of the colour are kept.  Clearing the
        # value instead would leave a scheme-colour reference with no name,
        # which is not a colour.
        candidate.tag = ooxml_path(candidate, f"{{{A_NS}}}srgbClr")
        candidate.attrib.clear()
        candidate.set("val", resolved.rgb)
        if resolved.alpha != 1.0:
            candidate.insert(
                0,
                ET.Element(
                    ooxml_path(candidate, f"{{{A_NS}}}alpha"),
                    {"val": f"{resolved.alpha * 100:.6f}%"},
                ),
            )


def _pattern_color(
    pattern: ET.Element,
    role: str,
    scheme: ThemeScheme,
    placeholder: str | None,
) -> ResolvedColor:
    holder = find_ooxml(pattern, f"{{{A_NS}}}{role}")
    if holder is None:
        return ResolvedColor("000000" if role == "fgClr" else "FFFFFF")
    colors = [element for element in list(holder) if element.tag.rsplit("}", 1)[-1] in COLOR_TAGS]
    if len(colors) != 1:
        raise ThemeRefusal(f"pattern {role} needs exactly one colour")
    return resolve_color_element(colors[0], scheme, placeholder=placeholder)


def resolve_paint(
    properties: ET.Element | None,
    scheme: ThemeScheme,
    *,
    placeholder: str | None = None,
    inherit_from: Sequence[ET.Element] = (),
) -> PaintResolution:
    """Resolve the paint of one property holder.

    ``inherit_from`` lists further property holders that supply the paint when
    the first holder carries none, which is how table cell fills and inherited
    shape styles are resolved.
    """
    for candidate in (properties, *inherit_from):
        if candidate is None:
            continue
        for child in list(candidate):
            name = child.tag.rsplit("}", 1)[-1]
            if child.tag != ooxml_path(candidate, f"{{{A_NS}}}{name}") or name not in _FILL_TAGS:
                continue
            if name == "noFill":
                return PaintResolution(None, "none")
            if name == "solidFill":
                colors = [
                    element
                    for element in list(child)
                    if element.tag.rsplit("}", 1)[-1] in COLOR_TAGS
                ]
                if len(colors) != 1:
                    raise ThemeRefusal("solid fill needs exactly one colour")
                return PaintResolution(
                    SolidPaint(resolve_color_element(colors[0], scheme, placeholder=placeholder)),
                    "solid",
                )
            if name == "pattFill":
                preset = child.get("prst")
                if preset not in PRESET_PATTERN_VALUES:
                    raise ThemeRefusal(f"preset pattern {preset!r} is not supported")
                return PaintResolution(
                    PatternPaint(
                        preset=preset,
                        foreground=_pattern_color(child, "fgClr", scheme, placeholder),
                        background=_pattern_color(child, "bgClr", scheme, placeholder),
                    ),
                    "pattern",
                )
            if name == "gradFill":
                flip = child.get("flip")
                if flip not in (None, "none"):
                    raise ThemeRefusal(f"gradient fill flip mode {flip!r} is not supported")
                rot_raw = child.get("rotWithShape", "1")
                if rot_raw not in ("0", "1", "false", "true"):
                    raise ThemeRefusal(f"gradient fill rotWithShape is invalid: {rot_raw!r}")
                rot_with_shape = rot_raw not in ("0", "false")
                path = find_ooxml(child, f"{{{A_NS}}}path")
                linear = find_ooxml(child, f"{{{A_NS}}}lin")
                tile = find_ooxml(child, f"{{{A_NS}}}tileRect")
                if tile is not None and (
                    len(tile)
                    or set(tile.attrib) - {"l", "t", "r", "b"}
                    or any(tile.get(key, "0") != "0" for key in ("l", "t", "r", "b"))
                ):
                    raise ThemeRefusal("expanded or tiled gradient fills are not supported")
                if path is not None:
                    if linear is not None:
                        raise ThemeRefusal(
                            "gradient fill cannot specify both path and linear shade"
                        )
                    path_kind = path.get("path")
                    if path_kind not in {"circle", "rect"}:
                        raise ThemeRefusal(
                            f"path gradient fills are not supported for path {path_kind!r}; "
                            "shape-following shading requires an authored contour distance field"
                        )
                    if not rot_with_shape:
                        raise ThemeRefusal("path gradient rotWithShape=false is not supported")
                    focus_element = find_ooxml(path, f"{{{A_NS}}}fillToRect")
                    if set(path.attrib) - {"path"} or len(path) != (
                        0 if focus_element is None else 1
                    ):
                        raise ThemeRefusal("path gradient has unsupported attributes or children")
                    focus = (0.0, 0.0, 0.0, 0.0)
                    if focus_element is not None:
                        if len(focus_element) or set(focus_element.attrib) - {"l", "t", "r", "b"}:
                            raise ThemeRefusal("path gradient focus has unsupported content")
                        try:
                            focus = tuple(
                                percentage_value(focus_element, focus_element.get(key, "0"))
                                for key in ("l", "t", "r", "b")
                            )
                        except ValueError as exc:
                            raise ThemeRefusal("path gradient focus is not numeric") from exc
                    left, top, right, bottom = focus
                    if (
                        not all(math.isfinite(value) and 0 <= value <= 1 for value in focus)
                        or left + right > 1
                        or top + bottom > 1
                    ):
                        raise ThemeRefusal("path gradient focus must be inside its tile")
                    if path_kind == "circle" and (
                        not math.isclose(left + right, 1) or not math.isclose(top + bottom, 1)
                    ):
                        raise ThemeRefusal(
                            "path gradient fills are not supported for circle with non-point focus"
                        )
                    if path_kind == "circle" and ((left - 0.5) ** 2 + (top - 0.5) ** 2 >= 0.25):
                        raise ThemeRefusal("circle gradient focus must be inside the outer circle")
                else:
                    if linear is None:
                        raise ThemeRefusal("gradient fill must specify a linear or path shade")
                    ang_raw = linear.get("ang", "0")
                    try:
                        ang_val = int(ang_raw)
                    except ValueError as exc:
                        raise ThemeRefusal(
                            f"linear gradient angle {ang_raw!r} is not numeric"
                        ) from exc
                    angle_degrees = (ang_val / 60000.0) % 360.0
                    scaled_raw = linear.get("scaled", "0")
                    if scaled_raw not in ("0", "1", "false", "true"):
                        raise ThemeRefusal(f"linear gradient scaled is invalid: {scaled_raw!r}")
                    scaled = scaled_raw in ("1", "true")
                stop_list = find_ooxml(child, f"{{{A_NS}}}gsLst")
                if stop_list is None:
                    raise ThemeRefusal("gradient fill has no gradient stop list (gsLst)")
                gs_elements = findall_ooxml(stop_list, f"{{{A_NS}}}gs")
                if len(gs_elements) < 2:
                    raise ThemeRefusal("gradient fill requires at least two gradient stops")
                stops: list[GradientStop] = []
                for gs in gs_elements:
                    pos_raw = gs.get("pos")
                    if pos_raw is None:
                        raise ThemeRefusal("gradient stop is missing pos attribute")
                    try:
                        position = percentage_value(gs, pos_raw)
                    except ValueError as exc:
                        raise ThemeRefusal(
                            f"gradient stop position {pos_raw!r} is not numeric"
                        ) from exc
                    if not 0.0 <= position <= 1.0:
                        raise ThemeRefusal("gradient stop position is out of range")
                    colors = [
                        element
                        for element in list(gs)
                        if element.tag.rsplit("}", 1)[-1] in COLOR_TAGS
                    ]
                    if len(colors) != 1:
                        raise ThemeRefusal("gradient stop needs exactly one colour")
                    color = resolve_color_element(colors[0], scheme, placeholder=placeholder)
                    stops.append(GradientStop(position=position, color=color))
                stops.sort(key=lambda s: s.position)
                if path is not None:
                    return PaintResolution(
                        PathGradientPaint(path_kind, tuple(stops), focus), "gradient"
                    )
                return PaintResolution(
                    LinearGradientPaint(
                        angle=angle_degrees,
                        stops=tuple(stops),
                        scaled=scaled,
                        rot_with_shape=rot_with_shape,
                    ),
                    "gradient",
                )
            raise ThemeRefusal(f"{name} is not a supported paint")
    return PaintResolution(None, "absent")
