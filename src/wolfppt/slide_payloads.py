"""Slide and shape payload loaders for the presentation facade."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from . import native
from .extractor import PresentationSemantics, extract_semantics
from .facade_values import centipoints_to_emu
from .package_parts import natural_key, normalize_package_partname
from .slide_metadata import (
    part_common_slide_name,
    presentation_slide_master_partnames,
    read_presentation_slide_metadata,
    related_package_partnames,
)


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def load_slide_payloads(path: Path) -> list[dict[str, Any]]:
    try:
        return [dict(slide) for slide in native.summarize(path).slides]
    except RuntimeError as exc:
        if "wolfppt_native is not installed" not in str(exc):
            raise
        return _slides_from_semantics(extract_semantics(path))


def load_slide_shell_payloads(path: Path) -> list[dict[str, Any]]:
    metadata = read_presentation_slide_metadata(path)
    if metadata:
        return [
            {
                "part": part,
                "texts": [],
                **dict(payload),
            }
            for part, payload in metadata.items()
        ]
    return [dict(slide) for slide in load_slide_payloads(path)]


def load_slide_layout_payloads(path: Path) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as zf:
            names = sorted(
                [
                    name
                    for name in zf.namelist()
                    if name.startswith("ppt/slideLayouts/slideLayout")
                    and name.endswith(".xml")
                ],
                key=natural_key,
            )
            return [
                {
                    "part": name,
                    "name": _slide_layout_name(zf.read(name), fallback=Path(name).stem),
                }
                for name in names
            ]
    except (FileNotFoundError, zipfile.BadZipFile):
        return []


def load_slide_master_payloads(path: Path) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as package:
            master_parts = presentation_slide_master_partnames(package, path)
            return [
                {
                    "part": part,
                    "name": part_common_slide_name(package, part),
                    "layout_parts": related_package_partnames(
                        package,
                        part,
                        "/slideLayout",
                    ),
                    "shapes": _part_shape_payloads(package, part),
                }
                for part in master_parts
            ]
    except (FileNotFoundError, zipfile.BadZipFile):
        return []


def load_slide_layout_placeholder_payloads(
    path: Path,
    partname: str,
) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as package:
            xml = package.read(normalize_package_partname(partname).lstrip("/")).decode(
                "utf-8"
            )
    except (FileNotFoundError, KeyError, UnicodeDecodeError, zipfile.BadZipFile):
        return []
    placeholders: list[dict[str, Any]] = []
    offset = 0
    while True:
        start = xml.find("<p:sp>", offset)
        if start == -1:
            break
        end = xml.find("</p:sp>", start)
        if end == -1:
            break
        end += len("</p:sp>")
        block = xml[start:end]
        ph_start = block.find("<p:ph")
        if ph_start != -1:
            ph_end = block.find(">", ph_start)
            ph_tag = block[ph_start:ph_end] if ph_end != -1 else ""
            placeholder_type = _string_attr(ph_tag, "type")
            if placeholder_type not in {"dt", "ftr", "sldNum"}:
                placeholders.append(
                    {
                        "kind": "shape",
                        "text": "",
                        "paragraphs": [""],
                        "paragraph_runs": [[]],
                        "is_placeholder": True,
                        "placeholder_type": placeholder_type,
                        "placeholder_idx": _string_attr(ph_tag, "idx"),
                        "placeholder_orient": _string_attr(ph_tag, "orient"),
                        "placeholder_size": _string_attr(ph_tag, "sz"),
                    }
                )
        offset = end
    return placeholders


def load_shape_payloads(path: Path, partname: str) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as package:
            return _part_shape_payloads(package, partname)
    except (FileNotFoundError, zipfile.BadZipFile):
        return []


def shape_element_text(element: ET.Element) -> str:
    return "\n".join(_shape_element_paragraphs(element))


def _part_shape_payloads(
    package: zipfile.ZipFile,
    partname: str,
) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(package.read(normalize_package_partname(partname).lstrip("/")))
    except (KeyError, ET.ParseError):
        return []
    shape_tree = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if shape_tree is None:
        return []
    shapes: list[dict[str, Any]] = []
    for child in list(shape_tree):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        payload = _shape_payload_from_xml(child)
        if payload is not None:
            shapes.append(payload)
    return shapes


def _shape_payload_from_xml(element: ET.Element) -> dict[str, Any] | None:
    kind_by_tag = {
        "sp": "shape",
        "pic": "picture",
        "graphicFrame": "graphic_frame",
        "cxnSp": "connector",
        "grpSp": "group",
    }
    kind = kind_by_tag.get(_xml_local_name(element.tag))
    if kind is None:
        return None
    if kind == "picture" and _element_contains_local_name(element, "videoFile"):
        kind = "movie"
    if kind == "graphic_frame" and _element_contains_local_name(element, "oleObj"):
        kind = "ole_object"
    non_visual_properties = element.find(f".//{{{P_NS}}}cNvPr")
    placeholder = element.find(f".//{{{P_NS}}}ph")
    paragraphs = _shape_element_paragraphs(element)
    payload: dict[str, Any] = {
        "id": None
        if non_visual_properties is None
        else non_visual_properties.attrib.get("id"),
        "name": ""
        if non_visual_properties is None
        else non_visual_properties.attrib.get("name", ""),
        "kind": kind,
        "text": "\n".join(paragraphs),
        "paragraphs": paragraphs,
        "paragraph_runs": _shape_element_paragraph_runs(element),
        "paragraph_run_bold": _shape_element_paragraph_run_bools(element, "b"),
        "paragraph_run_italic": _shape_element_paragraph_run_bools(element, "i"),
        "paragraph_run_underline": _shape_element_paragraph_run_underline(element),
        "paragraph_run_font_size": _shape_element_paragraph_run_font_size(element),
        "paragraph_run_font_name": _shape_element_paragraph_run_font_name(element),
        "paragraph_run_font_rgb": _shape_element_paragraph_run_font_rgb(element),
        "paragraph_run_font_fill_type": _shape_element_paragraph_run_font_fill_type(
            element
        ),
        "paragraph_run_font_language": _shape_element_paragraph_run_font_language(
            element
        ),
        "is_placeholder": placeholder is not None,
    }
    if placeholder is not None:
        payload["placeholder_type"] = placeholder.attrib.get("type")
        payload["placeholder_idx"] = placeholder.attrib.get("idx")
        payload["placeholder_orient"] = placeholder.attrib.get("orient")
        payload["placeholder_size"] = placeholder.attrib.get("sz")
    return payload


def _shape_element_paragraphs(element: ET.Element) -> list[str]:
    paragraphs: list[str] = []
    for paragraph in element.findall(f".//{{{A_NS}}}p"):
        paragraphs.append(
            "".join(text.text or "" for text in paragraph.findall(f".//{{{A_NS}}}t"))
        )
    return paragraphs


def _shape_element_paragraph_runs(element: ET.Element) -> list[list[str]]:
    paragraphs: list[list[str]] = []
    for paragraph in element.findall(f".//{{{A_NS}}}p"):
        runs: list[str] = []
        for run in paragraph:
            if _xml_local_name(run.tag) not in {"r", "fld"}:
                continue
            text = run.find(f"{{{A_NS}}}t")
            runs.append("" if text is None else text.text or "")
        paragraphs.append(runs)
    return paragraphs


def _shape_element_paragraph_run_bools(
    element: ET.Element,
    attr: str,
) -> list[list[bool | None]]:
    return _shape_element_paragraph_run_properties(
        element,
        lambda run_properties: _bool_attribute(run_properties, attr),
    )


def _shape_element_paragraph_run_underline(
    element: ET.Element,
) -> list[list[bool | None]]:
    def read(run_properties: ET.Element | None) -> bool | None:
        if run_properties is None or "u" not in run_properties.attrib:
            return None
        return run_properties.attrib["u"] != "none"

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_size(
    element: ET.Element,
) -> list[list[int | None]]:
    def read(run_properties: ET.Element | None) -> int | None:
        if run_properties is None or "sz" not in run_properties.attrib:
            return None
        return centipoints_to_emu(int(run_properties.attrib["sz"]))

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_name(
    element: ET.Element,
) -> list[list[str | None]]:
    def read(run_properties: ET.Element | None) -> str | None:
        if run_properties is None:
            return None
        latin = run_properties.find(f"{{{A_NS}}}latin")
        if latin is None:
            return None
        return latin.attrib.get("typeface")

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_rgb(
    element: ET.Element,
) -> list[list[str | None]]:
    def read(run_properties: ET.Element | None) -> str | None:
        if run_properties is None:
            return None
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if solid_fill is None:
            return None
        srgb_color = solid_fill.find(f"{{{A_NS}}}srgbClr")
        if srgb_color is None:
            return None
        return srgb_color.attrib.get("val")

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_fill_type(
    element: ET.Element,
) -> list[list[str | None]]:
    def read(run_properties: ET.Element | None) -> str | None:
        if run_properties is None:
            return None
        if run_properties.find(f"{{{A_NS}}}solidFill") is not None:
            return "solid"
        if run_properties.find(f"{{{A_NS}}}noFill") is not None:
            return "background"
        return None

    return _shape_element_paragraph_run_properties(element, read)


def _shape_element_paragraph_run_font_language(
    element: ET.Element,
) -> list[list[str | None]]:
    return _shape_element_paragraph_run_properties(
        element,
        lambda run_properties: None
        if run_properties is None
        else run_properties.attrib.get("lang"),
    )


def _shape_element_paragraph_run_properties(
    element: ET.Element,
    reader: Any,
) -> list[list[Any]]:
    paragraphs: list[list[Any]] = []
    for paragraph in element.findall(f".//{{{A_NS}}}p"):
        values: list[Any] = []
        for run in paragraph:
            if _xml_local_name(run.tag) not in {"r", "fld"}:
                continue
            values.append(reader(run.find(f"{{{A_NS}}}rPr")))
        paragraphs.append(values)
    return paragraphs


def _bool_attribute(run_properties: ET.Element | None, attr: str) -> bool | None:
    if run_properties is None or attr not in run_properties.attrib:
        return None
    return run_properties.attrib[attr] not in {"0", "false", "False"}


def _element_contains_local_name(element: ET.Element, local_name: str) -> bool:
    return any(_xml_local_name(child.tag) == local_name for child in element.iter())


def _slide_layout_name(payload: bytes, fallback: str) -> str:
    try:
        xml = payload.decode("utf-8")
    except UnicodeDecodeError:
        xml = ""
    start = xml.find("<p:cSld")
    if start != -1:
        end = xml.find(">", start)
        if end != -1:
            name = _string_attr(xml[start:end], "name")
            if name:
                return name
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return fallback
    common_slide_data = root.find(f".//{{{P_NS}}}cSld")
    if common_slide_data is None:
        return fallback
    return common_slide_data.attrib.get("name") or fallback


def _string_attr(tag: str, name: str) -> str | None:
    needle = f'{name}="'
    start = tag.find(needle)
    if start == -1:
        return None
    start += len(needle)
    end = tag.find('"', start)
    if end == -1:
        return None
    return tag[start:end]


def _slides_from_semantics(summary: PresentationSemantics) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for slide in summary.slides:
        slides.append(
            {
                "part": slide.part,
                "texts": list(slide.texts),
                "shapes": [
                    {
                        "id": shape.id,
                        "name": shape.name,
                        "kind": shape.kind,
                        "text": shape.text,
                        "paragraphs": list(shape.paragraphs),
                        "paragraph_line_breaks": [
                            _paragraph_line_break_slots(paragraph)
                            for paragraph in shape.paragraphs
                        ],
                        "relationship_ids": list(shape.relationship_ids),
                        "transform": _transform_payload(shape.transform),
                        "effective_transform": _transform_payload(
                            shape.effective_transform
                        ),
                        "tables": [
                            {
                                "rows": [list(row) for row in table.rows],
                                "row_count": table.row_count,
                                "col_count": table.col_count,
                            }
                            for table in shape.tables
                        ],
                        "has_chart": shape.has_chart,
                        "has_picture": shape.has_picture,
                    }
                    for shape in slide.shapes
                ],
            }
        )
    return slides


def _transform_payload(transform: Any) -> dict[str, int] | None:
    if transform is None:
        return None
    return {
        "x": int(transform.x),
        "y": int(transform.y),
        "cx": int(transform.cx),
        "cy": int(transform.cy),
    }


def _paragraph_line_break_slots(text: str) -> list[int]:
    parts = text.split("\v")
    line_breaks: list[int] = []
    run_slot = 0
    for part in parts[:-1]:
        if part:
            run_slot += 1
        line_breaks.append(run_slot)
    return line_breaks


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
