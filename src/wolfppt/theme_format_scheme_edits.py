"""Pre-write validation of detached DrawingML format-scheme entries.

This is deliberately not a DrawingML schema validator or a renderability gate.
It checks the style-list envelope, relationship references, colour payloads and
ordered transforms, line widths, and numeric outer/inner/preset-shadow values.
Other fill/effect declarations and attributes remain opaque, including valid
families the renderer does not draw. Extension lists and foreign-namespace
subtrees are preserved without interpreting their content; their relationship
references still have to be declared by the theme part.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence, Set
from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .render_theme import COLOR_TAGS, ThemeRefusal, ThemeScheme, resolve_color_element
from .xml_helpers import (
    A_NS,
    R_NS,
    STRICT_R_NS,
    percentage_value,
    xml_local_name,
)


class ThemeEditRefusal(ThemeRefusal, ValueError):
    """An invalid theme edit refused before any writable scheme is obtained."""


# The real palette is irrelevant to admission, but all standard slots must be
# present so that legal references (including renderer aliases) can resolve.
# phClr is supplied explicitly rather than pretending it is a thirteenth slot.
_VALIDATION_SCHEME = ThemeScheme(
    colors={
        name: "808080"
        for name in (
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
    }
)
_REL_NAMESPACES = frozenset({R_NS, STRICT_R_NS})
_SINGLE_COLOR_CONTAINERS = frozenset(
    {
        "solidFill",
        "gs",
        "fgClr",
        "bgClr",
        "outerShdw",
        "innerShdw",
        "prstShdw",
        "glow",
        "clrFrom",
        "clrTo",
        "clrRepl",
    }
)
_SHADOW_TAGS = frozenset({"outerShdw", "innerShdw", "prstShdw"})
_MAX_COORDINATE = 27273042316900
_MAX_LINE_WIDTH = 20116800


def _fragment_element(value: str, namespace: str, list_name: str) -> ET.Element:
    relationship_namespace = R_NS if namespace == A_NS else STRICT_R_NS
    wrapper = f'<w xmlns:a="{namespace}" xmlns:r="{relationship_namespace}">{value}</w>'
    try:
        parsed = ET.fromstring(wrapper)
    except ET.ParseError as exc:
        raise ThemeEditRefusal(f"{list_name} entry is not well-formed XML: {exc}") from exc
    if (
        len(parsed) != 1
        or (parsed.text and parsed.text.strip())
        or (parsed[0].tail and parsed[0].tail.strip())
    ):
        raise ThemeEditRefusal(f"{list_name} entry must be exactly one element")
    return parsed[0]


def _parse_style(
    value: str | ET.Element, namespace: str, admitted: Set[str], list_name: str
) -> ET.Element:
    if isinstance(value, ET.Element):
        element = deepcopy(value)
        # Elements can be constructed with invalid XML names, attributes, or
        # characters. Check their serialization too, retaining the detached
        # original tree so comments and extension content are not discarded.
        try:
            serialized = ET.tostring(element, encoding="unicode")
        except (TypeError, ValueError) as exc:
            raise ThemeEditRefusal(f"{list_name} entry is not well-formed XML: {exc}") from exc
        _fragment_element(serialized, namespace, list_name)
    elif isinstance(value, str):
        element = _fragment_element(value, namespace, list_name)
    else:
        raise TypeError(f"{list_name} entries are XML strings or elements")
    if not isinstance(element.tag, str):
        raise ThemeEditRefusal(f"{list_name} entry must be a DrawingML element")
    local = xml_local_name(element.tag)
    if element.tag != f"{{{namespace}}}{local}" or local not in admitted:
        raise ThemeEditRefusal(
            f"{list_name} admits only {sorted(admitted)} in the theme's DrawingML "
            f"namespace, not {element.tag!r}"
        )
    return element


def _integer_attribute(element: ET.Element, attribute: str, minimum: int, maximum: int) -> None:
    raw = element.get(attribute)
    if raw is None:
        return
    label = f"{xml_local_name(element.tag)} {attribute}"
    if re.fullmatch(r"[+-]?[0-9]+", raw.strip()) is None:
        raise ThemeEditRefusal(f"{label} must be an OOXML integer, not {raw!r}")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ThemeEditRefusal(f"{label} is an invalid integer") from exc
    if not minimum <= value <= maximum:
        raise ThemeEditRefusal(f"{label} must be between {minimum} and {maximum}")


def _validate_shadow_numbers(element: ET.Element) -> None:
    name = xml_local_name(element.tag)
    for attribute in ("blurRad", "dist") if name != "prstShdw" else ("dist",):
        _integer_attribute(element, attribute, 0, _MAX_COORDINATE)
    _integer_attribute(element, "dir", 0, 21599999)
    if name != "outerShdw":
        return
    for attribute in ("kx", "ky"):
        # ST_FixedAngle excludes +/-90 degrees (60000 units per degree).
        _integer_attribute(element, attribute, -5399999, 5399999)
    for attribute in ("sx", "sy"):
        raw = element.get(attribute)
        if raw is None:
            continue
        try:
            percentage_value(element, raw)
        except (ValueError, OverflowError) as exc:
            raise ThemeEditRefusal(f"outerShdw {attribute}: {exc}") from exc
        if not raw.endswith("%"):
            _integer_attribute(element, attribute, -(2**31), 2**31 - 1)


def _validate_content(element: ET.Element, namespace: str) -> None:
    if not isinstance(element.tag, str):
        return  # Preserve comments and processing instructions on Element inputs.
    name = xml_local_name(element.tag)
    if element.tag != f"{{{namespace}}}{name}" or name == "extLst":
        return
    if name in COLOR_TAGS:
        if (element.text and element.text.strip()) or any(
            (isinstance(child.tag, str) and child.text and child.text.strip())
            or (child.tail and child.tail.strip())
            for child in element
        ):
            raise ThemeEditRefusal(f"colour element {name!r} must not contain text")
        # Comments and processing instructions are XML trivia, not transforms.
        # Keep them in the returned tree, but do not pass them to the resolver.
        color = element
        if any(not isinstance(node.tag, str) for node in element.iter()):
            color = deepcopy(element)
            for parent in color.iter():
                for child in list(parent):
                    if not isinstance(child.tag, str):
                        parent.remove(child)
        try:
            resolve_color_element(color, _VALIDATION_SCHEME, placeholder="808080")
        except (ThemeRefusal, ValueError, OverflowError) as exc:
            raise ThemeEditRefusal(str(exc)) from exc
        return
    # Only inspect known colour-choice containers, not the entire fill/effect
    # grammar. A missing, foreign, unknown or duplicate colour is not a usable
    # reference; duotone has two colours and alphaInv has an optional one.
    if name in _SINGLE_COLOR_CONTAINERS or name in {"duotone", "alphaInv"}:
        color_tags = {f"{{{namespace}}}{color}" for color in COLOR_TAGS}
        colors = [
            child for child in element if isinstance(child.tag, str) and child.tag in color_tags
        ]
        minimum = 0 if name == "alphaInv" else 2 if name == "duotone" else 1
        maximum = 2 if name == "duotone" else 1
        if not minimum <= len(colors) <= maximum:
            description = "at most one" if name == "alphaInv" else str(minimum)
            raise ThemeEditRefusal(
                f"{name} requires {description} recognized DrawingML colour element(s)"
            )
    if name == "ln":
        _integer_attribute(element, "w", 0, _MAX_LINE_WIDTH)
    elif name in _SHADOW_TAGS:
        _validate_shadow_numbers(element)
    for child in element:
        _validate_content(child, namespace)


def validate_style_entries(
    values: Sequence[str | ET.Element],
    namespace: str,
    admitted: Set[str],
    list_name: str,
    relationship_ids: Set[str],
) -> list[ET.Element]:
    """Return detached validated entries, without reading or mutating theme state.

    Strings retain the facade's implicit ``a:`` and ``r:`` prefix bindings.
    There must be at least three entries with an admitted root in the theme's
    DrawingML namespace. Invalid XML/content/references raise ThemeEditRefusal
    (also ValueError); wrong Python sequence/entry types retain TypeError.

    Colours use the renderer's payload/ordered-transform rules, a synthetic full
    twelve-slot palette, and an explicit phClr value. Known colour containers
    check colour cardinality. Line widths and shadow coordinate, angle and scale
    attributes check their lexical forms and ranges. Renderability, other
    DrawingML schema rules, extension payloads and foreign subtrees are not
    admission criteria. Relationship IDs are checked even inside opaque XML.
    """
    if isinstance(values, (str, ET.Element)) or not isinstance(values, Sequence):
        raise TypeError(f"{list_name} must be a sequence of DrawingML entries")
    entries = [_parse_style(value, namespace, admitted, list_name) for value in values]
    if len(entries) < 3:
        raise ThemeEditRefusal(f"{list_name} needs at least 3 entries")
    for entry in entries:
        referenced = {
            value
            for node in entry.iter()
            for name, value in node.attrib.items()
            if name.startswith("{") and name[1:].split("}", 1)[0] in _REL_NAMESPACES
        }
        unknown = referenced - relationship_ids
        if unknown:
            raise ThemeEditRefusal(
                f"{list_name} entry references relationships {sorted(unknown)} "
                "that the theme part does not declare"
            )
        _validate_content(entry, namespace)
    return entries


def _drawing_copy(element: ET.Element, namespace: str) -> ET.Element:
    """Use the shape codecs' namespace without interpreting opaque payloads."""
    from .package_conformance import _PERCENT_ATTRIBUTES, _convert_value
    from .xml_helpers import STRICT_A_NS

    result = deepcopy(element)
    source = result.tag[1:].split("}", 1)[0]

    def convert(node: ET.Element) -> None:
        if not isinstance(node.tag, str) or not node.tag.startswith(f"{{{source}}}"):
            return
        name = xml_local_name(node.tag)
        if source != namespace:
            for attribute, kind in _PERCENT_ATTRIBUTES[A_NS].get(name, {}).items():
                if attribute in node.attrib:
                    node.set(
                        attribute,
                        _convert_value(
                            "theme style",
                            name,
                            attribute,
                            node.get(attribute),
                            kind,
                            namespace == STRICT_A_NS,
                        ),
                    )
        node.tag = f"{{{namespace}}}{name}"
        if name != "extLst":
            for child in node:
                convert(child)

    convert(result)
    return result


