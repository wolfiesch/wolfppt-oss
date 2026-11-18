"""Chart XML inspection helpers for the presentation facade."""
# ruff: noqa: F401

from __future__ import annotations

import math
from collections.abc import Sequence
from contextlib import suppress
from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .chart_axis_ids import (
    chart_axis_ids_as_openxml_int32 as _chart_axis_ids_as_openxml_int32,
)
from .chart_axis_payload_xml import (
    chart_axes_payload,
    chart_axis_element,
    chart_axis_payload_from_xml,
    default_chart_axis_payload,
)
from .chart_axis_xml import (
    axis_title_element as _axis_title_element,
)
from .chart_axis_xml import (
    set_chart_axis_property as _set_chart_axis_property,
)
from .chart_data_label_xml import (
    chart_data_labels_payload,
    default_chart_data_labels_payload,
    replace_chart_xml_data_labels,
)
from .chart_element_format_xml import (
    set_chart_element_background_fill as _set_chart_element_background_fill,
)
from .chart_element_format_xml import (
    set_chart_element_fill_rgb as _set_chart_element_fill_rgb,
)
from .chart_element_format_xml import (
    set_chart_element_format_properties as _set_chart_element_format_properties,
)
from .chart_element_format_xml import (
    set_chart_element_gradient_fill as _set_chart_element_gradient_fill,
)
from .chart_element_format_xml import (
    set_chart_element_line_dash as _set_chart_element_line_dash,
)
from .chart_element_format_xml import (
    set_chart_element_line_fill_type as _set_chart_element_line_fill_type,
)
from .chart_element_format_xml import (
    set_chart_element_line_pattern_fill as _set_chart_element_line_pattern_fill,
)
from .chart_element_format_xml import (
    set_chart_element_line_pattern_rgb as _set_chart_element_line_pattern_rgb,
)
from .chart_element_format_xml import (
    set_chart_element_line_rgb as _set_chart_element_line_rgb,
)
from .chart_element_format_xml import (
    set_chart_element_line_width as _set_chart_element_line_width,
)
from .chart_element_format_xml import (
    set_chart_element_pattern_fill as _set_chart_element_pattern_fill,
)
from .chart_element_format_xml import (
    set_chart_element_pattern_rgb as _set_chart_element_pattern_rgb,
)
from .chart_element_format_xml import (
    set_chart_element_solid_fill as _set_chart_element_solid_fill,
)
from .chart_font_xml import replace_chart_xml_font
from .chart_legend_xml import (
    chart_has_legend,
    chart_legend_font_bool,
    chart_legend_font_name,
    chart_legend_font_rgb,
    chart_legend_font_size,
    chart_legend_font_underline,
    chart_legend_horz_offset,
    chart_legend_include_in_layout,
    chart_legend_position,
    replace_chart_xml_legend,
)
from .chart_title_text_xml import _title_insert_index
from .chart_title_text_xml import (
    ensure_title_layout as _ensure_title_layout,
)
from .chart_title_text_xml import (
    set_title_auto_size as _set_title_auto_size,
)
from .chart_title_text_xml import (
    set_title_body_margin as _set_title_body_margin,
)
from .chart_title_text_xml import (
    set_title_paragraph_format as _set_title_paragraph_format,
)
from .chart_title_text_xml import (
    set_title_paragraph_runs as _set_title_paragraph_runs,
)
from .chart_title_text_xml import (
    set_title_run_font as _set_title_run_font,
)
from .chart_title_text_xml import (
    set_title_text as _set_rich_title_text,
)
from .chart_title_text_xml import (
    set_title_text_frame_fit as _set_title_text_frame_fit,
)
from .chart_title_text_xml import (
    set_title_vertical_anchor as _set_title_vertical_anchor,
)
from .chart_title_text_xml import (
    set_title_word_wrap as _set_title_word_wrap,
)
from .chart_type_xml import (
    chart_element_type,
    chart_type_payload_from_value,
    chart_type_value,
)
from .chart_xml_utils import (
    C_NS,
    chart_title_element_text,
    child_val,
)
from .chart_xml_utils import (
    optional_int as _optional_int,
)
from .chart_xml_utils import (
    xml_bool_value as _xml_bool_value,
)
from .chart_xml_utils import (
    xml_local_name as _xml_local_name,
)


class ChartDataRefusal(ValueError):
    """Chart data cannot be read or replaced within the supported structure and limits."""


_MAX_CHART_NUMERIC_CACHE_POINTS = 1_048_576


class _NumericCacheBudget:
    """Bound dense value/axis cache expansion across all series of one chart."""

    def __init__(self) -> None:
        self.remaining = _MAX_CHART_NUMERIC_CACHE_POINTS

    def consume(self, count: int) -> None:
        if count > self.remaining:
            raise ChartDataRefusal(
                f"chart numeric caches exceed the {_MAX_CHART_NUMERIC_CACHE_POINTS}-point "
                "expansion limit"
            )
        self.remaining -= count


def _validate_chart_data_layout(root: ET.Element, chart_data: dict[str, Any]) -> None:
    plots = chart_plot_elements(root)
    if not plots:
        raise ChartDataRefusal("missing chart plotArea plot or chart data cache")
    kind = chart_data.get("data_kind", "category")
    supported = (
        {"bubbleChart"}
        if kind == "bubble"
        else {"scatterChart"}
        if kind == "xy"
        else {
            "barChart",
            "bar3DChart",
            "lineChart",
            "line3DChart",
            "areaChart",
            "area3DChart",
            "pieChart",
            "pie3DChart",
            "doughnutChart",
            "ofPieChart",
            "radarChart",
            "stockChart",
            "surfaceChart",
            "surface3DChart",
        }
    )
    for plot in plots:
        tag = _xml_local_name(plot.tag)
        if tag not in supported:
            raise ChartDataRefusal(f"{tag}: unsupported {kind} chart data replacement")
        series = plot.findall(f"{{{C_NS}}}ser")
        if not series and chart_data["series"]:
            raise ChartDataRefusal(f"{tag}: missing series template")
        containers = (
            ("xVal", "yVal", "bubbleSize")
            if kind == "bubble"
            else (("xVal", "yVal") if kind == "xy" else ("val",))
        )
        for element in series:
            name_reference = element.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef")
            if name_reference is not None and name_reference.find(f"{{{C_NS}}}strCache") is None:
                raise ChartDataRefusal(f"{tag}: missing tx/strRef/strCache")
            for container in containers:
                if element.find(
                    f"{{{C_NS}}}{container}/{{{C_NS}}}numRef/{{{C_NS}}}numCache"
                ) is None and not (
                    kind == "category"
                    and element.find(f"{{{C_NS}}}{container}/{{{C_NS}}}numLit") is not None
                ):
                    raise ChartDataRefusal(f"{tag}: missing {container}/numRef/numCache")
            if kind == "category" and element.find(f"{{{C_NS}}}cat") is None:
                raise ChartDataRefusal(f"{tag}: missing category cache")


