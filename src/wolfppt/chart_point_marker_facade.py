"""Chart point marker and point shape-format facade helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_format_facade import ChartFormat
from .chart_point_facade_xml import (
    _chart_point_element,
    _chart_point_marker_element,
    _data_label_insert_index,
    _marker_child_insert_index,
)
from .dml_fill import (
    no_fill_element as _no_fill_element,
    set_shape_gradient_fill as _set_shape_gradient_fill,
    set_shape_pattern_fill as _set_shape_pattern_fill,
    set_shape_pattern_fill_color as _set_shape_pattern_fill_color,
    solid_fill_element as _solid_fill_element,
)
from .facade_chart_values import (
    marker_style_value as _marker_style_value,
    normalize_marker_size as _normalize_marker_size,
    normalize_marker_style as _normalize_marker_style,
)
from .package_parts import XmlElementProxy

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


class Marker:
    def __init__(self, point: Any) -> None:
        self._point = point

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(
            _chart_point_element(
                self._point._series._chart._shape,
                self._point._series.index,
                self._point._index,
            )
        )

    @property
    def style(self) -> Any:
        element = _chart_point_marker_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
        )
        symbol = element.find(f"{{{C_NS}}}symbol")
        return _marker_style_value(None if symbol is None else symbol.attrib.get("val"))

    @style.setter
    def style(self, value: Any) -> None:
        style = _normalize_marker_style(value)
        if _marker_style_xml(
            _chart_point_marker_element(
                self._point._series._chart._shape,
                self._point._series.index,
                self._point._index,
            )
        ) == style:
            return
        element = _chart_point_marker_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
            create=True,
        )
        _set_marker_style(element, style)
        self._queue_format({"marker_style": style})

    @property
    def size(self) -> int | None:
        element = _chart_point_marker_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
        )
        size = element.find(f"{{{C_NS}}}size")
        if size is None:
            return None
        raw_value = size.attrib.get("val")
        return None if raw_value is None else int(raw_value)

    @size.setter
    def size(self, value: Any) -> None:
        size = _normalize_marker_size(value)
        if self.size == size:
            return
        element = _chart_point_marker_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
            create=True,
        )
        _set_marker_size(element, size)
        self._queue_format({"marker_size": size})

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_point_marker_element(
                self._point._series._chart._shape,
                self._point._series.index,
                self._point._index,
            ),
            self._queue_format,
        )

    def _queue_format(self, properties: dict[str, Any]) -> None:
        element = _chart_point_marker_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
            create=True,
        )
        if properties.get("fill_type") == "solid":
            _set_point_solid_fill(element)
        if properties.get("fill_type") == "background":
            _set_point_background_fill(element)
        if properties.get("fill_type") == "patterned":
            _set_point_pattern_fill(element, None)
        if properties.get("fill_type") == "gradient":
            _set_point_gradient_fill(element, properties.get("fill_gradient"))
        if "fill_rgb" in properties:
            _set_point_fill_rgb(element, str(properties["fill_rgb"]))
        if "fill_gradient" in properties:
            _set_point_gradient_fill(element, properties["fill_gradient"])
        if "fill_pattern" in properties:
            _set_point_pattern_fill(element, properties["fill_pattern"])
        if "fill_pattern_fore_rgb" in properties:
            _set_point_pattern_rgb(
                element,
                "fgClr",
                str(properties["fill_pattern_fore_rgb"]),
            )
        if "fill_pattern_back_rgb" in properties:
            _set_point_pattern_rgb(
                element,
                "bgClr",
                str(properties["fill_pattern_back_rgb"]),
            )
        if "line_rgb" in properties:
            _set_point_line_rgb(element, str(properties["line_rgb"]))
        if "line_width" in properties:
            _set_point_line_width(element, int(properties["line_width"]))
        if "line_dash" in properties:
            _set_point_line_dash(element, properties["line_dash"])
        if "line_fill_type" in properties:
            _set_point_line_fill_type(element, str(properties["line_fill_type"]))
        if "line_pattern" in properties:
            _set_point_line_pattern_fill(element, properties["line_pattern"])
        if "line_pattern_fore_rgb" in properties:
            _set_point_line_pattern_rgb(
                element,
                "fgClr",
                str(properties["line_pattern_fore_rgb"]),
            )
        if "line_pattern_back_rgb" in properties:
            _set_point_line_pattern_rgb(
                element,
                "bgClr",
                str(properties["line_pattern_back_rgb"]),
            )
        if "marker_style" in properties:
            _set_marker_style(element, properties["marker_style"])
        if "marker_size" in properties:
            _set_marker_size(element, properties["marker_size"])
        chart = self._point._series._chart
        chart._shape._slide._presentation._queue_chart_data_labels(
            chart._shape._slide._index,
            chart._shape._index,
            {
                "point_marker_formats": [
                    {
                        "series_index": self._point._series.index,
                        "point_index": self._point._index,
                        "properties": properties,
                    }
                ]
            },
        )


def _set_point_solid_fill(point: ET.Element) -> None:
    shape_properties = _shape_properties_element(point)
    for child in list(shape_properties):
        if child.tag in {
            f"{{{A_NS}}}noFill",
            f"{{{A_NS}}}solidFill",
            f"{{{A_NS}}}gradFill",
            f"{{{A_NS}}}blipFill",
            f"{{{A_NS}}}pattFill",
            f"{{{A_NS}}}grpFill",
        }:
            shape_properties.remove(child)
    shape_properties.insert(0, ET.Element(f"{{{A_NS}}}solidFill"))


def _set_point_fill_rgb(point: ET.Element, rgb: str) -> None:
    shape_properties = _shape_properties_element(point)
    solid_fill = shape_properties.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        _set_point_solid_fill(point)
        solid_fill = shape_properties.find(f"{{{A_NS}}}solidFill")
    assert solid_fill is not None
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def _set_point_pattern_fill(point: ET.Element, pattern: Any) -> None:
    _set_shape_pattern_fill(
        _shape_properties_element(point),
        None if pattern is None else str(pattern),
    )


def _set_point_pattern_rgb(point: ET.Element, color_tag: str, rgb: str) -> None:
    _set_shape_pattern_fill_color(_shape_properties_element(point), color_tag, rgb)


def _set_point_background_fill(point: ET.Element) -> None:
    _no_fill_element(_shape_properties_element(point))


def _set_point_gradient_fill(point: ET.Element, gradient: Any) -> None:
    _set_shape_gradient_fill(
        _shape_properties_element(point),
        gradient if isinstance(gradient, dict) else {},
    )


def _set_point_line_rgb(point: ET.Element, rgb: str) -> None:
    shape_properties = _shape_properties_element(point)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    solid_fill = line.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        solid_fill = ET.Element(f"{{{A_NS}}}solidFill")
        line.insert(0, solid_fill)
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def _set_point_line_width(point: ET.Element, width: int) -> None:
    shape_properties = _shape_properties_element(point)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    line.set("w", str(width))


def _set_point_line_dash(point: ET.Element, dash_style: Any) -> None:
    shape_properties = _shape_properties_element(point)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    preset_dash = line.find(f"{{{A_NS}}}prstDash")
    if dash_style is None:
        if preset_dash is not None:
            line.remove(preset_dash)
        return
    if preset_dash is None:
        preset_dash = ET.Element(f"{{{A_NS}}}prstDash")
        line.append(preset_dash)
    preset_dash.set("val", str(dash_style))


def _set_point_line_fill_type(point: ET.Element, fill_type: str) -> None:
    shape_properties = _shape_properties_element(point)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    if fill_type == "solid":
        _solid_fill_element(line)
        return
    if fill_type == "background":
        _no_fill_element(line)
        return
    if fill_type == "patterned":
        _set_shape_pattern_fill(line, None)
        return
    raise ValueError(f"unsupported chart point line fill type: {fill_type!r}")


def _set_point_line_pattern_fill(point: ET.Element, pattern: Any) -> None:
    shape_properties = _shape_properties_element(point)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    _set_shape_pattern_fill(line, None if pattern is None else str(pattern))


def _set_point_line_pattern_rgb(
    point: ET.Element,
    color_tag: str,
    rgb: str,
) -> None:
    shape_properties = _shape_properties_element(point)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    _set_shape_pattern_fill_color(line, color_tag, rgb)


def _set_marker_style(marker: ET.Element, style: str | None) -> None:
    symbol = marker.find(f"{{{C_NS}}}symbol")
    if style is None:
        if symbol is not None:
            marker.remove(symbol)
        return
    if symbol is None:
        symbol = ET.Element(f"{{{C_NS}}}symbol")
        marker.insert(_marker_child_insert_index(marker, "symbol"), symbol)
    symbol.set("val", style)


def _marker_style_xml(marker: ET.Element) -> str | None:
    symbol = marker.find(f"{{{C_NS}}}symbol")
    return None if symbol is None else symbol.attrib.get("val")


def _set_marker_size(marker: ET.Element, size: int | None) -> None:
    size_element = marker.find(f"{{{C_NS}}}size")
    if size is None:
        if size_element is not None:
            marker.remove(size_element)
        return
    if size_element is None:
        size_element = ET.Element(f"{{{C_NS}}}size")
        marker.insert(_marker_child_insert_index(marker, "size"), size_element)
    size_element.set("val", str(size))


def _shape_properties_element(point: ET.Element) -> ET.Element:
    shape_properties = point.find(f"{{{C_NS}}}spPr")
    if shape_properties is not None:
        return shape_properties
    shape_properties = ET.Element(f"{{{C_NS}}}spPr")
    local_name = point.tag.rsplit("}", 1)[-1]
    insert_index = (
        _marker_child_insert_index(point, "spPr")
        if local_name == "marker"
        else _data_label_insert_index(point, "spPr")
    )
    point.insert(insert_index, shape_properties)
    return shape_properties
