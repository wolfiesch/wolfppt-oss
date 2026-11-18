"""Chart point marker and point shape-format facade helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_element_format_xml import (
    set_chart_element_format_property as _set_chart_element_format_property,
)
from .chart_format_facade import ChartFormat
from .chart_point_facade_xml import (
    _chart_point_element,
    _chart_point_marker_element,
    _marker_child_insert_index,
)
from .facade_chart_values import (
    marker_style_value as _marker_style_value,
)
from .facade_chart_values import (
    normalize_marker_size as _normalize_marker_size,
)
from .facade_chart_values import (
    normalize_marker_style as _normalize_marker_style,
)
from .package_parts import XmlElementProxy

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
        if (
            _marker_style_xml(
                _chart_point_marker_element(
                    self._point._series._chart._shape,
                    self._point._series.index,
                    self._point._index,
                )
            )
            == style
        ):
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
        for attr, value in properties.items():
            if attr == "marker_style":
                _set_marker_style(element, value)
            elif attr == "marker_size":
                _set_marker_size(element, value)
            else:
                _set_chart_element_format_property(element, attr, value, properties)
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
