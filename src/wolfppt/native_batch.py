"""Build native edit-batch payloads for save coalescing."""

from __future__ import annotations

from typing import Any


def native_batch_edits(
    table_cell_edits: list[tuple[tuple[int, int, int, int], str]],
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
    text_edits: list[tuple[tuple[int, int], str]],
    group_child_text_edits: list[tuple[tuple[int, int, int], str]],
    group_child_paragraph_text_edits: list[tuple[tuple[int, int, int, int], str]],
    group_child_run_text_edits: list[tuple[tuple[int, int, int, int, int], str]],
    geometry_edits: list[tuple[tuple[int, int], tuple[int, int, int, int]]],
    group_child_geometry_edits: list[
        tuple[tuple[int, int, int], tuple[int, int, int, int]]
    ],
    shape_deletes: list[tuple[int, int]] | None = None,
    slide_order: list[int] | None = None,
    table_row_column_edits: list[dict[str, Any]] | None = None,
    group_child_shape_deletes: list[tuple[int, int, int]] | None = None,
) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    if table_row_column_edits:
        for edit in table_row_column_edits:
            edits.append(dict(edit))
    for (slide_index, table_index, row_index, col_index), text in table_cell_edits:
        edits.append(
            {
                "type": "replace_table_cell_text",
                "slide_index": slide_index,
                "table_index": table_index,
                "row_index": row_index,
                "col_index": col_index,
                "replacement": text,
            }
        )
    for edit in table_cell_merge_edits:
        edits.append(
            {
                "type": "set_table_cell_merge",
                "slide_index": int(edit["slide_index"]),
                "table_index": int(edit["table_index"]),
                "row_min": int(edit["row_min"]),
                "row_max": int(edit["row_max"]),
                "col_min": int(edit["col_min"]),
                "col_max": int(edit["col_max"]),
                "kind": str(edit["kind"]),
                "paragraphs": [str(paragraph) for paragraph in edit.get("paragraphs", [])],
            }
        )
    for (slide_index, table_index), flags in table_style_edits:
        edits.append(
            {
                "type": "set_table_style_flags",
                "slide_index": int(slide_index),
                "table_index": int(table_index),
                "flags": {str(key): bool(value) for key, value in flags.items()},
            }
        )
    for (slide_index, run_index), (_, _, text) in text_run_edits:
        edits.append(
            {
                "type": "replace_text_run",
                "slide_index": slide_index,
                "run_index": run_index,
                "replacement": text,
            }
        )
    run_formatting_edits: dict[tuple[int, int], dict[str, Any]] = {}
    for (slide_index, run_index), (_, _, _, bold) in text_run_bold_edits:
        run_formatting_edits.setdefault((slide_index, run_index), {})["bold"] = bold
    for (slide_index, run_index), (_, _, _, italic) in text_run_italic_edits:
        run_formatting_edits.setdefault((slide_index, run_index), {})["italic"] = italic
    for (slide_index, run_index), (_, _, _, underline) in text_run_underline_edits:
        run_formatting_edits.setdefault((slide_index, run_index), {})["underline"] = underline
    for (slide_index, run_index), (_, _, _, size) in text_run_font_size_edits:
        run_formatting_edits.setdefault((slide_index, run_index), {})["size"] = size
    for (slide_index, run_index), (_, _, _, name) in text_run_font_name_edits:
        run_formatting_edits.setdefault((slide_index, run_index), {})["name"] = name
    for (slide_index, _, _, _), (run_index, rgb) in text_run_font_color_edits:
        run_formatting_edits.setdefault((slide_index, run_index), {})["color"] = rgb
    for (slide_index, shape_index, paragraph_index, _), text in text_run_appends:
        edits.append(
            {
                "type": "append_text_run",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "paragraph_index": paragraph_index,
                "text": text,
            }
        )
    for slide_index, shape_index, paragraph_index, run_slot in paragraph_line_break_edits:
        edits.append(
            {
                "type": "insert_paragraph_line_break",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "paragraph_index": paragraph_index,
                "run_slot": run_slot,
            }
        )
    for (slide_index, shape_index), text in text_edits:
        edits.append(
            {
                "type": "set_shape_text",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "replacement": text,
            }
        )
    for (slide_index, group_index, child_index), text in group_child_text_edits:
        edits.append(
            {
                "type": "set_group_shape_child_text",
                "slide_index": slide_index,
                "group_index": group_index,
                "child_index": child_index,
                "replacement": text,
            }
        )
    for (
        slide_index,
        group_index,
        child_index,
        paragraph_index,
    ), text in group_child_paragraph_text_edits:
        edits.append(
            {
                "type": "set_group_shape_child_paragraph_text",
                "slide_index": slide_index,
                "group_index": group_index,
                "child_index": child_index,
                "paragraph_index": paragraph_index,
                "replacement": text,
            }
        )
    for (
        slide_index,
        group_index,
        child_index,
        paragraph_index,
        run_index,
    ), text in group_child_run_text_edits:
        edits.append(
            {
                "type": "set_group_shape_child_run_text",
                "slide_index": slide_index,
                "group_index": group_index,
                "child_index": child_index,
                "paragraph_index": paragraph_index,
                "run_index": run_index,
                "replacement": text,
            }
        )
    for (slide_index, shape_index, paragraph_index), text in paragraph_text_edits:
        edits.append(
            {
                "type": "set_paragraph_text",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "paragraph_index": paragraph_index,
                "replacement": text,
            }
        )
    for (slide_index, shape_index, _), text in paragraph_appends:
        edits.append(
            {
                "type": "append_paragraph_text",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "text": text,
            }
        )
    paragraph_property_edits = _paragraph_property_edits(
        paragraph_alignment_edits,
        paragraph_level_edits,
        paragraph_spacing_edits,
    )
    for (slide_index, shape_index, paragraph_index), properties in paragraph_property_edits:
        edits.append(
            {
                "type": "set_paragraph_properties",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "paragraph_index": paragraph_index,
                "set_alignment": "alignment" in properties,
                "alignment": properties.get("alignment"),
                "set_level": "level" in properties,
                "level": properties.get("level") or 0,
                "spacing": properties.get("spacing") or {},
            }
        )
    for (slide_index, shape_index, paragraph_index), font in paragraph_font_edits:
        edits.append(
            {
                "type": "set_paragraph_font_properties",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "paragraph_index": paragraph_index,
                "set_bold": "bold" in font,
                "bold": font.get("bold"),
                "set_italic": "italic" in font,
                "italic": font.get("italic"),
                "set_underline": "underline" in font,
                "underline": font.get("underline"),
                "set_size": "size" in font,
                "size": font.get("size"),
                "set_name": "name" in font,
                "name": font.get("name"),
                "set_color": "color" in font,
                "color": font.get("color"),
                "set_fill_type": "fill_type" in font,
                "fill_type": font.get("fill_type"),
                "set_language": "language_id" in font,
                "language_id": font.get("language_id"),
            }
        )
    for (slide_index, shape_index), properties in _text_frame_property_edits(
        text_frame_margin_edits,
        text_frame_word_wrap_edits,
        text_frame_vertical_anchor_edits,
        text_frame_auto_size_edits,
    ):
        edits.append(
            {
                "type": "set_text_frame_properties",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "properties": properties,
            }
        )
    for (slide_index, run_index), formatting in run_formatting_edits.items():
        if len(formatting) == 1 and "color" not in formatting:
            _append_single_run_formatting_edit(edits, slide_index, run_index, formatting)
            continue
        edit = {
            "type": "set_text_run_formatting",
            "slide_index": slide_index,
            "run_index": run_index,
            "set_bold": "bold" in formatting,
            "bold": formatting.get("bold"),
            "set_italic": "italic" in formatting,
            "italic": formatting.get("italic"),
            "set_underline": "underline" in formatting,
            "underline": formatting.get("underline"),
            "set_size": "size" in formatting,
            "size": formatting.get("size"),
            "set_name": "name" in formatting,
            "name": formatting.get("name"),
        }
        if "color" in formatting:
            edit["set_color"] = True
            edit["color"] = formatting["color"]
        edits.append(edit)
    for (slide_index, shape_index), (x_emu, y_emu, cx_emu, cy_emu) in geometry_edits:
        edits.append(
            {
                "type": "set_shape_geometry",
                "slide_index": slide_index,
                "shape_index": shape_index,
                "x_emu": x_emu,
                "y_emu": y_emu,
                "cx_emu": cx_emu,
                "cy_emu": cy_emu,
            }
        )
    for (
        slide_index,
        group_index,
        child_index,
    ), (x_emu, y_emu, cx_emu, cy_emu) in group_child_geometry_edits:
        edits.append(
            {
                "type": "set_group_shape_child_geometry",
                "slide_index": slide_index,
                "group_index": group_index,
                "child_index": child_index,
                "x_emu": x_emu,
                "y_emu": y_emu,
                "cx_emu": cx_emu,
                "cy_emu": cy_emu,
            }
        )
    for slide_index, shape_index in shape_deletes or []:
        edits.append(
            {
                "type": "delete_shape",
                "slide_index": slide_index,
                "shape_index": shape_index,
            }
        )
    for slide_index, group_shape_id, child_shape_id in group_child_shape_deletes or []:
        edits.append(
            {
                "type": "delete_group_shape_child",
                "slide_index": slide_index,
                "group_shape_id": group_shape_id,
                "child_shape_id": child_shape_id,
            }
        )
    if slide_order is not None:
        edits.append(
            {
                "type": "reorder_slides",
                "slide_indices": list(slide_order),
            }
        )
    return edits