def _category_value_reference(series: ET.Element) -> ET.Element | None:
    reference = series.find(f"{{{C_NS}}}val/{{{C_NS}}}numRef")
    return reference if reference is not None else series.find(f"{{{C_NS}}}val/{{{C_NS}}}numLit")


def parse_chart_xml(chart_xml: bytes) -> dict[str, Any]:
    root = ET.fromstring(chart_xml)
    return parse_chart_root(root)


def parse_chart_root(root: ET.Element) -> dict[str, Any]:
    chart_element = first_chart_element(root)
    chart_container = chart_container_element(root)
    if chart_element is None:
        return {
            "chart_type": "unknown",
            "chart_style": chart_style_value(root),
            "series": [],
            "vary_by_categories": True,
            "gap_width": 150,
            "overlap": 0,
            "has_title": False,
            "title_text": "",
            "has_legend": False,
            "legend_position": "r",
            "legend_include_in_layout": True,
            "axes": {},
            "view_3d": None,
        }
    point_budget = _NumericCacheBudget()
    series = [
        parse_chart_series(ser, _point_budget=point_budget) for ser in chart_series_elements(root)
    ]
    return {
        "chart_type": chart_element_type(chart_element),
        "chart_style": chart_style_value(root),
        "series": series,
        "vary_by_categories": chart_vary_by_categories(chart_element),
        "gap_width": chart_gap_width(chart_element),
        "overlap": chart_overlap(chart_element),
        "bubble_scale": chart_bubble_scale(chart_element),
        "has_title": chart_has_title(chart_container),
        "title_text": chart_title_text(chart_container),
        "has_legend": chart_has_legend(chart_container),
        "legend_position": chart_legend_position(chart_container),
        "legend_include_in_layout": chart_legend_include_in_layout(chart_container),
        "legend_horz_offset": chart_legend_horz_offset(chart_container),
        "legend_font_bold": chart_legend_font_bool(chart_container, "b"),
        "legend_font_italic": chart_legend_font_bool(chart_container, "i"),
        "legend_font_underline": chart_legend_font_underline(chart_container),
        "legend_font_size": chart_legend_font_size(chart_container),
        "legend_font_rgb": chart_legend_font_rgb(chart_container),
        "legend_font_name": chart_legend_font_name(chart_container),
        "data_labels": chart_data_labels_payload(chart_element),
        "axes": chart_axes_payload(chart_container),
        "view_3d": chart_view_3d(chart_container),
    }


def chart_plot_elements(root: ET.Element) -> list[ET.Element]:
    """Return every plot group of the chart's plot area in document order."""
    plot_area = root.find(f".//{{{C_NS}}}plotArea")
    if plot_area is None:
        return []
    return [child for child in list(plot_area) if _xml_local_name(child.tag).endswith("Chart")]


def chart_series_elements(root: ET.Element) -> list[ET.Element]:
    """Return every series of the chart, spanning all of its plot groups.

    A combination chart owns several plot groups (for example a column range and
    a secondary-axis line range), so a single plot group only ever exposes the
    series that are bound to it.  Series come back in plot order, which is the
    order their ``c:idx`` values follow.
    """
    return [
        series for plot in chart_plot_elements(root) for series in plot.findall(f"{{{C_NS}}}ser")
    ]


def first_chart_element(root: ET.Element) -> ET.Element | None:
    plot_elements = chart_plot_elements(root)
    return plot_elements[0] if plot_elements else None


def chart_plot_element_count(root: ET.Element) -> int:
    """Return how many plot groups the chart's plot area holds."""
    return len(chart_plot_elements(root))


def chart_container_element(root: ET.Element) -> ET.Element | None:
    if root.tag == f"{{{C_NS}}}chart":
        return root
    return root.find(f"{{{C_NS}}}chart")


def chart_has_title(chart: ET.Element | None) -> bool:
    if chart is None:
        return False
    title = chart.find(f"{{{C_NS}}}title")
    auto_title = chart.find(f"{{{C_NS}}}autoTitleDeleted")
    return title is not None and (auto_title is None or auto_title.attrib.get("val") != "1")


def chart_title_text(chart: ET.Element | None) -> str:
    if not chart_has_title(chart) or chart is None:
        return ""
    return chart_title_element_text(chart.find(f"{{{C_NS}}}title"))


def chart_view_3d(chart: ET.Element | None) -> dict[str, str] | None:
    """Return the authored DrawingML ``view3D`` camera parameters, if present."""
    if chart is None:
        return None
    view = chart.find(f"{{{C_NS}}}view3D")
    if view is None:
        return None
    return {
        _xml_local_name(child.tag): child.get("val", "")
        for child in view
        if _xml_local_name(child.tag) in {"rotX", "rotY", "rAngAx", "perspective"}
    }


def chart_vary_by_categories(chart_element: ET.Element | None) -> bool:
    vary_colors = None if chart_element is None else chart_element.find(f"{{{C_NS}}}varyColors")
    if vary_colors is None:
        return True
    return _xml_bool_value(vary_colors.attrib.get("val"), default=True)


def chart_gap_width(chart_element: ET.Element | None) -> int:
    return _optional_int(
        None if chart_element is None else child_val(chart_element, "gapWidth"), 150
    )


def chart_overlap(chart_element: ET.Element | None) -> int:
    return _optional_int(None if chart_element is None else child_val(chart_element, "overlap"), 0)


def chart_bubble_scale(chart_element: ET.Element | None) -> int | None:
    """Return the bubble size percentage of a bubble plot, ``None`` otherwise.

    ``c:bubbleScale`` defaults to 100 when the element or its ``val`` is absent,
    and python-pptx tolerates an ``ST_BubbleScale`` percent literal (``"150%"``).
    """
    if chart_element is None or _xml_local_name(chart_element.tag) != "bubbleChart":
        return None
    raw = child_val(chart_element, "bubbleScale")
    return _optional_int(None if raw is None else raw.replace("%", ""), 100)


#: ``c:dispBlanksAs`` tokens: leave a gap, connect across (line charts), plot as zero.
DISPLAY_BLANKS_AS_VALUES = ("gap", "span", "zero")

#: Public bubble size representation names and their ``ST_SizeRepresents`` tokens.
BUBBLE_SIZE_REPRESENTATION_TOKENS = {"area": "area", "width": "w"}


def chart_display_blanks_as(root: ET.Element) -> str:
    """Return how the chart plots empty cells: ``gap``, ``span`` or ``zero``.

    A chart without ``c:dispBlanksAs`` reads as ``gap``, the Office default; an
    element without ``val`` takes the schema default ``zero``.
    """
    chart = chart_container_element(root)
    element = None if chart is None else chart.find(f"{{{C_NS}}}dispBlanksAs")
    if element is None:
        return "gap"
    return element.get("val", "zero")


