"""Package-level replacement builders for narrow save fast paths."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .chart_edits import _chart_data_replacements_from_package
from .package_parts import (
    copy_open_package_with_replacements as _copy_open_package_with_replacements,
    normalize_package_partname as _normalize_package_partname,
)
from .shape_xml import _shape_xml_element
from .slide_edits import _part_shape_text_replacements_from_package, _set_shape_text
from .slide_payloads import load_slide_payloads as _load_slide_payloads
from .table_xml import _set_table_cell_text_frame_paragraph_xml, _table_cell_xml_element
from .xml_helpers import xml_local_name as _xml_local_name


def apply_simple_text_table_chart_replacements(
    input_path: Path,
    output_path: Path,
    chart_data_edits: list[tuple[tuple[int, int], dict[str, Any]]],
    part_shape_text_edits: list[tuple[tuple[str, int], str]],
    text_edits: list[tuple[tuple[int, int], str]],
    table_cell_edits: list[tuple[tuple[int, int, int, int], str]],
    slide_payloads: list[dict[str, Any]] | None = None,
    part_shape_payloads: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    with zipfile.ZipFile(input_path) as package:
        replacements = _simple_text_table_chart_replacements_from_package(
            package,
            input_path,
            chart_data_edits,
            part_shape_text_edits,
            text_edits,
            table_cell_edits,
            slide_payloads=slide_payloads,
            part_shape_payloads=part_shape_payloads,
        )
        _copy_open_package_with_replacements(package, output_path, replacements)


def _simple_text_table_chart_replacements_from_package(
    package: zipfile.ZipFile,
    input_path: Path,
    chart_data_edits: list[tuple[tuple[int, int], dict[str, Any]]],
    part_shape_text_edits: list[tuple[tuple[str, int], str]],
    text_edits: list[tuple[tuple[int, int], str]],
    table_cell_edits: list[tuple[tuple[int, int, int, int], str]],
    slide_payloads: list[dict[str, Any]] | None = None,
    part_shape_payloads: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, bytes]:
    replacements: dict[str, bytes] = {}
    for (slide_index, shape_index), chart_data in chart_data_edits:
        _merge_replacements(
            replacements,
            _chart_data_replacements_from_package(
                package,
                input_path,
                slide_index,
                shape_index,
                chart_data,
            ),
        )
    if part_shape_text_edits:
        _merge_replacements(
            replacements,
            _part_shape_text_replacements_from_package(
                package,
                input_path,
                part_shape_text_edits,
                shape_payloads_by_part=part_shape_payloads,
            ),
        )
    if text_edits or table_cell_edits:
        _merge_replacements(
            replacements,
            _visible_text_table_replacements_from_package(
                package,
                input_path,
                text_edits,
                table_cell_edits,
                slide_payloads=slide_payloads,
            ),
        )
    return replacements


def _visible_text_table_replacements_from_package(
    package: zipfile.ZipFile,
    input_path: Path,
    text_edits: list[tuple[tuple[int, int], str]],
    table_cell_edits: list[tuple[tuple[int, int, int, int], str]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> dict[str, bytes]:
    slides = (
        slide_payloads
        if slide_payloads is not None
        else _load_slide_payloads(input_path)
    )
    edits_by_slide: dict[int, dict[str, list[Any]]] = {}
    for (slide_index, shape_index), text in text_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault("shape_text", []).append(
            (shape_index, text)
        )
    for (slide_index, table_index, row_index, col_index), text in table_cell_edits:
        edits_by_slide.setdefault(slide_index, {}).setdefault("table_cell", []).append(
            (table_index, row_index, col_index, text)
        )

    replacements: dict[str, bytes] = {}
    for slide_index, slide_edits in edits_by_slide.items():
        try:
            slide_payload = slides[slide_index]
        except IndexError as exc:
            raise IndexError("slide index out of range") from exc
        slide_part = str(slide_payload["part"])
        root = ET.fromstring(package.read(slide_part))
        for shape_index, text in slide_edits.get("shape_text", []):
            shape_payloads = slide_payload.get("shapes")
            if shape_payloads is None:
                shape_payloads = slide_payload.get("shape_shell_hints")
            if not isinstance(shape_payloads, list):
                raise KeyError("shapes")
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
        for table_index, row_index, col_index, text in slide_edits.get(
            "table_cell",
            [],
        ):
            cell_element = _table_cell_xml_element(
                root,
                table_index,
                row_index,
                col_index,
            )
            paragraphs = text.split("\n") if text else [""]
            _set_table_cell_text_frame_paragraph_xml(cell_element, paragraphs)
        replacements[slide_part] = ET.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
        )
    return replacements


def _merge_replacements(
    target: dict[str, bytes],
    additions: dict[str, bytes],
) -> None:
    for raw_name, payload in additions.items():
        name = _normalize_package_partname(raw_name).lstrip("/")
        if name in target:
            raise ValueError(f"coalesced package replacement overlaps {name!r}")
        target[name] = payload


def simple_package_fast_path_available(
    *,
    chart_data_edits: list[tuple[tuple[int, int], dict[str, Any]]],
    part_shape_text_edits: list[tuple[tuple[str, int], str]],
    table_cell_edits: list[tuple[tuple[int, int, int, int], str]],
    text_edits: list[tuple[tuple[int, int], str]],
    table_cell_merge_edits: list[dict[str, Any]],
    table_style_edits: list[tuple[tuple[int, int], dict[str, bool]]],
    text_run_edits: list[tuple[tuple[int, int], tuple[int, int, str]]],
    text_run_bold_edits: list[
        tuple[tuple[int, int], tuple[int, int, int, bool | None]]
    ],
    text_run_italic_edits: list[
        tuple[tuple[int, int], tuple[int, int, int, bool | None]]
    ],
    text_run_underline_edits: list[
        tuple[tuple[int, int], tuple[int, int, int, bool | None]]
    ],
    text_run_font_size_edits: list[
        tuple[tuple[int, int], tuple[int, int, int, int | None]]
    ],
    text_run_font_name_edits: list[
        tuple[tuple[int, int], tuple[int, int, int, str | None]]
    ],
    text_run_font_color_edits: list[
        tuple[tuple[int, int, int, int], tuple[int, str]]
    ],
    text_run_appends: list[tuple[tuple[int, int, int, int], str]],
    paragraph_line_break_edits: list[tuple[int, int, int, int]],
    paragraph_text_edits: list[tuple[tuple[int, int, int], str]],
    paragraph_appends: list[tuple[tuple[int, int, int], str]],
    paragraph_alignment_edits: list[tuple[tuple[int, int, int], str | None]],
    paragraph_level_edits: list[tuple[tuple[int, int, int], int]],
    paragraph_spacing_edits: list[
        tuple[tuple[int, int, int], dict[str, int | float | None]]
    ],
    paragraph_font_edits: list[tuple[tuple[int, int, int], dict[str, Any]]],
    text_frame_margin_edits: list[tuple[tuple[int, int], dict[str, int]]],
    text_frame_word_wrap_edits: list[tuple[tuple[int, int], bool | None]],
    text_frame_vertical_anchor_edits: list[tuple[tuple[int, int], str | None]],
    text_frame_auto_size_edits: list[tuple[tuple[int, int], str | None]],
    text_frame_fit_edits: list[tuple[tuple[int, int], dict[str, Any]]],
    group_child_text_edits: list[tuple[tuple[int, int, int], str]],
    nested_group_child_text_edits: list[tuple[tuple[int, int, int, int], str]],
    deeper_group_child_text_edits: list[tuple[tuple[int, int, int, int, int], str]],
    group_child_paragraph_text_edits: list[tuple[tuple[int, int, int, int], str]],
    group_child_run_text_edits: list[tuple[tuple[int, int, int, int, int], str]],
    group_child_run_font_edits: list[
        tuple[tuple[int, int, int, int, int], dict[str, Any]]
    ],
    group_child_run_hyperlink_edits: list[
        tuple[tuple[int, int, int, int, int], str | None]
    ],
    group_child_paragraph_alignment_edits: list[
        tuple[tuple[int, int, int, int], str | None]
    ],
    group_child_paragraph_clear_edits: list[tuple[int, int, int, int]],
    group_child_paragraph_font_edits: list[
        tuple[tuple[int, int, int, int], dict[str, Any]]
    ],
    group_child_paragraph_line_break_edits: list[tuple[int, int, int, int, int]],
    group_child_paragraph_level_edits: list[tuple[tuple[int, int, int, int], int]],
    group_child_paragraph_spacing_edits: list[
        tuple[tuple[int, int, int, int], dict[str, int | float | None]]
    ],
    group_child_text_frame_margin_edits: list[
        tuple[tuple[int, int, int], dict[str, int]]
    ],
    group_child_text_frame_word_wrap_edits: list[
        tuple[tuple[int, int, int], bool | None]
    ],
    group_child_text_frame_vertical_anchor_edits: list[
        tuple[tuple[int, int, int], str | None]
    ],
    group_child_text_frame_auto_size_edits: list[
        tuple[tuple[int, int, int], str | None]
    ],
    group_child_text_frame_fit_edits: list[
        tuple[tuple[int, int, int], dict[str, Any]]
    ],
    geometry_edits: list[tuple[tuple[int, int], tuple[int, int, int, int]]],
    group_child_geometry_edits: list[
        tuple[tuple[int, int, int], tuple[int, int, int, int]]
    ],
    nested_group_child_geometry_edits: list[
        tuple[tuple[int, int, int, int], tuple[int, int, int, int]]
    ],
    deeper_group_child_geometry_edits: list[
        tuple[tuple[int, int, int, int, int], tuple[int, int, int, int]]
    ],
) -> bool:
    if not (chart_data_edits or part_shape_text_edits):
        return False
    if not (table_cell_edits or text_edits):
        return False
    return not any(
        (
            table_cell_merge_edits,
            table_style_edits,
            text_run_edits,
            text_run_bold_edits,
            text_run_italic_edits,
            text_run_underline_edits,
            text_run_font_size_edits,
            text_run_font_name_edits,
            text_run_font_color_edits,
            text_run_appends,
            paragraph_line_break_edits,
            paragraph_text_edits,
            paragraph_appends,
            paragraph_alignment_edits,
            paragraph_level_edits,
            paragraph_spacing_edits,
            paragraph_font_edits,
            text_frame_margin_edits,
            text_frame_word_wrap_edits,
            text_frame_vertical_anchor_edits,
            text_frame_auto_size_edits,
            text_frame_fit_edits,
            group_child_text_edits,
            nested_group_child_text_edits,
            deeper_group_child_text_edits,
            group_child_paragraph_text_edits,
            group_child_run_text_edits,
            group_child_run_font_edits,
            group_child_run_hyperlink_edits,
            group_child_paragraph_alignment_edits,
            group_child_paragraph_clear_edits,
            group_child_paragraph_font_edits,
            group_child_paragraph_line_break_edits,
            group_child_paragraph_level_edits,
            group_child_paragraph_spacing_edits,
            group_child_text_frame_margin_edits,
            group_child_text_frame_word_wrap_edits,
            group_child_text_frame_vertical_anchor_edits,
            group_child_text_frame_auto_size_edits,
            group_child_text_frame_fit_edits,
            geometry_edits,
            group_child_geometry_edits,
            nested_group_child_geometry_edits,
            deeper_group_child_geometry_edits,
        )
    )