def _is_opaque(element: ET.Element) -> bool:
    return (
        not isinstance(element.tag, str)
        or not element.tag.startswith(f"{{{A_NS}}}")
        or xml_local_name(element.tag) == "extLst"
    )


def _retain_opaque(before: ET.Element, after: ET.Element) -> None:
    """Keep extension/foreign children when a shared codec replaces known XML."""
    for child in before:
        opaque = _is_opaque(child)
        matches = [node for node in after if node.tag == child.tag]
        siblings = [node for node in before if node.tag == child.tag]
        position = siblings.index(child)
        if opaque:
            if position >= len(matches):
                after.append(deepcopy(child))
        else:
            if position < len(matches):
                _retain_opaque(child, matches[position])
            elif any(_is_opaque(node) for node in child.iter()):
                raise ThemeEditRefusal(
                    f"cannot remove {xml_local_name(child.tag)} containing opaque XML"
                )


class _LiveFormat:
    """Rebuild a detached shape codec for each read or atomic theme mutation."""

    def __init__(self, entry: ThemeStyle, factory: Callable, path: tuple = ()) -> None:
        object.__setattr__(self, "_entry", entry)
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_path", path)

    def _target(self, element: ET.Element) -> Any:
        value = self._factory(element)
        for operation, key in self._path:
            value = getattr(value, key) if operation == "attr" else value[key]
        return value

    def _view(self, value: Any, path: tuple) -> Any:
        from .shape_3d_format import _ThreeDPart
        from .shape_format_facade import (
            ColorFormat,
            FillFormat,
            GradientStop,
            GradientStopColorFormat,
            GradientStops,
            LineFormat,
        )

        if isinstance(
            value,
            (
                FillFormat,
                ColorFormat,
                GradientStops,
                GradientStop,
                GradientStopColorFormat,
                LineFormat,
                _ThreeDPart,
            ),
        ):
            return _LiveFormat(self._entry, self._factory, path)
        return value

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self._target(self._entry._codec_element()), name)
        if callable(value):

            def invoke(*args: Any, **kwargs: Any) -> Any:
                result = None

                def mutate(element: ET.Element) -> None:
                    nonlocal result
                    result = getattr(self._target(element), name)(*args, **kwargs)

                self._entry._edit(mutate)
                # Gradient-stop insert/append return a live indexed view.
                from .shape_format_facade import GradientStop

                if isinstance(result, GradientStop):
                    return self._view(result, self._path + (("item", result._index),))
                return result

            return invoke
        return self._view(value, self._path + (("attr", name),))

    def __setattr__(self, name: str, value: Any) -> None:
        def mutate(element: ET.Element) -> None:
            target = self._target(element)
            descriptor = getattr(type(target), name, None)
            if descriptor is None or not hasattr(descriptor, "__set__"):
                raise ThemeEditRefusal(f"{name!r} is not a writable format property")
            setattr(target, name, value)

        self._entry._edit(mutate)

    def __getitem__(self, index: int) -> Any:
        value = self._target(self._entry._codec_element())[index]
        return self._view(value, self._path + (("item", index),))

    def __len__(self) -> int:
        return len(self._target(self._entry._codec_element()))