def set_chart_display_blanks_as(root: ET.Element, value: str) -> None:
    """Write ``c:dispBlanksAs`` in its schema position inside ``c:chart``."""
    if value not in DISPLAY_BLANKS_AS_VALUES:
        raise ValueError(f"unsupported display_blanks_as value: {value!r}")
    chart = chart_container_element(root)
    if chart is None:
        raise AttributeError("chart element is unavailable")
    element = chart.find(f"{{{C_NS}}}dispBlanksAs")
    if element is None:
        element = ET.Element(f"{{{C_NS}}}dispBlanksAs")
        insert_at = len(chart)
        for index, child in enumerate(list(chart)):
            if child.tag in {f"{{{C_NS}}}showDLblsOverMax", f"{{{C_NS}}}extLst"}:
                insert_at = index
                break
        chart.insert(insert_at, element)
    element.set("val", value)


def chart_bubble_size_representation(chart_element: ET.Element | None) -> str | None:
    """Return ``area`` or ``width`` for a bubble plot, ``None`` for other plots.

    ``c:sizeRepresents`` defaults to ``area`` when the element or its ``val`` is
    absent.
    """
    if chart_element is None or _xml_local_name(chart_element.tag) != "bubbleChart":
        return None
    raw = child_val(chart_element, "sizeRepresents") or "area"
    for name, token in BUBBLE_SIZE_REPRESENTATION_TOKENS.items():
        if raw == token:
            return name
    raise ValueError(f"unsupported bubble sizeRepresents value: {raw!r}")


def chart_style_value(root: ET.Element) -> int | None:
    style = root.find(f"{{{C_NS}}}style")
    if style is None:
        return None
    value = style.attrib.get("val")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def replace_chart_xml_data(chart_xml: bytes, chart_data: dict[str, Any]) -> bytes:
    root = ET.fromstring(chart_xml)
    return replace_chart_root_data(root, chart_data)


def replace_chart_root_data(root: ET.Element, chart_data: dict[str, Any]) -> bytes:
    _validate_chart_data_layout(root, chart_data)
    chart_element = first_chart_element(root)
    if chart_element is None:
        raise AttributeError("chart data cache is unavailable")
    if chart_data.get("data_kind") == "bubble":
        return _replace_bubble_chart_root_data(root, chart_element, chart_data)
    if chart_data.get("data_kind") == "xy":
        return _replace_xy_chart_root_data(root, chart_element, chart_data)
    if _xml_local_name(chart_element.tag) == "stockChart":
        _validate_stock_chart_data(chart_element, chart_data)
    return _replace_category_chart_root_data(root, chart_element, chart_data)


def _replace_category_chart_root_data(
    root: ET.Element, chart_element: ET.Element, chart_data: dict[str, Any]
) -> bytes:
    replacement_series = list(chart_data["series"])
    if not replacement_series and not chart_data.get("_preserve_empty_chart_type"):
        _remove_chart_type_element(root, chart_element)
        return _chart_data_xml_bytes(root)
    existing_series = chart_element.findall(f"{{{C_NS}}}ser")
    reset_identity = len(existing_series) != len(replacement_series) or len(
        {child_val(series, "idx") for series in existing_series}
    ) != len(existing_series)
    series_elements = _resize_chart_series(chart_element, len(replacement_series))
    categories = list(chart_data["categories"])
    category_hierarchy = list(chart_data.get("category_hierarchy", []))
    category_kind = str(chart_data.get("category_kind", "string"))
    category_depth = _category_depth(category_hierarchy)
    category_formula = _category_formula(len(categories), category_depth)
    for series_index, (series_element, series_data) in enumerate(
        zip(series_elements, replacement_series, strict=True),
    ):
        if reset_identity:
            _set_chart_series_identity(series_element, series_index)
        else:
            _set_child_val(series_element, "order", str(series_index), 1)
        value_column = _excel_column_name(category_depth + series_index + 1)
        values = [float(value) for value in series_data["values"]]
        name_reference = series_element.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef")
        name = str(series_data["name"])
        if name_reference is not None:
            _replace_chart_cache(name_reference, [name], f"Sheet1!${value_column}$1")
        elif name != "".join(chart_cache_values(series_element.find(f"{{{C_NS}}}tx"))):
            tx = series_element.find(f"{{{C_NS}}}tx")
            if tx is None:
                tx = ET.Element(f"{{{C_NS}}}tx")
                series_element.insert(2, tx)
            for child in list(tx):
                tx.remove(child)
            name_reference = ET.SubElement(tx, f"{{{C_NS}}}strRef")
            ET.SubElement(name_reference, f"{{{C_NS}}}f")
            ET.SubElement(name_reference, f"{{{C_NS}}}strCache")
            _replace_chart_cache(name_reference, [name], f"Sheet1!${value_column}$1")
        _replace_chart_categories(
            series_element,
            categories,
            category_hierarchy,
            category_formula,
            category_kind=category_kind,
        )
        _replace_chart_cache(
            _category_value_reference(series_element),
            [_chart_number_text(value) for value in values],
            f"Sheet1!${value_column}$2:${value_column}${len(values) + 1}",
        )
    return _chart_data_xml_bytes(root)


def _validate_stock_chart_data(chart_element: ET.Element, chart_data: dict[str, Any]) -> None:
    has_open = chart_element.find(f"{{{C_NS}}}upDownBars") is not None
    roles = ("open", "high", "low", "close") if has_open else ("high", "low", "close")
    if chart_element.find(f"{{{C_NS}}}hiLowLines") is None:
        raise ValueError("stock chart must declare high-low lines")
    categories = list(chart_data.get("categories") or [])
    series = list(chart_data.get("series") or [])
    if not categories:
        raise ValueError("stock chart data contains no categories")
    if len(series) != len(roles):
        raise ValueError(
            f"stock chart requires exactly {len(roles)} series ordered " + ", ".join(roles)
        )
    values_by_role: dict[str, list[float]] = {}
    for role, series_data in zip(roles, series, strict=True):
        values = list(series_data.get("values") or [])
        if len(values) != len(categories):
            raise ValueError(f"stock chart {role} series value count must match categories")
        converted: list[float] = []
        for point_index, value in enumerate(values, start=1):
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"stock chart {role} series point {point_index} is not numeric"
                ) from exc
            if not math.isfinite(number):
                raise ValueError(f"stock chart {role} series point {point_index} is not finite")
            converted.append(number)
        values_by_role[role] = converted
    for point_index in range(len(categories)):
        high = values_by_role["high"][point_index]
        low = values_by_role["low"][point_index]
        if high < low:
            raise ValueError(f"stock chart category {point_index + 1} high value is below low")
        for role in ("open", "close"):
            if role not in values_by_role:
                continue
            value = values_by_role[role][point_index]
            if value < low or value > high:
                raise ValueError(
                    f"stock chart category {point_index + 1} {role} value is outside "
                    "the high-low range"
                )


