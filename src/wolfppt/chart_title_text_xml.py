"""Rich-text XML helpers for chart and axis titles."""

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

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def title_text(title: ET.Element) -> str:
    return "\n".join(title_paragraph_texts(title))


def title_body_properties(
    title: ET.Element,
    *,
    create: bool,
) -> ET.Element | None:
    rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        if not create:
            return None
        set_title_paragraph_runs(title, [[]])
        rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich is not None
    body_properties = rich.find(f"{{{A_NS}}}bodyPr")
    if body_properties is None and create:
        body_properties = ET.Element(f"{{{A_NS}}}bodyPr")
        rich.insert(0, body_properties)
    return body_properties


def title_paragraph_texts(title: ET.Element) -> list[str]:
    return ["".join(runs) for runs in title_paragraph_run_texts(title)]


def title_paragraph_run_texts(title: ET.Element) -> list[list[str]]:
    rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
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


def title_paragraph_properties(
    title: ET.Element,
    paragraph_index: int,
    *,
    create: bool,
) -> ET.Element | None:
    rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        if not create:
            return None
        set_title_paragraph_runs(title, [[]])
        rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich is not None
    paragraphs = rich.findall(f"{{{A_NS}}}p")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        return None
    paragraph_properties = paragraphs[paragraph_index].find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None and create:
        paragraph_properties = ET.Element(f"{{{A_NS}}}pPr")
        paragraphs[paragraph_index].insert(0, paragraph_properties)
    return paragraph_properties


def title_paragraph_default_run_properties(
    title: ET.Element,
    paragraph_index: int,
    *,
    create: bool,
) -> ET.Element | None:
    paragraph_properties = title_paragraph_properties(
        title,
        paragraph_index,
        create=create,
    )
    if paragraph_properties is None:
        return None
    default_run_properties = paragraph_properties.find(f"{{{A_NS}}}defRPr")
    if default_run_properties is None and create:
        default_run_properties = ET.Element(f"{{{A_NS}}}defRPr")
        paragraph_properties.append(default_run_properties)
    return default_run_properties


def set_title_text(title: ET.Element, value: str) -> None:
    set_title_paragraphs(title, value.split("\n") if value else [""])


def set_title_paragraphs(title: ET.Element, paragraphs: list[str]) -> None:
    set_title_paragraph_runs(
        title,
        [[paragraph] if paragraph else [] for paragraph in paragraphs],
    )


def set_title_paragraph_runs(
    title: ET.Element,
    paragraph_runs: list[list[str]],
) -> None:
    text = title.find(f"{{{C_NS}}}tx")
    existing_body_properties = None
    existing_paragraph_properties: list[ET.Element | None] = []
    if text is not None:
        existing_rich = text.find(f"{{{C_NS}}}rich")
        if existing_rich is not None:
            existing_body_properties = existing_rich.find(f"{{{A_NS}}}bodyPr")
            existing_paragraph_properties = [
                paragraph.find(f"{{{A_NS}}}pPr")
                for paragraph in existing_rich.findall(f"{{{A_NS}}}p")
            ]
        title.remove(text)
    text = ET.Element(f"{{{C_NS}}}tx")
    rich = ET.SubElement(text, f"{{{C_NS}}}rich")
    if existing_body_properties is None:
        ET.SubElement(rich, f"{{{A_NS}}}bodyPr")
    else:
        rich.append(deepcopy(existing_body_properties))
    ET.SubElement(rich, f"{{{A_NS}}}lstStyle")
    for index, runs in enumerate(paragraph_runs or [[]]):
        paragraph = ET.SubElement(rich, f"{{{A_NS}}}p")
        if index < len(existing_paragraph_properties):
            paragraph_properties = existing_paragraph_properties[index]
            if paragraph_properties is not None:
                paragraph.append(deepcopy(paragraph_properties))
        for run_text in runs:
            run = ET.SubElement(paragraph, f"{{{A_NS}}}r")
            text_node = ET.SubElement(run, f"{{{A_NS}}}t")
            text_node.text = run_text
    title.insert(_title_insert_index(title, "tx"), text)
    ensure_title_layout(title)


def ensure_title_layout(title: ET.Element) -> None:
    layout = title.find(f"{{{C_NS}}}layout")
    if layout is None:
        layout = ET.Element(f"{{{C_NS}}}layout")
        title.insert(_title_insert_index(title, "layout"), layout)
    overlay = title.find(f"{{{C_NS}}}overlay")
    if overlay is None:
        overlay = ET.Element(f"{{{C_NS}}}overlay")
        overlay.set("val", "0")
        title.insert(_title_insert_index(title, "overlay"), overlay)


def title_run_element(
    title: ET.Element,
    paragraph_index: int,
    run_index: int,
    *,
    create: bool,
) -> ET.Element | None:
    rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        if not create:
            return None
        set_title_paragraph_runs(title, [[]])
        rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    assert rich is not None
    paragraphs = rich.findall(f"{{{A_NS}}}p")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        return None
    runs = paragraphs[paragraph_index].findall(f"{{{A_NS}}}r")
    if run_index < 0 or run_index >= len(runs):
        return None
    return runs[run_index]


def title_run_properties(
    title: ET.Element,
    paragraph_index: int,
    run_index: int,
    *,
    create: bool,
) -> ET.Element | None:
    run = title_run_element(
        title,
        paragraph_index,
        run_index,
        create=create,
    )
    if run is None:
        return None
    run_properties = run.find(f"{{{A_NS}}}rPr")
    if run_properties is None and create:
        run_properties = ET.Element(f"{{{A_NS}}}rPr")
        run.insert(0, run_properties)
    return run_properties


