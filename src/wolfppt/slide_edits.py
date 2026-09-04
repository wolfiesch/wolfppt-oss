"""Slide XML edit applicators for presentation saves."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    set_shape_gradient_fill as _set_shape_gradient_fill,
    set_shape_no_fill as _set_shape_no_fill,
    set_shape_pattern_fill as _set_shape_pattern_fill,
    set_shape_pattern_fill_color as _set_shape_pattern_fill_color,
    set_shape_solid_fill as _set_shape_solid_fill,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
    normalize_package_partname as _normalize_package_partname,
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .shape_xml import (
    _get_or_add_shape_line_element,
    _picture_blip_fill_element,
    _set_connector_connection,
    _set_connector_transform,
    _set_picture_crop,
    _set_shape_adjustment_guides,
    _set_shape_hyperlink_address,
    _set_shape_line_color,
    _set_shape_line_dash_style,
    _set_shape_line_no_fill,
    _set_shape_line_pattern_fill,
    _set_shape_line_pattern_fill_color,
    _set_shape_line_solid_fill,
    _set_shape_line_width,
    _set_shape_rotation,
    _set_shape_shadow_inherit,
    _set_shape_target_slide,
    _shape_properties_element,
    _shape_transform_xml_element,
    _shape_xml_element,
)
from .shape_edit_refs import ShapeEditRef
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
    load_slide_payloads as _load_slide_payloads,
)
from .slide_text_edits import (
    _apply_group_child_paragraph_alignment_edits,
    _apply_group_child_paragraph_clear_edits,
    _apply_group_child_paragraph_font_edits,
    _apply_group_child_paragraph_line_break_edits,
    _apply_group_child_paragraph_level_edits,
    _apply_group_child_paragraph_spacing_edits,
    _apply_group_child_text_frame_auto_size_edits,
    _apply_group_child_text_frame_fit_edits,
    _apply_group_child_text_frame_margin_edits,
    _apply_group_child_text_frame_vertical_anchor_edits,
    _apply_group_child_text_frame_word_wrap_edits,
    _apply_group_child_text_run_font_edits,
    _apply_group_child_text_run_hyperlink_edits,
    _apply_paragraph_alignment_edits,
    _apply_paragraph_clear_edits,
    _apply_paragraph_font_edits,
    _apply_paragraph_level_edits,
    _apply_paragraph_line_break_edits,
    _apply_paragraph_property_edits,
    _apply_paragraph_spacing_edits,
    _apply_part_paragraph_font_edits,
    _apply_part_paragraph_property_edits,
    _apply_part_text_edits,
    _apply_nested_group_child_shape_text_edits,
    _apply_part_shape_text_edits,
    _apply_part_text_run_hyperlink_edits,
    _apply_part_text_run_font_edits,
    _apply_part_text_frame_auto_size_edits,
    _apply_part_text_frame_edits,
    _apply_part_text_frame_margin_edits,
    _apply_part_text_frame_vertical_anchor_edits,
    _apply_part_text_frame_word_wrap_edits,
    _apply_text_frame_auto_size_edits,
    _apply_text_frame_fit_edits,
    _apply_text_frame_margin_edits,
    _apply_text_frame_vertical_anchor_edits,
    _apply_text_frame_word_wrap_edits,
    _apply_text_run_font_color_edits,
    _apply_text_run_font_fill_type_edits,
    _apply_text_run_font_language_edits,
    _apply_text_run_hyperlink_edits,
    _part_shape_text_replacements,
    _part_shape_text_replacements_from_package,
    _set_shape_text,
)
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
ShapeRef = ShapeEditRef
ShapeStyleKey = tuple[int, ShapeRef]


def _shape_style_edits(
    fill_solid_edits: list[ShapeStyleKey],
    fill_background_edits: list[ShapeStyleKey],
    fill_pattern_edits: list[tuple[ShapeStyleKey, str | None]],
    fill_pattern_fore_color_edits: list[tuple[ShapeStyleKey, str]],
    fill_pattern_back_color_edits: list[tuple[ShapeStyleKey, str]],
    fill_color_edits: list[tuple[ShapeStyleKey, str | dict[str, Any]]],
    fill_gradient_edits: list[tuple[ShapeStyleKey, dict[str, Any]]],
    line_solid_edits: list[ShapeStyleKey],
    line_background_edits: list[ShapeStyleKey],
    line_pattern_edits: list[tuple[ShapeStyleKey, str | None]],
    line_pattern_fore_color_edits: list[tuple[ShapeStyleKey, str]],
    line_pattern_back_color_edits: list[tuple[ShapeStyleKey, str]],
    line_color_edits: list[tuple[ShapeStyleKey, str | dict[str, Any]]],
    line_width_edits: list[tuple[ShapeStyleKey, int]],
    line_dash_edits: list[tuple[ShapeStyleKey, str | None]],
    shadow_inherit_edits: list[tuple[ShapeStyleKey, bool]],
) -> dict[ShapeStyleKey, dict[str, Any]]:
    edits: dict[ShapeStyleKey, dict[str, Any]] = {}
    for key in fill_solid_edits:
        edits.setdefault(key, {})["fill_solid"] = True
    for key in fill_background_edits:
        edits.setdefault(key, {})["fill_background"] = True
    for key, pattern in fill_pattern_edits:
        edits.setdefault(key, {})["fill_pattern"] = pattern
    for key, rgb in fill_pattern_fore_color_edits:
        edits.setdefault(key, {})["fill_pattern_fore"] = rgb
    for key, rgb in fill_pattern_back_color_edits:
        edits.setdefault(key, {})["fill_pattern_back"] = rgb
    for key, rgb in fill_color_edits:
        edits.setdefault(key, {})["fill"] = rgb
    for key, gradient in fill_gradient_edits:
        edits.setdefault(key, {})["fill_gradient"] = gradient
    for key in line_solid_edits:
        edits.setdefault(key, {})["line_solid"] = True
    for key in line_background_edits:
        edits.setdefault(key, {})["line_background"] = True
    for key, pattern in line_pattern_edits:
        edits.setdefault(key, {})["line_pattern"] = pattern
    for key, rgb in line_pattern_fore_color_edits:
        edits.setdefault(key, {})["line_pattern_fore"] = rgb
    for key, rgb in line_pattern_back_color_edits:
        edits.setdefault(key, {})["line_pattern_back"] = rgb
    for key, rgb in line_color_edits:
        edits.setdefault(key, {})["line"] = rgb
    for key, width in line_width_edits:
        edits.setdefault(key, {})["line_width"] = width
    for key, dash_style in line_dash_edits:
        edits.setdefault(key, {})["line_dash"] = dash_style
    for key, inherit in shadow_inherit_edits:
        edits.setdefault(key, {})["shadow_inherit"] = inherit
    return edits


def _apply_shape_style_edits(
    input_path: Path,
    output_path: Path,
    style_edits: dict[ShapeStyleKey, dict[str, Any]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    slides = (
        slide_payloads
        if slide_payloads is not None
        else _load_slide_payloads(input_path)
    )
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeRef, dict[str, Any]]]] = {}
    for (slide_index, shape_ref), edits in style_edits.items():
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, edits))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, edits in slide_edits:
                shape_payload = _shape_style_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload)
                shape_tag = _xml_local_name(shape_element.tag)
                if shape_tag not in {"sp", "cxnSp"}:
                    raise AttributeError(
                        "shape style editing is only supported for shape elements"
                    )
                if shape_tag == "cxnSp" and _style_edits_include_fill(edits):
                    raise AttributeError(
                        "shape fill editing is only supported for shape elements"
                    )
                shape_properties = _shape_properties_element(shape_element)
                if edits.get("fill_solid"):
                    _set_shape_solid_fill(shape_properties)
                if edits.get("fill_background"):
                    _set_shape_no_fill(shape_properties)
                if "fill_pattern" in edits:
                    _set_shape_pattern_fill(shape_properties, edits["fill_pattern"])
                if "fill_pattern_fore" in edits:
                    _set_shape_pattern_fill_color(
                        shape_properties,
                        "fgClr",
                        edits["fill_pattern_fore"],
                    )
                if "fill_pattern_back" in edits:
                    _set_shape_pattern_fill_color(
                        shape_properties,
                        "bgClr",
                        edits["fill_pattern_back"],
                    )
                if "fill" in edits:
                    _set_shape_solid_fill(shape_properties, edits["fill"])
                if "fill_gradient" in edits:
                    _set_shape_gradient_fill(shape_properties, edits["fill_gradient"])
                if edits.get("line_solid"):
                    _set_shape_line_solid_fill(shape_properties)
                if edits.get("line_background"):
                    _set_shape_line_no_fill(shape_properties)
                if "line_pattern" in edits:
                    _set_shape_line_pattern_fill(shape_properties, edits["line_pattern"])
                if "line_pattern_fore" in edits:
                    _set_shape_line_pattern_fill_color(
                        shape_properties,
                        "fgClr",
                        edits["line_pattern_fore"],
                    )
                if "line_pattern_back" in edits:
                    _set_shape_line_pattern_fill_color(
                        shape_properties,
                        "bgClr",
                        edits["line_pattern_back"],
                    )
                if "line" in edits:
                    _set_shape_line_color(shape_properties, edits["line"])
                if "line_width" in edits:
                    _set_shape_line_width(shape_properties, edits["line_width"])
                if "line_dash" in edits:
                    _set_shape_line_dash_style(shape_properties, edits["line_dash"])
                if "shadow_inherit" in edits:
                    _set_shape_shadow_inherit(
                        shape_properties,
                        bool(edits["shadow_inherit"]),
                    )
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _shape_style_payload(
    slide_payload: dict[str, Any],
    shape_ref: ShapeRef,
) -> dict[str, Any]:
    return _shape_payload(slide_payload, shape_ref)


def _shape_payload(
    slide_payload: dict[str, Any],
    shape_ref: ShapeRef,
) -> dict[str, Any]:
    if isinstance(shape_ref, tuple):
        try:
            child_payload = slide_payload["shapes"][shape_ref[0]]
            for child_index in shape_ref[1:]:
                child_payload = child_payload["children"][child_index]
        except IndexError as exc:
            raise IndexError("group child shape index out of range") from exc
        except KeyError as exc:
            raise AttributeError("group child shape payload is unavailable") from exc
        if not isinstance(child_payload, dict):
            raise AttributeError("group child shape payload is unavailable")
        return child_payload
    try:
        return slide_payload["shapes"][shape_ref]
    except IndexError as exc:
        raise IndexError("shape index out of range") from exc


def _apply_shape_hyperlink_edits(
    input_path: Path,
    output_path: Path,
    hyperlink_edits: list[tuple[tuple[int, ShapeRef], str | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeRef, str | None]]] = {}
    for (slide_index, shape_ref), address in hyperlink_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, address))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            slide_root = ET.fromstring(package.read(slide_part))
            rels_part = _rels_part_for_package_part(slide_part)
            try:
                rels_root = ET.fromstring(package.read(rels_part))
            except KeyError:
                rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            for shape_ref, address in slide_edits:
                shape_payload = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(slide_root, shape_payload)
                non_visual_properties = shape_element.find(f".//{{{P_NS}}}cNvPr")
                if non_visual_properties is None:
                    raise AttributeError("shape non-visual properties are unavailable")
                _set_shape_hyperlink_address(
                    non_visual_properties,
                    rels_root,
                    address,
                )
            replacements[slide_part] = ET.tostring(
                slide_root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[rels_part] = ET.tostring(
                rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_shape_hyperlink_edits(
    input_path: Path,
    output_path: Path,
    hyperlink_edits: list[tuple[tuple[str, int], str | None]],
) -> None:
    replacements: dict[str, bytes] = {}
    edits_by_part: dict[str, list[tuple[int, str | None]]] = {}
    for (partname, shape_index), address in hyperlink_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, []).append((shape_index, address))
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            rels_part = _rels_part_for_package_part(partname)
            try:
                rels_root = ET.fromstring(package.read(rels_part))
            except KeyError:
                rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            for shape_index, address in part_edits:
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                non_visual_properties = shape_element.find(f".//{{{P_NS}}}cNvPr")
                if non_visual_properties is None:
                    raise AttributeError("shape non-visual properties are unavailable")
                _set_shape_hyperlink_address(
                    non_visual_properties,
                    rels_root,
                    address,
                )
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[rels_part] = ET.tostring(
                rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_connector_connection_edits(
    input_path: Path,
    output_path: Path,
    connector_edits: list[tuple[tuple[int, ShapeRef], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeRef, dict[str, Any]]]] = {}
    for (slide_index, shape_ref), edits in connector_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, edits))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, edits in slide_edits:
                connector_payload = _shape_payload(slide_payload, shape_ref)
                if connector_payload.get("kind") != "connector":
                    raise AttributeError("shape is not a connector")
                connector_element = _shape_xml_element(root, connector_payload)
                for endpoint in ("begin", "end"):
                    connection = edits.get(endpoint)
                    if not connection:
                        continue
                    _set_connector_connection(
                        connector_element,
                        endpoint,
                        connection["shape_id"],
                        int(connection["cxn_pt_idx"]),
                    )
                _set_connector_transform(
                    connector_element,
                    edits["transform"],
                    bool(edits.get("flip_h")),
                    bool(edits.get("flip_v")),
                )
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_shape_target_slide_edits(
    input_path: Path,
    output_path: Path,
    target_slide_edits: list[tuple[tuple[int, ShapeRef], int | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeRef, int | None]]] = {}
    for (slide_index, shape_ref), target_slide_index in target_slide_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_ref, target_slide_index)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            slide_root = ET.fromstring(package.read(slide_part))
            rels_part = _rels_part_for_package_part(slide_part)
            try:
                rels_root = ET.fromstring(package.read(rels_part))
            except KeyError:
                rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            for shape_ref, target_slide_index in slide_edits:
                shape_payload = _shape_payload(slide_payload, shape_ref)
                target_slide_part = None
                if target_slide_index is not None:
                    try:
                        target_slide_part = str(slides[target_slide_index]["part"])
                    except IndexError as exc:
                        raise IndexError("target slide index out of range") from exc
                shape_element = _shape_xml_element(slide_root, shape_payload)
                non_visual_properties = shape_element.find(f".//{{{P_NS}}}cNvPr")
                if non_visual_properties is None:
                    raise AttributeError("shape non-visual properties are unavailable")
                _set_shape_target_slide(
                    non_visual_properties,
                    rels_root,
                    slide_part,
                    target_slide_part,
                )
            replacements[slide_part] = ET.tostring(
                slide_root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[rels_part] = ET.tostring(
                rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _style_edits_include_fill(edits: dict[str, Any]) -> bool:
    return any(
        key in edits
        for key in (
            "fill_solid",
            "fill_background",
            "fill_pattern",
            "fill_pattern_fore",
            "fill_pattern_back",
            "fill",
            "fill_gradient",
        )
    )


def _apply_shape_rotation_edits(
    input_path: Path,
    output_path: Path,
    rotation_edits: list[tuple[tuple[int, ShapeRef], float]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeRef, float]]] = {}
    for (slide_index, shape_ref), rotation in rotation_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, rotation))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, rotation in slide_edits:
                shape_payload = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload)
                transform = _shape_transform_xml_element(shape_element)
                _set_shape_rotation(transform, rotation)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_nested_group_child_geometry_edits(
    input_path: Path,
    output_path: Path,
    nested_geometry_edits: list[
        tuple[tuple[int, int, int, int], tuple[int, int, int, int]]
    ],
    deeper_geometry_edits: list[
        tuple[tuple[int, int, int, int, int], tuple[int, int, int, int]]
    ],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    slides = (
        slide_payloads
        if slide_payloads is not None
        else _load_slide_payloads(input_path)
    )
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[
        int,
        list[tuple[dict[str, Any], tuple[int, int, int, int]]],
    ] = {}
    for (slide_index, group_index, nested_index, child_index), geometry in (
        nested_geometry_edits
    ):
        target = _nested_group_child_payload(
            slides,
            slide_index,
            group_index,
            nested_index,
            child_index,
        )
        edits_by_slide.setdefault(slide_index, []).append((target, geometry))
    for (
        slide_index,
        group_index,
        nested_index,
        deeper_index,
        child_index,
    ), geometry in deeper_geometry_edits:
        target = _deeper_group_child_payload(
            slides,
            slide_index,
            group_index,
            nested_index,
            deeper_index,
            child_index,
        )
        edits_by_slide.setdefault(slide_index, []).append((target, geometry))

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_part = str(slides[slide_index]["part"])
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            root = ET.fromstring(package.read(slide_part))
            for shape_payload, geometry in slide_edits:
                shape_element = _shape_xml_element(root, shape_payload)
                transform = _shape_transform_xml_element(shape_element)
                _set_transform_geometry(transform, geometry)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _set_transform_geometry(
    transform: ET.Element,
    geometry: tuple[int, int, int, int],
) -> None:
    x_emu, y_emu, cx_emu, cy_emu = geometry
    offset = transform.find(f"{{{A_NS}}}off")
    if offset is None:
        offset = ET.Element(f"{{{A_NS}}}off")
        transform.insert(0, offset)
    extent = transform.find(f"{{{A_NS}}}ext")
    if extent is None:
        extent = ET.Element(f"{{{A_NS}}}ext")
        insert_at = list(transform).index(offset) + 1
        transform.insert(insert_at, extent)
    offset.set("x", str(x_emu))
    offset.set("y", str(y_emu))
    extent.set("cx", str(cx_emu))
    extent.set("cy", str(cy_emu))


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


def _apply_shape_name_edits(
    input_path: Path,
    output_path: Path,
    name_edits: list[tuple[tuple[int, ShapeRef], str]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    slides = (
        slide_payloads
        if slide_payloads is not None
        else _load_slide_payloads(input_path)
    )
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeRef, str]]] = {}
    for (slide_index, shape_ref), name in name_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, name))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, name in slide_edits:
                shape_payload = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload)
                non_visual_properties = shape_element.find(f".//{{{P_NS}}}cNvPr")
                if non_visual_properties is None:
                    raise AttributeError("shape non-visual properties are unavailable")
                non_visual_properties.set("name", name)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_shape_adjustment_edits(
    input_path: Path,
    output_path: Path,
    adjustment_edits: list[tuple[ShapeStyleKey, list[tuple[str, int]]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeRef, list[tuple[str, int]]]]] = {}
    for (slide_index, shape_ref), guides in adjustment_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, guides))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, guides in slide_edits:
                shape_payload = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "shape adjustments are only supported for shape elements"
                    )
                shape_properties = _shape_properties_element(shape_element)
                _set_shape_adjustment_guides(shape_properties, guides)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_shape_line_element_edits(
    input_path: Path,
    output_path: Path,
    line_element_edits: list[tuple[int, ShapeRef]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[ShapeRef]] = {}
    for slide_index, shape_ref in line_element_edits:
        edits_by_slide.setdefault(slide_index, []).append(shape_ref)
    with zipfile.ZipFile(input_path) as package:
        for slide_index, shape_refs in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref in shape_refs:
                shape_payload = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) not in {"sp", "pic", "cxnSp"}:
                    raise AttributeError(
                        "shape line element access is only supported for shape, "
                        "picture, and connector elements"
                    )
                shape_properties = _shape_properties_element(shape_element)
                _get_or_add_shape_line_element(shape_properties)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_picture_crop_edits(
    input_path: Path,
    output_path: Path,
    crop_edits: list[tuple[tuple[int, ShapeRef], dict[str, float]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeRef, dict[str, float]]]] = {}
    for (slide_index, shape_ref), crop in crop_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, crop))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, crop in slide_edits:
                shape_payload = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "pic":
                    raise AttributeError(
                        "picture crop editing is only supported for picture elements"
                    )
                blip_fill = _picture_blip_fill_element(shape_element)
                _set_picture_crop(blip_fill, crop)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_slide_name_edits(
    input_path: Path,
    output_path: Path,
    name_edits: list[tuple[int, str]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for slide_index, name in name_edits:
            try:
                slide_part = str(slides[slide_index]["part"])
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            root = ET.fromstring(package.read(slide_part))
            common_slide_data = root.find(f"{{{P_NS}}}cSld")
            if common_slide_data is None:
                raise AttributeError("slide common data is unavailable")
            if name:
                common_slide_data.set("name", name)
            else:
                common_slide_data.attrib.pop("name", None)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)
