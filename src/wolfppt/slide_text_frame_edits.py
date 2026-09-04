"""Text, paragraph, and text-frame slide XML edit applicators."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_open_package_with_replacements as _copy_open_package_with_replacements,
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


def _apply_text_frame_margin_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[int, int], dict[str, int]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, dict[str, int]]]] = {}
    for (slide_index, shape_index), margins in margin_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, margins))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, margins in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text frame margin editing is only supported for shape elements"
                    )
                body_properties = _text_body_properties_element(shape_element)
                for attr, value in margins.items():
                    body_properties.set(attr, str(value))
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_margin_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[str, int], dict[str, int]]],
) -> None:
    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=margin_edits,
        apply_edit=lambda body_properties, margins: [
            body_properties.set(attr, str(value))
            for attr, value in margins.items()
        ],
        feature="text frame margin editing",
    )


def _apply_group_child_text_frame_margin_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[int, int, int], dict[str, int]]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, dict[str, int]]]] = {}
    for (slide_index, group_index, child_index), margins in margin_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, margins)
        )
    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=lambda body_properties, margins: [
            body_properties.set(attr, str(value))
            for attr, value in margins.items()
        ],
        feature="text frame margin editing",
    )


def _apply_text_frame_word_wrap_edits(
    input_path: Path,
    output_path: Path,
    word_wrap_edits: list[tuple[tuple[int, int], bool | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, bool | None]]] = {}
    for (slide_index, shape_index), word_wrap in word_wrap_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, word_wrap))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, word_wrap in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text frame word-wrap editing is only supported for shape elements"
                    )
                body_properties = _text_body_properties_element(shape_element)
                if word_wrap is None:
                    body_properties.attrib.pop("wrap", None)
                else:
                    body_properties.set("wrap", "square" if word_wrap else "none")
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_word_wrap_edits(
    input_path: Path,
    output_path: Path,
    word_wrap_edits: list[tuple[tuple[str, int], bool | None]],
) -> None:
    def apply_edit(body_properties: ET.Element, word_wrap: bool | None) -> None:
        if word_wrap is None:
            body_properties.attrib.pop("wrap", None)
        else:
            body_properties.set("wrap", "square" if word_wrap else "none")

    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=word_wrap_edits,
        apply_edit=apply_edit,
        feature="text frame word-wrap editing",
    )


def _apply_group_child_text_frame_word_wrap_edits(
    input_path: Path,
    output_path: Path,
    word_wrap_edits: list[tuple[tuple[int, int, int], bool | None]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, bool | None]]] = {}
    for (slide_index, group_index, child_index), word_wrap in word_wrap_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, word_wrap)
        )

    def apply_edit(body_properties: ET.Element, word_wrap: bool | None) -> None:
        if word_wrap is None:
            body_properties.attrib.pop("wrap", None)
        else:
            body_properties.set("wrap", "square" if word_wrap else "none")

    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=apply_edit,
        feature="text frame word-wrap editing",
    )


def _apply_text_frame_vertical_anchor_edits(
    input_path: Path,
    output_path: Path,
    vertical_anchor_edits: list[tuple[tuple[int, int], str | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, str | None]]] = {}
    for (slide_index, shape_index), anchor in vertical_anchor_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, anchor))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, anchor in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text frame vertical-anchor editing is only supported for shape elements"
                    )
                body_properties = _text_body_properties_element(shape_element)
                if anchor is None:
                    body_properties.attrib.pop("anchor", None)
                else:
                    body_properties.set("anchor", anchor)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_vertical_anchor_edits(
    input_path: Path,
    output_path: Path,
    vertical_anchor_edits: list[tuple[tuple[str, int], str | None]],
) -> None:
    def apply_edit(body_properties: ET.Element, anchor: str | None) -> None:
        if anchor is None:
            body_properties.attrib.pop("anchor", None)
        else:
            body_properties.set("anchor", anchor)

    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=vertical_anchor_edits,
        apply_edit=apply_edit,
        feature="text frame vertical-anchor editing",
    )


def _apply_group_child_text_frame_vertical_anchor_edits(
    input_path: Path,
    output_path: Path,
    vertical_anchor_edits: list[tuple[tuple[int, int, int], str | None]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, str | None]]] = {}
    for (slide_index, group_index, child_index), anchor in vertical_anchor_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, anchor)
        )

    def apply_edit(body_properties: ET.Element, anchor: str | None) -> None:
        if anchor is None:
            body_properties.attrib.pop("anchor", None)
        else:
            body_properties.set("anchor", anchor)

    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=apply_edit,
        feature="text frame vertical-anchor editing",
    )


def _apply_text_frame_auto_size_edits(
    input_path: Path,
    output_path: Path,
    auto_size_edits: list[tuple[tuple[int, int], str | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, str | None]]] = {}
    for (slide_index, shape_index), auto_size in auto_size_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, auto_size))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, auto_size in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text frame auto-size editing is only supported for shape elements"
                    )
                body_properties = _text_body_properties_element(shape_element)
                _clear_text_frame_auto_size_children(body_properties)
                if auto_size is not None:
                    body_properties.insert(
                        _text_frame_auto_size_insert_index(body_properties),
                        ET.Element(f"{{{A_NS}}}{auto_size}"),
                    )
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_auto_size_edits(
    input_path: Path,
    output_path: Path,
    auto_size_edits: list[tuple[tuple[str, int], str | None]],
) -> None:
    def apply_edit(body_properties: ET.Element, auto_size: str | None) -> None:
        _clear_text_frame_auto_size_children(body_properties)
        if auto_size is not None:
            body_properties.insert(
                _text_frame_auto_size_insert_index(body_properties),
                ET.Element(f"{{{A_NS}}}{auto_size}"),
            )

    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=auto_size_edits,
        apply_edit=apply_edit,
        feature="text frame auto-size editing",
    )


def _apply_part_text_frame_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[str, int], dict[str, int]]],
    word_wrap_edits: list[tuple[tuple[str, int], bool | None]],
    vertical_anchor_edits: list[tuple[tuple[str, int], str | None]],
    auto_size_edits: list[tuple[tuple[str, int], str | None]],
) -> None:
    edits_by_part: dict[str, dict[int, dict[str, Any]]] = {}
    for (partname, shape_index), margins in margin_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})[
            "margins"
        ] = margins
    for (partname, shape_index), word_wrap in word_wrap_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})[
            "word_wrap"
        ] = word_wrap
    for (partname, shape_index), anchor in vertical_anchor_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})[
            "vertical_anchor"
        ] = anchor
    for (partname, shape_index), auto_size in auto_size_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})[
            "auto_size"
        ] = auto_size

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            for shape_index, properties in part_edits.items():
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    for property_name, feature in (
                        ("margins", "text frame margin editing"),
                        ("word_wrap", "text frame word-wrap editing"),
                        ("vertical_anchor", "text frame vertical-anchor editing"),
                        ("auto_size", "text frame auto-size editing"),
                    ):
                        if property_name in properties:
                            raise AttributeError(
                                f"{feature} is only supported for shape elements"
                            )
                body_properties = _text_body_properties_element(shape_element)
                margins = properties.get("margins")
                if margins is not None:
                    for attr, value in margins.items():
                        body_properties.set(attr, str(value))
                if "word_wrap" in properties:
                    word_wrap = properties["word_wrap"]
                    if word_wrap is None:
                        body_properties.attrib.pop("wrap", None)
                    else:
                        body_properties.set(
                            "wrap",
                            "square" if word_wrap else "none",
                        )
                if "vertical_anchor" in properties:
                    anchor = properties["vertical_anchor"]
                    if anchor is None:
                        body_properties.attrib.pop("anchor", None)
                    else:
                        body_properties.set("anchor", anchor)
                if "auto_size" in properties:
                    auto_size = properties["auto_size"]
                    _clear_text_frame_auto_size_children(body_properties)
                    if auto_size is not None:
                        body_properties.insert(
                            _text_frame_auto_size_insert_index(body_properties),
                            ET.Element(f"{{{A_NS}}}{auto_size}"),
                        )
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
        _copy_open_package_with_replacements(package, output_path, replacements)


def _apply_group_child_text_frame_auto_size_edits(
    input_path: Path,
    output_path: Path,
    auto_size_edits: list[tuple[tuple[int, int, int], str | None]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, str | None]]] = {}
    for (slide_index, group_index, child_index), auto_size in auto_size_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, auto_size)
        )

    def apply_edit(body_properties: ET.Element, auto_size: str | None) -> None:
        _clear_text_frame_auto_size_children(body_properties)
        if auto_size is not None:
            body_properties.insert(
                _text_frame_auto_size_insert_index(body_properties),
                ET.Element(f"{{{A_NS}}}{auto_size}"),
            )

    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=apply_edit,
        feature="text frame auto-size editing",
    )


def _apply_group_child_text_frame_fit_edits(
    input_path: Path,
    output_path: Path,
    fit_edits: list[tuple[tuple[int, int, int], dict[str, Any]]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, dict[str, Any]]]] = {}
    for (slide_index, group_index, child_index), fit in fit_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, fit)
        )

    def apply_edit(shape_element: ET.Element, fit: dict[str, Any]) -> None:
        _set_text_frame_fit(shape_element, fit)

    _apply_group_child_text_frame_shape_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=apply_edit,
        feature="text fitting",
    )


def _apply_text_frame_fit_edits(
    input_path: Path,
    output_path: Path,
    fit_edits: list[tuple[tuple[int, int], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for (slide_index, shape_index), fit in fit_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, fit))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, fit in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text fitting is only supported for shape elements"
                    )
                _set_text_frame_fit(shape_element, fit)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_text_frame_shape_edits(
    input_path: Path,
    output_path: Path,
    *,
    edits_by_slide: dict[int, list[tuple[int, int, Any]]],
    apply_edit: Any,
    feature: str,
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for group_index, child_index, value in slide_edits:
                shape_element = _group_child_shape_element(
                    root,
                    slide_payload,
                    group_index,
                    child_index,
                )
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(f"{feature} is only supported for shape elements")
                apply_edit(shape_element, value)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_property_edits(
    input_path: Path,
    output_path: Path,
    *,
    edits: list[tuple[tuple[str, int], Any]],
    apply_edit: Any,
    feature: str,
) -> None:
    replacements: dict[str, bytes] = {}
    edits_by_part: dict[str, list[tuple[int, Any]]] = {}
    for (partname, shape_index), value in edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, []).append((shape_index, value))
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            for shape_index, value in part_edits:
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        f"{feature} is only supported for shape elements"
                    )
                body_properties = _text_body_properties_element(shape_element)
                apply_edit(body_properties, value)
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_text_frame_property_edits(
    input_path: Path,
    output_path: Path,
    *,
    edits_by_slide: dict[int, list[tuple[int, int, Any]]],
    apply_edit: Any,
    feature: str,
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for group_index, child_index, value in slide_edits:
                shape_element = _group_child_shape_element(
                    root,
                    slide_payload,
                    group_index,
                    child_index,
                )
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(f"{feature} is only supported for shape elements")
                body_properties = _text_body_properties_element(shape_element)
                apply_edit(body_properties, value)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _group_child_shape_element(
    root: ET.Element,
    slide_payload: dict[str, Any],
    group_index: int,
    child_index: int,
) -> ET.Element:
    try:
        group_payload = slide_payload["shapes"][group_index]
        child_payload = group_payload["children"][child_index]
    except IndexError as exc:
        raise IndexError("group child shape index out of range") from exc
    if not isinstance(child_payload, dict):
        raise AttributeError("group child shape payload is unavailable")
    return _shape_xml_element(root, child_payload)
