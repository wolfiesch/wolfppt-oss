"""Color values and editable color text/transform interfaces."""

from __future__ import annotations

import colorsys
import math
import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Any, Self
from xml.etree import ElementTree as ET

from ..dml_fill import (
    color_element,
    color_transforms,
    existing_run_pattern_fill_element,
    pattern_color_element,
    run_solid_fill_element,
    set_color_transforms,
    validate_text_color_element,
)
from ..enum.dml import MSO_COLOR_TYPE, MSO_THEME_COLOR
from ..xml_helpers import STRICT_A_NS, find_ooxml

COLOR_STRING_STYLES = ("hex", "argb", "rgb", "rgba", "hsl", "hsla", "scheme")


class ColorFormatRefusal(ValueError):
    """An unsupported color edit was refused before changing its owner."""


class ColorResolutionRefusal(ColorFormatRefusal):
    """Theme-resolved color text was refused; the owner and its deck stay unchanged."""


class RGBColor(tuple):
    """Immutable ``(r, g, b)`` color value; equal to the matching python-pptx value."""

    def __new__(cls, r: int, g: int, b: int) -> Self:
        for val in (r, g, b):
            if not isinstance(val, int) or val < 0 or val > 255:
                raise ValueError("RGBColor() takes three integer values 0-255")
        return super().__new__(cls, (r, g, b))

    def __str__(self) -> str:
        """Hex string RGB value, like '3C2F80'."""
        return "{:02X}{:02X}{:02X}".format(*self)

    @classmethod
    def from_string(cls, rgb_hex_str: str) -> Self:
        """New instance from an RGB hex string like ``'3C2F80'``."""
        r = int(rgb_hex_str[:2], 16)
        g = int(rgb_hex_str[2:4], 16)
        b = int(rgb_hex_str[4:], 16)
        return cls(r, g, b)


def _number(text: str) -> float:
    if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e[+-]?[0-9]+)?", text) is None:
        raise ColorFormatRefusal(f"invalid color number: {text!r}")
    value = float(text)
    if not math.isfinite(value):
        raise ColorFormatRefusal("color numbers must be finite")
    return value


