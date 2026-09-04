"""Chart-space font XML edit helpers."""

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
from .facade_values import emu_to_centipoints as _emu_to_centipoints


def replace_chart_xml_font(chart_xml: bytes, font: dict[str, Any]) -> bytes:
    root = ET.fromstring(chart_xml)
    if "chart_font_size" in font:
        _set_chart_space_font_size(root, font["chart_font_size"])
    if "chart_font_bold" in font:
        _set_chart_space_font_bool(root, "b", font["chart_font_bold"])
    if "chart_font_italic" in font:
        _set_chart_space_font_bool(root, "i", font["chart_font_italic"])
    if "chart_font_underline" in font:
        _set_chart_space_font_underline(root, font["chart_font_underline"])
    if "chart_font_fill_type" in font:
        _set_chart_space_font_fill_type(root, str(font["chart_font_fill_type"]))
    if "chart_font_pattern" in font:
        _set_chart_space_font_pattern(root, font["chart_font_pattern"])
    if "chart_font_pattern_fore_rgb" in font:
        _set_chart_space_font_pattern_rgb(
            root,
            "fgClr",
            font["chart_font_pattern_fore_rgb"],
        )
    if "chart_font_pattern_back_rgb" in font:
        _set_chart_space_font_pattern_rgb(
            root,
            "bgClr",
            font["chart_font_pattern_back_rgb"],
        )
    if "chart_font_gradient" in font:
        _set_chart_space_font_gradient(root, font["chart_font_gradient"])
    if "chart_font_rgb" in font:
        _set_chart_space_font_rgb(root, font["chart_font_rgb"])
    if "chart_font_name" in font:
        _set_chart_space_font_name(root, font["chart_font_name"])
    if "chart_font_language_id" in font:
        _set_chart_space_font_language_id(root, font["chart_font_language_id"])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _chart_space_child_insert_index(root: ET.Element) -> int:
    for index, child in enumerate(list(root)):
        if child.tag in {
            f"{{{C_NS}}}externalData",
            f"{{{C_NS}}}printSettings",
            f"{{{C_NS}}}userShapes",
            f"{{{C_NS}}}extLst",
        }:
            return index
    return len(root)


def _chart_space_text_default_run_properties(root: ET.Element) -> ET.Element:
    text_properties = root.find(f"{{{C_NS}}}txPr")
    if text_properties is None:
        text_properties = ET.Element(f"{{{C_NS}}}txPr")
        text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
        text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
        paragraph = ET.Element(f"{{{A_NS}}}p")
        paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
        text_properties.append(paragraph)
        root.insert(_chart_space_child_insert_index(root), text_properties)
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


def _set_chart_space_font_size(root: ET.Element, value: Any) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
    if value is None:
        run_properties.attrib.pop("sz", None)
        return
    run_properties.set("sz", str(_emu_to_centipoints(int(value))))


def _set_chart_space_font_bool(
    root: ET.Element,
    attr: str,
    value: bool | None,
) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
    if value is None:
        run_properties.attrib.pop(attr, None)
        return
    run_properties.set(attr, "1" if value else "0")


def _set_chart_space_font_underline(root: ET.Element, value: bool | None) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
    if value is None:
        run_properties.attrib.pop("u", None)
        return
    run_properties.set("u", "sng" if value else "none")


def _set_chart_space_font_rgb(root: ET.Element, value: str | None) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
    if value is None:
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if solid_fill is not None:
            run_properties.remove(solid_fill)
        return
    solid_fill = _run_solid_fill_element(run_properties)
    _set_solid_fill_rgb(solid_fill, value)


def _set_chart_space_font_fill_type(root: ET.Element, value: str) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
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
    raise ValueError(f"unsupported chart font fill type: {value!r}")


def _set_chart_space_font_pattern(root: ET.Element, value: str | None) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
    _set_run_pattern_fill(run_properties, value)


def _set_chart_space_font_pattern_rgb(
    root: ET.Element,
    color_tag: str,
    value: str | None,
) -> None:
    if value is None:
        return
    run_properties = _chart_space_text_default_run_properties(root)
    _set_run_pattern_fill_color(run_properties, color_tag, value)


def _set_chart_space_font_gradient(
    root: ET.Element,
    value: dict[str, Any],
) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
    _set_run_gradient_fill(run_properties, value)


def _set_chart_space_font_name(root: ET.Element, value: str | None) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if value is None:
        if latin is not None:
            run_properties.remove(latin)
        return
    if latin is None:
        latin = ET.Element(f"{{{A_NS}}}latin")
        run_properties.append(latin)
    latin.set("typeface", value)


def _set_chart_space_font_language_id(
    root: ET.Element,
    value: str | None,
) -> None:
    run_properties = _chart_space_text_default_run_properties(root)
    if value is None:
        run_properties.attrib.pop("lang", None)
        return
    run_properties.set("lang", value)
