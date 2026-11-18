"""Freeform shape builder facade and the public ``a:custGeom`` read/edit model."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Any, NamedTuple
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as _escape

from .facade_values import coerce_emu as _coerce_emu
from .package_parts import package_xml_element as _package_xml_element
from .shape_inspection import _next_shape_id
from .shape_xml import _shape_xml_element

__all__ = [
    "ConnectionSite",
    "CustomGeometry",
    "CustomGeometryError",
    "FreeformBuilder",
    "GeometryGuide",
    "GeometryPath",
    "GeometryPoint",
    "GeometryRect",
    "PathSegment",
    "PolarAdjustHandle",
    "XYAdjustHandle",
]


class FreeformBuilder(Sequence[dict[str, Any]]):
    def __init__(
        self,
        shapes: Any,
        shape_factory: Any,
        start_x: float = 0,
        start_y: float = 0,
        x_scale: float = 1.0,
        y_scale: float = 1.0,
    ) -> None:
        self._shapes = shapes
        self._shape_factory = shape_factory
        self._start_x = int(round(start_x))
        self._start_y = int(round(start_y))
        self._x_scale = float(x_scale)
        self._y_scale = float(y_scale)
        self._operations: list[dict[str, int | str]] = []
        self._path_attributes: GeometryPath | None = None
        self._adjust_values: list[GeometryGuide] = []
        self._guides: list[GeometryGuide] = []
        self._handles: list[XYAdjustHandle | PolarAdjustHandle] = []
        self._sites: list[ConnectionSite] = []

    def __getitem__(self, index: int | slice) -> Any:
        return self._operations[index]

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._operations)

    def __len__(self) -> int:
        return len(self._operations)

    def add_line_segments(
        self,
        vertices: Sequence[tuple[float, float]],
        close: bool = True,
    ) -> FreeformBuilder:
        for x, y in vertices:
            self._operations.append({"type": "line_to", "x": int(round(x)), "y": int(round(y))})
        if close:
            self._operations.append({"type": "close"})
        return self

    def move_to(self, x: float, y: float) -> FreeformBuilder:
        self._operations.append({"type": "move_to", "x": int(round(x)), "y": int(round(y))})
        return self

    def add_arc_to(
        self,
        width_radius: float,
        height_radius: float,
        start_angle: int,
        swing_angle: int,
    ) -> FreeformBuilder:
        """Append ``a:arcTo`` from the current point.

        Radii are in builder coordinates; angles are in 60,000ths of a degree,
        as in DrawingML: ``start_angle`` places the current point on the
        ellipse and the arc sweeps ``swing_angle`` (positive is clockwise).
        """
        segment = PathSegment(
            "arc_to",
            width_radius=int(round(width_radius)),
            height_radius=int(round(height_radius)),
            start_angle=start_angle,
            swing_angle=swing_angle,
        )
        _check_segment(segment, "arc_to")
        for field in ("width_radius", "height_radius"):
            if getattr(segment, field) < 0:
                raise CustomGeometryError(f"arc_to.{field} must not be negative")
        self._operations.append(
            {
                "type": "arc_to",
                "wr": segment.width_radius,
                "hr": segment.height_radius,
                "st_ang": start_angle,
                "sw_ang": swing_angle,
            }
        )
        return self

    def add_quadratic_bezier(
        self, control: tuple[float, float], end: tuple[float, float]
    ) -> FreeformBuilder:
        """Append ``a:quadBezTo`` through ``control`` to ``end``."""
        (x1, y1), (x, y) = control, end
        self._operations.append(
            {
                "type": "quad_bezier_to",
                "x1": int(round(x1)),
                "y1": int(round(y1)),
                "x": int(round(x)),
                "y": int(round(y)),
            }
        )
        return self

    def add_cubic_bezier(
        self,
        control1: tuple[float, float],
        control2: tuple[float, float],
        end: tuple[float, float],
    ) -> FreeformBuilder:
        """Append ``a:cubicBezTo`` through ``control1`` and ``control2`` to ``end``."""
        (x1, y1), (x2, y2), (x, y) = control1, control2, end
        self._operations.append(
            {
                "type": "cubic_bezier_to",
                "x1": int(round(x1)),
                "y1": int(round(y1)),
                "x2": int(round(x2)),
                "y2": int(round(y2)),
                "x": int(round(x)),
                "y": int(round(y)),
            }
        )
        return self

    def set_path_attributes(
        self,
        fill: str | None = None,
        stroke: bool | None = None,
        extrusion_ok: bool | None = None,
    ) -> FreeformBuilder:
        """Set the ``a:path`` ``fill`` mode, ``stroke`` and ``extrusionOk``.

        ``None`` leaves an attribute absent (its schema default applies).
        """
        attributes = GeometryPath(fill=fill, stroke=stroke, extrusion_ok=extrusion_ok)
        _check_path(attributes, "path")
        self._path_attributes = attributes
        return self

    def add_adjust_value(self, name: str, formula: str) -> FreeformBuilder:
        """Append an ``a:avLst`` guide (an adjust value a handle can drive)."""
        guide = GeometryGuide(name, formula)
        _check_guides((guide,), "adjust_value")
        self._adjust_values.append(guide)
        return self

    def add_guide(self, name: str, formula: str) -> FreeformBuilder:
        """Append an ``a:gdLst`` shape guide."""
        guide = GeometryGuide(name, formula)
        _check_guides((guide,), "guide")
        self._guides.append(guide)
        return self

    def add_adjust_handle(self, handle: XYAdjustHandle | PolarAdjustHandle) -> FreeformBuilder:
        """Append an ``a:ahXY`` or ``a:ahPolar`` handle.

        An integer position coordinate is a builder coordinate, like a segment
        point; a string is a guide name.
        """
        validate_custom_geometry(CustomGeometry(handles=(handle,)))
        self._handles.append(handle)
        return self

    def add_connection_site(self, site: ConnectionSite) -> FreeformBuilder:
        """Append an ``a:cxn`` connection site; positions as in ``add_adjust_handle``."""
        validate_custom_geometry(CustomGeometry(connection_sites=(site,)))
        self._sites.append(site)
        return self

    @property
    def shape_offset_x(self) -> int:
        return min(x for x, _ in self._points)

    @property
    def shape_offset_y(self) -> int:
        return min(y for _, y in self._points)

    def convert_to_shape(self, origin_x: int = 0, origin_y: int = 0) -> Any:
        offset_x = self.shape_offset_x
        offset_y = self.shape_offset_y
        path_w = max(x for x, _ in self._points) - offset_x
        path_h = max(y for _, y in self._points) - offset_y
        x_emu = _coerce_emu(origin_x, "origin_x") + int(round(offset_x * self._x_scale))
        y_emu = _coerce_emu(origin_y, "origin_y") + int(round(offset_y * self._y_scale))
        cx_emu = int(round(path_w * self._x_scale))
        cy_emu = int(round(path_h * self._y_scale))
        path_operations = self._path_operations(offset_x, offset_y)
        path_operations += self._geometry_operations(offset_x, offset_y)
        shape_index = len(self._shapes._shapes)
        is_group_child = hasattr(self._shapes, "_group_shape")
        nested_group_child_index: int | None = None
        deeper_group_child_index: int | None = None
        if is_group_child:
            slide = self._shapes._group_shape._slide
            group_index = self._shapes._group_ordinal()
            if self._shapes._is_deeper_nested_group_target():
                group_index = int(self._shapes._group_shape._payload["_group_index"])
                nested_group_child_index = int(
                    self._shapes._group_shape._payload["_nested_group_child_index"]
                )
                deeper_group_child_index = int(
                    self._shapes._group_shape._payload["_group_child_index"]
                )
                slide._presentation._queue_deeper_nested_group_freeform_shape_add(
                    slide._index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    shape_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    path_operations,
                )
            elif self._shapes._is_nested_group_target():
                group_index = int(self._shapes._group_shape._payload["_group_index"])
                nested_group_child_index = int(
                    self._shapes._group_shape._payload["_group_child_index"]
                )
                slide._presentation._queue_nested_group_freeform_shape_add(
                    slide._index,
                    group_index,
                    nested_group_child_index,
                    shape_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    path_operations,
                )
            else:
                slide._presentation._queue_group_freeform_shape_add(
                    slide._index,
                    group_index,
                    shape_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    path_operations,
                )
        else:
            slide = self._shapes._slide
            shape_id = _next_shape_id(self._shapes._shapes)
            slide._presentation._queue_freeform_shape_add(
                slide._index,
                shape_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                path_w,
                path_h,
                path_operations,
            )
            group_index = None
        if is_group_child:
            shape_id = self._shapes._next_pending_shape_id()
            identity_payload = {"id": str(shape_id), "_pending_shape": True}
        else:
            identity_payload = {"id": str(shape_id), "_pending_shape": True}
        shape = self._shape_factory(
            slide,
            shape_index,
            {
                **identity_payload,
                "name": f"Freeform {shape_index + 1}",
                "kind": "freeform",
                "text": "",
                "paragraphs": [""],
                "paragraph_runs": [[]],
                "transform": {
                    "x": x_emu,
                    "y": y_emu,
                    "cx": cx_emu,
                    "cy": cy_emu,
                },
                **(
                    {
                        "_group_child": True,
                        "_pending_group_child": True,
                        "_pending_group_child_kind": "freeform",
                        "_group_shape_index": self._shapes._group_shape._index,
                        "_group_index": group_index,
                        "_group_child_index": shape_index,
                        **(
                            {
                                "_nested_group_child": True,
                                "_nested_group_child_index": nested_group_child_index,
                            }
                            if nested_group_child_index is not None
                            else {}
                        ),
                        **(
                            {
                                "_deep_nested_group_child": True,
                                "_deeper_group_child_index": deeper_group_child_index,
                            }
                            if deeper_group_child_index is not None
                            else {}
                        ),
                    }
                    if is_group_child
                    else {}
                ),
            },
        )
        if is_group_child:
            self._shapes._append_pending_shape(shape)
        else:
            self._shapes._shapes.append(shape)
        return shape

    @property
    def _points(self) -> list[tuple[int, int]]:
        """Every point bounding the path: vertices, control points, arc extremes."""
        start = (self._start_x, self._start_y)
        points = [start]
        current = subpath = start
        for operation in self._operations:
            kind = operation["type"]
            if kind == "close":
                current = subpath
                continue
            if kind == "arc_to":
                arc = _arc_points(current, operation)
                points.extend(arc)
                current = arc[-1]
                continue
            for suffix in ("1", "2", ""):
                if f"x{suffix}" in operation:
                    points.append((int(operation[f"x{suffix}"]), int(operation[f"y{suffix}"])))
            current = (int(operation["x"]), int(operation["y"]))
            if kind == "move_to":
                subpath = current
        return points

    def _path_operations(
        self,
        offset_x: int,
        offset_y: int,
    ) -> list[dict[str, int | str]]:
        operations: list[dict[str, int | str]] = [
            {
                "type": "move_to",
                "x": self._start_x - offset_x,
                "y": self._start_y - offset_y,
            }
        ]
        for operation in self._operations:
            shifted = dict(operation)
            for key in ("x", "x1", "x2"):
                if key in shifted:
                    shifted[key] = int(shifted[key]) - offset_x
            for key in ("y", "y1", "y2"):
                if key in shifted:
                    shifted[key] = int(shifted[key]) - offset_y
            operations.append(shifted)
        return operations

    def _geometry_operations(self, offset_x: int, offset_y: int) -> list[dict[str, Any]]:
        """The path attributes, guides, handles and sites as native operations."""

        def text(value: int | str | None, offset: int = 0) -> str | None:
            if value is None:
                return None
            return str(value - offset) if isinstance(value, int) else value

        def position(point: GeometryPoint) -> dict[str, str | None]:
            return {"x": text(point[0], offset_x), "y": text(point[1], offset_y)}

        operations: list[dict[str, Any]] = []
        if self._path_attributes is not None:
            attributes = self._path_attributes
            operations.append(
                {
                    "type": "path_attributes",
                    "fill": attributes.fill,
                    "stroke": attributes.stroke,
                    "extrusion_ok": attributes.extrusion_ok,
                }
            )
        for kind, guides in (("adjust_value", self._adjust_values), ("guide", self._guides)):
            operations.extend(
                {"type": kind, "name": guide.name, "fmla": guide.formula} for guide in guides
            )
        for handle in self._handles:
            xy = isinstance(handle, XYAdjustHandle)
            fields = _HANDLE_OPERATION_FIELDS[xy]
            operations.append(
                {
                    "type": "adjust_handle_xy" if xy else "adjust_handle_polar",
                    **position(handle.position),
                    **{key: text(getattr(handle, field)) for field, key in fields},
                }
            )
        operations.extend(
            {"type": "connection_site", "ang": text(site.angle), **position(site.position)}
            for site in self._sites
        )
        return operations


def _ellipse_point(width_radius: int, height_radius: int, angle: float) -> tuple[float, float]:
    """The ellipse point at DrawingML (visual) ``angle`` in radians, relative to its center."""
    parametric = math.atan2(width_radius * math.sin(angle), height_radius * math.cos(angle))
    return width_radius * math.cos(parametric), height_radius * math.sin(parametric)


def _arc_points(current: tuple[int, int], operation: dict[str, int | str]) -> list[tuple[int, int]]:
    """The axis extremes the arc passes through, ending with its end point."""
    width_radius, height_radius = int(operation["wr"]), int(operation["hr"])
    start = int(operation["st_ang"])
    end = start + int(operation["sw_ang"])
    start_x, start_y = _ellipse_point(width_radius, height_radius, math.radians(start / 60000))
    center = (current[0] - start_x, current[1] - start_y)
    low, high = min(start, end), max(start, end)
    quarter = 5_400_000
    angles = [a * quarter for a in range(-(-low // quarter), high // quarter + 1)]
    points = []
    for angle in [*angles, end]:
        x, y = _ellipse_point(width_radius, height_radius, math.radians(angle / 60000))
        points.append((int(round(center[0] + x)), int(round(center[1] + y))))
    return points


# --------------------------------------------------------------------------------------------
# a:custGeom model (CT_CustomGeometry2D), Strict and transitional
# --------------------------------------------------------------------------------------------

_DRAWINGML_NAMESPACES = frozenset(
    {
        "http://schemas.openxmlformats.org/drawingml/2006/main",
        "http://purl.oclc.org/ooxml/drawingml/main",
    }
)
_FILL_MODES = frozenset({"none", "norm", "lighten", "lightenLess", "darken", "darkenLess"})
# Segment kind -> (CT_Path2D child local name, point count).
_SEGMENTS = {
    "move_to": ("moveTo", 1),
    "line_to": ("lnTo", 1),
    "arc_to": ("arcTo", 0),
    "quad_bezier_to": ("quadBezTo", 2),
    "cubic_bezier_to": ("cubicBezTo", 3),
    "close": ("close", 0),
}
_SEGMENT_KINDS = {local: kind for kind, (local, _) in _SEGMENTS.items()}
_ARC_ATTRIBUTES = (
    ("width_radius", "wR"),
    ("height_radius", "hR"),
    ("start_angle", "stAng"),
    ("swing_angle", "swAng"),
)
_XY_ATTRIBUTES = (
    ("guide_x", "gdRefX"),
    ("min_x", "minX"),
    ("max_x", "maxX"),
    ("guide_y", "gdRefY"),
    ("min_y", "minY"),
    ("max_y", "maxY"),
)
_POLAR_ATTRIBUTES = (
    ("guide_radius", "gdRefR"),
    ("min_radius", "minR"),
    ("max_radius", "maxR"),
    ("guide_angle", "gdRefAng"),
    ("min_angle", "minAng"),
    ("max_angle", "maxAng"),
)
_GUIDE_REFERENCES = frozenset({"guide_x", "guide_y", "guide_radius", "guide_angle"})
# Handle field -> native freeform operation key, keyed by "is an XY handle".
_HANDLE_OPERATION_FIELDS = {
    True: tuple(
        zip(
            (field for field, _ in _XY_ATTRIBUTES),
            ("gd_ref_x", "min_x", "max_x", "gd_ref_y", "min_y", "max_y"),
            strict=True,
        )
    ),
    False: tuple(
        zip(
            (field for field, _ in _POLAR_ATTRIBUTES),
            ("gd_ref_r", "min_r", "max_r", "gd_ref_ang", "min_ang", "max_ang"),
            strict=True,
        )
    ),
}
# CT_CustomGeometry2D child order.
_SECTIONS = ("avLst", "gdLst", "ahLst", "cxnLst", "rect", "pathLst")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)")


class CustomGeometryError(ValueError):
    """A custom geometry edit was refused; nothing was written."""


class GeometryPoint(NamedTuple):
    """``a:pt`` / ``a:pos``: an integer coordinate or a guide name per axis."""

    x: int | str
    y: int | str


class GeometryRect(NamedTuple):
    """``a:rect``: the text rectangle, each side an integer or a guide name."""

    left: int | str
    top: int | str
    right: int | str
    bottom: int | str


@dataclass(frozen=True)
class GeometryGuide:
    """``a:gd`` in ``a:avLst`` (adjust value) or ``a:gdLst`` (shape guide)."""

    name: str
    formula: str


@dataclass(frozen=True)
class XYAdjustHandle:
    """``a:ahXY``; an attribute left ``None`` is absent from the XML."""

    position: GeometryPoint
    guide_x: str | None = None
    min_x: int | str | None = None
    max_x: int | str | None = None
    guide_y: str | None = None
    min_y: int | str | None = None
    max_y: int | str | None = None


@dataclass(frozen=True)
class PolarAdjustHandle:
    """``a:ahPolar``; an attribute left ``None`` is absent from the XML."""

    position: GeometryPoint
    guide_radius: str | None = None
    min_radius: int | str | None = None
    max_radius: int | str | None = None
    guide_angle: str | None = None
    min_angle: int | str | None = None
    max_angle: int | str | None = None


@dataclass(frozen=True)
class ConnectionSite:
    """``a:cxn``: a connection site angle and position."""

    angle: int | str
    position: GeometryPoint


@dataclass(frozen=True)
class PathSegment:
    """One ``a:path`` command.

    ``kind`` is ``move_to``/``line_to`` (one point), ``quad_bezier_to`` (two),
    ``cubic_bezier_to`` (three), ``arc_to`` (no points; the four radius and
    angle fields are required) or ``close``.
    """

    kind: str
    points: tuple[GeometryPoint, ...] = ()
    width_radius: int | str | None = None
    height_radius: int | str | None = None
    start_angle: int | str | None = None
    swing_angle: int | str | None = None


@dataclass(frozen=True)
class GeometryPath:
    """``a:path``; an attribute left ``None`` is absent and takes its schema default."""

    segments: tuple[PathSegment, ...] = ()
    width: int | None = None
    height: int | None = None
    fill: str | None = None
    stroke: bool | None = None
    extrusion_ok: bool | None = None


@dataclass(frozen=True)
class CustomGeometry:
    """The content of a shape's ``a:custGeom``.

    Read it from ``Shape.custom_geometry``; edit it with
    :func:`dataclasses.replace` and assign it back.
    """

    paths: tuple[GeometryPath, ...] = ()
    adjust_guides: tuple[GeometryGuide, ...] = ()
    guides: tuple[GeometryGuide, ...] = ()
    handles: tuple[XYAdjustHandle | PolarAdjustHandle, ...] = ()
    connection_sites: tuple[ConnectionSite, ...] = ()
    text_rect: GeometryRect | None = None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, local: str) -> list[ET.Element]:
    return [item for item in element if _local(item.tag) == local]


def _child(element: ET.Element, local: str) -> ET.Element | None:
    found = _children(element, local)
    return found[0] if found else None


def _value(raw: str | None) -> int | str | None:
    if raw is None:
        return None
    return int(raw) if _INTEGER.fullmatch(raw) else raw


def _flag(raw: str | None) -> bool | None:
    return None if raw is None else raw in ("1", "true")


def _point(element: ET.Element | None) -> GeometryPoint:
    if element is None:
        raise CustomGeometryError("custom geometry point is missing")
    return GeometryPoint(_value(element.get("x")), _value(element.get("y")))


def _parse_guides(section: ET.Element | None) -> tuple[GeometryGuide, ...]:
    if section is None:
        return ()
    return tuple(
        GeometryGuide(item.get("name", ""), item.get("fmla", ""))
        for item in _children(section, "gd")
    )


def _parse_handles(
    section: ET.Element | None,
) -> tuple[XYAdjustHandle | PolarAdjustHandle, ...]:
    handles: list[XYAdjustHandle | PolarAdjustHandle] = []
    for item in [] if section is None else list(section):
        local = _local(item.tag)
        if local not in ("ahXY", "ahPolar"):
            continue
        cls, attributes = (
            (XYAdjustHandle, _XY_ATTRIBUTES)
            if local == "ahXY"
            else (PolarAdjustHandle, _POLAR_ATTRIBUTES)
        )
        values = {
            field: item.get(attr) if field in _GUIDE_REFERENCES else _value(item.get(attr))
            for field, attr in attributes
        }
        handles.append(cls(_point(_child(item, "pos")), **values))
    return tuple(handles)


def _parse_sites(section: ET.Element | None) -> tuple[ConnectionSite, ...]:
    if section is None:
        return ()
    return tuple(
        ConnectionSite(_value(item.get("ang")), _point(_child(item, "pos")))
        for item in _children(section, "cxn")
    )


def _parse_rect(element: ET.Element | None) -> GeometryRect | None:
    if element is None:
        return None
    return GeometryRect(*(_value(element.get(side)) for side in ("l", "t", "r", "b")))


def _parse_segment(element: ET.Element) -> PathSegment:
    kind = _SEGMENT_KINDS[_local(element.tag)]
    arc = (
        {field: _value(element.get(attr)) for field, attr in _ARC_ATTRIBUTES}
        if kind == "arc_to"
        else {}
    )
    return PathSegment(kind, tuple(_point(pt) for pt in _children(element, "pt")), **arc)


def _parse_paths(section: ET.Element | None) -> tuple[GeometryPath, ...]:
    if section is None:
        return ()
    return tuple(
        GeometryPath(
            tuple(
                _parse_segment(segment) for segment in item if _local(segment.tag) in _SEGMENT_KINDS
            ),
            _value(item.get("w")),
            _value(item.get("h")),
            item.get("fill"),
            _flag(item.get("stroke")),
            _flag(item.get("extrusionOk")),
        )
        for item in _children(section, "path")
    )


def _parse_section(element: ET.Element | None, section: str) -> Any:
    if section in ("avLst", "gdLst"):
        return _parse_guides(element)
    if section == "ahLst":
        return _parse_handles(element)
    if section == "cxnLst":
        return _parse_sites(element)
    if section == "rect":
        return _parse_rect(element)
    return _parse_paths(element)


def parse_custom_geometry(element: ET.Element) -> CustomGeometry:
    """Parse an ``a:custGeom`` element of either profile into the public model."""
    sections = {section: _parse_section(_child(element, section), section) for section in _SECTIONS}
    return CustomGeometry(
        paths=sections["pathLst"],
        adjust_guides=sections["avLst"],
        guides=sections["gdLst"],
        handles=sections["ahLst"],
        connection_sites=sections["cxnLst"],
        text_rect=sections["rect"],
    )


def _sections(geometry: CustomGeometry) -> dict[str, Any]:
    return {
        "avLst": geometry.adjust_guides,
        "gdLst": geometry.guides,
        "ahLst": geometry.handles,
        "cxnLst": geometry.connection_sites,
        "rect": geometry.text_rect,
        "pathLst": geometry.paths,
    }


def _shape_custom_geometry_element(shape_element: ET.Element) -> ET.Element | None:
    properties = _child(shape_element, "spPr")
    if properties is None:
        return None
    for item in properties:
        namespace = item.tag[1:].split("}", 1)[0] if item.tag.startswith("{") else ""
        if _local(item.tag) == "custGeom" and namespace in _DRAWINGML_NAMESPACES:
            return item
    return None


def read_custom_geometry(shape: Any) -> CustomGeometry | None:
    """Return ``shape``'s ``a:custGeom`` model, or ``None`` when it has no custom geometry."""
    if shape._payload.get("_pending_shape") or shape._payload.get("_pending_group_child"):
        return None
    slide = shape._slide
    try:
        root = _package_xml_element(slide._presentation._source_path, slide.partname)
        element = _shape_xml_element(root._element, shape._payload)
    except AttributeError:
        return None
    geometry = _shape_custom_geometry_element(element)
    return None if geometry is None else parse_custom_geometry(geometry)


