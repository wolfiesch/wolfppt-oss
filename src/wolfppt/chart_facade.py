"""Chart facade classes and XML readers for python-pptx-compatible access."""
# ruff: noqa: F401

from __future__ import annotations

import math
import numbers
import warnings
from collections.abc import Callable, Iterator, Sequence
from copy import deepcopy
from typing import Any, overload
from xml.etree import ElementTree as ET

from .chart_adds import (
    _generated_chart_package_parts,
)
from .chart_axis_facade import (
    ChartAxis,
    ChartAxisTitle,
    ChartSeriesDataLabels,
    DataLabels,
    MajorGridlines,
    TickLabels,
)
from .chart_edits import (
    ChartWorkbookNotUpdatedWarning,
    _chart_embedded_workbook_part_in_package,
    _normalize_chart_add_data,
)
from .chart_element_format_xml import (
    set_chart_element_format_properties as _set_chart_element_format_properties,
)
from .chart_element_format_xml import (
    set_chart_element_format_property as _set_chart_element_format_property,
)
from .chart_extended_facade import ExtendedChart
from .chart_extended_facade import extended_chart_for_shape as _extended_chart
from .chart_facade_helpers import (
    C_NS,
    _chart_legend_insert_index,
)
from .chart_facade_helpers import (
    chart_axis_payload as _chart_axis_payload,
)
from .chart_facade_helpers import (
    chart_axis_proxy_element as _chart_axis_proxy_element,
)
from .chart_facade_helpers import (
    chart_axis_text_default_run_properties as _chart_axis_text_default_run_properties,
)
from .chart_facade_helpers import (
    chart_data_labels_payload as _chart_data_labels_payload,
)
from .chart_facade_helpers import (
    chart_data_labels_text_default_run_properties as _chart_data_labels_text_default_run_properties,
)
from .chart_facade_helpers import (
    chart_legend_text_default_run_properties as _chart_legend_text_default_run_properties,
)
from .chart_facade_helpers import (
    chart_payload as _chart_payload,
)
from .chart_facade_helpers import (
    chart_text_default_run_properties as _chart_text_default_run_properties,
)
from .chart_facade_helpers import (
    chart_title_proxy_element as _chart_title_proxy_element,
)
from .chart_facade_helpers import (
    normalize_chart_plot_int as _normalize_chart_plot_int,
)
from .chart_facade_helpers import normalize_choice as _normalize_choice
from .chart_facade_helpers import (
    normalize_tick_label_offset as _normalize_tick_label_offset,
)
from .chart_facade_helpers import (
    set_chart_series_invert_if_negative as _set_chart_series_invert_if_negative,
)
from .chart_facade_helpers import (
    shape_chart_part as _shape_chart_part,
)
from .chart_facade_helpers import (
    shape_chart_root as _shape_chart_root,
)
from .chart_financial import (
    apply_financial_chart_formatting as _apply_financial_formatting,
)
from .chart_financial import (
    financial_chart_payload as _financial_chart_payload,
)
from .chart_financial import financial_marker_kind as _financial_marker_kind
from .chart_font_format_facade import ChartTextFormat, chart_text_body, chart_text_xml
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
from .chart_gap_xml import set_child
from .chart_layout_facade import ElementLayout, layout_signature, render_layout_package
from .chart_legend_xml import (
    legend_entry_element,
    set_legend_entry_font,
)
from .chart_point_data_label_xml import set_run_properties_font
from .chart_point_facade import (
    ChartPoint,
    ChartPointCollection,
    DataLabel,
    Marker,
)
from .chart_point_facade_xml import (
    chart_series_element as _chart_series_element,
)
from .chart_title_text_facade import (
    ChartTitleTextFrame,
)
from .chart_title_text_facade import (
    ChartTitleTextFrame as ChartAxisTitleTextFrame,
)
from .chart_title_text_xml import (
    _title_insert_index,
)
from .chart_title_text_xml import (
    set_title_text as _set_title_text,
)
from .chart_trendline_facade import (
    ChartTrendlines,
    _SeriesTrendlineState,
)
from .chart_trendline_xml import (
    TrendlineRefusal,
    TrendlineSpec,
)
from .chart_trendline_xml import (
    register_chart_namespaces as _register_chart_namespaces,
)
from .chart_trendline_xml import (
    resolve_series_and_plot as _resolve_series_and_plot,
)
from .chart_trendline_xml import (
    set_chart_series_trendlines as _set_chart_series_trendlines,
)
from .chart_trendline_xml import (
    validate_series_plot_family as _validate_series_plot_family,
)
from .chart_xml import (
    BUBBLE_SIZE_REPRESENTATION_TOKENS as _BUBBLE_SIZE_REPRESENTATION_TOKENS,
)
from .chart_xml import (
    DISPLAY_BLANKS_AS_VALUES as _DISPLAY_BLANKS_AS_VALUES,
)
from .chart_xml import (
    chart_axis_element as _chart_axis_element,
)
from .chart_xml import (
    chart_bubble_size_representation as _chart_bubble_size_representation,
)
from .chart_xml import (
    chart_container_element as _chart_container_element,
)
from .chart_xml import (
    chart_display_blanks_as as _chart_display_blanks_as,
)
from .chart_xml import (
    chart_plot_element_count as _chart_plot_element_count,
)
from .chart_xml import (
    chart_plot_elements as _chart_plot_elements,
)
from .chart_xml import (
    chart_type_value as _chart_type_value,
)
from .chart_xml import (
    default_chart_data_labels_payload as _default_chart_data_labels_payload,
)
from .chart_xml import (
    first_chart_element as _first_chart_element,
)
from .chart_xml import (
    reorder_chart_root_series as _reorder_chart_root_series,
)
from .chart_xml import (
    replace_chart_root_data as _replace_chart_root_data,
)
from .chart_xml import (
    replace_chart_root_data_preserving_series_layout as _preserving_series_layout,
)
from .facade_values import (
    axis_crosses_value as _axis_crosses_value,
)
from .facade_values import (
    axis_tick_mark_value as _axis_tick_mark_value,
)
from .facade_values import (
    category_axis_type_value as _category_axis_type_value,
)
from .facade_values import (
    data_label_position_value as _data_label_position_value,
)
from .facade_values import (
    legend_position_value as _legend_position_value,
)
from .facade_values import (
    normalize_axis_crosses as _normalize_axis_crosses,
)
from .facade_values import (
    normalize_axis_tick_mark as _normalize_axis_tick_mark,
)
from .facade_values import (
    normalize_data_label_position as _normalize_data_label_position,
)
from .facade_values import (
    normalize_legend_position as _normalize_legend_position,
)
from .facade_values import (
    normalize_optional_float as _normalize_optional_float,
)
from .facade_values import (
    normalize_tick_label_position as _normalize_tick_label_position,
)
from .facade_values import (
    optional_float as _optional_float,
)
from .facade_values import (
    tick_label_position_value as _tick_label_position_value,
)
from .package_parts import (
    PackagePart,
    XmlElementProxy,
    open_package_source,
)
from .package_parts import (
    package_xml_element as _package_xml_element,
)


