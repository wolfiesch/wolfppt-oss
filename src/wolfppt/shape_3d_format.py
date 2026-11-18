"""Typed read/edit access to a shape's 3-D format (``a:scene3d``/``a:sp3d``).

Reach it as ``shape.three_d`` on a saved slide shape, connector or picture.
Lengths are EMU, angles degrees and colours RGB/RGBA/HSL or ``scheme:<name>`` text.
Each setter rewrites the saved slide part through the package-backed edit
channel of :mod:`wolfppt.shape_format_facade`, so queued facade edits must be
saved first.

Reads follow the saved part's namespace profile, Transitional or Strict. Edits
support Transitional DrawingML only: a Strict shape raises
:class:`ThreeDFormatRefusal` before any write, so no mixed-profile XML is authored.
Extension lists (``a:extLst``) under the scene, backdrop and solid are kept on edit.
"""

from __future__ import annotations

import math
from typing import Any, NamedTuple
from xml.etree import ElementTree as ET

from . import drawingml_3d_vocabulary
from .dml.color import color_alpha, color_element_from_string, color_element_to_string
from .facade_values import emu_value as _emu_value
from .package_parts import open_package_source
from .shape_format_facade import (
    _SHAPE_PROPERTIES_ORDER,
    _a,
    _detached_fill_parent,
    _edit_shape_properties,
    _ensure_child,
    _insert_ordered,
    _is_pending_shape,
    _remove_children,
)
from .shape_xml import _shape_xml_element
from .xml_helpers import A_NS, P_NS, find_ooxml, ooxml_namespace
from .xml_helpers import xml_local_name as _xml_local_name

__all__ = [
    "Backdrop",
    "BevelFormat",
    "CameraFormat",
    "LightRigFormat",
    "ThreeDFormat",
    "ThreeDFormatRefusal",
]

_SCENE_ORDER = {"camera": 0, "lightRig": 1, "backdrop": 2, "extLst": 3}
_SOLID_ORDER = {
    "bevelT": 0,
    "bevelB": 1,
    "extrusionClr": 2,
    "contourClr": 3,
    "extLst": 4,
}
_COORDINATE_MAX = 27273042316900
_ANGLE_TURN = 21600000


class ThreeDFormatRefusal(ValueError):
    """A named 3-D authoring value refusal, raised before any package write."""


class Backdrop(NamedTuple):
    """``a:scene3d/a:backdrop``: ``anchor`` is an (x, y, z) point in EMU and
    ``normal`` and ``up`` are integer (dx, dy, dz) direction vectors."""

    anchor: tuple[int, int, int]
    normal: tuple[int, int, int]
    up: tuple[int, int, int]


_BACKDROP_PARTS = (
    ("anchor", ("x", "y", "z")),
    ("norm", ("dx", "dy", "dz")),
    ("up", ("dx", "dy", "dz")),
)


def _coordinates(value: Any, label: str) -> tuple[int, int, int]:
    """Validate an integer triple of ST_Coordinate values."""
    try:
        first, second, third = value
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{label} must be three integers") from exc
    check = _coordinate(label, signed=True)
    return (int(check(first)), int(check(second)), int(check(third)))


def _find(parent: ET.Element | None, name: str) -> ET.Element | None:
    """Find a DrawingML child of ``parent`` in the parent's own namespace profile."""
    return None if parent is None else find_ooxml(parent, f"{{{A_NS}}}{name}")


