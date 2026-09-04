"""Planning helpers for save orchestration."""

from __future__ import annotations

from typing import Any

CHART_ADD_KINDS = {
    "chart",
    "group_chart",
    "nested_group_chart",
    "deeper_nested_group_chart",
    "nested_group_chart_in_new_group",
}


def shape_add_as_chart_add(add_kind: str, args: tuple[Any, ...]) -> tuple[Any, ...]:
    if add_kind == "chart":
        slide_index, chart_type, chart_data, x_emu, y_emu, cx_emu, cy_emu = args
        return (
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            None,
            None,
            None,
            False,
        )
    if add_kind == "group_chart":
        (
            slide_index,
            group_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        return (
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index,
            None,
            None,
            False,
        )
    if add_kind == "nested_group_chart":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        return (
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index,
            nested_group_child_index,
            None,
            False,
        )
    if add_kind == "deeper_nested_group_chart":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        return (
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            False,
        )
    if add_kind == "nested_group_chart_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        return (
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index,
            None,
            None,
            True,
        )
    raise ValueError(f"shape add is not a chart add: {add_kind}")


def has_edits_after_shape_adds(edits: Any) -> bool:
    for name, value in vars(edits).items():
        if name in {"slide_creations", "shape_adds"}:
            continue
        if value:
            return True
    return False


def has_edits_after_slide_creations(edits: Any) -> bool:
    for name, value in vars(edits).items():
        if name == "slide_creations":
            continue
        if value:
            return True
    return False

def has_edits_after_slide_deletions(edits: Any) -> bool:
    for name, value in vars(edits).items():
        if name == "slide_deletions":
            continue
        if value:
            return True
    return False

def has_edits_after_native_batch(
    edits: Any,
    *,
    table_cell_merges_in_native_batch: bool,
    table_style_in_native_batch: bool,
    line_breaks_in_native_batch: bool,
    paragraph_properties_in_native_batch: bool,
    paragraph_font_in_native_batch: bool,
    text_frame_properties_in_native_batch: bool,
    text_run_font_color_xml_edits: bool = False,
) -> bool:
    remaining_edits = [
        edits.group_child_run_font_edits,
        edits.group_child_paragraph_clear_edits,
        edits.group_child_paragraph_line_break_edits,
        edits.group_child_paragraph_alignment_edits,
        edits.group_child_paragraph_font_edits,
        edits.group_child_paragraph_level_edits,
        edits.group_child_paragraph_spacing_edits,
        edits.nested_group_child_text_edits,
        edits.deeper_group_child_text_edits,
        edits.nested_group_child_geometry_edits,
        edits.deeper_group_child_geometry_edits,
        edits.part_shape_text_edits,
        edits.part_paragraph_alignment_edits,
        edits.part_paragraph_level_edits,
        edits.part_paragraph_spacing_edits,
        edits.part_paragraph_font_edits,
        edits.part_run_font_edits,
        edits.part_text_frame_margin_edits,
        edits.part_text_frame_word_wrap_edits,
        edits.part_text_frame_vertical_anchor_edits,
        edits.part_text_frame_auto_size_edits,
        edits.table_cell_margin_edits,
        edits.table_cell_vertical_anchor_edits,
        edits.table_cell_text_frame_margin_edits,
        edits.table_cell_text_frame_vertical_anchor_edits,
        edits.table_cell_text_frame_content_edits,
        edits.table_cell_text_frame_word_wrap_edits,
        edits.table_cell_text_frame_auto_size_edits,
        edits.table_cell_text_frame_fit_edits,
        edits.table_cell_text_frame_paragraph_line_break_edits,
        edits.table_cell_text_frame_paragraph_run_font_edits,
        edits.table_cell_text_frame_paragraph_run_hyperlink_edits,
        edits.table_cell_fill_solid_edits,
        edits.table_cell_fill_background_edits,
        edits.table_cell_fill_pattern_edits,
        edits.table_cell_fill_pattern_fore_color_edits,
        edits.table_cell_fill_pattern_back_color_edits,
        edits.table_cell_fill_color_edits,
        edits.table_cell_fill_gradient_edits,
        edits.background_fill_solid_edits,
        edits.background_fill_background_edits,
        edits.background_fill_color_edits,
        edits.table_row_height_edits,
        edits.table_column_width_edits,
        edits.paragraph_clear_edits,
        edits.text_frame_fit_edits,
        edits.group_child_text_frame_margin_edits,
        edits.group_child_text_frame_word_wrap_edits,
        edits.group_child_text_frame_vertical_anchor_edits,
        edits.group_child_text_frame_auto_size_edits,
        edits.group_child_text_frame_fit_edits,
        edits.text_run_font_fill_type_edits,
        edits.text_run_font_language_edits,
        edits.text_run_hyperlink_edits,
        edits.group_child_run_hyperlink_edits,
        edits.fill_solid_edits,
        edits.fill_background_edits,
        edits.fill_pattern_edits,
        edits.fill_pattern_fore_color_edits,
        edits.fill_pattern_back_color_edits,
        edits.fill_color_edits,
        edits.fill_gradient_edits,
        edits.line_solid_edits,
        edits.line_background_edits,
        edits.line_pattern_edits,
        edits.line_pattern_fore_color_edits,
        edits.line_pattern_back_color_edits,
        edits.line_color_edits,
        edits.line_width_edits,
        edits.line_dash_edits,
        edits.connector_connection_edits,
        edits.shadow_inherit_edits,
        edits.hyperlink_edits,
        edits.target_slide_edits,
        edits.rotation_edits,
        edits.name_edits,
        edits.adjustment_edits,
        edits.line_element_edits,
        edits.picture_crop_edits,
        edits.picture_replace_edits,
        edits.slide_name_edits,
        edits.presentation_size_edits,
        edits.slide_layout_removals,
        edits.notes_slide_adds,
    ]
    if any(remaining_edits):
        return True
    if edits.core_properties_edits is not None:
        return True
    if edits.table_cell_merge_edits and not table_cell_merges_in_native_batch:
        return True
    if edits.table_style_edits and not table_style_in_native_batch:
        return True
    if edits.paragraph_line_break_edits and not line_breaks_in_native_batch:
        return True
    if (
        edits.paragraph_alignment_edits
        or edits.paragraph_level_edits
        or edits.paragraph_spacing_edits
    ) and not paragraph_properties_in_native_batch:
        return True
    if edits.paragraph_font_edits and not paragraph_font_in_native_batch:
        return True
    if (
        edits.text_frame_margin_edits
        or edits.text_frame_word_wrap_edits
        or edits.text_frame_vertical_anchor_edits
        or edits.text_frame_auto_size_edits
    ) and not text_frame_properties_in_native_batch:
        return True
    if text_run_font_color_xml_edits:
        return True
    return False
