"""Text, paragraph, and text-frame slide XML edit applicators."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

from .background_edits import (
    _MEDIA_PART,
    _add_image_relationship,
    _ensure_content_type,
)
from .image_inputs import (
    InMemoryFile as _InMemoryFile,
)
from .image_inputs import (
    image_extension_from_blob as _image_extension_from_blob,
)
from .image_inputs import (
    image_input_bytes as _image_input_bytes,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .shape_xml import (
    _clear_paragraph_content,
    _insert_paragraph_line_break,
    _paragraph_default_run_properties_element,
    _paragraph_properties_element,
    _paragraph_xml_element,
    _set_paragraph_alignment,
    _set_paragraph_bullet,
    _set_paragraph_font_properties,
    _set_paragraph_level,
    _set_paragraph_spacing,
    _shape_xml_element,
)
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
)
from .slide_payloads import (
    load_slide_payloads as _load_slide_payloads,
)
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


from .text_xml import _add_paragraph_tab_stop


def _materialize_picture_bullet(
    package: zipfile.ZipFile,
    replacements: dict[str, bytes],
    owner_part: str,
    bullet: dict[str, Any],
    next_media_number: int,
) -> tuple[dict[str, Any], int]:
    source = bullet.get("image_source")
    if isinstance(source, _InMemoryFile):
        blob = source.blob
    else:
        blob = _image_input_bytes(source)
    extension = _image_extension_from_blob(blob)
    media_part = f"ppt/media/image{next_media_number}.{extension}"
    replacements[media_part] = blob
    _ensure_content_type(package, replacements, extension)
    relationship_id = _add_image_relationship(
        package,
        replacements,
        _rels_part_for_package_part(owner_part).lstrip("/"),
        media_part,
        owner_part,
    )
    return {"type": "blip", "embed": relationship_id}, next_media_number + 1


def _apply_paragraph_tab_stop_edits(
    input_path: Path,
    output_path: Path,
    tab_edits: list[tuple[tuple[int, int, int], list[dict[str, Any]]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index, paragraph_index), stops in tab_edits:
            try:
                slide_payload = slides[slide_index]
                shape_payload = slide_payload["shapes"][shape_index]
            except IndexError as exc:
                raise IndexError("slide or shape index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = (
                ET.fromstring(replacements[slide_part])
                if slide_part in replacements
                else ET.fromstring(package.read(slide_part))
            )
            shape_element = _shape_xml_element(root, shape_payload)
            paragraph = _paragraph_xml_element(shape_element, paragraph_index)
            paragraph_properties = _paragraph_properties_element(paragraph)
            tab_list = paragraph_properties.find(f"{{{A_NS}}}tabLst")
            if tab_list is not None:
                paragraph_properties.remove(tab_list)
            for stop in stops:
                _add_paragraph_tab_stop(
                    paragraph_properties, stop["pos"], stop.get("align", "l")
                )
            replacements[slide_part] = ET.tostring(
                root, encoding="utf-8", xml_declaration=True
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_paragraph_tab_stop_edits(
    input_path: Path,
    output_path: Path,
    tab_edits: list[tuple[tuple[str, int, int], list[dict[str, Any]]]],
) -> None:
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for (partname, shape_index, paragraph_index), stops in tab_edits:
            normalized = _normalize_package_partname(partname).lstrip("/")
            root = (
                ET.fromstring(replacements[normalized])
                if normalized in replacements
                else ET.fromstring(package.read(normalized))
            )
            try:
                shape_payload = _load_shape_payloads(input_path, normalized)[
                    shape_index
                ]
            except IndexError as exc:
                raise IndexError("shape index out of range") from exc
            paragraph = _paragraph_xml_element(
                _shape_xml_element(root, shape_payload), paragraph_index
            )
            paragraph_properties = _paragraph_properties_element(paragraph)
            tab_list = paragraph_properties.find(f"{{{A_NS}}}tabLst")
            if tab_list is not None:
                paragraph_properties.remove(tab_list)
            for stop in stops:
                _add_paragraph_tab_stop(
                    paragraph_properties, stop["pos"], stop.get("align", "l")
                )
            replacements[normalized] = ET.tostring(
                root, encoding="utf-8", xml_declaration=True
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_paragraph_tab_stop_edits(
    input_path: Path,
    output_path: Path,
    tab_edits: list[tuple[tuple[int, int, int, int], list[dict[str, Any]]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for (
            slide_index,
            group_index,
            child_index,
            paragraph_index,
        ), stops in tab_edits:
            try:
                slide_payload = slides[slide_index]
                child_payload = slide_payload["shapes"][group_index]["children"][
                    child_index
                ]
            except IndexError as exc:
                raise IndexError("group child shape index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = (
                ET.fromstring(replacements[slide_part])
                if slide_part in replacements
                else ET.fromstring(package.read(slide_part))
            )
            paragraph = _paragraph_xml_element(
                _shape_xml_element(root, child_payload), paragraph_index
            )
            paragraph_properties = _paragraph_properties_element(paragraph)
            tab_list = paragraph_properties.find(f"{{{A_NS}}}tabLst")
            if tab_list is not None:
                paragraph_properties.remove(tab_list)
            for stop in stops:
                _add_paragraph_tab_stop(
                    paragraph_properties, stop["pos"], stop.get("align", "l")
                )
            replacements[slide_part] = ET.tostring(
                root, encoding="utf-8", xml_declaration=True
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


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
    bullet_edits: list[tuple[tuple[int, int, int], dict[str, Any] | None]]
    | None = None,
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
    if bullet_edits:
        for (slide_index, shape_index, paragraph_index), bullet in bullet_edits:
            edits_by_slide.setdefault(slide_index, {}).setdefault(
                (shape_index, paragraph_index),
                {},
            )["bullet"] = bullet
    with zipfile.ZipFile(input_path) as package:
        used_media_numbers = {
            int(match.group(1))
            for name in package.namelist()
            if (match := _MEDIA_PART.fullmatch(name)) is not None
        }
        next_media_number = max(used_media_numbers, default=0) + 1
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
                if "bullet" in edits:
                    bullet = cast(dict[str, Any] | None, edits["bullet"])
                    if bullet is not None and bullet.get("type") == "blip":
                        bullet, next_media_number = _materialize_picture_bullet(
                            package,
                            replacements,
                            slide_part,
                            bullet,
                            next_media_number,
                        )
                    _set_paragraph_bullet(paragraph_properties, bullet)
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
    spacing_edits: list[tuple[tuple[str, int, int], dict[str, int | float | None]]],
    bullet_edits: list[tuple[tuple[str, int, int], dict[str, Any] | None]]
    | None = None,
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
    if bullet_edits:
        for (partname, shape_index, paragraph_index), bullet in bullet_edits:
            normalized = _normalize_package_partname(partname).lstrip("/")
            edits_by_part.setdefault(normalized, {}).setdefault(
                (shape_index, paragraph_index),
                {},
            )["bullet"] = bullet
    with zipfile.ZipFile(input_path) as package:
        used_media_numbers = {
            int(match.group(1))
            for name in package.namelist()
            if (match := _MEDIA_PART.fullmatch(name)) is not None
        }
        next_media_number = max(used_media_numbers, default=0) + 1
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
                if "bullet" in edits:
                    bullet = cast(dict[str, Any] | None, edits["bullet"])
                    if bullet is not None and bullet.get("type") == "blip":
                        bullet, next_media_number = _materialize_picture_bullet(
                            package, replacements, partname, bullet, next_media_number
                        )
                    _set_paragraph_bullet(paragraph_properties, bullet)
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
                    raise TypeError("group child shape payload is unavailable")
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
    for (
        slide_index,
        group_index,
        child_index,
        paragraph_index,
        run_slot,
    ) in line_break_edits:
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
                    raise TypeError("group child shape payload is unavailable")
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
                    raise TypeError("group child shape payload is unavailable")
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
    bullet_edits: list[tuple[tuple[int, int, int, int], dict[str, Any] | None]]
    | None = None,
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
    if bullet_edits:
        for (
            slide_index,
            group_index,
            child_index,
            paragraph_index,
        ), bullet in bullet_edits:
            edits_by_slide.setdefault(slide_index, {}).setdefault(
                (group_index, child_index, paragraph_index),
                {},
            )["bullet"] = bullet
    with zipfile.ZipFile(input_path) as package:
        used_media_numbers = {
            int(match.group(1))
            for name in package.namelist()
            if (match := _MEDIA_PART.fullmatch(name)) is not None
        }
        next_media_number = max(used_media_numbers, default=0) + 1
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for (
                group_index,
                child_index,
                paragraph_index,
            ), edits in slide_edits.items():
                try:
                    group_payload = slide_payload["shapes"][group_index]
                    child_payload = group_payload["children"][child_index]
                except IndexError as exc:
                    raise IndexError("group child shape index out of range") from exc
                if not isinstance(child_payload, dict):
                    raise TypeError("group child shape payload is unavailable")
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
                    _set_paragraph_level(
                        paragraph_properties, cast(int, edits["level"])
                    )
                if "spacing" in edits:
                    _set_paragraph_spacing(
                        paragraph_properties,
                        cast(dict[str, int | float | None], edits["spacing"]),
                    )
                if "bullet" in edits:
                    bullet = cast(dict[str, Any] | None, edits["bullet"])
                    if bullet is not None and bullet.get("type") == "blip":
                        bullet, next_media_number = _materialize_picture_bullet(
                            package,
                            replacements,
                            slide_part,
                            bullet,
                            next_media_number,
                        )
                    _set_paragraph_bullet(paragraph_properties, bullet)
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


def _apply_paragraph_bullet_edits(
    input_path: Path,
    output_path: Path,
    bullet_edits: list[tuple[tuple[int, int, int], dict[str, Any] | None]],
) -> None:
    _apply_paragraph_property_edits(
        input_path,
        output_path,
        alignment_edits=[],
        level_edits=[],
        spacing_edits=[],
        bullet_edits=bullet_edits,
    )


def _apply_part_paragraph_bullet_edits(
    input_path: Path,
    output_path: Path,
    bullet_edits: list[tuple[tuple[str, int, int], dict[str, Any] | None]],
) -> None:
    _apply_part_paragraph_property_edits(
        input_path,
        output_path,
        alignment_edits=[],
        level_edits=[],
        spacing_edits=[],
        bullet_edits=bullet_edits,
    )


def _apply_group_child_paragraph_bullet_edits(
    input_path: Path,
    output_path: Path,
    bullet_edits: list[tuple[tuple[int, int, int, int], dict[str, Any] | None]],
) -> None:
    _apply_group_child_paragraph_property_edits(
        input_path,
        output_path,
        alignment_edits=[],
        level_edits=[],
        spacing_edits=[],
        bullet_edits=bullet_edits,
    )
