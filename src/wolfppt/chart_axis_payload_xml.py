"""Chart axis payload inspection helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_xml_utils import (
    A_NS,
    C_NS,
    chart_title_element_text,
    child_val,
    optional_float as _optional_float,
    optional_int as _optional_int,
    xml_bool_value as _xml_bool_value,
)


def default_chart_axis_payload() -> dict[str, Any]:
    return {
        "has_title": False,
        "title_text": "",
        "visible": True,
        "has_major_gridlines": False,
        "has_minor_gridlines": False,
        "major_tick_mark": "out",
        "minor_tick_mark": "none",
        "tick_label_position": "nextTo",
        "reverse_order": False,
        "minimum_scale": None,
        "maximum_scale": None,
        "number_format": "General",
        "number_format_is_linked": False,
        "tick_label_offset": 100,
        "tick_label_font_size": None,
        "tick_label_font_language_id": None,
        "major_unit": None,
        "minor_unit": None,
        "crosses": None,
        "crosses_at": None,
    }


def chart_axis_element(chart: ET.Element, axis: str) -> ET.Element | None:
    tag = {
        "cat": "catAx",
        "val": "valAx",
    }.get(axis)
    if tag is None:
        raise ValueError(f"unsupported chart axis: {axis!r}")
    return chart.find(f"{{{C_NS}}}plotArea/{{{C_NS}}}{tag}")


def chart_axes_payload(chart: ET.Element | None) -> dict[str, dict[str, Any]]:
    return {
        "cat": chart_axis_payload_from_xml(chart, "cat"),
        "val": chart_axis_payload_from_xml(chart, "val"),
    }


def chart_axis_payload_from_xml(
    chart: ET.Element | None,
    axis: str,
) -> dict[str, Any]:
    axis_element = None if chart is None else chart_axis_element(chart, axis)
    if axis_element is None:
        return default_chart_axis_payload()
    title = axis_element.find(f"{{{C_NS}}}title")
    scaling = axis_element.find(f"{{{C_NS}}}scaling")
    delete = axis_element.find(f"{{{C_NS}}}delete")
    num_fmt = axis_element.find(f"{{{C_NS}}}numFmt")
    deleted = False
    if delete is not None:
        deleted = _xml_bool_value(delete.attrib.get("val"), default=True)
    payload = default_chart_axis_payload()
    payload.update(
        {
            "has_title": title is not None,
            "title_text": chart_title_element_text(title),
            "visible": not deleted,
            "has_major_gridlines": axis_element.find(
                f"{{{C_NS}}}majorGridlines"
            )
            is not None,
            "has_minor_gridlines": axis_element.find(
                f"{{{C_NS}}}minorGridlines"
            )
            is not None,
            "major_tick_mark": child_val(axis_element, "majorTickMark") or "out",
            "minor_tick_mark": child_val(axis_element, "minorTickMark") or "none",
            "tick_label_position": child_val(axis_element, "tickLblPos")
            or "nextTo",
            "reverse_order": (
                scaling is not None
                and child_val(scaling, "orientation") == "maxMin"
            ),
            "minimum_scale": (
                None if scaling is None else _optional_float(child_val(scaling, "min"))
            ),
            "maximum_scale": (
                None if scaling is None else _optional_float(child_val(scaling, "max"))
            ),
            "number_format": (
                "General"
                if num_fmt is None
                else num_fmt.attrib.get("formatCode", "General")
            ),
            "number_format_is_linked": (
                False
                if num_fmt is None
                else _xml_bool_value(num_fmt.attrib.get("sourceLinked"), default=True)
            ),
            "tick_label_offset": _optional_int(child_val(axis_element, "lblOffset"), 100),
            "tick_label_font_bold": _chart_axis_tick_label_font_bool(axis_element, "b"),
            "tick_label_font_italic": _chart_axis_tick_label_font_bool(axis_element, "i"),
            "tick_label_font_underline": _chart_axis_tick_label_font_underline(
                axis_element
            ),
            "tick_label_font_size": _chart_axis_tick_label_font_size(axis_element),
            "tick_label_font_language_id": _chart_axis_tick_label_font_language_id(
                axis_element
            ),
            "tick_label_font_rgb": _chart_axis_tick_label_font_rgb(axis_element),
            "tick_label_font_name": _chart_axis_tick_label_font_name(axis_element),
            "major_unit": _optional_float(child_val(axis_element, "majorUnit")),
            "minor_unit": _optional_float(child_val(axis_element, "minorUnit")),
            "crosses": child_val(axis_element, "crosses"),
            "crosses_at": _optional_float(child_val(axis_element, "crossesAt")),
        }
    )
    return payload


def _chart_axis_tick_label_font_size(axis_element: ET.Element) -> int | None:
    run_properties = _chart_axis_tick_label_run_properties(axis_element)
    if run_properties is None:
        return None
    raw = run_properties.attrib.get("sz")
    if raw is None:
        return None
    from .facade_values import centipoints_to_emu as _centipoints_to_emu

    return _centipoints_to_emu(int(raw))


def _chart_axis_tick_label_run_properties(axis_element: ET.Element) -> ET.Element | None:
    return axis_element.find(
        f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )


def _chart_axis_tick_label_font_bool(
    axis_element: ET.Element,
    attr: str,
) -> bool | None:
    run_properties = _chart_axis_tick_label_run_properties(axis_element)
    if run_properties is None:
        return None
    value = run_properties.attrib.get(attr)
    if value is None:
        return None
    return value in {"1", "true"}


def _chart_axis_tick_label_font_underline(
    axis_element: ET.Element,
) -> bool | None:
    run_properties = _chart_axis_tick_label_run_properties(axis_element)
    if run_properties is None:
        return None
    value = run_properties.attrib.get("u")
    if value is None:
        return None
    return value != "none"


def _chart_axis_tick_label_font_rgb(axis_element: ET.Element) -> str | None:
    run_properties = _chart_axis_tick_label_run_properties(axis_element)
    if run_properties is None:
        return None
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    value = None if color is None else color.attrib.get("val")
    return None if value is None else value.upper()


def _chart_axis_tick_label_font_name(axis_element: ET.Element) -> str | None:
    run_properties = _chart_axis_tick_label_run_properties(axis_element)
    if run_properties is None:
        return None
    latin = run_properties.find(f"{{{A_NS}}}latin")
    return None if latin is None else latin.attrib.get("typeface")


def _chart_axis_tick_label_font_language_id(
    axis_element: ET.Element,
) -> str | None:
    run_properties = _chart_axis_tick_label_run_properties(axis_element)
    return None if run_properties is None else run_properties.attrib.get("lang")
