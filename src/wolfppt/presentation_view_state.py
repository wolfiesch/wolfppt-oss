"""Typed stored/effective PresentationML view settings.

Defaults and particles: ECMA-376 fifth edition (2016), Strict / Transitional
pml.xsd, CT_ViewProperties / CT_NormalViewProperties / CT_NormalViewPortion.
Effective values are schema-attribute defaults, not an Office UI prediction.
An absent parent element has no effective value; schema_default remains
available independently. No pane dimension or grid spacing default is defined.

Slide and notes views (CT_SlideViewProperties / CT_NotesViewProperties) carry
a CT_CommonSlideViewProperties: a required CT_CommonViewProperties (scale and
origin, both required) and an optional CT_GuideList. Creating either view
therefore needs an explicit scale and origin; no Office default is guessed.

Snap flags on ``p:cSldViewPr`` use the same read/update/reset lifecycle:
``slide_snap_to_grid``, ``slide_snap_to_objects``, ``notes_snap_to_grid`` and
``notes_snap_to_objects``. Grid snapping defaults to true, object snapping to
false. These are editor alignment settings, not rendered slide content.
Call ``set_view_properties(scope, scale=..., origin=...)`` before setting snap
flags on an absent view. Reset removes the selected attribute, retaining the
common view and its required children.

The presentation-level view lifecycle also stages queued package operations
(custom XML parts, docProps/app.xml title refresh) on the same scratch package
so they commit and acknowledge with the view edits of one save.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import P_NS, R_NS, open_package_source
from .presentation_tags import (
    LifecycleRefusal,
    add_part,
    one,
    parse_xml,
    relationship_target,
    relationships,
)
from .slide_metadata import presentation_partname
from .xml_helpers import A_NS, STRICT_P_NS, ooxml_namespace, ooxml_path

VIEW_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"
VIEW_TYPES = frozenset(
    (
        "sldView",
        "sldMasterView",
        "notesView",
        "handoutView",
        "notesMasterView",
        "outlineView",
        "sldSorterView",
        "sldThumbnailView",
    )
)
BAR_STATES = frozenset(("minimized", "restored", "maximized"))
# Public key -> parent path, XML attribute, value kind, schema default.
SETTINGS = {
    "last_view": ((), "lastView", VIEW_TYPES, "sldView"),
    "show_comments": ((), "showComments", bool, True),
    "show_outline_icons": (("normalViewPr",), "showOutlineIcons", bool, True),
    "snap_vertical_splitter": (("normalViewPr",), "snapVertSplitter", bool, False),
    "vertical_bar_state": (("normalViewPr",), "vertBarState", BAR_STATES, "restored"),
    "horizontal_bar_state": (("normalViewPr",), "horzBarState", BAR_STATES, "restored"),
    "prefer_single_view": (("normalViewPr",), "preferSingleView", bool, False),
    "restored_left_size": (("normalViewPr", "restoredLeft"), "sz", "percentage", None),
    "restored_top_size": (("normalViewPr", "restoredTop"), "sz", "percentage", None),
    "restored_left_auto_adjust": (
        ("normalViewPr", "restoredLeft"),
        "autoAdjust",
        bool,
        True,
    ),
    "restored_top_auto_adjust": (
        ("normalViewPr", "restoredTop"),
        "autoAdjust",
        bool,
        True,
    ),
    "grid_spacing_x": (("gridSpacing",), "cx", "coordinate", None),
    "grid_spacing_y": (("gridSpacing",), "cy", "coordinate", None),
    "slide_snap_to_grid": (("slideViewPr", "cSldViewPr"), "snapToGrid", bool, True),
    "slide_snap_to_objects": (("slideViewPr", "cSldViewPr"), "snapToObjects", bool, False),
    "notes_snap_to_grid": (("notesViewPr", "cSldViewPr"), "snapToGrid", bool, True),
    "notes_snap_to_objects": (("notesViewPr", "cSldViewPr"), "snapToObjects", bool, False),
}
# Public view scope -> CT_ViewProperties child holding a cSldViewPr.
VIEW_SCOPES = {"slide": "slideViewPr", "notes": "notesViewPr"}
_ROOT_ORDER = (
    "normalViewPr",
    "slideViewPr",
    "outlineViewPr",
    "notesTextViewPr",
    "sorterViewPr",
    "notesViewPr",
    "gridSpacing",
    "extLst",
)
# Public guide orientation -> ST_Direction.
GUIDE_ORIENTATIONS = {"horizontal": "horz", "vertical": "vert"}
_GUIDE_PUBLIC = {raw: name for name, raw in GUIDE_ORIENTATIONS.items()}
COORDINATE32_RANGE = (-2147483648, 2147483647)
COORDINATE_RANGE = (-27273042329600, 27273042316900)
RATIO_RANGE = (1, 2147483647)
# Snapshot key carrying queued package operations (see stage_package_operation).
PACKAGE_OPERATIONS = "package_operations"


@dataclass(frozen=True)
class UnknownViewValue:
    raw: str


@dataclass(frozen=True)
class ViewSetting:
    raw: str | None
    stored: bool | int | str | UnknownViewValue | None
    effective: bool | int | str | UnknownViewValue | None
    schema_default: bool | str | None
    element_present: bool


@dataclass(frozen=True)
class DrawingGuide:
    """One ``p:guide``: orientation and position in master units.

    Guide positions are ST_Coordinate32 master units (576 per inch, i.e. eight
    per point), which is how PowerPoint stores ``p:guide@pos``.
    """

    orientation: str
    position: int

    @property
    def position_points(self) -> float:
        return self.position / 8


@dataclass(frozen=True)
class CommonViewProperties:
    """``p:cViewPr``: scale ratios (n, d), origin (x, y) and ``varScale``."""

    scale_x: tuple[int, int]
    scale_y: tuple[int, int]
    origin: tuple[int, int]
    variable_scale: bool


def _setting(name: str) -> tuple:
    if not isinstance(name, str):
        raise TypeError("view setting name must be str")
    try:
        return SETTINGS[name]
    except KeyError:
        raise KeyError(name) from None


def _decode(raw: str, kind: Any) -> Any:
    if kind is bool:
        if raw.strip() in ("true", "1"):
            return True
        if raw.strip() in ("false", "0"):
            return False
    elif isinstance(kind, frozenset):
        if raw.strip() in kind:
            return raw.strip()
    else:
        try:
            if kind == "percentage" and raw.endswith("%"):
                from decimal import Decimal

                scaled = Decimal(raw[:-1]) * 1000
                if (
                    scaled.is_finite()
                    and scaled == scaled.to_integral_value()
                    and 0 <= scaled <= 100000
                ):
                    return int(scaled)
            elif raw.strip().lstrip("+").isdigit():
                value = int(raw)
                if 0 <= value <= (100000 if kind == "percentage" else 27273042316900):
                    return value
        except (ValueError, ArithmeticError):
            pass
    return UnknownViewValue(raw)


def _encode(value: Any, kind: Any, namespace: str) -> str:
    if kind is bool:
        if type(value) is not bool:
            raise TypeError("boolean view setting requires bool")
        return "true" if value else "false"
    if isinstance(kind, frozenset):
        if not isinstance(value, str):
            raise TypeError("enumerated view setting requires str")
        if value not in kind:
            raise LifecycleRefusal(f"unsupported view value {value!r}")
        return value
    if type(value) is not int:
        raise TypeError("view dimensions require integer units")
    maximum = 100000 if kind == "percentage" else 27273042316900
    if not 0 <= value <= maximum:
        raise LifecycleRefusal(f"view dimension must be between 0 and {maximum}")
    if kind == "percentage" and namespace == STRICT_P_NS:
        if value % 10:
            raise LifecycleRefusal(
                f"Strict pane percentage {value} requires a multiple of 10 units "
                "(0.01%); choose an exactly representable value"
            )
        whole, fractional = divmod(value, 1000)
        fraction = f"{fractional:03d}".rstrip("0")
        return f"{whole}.{fraction}%" if fraction else f"{whole}%"
    return str(value)


def _node(root: ET.Element | None, path: tuple[str, ...]) -> ET.Element | None:
    current = root
    for name in path:
        if current is None:
            return None
        current = one(current, f"{{{P_NS}}}{name}")
    return current


def _int_in(value: Any, bounds: tuple[int, int], name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} requires int")
    if not bounds[0] <= value <= bounds[1]:
        raise LifecycleRefusal(f"{name} must be between {bounds[0]} and {bounds[1]}")
    return value


def _stored_int(element: ET.Element, attr: str, bounds: tuple[int, int]) -> int:
    raw = element.get(attr)
    try:
        value = int(raw) if raw is not None and raw.strip().lstrip("+-").isdigit() else None
    except ValueError:
        value = None
    if value is None or not bounds[0] <= value <= bounds[1]:
        raise LifecycleRefusal(f"unsupported stored view value {attr}={raw!r}")
    return value


def _ratio(value: Any, name: str) -> tuple[int, int]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"{name} requires an (n, d) tuple of int")
    return (
        _int_in(value[0], RATIO_RANGE, f"{name} numerator"),
        _int_in(value[1], RATIO_RANGE, f"{name} denominator"),
    )


def _scale(value: Any) -> tuple[tuple[int, int], tuple[int, int]]:
    """Accept an int percentage, one (n, d) ratio, or ((n, d), (n, d))."""
    if type(value) is int:
        ratio = (_int_in(value, RATIO_RANGE, "scale percentage"), 100)
        return ratio, ratio
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], tuple):
        return _ratio(value[0], "scale x"), _ratio(value[1], "scale y")
    ratio = _ratio(value, "scale")
    return ratio, ratio


def _cview_tuple(cview: ET.Element) -> tuple:
    """Decode one cViewPr as (sx_n, sx_d, sy_n, sy_d, x, y, varScale raw)."""
    scale = one(cview, f"{{{P_NS}}}scale")
    origin = one(cview, f"{{{P_NS}}}origin")
    sx = None if scale is None else one(scale, f"{{{A_NS}}}sx")
    sy = None if scale is None else one(scale, f"{{{A_NS}}}sy")
    if sx is None or sy is None or origin is None:
        raise LifecycleRefusal("view properties lack the required scale or origin")
    return (
        _stored_int(sx, "n", (0, RATIO_RANGE[1])),
        _stored_int(sx, "d", RATIO_RANGE),
        _stored_int(sy, "n", (0, RATIO_RANGE[1])),
        _stored_int(sy, "d", RATIO_RANGE),
        _stored_int(origin, "x", COORDINATE_RANGE),
        _stored_int(origin, "y", COORDINATE_RANGE),
        cview.get("varScale"),
    )


def _cview_public(values: tuple) -> CommonViewProperties:
    raw = values[6]
    variable = _decode(raw, bool) if raw is not None else False
    if isinstance(variable, UnknownViewValue):
        raise LifecycleRefusal(f"unsupported stored varScale {raw!r}")
    return CommonViewProperties(
        (values[0], values[1]), (values[2], values[3]), (values[4], values[5]), variable
    )


def _stored_guides(csld: ET.Element | None) -> tuple[tuple[int | None, str, int], ...]:
    """Guides as (source index, ST_Direction, position) in document order."""
    guide_list = None if csld is None else one(csld, f"{{{P_NS}}}guideLst")
    if guide_list is None:
        return ()
    entries = []
    for index, guide in enumerate(guide_list.findall(ooxml_path(guide_list, f"{{{P_NS}}}guide"))):
        orientation = guide.get("orient", "vert").strip()
        if orientation not in _GUIDE_PUBLIC:
            raise LifecycleRefusal(f"unsupported stored guide orientation {orientation!r}")
        position = 0 if guide.get("pos") is None else _stored_int(guide, "pos", COORDINATE32_RANGE)
        entries.append((index, orientation, position))
    return tuple(entries)


def _insert_ordered(parent: ET.Element, child: ET.Element, local: str, order: tuple) -> None:
    successors = {
        ooxml_path(parent, f"{{{P_NS}}}{name}") for name in order[order.index(local) + 1 :]
    }
    index = next((i for i, c in enumerate(parent) if c.tag in successors), len(parent))
    parent.insert(index, child)


def _child(parent: ET.Element, local: str, order: tuple) -> ET.Element:
    child = one(parent, f"{{{P_NS}}}{local}")
    if child is None:
        child = ET.Element(ooxml_path(parent, f"{{{P_NS}}}{local}"))
        _insert_ordered(parent, child, local, order)
    return child


def _set_int(element: ET.Element, attr: str, value: int) -> None:
    raw = element.get(attr)
    try:
        if raw is not None and int(raw) == value:
            return
    except ValueError:
        pass
    element.set(attr, str(value))


def _write_cview(cview: ET.Element, values: tuple) -> None:
    scale = _child(cview, "scale", ("scale", "origin"))
    for local, n, d in (("sx", values[0], values[1]), ("sy", values[2], values[3])):
        ratio = one(scale, f"{{{A_NS}}}{local}")
        if ratio is None:
            ratio = ET.Element(ooxml_path(scale, f"{{{A_NS}}}{local}"))
            scale.insert(0 if local == "sx" else len(scale), ratio)
        _set_int(ratio, "n", n)
        _set_int(ratio, "d", d)
    origin = _child(cview, "origin", ("scale", "origin"))
    _set_int(origin, "x", values[4])
    _set_int(origin, "y", values[5])
    if values[6] is None:
        cview.attrib.pop("varScale", None)
    elif cview.get("varScale") != values[6]:
        cview.set("varScale", values[6])


def _write_guides(csld: ET.Element, entries: tuple) -> None:
    """Keep untouched guide elements (and their extensions); author the rest."""
    guide_list = one(csld, f"{{{P_NS}}}guideLst")
    originals: list[ET.Element] = []
    if guide_list is None:
        if not entries:
            return
        guide_list = _child(csld, "guideLst", ("cViewPr", "guideLst"))
    else:
        originals = guide_list.findall(ooxml_path(guide_list, f"{{{P_NS}}}guide"))
    kept = []
    for index, orientation, position in entries:
        if index is None:
            guide = ET.Element(ooxml_path(guide_list, f"{{{P_NS}}}guide"))
        else:
            if index >= len(originals):
                raise LifecycleRefusal("queued guide no longer matches the view part")
            guide = originals[index]
        if guide.get("orient", "vert").strip() != orientation:
            guide.set("orient", orientation)
        if index is None or _stored_int(guide, "pos", COORDINATE32_RANGE) != position:
            guide.set("pos", str(position))
        kept.append(guide)
    for guide in originals:
        guide_list.remove(guide)
    first_other = next(
        (
            i
            for i, c in enumerate(guide_list)
            if c.tag != ooxml_path(guide_list, f"{{{P_NS}}}guide")
        ),
        len(guide_list),
    )
    for offset, guide in enumerate(kept):
        guide_list.insert(first_other + offset, guide)


def _resolve_view(
    package: Any, source: str, roots: dict, *, read_only: bool = False
) -> tuple[str | None, ET.Element | None]:
    """Use one parse intent for the owner, relationships and view target."""
    owner = roots.get(source)
    if owner is None:
        owner = roots[source] = parse_xml(package.read(source), read_only=read_only)
    part = relationship_target(
        package,
        source,
        relationships(package, source, roots, read_only=read_only),
        rel_type=ooxml_namespace(owner, R_NS) + "/viewProps",
    )
    if part is None:
        return None, None
    root = roots.setdefault(part, parse_xml(package.read(part), read_only=read_only))
    if root.tag != ooxml_path(root, f"{{{P_NS}}}viewPr"):
        raise LifecycleRefusal("invalid view properties root")
    return part, root


class ViewState:
    """Inspect scoped settings; reparse strictly when staging queued edits."""

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation
        self._edits: dict[str, str | None] = {}
        # "<scope>_view" -> cViewPr tuple; "<scope>_guides" -> guide entries.
        self._structured: dict[str, tuple] = {}
        self._operations: list[Any] = []
        self._source = presentation_partname(presentation._source_path)
        with open_package_source(presentation._source_path) as package:
            roots: dict = {}
            self._part, self._root = _resolve_view(package, self._source, roots, read_only=True)
            self._namespace = ooxml_namespace(
                roots[self._source] if self._root is None else self._root, P_NS
            )

    def _check(self) -> None:
        if self._presentation._disposed:
            raise RuntimeError("presentation is disposed")

    @property
    def present(self) -> bool:
        self._check()
        return (
            self._root is not None
            or any(v is not None for v in self._edits.values())
            or bool(self._structured)
        )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(SETTINGS)

    def read(self, name: str) -> ViewSetting:
        self._check()
        path, attr, kind, default = _setting(name)
        node = _node(self._root, path)
        present = node is not None
        if any(
            value is not None and SETTINGS[key][0][: len(path)] == path
            for key, value in self._edits.items()
        ):
            present = True
        if any(
            path == (container, "cSldViewPr") and f"{scope}_view" in self._structured
            for scope, container in VIEW_SCOPES.items()
        ):
            present = True
        raw = self._edits.get(name, None if node is None else node.get(attr))
        stored = None if raw is None else _decode(raw, kind)
        effective = (default if stored is None else stored) if present else None
        return ViewSetting(raw, stored, effective, default, present)

    def update(self, **settings: Any) -> None:
        self._check()
        encoded = {}
        for name, value in settings.items():
            path, _, kind, _ = _setting(name)
            if path[-1:] == ("cSldViewPr",) and type(value) is not bool:
                raise LifecycleRefusal(f"{name} requires bool")
            encoded[name] = _encode(value, kind, self._namespace)
        proposed = self._edits | encoded
        _validate_required_children(self._root, proposed, self._structured)
        self._edits.update(encoded)

    def reset(self, *names: str) -> None:
        """Remove only the selected attributes, never unknown XML or the part.

        Required pane sizes and grid dimensions cannot be reset in isolation.
        Use an explicit dimension instead; there is no normative default.
        """
        self._check()
        for name in names:
            _, _, kind, _ = _setting(name)
            if kind in ("percentage", "coordinate"):
                raise LifecycleRefusal("required view dimensions have no reset default")
        resets = {name: None for name in names if self.read(name).raw is not None}
        _validate_required_children(self._root, self._edits | resets, self._structured)
        self._edits.update(resets)

    # -- slide / notes view: scale, origin and drawing guides ------------------

    def _csld(self, scope: str) -> ET.Element | None:
        if scope not in VIEW_SCOPES:
            raise KeyError(scope)
        return _node(self._root, (VIEW_SCOPES[scope], "cSldViewPr"))

    def _stored_view(self, scope: str) -> tuple | None:
        cview = _node(self._csld(scope), ("cViewPr",))
        return None if cview is None else _cview_tuple(cview)

    def _view_values(self, scope: str) -> tuple | None:
        key = f"{scope}_view"
        if key in self._structured:
            return self._structured[key]
        return self._stored_view(scope)

    def _guide_entries(self, scope: str) -> tuple:
        key = f"{scope}_guides"
        if key in self._structured:
            return self._structured[key]
        return _stored_guides(self._csld(scope))

    def _stage(self, key: str, value: tuple, stored: tuple | None) -> None:
        if value == stored:
            self._structured.pop(key, None)
        else:
            self._structured[key] = value

    def view_properties(self, scope: str = "slide") -> CommonViewProperties | None:
        """Scale and origin of the slide or notes view; None when not stored."""
        self._check()
        values = self._view_values(scope)
        return None if values is None else _cview_public(values)

    def set_view_properties(
        self,
        scope: str = "slide",
        *,
        scale: Any = None,
        origin: tuple[int, int] | None = None,
        variable_scale: bool | None = None,
    ) -> None:
        """Queue scale (int %, (n, d) or ((n, d), (n, d))), origin and varScale.

        A view without stored ``p:cViewPr`` needs both scale and origin.
        """
        self._check()
        current = self._view_values(scope)
        if current is None and (scale is None or origin is None):
            raise LifecycleRefusal(
                f"creating {scope} view properties requires explicit scale and origin"
            )
        sx, sy = _scale(scale) if scale is not None else (current[:2], current[2:4])
        if origin is not None:
            if not isinstance(origin, tuple) or len(origin) != 2:
                raise TypeError("origin requires an (x, y) tuple of int")
            point = (
                _int_in(origin[0], COORDINATE_RANGE, "origin x"),
                _int_in(origin[1], COORDINATE_RANGE, "origin y"),
            )
        else:
            point = current[4:6]
        if variable_scale is None:
            variable = None if current is None else current[6]
        else:
            variable = _encode(variable_scale, bool, self._namespace)
        self._stage(f"{scope}_view", (*sx, *sy, *point, variable), self._stored_view(scope))

    def guides(self, scope: str = "slide") -> tuple[DrawingGuide, ...]:
        """Drawing guides of the slide or notes view, in document order."""
        self._check()
        return tuple(
            DrawingGuide(_GUIDE_PUBLIC[orientation], position)
            for _, orientation, position in self._guide_entries(scope)
        )

    def _require_view(self, scope: str) -> None:
        if self._view_values(scope) is None:
            raise LifecycleRefusal(
                f"{scope} guides need {scope} view properties; "
                "call set_view_properties with scale and origin first"
            )

    def add_guide(self, orientation: str, position: int, scope: str = "slide") -> DrawingGuide:
        """Append a guide; position is in master units (8 per point)."""
        self._check()
        if orientation not in GUIDE_ORIENTATIONS:
            raise LifecycleRefusal(f"guide orientation must be one of {sorted(GUIDE_ORIENTATIONS)}")
        position = _int_in(position, COORDINATE32_RANGE, "guide position")
        self._require_view(scope)
        entries = self._guide_entries(scope)
        self._stage(
            f"{scope}_guides",
            (*entries, (None, GUIDE_ORIENTATIONS[orientation], position)),
            _stored_guides(self._csld(scope)),
        )
        return DrawingGuide(orientation, position)

    def update_guide(
        self,
        index: int,
        *,
        orientation: str | None = None,
        position: int | None = None,
        scope: str = "slide",
    ) -> DrawingGuide:
        self._check()
        entries = list(self._guide_entries(scope))
        source, raw, current = entries[index]
        if orientation is not None:
            if orientation not in GUIDE_ORIENTATIONS:
                raise LifecycleRefusal(
                    f"guide orientation must be one of {sorted(GUIDE_ORIENTATIONS)}"
                )
            raw = GUIDE_ORIENTATIONS[orientation]
        if position is not None:
            current = _int_in(position, COORDINATE32_RANGE, "guide position")
        entries[index] = (source, raw, current)
        self._stage(f"{scope}_guides", tuple(entries), _stored_guides(self._csld(scope)))
        return DrawingGuide(_GUIDE_PUBLIC[raw], current)

    def remove_guide(self, index: int, scope: str = "slide") -> DrawingGuide:
        self._check()
        entries = list(self._guide_entries(scope))
        _, raw, position = entries.pop(index)
        self._stage(f"{scope}_guides", tuple(entries), _stored_guides(self._csld(scope)))
        return DrawingGuide(_GUIDE_PUBLIC[raw], position)

    def clear_guides(self, scope: str = "slide") -> None:
        self._check()
        self._guide_entries(scope)
        self._stage(f"{scope}_guides", (), _stored_guides(self._csld(scope)))

    # -- queued package operations ---------------------------------------------

    def stage_package_operation(self, operation: Any) -> None:
        """Queue an operation applied to this save's lifecycle scratch package.

        ``operation.apply(package, roots, source)`` mutates only the parsed parts in
        ``roots``; ``operation.validate()`` rejects a stale owner at snapshot.
        """
        self._check()
        self._operations.append(operation)

    def pending_operations(self) -> tuple[Any, ...]:
        return tuple(self._operations)

    def replace_pending_operation(self, old: Any, new: Any | None) -> None:
        index = next(i for i, op in enumerate(self._operations) if op is old)
        if new is None:
            del self._operations[index]
        else:
            self._operations[index] = new

    @property
    def dirty(self) -> bool:
        return bool(self._edits or self._structured or self._operations)

    def snapshot(self) -> tuple[tuple[str, Any], ...]:
        self._check()
        for operation in self._operations:
            operation.validate()
        records = (*self._edits.items(), *self._structured.items())
        if self._operations:
            records += ((PACKAGE_OPERATIONS, tuple(self._operations)),)
        return tuple(records)

    def acknowledge(self, edits: tuple, root: bytes | None, part: str | None) -> None:
        self._root = None if root is None else parse_xml(root, read_only=True)
        self._part = part
        for name, value in edits:
            if name == PACKAGE_OPERATIONS:
                if tuple(self._operations[: len(value)]) == value:
                    del self._operations[: len(value)]
                continue
            pending = self._structured if name in self._structured else self._edits
            if name in pending and pending[name] == value:
                del pending[name]


def _validate_required_children(
    root: ET.Element | None, edits: dict, structured: dict | None = None
) -> None:
    normal = any(
        SETTINGS[k][0] and SETTINGS[k][0][0] == "normalViewPr" and v is not None
        for k, v in edits.items()
    )
    grid = any(SETTINGS[k][0] == ("gridSpacing",) and v is not None for k, v in edits.items())
    for needed, names in (
        (normal, ("restored_left_size", "restored_top_size")),
        (grid, ("grid_spacing_x", "grid_spacing_y")),
    ):
        if not needed:
            continue
        for name in names:
            path, attr, kind, _ = SETTINGS[name]
            node = _node(root, path)
            raw = edits.get(name, None if node is None else node.get(attr))
            if raw is None or isinstance(_decode(raw, kind), UnknownViewValue):
                raise LifecycleRefusal(f"creating/editing view group requires explicit {name}")
    for scope, container in VIEW_SCOPES.items():
        if not any(SETTINGS[name][0] == (container, "cSldViewPr") for name in edits):
            continue
        if structured is not None and f"{scope}_view" in structured:
            continue
        cview = _node(root, (container, "cSldViewPr", "cViewPr"))
        if cview is None:
            raise LifecycleRefusal(
                f"creating/editing {scope} snap flags requires explicit scale and origin; "
                "call set_view_properties first"
            )
        _cview_tuple(cview)


def apply_view_edits(
    package: Any, roots: dict, edits: tuple, source: str
) -> tuple[str | None, ET.Element | None]:
    settings = tuple((name, value) for name, value in edits if name in SETTINGS)
    structured = {
        name: value for name, value in edits if name not in SETTINGS and name != PACKAGE_OPERATIONS
    }
    operations = next((value for name, value in edits if name == PACKAGE_OPERATIONS), ())
    part, root = _resolve_view(package, source, roots)
    _validate_required_children(root, dict(settings), structured)
    for scope, container in VIEW_SCOPES.items():
        if (
            f"{scope}_guides" in structured
            and f"{scope}_view" not in structured
            and _node(root, (container, "cSldViewPr", "cViewPr")) is None
        ):
            raise LifecycleRefusal(f"{scope} guides need {scope} view properties")
    if root is None and (structured or any(value is not None for _, value in settings)):
        owner = roots[source]
        root = ET.Element(f"{{{ooxml_namespace(owner, P_NS)}}}viewPr")
        part, _ = add_part(
            package,
            roots,
            source,
            "ppt/viewProps",
            ooxml_namespace(owner, R_NS) + "/viewProps",
            VIEW_CONTENT_TYPE,
            root,
        )
    for scope, container in VIEW_SCOPES.items():
        view = structured.get(f"{scope}_view")
        guides = structured.get(f"{scope}_guides")
        if view is None and guides is None:
            continue
        csld = _child(_child(root, container, _ROOT_ORDER), "cSldViewPr", ("cSldViewPr", "extLst"))
        cview = one(csld, f"{{{P_NS}}}cViewPr")
        if cview is None:
            cview = ET.Element(ooxml_path(csld, f"{{{P_NS}}}cViewPr"))
            csld.insert(0, cview)
        if view is not None:
            _write_cview(cview, view)
        if guides is not None:
            _write_guides(csld, guides)
    for name, value in settings if root is not None else ():
        path, attr, _, _ = SETTINGS[name]
        current = root
        for local in path:
            child = one(current, f"{{{P_NS}}}{local}")
            if child is None:
                if value is None:
                    break
                child = ET.Element(ooxml_path(current, f"{{{P_NS}}}{local}"))
                _insert_ordered(
                    current,
                    child,
                    local,
                    _ROOT_ORDER if current is root else ("restoredLeft", "restoredTop", "extLst"),
                )
            current = child
        else:
            if value is None:
                current.attrib.pop(attr, None)
            else:
                current.set(attr, value)
    for operation in operations:
        operation.apply(package, roots, source)
    return part, root
