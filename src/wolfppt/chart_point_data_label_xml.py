"""XML helpers for chart point data-label text and run formatting."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .chart_point_facade_xml import _data_label_insert_index
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
from .text_xml import (
    _clear_text_frame_auto_size_children,
    _text_frame_auto_size_insert_index,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def set_point_data_label_position(label: ET.Element, value: str | None) -> None:
    position = label.find(f"{{{C_NS}}}dLblPos")
    if value is None:
        if position is not None:
            label.remove(position)
        return
    if position is None:
        position = ET.Element(f"{{{C_NS}}}dLblPos")
        label.insert(_data_label_insert_index(label, "dLblPos"), position)
    position.set("val", value)


def point_data_label_text_default_run_properties(label: ET.Element) -> ET.Element:
    text_properties = label.find(f"{{{C_NS}}}txPr")
    if text_properties is None:
        text_properties = ET.Element(f"{{{C_NS}}}txPr")
        text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
        text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
        paragraph = ET.Element(f"{{{A_NS}}}p")
        paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
        text_properties.append(paragraph)
        label.insert(_data_label_insert_index(label, "txPr"), text_properties)
    run_properties = text_properties.find(
        f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )
    if run_properties is not None:
        return run_properties
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


def set_point_data_label_text_frame(label: ET.Element, enabled: bool) -> None:
    text = label.find(f"{{{C_NS}}}tx")
    if not enabled:
        if text is not None:
            label.remove(text)
        return
    if text is None:
        text = ET.Element(f"{{{C_NS}}}tx")
        label.insert(_data_label_insert_index(label, "tx"), text)
    if text.find(f"{{{C_NS}}}rich") is None:
        text.append(rich_text_element())


def set_point_data_label_text(label: ET.Element, value: str) -> None:
    set_point_data_label_paragraphs(label, value.split("\n") if value else [""])


def set_point_data_label_text_frame_fit(
    label: ET.Element,
    fit: dict[str, Any],
) -> None:
    set_point_data_label_text_frame(label, True)
    body_properties = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich/{{{A_NS}}}bodyPr")
    if body_properties is None:
        rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
        assert rich is not None
        body_properties = ET.Element(f"{{{A_NS}}}bodyPr")
        rich.insert(0, body_properties)
    body_properties.set("wrap", "square")
    _clear_text_frame_auto_size_children(body_properties)
    body_properties.insert(
        _text_frame_auto_size_insert_index(body_properties),
        ET.Element(f"{{{A_NS}}}noAutofit"),
    )
    rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        return
    properties = {
        "bold": bool(fit["bold"]),
        "italic": bool(fit["italic"]),
        "size": int(fit["size"]),
        "name": str(fit["font_family"]),
    }
    for paragraph in rich.findall(f"{{{A_NS}}}p"):
        for child in list(paragraph):
            if child.tag.rsplit("}", 1)[-1] not in {"r", "br", "fld"}:
                continue
            run_properties = child.find(f"{{{A_NS}}}rPr")
            if run_properties is None:
                run_properties = ET.Element(f"{{{A_NS}}}rPr")
                child.insert(0, run_properties)
            set_run_properties_font(run_properties, properties)
        end_properties = paragraph.find(f"{{{A_NS}}}endParaRPr")
        if end_properties is None:
            end_properties = ET.Element(f"{{{A_NS}}}endParaRPr")
            paragraph.insert(
                _paragraph_end_properties_insert_index(paragraph),
                end_properties,
            )
        set_run_properties_font(end_properties, properties)


def set_point_data_label_paragraphs(
    label: ET.Element,
    paragraphs: list[str],
) -> None:
    paragraph_runs = []
    paragraph_break_slots = []
    for paragraph in paragraphs:
        runs, break_slots = _split_paragraph_text(str(paragraph))
        paragraph_runs.append(runs)
        paragraph_break_slots.append(break_slots)
    set_point_data_label_paragraph_runs(
        label,
        paragraph_runs,
        preserve_line_breaks=False,
    )
    for paragraph_index, break_slots in enumerate(paragraph_break_slots):
        for run_slot in break_slots:
            insert_point_data_label_paragraph_line_break(
                label,
                paragraph_index,
                run_slot,
            )


def set_point_data_label_paragraph_runs(
    label: ET.Element,
    paragraph_runs: list[list[str]],
    *,
    preserve_line_breaks: bool = True,
) -> None:
    text = label.find(f"{{{C_NS}}}tx")
    existing_body_properties = None
    existing_paragraph_properties: list[ET.Element | None] = []
    existing_line_break_slots: list[list[int]] = []
    if text is not None:
        existing_rich = text.find(f"{{{C_NS}}}rich")
        if existing_rich is not None:
            existing_body_properties = existing_rich.find(f"{{{A_NS}}}bodyPr")
            for paragraph in existing_rich.findall(f"{{{A_NS}}}p"):
                existing_paragraph_properties.append(
                    paragraph.find(f"{{{A_NS}}}pPr")
                )
                existing_line_break_slots.append(
                    _paragraph_line_break_slots(paragraph)
                    if preserve_line_breaks
                    else []
                )
    if text is not None:
        label.remove(text)
    text = ET.Element(f"{{{C_NS}}}tx")
    rich = ET.SubElement(text, f"{{{C_NS}}}rich")
    if existing_body_properties is None:
        ET.SubElement(rich, f"{{{A_NS}}}bodyPr")
    else:
        rich.append(deepcopy(existing_body_properties))
    ET.SubElement(rich, f"{{{A_NS}}}lstStyle")
    for index, runs in enumerate(paragraph_runs):
        paragraph = ET.SubElement(rich, f"{{{A_NS}}}p")
        if index < len(existing_paragraph_properties):
            paragraph_properties = existing_paragraph_properties[index]
            if paragraph_properties is not None:
                paragraph.append(deepcopy(paragraph_properties))
        break_slots = (
            existing_line_break_slots[index]
            if index < len(existing_line_break_slots)
            else []
        )
        for run_slot, run_text in enumerate(runs):
            for _ in range(break_slots.count(run_slot)):
                ET.SubElement(paragraph, f"{{{A_NS}}}br")
            run = ET.SubElement(paragraph, f"{{{A_NS}}}r")
            text_node = ET.SubElement(run, f"{{{A_NS}}}t")
            text_node.text = run_text
        for _ in range(break_slots.count(len(runs))):
            ET.SubElement(paragraph, f"{{{A_NS}}}br")
    label.insert(_data_label_insert_index(label, "tx"), text)


def insert_point_data_label_paragraph_line_break(
    label: ET.Element,
    paragraph_index: int,
    run_slot: int,
) -> None:
    rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        set_point_data_label_paragraph_runs(label, [[]])
        rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich is not None
    paragraphs = rich.findall(f"{{{A_NS}}}p")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        raise IndexError("chart data label paragraph index out of range")
    paragraph = paragraphs[paragraph_index]
    run_count = len(paragraph.findall(f"{{{A_NS}}}r"))
    if run_slot < 0 or run_slot > run_count:
        raise IndexError("chart data label run slot out of range")
    paragraph.insert(
        _paragraph_line_break_insert_index(paragraph, run_slot),
        ET.Element(f"{{{A_NS}}}br"),
    )


def set_run_properties_font(
    run_properties: ET.Element,
    properties: dict[str, Any],
) -> None:
    if "bold" in properties:
        value = properties["bold"]
        if value is None:
            run_properties.attrib.pop("b", None)
        else:
            run_properties.set("b", "1" if bool(value) else "0")
    if "italic" in properties:
        value = properties["italic"]
        if value is None:
            run_properties.attrib.pop("i", None)
        else:
            run_properties.set("i", "1" if bool(value) else "0")
    if "underline" in properties:
        value = properties["underline"]
        if value is None:
            run_properties.attrib.pop("u", None)
        else:
            run_properties.set("u", "sng" if bool(value) else "none")
    if "size" in properties:
        value = properties["size"]
        if value is None:
            run_properties.attrib.pop("sz", None)
        else:
            run_properties.set("sz", str(_emu_to_centipoints(int(value))))
    if "rgb" in properties:
        value = properties["rgb"]
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if value is None:
            if solid_fill is not None:
                run_properties.remove(solid_fill)
        else:
            solid_fill = _run_solid_fill_element(run_properties)
            _set_solid_fill_rgb(solid_fill, str(value))
    if "fill_type" in properties:
        value = properties["fill_type"]
        if value == "solid":
            if run_properties.find(f"{{{A_NS}}}solidFill") is None:
                _run_solid_fill_element(run_properties)
            no_fill = run_properties.find(f"{{{A_NS}}}noFill")
            if no_fill is not None:
                run_properties.remove(no_fill)
        elif value == "background":
            _run_no_fill_element(run_properties)
        elif value == "patterned":
            if run_properties.find(f"{{{A_NS}}}pattFill") is None:
                _run_pattern_fill_element(run_properties)
        elif value == "gradient":
            if run_properties.find(f"{{{A_NS}}}gradFill") is None:
                _run_gradient_fill_element(run_properties)
        elif value is not None:
            raise ValueError(f"unsupported chart data-label font fill: {value!r}")
    if "pattern" in properties:
        _set_run_pattern_fill(run_properties, properties["pattern"])
    if "pattern_fore_rgb" in properties and properties["pattern_fore_rgb"] is not None:
        _set_run_pattern_fill_color(
            run_properties,
            "fgClr",
            str(properties["pattern_fore_rgb"]),
        )
    if "pattern_back_rgb" in properties and properties["pattern_back_rgb"] is not None:
        _set_run_pattern_fill_color(
            run_properties,
            "bgClr",
            str(properties["pattern_back_rgb"]),
        )
    if "gradient" in properties:
        _set_run_gradient_fill(run_properties, properties["gradient"])
    if "name" in properties:
        value = properties["name"]
        latin = run_properties.find(f"{{{A_NS}}}latin")
        if value is None:
            if latin is not None:
                run_properties.remove(latin)
        else:
            if latin is None:
                latin = ET.Element(f"{{{A_NS}}}latin")
                run_properties.append(latin)
            latin.set("typeface", str(value))
    if "language_id" in properties:
        value = properties["language_id"]
        if value is None:
            run_properties.attrib.pop("lang", None)
        else:
            run_properties.set("lang", str(value))


def point_data_label_run_element(
    label: ET.Element,
    paragraph_index: int,
    run_index: int,
    *,
    create: bool,
) -> ET.Element | None:
    rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        if not create:
            return None
        set_point_data_label_paragraph_runs(label, [[]])
        rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich is not None
    paragraphs = rich.findall(f"{{{A_NS}}}p")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        return None
    runs = paragraphs[paragraph_index].findall(f"{{{A_NS}}}r")
    if run_index < 0 or run_index >= len(runs):
        return None
    return runs[run_index]


def point_data_label_text(label: ET.Element) -> str:
    return "\n".join(point_data_label_paragraph_texts(label))


def point_data_label_position_xml(label: ET.Element) -> str | None:
    position = label.find(f"{{{C_NS}}}dLblPos")
    return None if position is None else position.attrib.get("val")


def point_data_label_paragraph_texts(label: ET.Element) -> list[str]:
    rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        return [""]
    texts = [_paragraph_text(paragraph) for paragraph in rich.findall(f"{{{A_NS}}}p")]
    return texts or [""]


def point_data_label_paragraph_run_texts(label: ET.Element) -> list[list[str]]:
    rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        return [[]]
    paragraphs: list[list[str]] = []
    for paragraph in rich.findall(f"{{{A_NS}}}p"):
        runs = [
            text_node.text or ""
            for run in paragraph.findall(f"{{{A_NS}}}r")
            for text_node in run.findall(f"{{{A_NS}}}t")
        ]
        paragraphs.append(runs)
    return paragraphs or [[]]


def point_data_label_paragraph_line_breaks(label: ET.Element) -> list[dict[str, int]]:
    rich = label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        return []
    line_breaks: list[dict[str, int]] = []
    for paragraph_index, paragraph in enumerate(rich.findall(f"{{{A_NS}}}p")):
        for run_slot in _paragraph_line_break_slots(paragraph):
            line_breaks.append(
                {
                    "paragraph_index": paragraph_index,
                    "run_slot": run_slot,
                }
            )
    return line_breaks


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for child in list(paragraph):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name == "r":
            parts.extend(
                text_node.text or ""
                for text_node in child.findall(f"{{{A_NS}}}t")
            )
        elif local_name == "br":
            parts.append("\v")
    return "".join(parts)


def _split_paragraph_text(text: str) -> tuple[list[str], list[int]]:
    runs: list[str] = []
    break_slots: list[int] = []
    current: list[str] = []
    for char in text:
        if char == "\v":
            if current:
                runs.append("".join(current))
                current = []
            break_slots.append(len(runs))
            continue
        current.append(char)
    if current:
        runs.append("".join(current))
    return runs, break_slots


def _paragraph_line_break_slots(paragraph: ET.Element) -> list[int]:
    slots: list[int] = []
    run_slot = 0
    for child in list(paragraph):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name == "r":
            run_slot += 1
        elif local_name == "br":
            slots.append(run_slot)
    return slots


def _paragraph_line_break_insert_index(paragraph: ET.Element, run_slot: int) -> int:
    current_run_slot = 0
    insert_index = 0
    for index, child in enumerate(list(paragraph)):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name == "pPr":
            insert_index = index + 1
            continue
        if local_name != "r":
            continue
        if current_run_slot >= run_slot:
            return index
        current_run_slot += 1
        insert_index = index + 1
    return insert_index


def _paragraph_end_properties_insert_index(paragraph: ET.Element) -> int:
    for index, child in enumerate(list(paragraph)):
        if child.tag.rsplit("}", 1)[-1] == "extLst":
            return index
    return len(paragraph)


def set_point_data_label_text_properties(label: ET.Element) -> None:
    if label.find(f"{{{C_NS}}}txPr") is not None:
        return
    text_properties = ET.Element(f"{{{C_NS}}}txPr")
    text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
    text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
    paragraph = ET.Element(f"{{{A_NS}}}p")
    paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
    ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
    text_properties.append(paragraph)
    label.insert(_data_label_insert_index(label, "txPr"), text_properties)


def rich_text_element() -> ET.Element:
    rich = ET.Element(f"{{{C_NS}}}rich")
    rich.append(ET.Element(f"{{{A_NS}}}bodyPr"))
    rich.append(ET.Element(f"{{{A_NS}}}lstStyle"))
    paragraph = ET.Element(f"{{{A_NS}}}p")
    paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
    ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
    rich.append(paragraph)
    return rich
