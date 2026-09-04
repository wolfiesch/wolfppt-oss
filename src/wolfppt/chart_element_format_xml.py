"""Chart element fill and line formatting XML helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_xml_utils import A_NS, C_NS, xml_local_name as _xml_local_name
from .dml_fill import (
    no_fill_element as _no_fill_element,
    set_shape_gradient_fill as _set_shape_gradient_fill,
    set_shape_pattern_fill as _set_shape_pattern_fill,
    set_shape_pattern_fill_color as _set_shape_pattern_fill_color,
)


def set_chart_element_format_properties(
    element: ET.Element,
    properties: dict[str, Any],
) -> None:
    if properties.get("fill_type") == "solid":
        set_chart_element_solid_fill(element)
    if properties.get("fill_type") == "background":
        set_chart_element_background_fill(element)
    if properties.get("fill_type") == "patterned":
        set_chart_element_pattern_fill(element, None)
    if properties.get("fill_type") == "gradient":
        set_chart_element_gradient_fill(element, properties.get("fill_gradient"))
    if "fill_rgb" in properties:
        set_chart_element_fill_rgb(element, str(properties["fill_rgb"]))
    if "fill_gradient" in properties:
        set_chart_element_gradient_fill(element, properties["fill_gradient"])
    if "fill_pattern" in properties:
        set_chart_element_pattern_fill(element, properties["fill_pattern"])
    if "fill_pattern_fore_rgb" in properties:
        set_chart_element_pattern_rgb(
            element,
            "fgClr",
            str(properties["fill_pattern_fore_rgb"]),
        )
    if "fill_pattern_back_rgb" in properties:
        set_chart_element_pattern_rgb(
            element,
            "bgClr",
            str(properties["fill_pattern_back_rgb"]),
        )
    if "line_fill_type" in properties:
        set_chart_element_line_fill_type(element, str(properties["line_fill_type"]))
    if "line_pattern" in properties:
        set_chart_element_line_pattern_fill(element, properties["line_pattern"])
    if "line_pattern_fore_rgb" in properties:
        set_chart_element_line_pattern_rgb(
            element,
            "fgClr",
            str(properties["line_pattern_fore_rgb"]),
        )
    if "line_pattern_back_rgb" in properties:
        set_chart_element_line_pattern_rgb(
            element,
            "bgClr",
            str(properties["line_pattern_back_rgb"]),
        )
    if "line_rgb" in properties:
        set_chart_element_line_rgb(element, str(properties["line_rgb"]))
    if "line_width" in properties:
        set_chart_element_line_width(element, int(properties["line_width"]))
    if "line_dash" in properties:
        set_chart_element_line_dash(element, properties["line_dash"])


def chart_element_shape_properties(element: ET.Element) -> ET.Element:
    shape_properties = element.find(f"{{{C_NS}}}spPr")
    if shape_properties is not None:
        return shape_properties
    shape_properties = ET.Element(f"{{{C_NS}}}spPr")
    element.insert(chart_element_sppr_insert_index(element), shape_properties)
    return shape_properties


def chart_element_sppr_insert_index(element: ET.Element) -> int:
    order = {
        "idx": 0,
        "order": 1,
        "tx": 2,
        "layout": 3,
        "overlay": 4,
        "spPr": 5,
        "txPr": 6,
        "extLst": 7,
        "invertIfNegative": 4,
        "dPt": 5,
        "dLbls": 6,
        "cat": 7,
        "val": 8,
    }
    target_order = order["spPr"]
    for index, child in enumerate(list(element)):
        child_order = order.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(element)


def set_chart_element_solid_fill(element: ET.Element) -> None:
    shape_properties = chart_element_shape_properties(element)
    for child in list(shape_properties):
        if child.tag in {
            f"{{{A_NS}}}noFill",
            f"{{{A_NS}}}solidFill",
            f"{{{A_NS}}}gradFill",
            f"{{{A_NS}}}blipFill",
            f"{{{A_NS}}}pattFill",
            f"{{{A_NS}}}grpFill",
        }:
            shape_properties.remove(child)
    shape_properties.insert(0, ET.Element(f"{{{A_NS}}}solidFill"))


def set_chart_element_fill_rgb(element: ET.Element, rgb: str) -> None:
    shape_properties = chart_element_shape_properties(element)
    solid_fill = shape_properties.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        set_chart_element_solid_fill(element)
        solid_fill = shape_properties.find(f"{{{A_NS}}}solidFill")
    assert solid_fill is not None
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def set_chart_element_pattern_fill(element: ET.Element, pattern: Any) -> None:
    _set_shape_pattern_fill(
        chart_element_shape_properties(element),
        None if pattern is None else str(pattern),
    )


def set_chart_element_pattern_rgb(
    element: ET.Element,
    color_tag: str,
    rgb: str,
) -> None:
    _set_shape_pattern_fill_color(
        chart_element_shape_properties(element),
        color_tag,
        rgb,
    )


def set_chart_element_background_fill(element: ET.Element) -> None:
    _no_fill_element(chart_element_shape_properties(element))


def set_chart_element_gradient_fill(element: ET.Element, gradient: Any) -> None:
    _set_shape_gradient_fill(
        chart_element_shape_properties(element),
        gradient if isinstance(gradient, dict) else {},
    )


def chart_element_line(element: ET.Element) -> ET.Element:
    shape_properties = chart_element_shape_properties(element)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    return line


def set_chart_element_line_fill_type(element: ET.Element, fill_type: str) -> None:
    line = chart_element_line(element)
    if fill_type == "solid":
        for child in list(line):
            if child.tag in {
                f"{{{A_NS}}}noFill",
                f"{{{A_NS}}}solidFill",
                f"{{{A_NS}}}gradFill",
                f"{{{A_NS}}}pattFill",
            }:
                line.remove(child)
        line.insert(0, ET.Element(f"{{{A_NS}}}solidFill"))
        return
    if fill_type == "background":
        for child in list(line):
            if child.tag in {
                f"{{{A_NS}}}noFill",
                f"{{{A_NS}}}solidFill",
                f"{{{A_NS}}}gradFill",
                f"{{{A_NS}}}pattFill",
            }:
                line.remove(child)
        line.insert(0, ET.Element(f"{{{A_NS}}}noFill"))
        return
    if fill_type == "patterned":
        _set_shape_pattern_fill(line, None)
        return
    raise ValueError(f"unsupported chart line fill type: {fill_type!r}")


def set_chart_element_line_pattern_fill(element: ET.Element, pattern: Any) -> None:
    _set_shape_pattern_fill(
        chart_element_line(element),
        None if pattern is None else str(pattern),
    )


def set_chart_element_line_pattern_rgb(
    element: ET.Element,
    color_tag: str,
    rgb: str,
) -> None:
    _set_shape_pattern_fill_color(chart_element_line(element), color_tag, rgb)


def set_chart_element_line_rgb(element: ET.Element, rgb: str) -> None:
    line = chart_element_line(element)
    solid_fill = line.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        set_chart_element_line_fill_type(element, "solid")
        solid_fill = line.find(f"{{{A_NS}}}solidFill")
    assert solid_fill is not None
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def set_chart_element_line_width(element: ET.Element, width: int) -> None:
    chart_element_line(element).set("w", str(width))


def set_chart_element_line_dash(element: ET.Element, dash_style: Any) -> None:
    line = chart_element_line(element)
    preset_dash = line.find(f"{{{A_NS}}}prstDash")
    if dash_style is None:
        if preset_dash is not None:
            line.remove(preset_dash)
        return
    if preset_dash is None:
        preset_dash = ET.Element(f"{{{A_NS}}}prstDash")
        line.append(preset_dash)
    preset_dash.set("val", str(dash_style))
