"""Chart legend XML inspection and mutation helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_xml_utils import A_NS, C_NS
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


def chart_has_legend(chart: ET.Element | None) -> bool:
    return chart is not None and chart.find(f"{{{C_NS}}}legend") is not None


def chart_legend_position(chart: ET.Element | None) -> str:
    if chart is None:
        return "r"
    legend = chart.find(f"{{{C_NS}}}legend")
    if legend is None:
        return "r"
    legend_position = legend.find(f"{{{C_NS}}}legendPos")
    if legend_position is None:
        return "r"
    return legend_position.attrib.get("val") or "r"


def chart_legend_include_in_layout(chart: ET.Element | None) -> bool:
    if chart is None:
        return True
    legend = chart.find(f"{{{C_NS}}}legend")
    if legend is None:
        return True
    overlay = legend.find(f"{{{C_NS}}}overlay")
    if overlay is None:
        return True
    return overlay.attrib.get("val") != "0"


def chart_legend_font_bool(chart: ET.Element | None, attr: str) -> bool | None:
    run_properties = _chart_legend_run_properties(chart)
    if run_properties is None:
        return None
    value = run_properties.attrib.get(attr)
    if value is None:
        return None
    return value in {"1", "true"}


def chart_legend_font_underline(chart: ET.Element | None) -> bool | None:
    run_properties = _chart_legend_run_properties(chart)
    if run_properties is None:
        return None
    value = run_properties.attrib.get("u")
    if value is None:
        return None
    if value == "none":
        return False
    if value == "sng":
        return True
    return None


def chart_legend_font_size(chart: ET.Element | None) -> int | None:
    run_properties = _chart_legend_run_properties(chart)
    if run_properties is None:
        return None
    raw = run_properties.attrib.get("sz")
    if raw is None:
        return None
    from .facade_values import centipoints_to_emu as _centipoints_to_emu

    return _centipoints_to_emu(int(raw))


def chart_legend_font_rgb(chart: ET.Element | None) -> str | None:
    run_properties = _chart_legend_run_properties(chart)
    if run_properties is None:
        return None
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    if color is None:
        return None
    value = color.attrib.get("val")
    return value.upper() if value else None


def chart_legend_font_name(chart: ET.Element | None) -> str | None:
    run_properties = _chart_legend_run_properties(chart)
    if run_properties is None:
        return None
    latin = run_properties.find(f"{{{A_NS}}}latin")
    return None if latin is None else latin.attrib.get("typeface")


def replace_chart_xml_legend(chart_xml: bytes, legend: dict[str, Any]) -> bytes:
    root = ET.fromstring(chart_xml)
    chart = _chart_container_element(root)
    if chart is None:
        raise AttributeError("chart element is unavailable")
    if legend.get("has_legend") is False:
        legend_element = chart.find(f"{{{C_NS}}}legend")
        if legend_element is not None:
            chart.remove(legend_element)
        else:
            return chart_xml
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    legend_element = _chart_legend_element(chart)
    if "position" in legend:
        _set_chart_legend_position(legend_element, str(legend["position"]))
    if "include_in_layout" in legend:
        _set_chart_legend_include_in_layout(
            legend_element,
            bool(legend["include_in_layout"]),
        )
    if "legend_font_size" in legend:
        _set_chart_legend_font_size(legend_element, legend["legend_font_size"])
    if "legend_font_bold" in legend:
        _set_chart_legend_font_bool(legend_element, "b", legend["legend_font_bold"])
    if "legend_font_italic" in legend:
        _set_chart_legend_font_bool(legend_element, "i", legend["legend_font_italic"])
    if "legend_font_underline" in legend:
        _set_chart_legend_font_underline(legend_element, legend["legend_font_underline"])
    if "legend_font_fill_type" in legend:
        _set_chart_legend_font_fill_type(
            legend_element,
            str(legend["legend_font_fill_type"]),
        )
    if "legend_font_pattern" in legend:
        _set_chart_legend_font_pattern(
            legend_element,
            legend["legend_font_pattern"],
        )
    if "legend_font_pattern_fore_rgb" in legend:
        _set_chart_legend_font_pattern_rgb(
            legend_element,
            "fgClr",
            legend["legend_font_pattern_fore_rgb"],
        )
    if "legend_font_pattern_back_rgb" in legend:
        _set_chart_legend_font_pattern_rgb(
            legend_element,
            "bgClr",
            legend["legend_font_pattern_back_rgb"],
        )
    if "legend_font_gradient" in legend:
        _set_chart_legend_font_gradient(
            legend_element,
            legend["legend_font_gradient"],
        )
    if "legend_font_rgb" in legend:
        _set_chart_legend_font_rgb(legend_element, legend["legend_font_rgb"])
    if "legend_font_name" in legend:
        _set_chart_legend_font_name(legend_element, legend["legend_font_name"])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _chart_container_element(root: ET.Element) -> ET.Element | None:
    if root.tag == f"{{{C_NS}}}chart":
        return root
    return root.find(f"{{{C_NS}}}chart")


def _chart_legend_run_properties(chart: ET.Element | None) -> ET.Element | None:
    if chart is None:
        return None
    legend = chart.find(f"{{{C_NS}}}legend")
    if legend is None:
        return None
    return legend.find(
        f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )


def _chart_legend_element(chart: ET.Element) -> ET.Element:
    legend = chart.find(f"{{{C_NS}}}legend")
    if legend is not None:
        return legend
    legend = ET.Element(f"{{{C_NS}}}legend")
    insert_at = len(chart)
    for index, child in enumerate(list(chart)):
        if child.tag in {
            f"{{{C_NS}}}dispBlanksAs",
            f"{{{C_NS}}}plotVisOnly",
            f"{{{C_NS}}}showDLblsOverMax",
            f"{{{C_NS}}}extLst",
        }:
            insert_at = index
            break
    else:
        plot_area = chart.find(f"{{{C_NS}}}plotArea")
        if plot_area is not None:
            insert_at = list(chart).index(plot_area) + 1
    chart.insert(insert_at, legend)
    return legend


def _set_chart_legend_position(legend: ET.Element, position: str) -> None:
    legend_position = legend.find(f"{{{C_NS}}}legendPos")
    if legend_position is None:
        legend_position = ET.Element(f"{{{C_NS}}}legendPos")
        legend.insert(0, legend_position)
    if position == "r":
        legend_position.attrib.pop("val", None)
        return
    legend_position.set("val", position)


def _set_chart_legend_include_in_layout(legend: ET.Element, include: bool) -> None:
    overlay = legend.find(f"{{{C_NS}}}overlay")
    if overlay is None:
        overlay = ET.Element(f"{{{C_NS}}}overlay")
        legend.append(overlay)
    overlay.set("val", "1" if include else "0")


def _chart_legend_child_insert_index(legend: ET.Element) -> int:
    for index, child in enumerate(list(legend)):
        if child.tag == f"{{{C_NS}}}extLst":
            return index
    return len(legend)


def _chart_legend_text_default_run_properties(legend: ET.Element) -> ET.Element:
    text_properties = legend.find(f"{{{C_NS}}}txPr")
    if text_properties is None:
        text_properties = ET.Element(f"{{{C_NS}}}txPr")
        text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
        text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
        paragraph = ET.Element(f"{{{A_NS}}}p")
        paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
        text_properties.append(paragraph)
        legend.insert(_chart_legend_child_insert_index(legend), text_properties)
    run_properties = text_properties.find(
        f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )
    if run_properties is None:
        paragraph = text_properties.find(f"{{{A_NS}}}p")
        if paragraph is None:
            paragraph = ET.SubElement(text_properties, f"{{{A_NS}}}p")
        paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
        if paragraph_properties is None:
            paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        run_properties = ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
    return run_properties


def _set_chart_legend_font_size(legend: ET.Element, value: Any) -> None:
    run_properties = _chart_legend_text_default_run_properties(legend)
    if value is None:
        run_properties.attrib.pop("sz", None)
        return
    from .facade_values import emu_to_centipoints as _emu_to_centipoints

    run_properties.set("sz", str(_emu_to_centipoints(int(value))))


def _set_chart_legend_font_bool(
    legend: ET.Element,
    attr: str,
    value: bool | None,
) -> None:
    run_properties = _chart_legend_text_default_run_properties(legend)
    if value is None:
        run_properties.attrib.pop(attr, None)
        return
    run_properties.set(attr, "1" if value else "0")


def _set_chart_legend_font_underline(
    legend: ET.Element,
    value: bool | None,
) -> None:
    run_properties = _chart_legend_text_default_run_properties(legend)
    if value is None:
        run_properties.attrib.pop("u", None)
        return
    run_properties.set("u", "sng" if value else "none")


def _set_chart_legend_font_rgb(legend: ET.Element, value: str | None) -> None:
    run_properties = _chart_legend_text_default_run_properties(legend)
    if value is None:
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if solid_fill is not None:
            run_properties.remove(solid_fill)
        return
    solid_fill = _run_solid_fill_element(run_properties)
    _set_solid_fill_rgb(solid_fill, value)


def _set_chart_legend_font_fill_type(legend: ET.Element, value: str) -> None:
    run_properties = _chart_legend_text_default_run_properties(legend)
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
    raise ValueError(f"unsupported chart legend font fill type: {value!r}")


def _set_chart_legend_font_pattern(
    legend: ET.Element,
    value: str | None,
) -> None:
    run_properties = _chart_legend_text_default_run_properties(legend)
    _set_run_pattern_fill(run_properties, value)


def _set_chart_legend_font_pattern_rgb(
    legend: ET.Element,
    color_tag: str,
    value: str | None,
) -> None:
    if value is None:
        return
    run_properties = _chart_legend_text_default_run_properties(legend)
    _set_run_pattern_fill_color(run_properties, color_tag, value)


def _set_chart_legend_font_gradient(
    legend: ET.Element,
    value: dict[str, Any],
) -> None:
    run_properties = _chart_legend_text_default_run_properties(legend)
    _set_run_gradient_fill(run_properties, value)


def _set_chart_legend_font_name(legend: ET.Element, value: str | None) -> None:
    run_properties = _chart_legend_text_default_run_properties(legend)
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if value is None:
        if latin is not None:
            run_properties.remove(latin)
        return
    if latin is None:
        latin = ET.Element(f"{{{A_NS}}}latin")
        run_properties.append(latin)
    latin.set("typeface", value)
