"""Text, paragraph, and text-frame slide XML edit applicators."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
    normalize_package_partname as _normalize_package_partname,
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .shape_xml import (
    _clear_paragraph_content,
    _insert_paragraph_line_break,
    _paragraph_default_run_properties_element,
    _paragraph_properties_element,
    _paragraph_xml_element,
    _run_properties_element,
    _set_hyperlink_address,
    _set_paragraph_alignment,
    _set_paragraph_font_properties,
    _set_paragraph_level,
    _set_paragraph_spacing,
    _set_run_font_color,
    _set_run_font_fill_type,
    _set_run_font_language,
    _set_text_frame_fit,
    _shape_xml_element,
    _text_body_properties_element,
    _text_run_xml_element,
)
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
    load_slide_payloads as _load_slide_payloads,
)
from .text_xml import (
    _clear_text_frame_auto_size_children,
    _set_font_bool_attribute,
    _set_font_name,
    _set_font_size,
    _set_font_underline,
    _text_frame_auto_size_insert_index,
)
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _apply_part_shape_text_edits(
    input_path: Path,
    output_path: Path,
    text_edits: list[tuple[tuple[str, int], str]],
) -> None:
    _copy_package_with_replacements(
        input_path,
        output_path,
        _part_shape_text_replacements(input_path, text_edits),
    )


def _part_shape_text_replacements(
    input_path: Path,
    text_edits: list[tuple[tuple[str, int], str]],
    shape_payloads_by_part: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, bytes]:
    with zipfile.ZipFile(input_path) as package:
        return _part_shape_text_replacements_from_package(
            package,
            input_path,
            text_edits,
            shape_payloads_by_part=shape_payloads_by_part,
        )


def _part_shape_text_replacements_from_package(
    package: zipfile.ZipFile,
    input_path: Path,
    text_edits: list[tuple[tuple[str, int], str]],
    shape_payloads_by_part: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, bytes]:
    replacements: dict[str, bytes] = {}
    edits_by_part: dict[str, list[tuple[int, str]]] = {}
    for (partname, shape_index), text in text_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, []).append((shape_index, text))
    for partname, part_edits in edits_by_part.items():
        shape_payloads = (
            (shape_payloads_by_part or {}).get(partname)
            or _load_shape_payloads(input_path, partname)
        )
        root = ET.fromstring(package.read(partname))
        for shape_index, text in part_edits:
            try:
                shape_payload = shape_payloads[shape_index]
            except IndexError as exc:
                raise IndexError("shape index out of range") from exc
            shape_element = _shape_xml_element(root, shape_payload)
            if _xml_local_name(shape_element.tag) != "sp":
                raise AttributeError(
                    "shape text editing is only supported for shape elements"
                )
            _set_shape_text(shape_element, text)
        replacements[partname] = ET.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
        )
    return replacements


def _apply_nested_group_child_shape_text_edits(
    input_path: Path,
    output_path: Path,
    nested_text_edits: list[tuple[tuple[int, int, int, int], str]],
    deeper_text_edits: list[tuple[tuple[int, int, int, int, int], str]],
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    _copy_package_with_replacements(
        input_path,
        output_path,
        _nested_group_child_shape_text_replacements(
            input_path,
            nested_text_edits,
            deeper_text_edits,
            slide_payloads=slide_payloads,
        ),
    )


def _nested_group_child_shape_text_replacements(
    input_path: Path,
    nested_text_edits: list[tuple[tuple[int, int, int, int], str]],
    deeper_text_edits: list[tuple[tuple[int, int, int, int, int], str]],
    slide_payloads: list[dict[str, Any]] | None = None,
) -> dict[str, bytes]:
    payloads = slide_payloads or _load_slide_payloads(input_path)
    edits_by_slide: dict[int, list[tuple[dict[str, Any], str]]] = {}
    for (slide_index, group_index, nested_index, child_index), text in (
        nested_text_edits
    ):
        target = _nested_group_child_payload(
            payloads,
            slide_index,
            group_index,
            nested_index,
            child_index,
        )
        edits_by_slide.setdefault(slide_index, []).append((target, text))
    for (
        slide_index,
        group_index,
        nested_index,
        deeper_index,
        child_index,
    ), text in deeper_text_edits:
        target = _deeper_group_child_payload(
            payloads,
            slide_index,
            group_index,
            nested_index,
            deeper_index,
            child_index,
        )
        edits_by_slide.setdefault(slide_index, []).append((target, text))

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                partname = str(payloads[slide_index]["part"])
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            partname = _normalize_package_partname(partname).lstrip("/")
            root = ET.fromstring(package.read(partname))
            for shape_payload, text in slide_edits:
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "shape text editing is only supported for shape elements"
                    )
                _set_shape_text(shape_element, text)
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    return replacements


def _nested_group_child_payload(
    slide_payloads: list[dict[str, Any]],
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    child_index: int,
) -> dict[str, Any]:
    try:
        return slide_payloads[slide_index]["shapes"][group_index]["children"][
            nested_group_child_index
        ]["children"][child_index]
    except IndexError as exc:
        raise IndexError("nested group child index out of range") from exc
    except KeyError as exc:
        raise AttributeError("nested group child payload is unavailable") from exc


def _deeper_group_child_payload(
    slide_payloads: list[dict[str, Any]],
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
    child_index: int,
) -> dict[str, Any]:
    try:
        return slide_payloads[slide_index]["shapes"][group_index]["children"][
            nested_group_child_index
        ]["children"][deeper_group_child_index]["children"][child_index]
    except IndexError as exc:
        raise IndexError("deeper group child index out of range") from exc
    except KeyError as exc:
        raise AttributeError("deeper group child payload is unavailable") from exc


def _set_shape_text(shape_element: ET.Element, text: str) -> None:
    text_body = shape_element.find(f"{{{P_NS}}}txBody")
    if text_body is None:
        raise AttributeError("shape text body is unavailable")
    preserved_children = [
        child
        for child in list(text_body)
        if _xml_local_name(child.tag) in {"bodyPr", "lstStyle"}
    ]
    text_body.clear()
    for child in preserved_children:
        text_body.append(child)
    for paragraph_text in text.split("\n") if text else [""]:
        paragraph = ET.SubElement(text_body, f"{{{A_NS}}}p")
        _append_paragraph_text(paragraph, paragraph_text)


def _append_paragraph_text(paragraph: ET.Element, text: str) -> None:
    parts = text.split("\v")
    wrote_child = False
    for index, part in enumerate(parts):
        if part or (not wrote_child and len(parts) == 1):
            run = ET.SubElement(paragraph, f"{{{A_NS}}}r")
            text_node = ET.SubElement(run, f"{{{A_NS}}}t")
            text_node.text = part
            wrote_child = True
        if index < len(parts) - 1:
            ET.SubElement(paragraph, f"{{{A_NS}}}br")
            wrote_child = True