def _fill_format(element: ET.Element) -> Any:
    from .shape_format_facade import FillFormat

    parent = ET.Element(f"{{{A_NS}}}spPr")
    parent.append(element)
    return FillFormat.from_fill_parent(parent)


def _line_format(element: ET.Element) -> Any:
    from .facade_values import coerce_emu, emu_value
    from .shape_format_facade import LineFormat, _DetachedFillShape
    from .shape_line_end_edits import (
        set_shape_line_cap,
        set_shape_line_head_end,
        set_shape_line_join,
        set_shape_line_tail_end,
        validate_line_cap,
        validate_line_end_spec,
        validate_miter_limit,
    )

    parent = ET.Element(f"{{{A_NS}}}spPr")
    parent.append(element)

    # The shape's XML-backed outline properties already support detached XML.
    # Redirect the remaining slide-queue properties to this theme-owned line.
    def attribute(name: str, validator: Callable, reader: Callable = lambda v: v) -> property:
        def get(self: Any) -> Any:
            return reader(element.get(name))

        def set_value(self: Any, value: Any) -> None:
            raw = validator(value)
            if raw is None:
                element.attrib.pop(name, None)
            else:
                element.set(name, str(raw))

        return property(get, set_value)

    def join_get(self: Any) -> str | None:
        return next(
            (
                xml_local_name(child.tag)
                for child in element
                if child.tag in {f"{{{A_NS}}}{name}" for name in ("round", "bevel", "miter")}
            ),
            None,
        )

    def join_set(self: Any, value: Any) -> None:
        set_shape_line_join(parent, value)

    def endpoint(name: str) -> property:
        def get(self: Any) -> Any:
            child = element.find(f"{{{A_NS}}}{name}")
            return (
                None
                if child is None
                else {
                    "type": child.get("type"),
                    "width": child.get("w"),
                    "length": child.get("len"),
                }
            )

        def set_value(self: Any, value: Any) -> None:
            spec = validate_line_end_spec(value)
            writer = set_shape_line_head_end if name == "headEnd" else set_shape_line_tail_end
            writer(
                parent,
                **(
                    {}
                    if spec is None
                    else {
                        "end_type": spec["type"],
                        "width": spec["width"],
                        "length": spec["length"],
                    }
                ),
            )

        return property(get, set_value)

    class ThemeOutline(LineFormat):
        width = attribute(
            "w", lambda v: coerce_emu(v, "line width"), lambda v: emu_value(int(v or 0))
        )

        @property
        def cap(self) -> str | None:
            return element.get("cap")

        @cap.setter
        def cap(self, value: Any) -> None:
            set_shape_line_cap(parent, validate_line_cap(value))

        join = property(join_get, join_set)
        head_end = endpoint("headEnd")
        tail_end = endpoint("tailEnd")

        @property
        def miter_limit(self) -> int | None:
            node = element.find(f"{{{A_NS}}}miter")
            return None if node is None or node.get("lim") is None else int(node.get("lim"))

        @miter_limit.setter
        def miter_limit(self, value: Any) -> None:
            limit = validate_miter_limit(value)
            if limit is None:
                node = element.find(f"{{{A_NS}}}miter")
                if node is not None:
                    node.attrib.pop("lim", None)
            else:
                set_shape_line_join(parent, "miter", limit)

        @property
        def fill(self) -> Any:
            from .shape_format_facade import FillFormat

            class ThemeLineFill(FillFormat):
                def group(self) -> None:
                    raise ThemeEditRefusal("group fill is not a DrawingML line fill")

                @property
                def blend_mode(self) -> None:
                    raise ThemeEditRefusal("fill effects are not DrawingML line properties")

                @blend_mode.setter
                def blend_mode(self, value: Any) -> None:
                    raise ThemeEditRefusal("fill effects are not DrawingML line properties")

            return ThemeLineFill.from_fill_parent(element)

        @property
        def color(self) -> Any:
            return self.fill.fore_color

        @property
        def dash_style(self) -> Any:
            from .facade_values import line_dash_style_value

            node = element.find(f"{{{A_NS}}}prstDash")
            return line_dash_style_value(None if node is None else node.get("val"))

        @dash_style.setter
        def dash_style(self, value: Any) -> None:
            from .facade_values import normalize_line_dash_style
            from .shape_format_facade import _LINE_ORDER, _insert_ordered

            raw = normalize_line_dash_style(value)
            for child in list(element):
                if child.tag in {f"{{{A_NS}}}prstDash", f"{{{A_NS}}}custDash"}:
                    element.remove(child)
            if raw is not None:
                _insert_ordered(
                    element, ET.Element(f"{{{A_NS}}}prstDash", {"val": raw}), _LINE_ORDER
                )

    return ThemeOutline(_DetachedFillShape(parent))