def _append_single_run_formatting_edit(
    edits: list[dict[str, Any]],
    slide_index: int,
    run_index: int,
    formatting: dict[str, Any],
) -> None:
    if "bold" in formatting:
        edits.append(
            {
                "type": "set_text_run_bold",
                "slide_index": slide_index,
                "run_index": run_index,
                "bold": formatting["bold"],
            }
        )
        return
    if "italic" in formatting:
        edits.append(
            {
                "type": "set_text_run_italic",
                "slide_index": slide_index,
                "run_index": run_index,
                "italic": formatting["italic"],
            }
        )
        return
    if "underline" in formatting:
        edits.append(
            {
                "type": "set_text_run_underline",
                "slide_index": slide_index,
                "run_index": run_index,
                "underline": formatting["underline"],
            }
        )
        return
    if "size" in formatting:
        edits.append(
            {
                "type": "set_text_run_font_size",
                "slide_index": slide_index,
                "run_index": run_index,
                "size": formatting["size"],
            }
        )
        return
    edits.append(
        {
            "type": "set_text_run_font_name",
            "slide_index": slide_index,
            "run_index": run_index,
            "name": formatting["name"],
        }
    )


def _paragraph_property_edits(
    paragraph_alignment_edits: list[tuple[tuple[int, int, int], str | None]],
    paragraph_level_edits: list[tuple[tuple[int, int, int], int]],
    paragraph_spacing_edits: list[
        tuple[tuple[int, int, int], dict[str, int | float | None]]
    ],
) -> list[tuple[tuple[int, int, int], dict[str, Any]]]:
    edits: dict[tuple[int, int, int], dict[str, Any]] = {}
    for key, alignment in paragraph_alignment_edits:
        edits.setdefault(key, {})["alignment"] = alignment
    for key, level in paragraph_level_edits:
        edits.setdefault(key, {})["level"] = level
    for key, spacing in paragraph_spacing_edits:
        edits.setdefault(key, {})["spacing"] = _paragraph_spacing_patch(spacing)
    return list(edits.items())


