"""Read and edit theme colour, font and format schemes.

``Presentation.theme_for(master)`` returns the :class:`Theme` a slide, notes
or handout master relates to.  ``Presentation.theme_for(slide)`` (or a slide
layout or notes slide) returns that part's :class:`ThemeOverride`, the
optional ``a:themeOverride`` part (ECMA-376 Part 1, 14.2.8) that replaces the
inherited schemes for that part alone.

``Presentation.theme_for(chart)`` or ``chart.theme`` returns a chart-local
override inheriting from its containing slide. Use ``chart.theme.set(theme)``
to copy a theme's colour, font and format schemes, or edit the override's views
directly. Save and reopen newly authored charts before editing their themes.
Clear the override to resume slide inheritance. Other charts and slide shapes
keep their own themes.

The returned :class:`Theme` or :class:`ThemeOverride` is the owner's theme
manager. ``manager.get_effective(placeholder="accent1")`` returns detached
colour, font and style collections using the renderer's resolvers. Style
matrix placeholders require a shape's reference colour; ``accent1`` is the
documented default. Pass ``color_context`` as a DrawingML ``srgbClr`` element
with optional ordered transforms to resolve an explicit RGB/alpha reference
without editing the palette::

    context = ET.fromstring(
        '<a:srgbClr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'val="336699"><a:alpha val="80000"/></a:srgbClr>'
    )
    effective = manager.get_effective(color_context=context)

The explicit context takes precedence over ``placeholder``; other scheme colours
retain the owner's palette and colour map. Invalid contexts raise ``ThemeRefusal``
without queuing edits. ``manager.extra_color_schemes`` exposes live alternatives
owned by the inherited master theme, even through an override manager::

    palette = dict(theme.color_scheme)
    palette["accent1"] = "336699"
    alternative = theme.extra_color_schemes.add("Brand", palette)
    alternative.name = "Brand revised"
    alternative.color_scheme["accent2"] = "669933"
    override.apply_extra_color_scheme(-1)

``theme.apply_extra_color_scheme(index)`` and the override equivalent copy only
the palette: inherited fonts, styles and existing colour-map overrides are
unchanged. An alternative's optional ``color_map`` is editable metadata and is
not applied with its palette.

Edits change the scheme XML in place, so every shape that references a scheme
colour (``a:schemeClr``), a theme font (``+mj-lt``, ``+mn-ea``, ...) or a style
matrix entry (``a:fillRef idx``) picks up the new value without touching the
shape.  Reads merge queued edits over the loaded package; the next
``Presentation.save`` publishes them.  Everything in a theme part outside the
edited values -- object defaults, extra colour schemes, extensions -- is kept.
"""

from __future__ import annotations

import posixpath
import re
import tempfile
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    CONTENT_TYPES_NS,
    PKG_REL_NS,
    InMemoryPackageSource,
    copy_open_package_with_replacements,
    open_package_source,
    rels_part_for_package_part,
    resolve_package_target,
)
from .presentation_tags import LifecycleRefusal, parse_xml, serialize_xml, xml_string
from .render_theme import (
    THEME_SCHEME_TAGS,
    ThemeEffectiveData,
    ThemeRefusal,
    ThemeScheme,
    color_map_from,
    effective_theme_data,
    override_color_map,
    parse_theme_scheme,
    resolve_color_element,
    theme_with_overrides,
)
from .theme_format_scheme_edits import (
    ThemeEditRefusal,
    ThemeEffectStyle,
    ThemeFillStyle,
    ThemeLineStyle,
    ThemeStyleCollection,
    validate_style_entries,
)
from .xml_helpers import (
    A_NS,
    P_NS,
    R_NS,
    STRICT_R_NS,
    find_ooxml,
    findall_ooxml,
    ooxml_namespace,
    xml_local_name,
)

THEME_OVERRIDE_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.themeOverride+xml"

#: The twelve ``a:clrScheme`` slots, in schema order.
COLOR_SLOTS = (
    "dk1",
    "lt1",
    "dk2",
    "lt2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
)
_COLOR_MAP_SLOTS = (
    "bg1",
    "tx1",
    "bg2",
    "tx2",
    *COLOR_SLOTS[4:],
)

_FILL_TAGS = frozenset({"noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill"})
#: ``a:fmtScheme`` style lists: (list element, admitted entry names).
_STYLE_LISTS = {
    "fill": ("fillStyleLst", _FILL_TAGS),
    "line": ("lnStyleLst", frozenset({"ln"})),
    "effect": ("effectStyleLst", frozenset({"effectStyle"})),
    "background_fill": ("bgFillStyleLst", _FILL_TAGS),
}
_FONT_COLLECTION_ORDER = ("latin", "ea", "cs")
_FONT_FACE_ATTRIBUTES = ("panose", "pitchFamily", "charset")
_HEX_RGB = re.compile(r"#?([0-9A-Fa-f]{6})")
_REL_NAMESPACES = (R_NS, STRICT_R_NS)
_OVERRIDE_RELATIONSHIP_ID = "rIdThemeOverride"
_MASTER_ROOTS = frozenset({"sldMaster", "notesMaster", "handoutMaster"})
_OVERRIDE_ROOTS = frozenset({"sld", "sldLayout", "notes"})

#: ``elements(writable)`` returns the XML element a view reads or edits.
_Access = Callable[[bool], ET.Element]


def _child(parent: ET.Element, name: str) -> ET.Element:
    found = find_ooxml(parent, f"{{{A_NS}}}{name}")
    if found is None:
        raise ThemeRefusal(f"{xml_local_name(parent.tag)} has no {name}")
    return found


def _drawing(parent: ET.Element, name: str) -> str:
    return f"{{{ooxml_namespace(parent, A_NS)}}}{name}"


def _relationship_ids(element: ET.Element) -> set[str]:
    return {
        value
        for node in element.iter()
        for name, value in node.attrib.items()
        if name.startswith("{") and name[1:].split("}", 1)[0] in _REL_NAMESPACES
    }


def _r_namespace(drawing_namespace: str) -> str:
    return R_NS if drawing_namespace == A_NS else STRICT_R_NS


