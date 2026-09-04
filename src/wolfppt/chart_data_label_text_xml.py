"""Chart data-label text and font XML helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

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
from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
    emu_to_centipoints as _emu_to_centipoints,
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
)
from .text_xml import (
    _clear_text_frame_auto_size_children,
    _text_frame_auto_size_insert_index,
)
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"

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


def set_chart_data_label_position(data_labels: ET.Element, value: Any) -> None:
    position = data_labels.find(f"{{{C_NS}}}dLblPos")
    if value is None:
        if position is not None:
            data_labels.remove(position)
        return
    if position is None:
        position = ET.Element(f"{{{C_NS}}}dLblPos")
        data_labels.insert(data_label_insert_index(data_labels, "dLblPos"), position)
    position.set("val", str(value))


def set_chart_data_label_number_format(
    data_labels: ET.Element,
    format_code: str,
) -> None:
    num_fmt = _chart_data_label_num_fmt_element(data_labels)
    num_fmt.set("formatCode", format_code)
    num_fmt.set("sourceLinked", "0")


def set_chart_data_label_number_format_source_linked(
    data_labels: ET.Element,
    source_linked: bool,
) -> None:
    num_fmt = _chart_data_label_num_fmt_element(data_labels)
    if num_fmt.get("formatCode") is None:
        num_fmt.set("formatCode", "General")
    num_fmt.set("sourceLinked", "1" if source_linked else "0")


def set_chart_data_label_font_size(data_labels: ET.Element, value: Any) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        run_properties.attrib.pop("sz", None)
        return
    run_properties.set("sz", str(_emu_to_centipoints(int(value))))


def set_chart_data_label_font_bool(
    data_labels: ET.Element,
    attr: str,
    value: bool | None,
) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        run_properties.attrib.pop(attr, None)
        return
    run_properties.set(attr, "1" if bool(value) else "0")


def set_chart_data_label_font_underline(
    data_labels: ET.Element,
    value: bool | None,
) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        run_properties.attrib.pop("u", None)
        return
    run_properties.set("u", "sng" if bool(value) else "none")


def set_chart_data_label_font_rgb(
    data_labels: ET.Element,
    value: str | None,
) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if solid_fill is not None:
            run_properties.remove(solid_fill)
        return
    solid_fill = _run_solid_fill_element(run_properties)
    _set_solid_fill_rgb(solid_fill, value)


def set_chart_data_label_font_fill_type(
    data_labels: ET.Element,
    value: str,
) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
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


def set_chart_data_label_font_pattern(
    data_labels: ET.Element,
    value: str | None,
) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    _set_run_pattern_fill(run_properties, value)


def set_chart_data_label_font_pattern_rgb(
    data_labels: ET.Element,
    color_tag: str,
    value: str | None,
) -> None:
    if value is None:
        return
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    _set_run_pattern_fill_color(run_properties, color_tag, value)


def set_chart_data_label_font_gradient(
    data_labels: ET.Element,
    value: dict[str, Any],
) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    _set_run_gradient_fill(run_properties, value)


def set_chart_data_label_font_name(
    data_labels: ET.Element,
    value: str | None,
) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if value is None:
        if latin is not None:
            run_properties.remove(latin)
        return
    if latin is None:
        latin = ET.Element(f"{{{A_NS}}}latin")
        run_properties.append(latin)
    latin.set("typeface", value)


def set_chart_data_label_font_language_id(
    data_labels: ET.Element,
    value: str | None,
) -> None:
    run_properties = chart_data_label_text_default_run_properties(data_labels)
    if value is None:
        run_properties.attrib.pop("lang", None)
    else:
        run_properties.set("lang", value)


def set_chart_data_label_text_frame(data_label: ET.Element, enabled: bool) -> None:
    text = data_label.find(f"{{{C_NS}}}tx")
    if not enabled:
        if text is not None:
            data_label.remove(text)
        return
    if text is None:
        text = ET.Element(f"{{{C_NS}}}tx")
        data_label.insert(data_label_insert_index(data_label, "tx"), text)
    if text.find(f"{{{C_NS}}}rich") is None:
        text.append(chart_rich_text_element())


def set_chart_data_label_text(data_label: ET.Element, value: str) -> None:
    set_chart_data_label_paragraphs(data_label, value.split("\n") if value else [""])


def set_chart_data_label_text_frame_fit(
    data_label: ET.Element,
    fit: dict[str, Any],
) -> None:
    set_chart_data_label_text_frame(data_label, True)
    body_properties = chart_data_label_body_properties(data_label, create=True)
    assert body_properties is not None
    body_properties.set("wrap", "square")
    _clear_text_frame_auto_size_children(body_properties)
    body_properties.insert(
        _text_frame_auto_size_insert_index(body_properties),
        ET.Element(f"{{{A_NS}}}noAutofit"),
    )
    rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich_text is None:
        return
    properties = {
        "bold": bool(fit["bold"]),
        "italic": bool(fit["italic"]),
        "size": int(fit["size"]),
        "name": str(fit["font_family"]),
    }
    for paragraph in rich_text.findall(f"{{{A_NS}}}p"):
        for child in list(paragraph):
            if child.tag.rsplit("}", 1)[-1] not in {"r", "br", "fld"}:
                continue
            run_properties = child.find(f"{{{A_NS}}}rPr")
            if run_properties is None:
                run_properties = ET.Element(f"{{{A_NS}}}rPr")
                child.insert(0, run_properties)
            set_chart_data_label_run_font_properties(run_properties, properties)
        end_properties = paragraph.find(f"{{{A_NS}}}endParaRPr")
        if end_properties is None:
            end_properties = ET.Element(f"{{{A_NS}}}endParaRPr")
            paragraph.insert(
                _paragraph_end_properties_insert_index(paragraph),
                end_properties,
            )
        set_chart_data_label_run_font_properties(end_properties, properties)


def set_chart_data_label_paragraphs(
    data_label: ET.Element,
    paragraphs: list[str],
) -> None:
    paragraph_runs = []
    paragraph_break_slots = []
    for paragraph in paragraphs:
        runs, break_slots = _split_paragraph_text(str(paragraph))
        paragraph_runs.append(runs)
        paragraph_break_slots.append(break_slots)
    set_chart_data_label_paragraph_runs(
        data_label,
        paragraph_runs,
        preserve_line_breaks=False,
    )
    for paragraph_index, break_slots in enumerate(paragraph_break_slots):
        for run_slot in break_slots:
            insert_chart_data_label_paragraph_line_break(
                data_label,
                paragraph_index,
                run_slot,
            )


def set_chart_data_label_paragraph_runs(
    data_label: ET.Element,
    paragraph_runs: list[list[str]],
    *,
    preserve_line_breaks: bool = True,
) -> None:
    text = data_label.find(f"{{{C_NS}}}tx")
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
        data_label.remove(text)
    text = ET.Element(f"{{{C_NS}}}tx")
    rich_text = ET.SubElement(text, f"{{{C_NS}}}rich")
    if existing_body_properties is None:
        ET.SubElement(rich_text, f"{{{A_NS}}}bodyPr")
    else:
        rich_text.append(deepcopy(existing_body_properties))
    ET.SubElement(rich_text, f"{{{A_NS}}}lstStyle")
    for index, runs in enumerate(paragraph_runs):
        paragraph = ET.SubElement(rich_text, f"{{{A_NS}}}p")
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
    data_label.insert(data_label_insert_index(data_label, "tx"), text)


def chart_data_label_paragraph_properties(
    data_label: ET.Element,
    paragraph_index: int,
    *,
    create: bool,
) -> ET.Element | None:
    rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich_text is None:
        if not create:
            return None
        set_chart_data_label_paragraph_runs(data_label, [[]])
        rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich_text is not None
    paragraphs = rich_text.findall(f"{{{A_NS}}}p")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        return None
    paragraph_properties = paragraphs[paragraph_index].find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None and create:
        paragraph_properties = ET.Element(f"{{{A_NS}}}pPr")
        paragraphs[paragraph_index].insert(0, paragraph_properties)
    return paragraph_properties


def chart_data_label_paragraph_default_run_properties(
    data_label: ET.Element,
    paragraph_index: int,
    *,
    create: bool,
) -> ET.Element | None:
    paragraph_properties = chart_data_label_paragraph_properties(
        data_label,
        paragraph_index,
        create=create,
    )
    if paragraph_properties is None:
        return None
    run_properties = paragraph_properties.find(f"{{{A_NS}}}defRPr")
    if run_properties is None and create:
        run_properties = ET.Element(f"{{{A_NS}}}defRPr")
        paragraph_properties.append(run_properties)
    return run_properties


def set_chart_data_label_paragraph_format(
    data_label: ET.Element,
    paragraph_index: int,
    properties: dict[str, Any],
) -> None:
    paragraph_properties = chart_data_label_paragraph_properties(
        data_label,
        paragraph_index,
        create=True,
    )
    assert paragraph_properties is not None
    if "alignment" in properties:
        alignment = properties["alignment"]
        if alignment is None:
            paragraph_properties.attrib.pop("algn", None)
        else:
            paragraph_properties.set("algn", str(alignment))
    if "level" in properties:
        level = int(properties["level"])
        if level == 0:
            paragraph_properties.attrib.pop("lvl", None)
        else:
            paragraph_properties.set("lvl", str(level))
    spacing = {
        key: properties[key]
        for key in ("line_spacing", "space_before", "space_after")
        if key in properties
    }
    _set_chart_data_label_paragraph_spacing(paragraph_properties, spacing)
    if "font" in properties:
        run_properties = chart_data_label_paragraph_default_run_properties(
            data_label,
            paragraph_index,
            create=True,
        )
        assert run_properties is not None
        set_chart_data_label_run_font_properties(
            run_properties,
            dict(properties["font"]),
        )


def insert_chart_data_label_paragraph_line_break(
    data_label: ET.Element,
    paragraph_index: int,
    run_slot: int,
) -> None:
    rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich_text is None:
        set_chart_data_label_paragraph_runs(data_label, [[]])
        rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich_text is not None
    paragraphs = rich_text.findall(f"{{{A_NS}}}p")
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


def set_chart_data_label_run_formats(data_label: ET.Element, edits: Any) -> None:
    for edit in edits:
        run = chart_data_label_run_element(
            data_label,
            int(edit["paragraph_index"]),
            int(edit["run_index"]),
        )
        run_properties = run.find(f"{{{A_NS}}}rPr")
        if run_properties is None:
            run_properties = ET.Element(f"{{{A_NS}}}rPr")
            run.insert(0, run_properties)
        set_chart_data_label_run_font_properties(
            run_properties,
            edit.get("properties", {}),
        )


def set_chart_data_label_text_properties(data_label: ET.Element) -> None:
    if data_label.find(f"{{{C_NS}}}txPr") is not None:
        return
    text_properties = ET.Element(f"{{{C_NS}}}txPr")
    text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
    text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
    paragraph = ET.Element(f"{{{A_NS}}}p")
    paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
    ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
    text_properties.append(paragraph)
    data_label.insert(data_label_insert_index(data_label, "txPr"), text_properties)


def chart_data_label_body_properties(
    data_label: ET.Element,
    *,
    create: bool = False,
) -> ET.Element | None:
    rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich_text is None:
        if not create:
            return None
        set_chart_data_label_text_frame(data_label, True)
        rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich_text is not None
    body_properties = rich_text.find(f"{{{A_NS}}}bodyPr")
    if body_properties is not None:
        return body_properties
    if not create:
        return None
    body_properties = ET.Element(f"{{{A_NS}}}bodyPr")
    rich_text.insert(0, body_properties)
    return body_properties


def set_chart_data_label_body_margin(
    data_label: ET.Element,
    attr: str,
    value: int,
) -> None:
    body_properties = chart_data_label_body_properties(data_label, create=True)
    assert body_properties is not None
    body_properties.set(attr, str(int(value)))


def set_chart_data_label_word_wrap(
    data_label: ET.Element,
    value: bool | None,
) -> None:
    body_properties = chart_data_label_body_properties(data_label, create=True)
    assert body_properties is not None
    if value is None:
        body_properties.attrib.pop("wrap", None)
    else:
        body_properties.set("wrap", "square" if value else "none")


def set_chart_data_label_vertical_anchor(
    data_label: ET.Element,
    value: str | None,
) -> None:
    body_properties = chart_data_label_body_properties(data_label, create=True)
    assert body_properties is not None
    if value is None:
        body_properties.attrib.pop("anchor", None)
    else:
        body_properties.set("anchor", value)


def set_chart_data_label_auto_size(
    data_label: ET.Element,
    value: str | None,
) -> None:
    body_properties = chart_data_label_body_properties(data_label, create=True)
    assert body_properties is not None
    _clear_text_frame_auto_size_children(body_properties)
    if value is not None:
        body_properties.insert(
            _text_frame_auto_size_insert_index(body_properties),
            ET.Element(f"{{{A_NS}}}{value}"),
        )


def data_label_insert_index(data_labels: ET.Element, local_name: str) -> int:
    target_order = _DATA_LABEL_CHILD_INDEX.get(local_name)
    if target_order is None:
        return len(data_labels)
    for index, child in enumerate(list(data_labels)):
        child_order = _DATA_LABEL_CHILD_INDEX.get(_xml_local_name(child.tag))
        if child_order is not None and child_order > target_order:
            return index
    return len(data_labels)


def _chart_data_label_num_fmt_element(data_labels: ET.Element) -> ET.Element:
    num_fmt = data_labels.find(f"{{{C_NS}}}numFmt")
    if num_fmt is not None:
        return num_fmt
    num_fmt = ET.Element(f"{{{C_NS}}}numFmt")
    data_labels.insert(data_label_insert_index(data_labels, "numFmt"), num_fmt)
    return num_fmt


def chart_data_label_text_default_run_properties(
    data_labels: ET.Element,
) -> ET.Element:
    text_properties = data_labels.find(f"{{{C_NS}}}txPr")
    if text_properties is None:
        text_properties = ET.Element(f"{{{C_NS}}}txPr")
        text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
        text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
        paragraph = ET.Element(f"{{{A_NS}}}p")
        paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
        text_properties.append(paragraph)
        data_labels.insert(data_label_insert_index(data_labels, "txPr"), text_properties)
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


def chart_data_label_run_element(
    data_label: ET.Element,
    paragraph_index: int,
    run_index: int,
) -> ET.Element:
    rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich_text is None:
        set_chart_data_label_paragraph_runs(data_label, [[]])
        rich_text = data_label.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich_text is not None
    paragraphs = rich_text.findall(f"{{{A_NS}}}p")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        raise IndexError("chart data label paragraph index out of range")
    runs = paragraphs[paragraph_index].findall(f"{{{A_NS}}}r")
    if run_index < 0 or run_index >= len(runs):
        raise IndexError("chart data label run index out of range")
    return runs[run_index]


def chart_data_label_paragraph_spacing_value(
    paragraph_properties: ET.Element | None,
    attr: str,
) -> int | float | None:
    if paragraph_properties is None:
        return None
    spacing = paragraph_properties.find(
        f"{{{A_NS}}}{_paragraph_spacing_xml_tag(attr)}"
    )
    if spacing is None:
        return None
    spacing_points = spacing.find(f"{{{A_NS}}}spcPts")
    if spacing_points is not None:
        try:
            return _centipoints_to_emu(int(spacing_points.attrib["val"]))
        except (KeyError, ValueError):
            return None
    if attr == "line_spacing":
        spacing_percent = spacing.find(f"{{{A_NS}}}spcPct")
        if spacing_percent is not None:
            try:
                return int(spacing_percent.attrib["val"]) / 100000
            except (KeyError, ValueError):
                return None
    return None


def _set_chart_data_label_paragraph_spacing(
    paragraph_properties: ET.Element,
    spacing: dict[str, int | float | None],
) -> None:
    for attr in ("line_spacing", "space_before", "space_after"):
        if attr not in spacing:
            continue
        _set_chart_data_label_paragraph_spacing_value(
            paragraph_properties,
            _paragraph_spacing_xml_tag(attr),
            spacing[attr],
        )


def _set_chart_data_label_paragraph_spacing_value(
    paragraph_properties: ET.Element,
    tag: str,
    value: int | float | None,
) -> None:
    _remove_chart_data_label_paragraph_spacing_child(paragraph_properties, tag)
    if value is None:
        return
    spacing = ET.Element(f"{{{A_NS}}}{tag}")
    if tag == "lnSpc" and isinstance(value, float):
        ET.SubElement(spacing, f"{{{A_NS}}}spcPct").set(
            "val",
            str(int(round(value * 100000))),
        )
    else:
        ET.SubElement(spacing, f"{{{A_NS}}}spcPts").set(
            "val",
            str(_emu_to_centipoints(int(value))),
        )
    paragraph_properties.insert(
        _chart_data_label_paragraph_spacing_insert_index(paragraph_properties, tag),
        spacing,
    )


def _remove_chart_data_label_paragraph_spacing_child(
    paragraph_properties: ET.Element,
    tag: str,
) -> None:
    for child in list(paragraph_properties):
        if child.tag.rsplit("}", 1)[-1] == tag:
            paragraph_properties.remove(child)


def _chart_data_label_paragraph_spacing_insert_index(
    paragraph_properties: ET.Element,
    tag: str,
) -> int:
    tags = ("lnSpc", "spcBef", "spcAft")
    target_index = tags.index(tag)
    insert_index = 0
    for index, child in enumerate(list(paragraph_properties)):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name not in tags:
            continue
        if tags.index(local_name) > target_index:
            return index
        insert_index = index + 1
    return insert_index


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


def set_chart_data_label_run_font_properties(
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


def chart_rich_text_element() -> ET.Element:
    rich_text = ET.Element(f"{{{C_NS}}}rich")
    rich_text.append(ET.Element(f"{{{A_NS}}}bodyPr"))
    rich_text.append(ET.Element(f"{{{A_NS}}}lstStyle"))
    paragraph = ET.Element(f"{{{A_NS}}}p")
    paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
    ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
    rich_text.append(paragraph)
    return rich_text