class Chart:
    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def part(self) -> PackagePart:
        return PackagePart(
            self._shape._slide._presentation,
            str(_chart_payload(self._shape)["part"]),
            name=None,
        )

    @property
    def theme(self) -> Any:
        """Chart-local theme override; save and reopen new charts before editing."""
        from .theme_facade import theme_edits

        return theme_edits(self._shape._slide._presentation).theme_for(self)

    @property
    def element(self) -> XmlElementProxy:
        return _package_xml_element(
            self._shape._slide._presentation._source_path,
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
        style = None if value is None else _normalize_chart_plot_int(value, minimum=1, maximum=48)
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
    def rounded_corners(self) -> bool:
        """Read ``c:roundedCorners``; absent means square corners."""
        return _chart_option_bool(_shape_chart_root(self._shape), "roundedCorners", False)

    @property
    def auto_title_deleted(self) -> bool:
        """Whether the automatic chart title was explicitly deleted."""
        return _chart_option_bool(_shape_chart_root(self._shape), "chart/autoTitleDeleted", False)

    @property
    def plot_visible_only(self) -> bool:
        """Whether hidden source cells are excluded; absent means true."""
        return _chart_option_bool(_shape_chart_root(self._shape), "chart/plotVisOnly", True)

    @property
    def view_3d(self) -> ChartView3D:
        """Read the chart's 3-D view, including defaults for omitted options."""
        return ChartView3D(self)

    @property
    def floor(self) -> ChartWall:
        """Read the 3-D chart floor."""
        return ChartWall(self, "floor")

    @property
    def side_wall(self) -> ChartWall:
        """Read the 3-D chart side wall."""
        return ChartWall(self, "sideWall")

    @property
    def back_wall(self) -> ChartWall:
        """Read the 3-D chart back wall."""
        return ChartWall(self, "backWall")

    @property
    def financial_kind(self) -> str | None:
        """Return the authored financial chart kind recorded on the chart part.

        Charts authored through :mod:`wolfppt.chart_financial` carry an explicit
        chart extension marker naming the financial construction, so the kind
        survives a save/reopen round trip without depending on series names.
        """
        return _financial_marker_kind(_shape_chart_root(self._shape))

    @property
    def series(self) -> ChartSeriesCollection:
        return ChartSeriesCollection(self, _chart_payload(self._shape)["series"])

    @property
    def plots(self) -> ChartPlotCollection:
        return ChartPlotCollection(self)

    @property
    def extended(self) -> ExtendedChart | None:
        """The Office 2016+ ChartEx facade, ``None`` for a classic chart.

        Treemap, sunburst, histogram, box-and-whisker and the other ChartEx
        layouts live in a ``cx:chartSpace`` part; this facade edits their point
        levels and series layout properties.
        """
        return _extended_chart(self._shape)

    @property
    def display_blanks_as(self) -> str:
        """How empty cells plot: ``"gap"``, ``"span"`` (connect) or ``"zero"``."""
        payload = _chart_payload(self._shape)
        if "display_blanks_as" not in payload:
            payload["display_blanks_as"] = _chart_display_blanks_as(_shape_chart_root(self._shape))
        return str(payload["display_blanks_as"])

    @display_blanks_as.setter
    def display_blanks_as(self, value: Any) -> None:
        token = _normalize_choice(value, _DISPLAY_BLANKS_AS_VALUES, "display_blanks_as")
        _chart_payload(self._shape)["display_blanks_as"] = token
        self._shape._payload.pop("_chart_actual_layout", None)
        self._shape._slide._presentation._queue_chart_plot_property(
            self._shape._slide._index,
            self._shape._index,
            "display_blanks_as",
            token,
        )

    @property
    def plot_area(self) -> Any:
        """Plot-area manual layout and renderer-reported actual geometry."""
        from .chart_gap_facade import ChartPlotArea

        return ChartPlotArea(self)

    def data_label_layout(self, series_index: int, point_index: int) -> Any:
        """Manual/actual geometry of a point label, addressed by public indices."""
        from .chart_point_data_label_xml import PointDataLabelLayout

        return PointDataLabelLayout(self, series_index, point_index)

    def render_layout(self, *, fonts: Any, scheme: Any, text_style: Any) -> list[Any]:
        """Render the current in-memory chart and record its actual plot rectangle.

        Fonts, theme and text style are the same admitted objects accepted by
        the native renderer. Coordinates are EMU relative to the chart frame.
        A refused render clears stale geometry and raises RenderRefusal.
        Community installs raise CommercialFeatureError for this rendering API.
        """
        from .editions import commercial_module

        self._shape._payload.pop("_chart_actual_layout", None)
        renderer = commercial_module("render_chart", "Rendering chart layout")
        geometry = commercial_module("render_model", "Rendering chart layout")
        refusals = commercial_module("render_refusals", "Rendering chart layout")
        layout: dict[str, Any] = {}
        log = refusals.RefusalLog()
        primitives = renderer.chart_primitives(
            _shape_chart_root(self._shape),
            render_layout_package(self),
            scheme,
            fonts,
            geometry.Rect(0, 0, int(self._shape.width), int(self._shape.height)),
            text_style,
            log=log,
            label="chart",
            part=str(_chart_payload(self._shape).get("part") or ""),
            layout_output=layout,
        )
        log.raise_if_any()
        self._shape._payload["_chart_actual_layout"] = layout
        self._shape._payload["_chart_actual_layout_signature"] = layout_signature(self)
        return primitives

    @property
    def has_data_table(self) -> bool:
        """Whether the chart displays an Open XML ``c:dTable``."""
        return bool(_chart_data_table_state(self._shape)["has_data_table"])

    @has_data_table.setter
    def has_data_table(self, value: bool) -> None:
        state = _chart_data_table_state(self._shape)
        enabled = bool(value)
        if enabled == state["has_data_table"]:
            return
        self._queue_data_table({"has_data_table": enabled})

    @property
    def data_table(self) -> ChartDataTable:
        """Return the chart data-table configuration."""
        return ChartDataTable(self)

    def _queue_data_table(self, changes: dict[str, bool]) -> None:
        payload = _chart_payload(self._shape)
        self._shape._slide._presentation._queue_chart_data_table(
            self._shape._slide._index,
            self._shape._index,
            {
                **_chart_data_table_state(self._shape),
                **changes,
                "_chart_part": str(payload.get("part") or ""),
            },
        )

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
    def chart_title(self) -> ChartTitle:
        return ChartTitle(self)

    @property
    def font(self) -> ChartFont:
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
    def legend(self) -> Legend | None:
        if not self.has_legend:
            return None
        return Legend(self)

    @property
    def category_axis(self) -> ChartAxis:
        return ChartAxis(self, "cat")

    @property
    def value_axis(self) -> ChartAxis:
        return ChartAxis(self, "val")

    @property
    def series_axis(self) -> ChartAxis:
        """Return the existing 3-D chart series axis; do not create an axis."""
        axis = ChartAxis(self, "ser")
        axis._check_live()
        chart = _chart_container_element(_shape_chart_root(self._shape))
        if chart is None or _chart_axis_element(chart, "ser") is None:
            raise ValueError("chart has no series axis")
        return axis

    @property
    def secondary_value_axis(self) -> ChartAxis:
        """Return and attach the chart's right-hand value axis."""
        axis = ChartAxis(self, "val2")
        axis._set_property("attach_secondary", True)
        return axis

    def replace_data(self, chart_data: Any) -> None:
        """Replace chart data with python-pptx-compatible positional semantics.

        Charts without an embedded workbook are edited cache-only. In that
        case, emit ``wolfppt.chart_edits.ChartWorkbookNotUpdatedWarning``;
        retain external links without reading or writing their targets.
        Unsupported caches or missing embedded parts raise
        ``wolfppt.chart_xml.ChartDataRefusal`` before changing the chart.
        """
        self._replace_data(chart_data)

    def replace_data_keyed(
        self,
        chart_data: Any,
        current_keys: Sequence[str],
        replacement_keys: Sequence[str],
    ) -> None:
        """Replace data after moving each existing series by its stable business key."""
        self._replace_data(
            chart_data,
            current_keys=tuple(current_keys),
            replacement_keys=tuple(replacement_keys),
        )

    def replace_financial_data(self, spec: Any) -> None:
        """Refresh an authored combination or waterfall chart from its spec.

        The chart part and its embedded workbook are the only package parts
        rewritten, so chart styling, the slide, and every unrelated part are
        preserved exactly.  Bridge charts additionally reapply their
        data-derived role fills and label text, because a category that moves
        across zero changes role and a stale label would state a wrong value.
        """
        replacement = dict(_financial_chart_payload(spec))
        replacement.pop("_precomputed_chart_xml", None)
        self._replace_data(
            replacement,
            xml_transform=lambda chart_xml: _apply_financial_formatting(
                chart_xml=chart_xml,
                spec=spec,
            ),
        )

    def _replace_data(
        self,
        chart_data: Any,
        *,
        current_keys: tuple[str, ...] | None = None,
        replacement_keys: tuple[str, ...] | None = None,
        xml_transform: Callable[[bytes], bytes] | None = None,
    ) -> None:
        replacement = _normalize_chart_add_data(chart_data)
        payload = _chart_payload(self._shape)
        shape_root = _shape_chart_root(self._shape)
        chart_root = deepcopy(shape_root)
        if (
            current_keys is None
            and _chart_data_matches_payload(payload, replacement)
            and _series_cache_formats_match(chart_root, replacement["series"])
        ):
            return
        chart_part = str(payload.get("part") or "")
        cache_only = False
        if chart_part and replacement.get("xlsx_blob") is not None:
            with open_package_source(self._shape._slide._presentation._source_path) as package:
                cache_only = _chart_embedded_workbook_part_in_package(package, chart_part) is None
        if current_keys is not None:
            if replacement_keys is None:
                raise ValueError("replacement business-series keys are required")
            _reorder_chart_root_series(chart_root, current_keys, replacement_keys)
        if _chart_plot_element_count(chart_root) > 1:
            # Combination charts bind series and axes per plot, so the refresh
            # must reuse the authored plot layout instead of treating every
            # series as a member of the first plot.
            replacement_chart_xml = _preserving_series_layout(chart_root, replacement)
        else:
            replacement_chart_xml = _replace_chart_root_data(chart_root, replacement)
        if xml_transform is not None:
            replacement_chart_xml = xml_transform(replacement_chart_xml)
        if cache_only:
            warnings.warn(
                f"{chart_part}: cache only; no embedded workbook was updated",
                ChartWorkbookNotUpdatedWarning,
                stacklevel=3,
            )
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
            "bubble_scale": payload.get("bubble_scale"),
            "part": payload["part"],
            "has_title": bool(payload.get("has_title")),
            "title_text": str(payload.get("title_text") or ""),
            "has_legend": bool(payload.get("has_legend")),
            "legend_position": str(payload.get("legend_position") or "r"),
            "legend_include_in_layout": bool(payload.get("legend_include_in_layout", True)),
            "legend_horz_offset": float(payload.get("legend_horz_offset", 0.0)),
            "data_labels": deepcopy(
                payload.get("data_labels") or _default_chart_data_labels_payload()
            ),
            "axes": deepcopy(payload.get("axes") or {}),
        }
        # Queued title and legend edits hold the shape's root object, so commit the
        # refreshed tree into it instead of rebinding the payload to the working copy.
        shape_root.clear()
        shape_root.attrib.update(chart_root.attrib)
        shape_root.extend(list(chart_root))
        self._shape._payload["_chart_root"] = shape_root
        self._shape._slide._presentation._queue_chart_data_replace(
            self._shape._slide._index,
            self._shape._index,
            {
                **replacement,
                "_chart_part": str(payload.get("part") or ""),
                "_chart_xml": replacement_chart_xml,
                "_cache_only": cache_only,
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


def _chart_option_element(root: ET.Element, path: str) -> ET.Element | None:
    return root.find("/".join(f"{{{C_NS}}}{name}" for name in path.split("/")))


def _chart_option_bool(root: ET.Element, path: str, default: bool) -> bool:
    element = _chart_option_element(root, path)
    if element is None:
        return default
    return element.get("val", "1").lower() in {"1", "true", "on"}


def _chart_option_int(root: ET.Element, path: str, default: int) -> int:
    element = _chart_option_element(root, path)
    return default if element is None else int(element.get("val", str(default)))


class ChartView3D:
    """Read-only ECMA-376 ``c:view3D`` settings, in degrees or percentages."""

    def __init__(self, chart: Chart) -> None:
        self._chart = chart

    @property
    def rotation_x(self) -> int:
        return _chart_option_int(_shape_chart_root(self._chart._shape), "chart/view3D/rotX", 0)

    @property
    def rotation_y(self) -> int:
        return _chart_option_int(_shape_chart_root(self._chart._shape), "chart/view3D/rotY", 0)

    @property
    def right_angle_axes(self) -> bool:
        return _chart_option_bool(
            _shape_chart_root(self._chart._shape), "chart/view3D/rAngAx", True
        )

    @property
    def depth_percent(self) -> int:
        return _chart_option_int(
            _shape_chart_root(self._chart._shape), "chart/view3D/depthPercent", 100
        )

    @property
    def perspective(self) -> int:
        return _chart_option_int(
            _shape_chart_root(self._chart._shape), "chart/view3D/perspective", 30
        )


class ChartWall:
    """Read-only floor, side-wall or back-wall settings."""

    def __init__(self, chart: Chart, name: str) -> None:
        self._chart = chart
        self._name = name

    @property
    def thickness(self) -> int:
        """Wall thickness as a percentage; absent means zero."""
        return _chart_option_int(
            _shape_chart_root(self._chart._shape), f"chart/{self._name}/thickness", 0
        )


class ChartDataTable:
    """Configuration for the ``c:dTable`` child of a chart plot area."""

    def __init__(self, chart: Chart) -> None:
        self._chart = chart

    @property
    def has_horizontal_border(self) -> bool:
        return bool(_chart_data_table_state(self._chart._shape)["show_horz_border"])

    @has_horizontal_border.setter
    def has_horizontal_border(self, value: bool) -> None:
        self._set("show_horz_border", value)

    @property
    def has_vertical_border(self) -> bool:
        return bool(_chart_data_table_state(self._chart._shape)["show_vert_border"])

    @has_vertical_border.setter
    def has_vertical_border(self, value: bool) -> None:
        self._set("show_vert_border", value)

    @property
    def has_outline(self) -> bool:
        return bool(_chart_data_table_state(self._chart._shape)["show_outline"])

    @has_outline.setter
    def has_outline(self, value: bool) -> None:
        self._set("show_outline", value)

    @property
    def show_legend_key(self) -> bool:
        return bool(_chart_data_table_state(self._chart._shape)["show_keys"])

    @show_legend_key.setter
    def show_legend_key(self, value: bool) -> None:
        self._set("show_keys", value)

    def _set(self, name: str, value: bool) -> None:
        state = _chart_data_table_state(self._chart._shape)
        normalized = bool(value)
        if state[name] == normalized and state["has_data_table"]:
            return
        self._chart._queue_data_table({"has_data_table": True, name: normalized})


def _chart_data_table_state(shape: Any) -> dict[str, bool]:
    defaults = {
        "has_data_table": False,
        "show_horz_border": False,
        "show_vert_border": False,
        "show_outline": False,
        "show_keys": False,
    }
    edits = getattr(shape._slide._presentation, "_chart_plot_property_edits", {})
    pending = edits.get((shape._slide._index, shape._index), {}).get("_data_table")
    if isinstance(pending, dict):
        return {name: bool(pending.get(name, default)) for name, default in defaults.items()}

    plot_area = _shape_chart_root(shape).find(f".//{{{C_NS}}}plotArea")
    if plot_area is None:
        return defaults
    data_table = plot_area.find(f"{{{C_NS}}}dTable")
    if data_table is None:
        return defaults

    def enabled(name: str) -> bool:
        element = data_table.find(f"{{{C_NS}}}{name}")
        return element is not None and element.get("val", "1").casefold() not in {
            "0",
            "false",
            "off",
        }

    return {
        "has_data_table": True,
        "show_horz_border": enabled("showHorzBorder"),
        "show_vert_border": enabled("showVertBorder"),
        "show_outline": enabled("showOutline"),
        "show_keys": enabled("showKeys"),
    }


def _chart_numeric_values(values: Any) -> list[float | None]:
    return [None if value is None else float(value) for value in values or []]


def _chart_data_matches_payload(
    payload: dict[str, Any],
    replacement: dict[str, Any],
) -> bool:
    current_series = list(payload.get("series") or [])
    replacement_series = list(replacement.get("series") or [])
    if len(current_series) != len(replacement_series):
        return False
    for current, new in zip(current_series, replacement_series, strict=True):
        if str(current.get("name") or "") != str(new.get("name") or ""):
            return False
        if [str(value) for value in current.get("categories") or []] != [
            str(value) for value in new.get("categories") or []
        ]:
            return False
        for key in ("x_values", "bubble_sizes", "values"):
            if _chart_numeric_values(current.get(key)) != _chart_numeric_values(new.get(key)):
                return False
    return True


def _series_cache_formats_match(
    chart_root: ET.Element, replacement_series: list[dict[str, Any]]
) -> bool:
    """Whether every XY/bubble value cache already carries the new series format.

    replace_data rewrites these ``formatCode`` values, so identical numbers with
    a different format are still a change. Series without a format (category
    payloads) have nothing to compare.
    """
    number_formats = [series.get("number_format") for series in replacement_series]
    if all(number_format is None for number_format in number_formats):
        return True
    series_elements = list(chart_root.iter(f"{{{C_NS}}}ser"))
    if len(series_elements) != len(number_formats):
        return False
    for series_element, number_format in zip(series_elements, number_formats, strict=True):
        if number_format is None:
            continue
        for tag in ("xVal", "yVal", "bubbleSize"):
            cache = series_element.find(f"{{{C_NS}}}{tag}/{{{C_NS}}}numRef/{{{C_NS}}}numCache")
            if cache is None:
                continue
            format_code = cache.findtext(f"{{{C_NS}}}formatCode") or "General"
            if format_code != str(number_format):
                return False
    return True


class ChartTitle(ElementLayout):
    def __init__(self, chart: Chart) -> None:
        self._chart = chart

    @property
    def overlay(self) -> bool:
        """Whether the title overlaps the plot area; absent means False."""
        return _chart_option_bool(self._title_element(False), "overlay", False)

    @overlay.setter
    def overlay(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("overlay must be a bool")
        if value == self.overlay:
            return
        set_child(
            self._title_element(True),
            "overlay",
            int(value),
            (
                "tx",
                "layout",
                "overlay",
                "spPr",
                "txPr",
                "extLst",
            ),
        )
        self._queue_text({})

    @property
    def layout(self) -> float:
        """Manual x fraction, defaulting to zero for automatic layout."""
        return self.manual_layout.get("x", 0.0)

    @layout.setter
    def layout(self, value: float) -> None:
        self.manual_layout = {**self.manual_layout, "x": value}

    @property
    def _layout_chart(self) -> Chart:
        return self._chart

    _layout_key = "title"

    def _layout_element(self, create: bool) -> ET.Element:
        element = self._title_element(create)
        if create:
            _chart_payload(self._chart._shape)["has_title"] = True
        return element

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(self._title_element(create=False))

    @property
    def has_text_frame(self) -> bool:
        return self._title_element(False).find(f"{{{C_NS}}}tx/{{{C_NS}}}rich") is not None

    @has_text_frame.setter
    def has_text_frame(self, value: bool) -> None:
        if not value:
            raise NotImplementedError(
                "removing a chart title text frame is not supported; "
                "set chart.has_title = False to remove the title"
            )
        title = self._title_element(True)
        if title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich") is None:
            _set_title_text(title, "")
            self._queue_text({"text": ""})

    @property
    def text_frame(self) -> ChartTitleTextFrame:
        return ChartTitleTextFrame(self._title_element, self._queue_text)

    @property
    def text_format(self) -> ChartTextFormat:
        return self.text_frame.text_format

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_title_proxy_element(self._chart._shape),
            self._queue_format,
        )

    def _queue_format(self, properties: dict[str, Any]) -> None:
        payload = _chart_payload(self._chart._shape)
        title = _chart_title_proxy_element(self._chart._shape, create=True)
        # Apply outline fill after RGB/width/dash, as in the title edit contract.
        outline = {
            name: value
            for name, value in properties.items()
            if name.startswith(("line_fill_", "line_pattern"))
        }
        basic = {name: value for name, value in properties.items() if name not in outline}
        _set_chart_element_format_properties(title, basic)
        _set_chart_element_format_properties(title, outline)
        payload["has_title"] = True
        self._chart._shape._slide._presentation._queue_chart_title(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "has_title": True,
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
        properties = {
            **properties,
            "_text_xml": chart_text_xml(self._title_element(False)),
        }
        if "text" in properties:
            payload["title_text"] = str(properties["text"])
        elif "paragraphs" in properties:
            payload["title_text"] = "\n".join(
                str(paragraph) for paragraph in properties["paragraphs"]
            )
        elif "paragraph_runs" in properties:
            payload["title_text"] = "\n".join(
                "".join(str(run) for run in runs) for runs in properties["paragraph_runs"]
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

    @overload
    def __getitem__(self, index: int) -> ChartPlot: ...

    @overload
    def __getitem__(self, index: slice) -> list[ChartPlot]: ...

    def __getitem__(self, index: int | slice) -> ChartPlot | list[ChartPlot]:
        if isinstance(index, slice):
            return [ChartPlot(self._chart, item) for item in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("chart plot index out of range")
        return ChartPlot(self._chart, index)

    def __iter__(self) -> Iterator[ChartPlot]:
        for index in range(len(self)):
            yield ChartPlot(self._chart, index)

    def __len__(self) -> int:
        if not _chart_payload(self._chart._shape)["series"]:
            return 0
        return _chart_plot_element_count(_shape_chart_root(self._chart._shape))

    @property
    def count(self) -> int:
        return len(self)


class ChartPlot:
    def __init__(self, chart: Chart, index: int) -> None:
        self._chart = chart
        self._index = index

    @property
    def split_type(self) -> str:
        from .chart_gap_facade import get_plot_property

        return get_plot_property(self, "split_type")

    @split_type.setter
    def split_type(self, value: str) -> None:
        from .chart_gap_facade import set_plot_property

        set_plot_property(self, "split_type", value)

    @property
    def split_value(self) -> float:
        from .chart_gap_facade import get_plot_property

        return get_plot_property(self, "split_value")

    @split_value.setter
    def split_value(self, value: float) -> None:
        from .chart_gap_facade import set_plot_property

        set_plot_property(self, "split_value", value)

    @property
    def split_custom_points(self) -> Any:
        from .chart_gap_facade import PieSplitCustomPoints

        return PieSplitCustomPoints(self)

    @property
    def second_plot_size(self) -> int:
        from .chart_gap_facade import get_plot_property

        return get_plot_property(self, "second_plot_size")

    @second_plot_size.setter
    def second_plot_size(self, value: int) -> None:
        from .chart_gap_facade import set_plot_property

        set_plot_property(self, "second_plot_size", value)

    @property
    def chart(self) -> Chart:
        return self._chart

    @property
    def categories(self) -> list[str]:
        return self._chart.categories

    @property
    def series(self) -> ChartSeriesCollection:
        plot = _chart_plot_elements(_shape_chart_root(self._chart._shape))[self._index]
        indexes = {
            int(index.get("val"))
            for series in plot.findall(f"{{{C_NS}}}ser")
            if (index := series.find(f"{{{C_NS}}}idx")) is not None
        }
        return ChartSeriesCollection(
            self._chart,
            [
                payload
                for payload in _chart_payload(self._chart._shape)["series"]
                if int(payload.get("index", 0)) in indexes
            ],
        )

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
        from .chart_gap_facade import get_plot_property, is_of_pie_plot

        if is_of_pie_plot(self):
            return get_plot_property(self, "gap_width")
        return int(_chart_payload(self._chart._shape).get("gap_width", 150))

    @gap_width.setter
    def gap_width(self, value: Any) -> None:
        from .chart_gap_facade import is_of_pie_plot, set_plot_property

        if is_of_pie_plot(self):
            set_plot_property(self, "gap_width", value)
            return
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
    def bubble_scale(self) -> int:
        """Bubble size as a percentage of the default (0-300, default 100).

        Only bubble plots expose this, as in python-pptx.
        """
        return int(self._bubble_payload().get("bubble_scale", 100))

    @bubble_scale.setter
    def bubble_scale(self, value: int | None) -> None:
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, numbers.Integral):
                raise TypeError(f"bubble_scale must be an integer, got {type(value).__name__}")
            if not 0 <= value <= 300:
                raise ValueError(f"bubble_scale must be in range 0 to 300, got {value}")
            value = int(value)
        payload = self._bubble_payload()
        payload["bubble_scale"] = 100 if value is None else value
        self._chart._shape._slide._presentation._queue_chart_plot_property(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            "bubble_scale",
            value,
        )

    @property
    def bubble_size_representation(self) -> str:
        """What a bubble's size value scales: ``"area"`` (default) or ``"width"``."""
        payload = self._bubble_payload("bubble_size_representation")
        if "bubble_size_representation" not in payload:
            payload["bubble_size_representation"] = _chart_bubble_size_representation(
                _first_chart_element(_shape_chart_root(self._chart._shape))
            )
        return str(payload["bubble_size_representation"])

    @bubble_size_representation.setter
    def bubble_size_representation(self, value: Any) -> None:
        payload = self._bubble_payload("bubble_size_representation")
        token = _normalize_choice(
            value,
            tuple(_BUBBLE_SIZE_REPRESENTATION_TOKENS),
            "bubble_size_representation",
        )
        payload["bubble_size_representation"] = token
        self._chart._shape._slide._presentation._queue_chart_plot_property(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            "bubble_size_representation",
            token,
        )

    def _bubble_payload(self, name: str = "bubble_scale") -> dict[str, Any]:
        payload = _chart_payload(self._chart._shape)
        if payload["chart_type"].get("kind") != "bubbleChart":
            raise AttributeError(f"{name} is only available on bubble plots")
        return payload

    @property
    def has_data_labels(self) -> bool:
        return bool(DataLabels(self)._payload()["has_data_labels"])

    @has_data_labels.setter
    def has_data_labels(self, value: Any) -> None:
        has_data_labels = bool(value)
        labels = DataLabels(self)
        if has_data_labels == self.has_data_labels:
            return
        labels._queue({"has_data_labels": has_data_labels})

    @property
    def data_labels(self) -> DataLabels:
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


class Legend(ElementLayout):
    def __init__(self, chart: Chart) -> None:
        self._chart = chart

    @property
    def _layout_chart(self) -> Chart:
        return self._chart

    _layout_key = "legend"

    def _layout_element(self, create: bool) -> ET.Element:
        element = self._legend_element(create=create)
        if create:
            _chart_payload(self._chart._shape)["has_legend"] = True
        return element

    @property
    def entries(self) -> LegendEntryCollection:
        """All data legend entries, including individually hidden entries."""
        return LegendEntryCollection(self)

    @property
    def text_format(self) -> ChartTextFormat:
        """Shared formatting of legend text without overriding generated names."""
        return ChartTextFormat(self._text_body, self._commit_text_format)

    def _text_body(self, create: bool) -> ET.Element | None:
        return chart_text_body(
            self._legend_element(create=create),
            create,
            lambda element, name: next(
                (index for index, child in enumerate(element) if child.tag == f"{{{C_NS}}}extLst"),
                len(element),
            ),
        )

    def _commit_text_format(self, scope: str, delta: dict[str, Any]) -> None:
        payload = _chart_payload(self._chart._shape)
        payload["has_legend"] = True
        self._chart._shape._slide._presentation._queue_chart_legend(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "has_legend": True,
                "text_format_edits": [{"scope": scope, "delta": dict(delta)}],
                "_text_xml": chart_text_xml(self._legend_element(create=False)),
                "_chart_part": str(payload.get("part") or ""),
            },
        )

    @property
    def font(self) -> ChartFont:
        return ChartFont(
            lambda: _chart_legend_text_default_run_properties(self._chart._shape),
            self._set_font_properties,
            lambda: _chart_payload(self._chart._shape).get("legend_font_size"),
            lambda: _chart_payload(self._chart._shape).get("legend_font_fill_type"),
            lambda: _chart_payload(self._chart._shape).get("legend_font_pattern"),
            lambda: _chart_payload(self._chart._shape).get("legend_font_gradient"),
        )

    @property
    def format(self) -> ChartFormat:
        """Fill and outline formatting of the legend's ``c:spPr``."""
        return ChartFormat(
            lambda: self._legend_element(create=False),
            self._queue_format,
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

    @property
    def horz_offset(self) -> float:
        """Legend x offset as a fraction of chart width; 0.0 is automatic layout."""
        return float(_chart_payload(self._chart._shape).get("legend_horz_offset", 0.0))

    @horz_offset.setter
    def horz_offset(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise TypeError(f"horz_offset must be a number, got {type(value).__name__}")
        offset = float(value)
        if not math.isfinite(offset):
            raise ValueError(f"horz_offset must be finite, got {value}")
        payload = _chart_payload(self._chart._shape)
        payload["has_legend"] = True
        payload["legend_horz_offset"] = offset
        self._chart._shape._slide._presentation._queue_chart_legend(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "has_legend": True,
                "horz_offset": offset,
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
        run_properties = _chart_legend_text_default_run_properties(self._chart._shape, create=True)
        set_run_properties_font(
            run_properties,
            {attr.removeprefix("font_"): value for attr, value in properties.items()},
        )
        for attr, value in properties.items():
            payload_attr = prop_map.get(attr)
            if payload_attr is None:
                raise AttributeError(f"unsupported chart legend font property: {attr!r}")
            payload[payload_attr] = value
            queued[payload_attr] = value
        queued["_chart_part"] = str(payload.get("part") or "")
        queued["_text_xml"] = chart_text_xml(self._legend_element(create=False))
        self._chart._shape._slide._presentation._queue_chart_legend(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            queued,
        )

    def _legend_element(self, *, create: bool) -> ET.Element:
        chart = _chart_container_element(_shape_chart_root(self._chart._shape))
        if chart is None:
            raise AttributeError("chart element is unavailable")
        legend = chart.find(f"{{{C_NS}}}legend")
        if legend is not None:
            return legend
        legend = ET.Element(f"{{{C_NS}}}legend")
        if create:
            chart.insert(_chart_legend_insert_index(chart), legend)
        return legend

    def _queue_format(self, properties: dict[str, Any]) -> None:
        payload = _chart_payload(self._chart._shape)
        _set_chart_element_format_properties(
            self._legend_element(create=True),
            properties,
        )
        payload["has_legend"] = True
        self._chart._shape._slide._presentation._queue_chart_legend(
            self._chart._shape._slide._index,
            self._chart._shape._index,
            {
                "has_legend": True,
                "format": dict(properties),
                "_chart_part": str(payload.get("part") or ""),
            },
        )


class LegendEntryCollection(Sequence["LegendEntry"]):
    """Series legends, or category legends for pie/doughnut and varied bars."""

    def __init__(self, legend: Legend) -> None:
        self._legend = legend

    def _texts(self) -> list[str]:
        chart = self._legend._chart
        root = _shape_chart_root(chart._shape)
        area = root.find(f"{{{C_NS}}}chart/{{{C_NS}}}plotArea")
        plots = [] if area is None else [child for child in area if child.findall(f"{{{C_NS}}}ser")]
        if len(plots) == 1:
            plot = plots[0]
            kind = plot.tag.rsplit("}", 1)[-1]
            vary = plot.find(f"{{{C_NS}}}varyColors")
            varies = vary is not None and vary.get("val", "1") not in {"0", "false"}
            if kind in {"pieChart", "pie3DChart", "ofPieChart", "doughnutChart"} or (
                varies and len(chart.series) == 1 and kind in {"barChart", "bar3DChart"}
            ):
                return [
                    category or f"Category {index + 1}"
                    for index, category in enumerate(chart.categories)
                ]
        return [series.name or f"Series {index + 1}" for index, series in enumerate(chart.series)]

    def __len__(self) -> int:
        return len(self._texts())

    def __getitem__(self, index: int | slice) -> LegendEntry | list[LegendEntry]:
        texts = self._texts()
        if isinstance(index, slice):
            return [LegendEntry(self._legend, i) for i in range(*index.indices(len(texts)))]
        texts[index]  # Check the usual Sequence boundary before normalizing.
        return LegendEntry(self._legend, index if index >= 0 else index + len(texts))


class LegendEntry:
    """A zero-based legend entry override (ECMA-376 Part 1 §21.2)."""

    def __init__(self, legend: Legend, index: int) -> None:
        self._legend = legend
        self.index = index

    @property
    def text(self) -> str:
        return self._legend.entries._texts()[self.index]

    def _element(self, *, create: bool = False) -> ET.Element | None:
        # Re-evaluate the collection so stale handles cannot write past its end.
        self._legend.entries._texts()[self.index]
        return legend_entry_element(
            self._legend._legend_element(create=create), self.index, create=create
        )

    @property
    def hidden(self) -> bool:
        entry = self._element()
        delete = None if entry is None else entry.find(f"{{{C_NS}}}delete")
        return delete is not None and delete.get("val", "1") not in {"0", "false"}

    @hidden.setter
    def hidden(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("legend entry hidden must be a boolean")
        entry = self._element(create=True)
        delete = entry.find(f"{{{C_NS}}}delete")
        if delete is None:
            delete = ET.Element(f"{{{C_NS}}}delete")
            entry.insert(1, delete)
        delete.set("val", "1" if value else "0")
        self._queue()

    @property
    def font(self) -> ChartFont:
        return ChartFont(self._run_properties, self._set_font_properties)

    def _run_properties(self) -> ET.Element | None:
        entry = self._element()
        if entry is None:
            return None
        return entry.find(
            f"{{{C_NS}}}txPr/"
            "{http://schemas.openxmlformats.org/drawingml/2006/main}p/"
            "{http://schemas.openxmlformats.org/drawingml/2006/main}pPr/"
            "{http://schemas.openxmlformats.org/drawingml/2006/main}defRPr"
        )

    def _set_font_properties(self, properties: dict[str, Any]) -> None:
        set_legend_entry_font(self._element(create=True), properties)
        self._queue()

    def _queue(self) -> None:
        from .chart_gap_facade import queue_legend_entries

        queue_legend_entries(
            self._legend._chart,
            [
                ET.tostring(entry, encoding="utf-8")
                for entry in self._legend._legend_element(create=True).findall(
                    f"{{{C_NS}}}legendEntry"
                )
            ],
        )


class ChartSeriesCollection(Sequence["ChartSeries"]):
    def __init__(self, chart: Chart, series: list[dict[str, Any]]) -> None:
        self._chart = chart
        self._series = series

    @overload
    def __getitem__(self, index: int) -> ChartSeries: ...

    @overload
    def __getitem__(self, index: slice) -> list[ChartSeries]: ...

    def __getitem__(self, index: int | slice) -> ChartSeries | list[ChartSeries]:
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

    def __iter__(self) -> Iterator[ChartSeries]:
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
    def x_values(self) -> list[float | None]:
        return _chart_numeric_values(self._payload.get("x_values"))

    @property
    def bubble_sizes(self) -> list[float | None]:
        return _chart_numeric_values(self._payload.get("bubble_sizes"))

    @property
    def values(self) -> list[float | None]:
        return _chart_numeric_values(self._payload.get("values"))

    @property
    def smooth(self) -> bool:
        """Whether the series uses smoothed lines; absent means false."""
        return _chart_option_bool(self._option_root(), "smooth", False)

    @property
    def marker(self) -> ChartSeriesMarker:
        """Read the series marker symbol and size."""
        return ChartSeriesMarker(self)

    @property
    def explosion(self) -> int:
        """Pie-slice offset as a percentage; absent means zero."""
        return _chart_option_int(self._option_root(), "explosion", 0)

    def _option_root(self) -> ET.Element:
        # Materialize staged XML and normalize Strict namespaces before series lookup.
        _shape_chart_root(self._chart._shape)
        return _chart_series_element(self._chart._shape, self.index)

    @property
    def invert_if_negative(self) -> bool:
        element = _chart_series_element(self._chart._shape, self.index)
        if element is not None:
            child = element.find(f"{{{C_NS}}}invertIfNegative")
            if child is not None:
                val = child.attrib.get("val")
                return True if val is None else val not in {"0", "false", "False"}
            attr = element.get("invertIfNegative")
            if attr is not None:
                return attr.lower() in {"1", "true", "on"}
            return True
        return bool(self._payload.get("invert_if_negative", True))

    @invert_if_negative.setter
    def invert_if_negative(self, value: bool) -> None:
        bool_val = bool(value)
        self._payload["invert_if_negative"] = bool_val
        self._queue_format({"invert_if_negative": bool_val})

    @property
    def points(self) -> ChartPointCollection:
        return ChartPointCollection(self)

    def set_picture_fill(
        self,
        image: Any,
        picture_type: str = "stretch",
        stack_unit: float = 1.0,
        *,
        point_index: int | None = None,
    ) -> None:
        """Embed a series/point image with stretch, stack or stack-and-scale.

        ``stack_unit`` applies only to stack-and-scale; the other formats
        normalize it to 1 and omit the unused scale child for Office compatibility.
        """
        from .chart_gap_facade import set_picture_fill

        set_picture_fill(self, image, picture_type, stack_unit, point_index)

    def picture_fill(self, *, point_index: int | None = None) -> dict[str, Any] | None:
        """Read the embedded picture mode, scale and relationship identifier."""
        from .chart_gap_facade import picture_fill

        return picture_fill(self, point_index)

    @property
    def format(self) -> ChartFormat:
        return ChartFormat(
            lambda: _chart_series_element(self._chart._shape, self.index),
            self._queue_format,
        )

    @property
    def data_labels(self) -> DataLabels:
        return ChartSeriesDataLabels(self)

    @property
    def trendlines(self) -> Any:
        if self._chart._shape._payload.get("_pending_shape"):
            return _staged_series_trendlines(self)
        return ChartTrendlines(self)

    @property
    def error_bars(self) -> Any:
        from .chart_error_bars_facade import ChartErrorBars

        return ChartErrorBars(self)

    def _queue_format(self, properties: dict[str, Any]) -> None:
        element = _chart_series_element(self._chart._shape, self.index)
        for attr, value in properties.items():
            if attr == "invert_if_negative":
                _set_chart_series_invert_if_negative(element, bool(value))
            else:
                _set_chart_element_format_property(element, attr, value, properties)
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


class ChartSeriesMarker:
    """Read-only ``c:marker`` symbol and size for a chart series."""

    def __init__(self, series: ChartSeries) -> None:
        self._series = series

    @property
    def style(self) -> str:
        """The Open XML marker symbol; absent means ``"none"``."""
        element = _chart_option_element(self._series._option_root(), "marker/symbol")
        return "none" if element is None else element.get("val", "none")

    @property
    def size(self) -> int:
        """Marker diameter in points; the Open XML default is five."""
        return _chart_option_int(self._series._option_root(), "marker/size", 5)


def _is_staged_group_child(shape: Any) -> bool:
    payload = shape._payload
    return bool(payload.get("_pending_group_child") or payload.get("_group_child"))


def _is_staged_top_level_chart(shape: Any) -> bool:
    payload = shape._payload
    return bool(
        payload.get("_pending_shape")
        and payload.get("has_chart")
        and not _is_staged_group_child(shape)
    )


def _check_staged_chart_live(shape: Any) -> None:
    payload = shape._payload
    if payload.get("_deleted") or getattr(shape, "_deleted", False):
        raise ValueError("cannot edit or read trendlines of a deleted shape")
    if payload.get("_stale"):
        raise ValueError("cannot edit or read trendlines of a stale shape")
    slide = getattr(shape, "_slide", None)
    if slide is None:
        raise ValueError("chart shape is not associated with any slide")
    slides = slide._presentation._slides
    if getattr(slide, "_deleted", False) or not any(s is slide for s in slides):
        raise ValueError("cannot edit or read trendlines on a deleted slide")
    if _is_staged_group_child(shape):
        raise NotImplementedError(
            "trendlines on an unsaved chart inside a group are not supported yet; "
            "save the presentation first"
        )
    if not any(candidate is shape for candidate in slide.shapes):
        raise ValueError("cannot edit or read trendlines of a detached shape")


def _staged_chart_source(shape: Any) -> dict[str, Any]:
    """Return the queued chart data whose `_chart_xml` the save will write.

    A staged chart has no chart part until save, so its XML travels through the
    chart data replacement keyed by slide and shape index. An earlier staged
    `replace_data` already queued one; otherwise the chart add supplies the
    exact authored XML and workbook.
    """
    slide = shape._slide
    prs = slide._presentation
    edit = prs._chart_data_edits.get((slide._index, shape._index))
    if edit is not None:
        return edit
    adds = [args for kind, args in prs._shape_adds if kind == "chart" and args[0] == slide._index]
    staged = [c for c in slide.shapes if _is_staged_top_level_chart(c)]
    if len(adds) == len(staged):
        for candidate, (_, chart_type, chart_data, *_) in zip(staged, adds, strict=True):
            if candidate is shape and _chart_data_matches_payload(
                shape._payload["_chart_payload"], chart_data
            ):
                parts = _generated_chart_package_parts(chart_type, chart_data, 0, 0, 0, 0)
                return {
                    **chart_data,
                    "_chart_part": "",
                    "_chart_xml": parts["chart_xml"],
                }
    raise NotImplementedError(
        "cannot resolve the queued chart for this unsaved chart shape; "
        "save the presentation before editing trendlines"
    )


class _StagedSeriesTrendlineState(_SeriesTrendlineState):
    """Trendlines of a chart added in this session and not yet saved.

    Edits rewrite the staged chart XML carried by the chart's queued data
    replacement, which the save resolves to the chart part once it exists.
    """

    def load(self) -> None:
        if self._loaded:
            return
        source = _staged_chart_source(self.shape)
        source_root = ET.fromstring(source["_chart_xml"])
        self.shape._payload.setdefault("_chart_root", source_root)
        super().load()
        if self.family_error is not None:
            return
        # The session root can predate 3-D authoring; judge the family by the
        # XML the save will write.
        try:
            _, plot = _resolve_series_and_plot(source_root, self.series_index)
            _validate_series_plot_family(plot)
        except TrendlineRefusal as exc:
            self.family_error = exc
            self.entries = []
        except IndexError as exc:
            raise TrendlineRefusal(f"malformed chart series XML: {exc}") from exc

    def validate_family(self) -> None:
        _check_staged_chart_live(self.shape)
        self.load()
        if self.family_error is not None:
            raise self.family_error

    def sync(self, shape: Any) -> None:
        _check_staged_chart_live(shape)
        self.shape = shape

    def _queue(self) -> None:
        spec = TrendlineSpec(entries=tuple(self.entries))
        source = _staged_chart_source(self.shape)
        root = ET.fromstring(source["_chart_xml"])
        _set_chart_series_trendlines(root, self.series_index, spec)
        _set_chart_series_trendlines(_shape_chart_root(self.shape), self.series_index, spec)
        _register_chart_namespaces()
        slide = self.shape._slide
        slide._presentation._queue_chart_data_replace(
            slide._index,
            self.shape._index,
            {
                **source,
                "_chart_xml": ET.tostring(root, encoding="utf-8", xml_declaration=True),
            },
        )


class _StagedChartTrendlines(ChartTrendlines):
    def __init__(self, series: ChartSeries, state: _StagedSeriesTrendlineState) -> None:
        self._series = series
        self._state = state


def _staged_series_trendlines(series: ChartSeries) -> ChartTrendlines:
    shape = series._chart._shape
    _check_staged_chart_live(shape)
    states = shape.__dict__.setdefault("_staged_trendline_states", {})
    series_index = int(series.index)
    state = states.get(series_index)
    if state is None:
        state = _StagedSeriesTrendlineState(shape._slide._presentation, "", series_index, shape)
        state.load()
        states[series_index] = state
    else:
        state.sync(shape)
    return _StagedChartTrendlines(series, state)