# -- validation -------------------------------------------------------------------------------


def _check_tuple(value: Any, label: str, item_type: Any) -> tuple[Any, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{label} must be a tuple, got {type(value).__name__}")
    for item in value:
        if not isinstance(item, item_type):
            raise TypeError(f"{label} items must be {item_type}, got {type(item).__name__}")
    return value


def _check_token(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string, got {type(value).__name__}")
    if not value or any(char.isspace() for char in value):
        raise CustomGeometryError(f"{label} must be a non-empty name without spaces: {value!r}")


def _check_value(value: Any, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise TypeError(f"{label} must be an int or a guide name, got {type(value).__name__}")
    if isinstance(value, str):
        _check_token(value, label)


def _check_point(value: Any, label: str) -> None:
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"{label} must be a GeometryPoint (x, y)")
    _check_value(value[0], f"{label}.x")
    _check_value(value[1], f"{label}.y")


def _check_guides(guides: Any, label: str) -> None:
    for index, guide in enumerate(_check_tuple(guides, label, GeometryGuide)):
        _check_token(guide.name, f"{label}[{index}].name")
        if not isinstance(guide.formula, str) or not guide.formula.strip():
            raise CustomGeometryError(f"{label}[{index}].formula must be a non-empty string")


def _check_segment(segment: PathSegment, label: str) -> None:
    if segment.kind not in _SEGMENTS:
        raise CustomGeometryError(
            f"{label}.kind must be one of {sorted(_SEGMENTS)}, got {segment.kind!r}"
        )
    points = _check_tuple(segment.points, f"{label}.points", tuple)
    expected = _SEGMENTS[segment.kind][1]
    if len(points) != expected:
        raise CustomGeometryError(
            f"{label} ({segment.kind}) takes {expected} point(s), got {len(points)}"
        )
    for index, point in enumerate(points):
        _check_point(point, f"{label}.points[{index}]")
    for field, _ in _ARC_ATTRIBUTES:
        value = getattr(segment, field)
        if segment.kind == "arc_to":
            if value is None:
                raise CustomGeometryError(f"{label} (arc_to) requires {field}")
            _check_value(value, f"{label}.{field}")
        elif value is not None:
            raise CustomGeometryError(f"{label} ({segment.kind}) takes no {field}")


def _check_path(path: GeometryPath, label: str) -> None:
    for field in ("width", "height"):
        value = getattr(path, field)
        _check_value(value, f"{label}.{field}", optional=True)
        if isinstance(value, int) and value < 0:
            raise CustomGeometryError(f"{label}.{field} must not be negative")
    if path.fill is not None and path.fill not in _FILL_MODES:
        raise CustomGeometryError(
            f"{label}.fill must be one of {sorted(_FILL_MODES)}, got {path.fill!r}"
        )
    for field in ("stroke", "extrusion_ok"):
        if getattr(path, field) not in (None, True, False):
            raise TypeError(f"{label}.{field} must be a bool or None")
    segments = _check_tuple(path.segments, f"{label}.segments", PathSegment)
    for index, segment in enumerate(segments):
        _check_segment(segment, f"{label}.segments[{index}]")


def validate_custom_geometry(geometry: Any) -> CustomGeometry:
    """Check every field of ``geometry``; raise before anything is written."""
    if not isinstance(geometry, CustomGeometry):
        raise TypeError(f"custom geometry must be a CustomGeometry, got {type(geometry).__name__}")
    _check_guides(geometry.adjust_guides, "adjust_guides")
    _check_guides(geometry.guides, "guides")
    handles = _check_tuple(geometry.handles, "handles", XYAdjustHandle | PolarAdjustHandle)
    for index, handle in enumerate(handles):
        label = f"handles[{index}]"
        _check_point(handle.position, f"{label}.position")
        xy = isinstance(handle, XYAdjustHandle)
        for field, _ in _XY_ATTRIBUTES if xy else _POLAR_ATTRIBUTES:
            value = getattr(handle, field)
            if field in _GUIDE_REFERENCES:
                if value is not None:
                    _check_token(value, f"{label}.{field}")
            else:
                _check_value(value, f"{label}.{field}", optional=True)
    sites = _check_tuple(geometry.connection_sites, "connection_sites", ConnectionSite)
    for index, site in enumerate(sites):
        _check_value(site.angle, f"connection_sites[{index}].angle")
        _check_point(site.position, f"connection_sites[{index}].position")
    if geometry.text_rect is not None:
        if not isinstance(geometry.text_rect, tuple) or len(geometry.text_rect) != 4:
            raise TypeError("text_rect must be a GeometryRect (left, top, right, bottom) or None")
        for side, value in zip(GeometryRect._fields, geometry.text_rect, strict=True):
            _check_value(value, f"text_rect.{side}")
    for index, path in enumerate(_check_tuple(geometry.paths, "paths", GeometryPath)):
        _check_path(path, f"paths[{index}]")
    return geometry


# -- byte-stable writeback --------------------------------------------------------------------


def _attrs(pairs: Sequence[tuple[str, Any]]) -> str:
    return "".join(
        f' {name}="{_escape(str(value), {chr(34): "&quot;"})}"'
        for name, value in pairs
        if value is not None
    )


def _flag_text(value: bool | None) -> str | None:
    return None if value is None else ("1" if value else "0")


def _serialize_section(section: str, value: Any, prefix: str) -> str:
    def tag(local: str, attributes: Sequence[tuple[str, Any]] = (), body: str = "") -> str:
        name = f"{prefix}{local}"
        head = f"<{name}{_attrs(attributes)}"
        return f"{head}>{body}</{name}>" if body else f"{head}/>"

    def point(local: str, value: GeometryPoint) -> str:
        return tag(local, (("x", value[0]), ("y", value[1])))

    def handle_xml(handle: XYAdjustHandle | PolarAdjustHandle) -> str:
        xy = isinstance(handle, XYAdjustHandle)
        attributes = _XY_ATTRIBUTES if xy else _POLAR_ATTRIBUTES
        return tag(
            "ahXY" if xy else "ahPolar",
            [(attr, getattr(handle, field)) for field, attr in attributes],
            point("pos", handle.position),
        )

    def segment_xml(segment: PathSegment) -> str:
        return tag(
            _SEGMENTS[segment.kind][0],
            [(attr, getattr(segment, field)) for field, attr in _ARC_ATTRIBUTES],
            "".join(point("pt", pt) for pt in segment.points),
        )

    def path_xml(path: GeometryPath) -> str:
        attributes = (
            ("w", path.width),
            ("h", path.height),
            ("fill", path.fill),
            ("stroke", _flag_text(path.stroke)),
            ("extrusionOk", _flag_text(path.extrusion_ok)),
        )
        return tag("path", attributes, "".join(segment_xml(s) for s in path.segments))

    if section == "rect":
        return tag("rect", tuple(zip(("l", "t", "r", "b"), value, strict=True)))
    if section in ("avLst", "gdLst"):
        body = "".join(tag("gd", (("name", g.name), ("fmla", g.formula))) for g in value)
    elif section == "ahLst":
        body = "".join(handle_xml(handle) for handle in value)
    elif section == "cxnLst":
        body = "".join(
            tag("cxn", (("ang", site.angle),), point("pos", site.position)) for site in value
        )
    else:
        body = "".join(path_xml(path) for path in value)
    return tag(section, (), body)


_TAG_TAIL = rb"(?:[^>\"']|\"[^\"]*\"|'[^']*')*?(/?)>"
_CUSTGEOM_START = re.compile(rb"<(?:([A-Za-z_][\w.\-]*):)?custGeom(?=[\s/>])" + _TAG_TAIL)
_TOKEN = re.compile(
    rb"<!--.*?-->|<\?.*?\?>|<(/?)(?:[A-Za-z_][\w.\-]*:)?([A-Za-z_][\w.\-]*)" + _TAG_TAIL,
    re.S,
)


def _top_level_children(inner: bytes) -> list[tuple[str, int, int]]:
    """``(local name, start, end)`` of each direct child element in ``inner``."""
    children: list[tuple[str, int, int]] = []
    depth, start, name = 0, 0, ""
    for token in _TOKEN.finditer(inner):
        closing, local, empty = token.group(1), token.group(2), token.group(3)
        if local is None:
            continue
        if closing:
            depth -= 1
            if depth == 0:
                children.append((name, start, token.end()))
        elif empty:
            if depth == 0:
                children.append((local.decode(), token.start(), token.end()))
        else:
            if depth == 0:
                start, name = token.start(), local.decode()
            depth += 1
    if depth != 0:
        raise CustomGeometryError("a:custGeom content is not well-formed")
    return children


def _rewrite_custom_geometry(
    raw: bytes, ordinal: int, count: int, original: ET.Element, geometry: CustomGeometry
) -> bytes:
    """Splice the changed ``a:custGeom`` sections into ``raw``; every other byte is kept."""
    starts = list(_CUSTGEOM_START.finditer(raw))
    if len(starts) != count:
        raise CustomGeometryError("cannot locate a:custGeom in the slide part bytes")
    start = starts[ordinal]
    prefix = f"{start.group(1).decode()}:" if start.group(1) else ""
    if start.group(2):
        # <a:custGeom/>: reopen it as a start tag and close it after the new content.
        head = start.group(0)[:-2].rstrip() + b">"
        inner, tail, tail_end = b"", f"</{prefix}custGeom>".encode(), start.end()
    else:
        closing = re.compile(rb"</" + re.escape(prefix.encode()) + rb"custGeom\s*>")
        end = closing.search(raw, start.end())
        if end is None:
            raise CustomGeometryError("a:custGeom has no end tag")
        head, inner, tail, tail_end = (
            start.group(0),
            raw[start.end() : end.start()],
            end.group(0),
            end.end(),
        )
    wanted = _sections(geometry)
    changed = {
        section: _serialize_section(section, wanted[section], prefix).encode()
        for section in _SECTIONS
        if _parse_section(_child(original, section), section) != wanted[section]
    }
    if "rect" in changed and wanted["rect"] is None:
        changed["rect"] = b""
    children = _top_level_children(inner)
    present = {name for name, _, _ in children}
    pending = [section for section in _SECTIONS if section in changed and section not in present]
    out, cursor = [], 0
    for name, child_start, child_end in children:
        rank = _SECTIONS.index(name) if name in _SECTIONS else len(_SECTIONS)
        out.append(inner[cursor:child_start])
        while pending and _SECTIONS.index(pending[0]) < rank:
            out.append(changed[pending.pop(0)])
        out.append(changed.get(name, inner[child_start:child_end]))
        cursor = child_end
    out.extend(changed[section] for section in pending)
    out.append(inner[cursor:])
    return raw[: start.start()] + head + b"".join(out) + tail + raw[tail_end:]


def write_custom_geometry(shape: Any, geometry: Any) -> None:
    """Replace ``shape``'s ``a:custGeom`` content; unchanged sections keep their bytes.

    The slide part is rewritten into a staged package and the presentation is rebased
    on it, so the edit refuses a presentation with other pending edits.
    """
    validate_custom_geometry(geometry)
    payload = shape._payload
    if (
        shape.shape_id is None
        or payload.get("_pending_shape")
        or payload.get("_pending_group_child")
        or shape._slide._payload.get("_pending_creation")
    ):
        raise CustomGeometryError(
            "cannot edit the custom geometry of an unsaved pending shape; save it first"
        )
    current = read_custom_geometry(shape)
    if current is None:
        raise CustomGeometryError(f"shape {shape.name!r} has no a:custGeom custom geometry")
    if current == geometry:
        return
    from .shape_locks import check_shape_locks

    # Adjust values are what handles drive; every other section edits the points.
    if current.adjust_guides != geometry.adjust_guides:
        check_shape_locks(shape, "custom geometry edit", "no_adjust_handles")
    if replace(current, adjust_guides=geometry.adjust_guides) != geometry:
        check_shape_locks(shape, "custom geometry edit", "no_edit_points")
    part = str(shape._slide.partname).lstrip("/")

    def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
        raw = package.read(part)
        root = ET.fromstring(raw)
        original = _shape_custom_geometry_element(_shape_xml_element(root, payload))
        if original is None:
            raise CustomGeometryError(f"shape {shape.name!r} has no a:custGeom custom geometry")
        every = [item for item in root.iter() if _local(item.tag) == "custGeom"]
        ordinal = next(index for index, item in enumerate(every) if item is original)
        rewritten = _rewrite_custom_geometry(raw, ordinal, len(every), original, geometry)
        return {part: rewritten}, set(), None

    shape._slide._presentation._rewrite_package("editing custom geometry", plan)
