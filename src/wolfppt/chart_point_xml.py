"""Point-level chart data-label XML writers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_data_label_text_xml import (
    data_label_insert_index as _data_label_insert_index,
)
from .chart_data_label_text_xml import (
    insert_chart_data_label_paragraph_line_break as _insert_chart_data_label_paragraph_line_break,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_auto_size as _set_point_data_label_auto_size,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_body_margin as _set_point_data_label_body_margin,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_bool as _set_chart_data_label_font_bool,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_fill_type as _set_chart_data_label_font_fill_type,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_gradient as _set_chart_data_label_font_gradient,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_language_id as _set_chart_data_label_font_language_id,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_name as _set_chart_data_label_font_name,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_pattern as _set_chart_data_label_font_pattern,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_pattern_rgb as _set_chart_data_label_font_pattern_rgb,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_rgb as _set_chart_data_label_font_rgb,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_size as _set_chart_data_label_font_size,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_font_underline as _set_chart_data_label_font_underline,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_number_format as _set_chart_data_label_number_format,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_number_format_source_linked as _set_chart_data_label_number_format_source_linked,  # noqa: E501
)
from .chart_data_label_text_xml import (
    set_chart_data_label_paragraph_format as _set_chart_data_label_paragraph_format,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_paragraph_runs as _set_chart_data_label_paragraph_runs,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_paragraphs as _set_chart_data_label_paragraphs,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_position as _set_chart_data_label_position,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_run_formats as _set_chart_data_label_run_formats,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_text as _set_chart_data_label_text,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_text_frame as _set_chart_data_label_text_frame,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_text_frame_fit as _set_chart_data_label_text_frame_fit,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_text_properties as _set_chart_data_label_text_properties,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_vertical_anchor as _set_point_data_label_vertical_anchor,
)
from .chart_data_label_text_xml import (
    set_chart_data_label_word_wrap as _set_point_data_label_word_wrap,
)
from .chart_element_format_xml import (
    CHART_FORMAT_PROPERTIES as _CHART_FORMAT_PROPERTIES,
)
from .chart_element_format_xml import (
    set_chart_element_format_properties_in_order as _set_chart_element_format_properties_in_order,
)
from .chart_element_format_xml import (
    set_chart_element_format_property as _set_chart_element_format_property,
)
from .xml_helpers import xml_local_name as _xml_local_name

C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"

_SERIES_CHILD_ORDER = [
    "idx",
    "order",
    "tx",
    "spPr",
    "invertIfNegative",
    "pictureOptions",
    "marker",
    "dPt",
    "dLbls",
    "trendline",
    "errBars",
    "cat",
    "xVal",
    "val",
    "yVal",
    "bubbleSize",
    "bubble3D",
    "smooth",
    "shape",
    "extLst",
]
_SERIES_CHILD_INDEX = {local_name: index for index, local_name in enumerate(_SERIES_CHILD_ORDER)}
#: Point scalar properties and the ``c:dPt`` children that carry them.
CHART_POINT_SCALAR_PROPERTIES = {
    "invert_if_negative": "invertIfNegative",
    "explosion": "explosion",
}


def set_chart_point_data_label_properties(
    chart_element: ET.Element,
    point_label_edits: Any,
) -> None:
    for point_label_edit in point_label_edits:
        series_element = _chart_series_element(
            chart_element,
            int(point_label_edit["series_index"]),
        )
        data_labels = _chart_series_data_labels_element(series_element)
        point_label = _chart_point_data_label_element(
            data_labels,
            int(point_label_edit["point_index"]),
        )
        properties = point_label_edit.get("properties", {})
        if "_label_xml" in properties:
            final_label = ET.fromstring(properties["_label_xml"])
            if final_label.tag != f"{{{C_NS}}}dLbl":
                raise ValueError("point label snapshot must be c:dLbl")
            point_label.attrib.clear()
            point_label.attrib.update(final_label.attrib)
            point_label[:] = list(final_label)
            continue
        run_formats = []
        paragraph_formats = []
        paragraph_line_breaks = []
        for attr, value in point_label_edit.get("properties", {}).items():
            if attr == "position":
                _set_chart_data_label_text_properties(point_label)
                _set_chart_data_label_position(point_label, value)
                continue
            if attr == "has_text_frame":
                _set_chart_data_label_text_frame(point_label, bool(value))
                continue
            if attr == "text":
                _set_chart_data_label_text(point_label, str(value))
                continue
            if attr == "paragraphs":
                _set_chart_data_label_paragraphs(
                    point_label,
                    [str(paragraph) for paragraph in value] or [""],
                )
                continue
            if attr == "paragraph_runs":
                _set_chart_data_label_paragraph_runs(
                    point_label,
                    [[str(run) for run in runs] for runs in value] or [[]],
                )
                continue
            if attr == "run_formats":
                run_formats.extend(value)
                continue
            if attr == "paragraph_formats":
                paragraph_formats.extend(value)
                continue
            if attr == "paragraph_line_breaks":
                paragraph_line_breaks.extend(value)
                continue
            if attr == "font_size":
                _set_chart_data_label_font_size(point_label, value)
                continue
            if attr == "font_bold":
                _set_chart_data_label_font_bool(point_label, "b", value)
                continue
            if attr == "font_italic":
                _set_chart_data_label_font_bool(point_label, "i", value)
                continue
            if attr == "font_underline":
                _set_chart_data_label_font_underline(point_label, value)
                continue
            if attr == "font_fill_type":
                _set_chart_data_label_font_fill_type(point_label, str(value))
                continue
            if attr == "font_pattern":
                _set_chart_data_label_font_pattern(point_label, value)
                continue
            if attr == "font_pattern_fore_rgb":
                _set_chart_data_label_font_pattern_rgb(point_label, "fgClr", value)
                continue
            if attr == "font_pattern_back_rgb":
                _set_chart_data_label_font_pattern_rgb(point_label, "bgClr", value)
                continue
            if attr == "font_gradient":
                _set_chart_data_label_font_gradient(point_label, value)
                continue
            if attr == "font_rgb":
                _set_chart_data_label_font_rgb(
                    point_label,
                    None if value is None else str(value),
                )
                continue
            if attr == "font_name":
                _set_chart_data_label_font_name(
                    point_label,
                    None if value is None else str(value),
                )
                continue
            if attr == "font_language_id":
                _set_chart_data_label_font_language_id(
                    point_label,
                    None if value is None else str(value),
                )
                continue
            if attr == "margin_left":
                _set_point_data_label_body_margin(point_label, "lIns", int(value))
                continue
            if attr == "margin_right":
                _set_point_data_label_body_margin(point_label, "rIns", int(value))
                continue
            if attr == "margin_top":
                _set_point_data_label_body_margin(point_label, "tIns", int(value))
                continue
            if attr == "margin_bottom":
                _set_point_data_label_body_margin(point_label, "bIns", int(value))
                continue
            if attr == "word_wrap":
                _set_point_data_label_word_wrap(point_label, value)
                continue
            if attr == "vertical_anchor":
                _set_point_data_label_vertical_anchor(
                    point_label,
                    None if value is None else str(value),
                )
                continue
            if attr == "auto_size":
                _set_point_data_label_auto_size(
                    point_label,
                    None if value is None else str(value),
                )
                continue
            if attr == "fit":
                _set_chart_data_label_text_frame_fit(point_label, dict(value))
                continue
            raise ValueError(f"unsupported chart point data-label property: {attr!r}")
        if run_formats:
            _set_chart_data_label_run_formats(point_label, run_formats)
        for line_break in paragraph_line_breaks:
            _insert_chart_data_label_paragraph_line_break(
                point_label,
                int(line_break["paragraph_index"]),
                int(line_break["run_slot"]),
            )
        for paragraph_format in paragraph_formats:
            _set_chart_data_label_paragraph_format(
                point_label,
                int(paragraph_format["paragraph_index"]),
                dict(paragraph_format.get("properties", {})),
            )


def set_chart_point_format_properties(
    chart_element: ET.Element,
    point_format_edits: Any,
) -> None:
    for point_format_edit in point_format_edits:
        series_element = _chart_series_element(
            chart_element,
            int(point_format_edit["series_index"]),
        )
        point = _chart_point_element(
            series_element,
            int(point_format_edit["point_index"]),
        )
        properties = point_format_edit.get("properties", {})
        # One queued edit merges scalar and format properties for the same point.
        _set_chart_element_format_properties_in_order(
            point,
            {
                attr: value
                for attr, value in properties.items()
                if attr not in CHART_POINT_SCALAR_PROPERTIES
            },
            "point",
        )
        for attr, value in properties.items():
            if attr in CHART_POINT_SCALAR_PROPERTIES:
                set_chart_point_scalar(point, attr, value)


def set_chart_point_scalar(point: ET.Element, attr: str, value: Any) -> None:
    """Write ``invert_if_negative`` (bool) or ``explosion`` (percent) on ``c:dPt``.

    ``None`` removes the point override so the series value applies again.
    """
    local_name = CHART_POINT_SCALAR_PROPERTIES[attr]
    child = point.find(f"{{{C_NS}}}{local_name}")
    if value is None:
        if child is not None:
            point.remove(child)
        return
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        point.insert(_dpt_child_insert_index(point, local_name), child)
    if attr == "invert_if_negative":
        child.set("val", "1" if value else "0")
    else:
        child.set("val", str(int(value)))


def set_chart_point_marker_format_properties(
    chart_element: ET.Element,
    point_marker_format_edits: Any,
) -> None:
    for point_marker_format_edit in point_marker_format_edits:
        series_element = _chart_series_element(
            chart_element,
            int(point_marker_format_edit["series_index"]),
        )
        point = _chart_point_element(
            series_element,
            int(point_marker_format_edit["point_index"]),
        )
        marker = _chart_point_marker_element(point)
        properties = point_marker_format_edit.get("properties", {})
        for attr, value in properties.items():
            if attr == "marker_style":
                _set_marker_style(marker, None if value is None else str(value))
            elif attr == "marker_size":
                _set_marker_size(marker, None if value is None else int(value))
            elif attr in _CHART_FORMAT_PROPERTIES:
                _set_chart_element_format_property(marker, attr, value, properties)
            else:
                raise ValueError(f"unsupported chart marker format property: {attr!r}")


def set_chart_series_format_properties(
    chart_element: ET.Element,
    series_format_edits: Any,
) -> None:
    for series_format_edit in series_format_edits:
        series_element = _chart_series_element(
            chart_element,
            int(series_format_edit["series_index"]),
        )
        properties = series_format_edit.get("properties", {})
        for attr, value in properties.items():
            if attr == "invert_if_negative":
                _set_chart_series_invert_if_negative(series_element, bool(value))
            elif attr in _CHART_FORMAT_PROPERTIES:
                _set_chart_element_format_property(series_element, attr, value, properties)
            else:
                raise ValueError(f"unsupported chart series format property: {attr!r}")


def set_chart_series_data_label_properties(
    chart_element: ET.Element,
    series_data_label_edits: Any,
) -> None:
    for series_data_label_edit in series_data_label_edits:
        series_element = _chart_series_element(
            chart_element,
            int(series_data_label_edit["series_index"]),
        )
        data_labels = _chart_series_data_labels_element(series_element)
        properties = series_data_label_edit.get("properties", {})
        for attr, value in series_data_label_edit.get("properties", {}).items():
            if attr == "has_data_labels":
                if value is False:
                    existing = series_element.find(f"{{{C_NS}}}dLbls")
                    if existing is not None:
                        series_element.remove(existing)
                continue
            if attr in {
                "text_format_edits",
                "_text_xml",
                "separator",
                "show_bubble_size",
                "show_leader_lines",
            }:
                from .chart_data_label_xml import _set_chart_data_label_property

                _set_chart_data_label_property(data_labels, attr, value)
                continue
            if attr == "show_value":
                _set_chart_data_label_bool_child(data_labels, "showVal", bool(value))
                continue
            if attr == "show_category_name":
                _set_chart_data_label_bool_child(
                    data_labels,
                    "showCatName",
                    bool(value),
                )
                continue
            if attr == "show_series_name":
                _set_chart_data_label_bool_child(
                    data_labels,
                    "showSerName",
                    bool(value),
                )
                continue
            if attr == "show_percentage":
                _set_chart_data_label_bool_child(
                    data_labels,
                    "showPercent",
                    bool(value),
                )
                continue
            if attr == "show_legend_key":
                _set_chart_data_label_bool_child(
                    data_labels,
                    "showLegendKey",
                    bool(value),
                )
                continue
            if attr == "position":
                _set_chart_data_label_position(data_labels, value)
                continue
            if attr == "number_format":
                _set_chart_data_label_number_format(data_labels, str(value))
                continue
            if attr == "number_format_is_linked":
                _set_chart_data_label_number_format_source_linked(
                    data_labels,
                    bool(value),
                )
                continue
            if attr == "font_size":
                _set_chart_data_label_font_size(data_labels, value)
                continue
            if attr == "font_bold":
                _set_chart_data_label_font_bool(data_labels, "b", value)
                continue
            if attr == "font_italic":
                _set_chart_data_label_font_bool(data_labels, "i", value)
                continue
            if attr == "font_underline":
                _set_chart_data_label_font_underline(data_labels, value)
                continue
            if attr == "font_fill_type":
                _set_chart_data_label_font_fill_type(data_labels, str(value))
                continue
            if attr == "font_pattern":
                _set_chart_data_label_font_pattern(data_labels, value)
                continue
            if attr == "font_pattern_fore_rgb":
                _set_chart_data_label_font_pattern_rgb(data_labels, "fgClr", value)
                continue
            if attr == "font_pattern_back_rgb":
                _set_chart_data_label_font_pattern_rgb(data_labels, "bgClr", value)
                continue
            if attr == "font_gradient":
                _set_chart_data_label_font_gradient(data_labels, value)
                continue
            if attr == "font_rgb":
                _set_chart_data_label_font_rgb(
                    data_labels,
                    None if value is None else str(value),
                )
                continue
            if attr == "font_name":
                _set_chart_data_label_font_name(
                    data_labels,
                    None if value is None else str(value),
                )
                continue
            if attr == "font_language_id":
                _set_chart_data_label_font_language_id(
                    data_labels,
                    None if value is None else str(value),
                )
                continue
            raise ValueError(f"unsupported chart series data-label property: {attr!r}")
        if "_text_xml" in properties:
            from .chart_font_format_facade import replace_chart_text_xml

            replace_chart_text_xml(data_labels, properties["_text_xml"], _data_label_insert_index)


def _chart_series_data_labels_element(series_element: ET.Element) -> ET.Element:
    data_labels = series_element.find(f"{{{C_NS}}}dLbls")
    if data_labels is not None:
        return data_labels
    data_labels = ET.Element(f"{{{C_NS}}}dLbls")
    series_element.insert(
        _chart_series_data_labels_insert_index(series_element),
        data_labels,
    )
    return data_labels


def _chart_point_data_label_element(
    data_labels: ET.Element,
    point_index: int,
) -> ET.Element:
    for fallback_index, point_label in enumerate(data_labels.findall(f"{{{C_NS}}}dLbl")):
        raw_index = point_label.find(f"{{{C_NS}}}idx")
        if (
            raw_index is not None
            and int(raw_index.attrib.get("val", fallback_index)) == point_index
        ):
            return point_label
        if raw_index is None and fallback_index == point_index:
            return point_label
    point_label = ET.Element(f"{{{C_NS}}}dLbl")
    ET.SubElement(point_label, f"{{{C_NS}}}idx", {"val": str(point_index)})
    _set_chart_data_label_bool_child(point_label, "showLegendKey", False)
    _set_chart_data_label_bool_child(point_label, "showVal", True)
    _set_chart_data_label_bool_child(point_label, "showCatName", False)
    _set_chart_data_label_bool_child(point_label, "showSerName", False)
    _set_chart_data_label_bool_child(point_label, "showPercent", False)
    _set_chart_data_label_bool_child(point_label, "showBubbleSize", False)
    data_labels.insert(_data_label_insert_index(data_labels, "dLbl"), point_label)
    return point_label


def _chart_point_element(
    series_element: ET.Element,
    point_index: int,
) -> ET.Element:
    for fallback_index, point in enumerate(series_element.findall(f"{{{C_NS}}}dPt")):
        raw_index = point.find(f"{{{C_NS}}}idx")
        if (
            raw_index is not None
            and int(raw_index.attrib.get("val", fallback_index)) == point_index
        ):
            return point
        if raw_index is None and fallback_index == point_index:
            return point
    point = ET.Element(f"{{{C_NS}}}dPt")
    ET.SubElement(point, f"{{{C_NS}}}idx", {"val": str(point_index)})
    series_element.insert(_chart_series_child_insert_index(series_element, "dPt"), point)
    return point


def _chart_point_marker_element(point: ET.Element) -> ET.Element:
    marker = point.find(f"{{{C_NS}}}marker")
    if marker is not None:
        return marker
    marker = ET.Element(f"{{{C_NS}}}marker")
    point.insert(_dpt_child_insert_index(point, "marker"), marker)
    return marker


def _chart_series_element(chart_element: ET.Element, series_index: int) -> ET.Element:
    series_items = chart_element.findall(f".//{{{C_NS}}}ser")
    for fallback_index, series_element in enumerate(series_items):
        raw_index = series_element.find(f"{{{C_NS}}}idx")
        if (
            raw_index is not None
            and int(raw_index.attrib.get("val", fallback_index)) == series_index
        ):
            return series_element
        if raw_index is None and fallback_index == series_index:
            return series_element
    raise IndexError("chart series index out of range")


def _set_chart_data_label_bool_child(
    data_labels: ET.Element,
    local_name: str,
    enabled: bool,
) -> None:
    child = data_labels.find(f"{{{C_NS}}}{local_name}")
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        data_labels.insert(_data_label_insert_index(data_labels, local_name), child)
    child.set("val", "1" if enabled else "0")


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


def _chart_series_data_labels_insert_index(series_element: ET.Element) -> int:
    return _chart_series_child_insert_index(series_element, "dLbls")


def _set_chart_series_invert_if_negative(series_element: ET.Element, value: bool) -> None:
    child = series_element.find(f"{{{C_NS}}}invertIfNegative")
    val_str = "1" if value else "0"
    if child is None:
        child = ET.Element(f"{{{C_NS}}}invertIfNegative")
        child.set("val", val_str)
        insert_idx = _chart_series_child_insert_index(series_element, "invertIfNegative")
        series_element.insert(insert_idx, child)
    else:
        child.set("val", val_str)


def _chart_series_child_insert_index(series_element: ET.Element, local_name: str) -> int:
    target_order = _SERIES_CHILD_INDEX[local_name]
    for index, child in enumerate(list(series_element)):
        child_order = _SERIES_CHILD_INDEX.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(series_element)


def _dpt_child_insert_index(point: ET.Element, local_name: str) -> int:
    order = {
        "idx": 0,
        "invertIfNegative": 1,
        "marker": 2,
        "bubble3D": 3,
        "explosion": 4,
        "spPr": 5,
        "pictureOptions": 6,
        "extLst": 7,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(point)
    for index, child in enumerate(list(point)):
        child_order = order.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(point)


def _marker_child_insert_index(marker: ET.Element, local_name: str) -> int:
    order = {
        "symbol": 0,
        "size": 1,
        "spPr": 2,
        "extLst": 3,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(marker)
    for index, child in enumerate(list(marker)):
        child_order = order.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(marker)