def set_title_run_font(
    title: ET.Element,
    paragraph_index: int,
    run_index: int,
    properties: dict[str, Any],
) -> None:
    run_properties = title_run_properties(
        title,
        paragraph_index,
        run_index,
        create=True,
    )
    assert run_properties is not None
    _set_run_properties_font(run_properties, properties)


def set_title_paragraph_format(
    title: ET.Element,
    paragraph_index: int,
    properties: dict[str, Any],
) -> None:
    paragraph_properties = title_paragraph_properties(
        title,
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
    _set_title_paragraph_spacing(paragraph_properties, spacing)
    if "font" in properties:
        default_run_properties = title_paragraph_default_run_properties(
            title,
            paragraph_index,
            create=True,
        )
        assert default_run_properties is not None
        _set_run_properties_font(default_run_properties, dict(properties["font"]))


def set_title_body_margin(title: ET.Element, attr: str, value: int) -> None:
    body_properties = title_body_properties(title, create=True)
    assert body_properties is not None
    body_properties.set(attr, str(int(value)))


def set_title_word_wrap(title: ET.Element, value: bool | None) -> None:
    body_properties = title_body_properties(title, create=True)
    assert body_properties is not None
    if value is None:
        body_properties.attrib.pop("wrap", None)
    else:
        body_properties.set("wrap", "square" if value else "none")


def set_title_vertical_anchor(title: ET.Element, value: str | None) -> None:
    body_properties = title_body_properties(title, create=True)
    assert body_properties is not None
    if value is None:
        body_properties.attrib.pop("anchor", None)
    else:
        body_properties.set("anchor", str(value))


def set_title_auto_size(title: ET.Element, value: str | None) -> None:
    body_properties = title_body_properties(title, create=True)
    assert body_properties is not None
    _clear_auto_size_children(body_properties)
    if value is None:
        return
    body_properties.insert(
        _auto_size_insert_index(body_properties),
        ET.Element(f"{{{A_NS}}}{value}"),
    )


def set_title_text_frame_fit(title: ET.Element, fit: dict[str, Any]) -> None:
    body_properties = title_body_properties(title, create=True)
    assert body_properties is not None
    body_properties.set("wrap", "square")
    _clear_auto_size_children(body_properties)
    body_properties.insert(
        _auto_size_insert_index(body_properties),
        ET.Element(f"{{{A_NS}}}noAutofit"),
    )
    rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
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
            _set_run_properties_font(run_properties, properties)
        end_properties = paragraph.find(f"{{{A_NS}}}endParaRPr")
        if end_properties is None:
            end_properties = ET.Element(f"{{{A_NS}}}endParaRPr")
            paragraph.insert(
                _paragraph_end_properties_insert_index(paragraph),
                end_properties,
            )
        _set_run_properties_font(end_properties, properties)


def _set_run_properties_font(
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
            raise ValueError(f"unsupported chart title font fill: {value!r}")
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


def _clear_auto_size_children(body_properties: ET.Element) -> None:
    for child in list(body_properties):
        if child.tag.rsplit("}", 1)[-1] in {"noAutofit", "spAutoFit", "normAutofit"}:
            body_properties.remove(child)


def _auto_size_insert_index(body_properties: ET.Element) -> int:
    for index, child in enumerate(list(body_properties)):
        if child.tag.rsplit("}", 1)[-1] == "extLst":
            return index
    return len(body_properties)


def _paragraph_end_properties_insert_index(paragraph: ET.Element) -> int:
    for index, child in enumerate(list(paragraph)):
        if child.tag.rsplit("}", 1)[-1] == "extLst":
            return index
    return len(paragraph)


def _set_title_paragraph_spacing(
    paragraph_properties: ET.Element,
    spacing: dict[str, int | float | None],
) -> None:
    for attr in ("line_spacing", "space_before", "space_after"):
        if attr not in spacing:
            continue
        _set_title_paragraph_spacing_value(
            paragraph_properties,
            _paragraph_spacing_xml_tag(attr),
            spacing[attr],
        )


def _set_title_paragraph_spacing_value(
    paragraph_properties: ET.Element,
    tag: str,
    value: int | float | None,
) -> None:
    _remove_title_paragraph_spacing_child(paragraph_properties, tag)
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
        _title_paragraph_spacing_insert_index(paragraph_properties, tag),
        spacing,
    )


def _remove_title_paragraph_spacing_child(
    paragraph_properties: ET.Element,
    tag: str,
) -> None:
    for child in list(paragraph_properties):
        if child.tag.rsplit("}", 1)[-1] == tag:
            paragraph_properties.remove(child)


def _title_paragraph_spacing_insert_index(
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


def title_paragraph_spacing_value(
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


def _title_insert_index(title: ET.Element, local_name: str) -> int:
    order = {"tx": 0, "layout": 1, "overlay": 2, "spPr": 3, "txPr": 4, "extLst": 5}
    target_order = order.get(local_name)
    if target_order is None:
        return len(title)
    for index, child in enumerate(list(title)):
        child_name = child.tag.rsplit("}", 1)[-1]
        child_order = order.get(child_name)
        if child_order is not None and child_order > target_order:
            return index
    return len(title)