def _alpha(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ColorFormatRefusal("alpha must be a finite fraction between 0 and 1")
    if not 0 <= value <= 1:
        raise ColorFormatRefusal("alpha must be a finite fraction between 0 and 1")
    return float(value)


def parse_color_string(text: Any) -> tuple[str, Any]:
    """Parse RGB, alpha RGB, ARGB, HSL or scheme text without losing alpha.

    Opaque colors return ``('rgb', 'RRGGBB')`` or ``('scheme', name)``.
    Alpha colors return ``('rgba', ('RRGGBB', alpha))``; alpha is a fraction,
    not an eight-bit channel. HSL uses degrees and percentage saturation/lightness.
    Hex accepts RGB/RGBA shorthand and six/eight digits, with alpha last. The
    explicit ``argb:`` prefix reads alpha first: ``argb:#AARRGGBB`` or ``argb:#ARGB``.
    """
    from ..facade_values import normalize_rgb, normalize_theme_color

    if not isinstance(text, str):
        raise ColorFormatRefusal("colour text must be a str")
    raw = text.strip()
    lowered = raw.lower()
    match = re.fullmatch(r"(rgb|rgba|hsl|hsla)\((.*)\)", lowered)
    if match:
        name, channels = match.groups()
        parts = [part.strip() for part in channels.split(",")]
        count = 4 if name.endswith("a") else 3
        if len(parts) != count:
            raise ColorFormatRefusal(f"{name}() colour needs {count} channels")
        alpha = 1.0
        if count == 4:
            alpha = _alpha(
                _number(parts[3][:-1]) / 100 if parts[3].endswith("%") else _number(parts[3])
            )
        if name.startswith("rgb"):
            if not all(part.isdigit() for part in parts[:3]):
                raise ColorFormatRefusal("rgb() colour needs integer channels")
            try:
                rgb = normalize_rgb(tuple(int(part) for part in parts[:3]))
            except (ValueError, TypeError) as error:
                raise ColorFormatRefusal(str(error)) from error
        else:
            hue = _number(parts[0].removesuffix("deg")) % 360
            if not all(part.endswith("%") for part in parts[1:3]):
                raise ColorFormatRefusal("hsl() saturation and lightness must be percentages")
            saturation, lightness = (_number(part[:-1]) / 100 for part in parts[1:3])
            if not 0 <= saturation <= 1 or not 0 <= lightness <= 1:
                raise ColorFormatRefusal("hsl() percentages must lie between 0 and 100")
            rgb = normalize_rgb(
                tuple(
                    round(channel * 255)
                    for channel in colorsys.hls_to_rgb(hue / 360, lightness, saturation)
                )
            )
        return ("rgba", (rgb, alpha)) if count == 4 else ("rgb", rgb)
    if lowered.startswith("argb:"):
        digits = raw[len("argb:") :].strip().removeprefix("#")
        if re.fullmatch(r"[0-9a-fA-F]{4}|[0-9a-fA-F]{8}", digits) is None:
            raise ColorFormatRefusal("argb colour needs four or eight hex digits, alpha first")
        if len(digits) == 4:
            digits = "".join(char * 2 for char in digits)
        return "rgba", (digits[2:].upper(), int(digits[:2], 16) / 255)
    if lowered.startswith("scheme:"):
        raw = raw[len("scheme:") :].strip()
    else:
        digits = raw.removeprefix("#")
        if len(digits) in {3, 4} and re.fullmatch(r"[0-9a-fA-F]+", digits):
            digits = "".join(char * 2 for char in digits)
        if len(digits) in {6, 8} and re.fullmatch(r"[0-9a-fA-F]+", digits):
            return (
                ("rgba", (digits[:6].upper(), int(digits[6:], 16) / 255))
                if len(digits) == 8
                else ("rgb", digits.upper())
            )
        if raw.startswith("#"):
            raise ColorFormatRefusal("hex colour needs three, four, six or eight digits")
    try:
        return "scheme", normalize_theme_color(raw)
    except (ValueError, TypeError) as error:
        raise ColorFormatRefusal(f"unrecognised colour text: {text!r}") from error


def format_color_string(kind: str, value: Any, style: str = "hex") -> str:
    """Format parsed color text, automatically retaining alpha in RGB/HSL styles."""
    from ..facade_values import normalize_rgb, normalize_theme_color

    if style not in COLOR_STRING_STYLES:
        raise ColorFormatRefusal(f"colour style must be one of {COLOR_STRING_STYLES}")
    if kind == "scheme":
        if style != "scheme":
            raise ColorFormatRefusal(
                f"scheme colour {value!r} has no fixed RGB value; use style 'scheme'"
            )
        try:
            return f"scheme:{normalize_theme_color(value)}"
        except (ValueError, TypeError) as error:
            raise ColorFormatRefusal(str(error)) from error
    alpha = 1.0
    if kind == "rgba":
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ColorFormatRefusal("rgba color must be (RGB hex, alpha fraction)")
        value, alpha = value[0], _alpha(value[1])
    elif kind != "rgb":
        raise ColorFormatRefusal(f"unsupported colour kind {kind!r}")
    try:
        rgb = normalize_rgb(value)
    except (ValueError, TypeError) as error:
        raise ColorFormatRefusal(str(error)) from error
    if style == "hex":
        return f"#{rgb}" + (f"{round(alpha * 255):02X}" if kind == "rgba" else "")
    if style == "argb":
        return f"argb:#{round(alpha * 255):02X}{rgb}"
    if style == "scheme":
        raise ColorFormatRefusal(f"RGB colour #{rgb} is not a scheme colour")
    red, green, blue = (int(rgb[index : index + 2], 16) for index in (0, 2, 4))
    if style in {"rgb", "rgba"}:
        channels = f"{red}, {green}, {blue}"
        name = "rgba" if style == "rgba" or kind == "rgba" else "rgb"
    else:
        hue, lightness, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
        channels = f"{hue * 360:.10g}, {saturation * 100:.10g}%, {lightness * 100:.10g}%"
        name = "hsla" if style == "hsla" or kind == "rgba" else "hsl"
    return f"{name}({channels}" + (f", {alpha:.15g})" if name.endswith("a") else ")")


def color_element_from_string(text: Any) -> ET.Element:
    """Build a fully validated DrawingML color from public color text."""
    kind, value = parse_color_string(text)
    if kind == "rgba":
        rgb, alpha = value
        return color_element({"type": "rgb", "value": rgb, "transforms": [("alpha", alpha)]})
    return color_element({"type": kind, "value": value})


def color_alpha(color: ET.Element | None) -> float:
    """Evaluate alpha transforms in document order, clamping each operation."""
    alpha = 1.0
    for name, value in () if color is None else color_transforms(color):
        if name == "alpha":
            alpha = value
        elif name == "alphaOff":
            alpha += value
        elif name == "alphaMod":
            alpha *= value
        alpha = min(1.0, max(0.0, alpha))
    return alpha


def color_element_to_string(color: ET.Element, style: str = "hex") -> str:
    """Format the stored RGB/scheme base and effective alpha, without resolving themes."""
    name = color.tag.rsplit("}", 1)[-1]
    alpha = color_alpha(color)
    if name == "schemeClr":
        if alpha != 1.0:
            raise ColorFormatRefusal("scheme text cannot represent alpha; read .transforms")
        return format_color_string("scheme", color.get("val"), style)
    if name != "srgbClr":
        raise ColorFormatRefusal(f"color text cannot represent {name!r}; read .element")
    return format_color_string(
        "rgba" if alpha != 1.0 else "rgb",
        (color.get("val"), alpha) if alpha != 1.0 else color.get("val"),
        style,
    )


def resolved_color_string(color: ET.Element, part_owner: Any, style: str = "hex") -> str:
    """Format ``color`` as concrete text through ``part_owner``'s theme and color map.

    ``part_owner`` is the slide, layout, master or notes part the color is drawn on.
    Scheme colors resolve through that part's effective theme (the master theme with
    any layout or slide theme override, including queued theme edits) and the master,
    layout and slide color-map precedence the renderer uses. System colors use their
    stored ``lastClr``. Every ordered transform applies, and the effective alpha is
    kept in the requested RGB, HSL, hex or ARGB style. Nothing is written.
    """
    from dataclasses import replace

    from ..presentation_tags import parse_xml
    from ..render_theme import (
        color_map_from,
        parse_theme_scheme,
        resolve_color_element,
    )
    from ..theme_facade import theme_edits
    from ..xml_helpers import P_NS

    if style not in COLOR_STRING_STYLES:
        raise ColorFormatRefusal(f"colour style must be one of {COLOR_STRING_STYLES}")
    if style == "scheme":
        raise ColorResolutionRefusal("a theme-resolved colour is concrete; use an RGB style")
    presentation = getattr(part_owner, "_presentation", None)
    partname = getattr(part_owner, "partname", None)
    if presentation is None or not isinstance(partname, str) or not partname:
        raise ColorResolutionRefusal(
            "colour has no slide, layout, master or notes part to resolve its theme from"
        )
    try:
        edits = theme_edits(presentation)
        theme = edits.theme_for(part_owner)
        partname = partname.lstrip("/")
        # A master states its own p:clrMap; other parts inherit through p:clrMapOvr.
        mapping = color_map_from(find_ooxml(parse_xml(edits._read(partname)), f"{{{P_NS}}}clrMap"))
        if mapping is None:
            mapping = edits._color_map(partname)
        scheme = replace(parse_theme_scheme(theme._effective_root()), color_map=mapping)
        resolved = resolve_color_element(color, scheme)
    except (ValueError, TypeError, KeyError) as error:
        raise ColorResolutionRefusal(f"cannot resolve colour through its theme: {error}") from error
    if resolved.alpha == 1.0:
        return format_color_string("rgb", resolved.rgb, style)
    return format_color_string("rgba", (resolved.rgb, resolved.alpha), style)


def fill_color_element(parent: ET.Element | None, role: str = "fore") -> ET.Element | None:
    """Read a solid or pattern color without changing its owner."""
    if role not in {"fore", "back"}:
        raise ColorFormatRefusal(f"unsupported fill color role {role!r}")
    if parent is None:
        if role == "back":
            raise ColorFormatRefusal("background color requires a patterned fill")
        return None
    namespace = "http://schemas.openxmlformats.org/drawingml/2006/main"
    pattern = find_ooxml(parent, f"{{{namespace}}}pattFill")
    if pattern is not None:
        holder = find_ooxml(pattern, f"{{{namespace}}}{'bgClr' if role == 'back' else 'fgClr'}")
    else:
        if role == "back":
            raise ColorFormatRefusal("background color requires a patterned fill")
        holder = find_ooxml(parent, f"{{{namespace}}}solidFill")
    if holder is None or not len(holder):
        return None
    color = deepcopy(holder[0])
    for node in color.iter():
        if node.tag.startswith(f"{{{STRICT_A_NS}}}"):
            node.tag = f"{{{namespace}}}{node.tag.rsplit('}', 1)[-1]}"
    return color


def replace_fill_color_element(parent: ET.Element, color: ET.Element, role: str = "fore") -> None:
    """Validate first, then replace only the addressed color choice."""
    detached = deepcopy(color)
    try:
        validate_text_color_element(detached)
    except (ValueError, TypeError, OverflowError) as error:
        raise ColorFormatRefusal(str(error)) from error
    if role not in {"fore", "back"}:
        raise ColorFormatRefusal(f"unsupported fill color role {role!r}")
    namespace = "http://schemas.openxmlformats.org/drawingml/2006/main"
    pattern = parent.find(f"{{{namespace}}}pattFill")
    if pattern is None:
        if role == "back":
            raise ColorFormatRefusal("background color requires a patterned fill")
        holder = run_solid_fill_element(parent)
    else:
        holder = pattern_color_element(
            existing_run_pattern_fill_element(parent), "bgClr" if role == "back" else "fgClr"
        )
        holder.clear()
    holder.append(detached)


class ColorTextAndTransforms:
    """Shared public color operations; owners supply element read/write methods.

    ``_color_element()`` reads without modifying its owner; ``_set_color_element``
    persists a validated detached element using the owner's edit mechanism.
    """

    @property
    def element(self) -> ET.Element | None:
        """A detached color snapshot; assign an element to author any supported color."""
        return deepcopy(self._color_element())

    @element.setter
    def element(self, value: ET.Element) -> None:
        if not isinstance(value, ET.Element):
            raise ColorFormatRefusal("color element must be a DrawingML element")
        color = deepcopy(value)
        try:
            validate_text_color_element(color)
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        self._set_color_element(color)

    @property
    def transforms(self) -> list[tuple[str, float | None]]:
        """Ordered DrawingML transforms; percentages are fractions, angles degrees."""
        color = self._color_element()
        return [] if color is None else color_transforms(color)

    @transforms.setter
    def transforms(self, value: Sequence[Any]) -> None:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise ColorFormatRefusal("color transforms must be an ordered sequence")
        color = deepcopy(self._color_element())
        if color is None:
            raise ColorFormatRefusal("set a color before editing its transforms")
        try:
            set_color_transforms(color, value)
            validate_text_color_element(color)
        except (ValueError, TypeError, OverflowError) as error:
            raise ColorFormatRefusal(str(error)) from error
        self._set_color_element(color)

    @property
    def alpha(self) -> float:
        return color_alpha(self._color_element())

    @alpha.setter
    def alpha(self, value: float) -> None:
        alpha = _alpha(value)
        self.transforms = [
            item for item in self.transforms if item[0] not in {"alpha", "alphaOff", "alphaMod"}
        ] + [("alpha", alpha)]

    def from_string(self, text: Any) -> None:
        self._set_color_element(color_element_from_string(text))

    def to_string(self, style: str = "hex", *, resolve_theme: bool = False) -> str | None:
        """Format the color as text; ``None`` when no color is set.

        By default the stored base and effective alpha are formatted: ``'hex'`` is
        ``#RRGGBB`` or ``#RRGGBBAA`` (alpha last) and ``'argb'`` is ``argb:#AARRGGBB``
        (alpha first). ``resolve_theme=True`` opts into concrete text resolved through
        the owning part's theme and color map with every transform applied; owners
        without a theme context raise :class:`ColorResolutionRefusal`.
        """
        if style not in COLOR_STRING_STYLES:
            raise ColorFormatRefusal(f"colour style must be one of {COLOR_STRING_STYLES}")
        if not isinstance(resolve_theme, bool):
            raise ColorFormatRefusal("resolve_theme must be a bool")
        if resolve_theme and style == "scheme":
            raise ColorResolutionRefusal("a theme-resolved colour is concrete; use an RGB style")
        owner = self._theme_part_owner() if resolve_theme else None
        color = self._color_element()
        if color is None:
            return None
        if not resolve_theme:
            return color_element_to_string(color, style)
        return resolved_color_string(color, owner, style)

    def _theme_part_owner(self) -> Any:
        """The part whose theme and color map resolve this color; owners override."""
        raise ColorResolutionRefusal(
            f"{type(self).__name__} colours have no theme context for resolve_theme=True; "
            "read .element and .transforms instead"
        )


__all__ = [
    "ColorFormatRefusal",
    "ColorResolutionRefusal",
    "ColorTextAndTransforms",
    "MSO_COLOR_TYPE",
    "MSO_THEME_COLOR",
    "RGBColor",
    "color_element_from_string",
    "color_element_to_string",
    "format_color_string",
    "parse_color_string",
    "resolved_color_string",
]
