"""Chart series point and point data-label facade helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any
from xml.etree import ElementTree as ET

from .chart_format_facade import ChartFont, ChartFormat
from .chart_point_data_label_text_facade import DataLabelTextFrame
from .chart_point_data_label_xml import (
    point_data_label_position_xml as _point_data_label_position_xml,
    point_data_label_text_default_run_properties as _point_data_label_text_default_run_properties,
    set_point_data_label_position as _set_point_data_label_position,
    set_point_data_label_text_frame as _set_point_data_label_text_frame,
    set_point_data_label_text_properties as _set_point_data_label_text_properties,
    set_run_properties_font as _set_run_properties_font,
)
from .chart_point_facade_xml import (
    _chart_point_data_label_element,
    _chart_point_element,
)
from .chart_point_marker_facade import (
    Marker,
    _set_point_background_fill,
    _set_point_fill_rgb,
    _set_point_gradient_fill,
    _set_point_pattern_fill,
    _set_point_pattern_rgb,
    _set_point_line_dash,
    _set_point_line_fill_type,
    _set_point_line_pattern_fill,
    _set_point_line_pattern_rgb,
    _set_point_line_rgb,
    _set_point_line_width,
    _set_point_solid_fill,
)
from .facade_values import (
    data_label_position_value as _data_label_position_value,
    normalize_data_label_position as _normalize_data_label_position,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


class ChartPointCollection(Sequence["ChartPoint"]):
    def __init__(self, series: Any) -> None:
        self._series = series

    def __getitem__(self, index: int | slice) -> "ChartPoint | list[ChartPoint]":
        if isinstance(index, slice):
            return [
                ChartPoint(self._series, item)
                for item in range(*index.indices(len(self)))
            ]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("chart point index out of range")
        return ChartPoint(self._series, index)

    def __iter__(self) -> Iterator["ChartPoint"]:
        for index in range(len(self)):
            yield ChartPoint(self._series, index)

    def __len__(self) -> int:
        return len(self._series.values)


class ChartPoint:
    def __init__(self, series: Any, index: int) -> None:
        self._series = series
        self._index = index

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_point_element(
                self._series._chart._shape,
                self._series.index,
                self._index,
            ),
            self._queue_format,
        )

    @property
    def data_label(self) -> "DataLabel":
        return DataLabel(self)

    @property
    def marker(self) -> "Marker":
        return Marker(self)

    def _queue_format(self, properties: dict[str, Any]) -> None:
        element = _chart_point_element(
            self._series._chart._shape,
            self._series.index,
            self._index,
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
        chart = self._series._chart
        chart._shape._slide._presentation._queue_chart_data_labels(
            chart._shape._slide._index,
            chart._shape._index,
            {
                "point_formats": [
                    {
                        "series_index": self._series.index,
                        "point_index": self._index,
                        "properties": properties,
                    }
                ]
            },
        )


class DataLabel:
    def __init__(self, point: ChartPoint) -> None:
        self._point = point

    @property
    def has_text_frame(self) -> bool:
        element = _chart_point_data_label_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
        )
        return element.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich") is not None

    @has_text_frame.setter
    def has_text_frame(self, value: Any) -> None:
        enabled = bool(value)
        if enabled == self.has_text_frame:
            return
        element = _chart_point_data_label_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
            create=True,
        )
        _set_point_data_label_text_frame(element, enabled)
        self._queue({"has_text_frame": enabled})

    @property
    def text_frame(self) -> "DataLabelTextFrame":
        return DataLabelTextFrame(self)

    @property
    def position(self) -> Any:
        element = _chart_point_data_label_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
        )
        position = element.find(f"{{{C_NS}}}dLblPos")
        return _data_label_position_value(
            None if position is None else position.attrib.get("val")
        )

    @position.setter
    def position(self, value: Any) -> None:
        position = _normalize_data_label_position(value)
        if (
            _point_data_label_position_xml(
                _chart_point_data_label_element(
                    self._point._series._chart._shape,
                    self._point._series.index,
                    self._point._index,
                )
            )
            == position
        ):
            return
        element = _chart_point_data_label_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
            create=True,
        )
        _set_point_data_label_text_properties(element)
        _set_point_data_label_position(element, position)
        self._queue({"position": position})

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            self._text_default_run_properties,
            self._queue_font,
        )

    def _text_default_run_properties(self) -> ET.Element | None:
        element = _chart_point_data_label_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
        )
        return element.find(
            f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
        )

    def _queue_font(self, properties: dict[str, Any]) -> None:
        element = _chart_point_data_label_element(
            self._point._series._chart._shape,
            self._point._series.index,
            self._point._index,
            create=True,
        )
        run_properties = _point_data_label_text_default_run_properties(element)
        font_properties: dict[str, Any] = {}
        for attr, value in properties.items():
            if attr == "font_bold":
                font_properties["bold"] = value
            elif attr == "font_italic":
                font_properties["italic"] = value
            elif attr == "font_underline":
                font_properties["underline"] = value
            elif attr == "font_size":
                font_properties["size"] = value
            elif attr == "font_fill_type":
                font_properties["fill_type"] = value
            elif attr == "font_pattern":
                font_properties["pattern"] = value
            elif attr == "font_pattern_fore_rgb":
                font_properties["pattern_fore_rgb"] = value
            elif attr == "font_pattern_back_rgb":
                font_properties["pattern_back_rgb"] = value
            elif attr == "font_gradient":
                font_properties["gradient"] = value
            elif attr == "font_rgb":
                font_properties["rgb"] = value
            elif attr == "font_name":
                font_properties["name"] = value
            elif attr == "font_language_id":
                font_properties["language_id"] = value
            else:
                raise AttributeError(
                    f"unsupported chart data-label font property: {attr!r}"
                )
        _set_run_properties_font(run_properties, font_properties)
        self._queue(properties)

    def _queue(self, properties: dict[str, Any]) -> None:
        chart = self._point._series._chart
        chart._shape._slide._presentation._queue_chart_data_labels(
            chart._shape._slide._index,
            chart._shape._index,
            {
                "point_labels": [
                    {
                        "series_index": self._point._series.index,
                        "point_index": self._point._index,
                        "properties": properties,
                    }
                ]
            },
        )