def _paragraph_spacing_patch(
    spacing: dict[str, int | float | None],
) -> dict[str, dict[str, Any]]:
    patch: dict[str, dict[str, Any]] = {}
    for key, value in spacing.items():
        if value is None:
            patch[key] = {"kind": "clear"}
        elif key == "line_spacing" and isinstance(value, float):
            patch[key] = {"kind": "multiple", "value": value}
        else:
            patch[key] = {"kind": "emu", "value": int(value)}
    return patch


def _text_frame_property_edits(
    text_frame_margin_edits: list[tuple[tuple[int, int], dict[str, int]]],
    text_frame_word_wrap_edits: list[tuple[tuple[int, int], bool | None]],
    text_frame_vertical_anchor_edits: list[tuple[tuple[int, int], str | None]],
    text_frame_auto_size_edits: list[tuple[tuple[int, int], str | None]],
) -> list[tuple[tuple[int, int], dict[str, Any]]]:
    edits: dict[tuple[int, int], dict[str, Any]] = {}
    for key, margins in text_frame_margin_edits:
        edits.setdefault(key, {})["margins"] = {
            str(attr): int(value) for attr, value in margins.items()
        }
    for key, value in text_frame_word_wrap_edits:
        edits.setdefault(key, {})["set_word_wrap"] = True
        edits[key]["word_wrap"] = _word_wrap_xml_value(value)
    for key, value in text_frame_vertical_anchor_edits:
        edits.setdefault(key, {})["set_vertical_anchor"] = True
        edits[key]["vertical_anchor"] = value
    for key, value in text_frame_auto_size_edits:
        edits.setdefault(key, {})["set_auto_size"] = True
        edits[key]["auto_size"] = value
    return list(edits.items())


def _word_wrap_xml_value(value: bool | None) -> str | None:
    if value is None:
        return None
    return "square" if value else "none"