def _saved_properties(shape: Any) -> tuple[ET.Element | None, bool]:
    """Return the shape's saved ``p:spPr`` (or detached parent) and whether it is Strict."""
    detached = _detached_fill_parent(shape)
    if detached is not None:
        return detached, False
    if _is_pending_shape(shape):
        return None, False
    with open_package_source(shape._slide._presentation._source_path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    element = _shape_xml_element(root, shape._payload)
    if _xml_local_name(element.tag) not in {"sp", "cxnSp", "pic"}:
        raise TypeError("this format is only available on shapes, connectors and pictures")
    return find_ooxml(element, f"{{{P_NS}}}spPr"), ooxml_namespace(element, A_NS) != A_NS


def _color_text(holder: ET.Element | None) -> str | None:
    """Format the single colour inside a ``CT_Color`` holder."""
    if holder is None or not len(holder):
        return None
    try:
        color = holder[0]
        style = (
            "scheme"
            if _xml_local_name(color.tag) == "schemeClr"
            else "rgba"
            if color_alpha(color) != 1.0
            else "hex"
        )
        return color_element_to_string(color, style)
    except ValueError as exc:
        raise ThreeDFormatRefusal(f"unsupported 3-D colour: {exc}") from exc


def _token(vocabulary: str, label: str, *, optional: bool = False) -> Any:
    """Validator for a token of a :mod:`wolfppt.drawingml_3d_vocabulary` set."""

    def convert(value: Any) -> str | None:
        if value is None and optional:
            return None
        if not isinstance(value, str):
            raise TypeError(f"{label} must be a str")
        if value not in getattr(drawingml_3d_vocabulary, vocabulary):
            raise ThreeDFormatRefusal(f"{value!r} is not a DrawingML {label}")
        return value

    return convert


def _coordinate(label: str, *, signed: bool = False) -> Any:
    """Validator for an ST_Coordinate EMU length, non-negative unless signed."""

    def convert(value: Any) -> str:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{label} must be an integer EMU value")
        low = -_COORDINATE_MAX if signed else 0
        if not low <= value <= _COORDINATE_MAX:
            raise ThreeDFormatRefusal(f"{label} {value} is outside {low}..{_COORDINATE_MAX} EMU")
        return str(int(value))

    return convert


def _scaled(label: str, scale: int, maximum: float | None = None) -> Any:
    """Validator for an optional non-negative number stored times ``scale``."""

    def convert(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{label} must be a number or None")
        try:
            number = float(value)
        except OverflowError as exc:
            raise ThreeDFormatRefusal(f"{label} is too large") from exc
        if not math.isfinite(number):
            raise ThreeDFormatRefusal(f"{label} must be finite")
        if number < 0 or (maximum is not None and number > maximum):
            bound = "not be negative" if maximum is None else f"be between 0 and {maximum}"
            raise ThreeDFormatRefusal(f"{label} must {bound}")
        scaled = number * scale
        if not math.isfinite(scaled):
            raise ThreeDFormatRefusal(f"{label} is too large")
        return str(round(scaled))

    return convert


def _number(scale: int) -> Any:
    return lambda raw: None if raw is None else int(raw) / scale


def _percent(raw: str | None) -> float | None:
    """Read an ST_PositivePercentage as a fraction (1.0 is 100%).

    Transitional stores thousandths of a percent (``100000``); Strict stores ``100%``.
    Both lexical forms read back, whatever the part's profile.
    """
    if raw is None:
        return None
    return float(raw[:-1]) / 100 if raw.endswith("%") else int(raw) / 100000


def _emu_reader(missing: int | None) -> Any:
    """Read EMU text; ``missing`` (None or the schema default) when unset."""
    return lambda raw: None if raw is None and missing is None else _emu_value(int(raw or missing))


def _angle_units(value: Any, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number of degrees")
    if isinstance(value, float) and not math.isfinite(value):
        raise ThreeDFormatRefusal(f"{label} must be finite")
    return str(round(float(value % 360) * 60000) % _ANGLE_TURN)


def _rotation_attributes(value: Any) -> dict[str, str] | None:
    """Validate and normalize a (latitude, longitude, revolution) rotation."""
    if value is None:
        return None
    try:
        latitude, longitude, revolution = value
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "rotation must be a (latitude, longitude, revolution) tuple or None"
        ) from exc
    return {
        "lat": _angle_units(latitude, "latitude"),
        "lon": _angle_units(longitude, "longitude"),
        "rev": _angle_units(revolution, "revolution"),
    }


def _solid(properties: ET.Element | None) -> ET.Element | None:
    return _find(properties, "sp3d")


def _ensure_scene(properties: ET.Element) -> ET.Element:
    """Create ``scene3d`` with PowerPoint's defaults for a newly 3-D shape."""
    scene = properties.find(_a("scene3d"))
    if scene is None:
        scene = ET.Element(_a("scene3d"))
        _insert_ordered(properties, scene, _SHAPE_PROPERTIES_ORDER)
    _ensure_child(scene, "camera", _SCENE_ORDER, {"prst": "orthographicFront"})
    _ensure_child(scene, "lightRig", _SCENE_ORDER, {"rig": "threePt", "dir": "t"})
    return scene


def _ensure_solid(properties: ET.Element) -> ET.Element:
    """Create ``sp3d``; a solid without a scene draws flat, so add one too."""
    _ensure_scene(properties)
    return _ensure_child(properties, "sp3d", _SHAPE_PROPERTIES_ORDER)


class _Attribute:
    """One attribute of the element a 3-D part finds with ``_node``.

    ``to_xml`` validates a value into attribute text (None removes it);
    ``from_xml`` reads the text back; ``default`` stands in for an attribute
    the element omits. Setting the current value leaves the deck untouched.
    """

    def __init__(
        self,
        name: str,
        label: str,
        to_xml: Any,
        from_xml: Any = None,
        default: Any = None,
    ) -> None:
        self._name, self._label, self._default = name, label, default
        self._to_xml, self._from_xml = to_xml, from_xml

    def _raw(self, part: _ThreeDPart) -> str | None:
        node = part._node(part._properties())
        return None if node is None else node.get(self._name, self._default)

    def __get__(self, part: _ThreeDPart | None, owner: Any = None) -> Any:
        if part is None:
            return self
        raw = self._raw(part)
        return raw if self._from_xml is None else self._from_xml(raw)

    def __set__(self, part: _ThreeDPart, value: Any) -> None:
        xml, name = self._to_xml(value), self._name
        if xml == self._raw(part):
            return

        def mutate(properties: ET.Element) -> None:
            if xml is not None:
                part._ensure_node(properties).set(name, xml)
            elif (node := part._node(properties)) is not None:
                node.attrib.pop(name, None)

        part._edit(self._label, mutate)


class _Rotation:
    """The ``a:rot`` child as (latitude, longitude, revolution) degrees."""

    def __init__(self, label: str) -> None:
        self._label = label

    def __get__(self, part: _ThreeDPart | None, owner: Any = None) -> Any:
        if part is None:
            return self
        node = part._node(part._properties())
        rotation = _find(node, "rot")
        if rotation is None:
            return None
        return tuple(int(rotation.get(name, "0")) / 60000 for name in ("lat", "lon", "rev"))

    def __set__(self, part: _ThreeDPart, value: Any) -> None:
        attributes = _rotation_attributes(value)
        if value is None and self.__get__(part) is None:
            return

        def mutate(properties: ET.Element) -> None:
            node = part._ensure_node(properties)
            _remove_children(node, "rot")
            if attributes is not None:
                node.insert(0, ET.Element(_a("rot"), attributes))

        part._edit(self._label, mutate)


class _SolidColor:
    """An ``a:sp3d`` colour as opaque hex, exact RGBA or ``scheme:<name>`` text."""

    def __init__(self, name: str, label: str) -> None:
        self._name, self._label = name, label

    def __get__(self, part: ThreeDFormat | None, owner: Any = None) -> Any:
        if part is None:
            return self
        solid = _solid(part._properties())
        return _color_text(_find(solid, self._name))

    def __set__(self, part: ThreeDFormat, value: Any) -> None:
        name = self._name
        try:
            color = None if value is None else color_element_from_string(value)
        except ValueError as exc:
            raise ThreeDFormatRefusal(f"{self._label}: {exc}") from exc

        def mutate(properties: ET.Element) -> None:
            if (solid := _solid(properties)) is not None:
                _remove_children(solid, name)
            if color is not None:
                holder = _ensure_child(_ensure_solid(properties), name, _SOLID_ORDER)
                holder.append(color)

        part._edit(self._label, mutate)


class _ThreeDPart:
    """Shared read/edit plumbing; subclasses locate their element."""

    def __init__(self, shape: Any) -> None:
        self._shape = shape

    def _properties(self) -> ET.Element | None:
        return _saved_properties(self._shape)[0]

    def _edit(self, label: str, mutate: Any) -> None:
        if _saved_properties(self._shape)[1]:
            raise ThreeDFormatRefusal(
                f"setting 3-D {label} is not supported on Strict OOXML shapes; "
                "read the 3-D format or edit a Transitional deck"
            )
        _edit_shape_properties(self._shape, f"setting 3-D {label}", mutate)


class _ScenePart(_ThreeDPart):
    _child = ""

    def _node(self, properties: ET.Element | None) -> ET.Element | None:
        return _find(_find(properties, "scene3d"), self._child)

    def _ensure_node(self, properties: ET.Element) -> ET.Element:
        return _ensure_scene(properties).find(_a(self._child))


class CameraFormat(_ScenePart):
    """``a:scene3d/a:camera``: preset, field of view (degrees, 0-180), zoom
    (1.0 is 100%) and rotation; unset values read as None."""

    _child = "camera"
    preset = _Attribute("prst", "camera preset", _token("CAMERA_PRESETS", "camera preset"))
    field_of_view = _Attribute(
        "fov",
        "camera field of view",
        _scaled("field_of_view", 60000, 180),
        _number(60000),
    )
    zoom = _Attribute("zoom", "camera zoom", _scaled("zoom", 100000), _percent)
    rotation = _Rotation("camera rotation")


class LightRigFormat(_ScenePart):
    """``a:scene3d/a:lightRig``: preset, direction and rotation."""

    _child = "lightRig"
    preset = _Attribute("rig", "light rig preset", _token("LIGHT_RIG_PRESETS", "light rig"))
    direction = _Attribute(
        "dir",
        "light rig direction",
        _token("LIGHT_RIG_DIRECTIONS", "light rig direction"),
    )
    rotation = _Rotation("light rig rotation")


class BevelFormat(_ThreeDPart):
    """``a:sp3d/a:bevelT`` or ``a:bevelB``: preset type, width and height."""

    _preset = _Attribute(
        "prst",
        "bevel preset",
        _token("BEVEL_PRESETS", "bevel preset"),
        default="circle",
    )
    width = _Attribute("w", "bevel width", _coordinate("bevel width"), _emu_reader(None), "76200")
    height = _Attribute(
        "h", "bevel height", _coordinate("bevel height"), _emu_reader(None), "76200"
    )

    def __init__(self, shape: Any, name: str) -> None:
        super().__init__(shape)
        self._name = name

    def _node(self, properties: ET.Element | None) -> ET.Element | None:
        solid = _solid(properties)
        return _find(solid, self._name)

    def _ensure_node(self, properties: ET.Element) -> ET.Element:
        return _ensure_child(_ensure_solid(properties), self._name, _SOLID_ORDER)

    @property
    def preset(self) -> str | None:
        """ST_BevelPresetType; None when the shape has no such bevel."""
        return self._preset

    @preset.setter
    def preset(self, value: Any) -> None:
        if value is not None:
            self._preset = value
        elif self._node(self._properties()) is not None:
            self._edit("bevel", lambda p: _remove_children(_solid(p), self._name))


class ThreeDFormat(_ThreeDPart):
    """Typed read/edit access to a shape's ``a:scene3d`` and ``a:sp3d``.

    ``depth`` is the distance of the shape from the ground plane (``sp3d@z``).
    ``contour_width`` is the full width of the solid contour line in EMU.
    Schema-valid authoring is broader than native rendering: the latter
    admits centered mitered contours on convex straight-edged shapes without
    bevels. Zero width draws no contour; omitted colour defaults to black.
    """

    extrusion_height = _Attribute(
        "extrusionH",
        "extrusion height",
        _coordinate("extrusion height"),
        _emu_reader(0),
    )
    extrusion_color = _SolidColor("extrusionClr", "extrusion colour")
    contour_width = _Attribute(
        "contourW", "contour width", _coordinate("contour width"), _emu_reader(0)
    )
    contour_color = _SolidColor("contourClr", "contour colour")
    depth = _Attribute("z", "depth", _coordinate("depth", signed=True), _emu_reader(0))
    material = _Attribute(
        "prstMaterial",
        "material",
        _token("MATERIAL_PRESETS", "material", optional=True),
    )

    def _node(self, properties: ET.Element | None) -> ET.Element | None:
        return _solid(properties)

    def _ensure_node(self, properties: ET.Element) -> ET.Element:
        return _ensure_solid(properties)

    @property
    def camera(self) -> CameraFormat:
        return CameraFormat(self._shape)

    @property
    def light_rig(self) -> LightRigFormat:
        return LightRigFormat(self._shape)

    @property
    def bevel_top(self) -> BevelFormat:
        return BevelFormat(self._shape, "bevelT")

    @property
    def bevel_bottom(self) -> BevelFormat:
        return BevelFormat(self._shape, "bevelB")

    @property
    def has_scene(self) -> bool:
        return _find(self._properties(), "scene3d") is not None

    @property
    def has_solid(self) -> bool:
        return _solid(self._properties()) is not None

    @property
    def backdrop(self) -> Backdrop | None:
        """``a:scene3d/a:backdrop`` as a :class:`Backdrop`; None when absent.

        Assign a :class:`Backdrop` (or an ``(anchor, normal, up)`` triple of integer
        triples) to create or replace it, or None to remove it. A scene that is
        missing is created with PowerPoint's default camera and light rig, and an
        existing backdrop keeps its extension list.
        """
        node = _find(_find(self._properties(), "scene3d"), "backdrop")
        if node is None:
            return None
        values = []
        for name, keys in _BACKDROP_PARTS:
            child = _find(node, name)
            if child is None:
                raise ThreeDFormatRefusal(f"the saved backdrop has no a:{name}")
            try:
                values.append(tuple(int(child.get(key, "0")) for key in keys))
            except ValueError as exc:
                raise ThreeDFormatRefusal(f"the saved backdrop a:{name} is not integral") from exc
        return Backdrop(*values)

    @backdrop.setter
    def backdrop(self, value: Any) -> None:
        if value is None:
            if _find(_find(self._properties(), "scene3d"), "backdrop") is not None:
                self._edit(
                    "backdrop removal",
                    lambda properties: _remove_children(_find(properties, "scene3d"), "backdrop"),
                )
            return
        try:
            anchor, normal, up = value
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "backdrop must be a Backdrop, an (anchor, normal, up) triple or None"
            ) from exc
        wanted = Backdrop(
            _coordinates(anchor, "backdrop anchor"),
            _coordinates(normal, "backdrop normal"),
            _coordinates(up, "backdrop up"),
        )
        if self.backdrop == wanted:
            return

        def mutate(properties: ET.Element) -> None:
            scene = _ensure_scene(properties)
            backdrop = _ensure_child(scene, "backdrop", _SCENE_ORDER)
            for name, _ in _BACKDROP_PARTS:
                _remove_children(backdrop, name)
            for position, ((name, keys), numbers) in enumerate(
                zip(_BACKDROP_PARTS, wanted, strict=True)
            ):
                backdrop.insert(
                    position,
                    ET.Element(
                        _a(name), {key: str(n) for key, n in zip(keys, numbers, strict=True)}
                    ),
                )

        self._edit("backdrop", mutate)

    def clear_scene(self) -> None:
        """Remove the shape's own ``a:scene3d`` (camera, light rig, backdrop)."""
        if self.has_scene:
            self._edit("scene removal", lambda target: _remove_children(target, "scene3d"))

    def clear_solid(self) -> None:
        """Remove the shape's own ``a:sp3d`` (bevels, extrusion, contour, material)."""
        if self.has_solid:
            self._edit("solid removal", lambda target: _remove_children(target, "sp3d"))

    def clear(self) -> None:
        """Remove the shape's own scene and solid, restoring a flat shape."""
        if not self.has_scene and not self.has_solid:
            return

        def mutate(target: ET.Element) -> None:
            _remove_children(target, "scene3d")
            _remove_children(target, "sp3d")

        self._edit("format removal", mutate)