def _three_d_format(element: ET.Element) -> Any:
    from .shape_3d_format import ThreeDFormat
    from .shape_format_facade import _DetachedFillShape

    return ThreeDFormat(_DetachedFillShape(element))


class ThemeStyle:
    """Live style at a matrix position; retained handles follow that position.

    ``xml`` is a detached serialized snapshot. Replacing/removing earlier entries
    changes the style at this position; an absent position raises IndexError.
    """

    def __init__(self, collection: ThemeStyleCollection, position: int) -> None:
        self._collection, self._position = collection, position

    def _codec_element(self) -> ET.Element:
        return _drawing_copy(self._collection._entries()[self._position], A_NS)

    def _edit(self, mutate: Callable[[ET.Element], None]) -> None:
        before = self._codec_element()
        replacement = deepcopy(before)
        try:
            mutate(replacement)
            _retain_opaque(before, replacement)
            if ET.tostring(before) == ET.tostring(replacement):
                return
            namespace = self._collection._namespace()
            replacement = _drawing_copy(replacement, namespace)
            self._collection[self._position] = replacement
        except (TypeError, ValueError, OverflowError, AttributeError) as exc:
            if isinstance(exc, ThemeEditRefusal):
                raise
            raise ThemeEditRefusal(str(exc)) from exc

    @property
    def xml(self) -> str:
        return self._collection._serialize(self._collection._entries()[self._position])


