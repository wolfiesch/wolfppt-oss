"""Text XML helpers for table cells."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .shape_payloads import _paragraph_runs_and_line_breaks
from .shape_xml import (
    _insert_paragraph_line_break,
    _paragraph_default_run_properties_element,
    _paragraph_properties_element,
    _set_hyperlink_address,
    _set_paragraph_alignment,
    _set_paragraph_font_properties,
    _set_paragraph_level,
    _set_paragraph_spacing,
)
from .text_xml import (
    _clear_text_frame_auto_size_children,
    _end_paragraph_run_properties_element,
    _set_fit_font_properties,
    _text_character_properties_element,
    _text_frame_auto_size_insert_index,
)
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _table_cell_body_properties_element(cell_element: ET.Element) -> ET.Element:
    text_body = cell_element.find(f"{{{A_NS}}}txBody")
    if text_body is None:
        text_body = ET.Element(f"{{{A_NS}}}txBody")
        cell_element.insert(0, text_body)
    body_properties = text_body.find(f"{{{A_NS}}}bodyPr")
    if body_properties is not None:
        return body_properties
    body_properties = ET.Element(f"{{{A_NS}}}bodyPr")
    text_body.insert(0, body_properties)
    return body_properties


def _table_cell_text_body_element(cell_element: ET.Element) -> ET.Element:
    text_body = cell_element.find(f"{{{A_NS}}}txBody")
    if text_body is None:
        text_body = ET.Element(f"{{{A_NS}}}txBody")
        cell_element.insert(0, text_body)
    _table_cell_body_properties_element(cell_element)
    if text_body.find(f"{{{A_NS}}}lstStyle") is None:
        lst_style = ET.Element(f"{{{A_NS}}}lstStyle")
        insert_at = 1 if text_body.find(f"{{{A_NS}}}bodyPr") is not None else 0
        text_body.insert(insert_at, lst_style)
    return text_body


def _set_table_cell_text_frame_paragraph_xml(
    cell_element: ET.Element,
    paragraphs: list[str],
) -> None:
    text_body = _table_cell_text_body_element(cell_element)
    for paragraph in list(text_body.findall(f"{{{A_NS}}}p")):
        text_body.remove(paragraph)
    insert_at = len(text_body)
    for index, child in enumerate(list(text_body)):
        if _xml_local_name(child.tag) == "extLst":
            insert_at = index
            break
    for paragraph_text in [str(paragraph) for paragraph in paragraphs] or [""]:
        text_body.insert(insert_at, _a_text_paragraph_element(paragraph_text))
        insert_at += 1


def _set_table_cell_text_frame_paragraph_properties(
    cell_element: ET.Element,
    paragraph_properties_edits: dict[int, dict[str, Any]],
) -> None:
    text_body = _table_cell_text_body_element(cell_element)
    paragraphs = text_body.findall(f"{{{A_NS}}}p")
    for paragraph_index, edits in paragraph_properties_edits.items():
        try:
            paragraph = paragraphs[paragraph_index]
        except IndexError as exc:
            raise IndexError("paragraph index out of range") from exc
        paragraph_properties = _paragraph_properties_element(paragraph)
        if "alignment" in edits:
            _set_paragraph_alignment(paragraph_properties, edits["alignment"])
        if "level" in edits:
            _set_paragraph_level(paragraph_properties, int(edits["level"]))
        if "spacing" in edits:
            _set_paragraph_spacing(paragraph_properties, edits["spacing"])
        if "font" in edits:
            default_run_properties = _paragraph_default_run_properties_element(
                paragraph
            )
            _set_paragraph_font_properties(default_run_properties, edits["font"])
        if "runs" in edits:
            _set_paragraph_runs(paragraph, edits["runs"])
        for run_slot in edits.get("line_breaks", []):
            _insert_paragraph_line_break(paragraph, int(run_slot))


def _has_table_cell_run_hyperlink_edits(
    paragraph_run_properties_edits: dict[int, dict[int, dict[str, Any]]],
) -> bool:
    return any(
        "hyperlink" in edits
        for run_edits in paragraph_run_properties_edits.values()
        for edits in run_edits.values()
    )


def _set_table_cell_text_frame_paragraph_run_properties(
    cell_element: ET.Element,
    paragraph_run_properties_edits: dict[int, dict[int, dict[str, Any]]],
    rels_root: ET.Element | None,
) -> None:
    text_body = _table_cell_text_body_element(cell_element)
    paragraphs = text_body.findall(f"{{{A_NS}}}p")
    for paragraph_index, run_edits in paragraph_run_properties_edits.items():
        try:
            paragraph = paragraphs[paragraph_index]
        except IndexError as exc:
            raise IndexError("paragraph index out of range") from exc
        runs = paragraph.findall(f"{{{A_NS}}}r")
        for run_index, edits in run_edits.items():
            try:
                run = runs[run_index]
            except IndexError as exc:
                raise IndexError("run index out of range") from exc
            if "font" in edits:
                _set_paragraph_font_properties(
                    _text_character_properties_element(run),
                    edits["font"],
                )
            if "hyperlink" in edits:
                if rels_root is None:
                    raise ValueError("relationship root is required for hyperlinks")
                _set_hyperlink_address(
                    _text_character_properties_element(run),
                    rels_root,
                    edits["hyperlink"],
                )


def _a_text_paragraph_element(text: str) -> ET.Element:
    paragraph = ET.Element(f"{{{A_NS}}}p")
    runs, line_breaks = _paragraph_runs_and_line_breaks(text)
    if not runs and not line_breaks:
        return paragraph
    for run_slot in range(len(runs) + 1):
        for _slot in (slot for slot in line_breaks if slot == run_slot):
            ET.SubElement(paragraph, f"{{{A_NS}}}br")
        if run_slot < len(runs):
            run = ET.SubElement(paragraph, f"{{{A_NS}}}r")
            text_node = ET.SubElement(run, f"{{{A_NS}}}t")
            text_node.text = runs[run_slot]
    return paragraph


def _set_paragraph_runs(paragraph: ET.Element, runs: list[str]) -> None:
    for child in list(paragraph):
        if child.tag in {f"{{{A_NS}}}r", f"{{{A_NS}}}br"}:
            paragraph.remove(child)
    insert_at = len(paragraph)
    for index, child in enumerate(list(paragraph)):
        if _xml_local_name(child.tag) in {"endParaRPr", "extLst"}:
            insert_at = index
            break
    for run_text in runs:
        run = ET.Element(f"{{{A_NS}}}r")
        text_node = ET.SubElement(run, f"{{{A_NS}}}t")
        text_node.text = str(run_text)
        paragraph.insert(insert_at, run)
        insert_at += 1


def _set_table_cell_text_frame_fit(
    cell_element: ET.Element,
    fit: dict[str, Any],
) -> None:
    body_properties = _table_cell_body_properties_element(cell_element)
    body_properties.set("wrap", "square")
    _clear_text_frame_auto_size_children(body_properties)
    body_properties.insert(
        _text_frame_auto_size_insert_index(body_properties),
        ET.Element(f"{{{A_NS}}}noAutofit"),
    )
    text_body = _table_cell_text_body_element(cell_element)
    for paragraph in text_body.findall(f"{{{A_NS}}}p"):
        for child in list(paragraph):
            if _xml_local_name(child.tag) not in {"r", "br", "fld"}:
                continue
            _set_fit_font_properties(_text_character_properties_element(child), fit)
        _set_fit_font_properties(_end_paragraph_run_properties_element(paragraph), fit)