def _fragment_xml(element: ET.Element) -> str:
    """Serialize one scheme entry with the conventional ``a:``/``r:`` prefixes."""
    fragment = deepcopy(element)
    registry = dict(ET._namespace_map)
    try:
        # parse_xml keeps declarations as attributes; turn them back into
        # prefix registrations so ElementTree declares each binding once.
        for node in fragment.iter():
            for name in [n for n in node.attrib if n == "xmlns" or n.startswith("xmlns:")]:
                prefix = name.partition(":")[2]
                if prefix and not re.fullmatch(r"ns\d+", prefix):
                    ET.register_namespace(prefix, node.attrib[name])
                del node.attrib[name]
        namespace = ooxml_namespace(element, A_NS)
        ET.register_namespace("a", namespace)
        ET.register_namespace("r", _r_namespace(namespace))
        return ET.tostring(fragment, encoding="unicode")
    finally:
        ET._namespace_map.clear()
        ET._namespace_map.update(registry)


def _rgb(value: Any) -> str:
    if isinstance(value, tuple) and len(value) == 3:
        if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value):
            raise ThemeEditRefusal("an RGB colour needs three channels in 0..255")
        return "{:02X}{:02X}{:02X}".format(*value)
    if not isinstance(value, str):
        raise TypeError("a scheme colour is an 'RRGGBB' hex string or RGBColor")
    match = _HEX_RGB.fullmatch(_theme_string(value, "scheme colour").strip())
    if match is None:
        raise ThemeEditRefusal(f"scheme colour {value!r} is not 'RRGGBB' hex")
    return match.group(1).upper()


def _theme_string(value: Any, name: str) -> str:
    """Validate XML content without changing legacy non-string TypeErrors."""
    try:
        return xml_string(value, name)
    except LifecycleRefusal as exc:
        raise ThemeEditRefusal(str(exc)) from exc


def _extra_name(value: Any) -> str:
    try:
        name = _theme_string(value, "extra colour scheme name")
    except TypeError as exc:
        raise ThemeEditRefusal(str(exc)) from exc
    if not name.strip():
        raise ThemeEditRefusal("an extra colour scheme needs a non-empty name")
    return name