class ThemeFillStyle(ThemeStyle):
    """Live shape-compatible fill format, including colours and gradient stops."""

    def _edit(self, mutate: Callable[[ET.Element], None]) -> None:
        # A fill codec replaces the entry within its detached parent.
        def edit_entry(element: ET.Element) -> None:
            parent = ET.Element(f"{{{A_NS}}}spPr")
            parent.append(element)
            mutate(parent)
            if len(parent) != 1:
                raise ThemeEditRefusal("a theme fill entry cannot carry shape effects")
            replacement = parent[0]
            if replacement is not element:
                element.tag, element.attrib = replacement.tag, dict(replacement.attrib)
                element[:] = list(replacement)

        super()._edit(edit_entry)

    @property
    def fill(self) -> _LiveFormat:
        from .shape_format_facade import FillFormat

        # Reads and edits both use a parent; the parent stays detached.
        def factory(element: ET.Element) -> Any:
            if xml_local_name(element.tag) == "spPr":
                return FillFormat.from_fill_parent(element)
            return _fill_format(element)

        return _LiveFormat(self, factory)


class ThemeLineStyle(ThemeStyle):
    @property
    def line(self) -> _LiveFormat:
        return _LiveFormat(self, _line_format)


class ThemeEffectStyle(ThemeStyle):
    @property
    def effects(self) -> Any:
        from .shape_effect_containers import inspect_effect_container

        try:
            return inspect_effect_container(self._codec_element())
        except ValueError as exc:
            raise ThemeEditRefusal(str(exc)) from exc

    @effects.setter
    def effects(self, value: Any) -> None:
        from .shape_effect_containers import set_effect_container

        self._edit(lambda element: set_effect_container(element, value))

    @property
    def three_d(self) -> _LiveFormat:
        return _LiveFormat(self, _three_d_format)


