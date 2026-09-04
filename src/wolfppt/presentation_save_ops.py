"""Operation dependencies for presentation save orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PresentationSaveOps:
    native: Any
    _apply_chart_add: Any
    _apply_chart_adds: Any
    _apply_chart_axis_property_edits: Any
    _apply_chart_axis_title_edits: Any
    _apply_chart_data_label_edits: Any
    _apply_chart_data_replace: Any
    _apply_chart_font_edits: Any
    _apply_chart_legend_edits: Any
    _apply_chart_plot_property_edits: Any
    _apply_chart_style_edits: Any
    _apply_chart_title_edits: Any
    _apply_background_fill_edits: Any
    _native_batch_edits: Any
    _apply_simple_text_table_chart_replacements: Any
    _simple_package_fast_path_available: Any
    _apply_presentation_size_edits: Any
    _apply_shape_add: Any
    _coalesce_auto_shape_adjustments: Any
    _coalesce_connected_connector_auto_shapes: Any
    _coalesce_auto_shape_text: Any
    _coalesce_table_cell_text: Any
    _apply_paragraph_alignment_edits: Any
    _apply_paragraph_clear_edits: Any
    _apply_paragraph_font_edits: Any
    _apply_paragraph_level_edits: Any
    _apply_part_paragraph_font_edits: Any
    _apply_part_paragraph_property_edits: Any
    _apply_part_text_edits: Any
    _apply_nested_group_child_shape_text_edits: Any
    _apply_part_shape_hyperlink_edits: Any
    _apply_part_shape_text_edits: Any
    _apply_part_text_run_font_edits: Any
    _apply_part_text_run_hyperlink_edits: Any
    _apply_part_text_frame_auto_size_edits: Any
    _apply_part_text_frame_edits: Any
    _apply_part_text_frame_margin_edits: Any
    _apply_part_text_frame_vertical_anchor_edits: Any
    _apply_part_text_frame_word_wrap_edits: Any
    _apply_paragraph_line_break_edits: Any
    _apply_paragraph_property_edits: Any
    _apply_paragraph_spacing_edits: Any
    _apply_picture_crop_edits: Any
    _apply_connector_connection_edits: Any
    _apply_shape_adjustment_edits: Any
    _apply_shape_hyperlink_edits: Any
    _apply_shape_line_element_edits: Any
    _apply_shape_name_edits: Any
    _apply_shape_rotation_edits: Any
    _apply_shape_style_edits: Any
    _apply_shape_target_slide_edits: Any
    _apply_slide_name_edits: Any
    _apply_text_frame_auto_size_edits: Any
    _apply_text_frame_fit_edits: Any
    _apply_text_frame_margin_edits: Any
    _apply_text_frame_vertical_anchor_edits: Any
    _apply_text_frame_word_wrap_edits: Any
    _apply_text_run_font_color_edits: Any
    _apply_text_run_font_fill_type_edits: Any
    _apply_group_child_text_run_font_edits: Any
    _apply_group_child_text_run_hyperlink_edits: Any
    _apply_nested_group_child_geometry_edits: Any
    _apply_group_child_paragraph_alignment_edits: Any
    _apply_group_child_paragraph_clear_edits: Any
    _apply_group_child_paragraph_font_edits: Any
    _apply_group_child_paragraph_line_break_edits: Any
    _apply_group_child_paragraph_level_edits: Any
    _apply_group_child_paragraph_spacing_edits: Any
    _apply_group_child_text_frame_auto_size_edits: Any
    _apply_group_child_text_frame_fit_edits: Any
    _apply_group_child_text_frame_margin_edits: Any
    _apply_group_child_text_frame_vertical_anchor_edits: Any
    _apply_group_child_text_frame_word_wrap_edits: Any
    _apply_text_run_font_language_edits: Any
    _apply_text_run_hyperlink_edits: Any
    _part_shape_text_replacements: Any
    _shape_style_edits: Any
    _apply_table_cell_merge_edits: Any
    _apply_table_cell_property_edits: Any
    _apply_table_dimension_edits: Any
    _apply_table_style_edits: Any