def _palette(values: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(values, Mapping):
        raise ThemeEditRefusal("a colour palette must be a mapping")
    if set(values) != set(COLOR_SLOTS):
        raise ThemeEditRefusal("a colour palette needs exactly the twelve colour slots")
    try:
        return {slot: _rgb(values[slot]) for slot in COLOR_SLOTS}
    except TypeError as exc:
        raise ThemeEditRefusal(str(exc)) from exc


def _color_mapping(values: Mapping[str, str] | None) -> dict[str, str] | None:
    if values is None:
        return None
    if not isinstance(values, Mapping):
        raise ThemeEditRefusal("a colour map must be a mapping or None")
    if set(values) != set(_COLOR_MAP_SLOTS):
        raise ThemeEditRefusal("a colour map needs exactly the twelve mapping slots")
    mapping = {}
    for slot in _COLOR_MAP_SLOTS:
        target = values[slot]
        if not isinstance(target, str) or target not in COLOR_SLOTS:
            raise ThemeEditRefusal(
                f"colour map {slot!r} must target one of the twelve colour slots"
            )
        mapping[slot] = target
    return mapping


def _replace_rgb(element: ET.Element, rgb: str) -> None:
    """Replace a slot's colour, preserving its extensions and their position."""
    colors = [
        child
        for child in element
        if isinstance(child.tag, str)
        and child.tag.startswith(f"{{{ooxml_namespace(element, A_NS)}}}")
        and xml_local_name(child.tag) != "extLst"
    ]
    index = list(element).index(colors[0]) if colors else 0
    for child in colors:
        element.remove(child)
    element.insert(index, ET.Element(_drawing(element, "srgbClr"), {"val": rgb}))


class ColorScheme(MutableMapping[str, str]):
    """The twelve slots of one ``a:clrScheme`` as ``RRGGBB`` strings.

    Reads resolve ``a:sysClr`` to its ``lastClr`` and apply any colour
    transforms.  Writing a slot stores ``a:srgbClr``.  The slot set is fixed by
    the schema, so slots cannot be added or removed.
    """

    def __init__(self, elements: _Access) -> None:
        self._elements = elements

    def _slot(self, slot: str, writable: bool) -> ET.Element:
        if slot not in COLOR_SLOTS:
            raise KeyError(slot)
        return _child(self._elements(writable), slot)

    @property
    def name(self) -> str:
        return self._elements(False).get("name", "")

    @name.setter
    def name(self, value: str) -> None:
        name = _theme_string(value, "colour scheme name")
        self._elements(True).set("name", name)

    def __getitem__(self, slot: str) -> str:
        colors = [
            c
            for c in self._slot(slot, False)
            if isinstance(c.tag, str) and xml_local_name(c.tag) != "extLst"
        ]
        if len(colors) != 1:
            raise ThemeRefusal(f"theme colour {slot!r} needs exactly one colour")
        return resolve_color_element(colors[0], ThemeScheme(colors={})).rgb

    def __setitem__(self, slot: str, value: Any) -> None:
        rgb = _rgb(value)
        element = self._slot(slot, True)
        _replace_rgb(element, rgb)

    def __delitem__(self, slot: str) -> None:
        raise TypeError("a colour scheme always has its twelve slots")

    def __iter__(self) -> Iterator[str]:
        return iter(COLOR_SLOTS)

    def __len__(self) -> int:
        return len(COLOR_SLOTS)

    def __repr__(self) -> str:
        return f"ColorScheme({self.name!r}, {dict(self)!r})"

    def get_effective(self) -> Mapping[str, str]:
        """Return all twelve slots using the renderer's recursive colour resolver."""
        root = ET.Element(f"{{{A_NS}}}theme")
        elements = ET.SubElement(root, f"{{{A_NS}}}themeElements")
        elements.append(deepcopy(self._elements(False)))
        return dict(parse_theme_scheme(root).colors)


class ThemeFonts:
    """One ``a:majorFont`` or ``a:minorFont`` collection.

    ``latin``, ``east_asian`` and ``complex_script`` are the collection's
    primary typefaces; ``supplemental`` maps ISO 15924 script codes to the
    per-script ``a:font`` entries.  Changing a typeface drops the old face's
    ``panose``, ``pitchFamily`` and ``charset`` hints, which describe that face.
    """

    def __init__(self, elements: _Access) -> None:
        self._elements = elements

    def _typeface(self, name: str) -> str:
        found = find_ooxml(self._elements(False), f"{{{A_NS}}}{name}")
        return "" if found is None else found.get("typeface", "")

    def _set_typeface(self, name: str, value: str) -> None:
        typeface = _theme_string(value, "typeface")
        collection = self._elements(True)
        element = find_ooxml(collection, f"{{{A_NS}}}{name}")
        if element is None:
            # latin, ea and cs lead the collection in that order.
            index = sum(
                1
                for local in _FONT_COLLECTION_ORDER[: _FONT_COLLECTION_ORDER.index(name)]
                if find_ooxml(collection, f"{{{A_NS}}}{local}") is not None
            )
            element = ET.Element(_drawing(collection, name))
            collection.insert(index, element)
        if element.get("typeface") != typeface:
            for attribute in _FONT_FACE_ATTRIBUTES:
                element.attrib.pop(attribute, None)
        element.set("typeface", typeface)

    @property
    def latin(self) -> str:
        return self._typeface("latin")

    @latin.setter
    def latin(self, value: str) -> None:
        self._set_typeface("latin", value)

    @property
    def east_asian(self) -> str:
        return self._typeface("ea")

    @east_asian.setter
    def east_asian(self, value: str) -> None:
        self._set_typeface("ea", value)

    @property
    def complex_script(self) -> str:
        return self._typeface("cs")

    @complex_script.setter
    def complex_script(self, value: str) -> None:
        self._set_typeface("cs", value)

    @property
    def supplemental(self) -> Mapping[str, str]:
        return {
            font.get("script", ""): font.get("typeface", "")
            for font in findall_ooxml(self._elements(False), f"{{{A_NS}}}font")
        }

    def set_supplemental(self, script: str, typeface: str | None) -> None:
        """Set (or with ``None`` remove) the typeface for one script code."""
        script = _theme_string(script, "script")
        if not script:
            raise ThemeEditRefusal("a supplemental font needs a script code")
        face = None if typeface is None else _theme_string(typeface, "typeface")
        collection = self._elements(True)
        fonts = findall_ooxml(collection, f"{{{A_NS}}}font")
        existing = next((f for f in fonts if f.get("script") == script), None)
        if face is None:
            if existing is not None:
                collection.remove(existing)
            return
        if existing is None:
            extensions = find_ooxml(collection, f"{{{A_NS}}}extLst")
            index = len(collection) if extensions is None else list(collection).index(extensions)
            existing = ET.Element(_drawing(collection, "font"), {"script": script})
            collection.insert(index, existing)
        existing.set("typeface", face)

    def __repr__(self) -> str:
        return (
            f"ThemeFonts(latin={self.latin!r}, east_asian={self.east_asian!r}, "
            f"complex_script={self.complex_script!r})"
        )


class FontScheme:
    """One ``a:fontScheme``: the major (heading) and minor (body) fonts."""

    def __init__(self, elements: _Access) -> None:
        self._elements = elements
        self.major = ThemeFonts(lambda writable: _child(elements(writable), "majorFont"))
        self.minor = ThemeFonts(lambda writable: _child(elements(writable), "minorFont"))

    @property
    def name(self) -> str:
        return self._elements(False).get("name", "")

    @name.setter
    def name(self, value: str) -> None:
        name = _theme_string(value, "font scheme name")
        self._elements(True).set("name", name)


def _style_list_property(kind: str) -> property:
    list_name, admitted = _STYLE_LISTS[kind]

    def getter(self: FormatScheme) -> tuple[str, ...]:
        styles = _child(self._elements(False), list_name)
        return tuple(_fragment_xml(entry) for entry in styles)

    def setter(self: FormatScheme, values: Sequence[str | ET.Element]) -> None:
        namespace = ooxml_namespace(self._elements(False), A_NS)
        entries = validate_style_entries(
            values, namespace, admitted, list_name, self._relationship_ids()
        )
        styles = _child(self._elements(True), list_name)
        for child in list(styles):
            styles.remove(child)
        styles.extend(entries)

    return property(
        getter,
        setter,
        doc=f"``a:{list_name}`` entries as DrawingML XML strings (at least three).",
    )


def _typed_style_list_property(kind: str, style_type: type) -> property:
    list_name, admitted = _STYLE_LISTS[kind]

    def getter(self: FormatScheme) -> ThemeStyleCollection:
        return ThemeStyleCollection(
            self._elements, self._relationship_ids, list_name, admitted, style_type, _fragment_xml
        )

    def setter(self: FormatScheme, values: Sequence) -> None:
        getter(self)[:] = values

    return property(getter, setter)


class FormatScheme:
    """One ``a:fmtScheme``: the style matrix shapes reference by index.

    ``a:fillRef idx="1"`` selects ``fill_styles[0]``, ``idx="1001"`` selects
    ``background_fill_styles[0]``, and likewise for lines and effects.
    XML tuple properties remain source-compatible. Use the live typed ``fills``,
    ``lines``, ``effects`` and ``background_fills`` collections for indexed edits,
    replacement, ``add`` and ``remove``. For example::

        scheme.fills[0].fill.fore_color.rgb = "336699"
        scheme.lines[0].line.width = 127000
        scheme.effects[0].effects = EffectListSpec()

    Each typed mutation reuses a detached shape codec, validates the resulting
    entry, then updates theme XML without using any slide edit queue.

    Validate malformed colours, numeric line/shadow values and relationship
    references before modifying a scheme. Raise ``ThemeEditRefusal`` for
    invalid XML/content; preserve valid opaque effects and render omissions.
    """

    fill_styles = _style_list_property("fill")
    line_styles = _style_list_property("line")
    effect_styles = _style_list_property("effect")
    background_fill_styles = _style_list_property("background_fill")

    fills = _typed_style_list_property("fill", ThemeFillStyle)
    lines = _typed_style_list_property("line", ThemeLineStyle)
    effects = _typed_style_list_property("effect", ThemeEffectStyle)
    background_fills = _typed_style_list_property("background_fill", ThemeFillStyle)

    def __init__(self, elements: _Access, relationship_ids: Callable[[], set[str]]) -> None:
        self._elements = elements
        self._relationship_ids = relationship_ids

    @property
    def name(self) -> str:
        return self._elements(False).get("name", "")

    @name.setter
    def name(self, value: str) -> None:
        name = _theme_string(value, "format scheme name")
        self._elements(True).set("name", name)


class _ExtraPalette(ColorScheme):
    """An editable alternative retaining recursive palette reads."""

    @ColorScheme.name.setter
    def name(self, value: str) -> None:
        name = _extra_name(value)
        self._elements(True).set("name", name)

    def __getitem__(self, slot: str) -> str:
        if slot not in COLOR_SLOTS:
            raise KeyError(slot)
        return self.get_effective()[slot]

    def __setitem__(self, slot: str, value: Any) -> None:
        if slot not in COLOR_SLOTS:
            raise KeyError(slot)
        try:
            rgb = _rgb(value)
        except TypeError as exc:
            raise ThemeEditRefusal(str(exc)) from exc
        self._slot(slot, False)
        _replace_rgb(self._slot(slot, True), rgb)


class _ExtraColorMap(MutableMapping[str, str]):
    """A live complete colour map; use the owning property to remove it."""

    def __init__(self, elements: _Access) -> None:
        self._elements = elements

    def __getitem__(self, slot: str) -> str:
        if slot not in _COLOR_MAP_SLOTS:
            raise KeyError(slot)
        return self._elements(False).attrib[slot]

    def __setitem__(self, slot: str, value: str) -> None:
        if slot not in _COLOR_MAP_SLOTS:
            raise KeyError(slot)
        mapping = _color_mapping({**dict(self), slot: value})
        assert mapping is not None
        self._elements(True).set(slot, mapping[slot])

    def __delitem__(self, slot: str) -> None:
        raise TypeError("a colour map always has its twelve slots")

    def __iter__(self) -> Iterator[str]:
        mapping = color_map_from(self._elements(False))
        return iter(() if mapping is None else mapping)

    def __len__(self) -> int:
        mapping = color_map_from(self._elements(False))
        return 0 if mapping is None else len(mapping)


class ExtraColorScheme:
    """One live editable ``a:extraClrScheme`` (ECMA-376 Part 1 §20.1.6.4).

    ``extra.name = "Brand"`` renames the palette; ``extra.color_scheme`` allows
    individual slot edits or replacement with a complete twelve-slot mapping.
    ``extra.color_map`` is a live mapping when present. Assign a complete map
    to replace it or ``None`` to remove it. Applying an alternative copies only
    its palette, never this metadata map or an owner's colour-map override.
    """

    def __init__(self, elements: _Access) -> None:
        self._elements = elements

    @property
    def name(self) -> str:
        return self.color_scheme.name

    @name.setter
    def name(self, value: str) -> None:
        self.color_scheme.name = value

    @property
    def color_scheme(self) -> ColorScheme:
        return _ExtraPalette(lambda writable: _child(self._elements(writable), "clrScheme"))

    @color_scheme.setter
    def color_scheme(self, values: Mapping[str, Any]) -> None:
        palette = _palette(values)
        replacement = deepcopy(_child(self._elements(False), "clrScheme"))
        for slot, rgb in palette.items():
            _replace_rgb(_child(replacement, slot), rgb)
        element = self._elements(True)
        current = _child(element, "clrScheme")
        element[list(element).index(current)] = replacement

    @property
    def color_map(self) -> MutableMapping[str, str] | None:
        mapping = color_map_from(find_ooxml(self._elements(False), f"{{{A_NS}}}clrMap"))
        if mapping is None:
            return None
        return _ExtraColorMap(lambda writable: _child(self._elements(writable), "clrMap"))

    @color_map.setter
    def color_map(self, values: Mapping[str, str] | None) -> None:
        mapping = _color_mapping(values)
        element = self._elements(True)
        current = find_ooxml(element, f"{{{A_NS}}}clrMap")
        if mapping is None:
            if current is not None:
                element.remove(current)
            return
        if current is None:
            current = ET.Element(_drawing(element, "clrMap"))
            scheme = _child(element, "clrScheme")
            element.insert(list(element).index(scheme) + 1, current)
        current.attrib.update(mapping)


class ExtraColorSchemeCollection(Sequence[ExtraColorScheme]):
    """Live alternatives in package order, owned by the inherited master theme.

    ``add(name, colors, color_map=None)`` appends a named complete palette and
    returns its editable view. Names need not be unique; indices, including
    negative ones, select alternatives. Slicing returns a tuple of live views.
    Adding through an override manager edits its inherited master theme, not
    its override. A previously obtained collection sees subsequent additions.
    """

    def __init__(self, roots: _Access) -> None:
        self._roots = roots
        self._items: list[ExtraColorScheme] = []

    def _entries(self, writable: bool) -> list[ET.Element]:
        listing = find_ooxml(self._roots(writable), f"{{{A_NS}}}extraClrSchemeLst")
        return [] if listing is None else findall_ooxml(listing, f"{{{A_NS}}}extraClrScheme")

    def __len__(self) -> int:
        return len(self._entries(False))

    def __getitem__(self, index: int | slice) -> ExtraColorScheme | tuple[ExtraColorScheme, ...]:
        count = len(self)
        while len(self._items) < count:
            position = len(self._items)
            self._items.append(
                ExtraColorScheme(
                    lambda writable, position=position: self._entries(writable)[position]
                )
            )
        if isinstance(index, slice):
            return tuple(self._items[position] for position in range(count)[index])
        position = range(count)[index]
        return self._items[position]

    def add(
        self,
        name: str,
        colors: Mapping[str, Any],
        color_map: Mapping[str, str] | None = None,
    ) -> ExtraColorScheme:
        """Append a complete alternative after validating every input atomically."""
        name = _extra_name(name)
        palette = _palette(colors)
        mapping = _color_mapping(color_map)
        source = self._roots(False)
        extra = ET.Element(_drawing(source, "extraClrScheme"))
        scheme = ET.SubElement(extra, _drawing(source, "clrScheme"), {"name": name})
        for slot, rgb in palette.items():
            entry = ET.SubElement(scheme, _drawing(source, slot))
            ET.SubElement(entry, _drawing(source, "srgbClr"), {"val": rgb})
        if mapping is not None:
            ET.SubElement(extra, _drawing(source, "clrMap"), mapping)
        root = self._roots(True)
        listing = find_ooxml(root, f"{{{A_NS}}}extraClrSchemeLst")
        if listing is None:
            # themeElements, objectDefaults, extraClrSchemeLst, custClrLst, extLst.
            later = [
                child
                for child in root
                if isinstance(child.tag, str)
                and child.tag
                in {
                    _drawing(root, "custClrLst"),
                    _drawing(root, "extLst"),
                }
            ]
            index = list(root).index(later[0]) if later else len(root)
            listing = ET.Element(_drawing(root, "extraClrSchemeLst"))
            root.insert(index, listing)
        extensions = find_ooxml(listing, f"{{{A_NS}}}extLst")
        index = len(listing) if extensions is None else list(listing).index(extensions)
        listing.insert(index, extra)
        return self[-1]


class _Schemes:
    """The three scheme views over one scheme-owning element source."""

    _edits: ThemeEdits

    def _scheme(self, name: str, writable: bool) -> ET.Element:
        raise NotImplementedError

    def _scheme_rel_source(self) -> str:
        """The part whose relationships the schemes' ``r:`` ids resolve in."""
        raise NotImplementedError

    def _scheme_relationship_ids(self) -> set[str]:
        return self._edits._relationship_ids_of(self._scheme_rel_source())

    @property
    def color_scheme(self) -> ColorScheme:
        return ColorScheme(lambda writable: self._scheme("clrScheme", writable))

    @property
    def font_scheme(self) -> FontScheme:
        return FontScheme(lambda writable: self._scheme("fontScheme", writable))

    @property
    def format_scheme(self) -> FormatScheme:
        return FormatScheme(
            lambda writable: self._scheme("fmtScheme", writable),
            self._scheme_relationship_ids,
        )

    def _effective_root(self) -> ET.Element:
        raise NotImplementedError

    def _extra_root(self, writable: bool) -> ET.Element:
        """The inherited master theme that owns alternative palettes."""
        raise NotImplementedError

    @property
    def extra_color_schemes(self) -> ExtraColorSchemeCollection:
        return ExtraColorSchemeCollection(self._extra_root)

    def get_effective(
        self, *, placeholder: str = "accent1", color_context: ET.Element | None = None
    ) -> ThemeEffectiveData:
        """Snapshot styles using a scheme slot or explicit DrawingML RGB context.

        ``color_context`` takes precedence over ``placeholder``. Supply a
        Transitional or Strict ``srgbClr`` element; alpha and other ordered
        colour transforms use the renderer's validation and resolution rules.
        Neither the input element nor the theme palette is changed.
        """
        mapping = self._edits._color_map(self._owner) if isinstance(self, ThemeOverride) else None
        return effective_theme_data(
            self._effective_root(),
            color_map=mapping,
            placeholder=placeholder,
            color_context=color_context,
        )


class Theme(_Schemes):
    """The theme part one slide, notes or handout master relates to.

    ``extra_color_schemes.add("Brand", dict(color_scheme))`` creates an editable
    alternative. ``apply_extra_color_scheme(index)`` makes its palette active
    without applying the alternative's optional colour map.
    """

    def __init__(self, edits: ThemeEdits, partname: str) -> None:
        self._edits = edits
        self._partname = partname

    @property
    def partname(self) -> str:
        return "/" + self._partname

    @property
    def name(self) -> str:
        return self._edits._theme_root(self._partname, False).get("name", "")

    @name.setter
    def name(self, value: str) -> None:
        name = _theme_string(value, "theme name")
        root = self._edits._theme_root(self._partname, True)
        root.set("name", name)

    def _scheme(self, name: str, writable: bool) -> ET.Element:
        root = self._edits._theme_root(self._partname, writable)
        return _child(_child(root, "themeElements"), name)

    def _scheme_rel_source(self) -> str:
        return self._partname

    def _effective_root(self) -> ET.Element:
        return self._edits._theme_root(self._partname, False)

    def _extra_root(self, writable: bool) -> ET.Element:
        return self._edits._theme_root(self._partname, writable)

    def apply_extra_color_scheme(self, index: int) -> None:
        """Copy an alternative palette only, preserving fonts, styles and maps."""
        alternative = self.extra_color_schemes[index]
        replacement = deepcopy(_child(alternative._elements(False), "clrScheme"))
        elements = _child(self._edits._theme_root(self._partname, False), "themeElements")
        _child(elements, "clrScheme")
        elements = _child(self._edits._theme_root(self._partname, True), "themeElements")
        current = _child(elements, "clrScheme")
        elements[list(elements).index(current)] = replacement

    def __repr__(self) -> str:
        return f"Theme({self.partname!r}, name={self.name!r})"


class ThemeOverride(_Schemes):
    """The optional ``a:themeOverride`` of a slide, layout, notes slide or chart.

    While no override is set, the scheme views read the inherited schemes: a
    slide inherits its layout's override, else the slide master's theme; a
    layout inherits its master's theme and a notes slide its notes master's.
    A chart inherits its containing slide's effective theme.
    The first write through a scheme view sets the override from the inherited
    schemes, as :meth:`set` does, and edits only the override.  :meth:`clear`
    removes it so the part follows its master again.

    Alternatives always belong to the inherited master theme, not the copied
    override. ``extra_color_schemes.add("Brand", palette)`` edits that master;
    ``apply_extra_color_scheme(index)`` copies only its palette into this
    override and ignores the alternative's accompanying colour map.
    """

    def __init__(self, edits: ThemeEdits, owner: str) -> None:
        self._edits = edits
        self._owner = owner

    @property
    def owner_partname(self) -> str:
        return "/" + self._owner

    @property
    def is_set(self) -> bool:
        return self._edits._override_root(self._owner) is not None

    @property
    def inherited(self) -> Theme | ThemeOverride:
        """The theme or override this part follows when no override is set."""
        kind, partname = self._edits._base(self._owner)
        if kind == "theme":
            return self._edits._theme(partname)
        return self._edits._override(partname)

    def set(self, source: Theme | ThemeOverride | None = None) -> None:
        """Set the override to copies of ``source``'s schemes.

        ``source`` defaults to the inherited schemes.  An already set override
        is replaced.
        """
        if source is None:
            source = self.inherited
        if not isinstance(source, (Theme, ThemeOverride)) or source._edits is not self._edits:
            raise ThemeEditRefusal("source must be a theme of this presentation")
        schemes = {name: deepcopy(source._scheme(name, False)) for name in THEME_SCHEME_TAGS}
        self._edits._set_override(self._owner, schemes, source._scheme_rel_source())

    def clear(self) -> None:
        """Remove the override; the part follows its inherited theme again."""
        self._edits._clear_override(self._owner)

    def apply_extra_color_scheme(self, index: int) -> None:
        """Copy a master palette only, preserving fonts, styles and owner maps."""
        alternative = self.extra_color_schemes[index]
        replacement = deepcopy(_child(alternative._elements(False), "clrScheme"))
        current = self._scheme("clrScheme", True)
        root = self._edits._override_root(self._owner)
        assert root is not None
        root[list(root).index(current)] = replacement

    def _extra_root(self, writable: bool) -> ET.Element:
        return self.inherited._extra_root(writable)

    def _effective_root(self) -> ET.Element:
        return theme_with_overrides(
            self.inherited._effective_root(),
            (self._edits._override_root(self._owner),),
        )

    def _scheme(self, name: str, writable: bool) -> ET.Element:
        root = self._edits._override_root(self._owner)
        if root is None:
            if not writable:
                return self.inherited._scheme(name, False)
            self.set()
            root = self._edits._override_root(self._owner)
            assert root is not None
        found = find_ooxml(root, f"{{{A_NS}}}{name}")
        if found is not None:
            if writable:
                self._edits._touch_override(self._owner)
            return found
        inherited = self.inherited
        if not writable:
            return inherited._scheme(name, False)
        # Materialize the missing scheme from the inherited one, in schema order.
        copy = deepcopy(inherited._scheme(name, False))
        position = THEME_SCHEME_TAGS.index(name)
        index = sum(
            1
            for earlier in THEME_SCHEME_TAGS[:position]
            if find_ooxml(root, f"{{{A_NS}}}{earlier}") is not None
        )
        root.insert(index, copy)
        self._edits._touch_override(self._owner)
        return copy

    def _scheme_rel_source(self) -> str:
        root = self._edits._override_root(self._owner)
        if root is None:
            return self.inherited._scheme_rel_source()
        return self._edits._override_rel_source(self._owner)

    def __repr__(self) -> str:
        return f"ThemeOverride({self.owner_partname!r}, is_set={self.is_set})"


class _Pending:
    """One queued override: the root to write (None clears) and its rel source."""

    __slots__ = ("rel_source", "root")

    def __init__(self, root: ET.Element | None, rel_source: str) -> None:
        self.root = root
        self.rel_source = rel_source


class ThemeEdits:
    """Queued theme and theme-override edits for one presentation."""

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation
        self._loaded_from: Any = None
        self._names: set[str] = set()
        self._rels: dict[str, list[tuple[str, str, str, bool]]] = {}
        self._roots: dict[str, ET.Element] = {}
        self._dirty: set[str] = set()
        self._overrides: dict[str, _Pending] = {}
        self._facades: dict[str, Theme | ThemeOverride] = {}
        self._chart_owners: dict[str, str] = {}

    # -- package reads ------------------------------------------------------

    def _sync(self) -> None:
        """Re-read package facts when the presentation moved to a new source.

        Queued edits survive a source change; only a published save clears
        them (see :func:`staged_theme_edits`).
        """
        presentation = self._presentation
        if presentation._disposed:
            raise RuntimeError("presentation is disposed")
        if self._loaded_from is not presentation._source_path:
            self._loaded_from = presentation._source_path
            self._rels = {}
            self._roots = {part: self._roots[part] for part in self._dirty}
            with open_package_source(presentation._source_path) as package:
                self._names = set(package.namelist())

    def _published(self) -> None:
        """Forget the queued edits once a save published them."""
        self._loaded_from = None
        self._dirty.clear()
        self._overrides.clear()
        self._roots.clear()

    def _read(self, partname: str) -> bytes:
        with open_package_source(self._presentation._source_path) as package:
            return package.read(partname)

    def _relationships(self, partname: str) -> list[tuple[str, str, str, bool]]:
        """``(id, type, absolute target or URL, external)`` for one part."""
        self._sync()
        cached = self._rels.get(partname)
        if cached is None:
            rels_name = rels_part_for_package_part(partname)
            cached = []
            if rels_name in self._names:
                root = ET.fromstring(self._read(rels_name))
                for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
                    external = rel.get("TargetMode") == "External"
                    target = rel.get("Target", "")
                    if not external:
                        target = resolve_package_target(partname, target)
                    cached.append((rel.get("Id", ""), rel.get("Type", ""), target, external))
            self._rels[partname] = cached
        return cached

    def _related(self, partname: str, kind: str) -> str | None:
        for _, rel_type, target, external in self._relationships(partname):
            if not external and rel_type.rsplit("/", 1)[-1] == kind:
                return target
        return None

    def _relationship_ids_of(self, partname: str) -> set[str]:
        return {rel_id for rel_id, *_ in self._relationships(partname)}

    def _part_root_name(self, partname: str) -> str:
        self._sync()
        if partname not in self._names:
            raise LifecycleRefusal(
                f"{partname!r} is not in the saved package; save the presentation "
                "before editing its theme"
            )
        return xml_local_name(ET.fromstring(self._read(partname)).tag)

    # -- facades ------------------------------------------------------------

    def theme_for(self, owner: Any) -> Theme | ThemeOverride:
        from .chart_facade import Chart

        if isinstance(owner, Chart):
            slide = owner._shape._slide
            if slide._presentation is not self._presentation:
                raise ThemeEditRefusal("chart must belong to this presentation")
            if owner._shape._payload.get("_pending_shape") or owner._shape._payload.get(
                "_pending_group_child"
            ):
                raise LifecycleRefusal("save and reopen the chart before editing its theme")
            partname = owner.part.partname.lstrip("/")
            self._part_root_name(partname)
            root = parse_xml(self._read(partname))
            if root.tag not in {
                "{http://schemas.openxmlformats.org/drawingml/2006/chart}chartSpace",
                "{http://purl.oclc.org/ooxml/drawingml/chart}chartSpace",
            }:
                raise ThemeEditRefusal("chart theme edits require a classic chartSpace part")
            self._chart_owners[partname] = slide.partname.lstrip("/")
            return self._override(partname)
        partname = getattr(owner, "partname", None)
        if not isinstance(partname, str) or not partname:
            raise TypeError("theme_for needs a master, layout, slide or notes slide")
        if getattr(owner, "_presentation", None) is not self._presentation:
            raise ValueError("owner must belong to this presentation")
        partname = partname.lstrip("/")
        root_name = self._part_root_name(partname)
        if root_name in _MASTER_ROOTS:
            theme_part = self._related(partname, "theme")
            if theme_part is None or theme_part not in self._names:
                raise LifecycleRefusal(f"{partname!r} relates no theme part")
            return self._theme(theme_part)
        if root_name in _OVERRIDE_ROOTS:
            return self._override(partname)
        raise TypeError(f"{partname!r} ({root_name}) has no theme")

    def _theme(self, partname: str) -> Theme:
        self._sync()
        facade = self._facades.get(partname)
        if not isinstance(facade, Theme):
            facade = self._facades[partname] = Theme(self, partname)
        return facade

    def _override(self, owner: str) -> ThemeOverride:
        self._sync()
        facade = self._facades.get(owner)
        if not isinstance(facade, ThemeOverride):
            facade = self._facades[owner] = ThemeOverride(self, owner)
        return facade

    def _base(self, owner: str) -> tuple[str, str]:
        """What ``owner`` inherits: ``("override", layout)`` or ``("theme", part)``."""
        if owner in self._chart_owners:
            return ("override", self._chart_owners[owner])
        layout = self._related(owner, "slideLayout")
        if layout is not None:
            return ("override", layout)
        master = self._related(owner, "slideMaster") or self._related(owner, "notesMaster")
        theme = None if master is None else self._related(master, "theme")
        if theme is None or theme not in self._names:
            raise LifecycleRefusal(f"{owner!r} inherits no theme part")
        return ("theme", theme)

    def _color_map(self, owner: str) -> Mapping[str, str] | None:
        """Mirror master/layout/slide colour-map precedence used by rendering."""
        if owner in self._chart_owners:
            root = parse_xml(self._read(owner))
            chart_ns = "http://schemas.openxmlformats.org/drawingml/2006/chart"
            return color_map_from(find_ooxml(root, f"{{{chart_ns}}}clrMapOvr")) or self._color_map(
                self._chart_owners[owner]
            )
        layout = self._related(owner, "slideLayout")
        master = self._related(owner, "slideMaster") or self._related(owner, "notesMaster")
        if layout is not None:
            master = self._related(layout, "slideMaster")
        master_map = None
        if master is not None:
            master_root = parse_xml(self._read(master))
            master_map = color_map_from(find_ooxml(master_root, f"{{{P_NS}}}clrMap"))
        inherited = self._color_map(layout) if layout is not None else master_map
        root = parse_xml(self._read(owner))
        return override_color_map(
            find_ooxml(root, f"{{{P_NS}}}clrMapOvr"), inherited, master=master_map
        )

    # -- theme roots --------------------------------------------------------

    def _theme_root(self, partname: str, writable: bool) -> ET.Element:
        self._sync()
        root = self._roots.get(partname)
        if root is None:
            root = parse_xml(self._read(partname))
            if xml_local_name(root.tag) != "theme":
                raise ThemeRefusal(f"{partname!r} has no a:theme root")
            self._roots[partname] = root
        if writable:
            self._dirty.add(partname)
        return root

    # -- overrides ----------------------------------------------------------

    def _stored_override_part(self, owner: str) -> str | None:
        part = self._related(owner, "themeOverride")
        return part if part is not None and part in self._names else None

    def _override_root(self, owner: str) -> ET.Element | None:
        self._sync()
        pending = self._overrides.get(owner)
        if pending is not None:
            return pending.root
        part = self._stored_override_part(owner)
        if part is None:
            return None
        root = self._roots.get(part)
        if root is None:
            root = parse_xml(self._read(part))
            if xml_local_name(root.tag) != "themeOverride":
                raise ThemeRefusal(f"{part!r} has no a:themeOverride root")
            self._roots[part] = root
        return root

    def _override_rel_source(self, owner: str) -> str:
        pending = self._overrides.get(owner)
        if pending is not None:
            return pending.rel_source
        part = self._stored_override_part(owner)
        assert part is not None
        return part

    def _touch_override(self, owner: str) -> None:
        if owner not in self._overrides:
            root = self._override_root(owner)
            self._overrides[owner] = _Pending(root, self._override_rel_source(owner))

    def _set_override(self, owner: str, schemes: Mapping[str, ET.Element], rel_source: str) -> None:
        namespace = ooxml_namespace(schemes["clrScheme"], A_NS)
        root = ET.Element(
            f"{{{namespace}}}themeOverride",
            {"xmlns:a": namespace, "xmlns:r": _r_namespace(namespace)},
        )
        root.extend(schemes[name] for name in THEME_SCHEME_TAGS)
        self._overrides[owner] = _Pending(root, rel_source)

    def _clear_override(self, owner: str) -> None:
        self._sync()
        if self._stored_override_part(owner) is None:
            self._overrides.pop(owner, None)
        else:
            self._overrides[owner] = _Pending(None, owner)

    # -- save ---------------------------------------------------------------

    @property
    def dirty(self) -> bool:
        return bool(self._dirty or self._overrides)

    def _snapshot(self) -> tuple[dict[str, bytes], dict[str, _Pending]]:
        themes = {part: serialize_xml(self._roots[part]) for part in self._dirty}
        overrides = {
            owner: _Pending(None if p.root is None else deepcopy(p.root), p.rel_source)
            for owner, p in self._overrides.items()
        }
        return themes, overrides


def theme_edits(presentation: Any) -> ThemeEdits:
    edits = presentation._theme_edits
    if edits is None:
        edits = presentation._theme_edits = ThemeEdits(presentation)
    return edits


def _relationships_root(package: Any, rels_name: str) -> ET.Element:
    if rels_name in package.namelist():
        return parse_xml(package.read(rels_name))
    return ET.Element(f"{{{PKG_REL_NS}}}Relationships", {"xmlns": PKG_REL_NS})


def _stage_theme_package(
    source: Any,
    output: Path,
    themes: Mapping[str, bytes],
    overrides: Mapping[str, _Pending],
) -> None:
    """Write ``source`` to ``output`` with the queued theme edits applied."""
    with open_package_source(source) as package:
        names = set(package.namelist())
        replacements: dict[str, bytes] = dict(themes)
        removals: set[str] = set()
        rels_roots: dict[str, ET.Element] = {}
        changed: set[str] = set()
        content_types = parse_xml(package.read("[Content_Types].xml"))

        def rels(part: str) -> ET.Element:
            name = rels_part_for_package_part(part)
            if name not in rels_roots:
                rels_roots[name] = _relationships_root(package, name)
            return rels_roots[name]

        def override_rels(root: ET.Element) -> list[ET.Element]:
            return [
                rel
                for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship")
                if rel.get("Type", "").rsplit("/", 1)[-1] == "themeOverride"
                and rel.get("TargetMode") != "External"
            ]

        def references(target: str) -> int:
            count = 0
            for name in names | rels_roots.keys():
                if not name.endswith(".rels") or name in removals:
                    continue
                root = rels_roots.get(name)
                if root is None:
                    root = ET.fromstring(package.read(name))
                owner = _rels_owner(name)
                for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
                    if rel.get("TargetMode") == "External":
                        continue
                    if resolve_package_target(owner, rel.get("Target", "")) == target:
                        count += 1
            return count

        def drop_part(part: str) -> None:
            removals.add(part)
            removals.add(rels_part_for_package_part(part))
            replacements.pop(part, None)
            for override in content_types.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
                if override.get("PartName") == "/" + part:
                    content_types.remove(override)
                    changed.add("[Content_Types].xml")

        allocated: set[str] = set()
        for owner, pending in overrides.items():
            if owner not in names:
                raise LifecycleRefusal(f"{owner!r} is no longer in the package")
            owner_rels = rels(owner)
            owner_rels_name = rels_part_for_package_part(owner)
            existing = override_rels(owner_rels)
            if pending.root is None:
                for rel in existing:
                    owner_rels.remove(rel)
                    changed.add(owner_rels_name)
                    target = resolve_package_target(owner, rel.get("Target", ""))
                    if target in names and references(target) == 0:
                        drop_part(target)
                continue
            target = None
            if existing:
                current = resolve_package_target(owner, existing[0].get("Target", ""))
                if references(current) == 1:
                    target = current
                else:
                    owner_rels.remove(existing[0])
                    changed.add(owner_rels_name)
            if target is None:
                index = 1
                taken = names | allocated
                while (candidate := f"ppt/theme/themeOverride{index}.xml") in taken:
                    index += 1
                target = candidate
                allocated.add(target)
                ids = {rel.get("Id") for rel in owner_rels}
                rel_id, suffix = _OVERRIDE_RELATIONSHIP_ID, 1
                while rel_id in ids:
                    suffix += 1
                    rel_id = f"{_OVERRIDE_RELATIONSHIP_ID}{suffix}"
                rel_type = _sibling_type(owner_rels, "themeOverride")
                ET.SubElement(
                    owner_rels,
                    f"{{{PKG_REL_NS}}}Relationship",
                    {
                        "Id": rel_id,
                        "Type": rel_type,
                        "Target": posixpath.relpath(target, posixpath.dirname(owner)),
                    },
                )
                changed.update((owner_rels_name, "[Content_Types].xml"))
                ET.SubElement(
                    content_types,
                    f"{{{CONTENT_TYPES_NS}}}Override",
                    {
                        "PartName": "/" + target,
                        "ContentType": THEME_OVERRIDE_CONTENT_TYPE,
                    },
                )
            replacements[target] = serialize_xml(pending.root)
            if pending.rel_source != target:
                changed.add(
                    _copy_scheme_relationships(
                        package, pending.root, pending.rel_source, target, rels_roots
                    )
                )
        for name, root in rels_roots.items():
            if name not in changed or name in removals:
                continue
            if len(root) == 0 and name not in names:
                continue
            replacements[name] = serialize_xml(root)
        if "[Content_Types].xml" in changed:
            replacements["[Content_Types].xml"] = serialize_xml(content_types)
        copy_open_package_with_replacements(package, output, replacements, removals)


def _rels_owner(rels_name: str) -> str:
    directory = posixpath.dirname(posixpath.dirname(rels_name))
    return posixpath.join(directory, posixpath.basename(rels_name)[: -len(".rels")])


def _sibling_type(rels_root: ET.Element, kind: str) -> str:
    """Use the relationship namespace (Transitional or Strict) the part already uses."""
    for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        rel_type = rel.get("Type", "")
        if rel_type.startswith(STRICT_R_NS):
            return f"{STRICT_R_NS}/{kind}"
    return f"{R_NS}/{kind}"


def _copy_scheme_relationships(
    package: Any,
    root: ET.Element,
    rel_source: str,
    target: str,
    rels_roots: dict[str, ET.Element],
) -> str:
    """Give a copied override the relationships its blip fills reference.

    Returns the override's relationships part name.
    """
    needed = _relationship_ids(root)
    name = rels_part_for_package_part(target)
    out = ET.Element(f"{{{PKG_REL_NS}}}Relationships", {"xmlns": PKG_REL_NS})
    if needed:
        source_rels = _relationships_root(package, rels_part_for_package_part(rel_source))
        for rel in source_rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
            if rel.get("Id") not in needed:
                continue
            copied = {key: value for key, value in rel.attrib.items() if key != "xmlns"}
            if copied.get("TargetMode") != "External":
                absolute = resolve_package_target(rel_source, copied.get("Target", ""))
                copied["Target"] = posixpath.relpath(absolute, posixpath.dirname(target))
            ET.SubElement(out, f"{{{PKG_REL_NS}}}Relationship", copied)
    if len(out) or name in package.namelist():
        rels_roots[name] = out
    return name


@contextmanager
def staged_theme_edits(presentation: Any) -> Iterator[None]:
    """Rebase onto a package carrying the queued theme edits for one save.

    The ordinary save transaction then publishes and rebases that package.  A
    failed save restores the original source and keeps the edits queued.
    """
    edits = presentation._theme_edits
    if edits is None or not edits.dirty:
        yield
        return
    themes, overrides = edits._snapshot()
    previous_source = presentation._source_path
    previous_tempdir = presentation._source_tempdir
    staged_dir: tempfile.TemporaryDirectory[str] | None = tempfile.TemporaryDirectory(
        prefix="wolfppt-theme-"
    )
    try:
        staged: Any = Path(staged_dir.name) / "presentation.pptx"
        _stage_theme_package(previous_source, staged, themes, overrides)
        if isinstance(previous_source, InMemoryPackageSource):
            staged = InMemoryPackageSource(staged.read_bytes())
            staged_dir.cleanup()
            staged_dir = None
    except BaseException:
        if staged_dir is not None:
            staged_dir.cleanup()
        raise
    presentation._source_path = staged
    if staged_dir is not None:
        presentation._source_tempdir = staged_dir
    try:
        yield
    except BaseException:
        if presentation._source_path is staged:
            presentation._source_path = previous_source
            presentation._source_tempdir = previous_tempdir
            if staged_dir is not None:
                staged_dir.cleanup()
        raise
    edits._published()
    if previous_tempdir is not None and presentation._source_tempdir is not previous_tempdir:
        previous_tempdir.cleanup()