class ThemeStyleCollection(Sequence[ThemeStyle]):
    """Live typed matrix entries with atomic replacement, add and removal.

    Keep at least three entries, as required by DrawingML. Existing XML tuple
    APIs remain available. Accept XML strings/elements or another typed entry.
    Slices return tuples of live positional views; slice mutations are atomic.
    Opaque list children are excluded from indexing and retained on every edit.
    """

    def __init__(
        self,
        elements: Callable,
        relationship_ids: Callable,
        list_name: str,
        admitted: Set[str],
        style_type: type[ThemeStyle],
        serialize: Callable,
    ) -> None:
        self._elements, self._relationship_ids = elements, relationship_ids
        self._list_name, self._admitted = list_name, admitted
        self._style_type, self._serialize = style_type, serialize

    def _namespace(self) -> str:
        from .xml_helpers import ooxml_namespace

        return ooxml_namespace(self._elements(False), A_NS)

    def _listing(self, writable: bool = False) -> ET.Element:
        from .xml_helpers import find_ooxml

        listing = find_ooxml(self._elements(writable), f"{{{A_NS}}}{self._list_name}")
        if listing is None:
            raise ThemeEditRefusal(f"format scheme has no {self._list_name}")
        return listing

    def _entries(self) -> list[ET.Element]:
        namespace = self._namespace()
        return [
            child
            for child in self._listing()
            if child.tag in {f"{{{namespace}}}{name}" for name in self._admitted}
        ]

    def __len__(self) -> int:
        return len(self._entries())

    def __getitem__(self, index: int | slice) -> Any:
        positions = range(len(self))
        if isinstance(index, slice):
            return tuple(self._style_type(self, position) for position in positions[index])
        return self._style_type(self, positions[index])

    def _validated(self, value: Any) -> ET.Element:
        if isinstance(value, ThemeStyle):
            value = value.xml
        try:
            return validate_style_entries(
                [value] * 3,
                self._namespace(),
                self._admitted,
                self._list_name,
                self._relationship_ids(),
            )[0]
        except TypeError as exc:
            raise ThemeEditRefusal(str(exc)) from exc

    def _publish(self, before: list[ET.Element], after: list[ET.Element]) -> None:
        if len(after) < 3:
            raise ThemeEditRefusal(f"{self._list_name} needs at least 3 entries")
        # Preserve opaque siblings and their relative order; style positions
        # retain the original XML slots, with extra entries before trailing XML.
        listing = self._listing(True)
        namespace = self._namespace()
        tags = {f"{{{namespace}}}{name}" for name in self._admitted}
        slots = [index for index, child in enumerate(listing) if child.tag in tags]
        cursor = 0
        for index in slots:
            if cursor < len(after):
                listing[index] = deepcopy(after[cursor])
                cursor += 1
        for index in reversed(slots[len(after) :]):
            del listing[index]
        insert_at = slots[-1] + 1 if slots else 0
        for child in after[cursor:]:
            listing.insert(insert_at, deepcopy(child))
            insert_at += 1

    def __setitem__(self, index: int | slice, value: Any) -> None:
        before = self._entries()
        after = list(before)
        if isinstance(index, slice):
            after[index] = [self._validated(entry) for entry in value]
        else:
            # Resolve the index before validating/obtaining writable state.
            position = range(len(before))[index]
            after[position] = self._validated(value)
        self._publish(before, after)

    def __delitem__(self, index: int | slice) -> None:
        before = self._entries()
        after = list(before)
        del after[index]
        self._publish(before, after)

    def insert(self, index: int, value: Any) -> None:
        before = self._entries()
        after = list(before)
        after.insert(index, self._validated(value))
        self._publish(before, after)

    def append(self, value: Any) -> None:
        self.insert(len(self), value)

    def add(self, value: Any) -> ThemeStyle:
        self.append(value)
        return self[-1]

    def remove(self, value: ThemeStyle | int) -> None:
        """Remove by index or by a view obtained from this collection."""
        if isinstance(value, int):
            del self[value]
        elif isinstance(value, ThemeStyle) and value._collection._listing() is self._listing():
            del self[value._position]
        else:
            raise ThemeEditRefusal("remove requires a style from this collection or an index")