def replace_chart_root_data_preserving_series_layout(
    root: ET.Element, chart_data: dict[str, Any]
) -> bytes:
    """Replace category-chart caches without moving series between plot elements.

    Combo charts bind series and axes per plot.  A refresh that changes only the
    source-bound data rectangle must retain that structure rather than treating
    every series as belonging to the first plot.
    """
    _validate_chart_data_layout(root, chart_data)
    replacement_series = list(chart_data["series"])
    plot_area = root.find(f".//{{{C_NS}}}plotArea")
    if plot_area is None:
        raise AttributeError("chart data cache is unavailable")
    chart_element = first_chart_element(root)
    if chart_element is not None and _xml_local_name(chart_element.tag) == "stockChart":
        _validate_stock_chart_data(chart_element, chart_data)
    series_elements = chart_series_elements(root)
    if len(series_elements) != len(replacement_series):
        raise ValueError("chart series layout does not match replacement data")
    categories = list(chart_data["categories"])
    category_hierarchy = list(chart_data.get("category_hierarchy", []))
    category_kind = str(chart_data.get("category_kind", "string"))
    category_depth = _category_depth(category_hierarchy)
    category_formula = _category_formula(len(categories), category_depth)
    for series_index, (series_element, series_data) in enumerate(
        zip(series_elements, replacement_series, strict=True)
    ):
        values = [float(value) for value in series_data["values"]]
        if len(values) != len(categories):
            raise ValueError("series value count must match categories")
        _replace_chart_categories(
            series_element,
            categories,
            category_hierarchy,
            category_formula,
            category_kind=category_kind,
        )
        value_column = _excel_column_name(category_depth + series_index + 1)
        _replace_chart_cache(
            _category_value_reference(series_element),
            [_chart_number_text(value) for value in values],
            f"Sheet1!${value_column}$2:${value_column}${len(values) + 1}",
        )
    return _chart_data_xml_bytes(root)


def reorder_chart_root_series(
    root: ET.Element, current_keys: Sequence[str], replacement_keys: Sequence[str]
) -> None:
    """Move existing series elements into caller-approved business-key order."""
    if len(current_keys) != len(set(current_keys)):
        raise ValueError("current business-series keys must be unique")
    if len(replacement_keys) != len(set(replacement_keys)):
        raise ValueError("replacement business-series keys must be unique")
    if set(current_keys) != set(replacement_keys):
        raise ValueError("business-series keys must select the existing series exactly")
    chart_element = first_chart_element(root)
    if chart_element is None:
        raise AttributeError("chart data cache is unavailable")
    series_elements = chart_element.findall(f"{{{C_NS}}}ser")
    if len(series_elements) != len(current_keys):
        raise ValueError("business-series keys do not match chart series")
    first_series_index = list(chart_element).index(series_elements[0])
    by_key = dict(zip(current_keys, series_elements, strict=True))
    for series_element in series_elements:
        chart_element.remove(series_element)
    for offset, key in enumerate(replacement_keys):
        chart_element.insert(first_series_index + offset, by_key[key])


def reorder_chart_root_series_with_template(
    root: ET.Element,
    current_keys: Sequence[str],
    replacement_keys: Sequence[str],
    addition_template_key: str | None,
) -> None:
    """Rebuild the series sequence, cloning a caller-approved business style."""
    if len(current_keys) != len(set(current_keys)):
        raise ValueError("current business-series keys must be unique")
    if len(replacement_keys) != len(set(replacement_keys)):
        raise ValueError("replacement business-series keys must be unique")
    additions = set(replacement_keys) - set(current_keys)
    if additions and addition_template_key not in current_keys:
        raise ValueError("new business series require a source style template key")
    chart_element = first_chart_element(root)
    if chart_element is None:
        raise AttributeError("chart data cache is unavailable")
    series_elements = chart_element.findall(f"{{{C_NS}}}ser")
    if len(series_elements) != len(current_keys):
        raise ValueError("business-series keys do not match chart series")
    first_series_index = list(chart_element).index(series_elements[0])
    by_key = dict(zip(current_keys, series_elements, strict=True))
    for series_element in series_elements:
        chart_element.remove(series_element)
    for offset, key in enumerate(replacement_keys):
        element = by_key.get(key)
        if element is None:
            assert addition_template_key is not None
            element = deepcopy(by_key[addition_template_key])
        chart_element.insert(first_series_index + offset, element)


def _replace_xy_chart_root_data(
    root: ET.Element,
    chart_element: ET.Element,
    chart_data: dict[str, Any],
) -> bytes:
    replacement_series = list(chart_data["series"])
    if not replacement_series and not chart_data.get("_preserve_empty_chart_type"):
        _remove_chart_type_element(root, chart_element)
        return _chart_data_xml_bytes(root)
    series_elements = _resize_chart_series(chart_element, len(replacement_series))
    for series_index, (series_element, series_data) in enumerate(
        zip(series_elements, replacement_series, strict=True),
    ):
        _set_chart_series_identity(series_element, series_index)
        x_values = [float(value) for value in series_data["x_values"]]
        y_values = [float(value) for value in series_data["values"]]
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef"),
            [str(series_data["name"])],
            str(series_data["name_formula"]),
        )
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}xVal/{{{C_NS}}}numRef"),
            [_chart_number_text(value) for value in x_values],
            str(series_data["x_formula"]),
        )
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}yVal/{{{C_NS}}}numRef"),
            [_chart_number_text(value) for value in y_values],
            str(series_data["y_formula"]),
        )
        _set_series_cache_number_format(series_element, series_data)
    return _chart_data_xml_bytes(root)


def _replace_bubble_chart_root_data(
    root: ET.Element,
    chart_element: ET.Element,
    chart_data: dict[str, Any],
) -> bytes:
    replacement_series = list(chart_data["series"])
    if not replacement_series and not chart_data.get("_preserve_empty_chart_type"):
        _remove_chart_type_element(root, chart_element)
        return _chart_data_xml_bytes(root)
    series_elements = _resize_chart_series(chart_element, len(replacement_series))
    for series_index, (series_element, series_data) in enumerate(
        zip(series_elements, replacement_series, strict=True),
    ):
        _set_chart_series_identity(series_element, series_index)
        x_values = [float(value) for value in series_data["x_values"]]
        y_values = [float(value) for value in series_data["values"]]
        bubble_sizes = [float(value) for value in series_data["bubble_sizes"]]
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef"),
            [str(series_data["name"])],
            str(series_data["name_formula"]),
        )
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}xVal/{{{C_NS}}}numRef"),
            [_chart_number_text(value) for value in x_values],
            str(series_data["x_formula"]),
        )
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}yVal/{{{C_NS}}}numRef"),
            [_chart_number_text(value) for value in y_values],
            str(series_data["y_formula"]),
        )
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}bubbleSize/{{{C_NS}}}numRef"),
            [_chart_number_text(value) for value in bubble_sizes],
            str(series_data["bubble_size_formula"]),
        )
        _set_series_cache_number_format(series_element, series_data)
    return _chart_data_xml_bytes(root)


