"""Chart data-label XML inspection and mutation helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_point_xml import (
    set_chart_point_data_label_properties as _set_chart_point_data_label_properties,
    set_chart_point_format_properties as _set_chart_point_format_properties,
    set_chart_point_marker_format_properties as _set_chart_point_marker_format_properties,
    set_chart_series_data_label_properties as _set_chart_series_data_label_properties,
    set_chart_series_format_properties as _set_chart_series_format_properties,
)
from .dml_fill import (
    run_gradient_fill_element as _run_gradient_fill_element,
    run_no_fill_element as _run_no_fill_element,
    run_pattern_fill_element as _run_pattern_fill_element,
    run_solid_fill_element as _run_solid_fill_element,
    set_run_gradient_fill as _set_run_gradient_fill,
    set_run_pattern_fill as _set_run_pattern_fill,
    set_run_pattern_fill_color as _set_run_pattern_fill_color,
    set_solid_fill_rgb as _set_solid_fill_rgb,
)

C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_DATA_LABEL_CHILD_ORDER = [
    "dLbl",
    "idx",
    "tx",
    "numFmt",
    "spPr",
    "txPr",
    "dLblPos",
    "showLegendKey",
    "showVal",
    "showCatName",
    "showSerName",
    "showPercent",
    "showBubbleSize",
    "separator",
    "showLeaderLines",
    "extLst",
]
_DATA_LABEL_CHILD_INDEX = {
    local_name: index for index, local_name in enumerate(_DATA_LABEL_CHILD_ORDER)
}


def default_chart_data_labels_payload() -> dict[str, Any]:
    return {
        "has_data_labels": False,
        "show_value": True,
        "show_category_name": False,
        "show_series_name": False,
        "show_percentage": False,
        "show_legend_key": False,
        "position": None,
        "number_format": "General",
        "number_format_is_linked": True,
        "font_bold": None,
        "font_italic": None,
        "font_underline": None,
        "font_size": None,
        "font_rgb": None,
        "font_name": None,
        "font_language_id": None,
    }


def chart_data_labels_payload(chart_element: ET.Element | None) -> dict[str, Any]:
    payload = default_chart_data_labels_payload()
    data_labels = None if chart_element is None else chart_element.find(f"{{{C_NS}}}dLbls")
    if data_labels is None:
        return payload
    num_fmt = data_labels.find(f"{{{C_NS}}}numFmt")
    payload.update(
        {
            "has_data_labels": True,
            "show_value": _chart_bool_child(data_labels, "showVal", default=False),
            "show_category_name": _chart_bool_child(
                data_labels,
                "showCatName",
                default=False,
            ),
            "show_series_name": _chart_bool_child(
                data_labels,
                "showSerName",
                default=False,
            ),
            "show_percentage": _chart_bool_child(
                data_labels,
                "showPercent",
                default=False,
            ),
            "show_legend_key": _chart_bool_child(
                data_labels,
                "showLegendKey",
                default=False,
            ),
            "position": _child_val(data_labels, "dLblPos"),
            "number_format": (
                "General"
                if num_fmt is None
                else num_fmt.attrib.get("formatCode", "General")
            ),
            "number_format_is_linked": (
                True
                if num_fmt is None
                else _xml_bool_value(num_fmt.attrib.get("sourceLinked"), default=True)
            ),
            "font_bold": _chart_data_label_font_bool(data_labels, "b"),
            "font_italic": _chart_data_label_font_bool(data_labels, "i"),
            "font_underline": _chart_data_label_font_underline(data_labels),
            "font_size": _chart_data_label_font_size(data_labels),
            "font_rgb": _chart_data_label_font_rgb(data_labels),
            "font_name": _chart_data_label_font_name(data_labels),
            "font_language_id": _chart_data_label_font_language_id(data_labels),
        }
    )
    return payload


def replace_chart_xml_data_labels(chart_xml: bytes, data_labels: dict[str, Any]) -> bytes:
    root = ET.fromstring(chart_xml)
    chart_element = _first_chart_element(root)
    if chart_element is None:
        raise AttributeError("chart plot element is unavailable")
    if data_labels.get("has_data_labels") is False:
        data_labels_element = chart_element.find(f"{{{C_NS}}}dLbls")
        if data_labels_element is not None:
            chart_element.remove(data_labels_element)
            return ET.tostring(root, encoding="utf-8", xml_declaration=True)
        return chart_xml

    scoped_keys = {
        "point_labels",
        "point_formats",
        "point_marker_formats",
        "series_data_labels",
        "series_formats",
    }
    if scoped_keys & set(data_labels) and not (
        set(data_labels) - {"has_data_labels", *scoped_keys}
    ):
        if "point_labels" in data_labels:
            _set_chart_point_data_label_properties(
                chart_element,
                data_labels["point_labels"],
            )
        if "point_formats" in data_labels:
            _set_chart_point_format_properties(
                chart_element,
                data_labels["point_formats"],
            )
        if "point_marker_formats" in data_labels:
            _set_chart_point_marker_format_properties(
                chart_element,
                data_labels["point_marker_formats"],
            )
        if "series_formats" in data_labels:
            _set_chart_series_format_properties(
                chart_element,
                data_labels["series_formats"],
            )
        if "series_data_labels" in data_labels:
            _set_chart_series_data_label_properties(
                chart_element,
                data_labels["series_data_labels"],
            )
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    data_labels_element = _chart_data_labels_element(chart_element)
    for attr, value in data_labels.items():
        if attr == "point_labels":
            _set_chart_point_data_label_properties(
                chart_element,
                value,
            )
            continue
        if attr == "point_formats":
            _set_chart_point_format_properties(
                chart_element,
                value,
            )
            continue
        if attr == "point_marker_formats":
            _set_chart_point_marker_format_properties(
                chart_element,
                value,
            )
            continue
        if attr == "series_formats":
            _set_chart_series_format_properties(
                chart_element,
                value,
            )
            continue
        if attr == "series_data_labels":
            _set_chart_series_data_label_properties(
                chart_element,
                value,
            )
            continue
        _set_chart_data_label_property(data_labels_element, attr, value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _first_chart_element(root: ET.Element) -> ET.Element | None:
    plot_area = root.find(f".//{{{C_NS}}}plotArea")
    if plot_area is None:
        return None
    for child in list(plot_area):
        if _xml_local_name(child.tag).endswith("Chart"):
            return child
    return None


def _chart_bool_child(
    element: ET.Element,
    child_name: str,
    *,
    default: bool,
) -> bool:
    child = element.find(f"{{{C_NS}}}{child_name}")
    if child is None:
        return default
    return _xml_bool_value(child.attrib.get("val"), default=default)


def _chart_data_labels_element(chart_element: ET.Element) -> ET.Element:
    data_labels = chart_element.find(f"{{{C_NS}}}dLbls")
    if data_labels is not None:
        return data_labels
    data_labels = ET.Element(f"{{{C_NS}}}dLbls")
    _set_chart_data_label_bool_child(data_labels, "showLegendKey", False)
    _set_chart_data_label_bool_child(data_labels, "showVal", True)
    _set_chart_data_label_bool_child(data_labels, "showCatName", False)
    _set_chart_data_label_bool_child(data_labels, "showSerName", False)
    _set_chart_data_label_bool_child(data_labels, "showPercent", False)
    _set_chart_data_label_bool_child(data_labels, "showBubbleSize", False)
    _set_chart_data_label_bool_child(data_labels, "showLeaderLines", True)
    chart_element.insert(_chart_data_labels_insert_index(chart_element), data_labels)
    return data_labels


def _set_chart_data_label_property(
    data_labels: ET.Element,
    attr: str,
    value: Any,
) -> None:
    if attr == "has_data_labels":
        return
    if attr == "show_value":
        _set_chart_data_label_bool_child(data_labels, "showVal", bool(value))
        return
    if attr == "show_category_name":
        _set_chart_data_label_bool_child(data_labels, "showCatName", bool(value))
        return
    if attr == "show_series_name":
        _set_chart_data_label_bool_child(data_labels, "showSerName", bool(value))
        return
    if attr == "show_percentage":
        _set_chart_data_label_bool_child(data_labels, "showPercent", bool(value))
        return
    if attr == "show_legend_key":
        _set_chart_data_label_bool_child(data_labels, "showLegendKey", bool(value))
        return
    if attr == "position":
        _set_chart_data_label_position(data_labels, value)
        return
    if attr == "number_format":
        _set_chart_data_label_number_format(data_labels, str(value))
        return
    if attr == "number_format_is_linked":
        _set_chart_data_label_number_format_source_linked(data_labels, bool(value))
        return
    if attr == "font_size":
        _set_chart_data_label_font_size(data_labels, value)
        return
    if attr == "font_bold":
        _set_chart_data_label_font_bool(data_labels, "b", value)
        return
    if attr == "font_italic":
        _set_chart_data_label_font_bool(data_labels, "i", value)
        return
    if attr == "font_underline":
        _set_chart_data_label_font_underline(data_labels, value)
        return
    if attr == "font_fill_type":
        _set_chart_data_label_font_fill_type(data_labels, str(value))
        return
    if attr == "font_pattern":
        _set_chart_data_label_font_pattern(data_labels, value)
        return
    if attr == "font_pattern_fore_rgb":
        _set_chart_data_label_font_pattern_rgb(data_labels, "fgClr", value)
        return
    if attr == "font_pattern_back_rgb":
        _set_chart_data_label_font_pattern_rgb(data_labels, "bgClr", value)
        return
    if attr == "font_gradient":
        _set_chart_data_label_font_gradient(data_labels, value)
        return
    if attr == "font_rgb":
        _set_chart_data_label_font_rgb(
            data_labels,
            None if value is None else str(value),
        )
        return
    if attr == "font_name":
        _set_chart_data_label_font_name(
            data_labels,
            None if value is None else str(value),
        )
        return
    if attr == "font_language_id":
        _set_chart_data_label_font_language_id(
            data_labels,
            None if value is None else str(value),
        )
        return
    raise ValueError(f"unsupported chart data-label property: {attr!r}")


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


def _set_chart_data_label_position(data_labels: ET.Element, value: Any) -> None:
    position = data_labels.find(f"{{{C_NS}}}dLblPos")
    if value is None:
        if position is not None:
            data_labels.remove(position)
        return
    if position is None:
        position = ET.Element(f"{{{C_NS}}}dLblPos")
        data_labels.insert(_data_label_insert_index(data_labels, "dLblPos"), position)
    position.set("val", str(value))


def _chart_data_label_num_fmt_element(data_labels: ET.Element) -> ET.Element:
    num_fmt = data_labels.find(f"{{{C_NS}}}numFmt")
    if num_fmt is not None:
        return num_fmt
    num_fmt = ET.Element(f"{{{C_NS}}}numFmt")
    data_labels.insert(_data_label_insert_index(data_labels, "numFmt"), num_fmt)
    return num_fmt


def _set_chart_data_label_number_format(
    data_labels: ET.Element,
    format_code: str,
) -> None:
    num_fmt = _chart_data_label_num_fmt_element(data_labels)
    num_fmt.set("formatCode", format_code)
    num_fmt.set("sourceLinked", "0")


def _set_chart_data_label_number_format_source_linked(
    data_labels: ET.Element,
    source_linked: bool,
) -> None:
    num_fmt = _chart_data_label_num_fmt_element(data_labels)
    if num_fmt.get("formatCode") is None:
        num_fmt.set("formatCode", "General")
    num_fmt.set("sourceLinked", "1" if source_linked else "0")


def _chart_data_label_font_size(data_labels: ET.Element) -> int | None:
    run_properties = data_labels.find(
        f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )
    if run_properties is None:
        return None
    raw = run_properties.attrib.get("sz")
    if raw is None:
        return None
    from .facade_values import centipoints_to_emu as _centipoints_to_emu

    return _centipoints_to_emu(int(raw))


def _chart_data_label_default_run_properties(data_labels: ET.Element) -> ET.Element | None:
    return data_labels.find(
        f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )


def _chart_data_label_font_bool(data_labels: ET.Element, attr: str) -> bool | None:
    run_properties = _chart_data_label_default_run_properties(data_labels)
    if run_properties is None:
        return None
    value = run_properties.attrib.get(attr)
    if value is None:
        return None
    return value in {"1", "true"}


def _chart_data_label_font_underline(data_labels: ET.Element) -> bool | None:
    run_properties = _chart_data_label_default_run_properties(data_labels)
    if run_properties is None:
        return None
    value = run_properties.attrib.get("u")
    if value is None:
        return None
    return value != "none"


def _chart_data_label_font_rgb(data_labels: ET.Element) -> str | None:
    run_properties = _chart_data_label_default_run_properties(data_labels)
    if run_properties is None:
        return None
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    value = None if color is None else color.attrib.get("val")
    return None if value is None else value.upper()


def _chart_data_label_font_name(data_labels: ET.Element) -> str | None:
    run_properties = _chart_data_label_default_run_properties(data_labels)
    if run_properties is None:
        return None
    latin = run_properties.find(f"{{{A_NS}}}latin")
    return None if latin is None else latin.attrib.get("typeface")


def _chart_data_label_font_language_id(data_labels: ET.Element) -> str | None:
    run_properties = _chart_data_label_default_run_properties(data_labels)
    if run_properties is None:
        return None
    return run_properties.attrib.get("lang")


def _chart_data_label_text_default_run_properties(data_labels: ET.Element) -> ET.Element:
    text_properties = data_labels.find(f"{{{C_NS}}}txPr")
    if text_properties is None:
        text_properties = ET.Element(f"{{{C_NS}}}txPr")
        text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
        text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
        paragraph = ET.Element(f"{{{A_NS}}}p")
        paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
        text_properties.append(paragraph)
        data_labels.insert(_data_label_insert_index(data_labels, "txPr"), text_properties)
    run_properties = text_properties.find(
        f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )
    if run_properties is None:
        paragraph = text_properties.find(f"{{{A_NS}}}p")
        if paragraph is None:
            paragraph = ET.Element(f"{{{A_NS}}}p")
            text_properties.append(paragraph)
        paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
        if paragraph_properties is None:
            paragraph_properties = ET.Element(f"{{{A_NS}}}pPr")
            paragraph.insert(0, paragraph_properties)
        run_properties = paragraph_properties.find(f"{{{A_NS}}}defRPr")
        if run_properties is None:
            run_properties = ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
    return run_properties


def _set_chart_data_label_font_size(data_labels: ET.Element, value: Any) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        run_properties.attrib.pop("sz", None)
        return
    from .facade_values import emu_to_centipoints as _emu_to_centipoints

    run_properties.set("sz", str(_emu_to_centipoints(int(value))))


def _set_chart_data_label_font_bool(
    data_labels: ET.Element,
    attr: str,
    value: bool | None,
) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        run_properties.attrib.pop(attr, None)
        return
    run_properties.set(attr, "1" if bool(value) else "0")


def _set_chart_data_label_font_underline(
    data_labels: ET.Element,
    value: bool | None,
) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        run_properties.attrib.pop("u", None)
        return
    run_properties.set("u", "sng" if bool(value) else "none")


def _set_chart_data_label_font_rgb(data_labels: ET.Element, value: str | None) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if solid_fill is not None:
            run_properties.remove(solid_fill)
        return
    solid_fill = _run_solid_fill_element(run_properties)
    _set_solid_fill_rgb(solid_fill, value)


def _set_chart_data_label_font_fill_type(data_labels: ET.Element, value: str) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    if value == "solid":
        if run_properties.find(f"{{{A_NS}}}solidFill") is None:
            _run_solid_fill_element(run_properties)
        no_fill = run_properties.find(f"{{{A_NS}}}noFill")
        if no_fill is not None:
            run_properties.remove(no_fill)
        return
    if value == "background":
        _run_no_fill_element(run_properties)
        return
    if value == "patterned":
        if run_properties.find(f"{{{A_NS}}}pattFill") is None:
            _run_pattern_fill_element(run_properties)
        return
    if value == "gradient":
        if run_properties.find(f"{{{A_NS}}}gradFill") is None:
            _run_gradient_fill_element(run_properties)
        return
    raise ValueError(f"unsupported chart data-label font fill type: {value!r}")


def _set_chart_data_label_font_pattern(
    data_labels: ET.Element,
    value: str | None,
) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    _set_run_pattern_fill(run_properties, value)


def _set_chart_data_label_font_pattern_rgb(
    data_labels: ET.Element,
    color_tag: str,
    value: str | None,
) -> None:
    if value is None:
        return
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    _set_run_pattern_fill_color(run_properties, color_tag, value)


def _set_chart_data_label_font_gradient(
    data_labels: ET.Element,
    value: dict[str, Any],
) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    _set_run_gradient_fill(run_properties, value)


def _set_chart_data_label_font_name(data_labels: ET.Element, value: str | None) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if value is None:
        if latin is not None:
            run_properties.remove(latin)
        return
    if latin is None:
        latin = ET.Element(f"{{{A_NS}}}latin")
        run_properties.append(latin)
    latin.set("typeface", value)


def _set_chart_data_label_font_language_id(
    data_labels: ET.Element,
    value: str | None,
) -> None:
    run_properties = _chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        run_properties.attrib.pop("lang", None)
    else:
        run_properties.set("lang", value)


def _chart_data_labels_insert_index(chart_element: ET.Element) -> int:
    series = chart_element.findall(f"{{{C_NS}}}ser")
    if series:
        children = list(chart_element)
        return children.index(series[-1]) + 1
    for index, child in enumerate(list(chart_element)):
        if _xml_local_name(child.tag) == "axId":
            return index
    return len(chart_element)


def _data_label_insert_index(data_labels: ET.Element, local_name: str) -> int:
    target_order = _DATA_LABEL_CHILD_INDEX.get(local_name)
    if target_order is None:
        return len(data_labels)
    for index, child in enumerate(list(data_labels)):
        child_order = _DATA_LABEL_CHILD_INDEX.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(data_labels)


def _child_val(element: ET.Element, child_name: str) -> str | None:
    child = element.find(f"{{{C_NS}}}{child_name}")
    if child is None:
        return None
    return child.attrib.get("val")


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _xml_bool_value(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value not in {"0", "false", "False"}
