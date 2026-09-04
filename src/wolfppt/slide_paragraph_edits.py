"""Text, paragraph, and text-frame slide XML edit applicators."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, cast
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


def _apply_paragraph_clear_edits(
    input_path: Path,
    output_path: Path,
    clear_edits: list[tuple[int, int, int]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int]]] = {}
    for slide_index, shape_index, paragraph_index in clear_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph clearing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                _clear_paragraph_content(paragraph)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_paragraph_line_break_edits(
    input_path: Path,
    output_path: Path,
    line_break_edits: list[tuple[int, int, int, int]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int]]] = {}
    for slide_index, shape_index, paragraph_index, run_slot in line_break_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, run_slot)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, run_slot in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph line breaks are only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                _insert_paragraph_line_break(paragraph, run_slot)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_paragraph_font_edits(
    input_path: Path,
    output_path: Path,
    font_edits: list[tuple[tuple[int, int, int], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, dict[str, Any]]]] = {}
    for (slide_index, shape_index, paragraph_index), edits in font_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, edits)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, edits in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph font editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                default_run_properties = _paragraph_default_run_properties_element(
                    paragraph
                )
                _set_paragraph_font_properties(default_run_properties, edits)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_paragraph_property_edits(
    input_path: Path,
    output_path: Path,
    alignment_edits: list[tuple[tuple[int, int, int], str | None]],
    level_edits: list[tuple[tuple[int, int, int], int]],
    spacing_edits: list[tuple[tuple[int, int, int], dict[str, int | float | None]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[
        int,
        dict[
            tuple[int, int],
            dict[str, str | int | dict[str, int | float | None] | None],
        ],
    ] = {}
    for (slide_index, shape_index, paragraph_index), alignment in alignment_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (shape_index, paragraph_index),
            {},
        )["alignment"] = alignment
    for (slide_index, shape_index, paragraph_index), level in level_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (shape_index, paragraph_index),
            {},
        )["level"] = level
    for (slide_index, shape_index, paragraph_index), spacing in spacing_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (shape_index, paragraph_index),
            {},
        )["spacing"] = spacing

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for (shape_index, paragraph_index), edits in slide_edits.items():
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph property editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                paragraph_properties = _paragraph_properties_element(paragraph)
                if "alignment" in edits:
                    _set_paragraph_alignment(
                        paragraph_properties,
                        cast(str | None, edits["alignment"]),
                    )
                if "level" in edits:
                    _set_paragraph_level(
                        paragraph_properties,
                        cast(int, edits["level"]),
                    )
                if "spacing" in edits:
                    _set_paragraph_spacing(
                        paragraph_properties,
                        cast(dict[str, int | float | None], edits["spacing"]),
                    )
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_paragraph_font_edits(
    input_path: Path,
    output_path: Path,
    font_edits: list[tuple[tuple[str, int, int], dict[str, Any]]],
) -> None:
    replacements: dict[str, bytes] = {}
    edits_by_part: dict[str, list[tuple[int, int, dict[str, Any]]]] = {}
    for (partname, shape_index, paragraph_index), edits in font_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, []).append(
            (shape_index, paragraph_index, edits)
        )
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            for shape_index, paragraph_index, edits in part_edits:
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "part paragraph font editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                default_run_properties = _paragraph_default_run_properties_element(
                    paragraph
                )
                _set_paragraph_font_properties(default_run_properties, edits)
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_paragraph_property_edits(
    input_path: Path,
    output_path: Path,
    alignment_edits: list[tuple[tuple[str, int, int], str | None]],
    level_edits: list[tuple[tuple[str, int, int], int]],
    spacing_edits: list[
        tuple[tuple[str, int, int], dict[str, int | float | None]]
    ],
) -> None:
    replacements: dict[str, bytes] = {}
    edits_by_part: dict[
        str,
        dict[
            tuple[int, int],
            dict[str, str | int | dict[str, int | float | None] | None],
        ],
    ] = {}
    for (partname, shape_index, paragraph_index), alignment in alignment_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(
            (shape_index, paragraph_index),
            {},
        )["alignment"] = alignment
    for (partname, shape_index, paragraph_index), level in level_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(
            (shape_index, paragraph_index),
            {},
        )["level"] = level
    for (partname, shape_index, paragraph_index), spacing in spacing_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(
            (shape_index, paragraph_index),
            {},
        )["spacing"] = spacing

    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            for (shape_index, paragraph_index), edits in part_edits.items():
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph property editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                paragraph_properties = _paragraph_properties_element(paragraph)
                if "alignment" in edits:
                    _set_paragraph_alignment(
                        paragraph_properties,
                        cast(str | None, edits["alignment"]),
                    )
                if "level" in edits:
                    _set_paragraph_level(
                        paragraph_properties,
                        cast(int, edits["level"]),
                    )
                if "spacing" in edits:
                    _set_paragraph_spacing(
                        paragraph_properties,
                        cast(dict[str, int | float | None], edits["spacing"]),
                    )
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_paragraph_alignment_edits(
    input_path: Path,
    output_path: Path,
    alignment_edits: list[tuple[tuple[int, int, int], str | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, str | None]]] = {}
    for (slide_index, shape_index, paragraph_index), alignment in alignment_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, alignment)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, alignment in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph alignment editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                paragraph_properties = _paragraph_properties_element(paragraph)
                _set_paragraph_alignment(paragraph_properties, alignment)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_paragraph_alignment_edits(
    input_path: Path,
    output_path: Path,
    alignment_edits: list[tuple[tuple[int, int, int, int], str | None]],
) -> None:
    _apply_group_child_paragraph_property_edits(
        input_path,
        output_path,
        alignment_edits=alignment_edits,
        level_edits=[],
        spacing_edits=[],
    )


def _apply_group_child_paragraph_level_edits(
    input_path: Path,
    output_path: Path,
    level_edits: list[tuple[tuple[int, int, int, int], int]],
) -> None:
    _apply_group_child_paragraph_property_edits(
        input_path,
        output_path,
        alignment_edits=[],
        level_edits=level_edits,
        spacing_edits=[],
    )


def _apply_group_child_paragraph_spacing_edits(
    input_path: Path,
    output_path: Path,
    spacing_edits: list[
        tuple[tuple[int, int, int, int], dict[str, int | float | None]]
    ],
) -> None:
    _apply_group_child_paragraph_property_edits(
        input_path,
        output_path,
        alignment_edits=[],
        level_edits=[],
        spacing_edits=spacing_edits,
    )


def _apply_group_child_paragraph_clear_edits(
    input_path: Path,
    output_path: Path,
    clear_edits: list[tuple[int, int, int, int]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int]]] = {}
    for slide_index, group_index, child_index, paragraph_index in clear_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, paragraph_index)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for group_index, child_index, paragraph_index in slide_edits:
                try:
                    group_payload = slide_payload["shapes"][group_index]
                    child_payload = group_payload["children"][child_index]
                except IndexError as exc:
                    raise IndexError("group child shape index out of range") from exc
                if not isinstance(child_payload, dict):
                    raise AttributeError("group child shape payload is unavailable")
                shape_element = _shape_xml_element(root, child_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph clearing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                _clear_paragraph_content(paragraph)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_paragraph_line_break_edits(
    input_path: Path,
    output_path: Path,
    line_break_edits: list[tuple[int, int, int, int, int]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, int]]] = {}
    for slide_index, group_index, child_index, paragraph_index, run_slot in (
        line_break_edits
    ):
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, paragraph_index, run_slot)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for group_index, child_index, paragraph_index, run_slot in slide_edits:
                try:
                    group_payload = slide_payload["shapes"][group_index]
                    child_payload = group_payload["children"][child_index]
                except IndexError as exc:
                    raise IndexError("group child shape index out of range") from exc
                if not isinstance(child_payload, dict):
                    raise AttributeError("group child shape payload is unavailable")
                shape_element = _shape_xml_element(root, child_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph line breaks are only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                _insert_paragraph_line_break(paragraph, run_slot)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_paragraph_font_edits(
    input_path: Path,
    output_path: Path,
    font_edits: list[tuple[tuple[int, int, int, int], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, dict[str, Any]]]] = {}
    for (
        slide_index,
        group_index,
        child_index,
        paragraph_index,
    ), edits in font_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, paragraph_index, edits)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for group_index, child_index, paragraph_index, edits in slide_edits:
                try:
                    group_payload = slide_payload["shapes"][group_index]
                    child_payload = group_payload["children"][child_index]
                except IndexError as exc:
                    raise IndexError("group child shape index out of range") from exc
                if not isinstance(child_payload, dict):
                    raise AttributeError("group child shape payload is unavailable")
                shape_element = _shape_xml_element(root, child_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph font editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                default_run_properties = _paragraph_default_run_properties_element(
                    paragraph
                )
                _set_paragraph_font_properties(default_run_properties, edits)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_paragraph_property_edits(
    input_path: Path,
    output_path: Path,
    alignment_edits: list[tuple[tuple[int, int, int, int], str | None]],
    level_edits: list[tuple[tuple[int, int, int, int], int]],
    spacing_edits: list[
        tuple[tuple[int, int, int, int], dict[str, int | float | None]]
    ],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[
        int,
        dict[
            tuple[int, int, int],
            dict[str, str | int | dict[str, int | float | None] | None],
        ],
    ] = {}
    for (
        slide_index,
        group_index,
        child_index,
        paragraph_index,
    ), alignment in alignment_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (group_index, child_index, paragraph_index),
            {},
        )["alignment"] = alignment
    for (
        slide_index,
        group_index,
        child_index,
        paragraph_index,
    ), level in level_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (group_index, child_index, paragraph_index),
            {},
        )["level"] = level
    for (
        slide_index,
        group_index,
        child_index,
        paragraph_index,
    ), spacing in spacing_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (group_index, child_index, paragraph_index),
            {},
        )["spacing"] = spacing
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for (group_index, child_index, paragraph_index), edits in slide_edits.items():
                try:
                    group_payload = slide_payload["shapes"][group_index]
                    child_payload = group_payload["children"][child_index]
                except IndexError as exc:
                    raise IndexError("group child shape index out of range") from exc
                if not isinstance(child_payload, dict):
                    raise AttributeError("group child shape payload is unavailable")
                shape_element = _shape_xml_element(root, child_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph alignment editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                paragraph_properties = _paragraph_properties_element(paragraph)
                if "alignment" in edits:
                    _set_paragraph_alignment(
                        paragraph_properties,
                        cast(str | None, edits["alignment"]),
                    )
                if "level" in edits:
                    _set_paragraph_level(paragraph_properties, cast(int, edits["level"]))
                if "spacing" in edits:
                    _set_paragraph_spacing(
                        paragraph_properties,
                        cast(dict[str, int | float | None], edits["spacing"]),
                    )
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_paragraph_level_edits(
    input_path: Path,
    output_path: Path,
    level_edits: list[tuple[tuple[int, int, int], int]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int]]] = {}
    for (slide_index, shape_index, paragraph_index), level in level_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, level)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, level in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph level editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                paragraph_properties = _paragraph_properties_element(paragraph)
                _set_paragraph_level(paragraph_properties, level)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_paragraph_spacing_edits(
    input_path: Path,
    output_path: Path,
    spacing_edits: list[tuple[tuple[int, int, int], dict[str, int | float | None]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, dict[str, int | float | None]]]] = {}
    for (slide_index, shape_index, paragraph_index), spacing in spacing_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, spacing)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, spacing in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "paragraph spacing editing is only supported for shape elements"
                    )
                paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                paragraph_properties = _paragraph_properties_element(paragraph)
                _set_paragraph_spacing(paragraph_properties, spacing)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)