def _set_series_cache_number_format(
    series_element: ET.Element, series_data: dict[str, Any]
) -> None:
    """Write the series format into every xVal/yVal/bubbleSize cache.

    python-pptx rewrites these caches with the resolved series format on both
    add_chart and replace_data. Payloads without a format keep the cache's.
    """
    number_format = series_data.get("number_format")
    if number_format is None:
        return
    for tag in ("xVal", "yVal", "bubbleSize"):
        cache = series_element.find(f"{{{C_NS}}}{tag}/{{{C_NS}}}numRef/{{{C_NS}}}numCache")
        if cache is None:
            continue
        format_code = cache.find(f"{{{C_NS}}}formatCode")
        if format_code is None:
            format_code = ET.Element(f"{{{C_NS}}}formatCode")
            cache.insert(0, format_code)
        format_code.text = str(number_format)


def _chart_data_xml_bytes(root: ET.Element) -> bytes:
    return _chart_axis_ids_as_openxml_int32(
        ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )


def _remove_chart_type_element(root: ET.Element, chart_element: ET.Element) -> None:
    plot_area = root.find(f".//{{{C_NS}}}plotArea")
    if plot_area is None:
        raise AttributeError("chart plot area is unavailable")
    plot_area.remove(chart_element)


def replace_chart_xml_title(chart_xml: bytes, title: dict[str, Any]) -> bytes:
    root = ET.fromstring(chart_xml)
    return replace_chart_root_title(root, title)


