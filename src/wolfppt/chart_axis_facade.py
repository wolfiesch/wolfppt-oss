"""Chart axis, gridline, tick label, and data label facades."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_facade_helpers import (
    chart_axis_major_gridlines_element as _chart_axis_major_gridlines_element,
    chart_axis_payload as _chart_axis_payload,
    chart_axis_proxy_element as _chart_axis_proxy_element,
    chart_axis_text_default_run_properties as _chart_axis_text_default_run_properties,
    chart_data_labels_payload as _chart_data_labels_payload,
    chart_data_labels_text_default_run_properties as _chart_data_labels_text_default_run_properties,
    normalize_tick_label_offset as _normalize_tick_label_offset,
    set_chart_element_fill_rgb as _set_chart_element_fill_rgb,
    set_chart_element_line_dash as _set_chart_element_line_dash,
    set_chart_element_line_fill_type as _set_chart_element_line_fill_type,
    set_chart_element_line_rgb as _set_chart_element_line_rgb,
    set_chart_element_line_width as _set_chart_element_line_width,
    set_chart_element_solid_fill as _set_chart_element_solid_fill,
)
from .chart_axis_xml import (
    axis_title_element as _axis_title_element,
    set_chart_axis_fill_rgb as _set_chart_axis_fill_rgb,
    set_chart_axis_fill_type as _set_chart_axis_fill_type,
    set_chart_axis_line_dash as _set_chart_axis_line_dash,
    set_chart_axis_line_fill_type as _set_chart_axis_line_fill_type,
    set_chart_axis_line_rgb as _set_chart_axis_line_rgb,
    set_chart_axis_line_width as _set_chart_axis_line_width,
)
from .chart_format_facade import ChartFont, ChartFormat
from .chart_point_facade_xml import (
    chart_series_data_labels_text_default_run_properties as _chart_series_data_labels_text_default_run_properties,
)
from .chart_title_text_facade import ChartTitleTextFrame
from .facade_values import (
    axis_crosses_value as _axis_crosses_value,
    axis_tick_mark_value as _axis_tick_mark_value,
    category_axis_type_value as _category_axis_type_value,
    data_label_position_value as _data_label_position_value,
    normalize_axis_crosses as _normalize_axis_crosses,
    normalize_axis_tick_mark as _normalize_axis_tick_mark,
    normalize_data_label_position as _normalize_data_label_position,
    normalize_optional_float as _normalize_optional_float,
    normalize_tick_label_position as _normalize_tick_label_position,
    optional_float as _optional_float,
    tick_label_position_value as _tick_label_position_value,
)
from .package_parts import XmlElementProxy
from .chart_xml_utils import C_NS


class ChartAxis:
    def __init__(self, chart: Chart, axis: str) -> None:
        self._chart = chart
        self._axis = axis

    @property
    def has_title(self) -> bool:
        return bool(_chart_axis_payload(self._chart._shape, self._axis).get("has_title"))

    @property
    def category_type(self) -> Any:
        if self._axis != "cat":
            raise AttributeError("'ValueAxis' object has no attribute 'category_type'")
        return _category_axis_type_value()

    @property
    def format(self) -> "ChartFormat":
        return ChartFormat(
            lambda: _chart_axis_proxy_element(self._chart._shape, self._axis),
            self._queue_format,
        )

    @property
    def major_gridlines(self) -> "MajorGridlines":
        return MajorGridlines(self)

    @property
    def tick_labels(self) -> "TickLabels":
        return TickLabels(self)

    @has_title.setter
    def has_title(self, value: bool) -> None:
        payload = _chart_axis_payload(self._chart._shape, self._axis)
        has_title = bool(value)
        if has_title == bool(payload.get("has_title")):
            return
        payload["has_title"] = has_title
        if not has_title:
            payload["title_text"] = ""
        self._chart._shape._slide._presentation._queue_chart_axis_title(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            self._axis,
            {
                "has_title": has_title,
                "text": str(payload.get("title_text") or ""),
            },
        )

    @property
    def axis_title(self) -> "ChartAxisTitle":
        return ChartAxisTitle(self)

    @property
    def visible(self) -> bool:
        return bool(_chart_axis_payload(self._chart._shape, self._axis).get("visible"))

    @visible.setter
    def visible(self, value: Any) -> None:
        self._set_property("visible", bool(value))

    @property
    def has_major_gridlines(self) -> bool:
        return bool(
            _chart_axis_payload(self._chart._shape, self._axis).get(
                "has_major_gridlines"
            )
        )

    @has_major_gridlines.setter
    def has_major_gridlines(self, value: Any) -> None:
        self._set_property("has_major_gridlines", bool(value))

    @property
    def has_minor_gridlines(self) -> bool:
        return bool(
            _chart_axis_payload(self._chart._shape, self._axis).get(
                "has_minor_gridlines"
            )
        )

    @has_minor_gridlines.setter
    def has_minor_gridlines(self, value: Any) -> None:
        self._set_property("has_minor_gridlines", bool(value))

    @property
    def major_tick_mark(self) -> Any:
        return _axis_tick_mark_value(
            _chart_axis_payload(self._chart._shape, self._axis).get(
                "major_tick_mark",
                "out",
            )
        )

    @major_tick_mark.setter
    def major_tick_mark(self, value: Any) -> None:
        self._set_property("major_tick_mark", _normalize_axis_tick_mark(value))

    @property
    def minor_tick_mark(self) -> Any:
        return _axis_tick_mark_value(
            _chart_axis_payload(self._chart._shape, self._axis).get(
                "minor_tick_mark",
                "none",
            )
        )

    @minor_tick_mark.setter
    def minor_tick_mark(self, value: Any) -> None:
        self._set_property("minor_tick_mark", _normalize_axis_tick_mark(value))

    @property
    def tick_label_position(self) -> Any:
        return _tick_label_position_value(
            _chart_axis_payload(self._chart._shape, self._axis).get(
                "tick_label_position",
                "nextTo",
            )
        )

    @tick_label_position.setter
    def tick_label_position(self, value: Any) -> None:
        self._set_property(
            "tick_label_position",
            _normalize_tick_label_position(value),
        )

    @property
    def reverse_order(self) -> bool:
        return bool(
            _chart_axis_payload(self._chart._shape, self._axis).get("reverse_order")
        )

    @reverse_order.setter
    def reverse_order(self, value: Any) -> None:
        self._set_property("reverse_order", bool(value))

    @property
    def minimum_scale(self) -> float | None:
        return _optional_float(
            _chart_axis_payload(self._chart._shape, self._axis).get("minimum_scale")
        )

    @minimum_scale.setter
    def minimum_scale(self, value: Any) -> None:
        self._set_property("minimum_scale", _normalize_optional_float(value))

    @property
    def maximum_scale(self) -> float | None:
        return _optional_float(
            _chart_axis_payload(self._chart._shape, self._axis).get("maximum_scale")
        )

    @maximum_scale.setter
    def maximum_scale(self, value: Any) -> None:
        self._set_property("maximum_scale", _normalize_optional_float(value))

    @property
    def major_unit(self) -> float | None:
        if self._axis != "val":
            raise AttributeError("'CategoryAxis' object has no attribute 'major_unit'")
        return _optional_float(
            _chart_axis_payload(self._chart._shape, self._axis).get("major_unit")
        )

    @major_unit.setter
    def major_unit(self, value: Any) -> None:
        if self._axis != "val":
            raise AttributeError("'CategoryAxis' object has no attribute 'major_unit'")
        self._set_property("major_unit", _normalize_optional_float(value))

    @property
    def minor_unit(self) -> float | None:
        if self._axis != "val":
            raise AttributeError("'CategoryAxis' object has no attribute 'minor_unit'")
        return _optional_float(
            _chart_axis_payload(self._chart._shape, self._axis).get("minor_unit")
        )

    @minor_unit.setter
    def minor_unit(self, value: Any) -> None:
        if self._axis != "val":
            raise AttributeError("'CategoryAxis' object has no attribute 'minor_unit'")
        self._set_property("minor_unit", _normalize_optional_float(value))

    @property
    def crosses(self) -> Any:
        if self._axis != "val":
            raise AttributeError("'CategoryAxis' object has no attribute 'crosses'")
        cross_axis = _chart_axis_payload(self._chart._shape, "cat")
        if cross_axis.get("crosses_at") is not None:
            return _axis_crosses_value(None)
        return _axis_crosses_value(cross_axis.get("crosses"))

    @crosses.setter
    def crosses(self, value: Any) -> None:
        if self._axis != "val":
            raise AttributeError("'CategoryAxis' object has no attribute 'crosses'")
        crosses = _normalize_axis_crosses(value)
        if crosses is None:
            cross_axis = _chart_axis_payload(self._chart._shape, "cat")
            if cross_axis.get("crosses_at") is not None:
                return
            self._set_cross_axis_property("crosses_at", 0.0)
            return
        self._set_cross_axis_property("crosses", crosses)

    @property
    def crosses_at(self) -> float | None:
        if self._axis != "val":
            raise AttributeError("'CategoryAxis' object has no attribute 'crosses_at'")
        return _optional_float(
            _chart_axis_payload(self._chart._shape, "cat").get("crosses_at")
        )

    @crosses_at.setter
    def crosses_at(self, value: Any) -> None:
        if self._axis != "val":
            raise AttributeError("'CategoryAxis' object has no attribute 'crosses_at'")
        self._set_cross_axis_property("crosses_at", _normalize_optional_float(value))

    def _set_property(self, attr: str, value: Any, *, force: bool = False) -> None:
        payload = _chart_axis_payload(self._chart._shape, self._axis)
        if not force and payload.get(attr) == value:
            return
        payload[attr] = value
        self._chart._shape._slide._presentation._queue_chart_axis_property(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            self._axis,
            attr,
            value,
        )

    def _queue_format(self, properties: dict[str, Any]) -> None:
        axis_element = _chart_axis_proxy_element(self._chart._shape, self._axis)
        queued_properties: dict[str, Any] = {}
        if properties.get("fill_type") == "solid":
            _set_chart_axis_fill_type(axis_element, "solid")
            queued_properties["axis_fill_type"] = "solid"
        if "fill_rgb" in properties:
            value = str(properties["fill_rgb"])
            _set_chart_axis_fill_rgb(axis_element, value)
            queued_properties["axis_fill_rgb"] = value
        if "line_fill_type" in properties:
            value = str(properties["line_fill_type"])
            _set_chart_axis_line_fill_type(axis_element, value)
            queued_properties["axis_line_fill_type"] = value
        if "line_rgb" in properties:
            value = str(properties["line_rgb"])
            _set_chart_axis_line_rgb(axis_element, value)
            queued_properties["axis_line_rgb"] = value
        if "line_width" in properties:
            value = int(properties["line_width"])
            _set_chart_axis_line_width(axis_element, value)
            queued_properties["axis_line_width"] = value
        if "line_dash" in properties:
            value = properties["line_dash"]
            _set_chart_axis_line_dash(axis_element, value)
            queued_properties["axis_line_dash"] = value
        for attr, value in queued_properties.items():
            self._chart._shape._slide._presentation._queue_chart_axis_property(
                self._chart._shape._slide._index,
                self._chart._shape._index,
                self._axis,
                attr,
                value,
            )

    def _set_cross_axis_property(self, attr: str, value: Any) -> None:
        payload = _chart_axis_payload(self._chart._shape, "cat")
        current_crosses = payload.get("crosses")
        current_crosses_at = payload.get("crosses_at")
        if (
            attr == "crosses"
            and current_crosses == value
            and current_crosses_at is None
        ):
            return
        if (
            attr == "crosses_at"
            and current_crosses is None
            and current_crosses_at == value
        ):
            return
        if attr == "crosses":
            payload["crosses"] = value
            payload["crosses_at"] = None
        elif attr == "crosses_at":
            payload["crosses"] = None
            payload["crosses_at"] = value
        self._chart._shape._slide._presentation._queue_chart_axis_property(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            "cat",
            attr,
            value,
        )


class ChartAxisTitle:
    def __init__(self, axis: ChartAxis) -> None:
        self._axis = axis

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(self._title_element(create=False))

    @property
    def has_text_frame(self) -> bool:
        return self._axis.has_title

    @property
    def text_frame(self) -> "ChartTitleTextFrame":
        return ChartTitleTextFrame(self._title_element, self._queue_text)

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(self._element, self._queue_format)

    def _element(self) -> Any:
        if not self._axis.has_title:
            return ET.Element(f"{{{C_NS}}}title")
        axis_element = _chart_axis_proxy_element(
            self._axis._chart._shape,
            self._axis._axis,
        )
        title = axis_element.find(f"{{{C_NS}}}title")
        return title if title is not None else ET.Element(f"{{{C_NS}}}title")

    def _queue_format(self, properties: dict[str, Any]) -> None:
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        axis_element = _chart_axis_proxy_element(
            self._axis._chart._shape,
            self._axis._axis,
        )
        title = _axis_title_element(axis_element)
        if properties.get("fill_type") == "solid":
            _set_chart_element_solid_fill(title)
        if "fill_rgb" in properties:
            _set_chart_element_fill_rgb(title, str(properties["fill_rgb"]))
        if "line_fill_type" in properties:
            _set_chart_element_line_fill_type(title, str(properties["line_fill_type"]))
        if "line_rgb" in properties:
            _set_chart_element_line_rgb(title, str(properties["line_rgb"]))
        if "line_width" in properties:
            _set_chart_element_line_width(title, int(properties["line_width"]))
        if "line_dash" in properties:
            _set_chart_element_line_dash(title, properties["line_dash"])
        payload["has_title"] = True
        self._axis._chart._shape._slide._presentation._queue_chart_axis_title(
            self._axis._chart._shape._slide._index,
            self._axis._chart._shape._index,
            self._axis._axis,
            {
                "has_title": True,
                "text": str(payload.get("title_text") or ""),
                "format": properties,
            },
        )

    def _title_element(self, create: bool) -> Any:
        if not create and not self._axis.has_title:
            return ET.Element(f"{{{C_NS}}}title")
        axis_element = _chart_axis_proxy_element(
            self._axis._chart._shape,
            self._axis._axis,
        )
        if not create:
            title = axis_element.find(f"{{{C_NS}}}title")
            return title if title is not None else ET.Element(f"{{{C_NS}}}title")
        return _axis_title_element(axis_element)

    def _queue_text(self, properties: dict[str, Any]) -> None:
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        payload["has_title"] = True
        if "text" in properties:
            payload["title_text"] = str(properties["text"])
        elif "paragraphs" in properties:
            payload["title_text"] = "\n".join(
                str(paragraph) for paragraph in properties["paragraphs"]
            )
        elif "paragraph_runs" in properties:
            payload["title_text"] = "\n".join(
                "".join(str(run) for run in runs)
                for runs in properties["paragraph_runs"]
            )
        self._axis._chart._shape._slide._presentation._queue_chart_axis_title(
            self._axis._chart._shape._slide._index,
            self._axis._chart._shape._index,
            self._axis._axis,
            {"has_title": True, **properties},
        )


class DataLabels:
    def __init__(self, plot: ChartPlot) -> None:
        self._plot = plot

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            lambda: _chart_data_labels_text_default_run_properties(
                self._plot._chart._shape,
            ),
            self._set_properties,
            lambda: _chart_data_labels_payload(self._plot._chart._shape).get(
                "font_size"
            ),
            lambda: _chart_data_labels_payload(self._plot._chart._shape).get(
                "font_fill_type"
            ),
            lambda: _chart_data_labels_payload(self._plot._chart._shape).get(
                "font_pattern"
            ),
            lambda: _chart_data_labels_payload(self._plot._chart._shape).get(
                "font_gradient"
            ),
        )

    @property
    def show_value(self) -> bool:
        return bool(_chart_data_labels_payload(self._plot._chart._shape)["show_value"])

    @show_value.setter
    def show_value(self, value: Any) -> None:
        self._set_property("show_value", bool(value))

    @property
    def show_category_name(self) -> bool:
        return bool(
            _chart_data_labels_payload(self._plot._chart._shape)["show_category_name"]
        )

    @show_category_name.setter
    def show_category_name(self, value: Any) -> None:
        self._set_property("show_category_name", bool(value))

    @property
    def show_series_name(self) -> bool:
        return bool(
            _chart_data_labels_payload(self._plot._chart._shape)["show_series_name"]
        )

    @show_series_name.setter
    def show_series_name(self, value: Any) -> None:
        self._set_property("show_series_name", bool(value))

    @property
    def show_percentage(self) -> bool:
        return bool(
            _chart_data_labels_payload(self._plot._chart._shape)["show_percentage"]
        )

    @show_percentage.setter
    def show_percentage(self, value: Any) -> None:
        self._set_property("show_percentage", bool(value))

    @property
    def show_legend_key(self) -> bool:
        return bool(
            _chart_data_labels_payload(self._plot._chart._shape)["show_legend_key"]
        )

    @show_legend_key.setter
    def show_legend_key(self, value: Any) -> None:
        self._set_property("show_legend_key", bool(value))

    @property
    def position(self) -> Any:
        return _data_label_position_value(
            _chart_data_labels_payload(self._plot._chart._shape).get("position")
        )

    @position.setter
    def position(self, value: Any) -> None:
        self._set_property("position", _normalize_data_label_position(value))

    @property
    def number_format(self) -> str:
        return str(
            _chart_data_labels_payload(self._plot._chart._shape).get(
                "number_format",
                "General",
            )
        )

    @number_format.setter
    def number_format(self, value: Any) -> None:
        number_format = str(value)
        payload = _chart_data_labels_payload(self._plot._chart._shape)
        if (
            payload.get("has_data_labels")
            and str(payload.get("number_format", "General")) == number_format
            and payload.get("number_format_is_linked") is False
        ):
            return
        payload["number_format"] = number_format
        payload["number_format_is_linked"] = False
        self._queue({"number_format": number_format})

    @property
    def number_format_is_linked(self) -> bool:
        return bool(
            _chart_data_labels_payload(self._plot._chart._shape).get(
                "number_format_is_linked",
                True,
            )
        )

    @number_format_is_linked.setter
    def number_format_is_linked(self, value: Any) -> None:
        self._set_property("number_format_is_linked", bool(value))

    def _set_property(self, attr: str, value: Any) -> None:
        payload = _chart_data_labels_payload(self._plot._chart._shape)
        if payload.get("has_data_labels") and payload.get(attr) == value:
            return
        payload[attr] = value
        self._queue({attr: value})

    def _set_properties(self, properties: dict[str, Any]) -> None:
        for attr, value in properties.items():
            self._set_property(attr, value)

    def _queue(self, data_labels: dict[str, Any]) -> None:
        data_labels.setdefault("has_data_labels", True)
        self._plot._chart._shape._slide._presentation._queue_chart_data_labels(
            self._plot._chart._shape._slide._index,
            self._plot._chart._shape._index,
            data_labels,
        )


class ChartSeriesDataLabels(DataLabels):
    def __init__(self, series: Any) -> None:
        self._series = series

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            lambda: _chart_series_data_labels_text_default_run_properties(
                self._series._chart._shape,
                self._series.index,
            ),
            self._set_properties,
            lambda: self._payload().get("font_size"),
            lambda: self._payload().get("font_fill_type"),
            lambda: self._payload().get("font_pattern"),
            lambda: self._payload().get("font_gradient"),
        )

    @property
    def show_value(self) -> bool:
        payload = self._payload()
        if not payload.get("has_data_labels"):
            return False
        return bool(payload["show_value"])

    @show_value.setter
    def show_value(self, value: Any) -> None:
        self._set_property("show_value", bool(value))

    @property
    def show_category_name(self) -> bool:
        return bool(self._payload().get("show_category_name"))

    @show_category_name.setter
    def show_category_name(self, value: Any) -> None:
        self._set_property("show_category_name", bool(value))

    @property
    def show_series_name(self) -> bool:
        return bool(self._payload().get("show_series_name"))

    @show_series_name.setter
    def show_series_name(self, value: Any) -> None:
        self._set_property("show_series_name", bool(value))

    @property
    def show_percentage(self) -> bool:
        return bool(self._payload().get("show_percentage"))

    @show_percentage.setter
    def show_percentage(self, value: Any) -> None:
        self._set_property("show_percentage", bool(value))

    @property
    def show_legend_key(self) -> bool:
        return bool(self._payload().get("show_legend_key"))

    @show_legend_key.setter
    def show_legend_key(self, value: Any) -> None:
        self._set_property("show_legend_key", bool(value))

    @property
    def position(self) -> Any:
        return _data_label_position_value(self._payload().get("position"))

    @position.setter
    def position(self, value: Any) -> None:
        self._set_property("position", _normalize_data_label_position(value))

    @property
    def number_format(self) -> str:
        return str(self._payload().get("number_format", "General"))

    @number_format.setter
    def number_format(self, value: Any) -> None:
        number_format = str(value)
        payload = self._payload()
        if (
            payload.get("has_data_labels")
            and str(payload.get("number_format", "General")) == number_format
            and payload.get("number_format_is_linked") is False
        ):
            return
        payload["number_format"] = number_format
        payload["number_format_is_linked"] = False
        self._queue({"number_format": number_format})

    @property
    def number_format_is_linked(self) -> bool:
        return bool(self._payload().get("number_format_is_linked", True))

    @number_format_is_linked.setter
    def number_format_is_linked(self, value: Any) -> None:
        self._set_property("number_format_is_linked", bool(value))

    def _payload(self) -> dict[str, Any]:
        payload = self._series._payload.setdefault("data_labels", {})
        payload.setdefault("has_data_labels", False)
        payload.setdefault("show_value", False)
        payload.setdefault("show_category_name", False)
        payload.setdefault("show_series_name", False)
        payload.setdefault("show_percentage", False)
        payload.setdefault("show_legend_key", False)
        payload.setdefault("position", None)
        payload.setdefault("number_format", "General")
        payload.setdefault("number_format_is_linked", True)
        return payload

    def _set_property(self, attr: str, value: Any) -> None:
        payload = self._payload()
        if payload.get("has_data_labels") and payload.get(attr) == value:
            return
        payload["has_data_labels"] = True
        payload[attr] = value
        self._queue({attr: value})

    def _set_properties(self, properties: dict[str, Any]) -> None:
        for attr, value in properties.items():
            self._set_property(attr, value)

    def _queue(self, data_labels: dict[str, Any]) -> None:
        data_labels.setdefault("has_data_labels", True)
        self._series._chart._shape._slide._presentation._queue_chart_data_labels(
            self._series._chart._shape._slide._index,
            self._series._chart._shape._index,
            {
                "series_data_labels": [
                    {
                        "series_index": self._series.index,
                        "properties": data_labels,
                    }
                ]
            },
        )


class MajorGridlines:
    def __init__(self, axis: ChartAxis) -> None:
        self._axis = axis

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(
            _chart_axis_proxy_element(self._axis._chart._shape, self._axis._axis)
        )

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_axis_major_gridlines_element(
                self._axis._chart._shape,
                self._axis._axis,
            ),
            self._queue_format,
        )

    def _queue_format(self, properties: dict[str, Any]) -> None:
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        payload["has_major_gridlines"] = True
        gridlines = _chart_axis_major_gridlines_element(
            self._axis._chart._shape,
            self._axis._axis,
            create=True,
        )
        queued_properties: dict[str, Any] = {"has_major_gridlines": True}
        if "line_fill_type" in properties:
            value = str(properties["line_fill_type"])
            _set_chart_element_line_fill_type(gridlines, value)
            queued_properties["major_gridlines_line_fill_type"] = value
        if "line_rgb" in properties:
            value = str(properties["line_rgb"])
            _set_chart_element_line_rgb(gridlines, value)
            queued_properties["major_gridlines_line_rgb"] = value
        if "line_width" in properties:
            value = int(properties["line_width"])
            _set_chart_element_line_width(gridlines, value)
            queued_properties["major_gridlines_line_width"] = value
        if "line_dash" in properties:
            value = properties["line_dash"]
            _set_chart_element_line_dash(gridlines, value)
            queued_properties["major_gridlines_line_dash"] = value
        for attr, value in queued_properties.items():
            self._axis._chart._shape._slide._presentation._queue_chart_axis_property(
                self._axis._chart._shape._slide._index,
                self._axis._chart._shape._index,
                self._axis._axis,
                attr,
                value,
            )


class TickLabels:
    def __init__(self, axis: ChartAxis) -> None:
        self._axis = axis

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            lambda: _chart_axis_text_default_run_properties(
                self._axis._chart._shape,
                self._axis._axis,
            ),
            self._queue_font,
            lambda: _chart_axis_payload(
                self._axis._chart._shape,
                self._axis._axis,
            ).get("tick_label_font_size"),
            lambda: _chart_axis_payload(
                self._axis._chart._shape,
                self._axis._axis,
            ).get("tick_label_font_fill_type"),
            lambda: _chart_axis_payload(
                self._axis._chart._shape,
                self._axis._axis,
            ).get("tick_label_font_pattern"),
            lambda: _chart_axis_payload(
                self._axis._chart._shape,
                self._axis._axis,
            ).get("tick_label_font_gradient"),
        )

    @property
    def number_format(self) -> str:
        return str(
            _chart_axis_payload(self._axis._chart._shape, self._axis._axis).get(
                "number_format",
                "General",
            )
        )

    @number_format.setter
    def number_format(self, value: Any) -> None:
        number_format = str(value)
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        if (
            str(payload.get("number_format", "General")) == number_format
            and payload.get("number_format_is_linked") is False
        ):
            return
        payload["number_format"] = number_format
        payload["number_format_is_linked"] = False
        self._axis._set_property("number_format", number_format, force=True)

    @property
    def number_format_is_linked(self) -> bool:
        return bool(
            _chart_axis_payload(self._axis._chart._shape, self._axis._axis).get(
                "number_format_is_linked",
            )
        )

    @number_format_is_linked.setter
    def number_format_is_linked(self, value: Any) -> None:
        linked = bool(value)
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        if linked == bool(payload.get("number_format_is_linked")):
            return
        payload.setdefault("number_format", "General")
        self._axis._set_property("number_format_is_linked", linked)

    @property
    def offset(self) -> int:
        if self._axis._axis != "cat":
            raise AttributeError("'CT_ValAx' object has no attribute 'lblOffset'")
        return int(
            _chart_axis_payload(self._axis._chart._shape, self._axis._axis).get(
                "tick_label_offset",
                100,
            )
        )

    @offset.setter
    def offset(self, value: Any) -> None:
        if self._axis._axis != "cat":
            raise ValueError("only a category axis has an offset")
        offset = _normalize_tick_label_offset(value)
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        if int(payload.get("tick_label_offset", 100)) == offset:
            return
        self._axis._set_property("tick_label_offset", offset)

    def _queue_font(self, properties: dict[str, Any]) -> None:
        payload = _chart_axis_payload(self._axis._chart._shape, self._axis._axis)
        mapping = {
            "font_bold": "tick_label_font_bold",
            "font_italic": "tick_label_font_italic",
            "font_underline": "tick_label_font_underline",
            "font_size": "tick_label_font_size",
            "font_fill_type": "tick_label_font_fill_type",
            "font_pattern": "tick_label_font_pattern",
            "font_pattern_fore_rgb": "tick_label_font_pattern_fore_rgb",
            "font_pattern_back_rgb": "tick_label_font_pattern_back_rgb",
            "font_gradient": "tick_label_font_gradient",
            "font_rgb": "tick_label_font_rgb",
            "font_name": "tick_label_font_name",
            "font_language_id": "tick_label_font_language_id",
        }
        for attr, value in properties.items():
            try:
                payload_attr = mapping[attr]
            except KeyError as exc:
                raise ValueError(
                    f"unsupported chart tick-label font property: {properties!r}"
                ) from exc
            self._axis._set_property(payload_attr, value)
