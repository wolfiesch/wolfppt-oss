"""Shared DrawingML text XML mutation helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .facade_values import emu_to_centipoints as _emu_to_centipoints
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_TEXT_FRAME_AUTO_SIZE_TAGS = {"noAutofit", "spAutoFit", "normAutofit"}


def _clear_text_frame_auto_size_children(body_properties: ET.Element) -> None:
    for child in list(body_properties):
        if _xml_local_name(child.tag) in _TEXT_FRAME_AUTO_SIZE_TAGS:
            body_properties.remove(child)


def _text_frame_auto_size_insert_index(body_properties: ET.Element) -> int:
    trailing_tags = {"scene3d", "sp3d", "flatTx", "extLst"}
    for index, child in enumerate(list(body_properties)):
        if _xml_local_name(child.tag) in trailing_tags:
            return index
    return len(body_properties)


def _text_character_properties_element(text_child: ET.Element) -> ET.Element:
    run_properties = text_child.find(f"{{{A_NS}}}rPr")
    if run_properties is not None:
        return run_properties
    run_properties = ET.Element(f"{{{A_NS}}}rPr")
    insert_at = 0
    for index, child in enumerate(list(text_child)):
        if _xml_local_name(child.tag) in {"t", "fldData", "extLst"}:
            insert_at = index
            break
    text_child.insert(insert_at, run_properties)
    return run_properties


def _end_paragraph_run_properties_element(paragraph: ET.Element) -> ET.Element:
    run_properties = paragraph.find(f"{{{A_NS}}}endParaRPr")
    if run_properties is not None:
        return run_properties
    run_properties = ET.Element(f"{{{A_NS}}}endParaRPr")
    insert_at = len(paragraph)
    for index, child in enumerate(list(paragraph)):
        if _xml_local_name(child.tag) == "extLst":
            insert_at = index
            break
    paragraph.insert(insert_at, run_properties)
    return run_properties


def _set_fit_font_properties(run_properties: ET.Element, fit: dict[str, Any]) -> None:
    _set_font_size(run_properties, int(fit["size"]))
    _set_font_bool_attribute(run_properties, "b", bool(fit["bold"]))
    _set_font_bool_attribute(run_properties, "i", bool(fit["italic"]))
    _set_font_name(run_properties, str(fit["font_family"]))


def _set_font_bool_attribute(
    run_properties: ET.Element,
    attr: str,
    value: bool | None,
) -> None:
    if value is None:
        run_properties.attrib.pop(attr, None)
        return
    run_properties.set(attr, "1" if value else "0")


def _set_font_underline(run_properties: ET.Element, value: bool | None) -> None:
    if value is None:
        run_properties.attrib.pop("u", None)
        return
    run_properties.set("u", "sng" if value else "none")


def _set_font_size(run_properties: ET.Element, value: int | None) -> None:
    if value is None:
        run_properties.attrib.pop("sz", None)
        return
    run_properties.set("sz", str(_emu_to_centipoints(int(value))))


def _set_font_name(run_properties: ET.Element, value: str | None) -> None:
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if value is None:
        if latin is not None:
            run_properties.remove(latin)
        return
    if latin is None:
        latin = ET.Element(f"{{{A_NS}}}latin")
        insert_at = len(run_properties)
        trailing_tags = {
            "ea",
            "cs",
            "sym",
            "hlinkClick",
            "hlinkMouseOver",
            "rtl",
            "extLst",
        }
        for index, child in enumerate(list(run_properties)):
            if _xml_local_name(child.tag) in trailing_tags:
                insert_at = index
                break
        run_properties.insert(insert_at, latin)
    latin.set("typeface", value)
