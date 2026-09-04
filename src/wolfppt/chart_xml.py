"""Chart XML inspection helpers for the presentation facade."""
# ruff: noqa: F401

from __future__ import annotations

from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .chart_axis_ids import (
    chart_axis_ids_as_openxml_int32 as _chart_axis_ids_as_openxml_int32,
)
from .chart_axis_xml import (
    axis_title_element as _axis_title_element,
    set_chart_axis_property as _set_chart_axis_property,
)
from .chart_axis_payload_xml import (
    chart_axes_payload,
    chart_axis_element,
    chart_axis_payload_from_xml,
    default_chart_axis_payload,
)
from .chart_data_label_xml import (
    chart_data_labels_payload,
    default_chart_data_labels_payload,
    replace_chart_xml_data_labels,
)
from .chart_element_format_xml import (
    set_chart_element_background_fill as _set_chart_element_background_fill,
    set_chart_element_fill_rgb as _set_chart_element_fill_rgb,
    set_chart_element_format_properties as _set_chart_element_format_properties,
    set_chart_element_gradient_fill as _set_chart_element_gradient_fill,
    set_chart_element_line_dash as _set_chart_element_line_dash,
    set_chart_element_line_fill_type as _set_chart_element_line_fill_type,
    set_chart_element_line_pattern_fill as _set_chart_element_line_pattern_fill,
    set_chart_element_line_pattern_rgb as _set_chart_element_line_pattern_rgb,
    set_chart_element_line_rgb as _set_chart_element_line_rgb,
    set_chart_element_line_width as _set_chart_element_line_width,
    set_chart_element_pattern_fill as _set_chart_element_pattern_fill,
    set_chart_element_pattern_rgb as _set_chart_element_pattern_rgb,
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
    chart_legend_include_in_layout,
    chart_legend_position,
    replace_chart_xml_legend,
)
from .chart_type_xml import (
    chart_element_type,
    chart_type_payload_from_value,
    chart_type_value,
)
from .chart_title_text_xml import (
    ensure_title_layout as _ensure_title_layout,
    set_title_auto_size as _set_title_auto_size,
    set_title_body_margin as _set_title_body_margin,
    set_title_paragraph_format as _set_title_paragraph_format,
    set_title_paragraph_runs as _set_title_paragraph_runs,
    set_title_run_font as _set_title_run_font,
    set_title_text as _set_rich_title_text,
    set_title_text_frame_fit as _set_title_text_frame_fit,
    set_title_vertical_anchor as _set_title_vertical_anchor,
    set_title_word_wrap as _set_title_word_wrap,
)
from .chart_xml_utils import (
    C_NS,
    chart_title_element_text,
    child_val,
    optional_int as _optional_int,
    xml_bool_value as _xml_bool_value,
    xml_local_name as _xml_local_name,
)


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
        }
    series = [
        parse_chart_series(ser) for ser in chart_element.findall(f"{{{C_NS}}}ser")
    ]
    return {
        "chart_type": chart_element_type(chart_element),
        "chart_style": chart_style_value(root),
        "series": series,
        "vary_by_categories": chart_vary_by_categories(chart_element),
        "gap_width": chart_gap_width(chart_element),
        "overlap": chart_overlap(chart_element),
        "has_title": chart_has_title(chart_container),
        "title_text": chart_title_text(chart_container),
        "has_legend": chart_has_legend(chart_container),
        "legend_position": chart_legend_position(chart_container),
        "legend_include_in_layout": chart_legend_include_in_layout(chart_container),
        "legend_font_bold": chart_legend_font_bool(chart_container, "b"),
        "legend_font_italic": chart_legend_font_bool(chart_container, "i"),
        "legend_font_underline": chart_legend_font_underline(chart_container),
        "legend_font_size": chart_legend_font_size(chart_container),
        "legend_font_rgb": chart_legend_font_rgb(chart_container),
        "legend_font_name": chart_legend_font_name(chart_container),
        "data_labels": chart_data_labels_payload(chart_element),
        "axes": chart_axes_payload(chart_container),
    }


def first_chart_element(root: ET.Element) -> ET.Element | None:
    plot_area = root.find(f".//{{{C_NS}}}plotArea")
    if plot_area is None:
        return None
    for child in list(plot_area):
        if _xml_local_name(child.tag).endswith("Chart"):
            return child
    return None


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


def chart_vary_by_categories(chart_element: ET.Element | None) -> bool:
    vary_colors = (
        None if chart_element is None else chart_element.find(f"{{{C_NS}}}varyColors")
    )
    if vary_colors is None:
        return True
    return _xml_bool_value(vary_colors.attrib.get("val"), default=True)


def chart_gap_width(chart_element: ET.Element | None) -> int:
    return _optional_int(None if chart_element is None else child_val(chart_element, "gapWidth"), 150)