def replace_chart_root_title(root: ET.Element, title: dict[str, Any]) -> bytes:
    chart = chart_container_element(root)
    if chart is None:
        raise AttributeError("chart element is unavailable")
    has_title = bool(title.get("has_title"))
    if not has_title:
        title_element = chart.find(f"{{{C_NS}}}title")
        if title_element is not None:
            chart.remove(title_element)
        _set_chart_auto_title_deleted(chart, "1")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    title_element = _chart_title_element(chart)
    _set_chart_title_rich_text(title_element, title)
    if "format" in title and isinstance(title["format"], dict):
        _set_chart_element_format_properties(title_element, title["format"])
    _set_chart_auto_title_deleted(chart, "0")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def replace_chart_xml_style(chart_xml: bytes, style: int | None) -> bytes:
    root = ET.fromstring(chart_xml)
    style_element = root.find(f"{{{C_NS}}}style")
    if style is None:
        if style_element is not None:
            root.remove(style_element)
            return ET.tostring(root, encoding="utf-8", xml_declaration=True)
        return chart_xml
    if style_element is None:
        style_element = ET.Element(f"{{{C_NS}}}style")
        root.insert(_chart_style_insert_index(root), style_element)
    style_element.set("val", str(int(style)))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def replace_chart_xml_plot_properties(
    chart_xml: bytes,
    properties: dict[str, Any],
) -> bytes:
    root = ET.fromstring(chart_xml)
    from .chart_gap_xml import apply_plot_options, set_plot_area_layout

    chart_element = first_chart_element(root)
    if chart_element is None:
        raise AttributeError("chart plot element is unavailable")
    for attr, value in properties.items():
        if attr.startswith("_"):
            continue
        if attr == "plot_options":
            apply_plot_options(root, value)
        elif attr == "display_blanks_as":
            set_chart_display_blanks_as(root, value)
        elif attr == "plot_area_layout":
            set_plot_area_layout(root, value)
        elif attr == "gap_width" and chart_element.tag == f"{{{C_NS}}}ofPieChart":
            from .chart_gap_xml import set_plot_option

            set_plot_option(chart_element, attr, value)
        else:
            _set_chart_plot_property(chart_element, attr, value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def replace_chart_xml_axis_title(
    chart_xml: bytes,
    axis: str,
    title: dict[str, Any],
) -> bytes:
    return replace_chart_xml_axis_title_groups(chart_xml, [(axis, title)])


def replace_chart_xml_axis_title_groups(
    chart_xml: bytes,
    axis_title_edits: list[tuple[str, dict[str, Any]]],
) -> bytes:
    root = ET.fromstring(chart_xml)
    chart = chart_container_element(root)
    if chart is None:
        raise AttributeError("chart element is unavailable")
    changed = False
    for axis, title in axis_title_edits:
        axis_element = chart_axis_element(chart, axis)
        if axis_element is None:
            raise AttributeError("chart axis is unavailable")
        if title.get("has_title") is False:
            title_element = axis_element.find(f"{{{C_NS}}}title")
            if title_element is not None:
                axis_element.remove(title_element)
                changed = True
            continue
        title_element = _axis_title_element(axis_element)
        _set_chart_title_rich_text(title_element, title)
        if "format" in title and isinstance(title["format"], dict):
            _set_chart_element_format_properties(title_element, title["format"])
        changed = True
    if not changed:
        return chart_xml
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def replace_chart_xml_axis_properties(
    chart_xml: bytes,
    axis: str,
    properties: dict[str, Any],
) -> bytes:
    return replace_chart_xml_axis_property_groups(chart_xml, [(axis, properties)])


def replace_chart_xml_axis_property_groups(
    chart_xml: bytes,
    axis_property_edits: list[tuple[str, dict[str, Any]]],
) -> bytes:
    root = ET.fromstring(chart_xml)
    chart = chart_container_element(root)
    if chart is None:
        raise AttributeError("chart element is unavailable")
    for axis, properties in axis_property_edits:
        axis_element = (
            _ensure_secondary_value_axis(chart)
            if axis == "val2"
            else chart_axis_element(chart, axis)
        )
        if axis_element is None:
            raise AttributeError("chart axis is unavailable")
        for attr, value in properties.items():
            if attr != "attach_secondary":
                _set_chart_axis_property(axis_element, attr, value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _ensure_secondary_value_axis(chart: ET.Element) -> ET.Element:
    """Return the right value axis, cloning the primary axis when first attached."""
    plot_area = chart.find(f"{{{C_NS}}}plotArea")
    if plot_area is None:
        raise AttributeError("chart plot area is unavailable")
    value_axes = plot_area.findall(f"{{{C_NS}}}valAx")
    if len(value_axes) > 1:
        return value_axes[1]
    if not value_axes:
        raise AttributeError("chart value axis is unavailable")
    category_axis = chart_axis_element(chart, "cat")
    if category_axis is None:
        raise AttributeError("chart category axis is unavailable")
    identifiers = [
        int(value)
        for axis in plot_area
        if _xml_local_name(axis.tag) in {"valAx", "catAx", "dateAx"}
        if (identifier := axis.find(f"{{{C_NS}}}axId")) is not None
        if (value := identifier.get("val")) is not None and value.lstrip("-").isdigit()
    ]
    secondary = deepcopy(value_axes[0])
    identifier = secondary.find(f"{{{C_NS}}}axId")
    category_identifier = category_axis.find(f"{{{C_NS}}}axId")
    cross_axis = secondary.find(f"{{{C_NS}}}crossAx")
    if identifier is None or category_identifier is None or cross_axis is None:
        raise AttributeError("chart axis relationship is unavailable")
    identifier.set("val", str(max(identifiers, default=0) + 1))
    position = secondary.find(f"{{{C_NS}}}axPos")
    if position is None:
        position = ET.SubElement(secondary, f"{{{C_NS}}}axPos")
    position.set("val", "r")
    cross_axis.set("val", category_identifier.get("val", ""))
    plot_area.append(secondary)
    return secondary


def parse_chart_series(
    series_element: ET.Element, *, _point_budget: _NumericCacheBudget | None = None
) -> dict[str, Any]:
    point_budget = _NumericCacheBudget() if _point_budget is None else _point_budget
    name_values = chart_cache_values(series_element.find(f"{{{C_NS}}}tx"))
    x_container = series_element.find(f"{{{C_NS}}}xVal")
    x_values = _chart_numeric_cache_values(x_container, point_budget)
    categories = (
        [] if x_container is not None else chart_cache_values(series_element.find(f"{{{C_NS}}}cat"))
    )
    value_container = "yVal" if x_container is not None else "val"
    values = _chart_numeric_cache_values(
        series_element.find(f"{{{C_NS}}}{value_container}"), point_budget
    )
    bubble_sizes = _chart_numeric_cache_values(
        series_element.find(f"{{{C_NS}}}bubbleSize"), point_budget
    )
    index = child_val(series_element, "idx")
    invert_negative = series_element.find(f"{{{C_NS}}}invertIfNegative")
    return {
        "index": 0 if index is None else int(index),
        "name": name_values[0] if name_values else "",
        "categories": categories,
        "x_values": x_values,
        "values": values,
        "bubble_sizes": bubble_sizes,
        "invert_if_negative": _xml_bool_value(
            None if invert_negative is None else invert_negative.attrib.get("val"),
            default=True,
        ),
        "data_labels": chart_data_labels_payload(series_element),
    }


def chart_cache_values(container: ET.Element | None) -> list[str]:
    if container is None:
        return []
    multi_level_cache = container.find(f".//{{{C_NS}}}multiLvlStrCache")
    if multi_level_cache is not None:
        leaf_level = multi_level_cache.find(f"{{{C_NS}}}lvl")
        return [] if leaf_level is None else _chart_level_values(leaf_level)
    return _chart_level_values(container)


def _chart_cache_unsigned_int(value: str | None, field: str) -> int:
    try:
        number = -1 if value is None else int(value)
    except ValueError as exc:
        raise ChartDataRefusal(
            f"chart numeric cache {field} must be a nonnegative integer"
        ) from exc
    if number < 0:
        raise ChartDataRefusal(f"chart numeric cache {field} must be a nonnegative integer")
    return number


def _chart_numeric_cache_values(
    container: ET.Element | None, point_budget: _NumericCacheBudget
) -> list[float | None]:
    """Retain value/axis cache positions; categories keep their separate representation."""
    if container is None:
        return []
    cache = (
        container
        if container.tag in {f"{{{C_NS}}}numCache", f"{{{C_NS}}}numLit"}
        else container.find(f".//{{{C_NS}}}numCache")
    )
    if cache is None:
        cache = container.find(f"{{{C_NS}}}numLit")
    if cache is None:
        return []
    count_node = cache.find(f"{{{C_NS}}}ptCount")
    count = (
        None
        if count_node is None
        else _chart_cache_unsigned_int(count_node.get("val"), "point count")
    )
    if count is not None and count > point_budget.remaining:
        point_budget.consume(count)
    points: dict[int, float | None] = {}
    for point in cache.findall(f"{{{C_NS}}}pt"):
        index = _chart_cache_unsigned_int(point.get("idx"), "point index")
        if index >= point_budget.remaining:
            raise ChartDataRefusal("chart numeric cache point index exceeds the expansion limit")
        if count is not None and index >= count:
            raise ChartDataRefusal(
                "chart numeric cache point index exceeds its declared point count"
            )
        if index in points:
            raise ChartDataRefusal("chart numeric cache contains a duplicate point index")
        value = point.find(f"{{{C_NS}}}v")
        points[index] = None if value is None else coerce_chart_number(value.text or "")
    length = max(points, default=-1) + 1 if count is None else count
    point_budget.consume(length)
    values: list[float | None] = [None] * length
    for index, value in points.items():
        values[index] = value
    return values


def _chart_level_values(container: ET.Element) -> list[str]:
    points: list[tuple[int, str]] = []
    for point in container.findall(f".//{{{C_NS}}}pt"):
        value_node = point.find(f"{{{C_NS}}}v")
        if value_node is None:
            continue
        raw_index = point.attrib.get("idx", "0")
        points.append((int(raw_index), value_node.text or ""))
    return [value for _, value in sorted(points)]


def coerce_chart_number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        # Excel may cache a blank or an error token for a numeric point.
        return None


def _chart_style_insert_index(root: ET.Element) -> int:
    for index, child in enumerate(list(root)):
        if child.tag == f"{{{C_NS}}}chart":
            return index
    return len(root)


def _set_chart_plot_property(
    chart_element: ET.Element,
    attr: str,
    value: Any,
) -> None:
    if attr == "vary_by_categories":
        _set_chart_vary_by_categories(chart_element, bool(value))
        return
    if attr == "gap_width":
        _set_chart_plot_int_child(chart_element, "gapWidth", value, default=150)
        return
    if attr == "overlap":
        _set_chart_plot_int_child(chart_element, "overlap", value, default=0)
        return
    if attr == "bubble_scale":
        _set_chart_bubble_scale(chart_element, value)
        return
    if attr == "bubble_size_representation":
        _set_chart_bubble_size_representation(chart_element, value)
        return
    raise ValueError(f"unsupported chart plot property: {attr!r}")


def _set_chart_vary_by_categories(
    chart_element: ET.Element,
    value: bool,
) -> None:
    vary_colors = chart_element.find(f"{{{C_NS}}}varyColors")
    if vary_colors is None:
        vary_colors = ET.Element(f"{{{C_NS}}}varyColors")
        chart_element.insert(
            _chart_plot_insert_index(chart_element, "varyColors"),
            vary_colors,
        )
    if value:
        vary_colors.attrib.pop("val", None)
    else:
        vary_colors.set("val", "0")


_BUBBLE_SCALE_SUCCESSORS = frozenset(
    f"{{{C_NS}}}{name}" for name in ("showNegBubbles", "sizeRepresents", "axId", "extLst")
)


def _set_chart_bubble_scale(chart_element: ET.Element, value: int | None) -> None:
    """Replace ``c:bubbleScale``; ``None`` removes it so the default 100 applies."""
    if _xml_local_name(chart_element.tag) != "bubbleChart":
        raise ValueError("bubble_scale applies only to bubble chart plots")
    existing = chart_element.find(f"{{{C_NS}}}bubbleScale")
    if existing is not None:
        chart_element.remove(existing)
    if value is None:
        return
    insert_at = len(chart_element)
    for index, child in enumerate(list(chart_element)):
        if child.tag in _BUBBLE_SCALE_SUCCESSORS:
            insert_at = index
            break
    chart_element.insert(
        insert_at,
        ET.Element(f"{{{C_NS}}}bubbleScale", {"val": str(int(value))}),
    )


def _set_chart_bubble_size_representation(chart_element: ET.Element, value: str) -> None:
    """Write ``c:sizeRepresents`` (``area`` or ``w``) after ``c:showNegBubbles``."""
    if _xml_local_name(chart_element.tag) != "bubbleChart":
        raise ValueError("bubble_size_representation applies only to bubble chart plots")
    token = BUBBLE_SIZE_REPRESENTATION_TOKENS.get(value)
    if token is None:
        raise ValueError(f"unsupported bubble size representation: {value!r}")
    element = chart_element.find(f"{{{C_NS}}}sizeRepresents")
    if element is None:
        element = ET.Element(f"{{{C_NS}}}sizeRepresents")
        insert_at = len(chart_element)
        for index, child in enumerate(list(chart_element)):
            if child.tag in {f"{{{C_NS}}}axId", f"{{{C_NS}}}extLst"}:
                insert_at = index
                break
        chart_element.insert(insert_at, element)
    element.set("val", token)


def _set_chart_plot_int_child(
    chart_element: ET.Element,
    local_name: str,
    value: Any,
    *,
    default: int,
) -> None:
    child = chart_element.find(f"{{{C_NS}}}{local_name}")
    normalized = int(value)
    if normalized == default:
        if child is not None:
            chart_element.remove(child)
        return
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        chart_element.insert(_chart_plot_insert_index(chart_element, local_name), child)
    child.set("val", str(normalized))


def _chart_plot_insert_index(chart_element: ET.Element, local_name: str) -> int:
    order = {
        "varyColors": 0,
        "ser": 1,
        "dLbls": 2,
        "gapWidth": 3,
        "overlap": 4,
        "axId": 5,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(chart_element)
    for index, child in enumerate(list(chart_element)):
        child_order = order.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(chart_element)


def _chart_title_element(chart: ET.Element) -> ET.Element:
    title = chart.find(f"{{{C_NS}}}title")
    if title is not None:
        return title
    title = ET.Element(f"{{{C_NS}}}title")
    insert_at = len(chart)
    for index, child in enumerate(list(chart)):
        if child.tag in {f"{{{C_NS}}}autoTitleDeleted", f"{{{C_NS}}}plotArea"}:
            insert_at = index
            break
    chart.insert(insert_at, title)
    return title


def _set_chart_title_text(title: ET.Element, text: str) -> None:
    _set_rich_title_text(title, text)


def _set_chart_title_rich_text(title: ET.Element, edit: dict[str, Any]) -> None:
    if "_text_xml" in edit:
        from .chart_font_format_facade import replace_chart_text_xml

        replace_chart_text_xml(title, edit["_text_xml"], _title_insert_index)
        _ensure_title_layout(title)
        return
    if "paragraph_runs" in edit:
        _set_title_paragraph_runs(title, edit["paragraph_runs"], preserve_runs=True)
    elif "paragraphs" in edit:
        _set_title_paragraph_runs(
            title,
            [[str(paragraph)] if str(paragraph) else [] for paragraph in edit["paragraphs"]],
        )
    elif "text" in edit:
        _set_chart_title_text(title, str(edit.get("text") or ""))
    for paragraph_format in edit.get("paragraph_formats", []):
        _set_title_paragraph_format(
            title,
            int(paragraph_format["paragraph_index"]),
            dict(paragraph_format["properties"]),
        )
    for run_format in edit.get("run_formats", []):
        _set_title_run_font(
            title,
            int(run_format["paragraph_index"]),
            int(run_format["run_index"]),
            dict(run_format["properties"]),
        )
    if "margin_left" in edit:
        _set_title_body_margin(title, "lIns", int(edit["margin_left"]))
    if "margin_right" in edit:
        _set_title_body_margin(title, "rIns", int(edit["margin_right"]))
    if "margin_top" in edit:
        _set_title_body_margin(title, "tIns", int(edit["margin_top"]))
    if "margin_bottom" in edit:
        _set_title_body_margin(title, "bIns", int(edit["margin_bottom"]))
    if "word_wrap" in edit:
        _set_title_word_wrap(title, edit["word_wrap"])
    if "vertical_anchor" in edit:
        _set_title_vertical_anchor(
            title,
            None if edit["vertical_anchor"] is None else str(edit["vertical_anchor"]),
        )
    if "auto_size" in edit:
        _set_title_auto_size(
            title,
            None if edit["auto_size"] is None else str(edit["auto_size"]),
        )
    if "fit" in edit:
        _set_title_text_frame_fit(title, dict(edit["fit"]))
    _ensure_title_layout(title)


def _set_chart_auto_title_deleted(chart: ET.Element, value: str) -> None:
    auto_title = chart.find(f"{{{C_NS}}}autoTitleDeleted")
    if auto_title is None:
        auto_title = ET.Element(f"{{{C_NS}}}autoTitleDeleted")
        title = chart.find(f"{{{C_NS}}}title")
        if title is not None:
            insert_at = list(chart).index(title) + 1
        else:
            insert_at = len(chart)
            for index, child in enumerate(list(chart)):
                if child.tag == f"{{{C_NS}}}plotArea":
                    insert_at = index
                    break
        chart.insert(insert_at, auto_title)
    auto_title.set("val", value)


def _resize_chart_series(chart_element: ET.Element, target_count: int) -> list[ET.Element]:
    series_elements = chart_element.findall(f"{{{C_NS}}}ser")
    if target_count < 0:
        raise ValueError("chart data series count must not be negative")
    if not series_elements:
        raise AttributeError("chart series template is unavailable")
    while len(series_elements) > target_count:
        chart_element.remove(series_elements.pop())
    if target_count == 0:
        return []
    if len(series_elements) < target_count:
        children = list(chart_element)
        insert_at = children.index(series_elements[-1]) + 1
        while len(series_elements) < target_count:
            clone = deepcopy(series_elements[-1])
            chart_element.insert(insert_at, clone)
            series_elements.append(clone)
            insert_at += 1
    return series_elements


def _set_chart_series_identity(series_element: ET.Element, series_index: int) -> None:
    _set_child_val(series_element, "idx", str(series_index), 0)
    _set_child_val(series_element, "order", str(series_index), 1)


def _set_child_val(
    parent: ET.Element,
    local_name: str,
    value: str,
    insert_at: int,
) -> None:
    child = parent.find(f"{{{C_NS}}}{local_name}")
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        parent.insert(insert_at, child)
    child.set("val", value)


def _replace_chart_categories(
    series_element: ET.Element,
    categories: list[str],
    category_hierarchy: list[list[str]],
    formula: str,
    *,
    category_kind: str = "string",
) -> None:
    cat = series_element.find(f"{{{C_NS}}}cat")
    if cat is None:
        raise AttributeError("chart data cache is unavailable")
    # Keep authored numeric and literal categories when a point-only refresh
    # supplies the same labels, including numeric categories read as strings.
    existing = chart_cache_values(cat)
    if not category_hierarchy and existing == categories:
        return
    if not category_hierarchy:
        reference_name = "numRef" if category_kind == "date" else "strRef"
        cache_name = "numCache" if category_kind == "date" else "strCache"
        reference = cat.find(f"{{{C_NS}}}{reference_name}")
        if reference is None:
            for child in list(cat):
                cat.remove(child)
            reference = ET.SubElement(cat, f"{{{C_NS}}}{reference_name}")
            ET.SubElement(reference, f"{{{C_NS}}}f")
            cache = ET.SubElement(reference, f"{{{C_NS}}}{cache_name}")
            if category_kind == "date":
                format_code = ET.SubElement(cache, f"{{{C_NS}}}formatCode")
                format_code.text = r"yyyy\-mm\-dd"
        elif category_kind == "date":
            cache = reference.find(f"{{{C_NS}}}numCache")
            if cache is not None and cache.find(f"{{{C_NS}}}formatCode") is None:
                format_code = ET.Element(f"{{{C_NS}}}formatCode")
                format_code.text = r"yyyy\-mm\-dd"
                cache.insert(0, format_code)
        _replace_chart_cache(reference, categories, formula)
        return

    for child in list(cat):
        cat.remove(child)
    reference = ET.SubElement(cat, f"{{{C_NS}}}multiLvlStrRef")
    formula_node = ET.SubElement(reference, f"{{{C_NS}}}f")
    formula_node.text = formula
    cache = ET.SubElement(reference, f"{{{C_NS}}}multiLvlStrCache")
    _append_multi_level_category_cache(cache, category_hierarchy)


def _append_multi_level_category_cache(
    cache: ET.Element,
    category_hierarchy: list[list[str]],
) -> None:
    paths = _padded_category_paths(category_hierarchy)
    ET.SubElement(cache, f"{{{C_NS}}}ptCount", {"val": str(len(paths))})
    if not paths:
        return
    depth = len(paths[0])
    for level_index in range(depth - 1, -1, -1):
        level = ET.SubElement(cache, f"{{{C_NS}}}lvl")
        previous_path: list[str] | None = None
        for point_index, path in enumerate(paths):
            if (
                previous_path is not None
                and previous_path[: level_index + 1] == path[: level_index + 1]
            ):
                continue
            previous_path = path
            point = ET.SubElement(level, f"{{{C_NS}}}pt", {"idx": str(point_index)})
            value_node = ET.SubElement(point, f"{{{C_NS}}}v")
            value_node.text = path[level_index]


def _padded_category_paths(category_hierarchy: list[list[str]]) -> list[list[str]]:
    depth = _category_depth(category_hierarchy)
    return [[*([""] * (depth - len(path))), *path] for path in category_hierarchy]


def _category_depth(category_hierarchy: list[list[str]]) -> int:
    return max((len(path) for path in category_hierarchy), default=1)


def _category_formula(category_count: int, category_depth: int) -> str:
    final_column = _excel_column_name(category_depth)
    return f"Sheet1!$A$2:${final_column}${category_count + 1}"


def _replace_chart_cache(
    reference: ET.Element | None,
    values: list[str],
    formula: str,
) -> None:
    if reference is None:
        raise ChartDataRefusal("missing chart data cache reference")
    cache = reference.find(f"{{{C_NS}}}strCache")
    if cache is None:
        cache = reference.find(f"{{{C_NS}}}numCache")
    if reference.tag in {f"{{{C_NS}}}numLit", f"{{{C_NS}}}strLit"}:
        cache = reference
    if cache is None:
        raise ChartDataRefusal("missing chart strCache or numCache")
    existing = chart_cache_values(reference)
    numeric = cache.tag in {f"{{{C_NS}}}numCache", f"{{{C_NS}}}numLit"}
    unchanged = existing == values
    if numeric and not unchanged:
        with suppress(ValueError):
            unchanged = [float(value) for value in existing] == [float(value) for value in values]
    formula_node = reference.find(f"{{{C_NS}}}f")
    if formula_node is not None:
        formula_node.text = formula
    point_count = cache.find(f"{{{C_NS}}}ptCount")
    if unchanged and point_count is not None and point_count.get("val") == str(len(values)):
        return
    if point_count is None:
        point_count = ET.Element(f"{{{C_NS}}}ptCount")
        format_code = cache.find(f"{{{C_NS}}}formatCode")
        insert_at = 1 if format_code is not None else 0
        cache.insert(insert_at, point_count)
    point_count.set("val", str(len(values)))
    points = cache.findall(f"{{{C_NS}}}pt")
    if len(points) == len(values) and all(
        point.get("idx") == str(index) and point.find(f"{{{C_NS}}}v") is not None
        for index, point in enumerate(points)
    ):
        for point, value in zip(points, values, strict=True):
            value_node = point.find(f"{{{C_NS}}}v")
            old = value_node.text or ""
            unchanged = old == value
            if numeric and not unchanged:
                with suppress(ValueError):
                    unchanged = float(old) == float(value)
            if unchanged:
                continue
            value_node.text = value
        return
    for point in list(cache.findall(f"{{{C_NS}}}pt")):
        cache.remove(point)
    for index, value in enumerate(values):
        point = ET.Element(f"{{{C_NS}}}pt", {"idx": str(index)})
        value_node = ET.SubElement(point, f"{{{C_NS}}}v")
        value_node.text = value
        cache.append(point)


def _chart_number_text(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value)


def _excel_column_name(index: int) -> str:
    if index < 1:
        raise ValueError("Excel column index must be at least 1")
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name
