"""Table XML edit helpers for presentation saves."""

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
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .slide_payloads import load_slide_payloads as _load_slide_payloads
from .table_text_xml import (
    _has_table_cell_run_hyperlink_edits,
    _set_table_cell_text_frame_fit,
    _set_table_cell_text_frame_paragraph_properties,
    _set_table_cell_text_frame_paragraph_run_properties,
    _set_table_cell_text_frame_paragraph_xml,
    _table_cell_body_properties_element,
)
from .text_xml import (
    _clear_text_frame_auto_size_children,
    _text_frame_auto_size_insert_index,
)
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _apply_table_cell_property_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[int, int, int, int], dict[str, int]]],
    vertical_anchor_edits: list[tuple[tuple[int, int, int, int], str | None]],
    text_frame_margin_edits: list[tuple[tuple[int, int, int, int], dict[str, int]]],
    text_frame_vertical_anchor_edits: list[
        tuple[tuple[int, int, int, int], str | None]
    ],
    text_frame_content_edits: list[tuple[tuple[int, int, int, int], list[str]]],
    text_frame_word_wrap_edits: list[
        tuple[tuple[int, int, int, int], bool | None]
    ],
    text_frame_auto_size_edits: list[
        tuple[tuple[int, int, int, int], str | None]
    ],
    text_frame_fit_edits: list[tuple[tuple[int, int, int, int], dict[str, Any]]],
    text_frame_paragraph_alignment_edits: list[
        tuple[tuple[int, int, int, int, int], str | None]
    ],
    text_frame_paragraph_level_edits: list[
        tuple[tuple[int, int, int, int, int], int]
    ],
    text_frame_paragraph_spacing_edits: list[
        tuple[tuple[int, int, int, int, int], dict[str, int | float | None]]
    ],
    text_frame_paragraph_font_edits: list[
        tuple[tuple[int, int, int, int, int], dict[str, Any]]
    ],
    text_frame_paragraph_run_edits: list[
        tuple[tuple[int, int, int, int, int], list[str]]
    ],
    text_frame_paragraph_line_break_edits: list[
        tuple[int, int, int, int, int, int]
    ],
    text_frame_paragraph_run_font_edits: list[
        tuple[tuple[int, int, int, int, int, int], dict[str, Any]]
    ],
    text_frame_paragraph_run_hyperlink_edits: list[
        tuple[tuple[int, int, int, int, int, int], str | None]
    ],
    fill_solid_edits: list[tuple[int, int, int, int]],
    fill_background_edits: list[tuple[int, int, int, int]],
    fill_pattern_edits: list[tuple[tuple[int, int, int, int], str | None]],
    fill_pattern_fore_color_edits: list[tuple[tuple[int, int, int, int], str]],
    fill_pattern_back_color_edits: list[tuple[tuple[int, int, int, int], str]],
    fill_color_edits: list[tuple[tuple[int, int, int, int], str]],
    fill_gradient_edits: list[tuple[tuple[int, int, int, int], dict[str, Any]]],
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
        dict[tuple[int, int, int], dict[str, Any]],
    ] = {}
    for (slide_index, table_index, row_index, col_index), margins in margin_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("margins", {}).update(margins)
    for (slide_index, table_index, row_index, col_index), anchor in vertical_anchor_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["vertical_anchor"] = anchor
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), margins in text_frame_margin_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_margins", {}).update(margins)
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), anchor in text_frame_vertical_anchor_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["text_frame_vertical_anchor"] = anchor
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), paragraphs in text_frame_content_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["text_frame_paragraphs"] = list(paragraphs)
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), word_wrap in text_frame_word_wrap_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["text_frame_word_wrap"] = word_wrap
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), auto_size in text_frame_auto_size_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["text_frame_auto_size"] = auto_size
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), fit in text_frame_fit_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["text_frame_fit"] = dict(fit)
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
        paragraph_index,
    ), alignment in text_frame_paragraph_alignment_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_paragraph_properties", {}).setdefault(
            paragraph_index,
            {},
        )["alignment"] = alignment
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
        paragraph_index,
    ), level in text_frame_paragraph_level_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_paragraph_properties", {}).setdefault(
            paragraph_index,
            {},
        )["level"] = level
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
        paragraph_index,
    ), spacing in text_frame_paragraph_spacing_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_paragraph_properties", {}).setdefault(
            paragraph_index,
            {},
        )["spacing"] = dict(spacing)
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
        paragraph_index,
    ), font in text_frame_paragraph_font_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_paragraph_properties", {}).setdefault(
            paragraph_index,
            {},
        ).setdefault("font", {}).update(font)
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
        paragraph_index,
    ), runs in text_frame_paragraph_run_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_paragraph_properties", {}).setdefault(
            paragraph_index,
            {},
        )["runs"] = list(runs)
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
        paragraph_index,
        run_slot,
    ) in text_frame_paragraph_line_break_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_paragraph_properties", {}).setdefault(
            paragraph_index,
            {},
        ).setdefault("line_breaks", []).append(run_slot)
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
        paragraph_index,
        run_index,
    ), font in text_frame_paragraph_run_font_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_paragraph_run_properties", {}).setdefault(
            paragraph_index,
            {},
        ).setdefault(run_index, {}).setdefault("font", {}).update(font)
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
        paragraph_index,
        run_index,
    ), address in text_frame_paragraph_run_hyperlink_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        ).setdefault("text_frame_paragraph_run_properties", {}).setdefault(
            paragraph_index,
            {},
        ).setdefault(run_index, {})["hyperlink"] = address
    for key in fill_solid_edits:
        slide_index, table_index, row_index, col_index = key
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["fill_solid"] = True
    for key in fill_background_edits:
        slide_index, table_index, row_index, col_index = key
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["fill_background"] = True
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), pattern in fill_pattern_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["fill_pattern"] = pattern
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), rgb in fill_pattern_fore_color_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["fill_pattern_fore"] = rgb
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), rgb in fill_pattern_back_color_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["fill_pattern_back"] = rgb
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), rgb in fill_color_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["fill"] = rgb
    for (
        slide_index,
        table_index,
        row_index,
        col_index,
    ), gradient in fill_gradient_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            (table_index, row_index, col_index),
            {},
        )["fill_gradient"] = dict(gradient)

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            needs_rels = any(
                _has_table_cell_run_hyperlink_edits(
                    edits.get("text_frame_paragraph_run_properties", {})
                )
                for edits in slide_edits.values()
            )
            rels_part = _rels_part_for_package_part(slide_part)
            if needs_rels:
                try:
                    rels_root = ET.fromstring(package.read(rels_part))
                except KeyError:
                    rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            else:
                rels_root = None
            for (table_index, row_index, col_index), edits in slide_edits.items():
                cell_element = _table_cell_xml_element(
                    root,
                    table_index,
                    row_index,
                    col_index,
                )
                cell_properties = _table_cell_properties_element(cell_element)
                for attr, value in edits.get("margins", {}).items():
                    cell_properties.set(attr, str(value))
                if edits.get("fill_solid"):
                    _set_shape_solid_fill(cell_properties)
                if edits.get("fill_background"):
                    _set_shape_no_fill(cell_properties)
                if "fill_pattern" in edits:
                    _set_shape_pattern_fill(cell_properties, edits["fill_pattern"])
                if "fill_pattern_fore" in edits:
                    _set_shape_pattern_fill_color(
                        cell_properties,
                        "fgClr",
                        edits["fill_pattern_fore"],
                    )
                if "fill_pattern_back" in edits:
                    _set_shape_pattern_fill_color(
                        cell_properties,
                        "bgClr",
                        edits["fill_pattern_back"],
                    )
                if "fill" in edits:
                    _set_shape_solid_fill(cell_properties, edits["fill"])
                if "fill_gradient" in edits:
                    _set_shape_gradient_fill(cell_properties, edits["fill_gradient"])
                if "vertical_anchor" in edits:
                    anchor = edits["vertical_anchor"]
                    if anchor is None:
                        cell_properties.attrib.pop("anchor", None)
                    else:
                        cell_properties.set("anchor", str(anchor))
                if "text_frame_margins" in edits:
                    body_properties = _table_cell_body_properties_element(cell_element)
                    for attr, value in edits["text_frame_margins"].items():
                        body_properties.set(attr, str(value))
                if "text_frame_vertical_anchor" in edits:
                    body_properties = _table_cell_body_properties_element(cell_element)
                    anchor = edits["text_frame_vertical_anchor"]
                    if anchor is None:
                        body_properties.attrib.pop("anchor", None)
                    else:
                        body_properties.set("anchor", str(anchor))
                if "text_frame_paragraphs" in edits:
                    _set_table_cell_text_frame_paragraph_xml(
                        cell_element,
                        edits["text_frame_paragraphs"],
                    )
                if "text_frame_word_wrap" in edits:
                    body_properties = _table_cell_body_properties_element(cell_element)
                    word_wrap = edits["text_frame_word_wrap"]
                    if word_wrap is None:
                        body_properties.attrib.pop("wrap", None)
                    else:
                        body_properties.set("wrap", "square" if word_wrap else "none")
                if "text_frame_auto_size" in edits:
                    body_properties = _table_cell_body_properties_element(cell_element)
                    _clear_text_frame_auto_size_children(body_properties)
                    auto_size = edits["text_frame_auto_size"]
                    if auto_size is not None:
                        body_properties.insert(
                            _text_frame_auto_size_insert_index(body_properties),
                            ET.Element(f"{{{A_NS}}}{auto_size}"),
                        )
                if "text_frame_fit" in edits:
                    _set_table_cell_text_frame_fit(
                        cell_element,
                        edits["text_frame_fit"],
                    )
                if "text_frame_paragraph_properties" in edits:
                    _set_table_cell_text_frame_paragraph_properties(
                        cell_element,
                        edits["text_frame_paragraph_properties"],
                    )
                if "text_frame_paragraph_run_properties" in edits:
                    _set_table_cell_text_frame_paragraph_run_properties(
                        cell_element,
                        edits["text_frame_paragraph_run_properties"],
                        rels_root,
                    )
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
            if rels_root is not None:
                replacements[rels_part] = ET.tostring(
                    rels_root,
                    encoding="utf-8",
                    xml_declaration=True,
                )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_table_dimension_edits(
    input_path: Path,
    output_path: Path,
    row_height_edits: list[tuple[tuple[int, int, int], int]],
    column_width_edits: list[tuple[tuple[int, int, int], int]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, dict[int, dict[str, dict[int, int]]]] = {}
    for (slide_index, table_index, row_index), height in row_height_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            table_index,
            {"rows": {}, "columns": {}},
        )["rows"][row_index] = height
    for (slide_index, table_index, column_index), width in column_width_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(
            table_index,
            {"rows": {}, "columns": {}},
        )["columns"][column_index] = width

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for table_index, edits in slide_edits.items():
                frame = _table_graphic_frame(root, table_index)
                table = _table_xml_element(root, table_index)
                for row_index, height in edits["rows"].items():
                    rows = table.findall(f"{{{A_NS}}}tr")
                    try:
                        rows[row_index].set("h", str(height))
                    except IndexError as exc:
                        raise IndexError("table row index out of range") from exc
                grid = table.find(f"{{{A_NS}}}tblGrid")
                if grid is None:
                    raise AttributeError("table grid is unavailable")
                for column_index, width in edits["columns"].items():
                    columns = grid.findall(f"{{{A_NS}}}gridCol")
                    try:
                        columns[column_index].set("w", str(width))
                    except IndexError as exc:
                        raise IndexError("table column index out of range") from exc
                _sync_table_frame_extent(frame, table)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_table_cell_merge_edits(
    input_path: Path,
    output_path: Path,
    merge_edits: list[dict[str, Any]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[dict[str, Any]]] = {}
    for edit in merge_edits:
        edits_by_slide.setdefault(int(edit["slide_index"]), []).append(dict(edit))

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for edit in slide_edits:
                table_index = int(edit["table_index"])
                row_min = int(edit["row_min"])
                row_max = int(edit["row_max"])
                col_min = int(edit["col_min"])
                col_max = int(edit["col_max"])
                if edit.get("kind") == "merge":
                    _apply_table_cell_merge_xml(
                        root,
                        table_index,
                        row_min,
                        row_max,
                        col_min,
                        col_max,
                        [str(paragraph) for paragraph in edit.get("paragraphs", [])]
                        or [""],
                    )
                elif edit.get("kind") == "split":
                    _apply_table_cell_split_xml(
                        root,
                        table_index,
                        row_min,
                        row_max,
                        col_min,
                        col_max,
                    )
                else:
                    raise ValueError(f"unknown table cell merge edit: {edit!r}")
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_table_cell_merge_xml(
    root: ET.Element,
    table_index: int,
    row_min: int,
    row_max: int,
    col_min: int,
    col_max: int,
    paragraphs: list[str],
) -> None:
    row_count = row_max - row_min + 1
    col_count = col_max - col_min + 1
    for row_index in range(row_min, row_max + 1):
        for col_index in range(col_min, col_max + 1):
            cell_element = _table_cell_xml_element(
                root,
                table_index,
                row_index,
                col_index,
            )
            if (row_index, col_index) == (row_min, col_min):
                _set_table_cell_text_frame_paragraph_xml(cell_element, paragraphs)
            else:
                _set_table_cell_text_frame_paragraph_xml(cell_element, [""])
            _set_table_cell_merge_attrs(
                cell_element,
                row_span=row_count if row_index == row_min else 1,
                grid_span=col_count if col_index == col_min else 1,
                h_merge=col_index != col_min,
                v_merge=row_index != row_min,
            )


def _apply_table_cell_split_xml(
    root: ET.Element,
    table_index: int,
    row_min: int,
    row_max: int,
    col_min: int,
    col_max: int,
) -> None:
    for row_index in range(row_min, row_max + 1):
        for col_index in range(col_min, col_max + 1):
            cell_element = _table_cell_xml_element(
                root,
                table_index,
                row_index,
                col_index,
            )
            _set_table_cell_merge_attrs(
                cell_element,
                row_span=1,
                grid_span=1,
                h_merge=False,
                v_merge=False,
            )


def _set_table_cell_merge_attrs(
    cell_element: ET.Element,
    row_span: int,
    grid_span: int,
    h_merge: bool,
    v_merge: bool,
) -> None:
    if row_span > 1:
        cell_element.set("rowSpan", str(row_span))
    else:
        cell_element.attrib.pop("rowSpan", None)
    if grid_span > 1:
        cell_element.set("gridSpan", str(grid_span))
    else:
        cell_element.attrib.pop("gridSpan", None)
    if h_merge:
        cell_element.set("hMerge", "1")
    else:
        cell_element.attrib.pop("hMerge", None)
    if v_merge:
        cell_element.set("vMerge", "1")
    else:
        cell_element.attrib.pop("vMerge", None)


def _apply_table_style_edits(
    input_path: Path,
    output_path: Path,
    style_edits: list[tuple[tuple[int, int], dict[str, bool]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, dict[int, dict[str, bool]]] = {}
    for (slide_index, table_index), edits in style_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault(table_index, {}).update(
            edits
        )

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for table_index, edits in slide_edits.items():
                table_element = _table_xml_element(root, table_index)
                table_properties = _table_properties_element(table_element)
                for attr, value in edits.items():
                    if value:
                        table_properties.set(attr, "1")
                    else:
                        table_properties.attrib.pop(attr, None)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _table_xml_element(root: ET.Element, table_index: int) -> ET.Element:
    tables = root.findall(f".//{{{A_NS}}}tbl")
    try:
        return tables[table_index]
    except IndexError as exc:
        raise IndexError("table index out of range") from exc


def _table_graphic_frame(root: ET.Element, table_index: int) -> ET.Element:
    frames = [
        frame
        for frame in root.findall(f".//{{{P_NS}}}graphicFrame")
        if frame.find(f".//{{{A_NS}}}tbl") is not None
    ]
    try:
        return frames[table_index]
    except IndexError as exc:
        raise IndexError("table index out of range") from exc


def _sync_table_frame_extent(frame: ET.Element, table: ET.Element) -> None:
    extent = frame.find(f"{{{P_NS}}}xfrm/{{{A_NS}}}ext")
    if extent is None:
        return
    widths = [
        _int_attr(column, "w")
        for column in table.findall(f"{{{A_NS}}}tblGrid/{{{A_NS}}}gridCol")
    ]
    heights = [_int_attr(row, "h") for row in table.findall(f"{{{A_NS}}}tr")]
    if widths:
        extent.set("cx", str(sum(widths)))
    if heights:
        extent.set("cy", str(sum(heights)))


def _int_attr(element: ET.Element, attr: str) -> int:
    try:
        return int(element.attrib.get(attr, "0"))
    except ValueError:
        return 0


def _table_properties_element(table_element: ET.Element) -> ET.Element:
    table_properties = table_element.find(f"{{{A_NS}}}tblPr")
    if table_properties is not None:
        return table_properties
    table_properties = ET.Element(f"{{{A_NS}}}tblPr")
    insert_at = 0
    for index, child in enumerate(list(table_element)):
        if _xml_local_name(child.tag) in {"tblGrid", "tr", "extLst"}:
            insert_at = index
            break
    table_element.insert(insert_at, table_properties)
    return table_properties


def _table_cell_xml_element(
    root: ET.Element,
    table_index: int,
    row_index: int,
    col_index: int,
) -> ET.Element:
    table = _table_xml_element(root, table_index)
    rows = table.findall(f"{{{A_NS}}}tr")
    try:
        row = rows[row_index]
    except IndexError as exc:
        raise IndexError("table row index out of range") from exc
    cells = row.findall(f"{{{A_NS}}}tc")
    try:
        return cells[col_index]
    except IndexError as exc:
        raise IndexError("table column index out of range") from exc


def _table_cell_properties_element(cell_element: ET.Element) -> ET.Element:
    cell_properties = cell_element.find(f"{{{A_NS}}}tcPr")
    if cell_properties is not None:
        return cell_properties
    cell_properties = ET.Element(f"{{{A_NS}}}tcPr")
    cell_element.append(cell_properties)
    return cell_properties