def chart_overlap(chart_element: ET.Element | None) -> int:
    return _optional_int(None if chart_element is None else child_val(chart_element, "overlap"), 0)


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
    chart_element = first_chart_element(root)
    if chart_element is None:
        raise AttributeError("chart data cache is unavailable")
    if chart_data.get("data_kind") == "bubble":
        return _replace_bubble_chart_root_data(root, chart_element, chart_data)
    if chart_data.get("data_kind") == "xy":
        return _replace_xy_chart_root_data(root, chart_element, chart_data)
    replacement_series = list(chart_data["series"])
    if not replacement_series and not chart_data.get("_preserve_empty_chart_type"):
        _remove_chart_type_element(root, chart_element)
        return _chart_data_xml_bytes(root)
    series_elements = _resize_chart_series(chart_element, len(replacement_series))
    categories = list(chart_data["categories"])
    category_hierarchy = list(chart_data.get("category_hierarchy", []))
    category_kind = str(chart_data.get("category_kind", "string"))
    category_depth = _category_depth(category_hierarchy)
    category_formula = _category_formula(len(categories), category_depth)
    for series_index, (series_element, series_data) in enumerate(
        zip(series_elements, replacement_series, strict=True),
    ):
        _set_chart_series_identity(series_element, series_index)
        value_column = _excel_column_name(category_depth + series_index + 1)
        values = [float(value) for value in series_data["values"]]
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef"),
            [str(series_data["name"])],
            f"Sheet1!${value_column}$1",
        )
        _replace_chart_categories(
            series_element,
            categories,
            category_hierarchy,
            category_formula,
            category_kind=category_kind,
        )
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}val/{{{C_NS}}}numRef"),
            [_chart_number_text(value) for value in values],
            f"Sheet1!${value_column}$2:${value_column}${len(values) + 1}",
        )
    return _chart_data_xml_bytes(root)


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
    return _chart_data_xml_bytes(root)


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
    chart_element = first_chart_element(root)
    if chart_element is None:
        raise AttributeError("chart plot element is unavailable")
    for attr, value in properties.items():
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
        axis_element = chart_axis_element(chart, axis)
        if axis_element is None:
            raise AttributeError("chart axis is unavailable")
        for attr, value in properties.items():
            _set_chart_axis_property(axis_element, attr, value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def parse_chart_series(series_element: ET.Element) -> dict[str, Any]:
    name_values = chart_cache_values(series_element.find(f"{{{C_NS}}}tx"))
    x_values = [
        coerce_chart_number(value)
        for value in chart_cache_values(series_element.find(f"{{{C_NS}}}xVal"))
    ]
    categories = [] if x_values else chart_cache_values(series_element.find(f"{{{C_NS}}}cat"))
    value_container = "yVal" if x_values else "val"
    values = [
        coerce_chart_number(value)
        for value in chart_cache_values(series_element.find(f"{{{C_NS}}}{value_container}"))
    ]
    bubble_sizes = [
        coerce_chart_number(value)
        for value in chart_cache_values(series_element.find(f"{{{C_NS}}}bubbleSize"))
    ]
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


def _chart_level_values(container: ET.Element) -> list[str]:
    points: list[tuple[int, str]] = []
    for point in container.findall(f".//{{{C_NS}}}pt"):
        value_node = point.find(f"{{{C_NS}}}v")
        if value_node is None:
            continue
        raw_index = point.attrib.get("idx", "0")
        points.append((int(raw_index), value_node.text or ""))
    return [value for _, value in sorted(points)]


def coerce_chart_number(value: str) -> float:
    return float(value)


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
    order = {"varyColors": 0, "ser": 1, "dLbls": 2, "gapWidth": 3, "overlap": 4, "axId": 5}
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
    if "paragraph_runs" in edit:
        _set_title_paragraph_runs(title, edit["paragraph_runs"])
    elif "paragraphs" in edit:
        _set_title_paragraph_runs(
            title,
            [
                [str(paragraph)] if str(paragraph) else []
                for paragraph in edit["paragraphs"]
            ],
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
        raise AttributeError("chart data cache is unavailable")
    formula_node = reference.find(f"{{{C_NS}}}f")
    if formula_node is not None:
        formula_node.text = formula
    cache = reference.find(f"{{{C_NS}}}strCache")
    if cache is None:
        cache = reference.find(f"{{{C_NS}}}numCache")
    if cache is None:
        raise AttributeError("chart data cache is unavailable")
    point_count = cache.find(f"{{{C_NS}}}ptCount")
    if point_count is None:
        point_count = ET.Element(f"{{{C_NS}}}ptCount")
        format_code = cache.find(f"{{{C_NS}}}formatCode")
        insert_at = 1 if format_code is not None else 0
        cache.insert(insert_at, point_count)
    point_count.set("val", str(len(values)))
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
