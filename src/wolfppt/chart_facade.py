"""Chart facade classes and XML readers for python-pptx-compatible access."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .chart_edits import (
    _normalize_chart_add_data,
)
from .chart_axis_facade import (
    ChartAxis,
    ChartAxisTitle,
    ChartSeriesDataLabels,
    DataLabels,
    MajorGridlines,
    TickLabels,
)
from .chart_title_text_facade import (
    ChartTitleTextFrame,
    ChartTitleTextFrame as ChartAxisTitleTextFrame,
)
from .chart_facade_helpers import (
    C_NS,
    chart_axis_major_gridlines_element as _chart_axis_major_gridlines_element,
    chart_axis_payload as _chart_axis_payload,
    chart_axis_proxy_element as _chart_axis_proxy_element,
    chart_axis_text_default_run_properties as _chart_axis_text_default_run_properties,
    chart_data_labels_payload as _chart_data_labels_payload,
    chart_data_labels_text_default_run_properties as _chart_data_labels_text_default_run_properties,
    chart_legend_text_default_run_properties as _chart_legend_text_default_run_properties,
    chart_payload as _chart_payload,
    chart_text_default_run_properties as _chart_text_default_run_properties,
    chart_title_proxy_element as _chart_title_proxy_element,
    normalize_chart_plot_int as _normalize_chart_plot_int,
    normalize_tick_label_offset as _normalize_tick_label_offset,
    set_chart_element_fill_rgb as _set_chart_element_fill_rgb,
    set_chart_element_line_dash as _set_chart_element_line_dash,
    set_chart_element_line_fill_type as _set_chart_element_line_fill_type,
    set_chart_element_line_rgb as _set_chart_element_line_rgb,
    set_chart_element_line_width as _set_chart_element_line_width,
    set_chart_element_solid_fill as _set_chart_element_solid_fill,
    shape_chart_part as _shape_chart_part,
    shape_chart_root as _shape_chart_root,
)
from .chart_xml import (
    replace_chart_root_data as _replace_chart_root_data,
    chart_type_value as _chart_type_value,
    default_chart_data_labels_payload as _default_chart_data_labels_payload,
    _set_chart_element_pattern_fill,
    _set_chart_element_pattern_rgb,
    _set_chart_element_gradient_fill,
    _set_chart_element_background_fill,
    _set_chart_element_line_pattern_fill,
    _set_chart_element_line_pattern_rgb,
)
from .chart_format_facade import (
    ChartColorFormat,
    ChartFillFormat,
    ChartFont,
    ChartFontColorFormat,
    ChartFontFillFormat,
    ChartFormat,
    ChartLineFillFormat,
    ChartLineFormat,
    _chart_format_fill_type,
    _chart_format_line_element,
    _chart_format_line_fill_type,
    _chart_format_rgb,
    _chart_format_shape_properties,
    _run_properties_fill_type,
    _run_properties_rgb,
)
from .chart_point_facade import (
    ChartPoint,
    ChartPointCollection,
    DataLabel,
    Marker,
)
from .chart_point_facade_xml import (
    chart_series_element as _chart_series_element,
)
from .facade_values import (
    axis_crosses_value as _axis_crosses_value,
    axis_tick_mark_value as _axis_tick_mark_value,
    category_axis_type_value as _category_axis_type_value,
    data_label_position_value as _data_label_position_value,
    legend_position_value as _legend_position_value,
    normalize_axis_crosses as _normalize_axis_crosses,
    normalize_axis_tick_mark as _normalize_axis_tick_mark,
    normalize_data_label_position as _normalize_data_label_position,
    normalize_legend_position as _normalize_legend_position,
    normalize_optional_float as _normalize_optional_float,
    normalize_tick_label_position as _normalize_tick_label_position,
    optional_float as _optional_float,
    tick_label_position_value as _tick_label_position_value,
)
from .package_parts import (
    PackagePart,
    XmlElementProxy,
    package_xml_element as _package_xml_element,
)

class Chart:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @property
    def part(self) -> PackagePart:
        return PackagePart(
            self._shape._slide._presentation,
            str(_chart_payload(self._shape)["part"]),
            name=None,
        )

    @property
    def element(self) -> XmlElementProxy:
        return _package_xml_element(
            self._shape._slide._presentation.path,
            str(_chart_payload(self._shape)["part"]),
        )

    @property
    def chart_type(self) -> Any:
        return _chart_type_value(_chart_payload(self._shape)["chart_type"])

    @property
    def chart_style(self) -> int | None:
        style = _chart_payload(self._shape).get("chart_style")
        return None if style is None else int(style)

    @chart_style.setter
    def chart_style(self, value: Any) -> None:
        style = None if value is None else int(value)
        payload = _chart_payload(self._shape)
        if payload.get("chart_style") == style:
            return
        payload["chart_style"] = style
        self._shape._slide._presentation._queue_chart_style(
            self._shape._slide._index,
            self._shape._index,
            style,
        )

    @property
    def series(self) -> "ChartSeriesCollection":
        return ChartSeriesCollection(self, _chart_payload(self._shape)["series"])

    @property
    def plots(self) -> "ChartPlotCollection":
        return ChartPlotCollection(self)

    @property
    def categories(self) -> list[str]:
        series = _chart_payload(self._shape)["series"]
        if not series:
            return []
        return list(series[0]["categories"])

    @property
    def has_title(self) -> bool:
        return bool(_chart_payload(self._shape).get("has_title"))

    @has_title.setter
    def has_title(self, value: bool) -> None:
        payload = _chart_payload(self._shape)
        has_title = bool(value)
        if has_title == bool(payload.get("has_title")):
            return
        payload["has_title"] = has_title
        if not has_title:
            payload["title_text"] = ""
        self._shape._slide._presentation._queue_chart_title(
            self._shape._slide._index,
            self._shape._index,
            {
                "has_title": has_title,
                "text": str(payload.get("title_text") or ""),
                "_chart_part": str(payload.get("part") or ""),
            },
        )

    @property
    def chart_title(self) -> "ChartTitle":
        return ChartTitle(self)

    @property
    def font(self) -> "ChartFont":
        return ChartFont(
            lambda: _chart_text_default_run_properties(self._shape),
            self._set_font_properties,
            lambda: _chart_payload(self._shape).get("chart_font_size"),
            lambda: _chart_payload(self._shape).get("chart_font_fill_type"),
            lambda: _chart_payload(self._shape).get("chart_font_pattern"),
            lambda: _chart_payload(self._shape).get("chart_font_gradient"),
        )

    @property
    def has_legend(self) -> bool:
        return bool(_chart_payload(self._shape).get("has_legend"))

    @has_legend.setter
    def has_legend(self, value: bool) -> None:
        payload = _chart_payload(self._shape)
        has_legend = bool(value)
        if has_legend == bool(payload.get("has_legend")):
            return
        payload["has_legend"] = has_legend
        if has_legend:
            payload.setdefault("legend_position", "r")
            payload.setdefault("legend_include_in_layout", True)
            edit = {"has_legend": True}
        else:
            edit = {"has_legend": False}
        edit["_chart_part"] = str(payload.get("part") or "")
        self._shape._slide._presentation._queue_chart_legend(
            self._shape._slide._index,
            self._shape._index,
            edit,
        )

    @property
    def legend(self) -> "Legend | None":
        if not self.has_legend:
            return None
        return Legend(self)

    @property
    def category_axis(self) -> "ChartAxis":
        return ChartAxis(self, "cat")

    @property
    def value_axis(self) -> "ChartAxis":
        return ChartAxis(self, "val")

    def replace_data(self, chart_data: Any) -> None:
        replacement = _normalize_chart_add_data(chart_data)
        payload = _chart_payload(self._shape)
        if _chart_data_matches_payload(payload, replacement):
            return
        chart_root = _shape_chart_root(self._shape)
        replacement_chart_xml = _replace_chart_root_data(chart_root, replacement)
        self._shape._payload["_chart_payload"] = {
            "chart_type": payload["chart_type"],
            "chart_style": payload.get("chart_style"),
            "series": [
                {
                    "name": series["name"],
                    "categories": list(series["categories"]),
                    "x_values": list(series.get("x_values") or []),
                    "values": list(series["values"]),
                    "bubble_sizes": list(series.get("bubble_sizes") or []),
                }
                for series in replacement["series"]
            ],
            "vary_by_categories": bool(payload.get("vary_by_categories", True)),
            "gap_width": int(payload.get("gap_width", 150)),
            "overlap": int(payload.get("overlap", 0)),
            "part": payload["part"],
            "has_title": bool(payload.get("has_title")),
            "title_text": str(payload.get("title_text") or ""),
            "has_legend": bool(payload.get("has_legend")),
            "legend_position": str(payload.get("legend_position") or "r"),
            "legend_include_in_layout": bool(
                payload.get("legend_include_in_layout", True)
            ),
            "data_labels": deepcopy(
                payload.get("data_labels") or _default_chart_data_labels_payload()
            ),
            "axes": deepcopy(payload.get("axes") or {}),
        }
        self._shape._payload["_chart_root"] = chart_root
        self._shape._slide._presentation._queue_chart_data_replace(
            self._shape._slide._index,
            self._shape._index,
            {
                **replacement,
                "_chart_part": str(payload.get("part") or ""),
                "_chart_xml": replacement_chart_xml,
            },
        )

    def _set_font_properties(self, properties: dict[str, Any]) -> None:
        payload = _chart_payload(self._shape)
        prop_map = {
            "font_bold": "chart_font_bold",
            "font_italic": "chart_font_italic",
            "font_underline": "chart_font_underline",
            "font_size": "chart_font_size",
            "font_fill_type": "chart_font_fill_type",
            "font_pattern": "chart_font_pattern",
            "font_pattern_fore_rgb": "chart_font_pattern_fore_rgb",
            "font_pattern_back_rgb": "chart_font_pattern_back_rgb",
            "font_gradient": "chart_font_gradient",
            "font_rgb": "chart_font_rgb",
            "font_name": "chart_font_name",
            "font_language_id": "chart_font_language_id",
        }
        queued: dict[str, Any] = {}
        _chart_text_default_run_properties(self._shape, create=True)
        for attr, value in properties.items():
            payload_attr = prop_map.get(attr)
            if payload_attr is None:
                raise AttributeError(f"unsupported chart font property: {attr!r}")
            payload[payload_attr] = value
            queued[payload_attr] = value
        queued["_chart_part"] = str(payload.get("part") or "")
        self._shape._slide._presentation._queue_chart_font(
            self._shape._slide._index,
            self._shape._index,
            queued,
        )


def _chart_data_matches_payload(
    payload: dict[str, Any],
    replacement: dict[str, Any],
) -> bool:
    current_series = list(payload.get("series") or [])
    replacement_series = list(replacement.get("series") or [])
    if len(current_series) != len(replacement_series):
        return False
    for current, new in zip(current_series, replacement_series):
        if str(current.get("name") or "") != str(new.get("name") or ""):
            return False
        if [str(value) for value in current.get("categories") or []] != [
            str(value) for value in new.get("categories") or []
        ]:
            return False
        if [float(value) for value in current.get("x_values") or []] != [
            float(value) for value in new.get("x_values") or []
        ]:
            return False
        if [float(value) for value in current.get("bubble_sizes") or []] != [
            float(value) for value in new.get("bubble_sizes") or []
        ]:
            return False
        if [float(value) for value in current.get("values") or []] != [
            float(value) for value in new.get("values") or []
        ]:
            return False
    return True


class ChartTitle:
    def __init__(self, chart: Chart) -> None:
        self._chart = chart

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(self._title_element(create=False))

    @property
    def has_text_frame(self) -> bool:
        return bool(_chart_payload(self._chart._shape).get("has_title"))

    @property
    def text_frame(self) -> "ChartTitleTextFrame":
        return ChartTitleTextFrame(self._title_element, self._queue_text)

    @property
    def format(self) -> "ChartFormat":
        return ChartFormat(
            lambda: _chart_title_proxy_element(self._chart._shape),
            self._queue_format,
        )

    def _queue_format(self, properties: dict[str, Any]) -> None:
        payload = _chart_payload(self._chart._shape)
        title = _chart_title_proxy_element(self._chart._shape, create=True)
        if properties.get("fill_type") == "solid":
            _set_chart_element_solid_fill(title)
        if properties.get("fill_type") == "background":
            _set_chart_element_background_fill(title)
        if properties.get("fill_type") == "patterned":
            _set_chart_element_pattern_fill(title, None)
        if properties.get("fill_type") == "gradient":
            _set_chart_element_gradient_fill(title, properties.get("fill_gradient"))
        if "fill_rgb" in properties:
            _set_chart_element_fill_rgb(title, str(properties["fill_rgb"]))
        if "fill_gradient" in properties:
            _set_chart_element_gradient_fill(title, properties["fill_gradient"])
        if "fill_pattern" in properties:
            _set_chart_element_pattern_fill(title, properties["fill_pattern"])
        if "fill_pattern_fore_rgb" in properties:
            _set_chart_element_pattern_rgb(
                title,
                "fgClr",
                str(properties["fill_pattern_fore_rgb"]),
            )
        if "fill_pattern_back_rgb" in properties:
            _set_chart_element_pattern_rgb(
                title,
                "bgClr",
                str(properties["fill_pattern_back_rgb"]),
            )
        if "line_rgb" in properties:
            _set_chart_element_line_rgb(title, str(properties["line_rgb"]))
        if "line_width" in properties:
            _set_chart_element_line_width(title, int(properties["line_width"]))
        if "line_dash" in properties:
            _set_chart_element_line_dash(title, properties["line_dash"])
        if "line_fill_type" in properties:
            _set_chart_element_line_fill_type(title, str(properties["line_fill_type"]))
        if "line_pattern" in properties:
            _set_chart_element_line_pattern_fill(title, properties["line_pattern"])
        if "line_pattern_fore_rgb" in properties:
            _set_chart_element_line_pattern_rgb(
                title,
                "fgClr",
                str(properties["line_pattern_fore_rgb"]),
            )
        if "line_pattern_back_rgb" in properties:
            _set_chart_element_line_pattern_rgb(
                title,
                "bgClr",
                str(properties["line_pattern_back_rgb"]),
            )
        payload["has_title"] = True
        self._chart._shape._slide._presentation._queue_chart_title(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "has_title": True,
                "text": str(payload.get("title_text") or ""),
                "format": properties,
                "_chart_part": str(payload.get("part") or ""),
                "_chart_root": _shape_chart_root(self._chart._shape),
            },
        )

    def _title_element(self, create: bool) -> Any:
        if not create and not self._chart.has_title:
            return ET.Element(f"{{{C_NS}}}title")
        return _chart_title_proxy_element(self._chart._shape, create=create)

    def _queue_text(self, properties: dict[str, Any]) -> None:
        payload = _chart_payload(self._chart._shape)
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
        self._chart._shape._slide._presentation._queue_chart_title(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "has_title": True,
                **properties,
                "_chart_part": str(payload.get("part") or ""),
                "_chart_root": _shape_chart_root(self._chart._shape),
            },
        )


class ChartPlotCollection(Sequence["ChartPlot"]):
    def __init__(self, chart: Chart) -> None:
        self._chart = chart

    def __getitem__(self, index: int | slice) -> "ChartPlot | list[ChartPlot]":
        if isinstance(index, slice):
            return [
                ChartPlot(self._chart, item)
                for item in range(*index.indices(len(self)))
            ]
        if index < 0:
            index += len(self)
        if index != 0 or len(self) == 0:
            raise IndexError("chart plot index out of range")
        return ChartPlot(self._chart, index)

    def __iter__(self) -> Iterator["ChartPlot"]:
        for index in range(len(self)):
            yield ChartPlot(self._chart, index)

    def __len__(self) -> int:
        return 1 if _chart_payload(self._chart._shape)["series"] else 0

    @property
    def count(self) -> int:
        return len(self)


class ChartPlot:
    def __init__(self, chart: Chart, index: int) -> None:
        self._chart = chart
        self._index = index

    @property
    def chart(self) -> Chart:
        return self._chart

    @property
    def categories(self) -> list[str]:
        return self._chart.categories

    @property
    def series(self) -> "ChartSeriesCollection":
        return self._chart.series

    @property
    def vary_by_categories(self) -> bool:
        return bool(_chart_payload(self._chart._shape).get("vary_by_categories", True))

    @vary_by_categories.setter
    def vary_by_categories(self, value: Any) -> None:
        vary = bool(value)
        payload = _chart_payload(self._chart._shape)
        if vary == bool(payload.get("vary_by_categories", True)):
            return
        payload["vary_by_categories"] = vary
        self._chart._shape._slide._presentation._queue_chart_plot_property(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            "vary_by_categories",
            vary,
        )

    @property
    def gap_width(self) -> int:
        return int(_chart_payload(self._chart._shape).get("gap_width", 150))

    @gap_width.setter
    def gap_width(self, value: Any) -> None:
        gap_width = _normalize_chart_plot_int(
            value,
            minimum=0,
            maximum=500,
        )
        self._set_property("gap_width", gap_width)

    @property
    def overlap(self) -> int:
        return int(_chart_payload(self._chart._shape).get("overlap", 0))

    @overlap.setter
    def overlap(self, value: Any) -> None:
        overlap = _normalize_chart_plot_int(
            value,
            minimum=-100,
            maximum=100,
        )
        self._set_property("overlap", overlap)

    @property
    def has_data_labels(self) -> bool:
        return bool(
            _chart_data_labels_payload(self._chart._shape).get("has_data_labels")
        )

    @has_data_labels.setter
    def has_data_labels(self, value: Any) -> None:
        has_data_labels = bool(value)
        payload = _chart_data_labels_payload(self._chart._shape)
        if has_data_labels == bool(payload.get("has_data_labels")):
            return
        payload["has_data_labels"] = has_data_labels
        self._chart._shape._slide._presentation._queue_chart_data_labels(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {"has_data_labels": has_data_labels},
        )

    @property
    def data_labels(self) -> "DataLabels":
        if not self.has_data_labels:
            raise ValueError("plot has no data labels, set has_data_labels = True first")
        return DataLabels(self)

    def _set_property(self, attr: str, value: Any) -> None:
        payload = _chart_payload(self._chart._shape)
        if payload.get(attr) == value:
            return
        payload[attr] = value
        self._chart._shape._slide._presentation._queue_chart_plot_property(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            attr,
            value,
        )


class Legend:
    def __init__(self, chart: Chart) -> None:
        self._chart = chart

    @property
    def font(self) -> "ChartFont":
        return ChartFont(
            lambda: _chart_legend_text_default_run_properties(self._chart._shape),
            self._set_font_properties,
            lambda: _chart_payload(self._chart._shape).get("legend_font_size"),
            lambda: _chart_payload(self._chart._shape).get("legend_font_fill_type"),
            lambda: _chart_payload(self._chart._shape).get("legend_font_pattern"),
            lambda: _chart_payload(self._chart._shape).get("legend_font_gradient"),
        )

    @property
    def position(self) -> Any:
        return _legend_position_value(
            str(_chart_payload(self._chart._shape).get("legend_position") or "r")
        )

    @position.setter
    def position(self, value: Any) -> None:
        position = _normalize_legend_position(value)
        payload = _chart_payload(self._chart._shape)
        if bool(payload.get("has_legend")) and position == str(
            payload.get("legend_position") or "r"
        ):
            return
        payload["has_legend"] = True
        payload["legend_position"] = position
        self._chart._shape._slide._presentation._queue_chart_legend(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "has_legend": True,
                "position": position,
                "_chart_part": str(payload.get("part") or ""),
            },
        )

    @property
    def include_in_layout(self) -> bool:
        return bool(_chart_payload(self._chart._shape).get("legend_include_in_layout", True))

    @include_in_layout.setter
    def include_in_layout(self, value: bool) -> None:
        include = bool(value)
        payload = _chart_payload(self._chart._shape)
        if bool(payload.get("has_legend")) and include == bool(
            payload.get("legend_include_in_layout", True)
        ):
            return
        payload["has_legend"] = True
        payload["legend_include_in_layout"] = include
        self._chart._shape._slide._presentation._queue_chart_legend(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "has_legend": True,
                "include_in_layout": include,
                "_chart_part": str(payload.get("part") or ""),
            },
        )

    def _set_font_properties(self, properties: dict[str, Any]) -> None:
        payload = _chart_payload(self._chart._shape)
        payload["has_legend"] = True
        prop_map = {
            "font_bold": "legend_font_bold",
            "font_italic": "legend_font_italic",
            "font_underline": "legend_font_underline",
            "font_size": "legend_font_size",
            "font_fill_type": "legend_font_fill_type",
            "font_pattern": "legend_font_pattern",
            "font_pattern_fore_rgb": "legend_font_pattern_fore_rgb",
            "font_pattern_back_rgb": "legend_font_pattern_back_rgb",
            "font_gradient": "legend_font_gradient",
            "font_rgb": "legend_font_rgb",
            "font_name": "legend_font_name",
        }
        queued: dict[str, Any] = {"has_legend": True}
        _chart_legend_text_default_run_properties(self._chart._shape, create=True)
        for attr, value in properties.items():
            payload_attr = prop_map.get(attr)
            if payload_attr is None:
                raise AttributeError(f"unsupported chart legend font property: {attr!r}")
            payload[payload_attr] = value
            queued[payload_attr] = value
        queued["_chart_part"] = str(payload.get("part") or "")
        self._chart._shape._slide._presentation._queue_chart_legend(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            queued,
        )


class ChartSeriesCollection(Sequence["ChartSeries"]):
    def __init__(self, chart: Chart, series: list[dict[str, Any]]) -> None:
        self._chart = chart
        self._series = series

    def __getitem__(self, index: int | slice) -> "ChartSeries | list[ChartSeries]":
        if isinstance(index, slice):
            return [
                ChartSeries(self._chart, item, item_index)
                for item_index, item in zip(
                    range(*index.indices(len(self))),
                    self._series[index],
                    strict=True,
                )
            ]
        item_index = index
        if item_index < 0:
            item_index += len(self)
        return ChartSeries(self._chart, self._series[index], item_index)

    def __iter__(self) -> Iterator["ChartSeries"]:
        for index, item in enumerate(self._series):
            yield ChartSeries(self._chart, item, index)

    def __len__(self) -> int:
        return len(self._series)


class ChartSeries:
    def __init__(self, chart: Chart, payload: dict[str, Any], index: int) -> None:
        self._chart = chart
        self._payload = payload
        self._fallback_index = index

    @property
    def index(self) -> int:
        return int(self._payload.get("index", self._fallback_index))

    @property
    def name(self) -> str:
        return str(self._payload.get("name") or "")

    @property
    def categories(self) -> list[str]:
        return list(self._payload.get("categories") or [])

    @property
    def x_values(self) -> list[float]:
        return [float(value) for value in self._payload.get("x_values") or []]

    @property
    def bubble_sizes(self) -> list[float]:
        return [float(value) for value in self._payload.get("bubble_sizes") or []]

    @property
    def values(self) -> list[float]:
        return [float(value) for value in self._payload.get("values") or []]

    @property
    def invert_if_negative(self) -> bool:
        return bool(self._payload.get("invert_if_negative", True))

    @property
    def points(self) -> "ChartPointCollection":
        return ChartPointCollection(self)

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_series_element(self._chart._shape, self.index),
            self._queue_format,
        )

    @property
    def data_labels(self) -> "DataLabels":
        return ChartSeriesDataLabels(self)

    def _queue_format(self, properties: dict[str, Any]) -> None:
        element = _chart_series_element(self._chart._shape, self.index)
        if properties.get("fill_type") == "solid":
            _set_chart_element_solid_fill(element)
        if properties.get("fill_type") == "background":
            _set_chart_element_background_fill(element)
        if properties.get("fill_type") == "patterned":
            _set_chart_element_pattern_fill(element, None)
        if properties.get("fill_type") == "gradient":
            _set_chart_element_gradient_fill(element, properties.get("fill_gradient"))
        if "fill_rgb" in properties:
            _set_chart_element_fill_rgb(element, str(properties["fill_rgb"]))
        if "fill_gradient" in properties:
            _set_chart_element_gradient_fill(element, properties["fill_gradient"])
        if "fill_pattern" in properties:
            _set_chart_element_pattern_fill(element, properties["fill_pattern"])
        if "fill_pattern_fore_rgb" in properties:
            _set_chart_element_pattern_rgb(
                element,
                "fgClr",
                str(properties["fill_pattern_fore_rgb"]),
            )
        if "fill_pattern_back_rgb" in properties:
            _set_chart_element_pattern_rgb(
                element,
                "bgClr",
                str(properties["fill_pattern_back_rgb"]),
            )
        if "line_rgb" in properties:
            _set_chart_element_line_rgb(element, str(properties["line_rgb"]))
        if "line_width" in properties:
            _set_chart_element_line_width(element, int(properties["line_width"]))
        if "line_dash" in properties:
            _set_chart_element_line_dash(element, properties["line_dash"])
        if "line_fill_type" in properties:
            _set_chart_element_line_fill_type(
                element,
                str(properties["line_fill_type"]),
            )
        if "line_pattern" in properties:
            _set_chart_element_line_pattern_fill(element, properties["line_pattern"])
        if "line_pattern_fore_rgb" in properties:
            _set_chart_element_line_pattern_rgb(
                element,
                "fgClr",
                str(properties["line_pattern_fore_rgb"]),
            )
        if "line_pattern_back_rgb" in properties:
            _set_chart_element_line_pattern_rgb(
                element,
                "bgClr",
                str(properties["line_pattern_back_rgb"]),
            )
        self._chart._shape._slide._presentation._queue_chart_data_labels(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "series_formats": [
                    {
                        "series_index": self.index,
                        "properties": properties,
                    }
                ]
            },
        )
