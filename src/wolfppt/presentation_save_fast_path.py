"""Simple package fast-path step for presentation saves."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .presentation_save_ops import PresentationSaveOps


def apply_simple_package_fast_path(
    owner: Any,
    current: Path,
    final_output: Path,
    tmp_dir: Path,
    step_index: int,
    edits: Any,
    ops: PresentationSaveOps,
) -> tuple[Path, int]:
    simple_package_fast_path = ops._simple_package_fast_path_available(
        chart_data_edits=edits.chart_data_edits,
        part_shape_text_edits=edits.part_shape_text_edits,
        table_cell_edits=edits.table_cell_edits,
        text_edits=edits.text_edits,
        table_cell_merge_edits=edits.table_cell_merge_edits,
        table_style_edits=edits.table_style_edits,
        text_run_edits=edits.text_run_edits,
        text_run_bold_edits=edits.text_run_bold_edits,
        text_run_italic_edits=edits.text_run_italic_edits,
        text_run_underline_edits=edits.text_run_underline_edits,
        text_run_font_size_edits=edits.text_run_font_size_edits,
        text_run_font_name_edits=edits.text_run_font_name_edits,
        text_run_font_color_edits=edits.text_run_font_color_edits,
        text_run_appends=edits.text_run_appends,
        paragraph_line_break_edits=edits.paragraph_line_break_edits,
        paragraph_text_edits=edits.paragraph_text_edits,
        paragraph_appends=edits.paragraph_appends,
        paragraph_alignment_edits=edits.paragraph_alignment_edits,
        paragraph_level_edits=edits.paragraph_level_edits,
        paragraph_spacing_edits=edits.paragraph_spacing_edits,
        paragraph_font_edits=edits.paragraph_font_edits,
        text_frame_margin_edits=edits.text_frame_margin_edits,
        text_frame_word_wrap_edits=edits.text_frame_word_wrap_edits,
        text_frame_vertical_anchor_edits=edits.text_frame_vertical_anchor_edits,
        text_frame_auto_size_edits=edits.text_frame_auto_size_edits,
        text_frame_fit_edits=edits.text_frame_fit_edits,
        group_child_text_edits=edits.group_child_text_edits,
        nested_group_child_text_edits=edits.nested_group_child_text_edits,
        deeper_group_child_text_edits=edits.deeper_group_child_text_edits,
        group_child_paragraph_text_edits=edits.group_child_paragraph_text_edits,
        group_child_run_text_edits=edits.group_child_run_text_edits,
        group_child_run_font_edits=edits.group_child_run_font_edits,
        group_child_run_hyperlink_edits=edits.group_child_run_hyperlink_edits,
        group_child_paragraph_alignment_edits=(
            edits.group_child_paragraph_alignment_edits
        ),
        group_child_paragraph_clear_edits=edits.group_child_paragraph_clear_edits,
        group_child_paragraph_font_edits=edits.group_child_paragraph_font_edits,
        group_child_paragraph_line_break_edits=(
            edits.group_child_paragraph_line_break_edits
        ),
        group_child_paragraph_level_edits=edits.group_child_paragraph_level_edits,
        group_child_paragraph_spacing_edits=edits.group_child_paragraph_spacing_edits,
        group_child_text_frame_margin_edits=edits.group_child_text_frame_margin_edits,
        group_child_text_frame_word_wrap_edits=edits.group_child_text_frame_word_wrap_edits,
        group_child_text_frame_vertical_anchor_edits=(
            edits.group_child_text_frame_vertical_anchor_edits
        ),
        group_child_text_frame_auto_size_edits=(
            edits.group_child_text_frame_auto_size_edits
        ),
        group_child_text_frame_fit_edits=edits.group_child_text_frame_fit_edits,
        geometry_edits=edits.geometry_edits,
        group_child_geometry_edits=edits.group_child_geometry_edits,
        nested_group_child_geometry_edits=edits.nested_group_child_geometry_edits,
        deeper_group_child_geometry_edits=edits.deeper_group_child_geometry_edits,
    )
    if not simple_package_fast_path:
        return current, step_index

    remaining_after_simple_fast_path = any(
        (
            edits.chart_title_edits,
            edits.chart_legend_edits,
            edits.chart_data_label_edits,
            edits.chart_plot_property_edits,
            edits.chart_axis_title_edits,
            edits.chart_axis_property_edits,
            edits.chart_style_edits,
            edits.table_row_height_edits,
            edits.table_column_width_edits,
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
            edits.table_cell_merge_edits,
            edits.table_style_edits,
            edits.paragraph_clear_edits,
            edits.paragraph_line_break_edits,
            edits.paragraph_alignment_edits,
            edits.paragraph_level_edits,
            edits.paragraph_spacing_edits,
            edits.paragraph_font_edits,
            edits.text_frame_margin_edits,
            edits.text_frame_word_wrap_edits,
            edits.text_frame_vertical_anchor_edits,
            edits.text_frame_auto_size_edits,
            edits.text_frame_fit_edits,
            edits.part_paragraph_alignment_edits,
            edits.part_paragraph_level_edits,
            edits.part_paragraph_spacing_edits,
            edits.part_paragraph_font_edits,
            edits.part_run_font_edits,
            edits.part_text_frame_margin_edits,
            edits.part_text_frame_word_wrap_edits,
            edits.part_text_frame_vertical_anchor_edits,
            edits.part_text_frame_auto_size_edits,
            edits.group_child_text_frame_margin_edits,
            edits.group_child_text_frame_word_wrap_edits,
            edits.group_child_text_frame_vertical_anchor_edits,
            edits.group_child_text_frame_auto_size_edits,
            edits.group_child_text_frame_fit_edits,
            edits.nested_group_child_text_edits,
            edits.deeper_group_child_text_edits,
            edits.nested_group_child_geometry_edits,
            edits.deeper_group_child_geometry_edits,
            edits.text_run_font_fill_type_edits,
            edits.text_run_font_language_edits,
            edits.text_run_hyperlink_edits,
            edits.group_child_run_font_edits,
            edits.group_child_run_hyperlink_edits,
            edits.group_child_paragraph_alignment_edits,
            edits.group_child_paragraph_clear_edits,
            edits.group_child_paragraph_font_edits,
            edits.group_child_paragraph_line_break_edits,
            edits.group_child_paragraph_level_edits,
            edits.group_child_paragraph_spacing_edits,
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
            edits.core_properties_edits is not None,
        )
    )
    step = (
        tmp_dir / f"step-{step_index}.pptx"
        if remaining_after_simple_fast_path
        else final_output
    )
    ops._apply_simple_text_table_chart_replacements(
        current,
        step,
        edits.chart_data_edits,
        edits.part_shape_text_edits,
        edits.text_edits,
        edits.table_cell_edits,
        slide_payloads=[
            slide._payload for slide in owner._slides
        ]
        if not (edits.slide_creations or edits.shape_adds)
        else None,
        part_shape_payloads=owner._part_shape_payload_cache,
    )
    current = step
    if remaining_after_simple_fast_path:
        step_index += 1
    edits.chart_data_edits = []
    edits.part_shape_text_edits = []
    edits.table_cell_edits = []
    edits.text_edits = []
    return current, step_index
