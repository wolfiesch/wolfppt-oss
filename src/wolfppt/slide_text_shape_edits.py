"""Text, paragraph, and text-frame slide XML edit applicators."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .shape_xml import _shape_xml_element
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
)
from .slide_payloads import (
    load_slide_payloads as _load_slide_payloads,
)
from .xml_helpers import ooxml_namespace
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
        shape_payloads = (shape_payloads_by_part or {}).get(partname) or _load_shape_payloads(
            input_path, partname
        )
        root = ET.fromstring(package.read(partname))
        for shape_index, text in part_edits:
            try:
                shape_payload = shape_payloads[shape_index]
            except IndexError as exc:
                raise IndexError("shape index out of range") from exc
            shape_element = _shape_xml_element(root, shape_payload)
            if _xml_local_name(shape_element.tag) != "sp":
                raise AttributeError("shape text editing is only supported for shape elements")
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
    for (slide_index, group_index, nested_index, child_index), text in nested_text_edits:
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
                    raise AttributeError("shape text editing is only supported for shape elements")
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
    p_ns = ooxml_namespace(shape_element, P_NS)
    text_body = shape_element.find(f"{{{p_ns}}}txBody")
    if text_body is None:
        text_body = ET.Element(f"{{{p_ns}}}txBody")
        a_ns = ooxml_namespace(shape_element, A_NS)
        ET.SubElement(text_body, f"{{{a_ns}}}bodyPr")
        ET.SubElement(text_body, f"{{{a_ns}}}lstStyle")
        # CT_Shape places the optional text body before its extension list.
        insert_at = len(shape_element)
        for index, child in enumerate(shape_element):
            if child.tag == f"{{{p_ns}}}extLst":
                insert_at = index
                break
        shape_element.insert(insert_at, text_body)
    a_ns = ooxml_namespace(text_body, A_NS)
    preserved_children = [
        child for child in list(text_body) if _xml_local_name(child.tag) in {"bodyPr", "lstStyle"}
    ]
    text_body.clear()
    for child in preserved_children:
        text_body.append(child)
    for paragraph_text in text.split("\n") if text else [""]:
        paragraph = ET.SubElement(text_body, f"{{{a_ns}}}p")
        _append_paragraph_text(paragraph, paragraph_text)


def _append_paragraph_text(paragraph: ET.Element, text: str) -> None:
    a_ns = ooxml_namespace(paragraph, A_NS)
    parts = text.split("\v")
    wrote_child = False
    for index, part in enumerate(parts):
        if part or (not wrote_child and len(parts) == 1):
            run = ET.SubElement(paragraph, f"{{{a_ns}}}r")
            text_node = ET.SubElement(run, f"{{{a_ns}}}t")
            text_node.text = part
            wrote_child = True
        if index < len(parts) - 1:
            ET.SubElement(paragraph, f"{{{a_ns}}}br")
            wrote_child = True
