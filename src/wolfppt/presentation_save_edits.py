"""Snapshot pending facade edits before save orchestration mutates them."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from .presentation_save_ops import PresentationSaveOps
from .shape_payloads import _invalidate_shape_text_cache


def _invalidate_presentation_text_cache(presentation: Any) -> None:
    slides = getattr(presentation, "_slides", None)
    if slides is None:
        return
    for slide in slides:
        shapes = getattr(slide, "_shapes", None)
        if shapes is None:
            continue
        for shape in shapes:
            _invalidate_shape_hierarchy_text_cache(shape)


def _invalidate_shape_hierarchy_text_cache(shape: Any) -> None:
    _invalidate_shape_text_cache(shape)
    child_shapes = getattr(shape, "_shapes", None)
    if child_shapes:
        for child in child_shapes:
            _invalidate_shape_hierarchy_text_cache(child)
def collect_save_edits(self: Any, ops: PresentationSaveOps) -> SimpleNamespace:
    _invalidate_presentation_text_cache(self)
    slide_creations = list(self._slide_creations)
    slide_deletions = list(self._slide_deletions)
    slide_order = None if self._slide_order is None else list(self._slide_order)
    slide_layout_removals = list(self._slide_layout_removals)
    notes_slide_adds = [
        (slide_index, slide_part, notes_part)
        for slide_index, (slide_part, notes_part) in self._notes_slide_adds.items()
    ]
    part_placeholder_adds = list(self._part_placeholder_adds)
    shape_adds = list(self._shape_adds)
    shape_deletes = sorted(self._shape_deletes)
    group_child_shape_deletes = sorted(self._group_child_shape_deletes)
    table_cell_edits = list(self._table_cell_edits.items())
    table_row_column_edits = list(self._table_row_column_edits)
    table_row_height_edits = list(self._table_row_height_edits.items())
    table_column_width_edits = list(self._table_column_width_edits.items())
    table_cell_margin_edits = list(self._table_cell_margin_edits.items())
    table_cell_vertical_anchor_edits = list(
        self._table_cell_vertical_anchor_edits.items()
    )
    table_cell_text_frame_margin_edits = list(
        self._table_cell_text_frame_margin_edits.items()
    )
    table_cell_text_frame_vertical_anchor_edits = list(
        self._table_cell_text_frame_vertical_anchor_edits.items()
    )
    table_cell_text_frame_content_edits = list(
        self._table_cell_text_frame_content_edits.items()
    )
    table_cell_text_frame_word_wrap_edits = list(
        self._table_cell_text_frame_word_wrap_edits.items()
    )
    table_cell_text_frame_auto_size_edits = list(
        self._table_cell_text_frame_auto_size_edits.items()
    )
    table_cell_text_frame_fit_edits = list(
        self._table_cell_text_frame_fit_edits.items()
    )
    table_cell_text_frame_paragraph_alignment_edits = list(
        self._table_cell_text_frame_paragraph_alignment_edits.items()
    )
    table_cell_text_frame_paragraph_level_edits = list(
        self._table_cell_text_frame_paragraph_level_edits.items()
    )
    table_cell_text_frame_paragraph_spacing_edits = list(
        self._table_cell_text_frame_paragraph_spacing_edits.items()
    )
    table_cell_text_frame_paragraph_font_edits = list(
        self._table_cell_text_frame_paragraph_font_edits.items()
    )
    table_cell_text_frame_paragraph_run_edits = list(
        self._table_cell_text_frame_paragraph_run_edits.items()
    )
    table_cell_text_frame_paragraph_line_break_edits = list(
        self._table_cell_text_frame_paragraph_line_break_edits
    )
    table_cell_text_frame_paragraph_run_font_edits = list(
        self._table_cell_text_frame_paragraph_run_font_edits.items()
    )
    table_cell_text_frame_paragraph_run_hyperlink_edits = list(
        self._table_cell_text_frame_paragraph_run_hyperlink_edits.items()
    )
    table_cell_fill_solid_edits = list(self._table_cell_fill_solid_edits)
    table_cell_fill_background_edits = list(
        self._table_cell_fill_background_edits
    )
    table_cell_fill_pattern_edits = list(
        self._table_cell_fill_pattern_edits.items()
    )
    table_cell_fill_pattern_fore_color_edits = list(
        self._table_cell_fill_pattern_fore_color_edits.items()
    )
    table_cell_fill_pattern_back_color_edits = list(
        self._table_cell_fill_pattern_back_color_edits.items()
    )
    table_cell_fill_color_edits = list(self._table_cell_fill_color_edits.items())
    table_cell_fill_gradient_edits = list(
        self._table_cell_fill_gradient_edits.items()
    )
    background_fill_solid_edits = list(self._background_fill_solid_edits)
    background_fill_background_edits = list(self._background_fill_background_edits)
    background_fill_color_edits = list(self._background_fill_color_edits.items())
    table_cell_merge_edits = [dict(edit) for edit in self._table_cell_merge_edits]
    table_style_edits = list(self._table_style_edits.items())
    text_run_edits = list(self._text_run_edits.items())
    text_run_bold_edits = list(self._text_run_bold_edits.items())
    text_run_italic_edits = list(self._text_run_italic_edits.items())
    text_run_underline_edits = list(self._text_run_underline_edits.items())
    text_run_font_size_edits = list(self._text_run_font_size_edits.items())
    text_run_font_name_edits = list(self._text_run_font_name_edits.items())
    text_run_font_color_edits = list(self._text_run_font_color_edits.items())
    text_run_font_fill_type_edits = list(
        self._text_run_font_fill_type_edits.items()
    )
    text_run_font_language_edits = list(
        self._text_run_font_language_edits.items()
    )
    text_run_hyperlink_edits = list(self._text_run_hyperlink_edits.items())
    text_run_appends = list(self._text_run_appends.items())
    paragraph_text_edits = list(self._paragraph_text_edits.items())
    paragraph_clear_edits = list(self._paragraph_clear_edits)
    paragraph_line_break_edits = list(self._paragraph_line_break_edits)
    paragraph_appends = list(self._paragraph_appends.items())
    paragraph_alignment_edits = list(self._paragraph_alignment_edits.items())
    paragraph_level_edits = list(self._paragraph_level_edits.items())
    paragraph_spacing_edits = list(self._paragraph_spacing_edits.items())
    paragraph_font_edits = list(self._paragraph_font_edits.items())
    text_frame_margin_edits = list(self._text_frame_margin_edits.items())
    text_frame_word_wrap_edits = list(self._text_frame_word_wrap_edits.items())
    text_frame_vertical_anchor_edits = list(
        self._text_frame_vertical_anchor_edits.items()
    )
    text_frame_auto_size_edits = list(self._text_frame_auto_size_edits.items())
    text_frame_fit_edits = list(self._text_frame_fit_edits.items())
    group_child_text_frame_margin_edits = list(
        self._group_child_text_frame_margin_edits.items()
    )
    group_child_text_frame_word_wrap_edits = list(
        self._group_child_text_frame_word_wrap_edits.items()
    )
    group_child_text_frame_vertical_anchor_edits = list(
        self._group_child_text_frame_vertical_anchor_edits.items()
    )
    group_child_text_frame_auto_size_edits = list(
        self._group_child_text_frame_auto_size_edits.items()
    )
    group_child_text_frame_fit_edits = list(
        self._group_child_text_frame_fit_edits.items()
    )
    text_edits = list(self._shape_text_edits.items())
    group_child_text_edits = list(self._group_child_text_edits.items())
    nested_group_child_text_edits = list(
        self._nested_group_child_text_edits.items()
    )
    deeper_group_child_text_edits = list(
        self._deeper_group_child_text_edits.items()
    )
    group_child_paragraph_text_edits = list(
        self._group_child_paragraph_text_edits.items()
    )
    group_child_paragraph_clear_edits = list(self._group_child_paragraph_clear_edits)
    group_child_paragraph_line_break_edits = list(
        self._group_child_paragraph_line_break_edits
    )
    group_child_run_text_edits = list(self._group_child_run_text_edits.items())
    group_child_run_font_edits = list(self._group_child_run_font_edits.items())
    group_child_run_hyperlink_edits = list(
        self._group_child_run_hyperlink_edits.items()
    )
    group_child_paragraph_alignment_edits = list(
        self._group_child_paragraph_alignment_edits.items()
    )
    group_child_paragraph_font_edits = list(
        self._group_child_paragraph_font_edits.items()
    )
    group_child_paragraph_level_edits = list(
        self._group_child_paragraph_level_edits.items()
    )
    group_child_paragraph_spacing_edits = list(
        self._group_child_paragraph_spacing_edits.items()
    )
    part_shape_text_edits = list(self._part_shape_text_edits.items())
    part_paragraph_alignment_edits = list(
        self._part_paragraph_alignment_edits.items()
    )
    part_paragraph_level_edits = list(self._part_paragraph_level_edits.items())
    part_paragraph_spacing_edits = list(
        self._part_paragraph_spacing_edits.items()
    )
    part_paragraph_font_edits = list(self._part_paragraph_font_edits.items())
    part_run_font_edits = list(self._part_run_font_edits.items())
    part_run_hyperlink_edits = list(self._part_run_hyperlink_edits.items())
    part_shape_hyperlink_edits = list(self._part_shape_hyperlink_edits.items())
    part_text_frame_margin_edits = list(self._part_text_frame_margin_edits.items())
    part_text_frame_word_wrap_edits = list(
        self._part_text_frame_word_wrap_edits.items()
    )
    part_text_frame_vertical_anchor_edits = list(
        self._part_text_frame_vertical_anchor_edits.items()
    )
    part_text_frame_auto_size_edits = list(
        self._part_text_frame_auto_size_edits.items()
    )
    adjustment_edits = list(self._shape_adjustment_edits.items())
    shape_adds, text_edits = ops._coalesce_auto_shape_text(shape_adds, text_edits)
    shape_adds, adjustment_edits = ops._coalesce_auto_shape_adjustments(
        shape_adds,
        adjustment_edits,
    )
    shape_adds = ops._coalesce_connected_connector_auto_shapes(shape_adds)
    shape_adds, table_cell_edits = ops._coalesce_table_cell_text(
        shape_adds, table_cell_edits
    )
    geometry_edits = list(self._shape_geometry_edits.items())
    group_child_geometry_edits = list(self._group_child_geometry_edits.items())
    nested_group_child_geometry_edits = list(
        self._nested_group_child_geometry_edits.items()
    )
    deeper_group_child_geometry_edits = list(
        self._deeper_group_child_geometry_edits.items()
    )
    fill_solid_edits = list(self._shape_fill_solid_edits)
    fill_background_edits = list(self._shape_fill_background_edits)
    fill_pattern_edits = list(self._shape_fill_pattern_edits.items())
    fill_pattern_fore_color_edits = list(
        self._shape_fill_pattern_fore_color_edits.items()
    )
    fill_pattern_back_color_edits = list(
        self._shape_fill_pattern_back_color_edits.items()
    )
    fill_color_edits = list(self._shape_fill_color_edits.items())
    fill_gradient_edits = list(self._shape_fill_gradient_edits.items())
    line_solid_edits = list(self._shape_line_solid_edits)
    line_background_edits = list(self._shape_line_background_edits)
    line_pattern_edits = list(self._shape_line_pattern_edits.items())
    line_pattern_fore_color_edits = list(
        self._shape_line_pattern_fore_color_edits.items()
    )
    line_pattern_back_color_edits = list(
        self._shape_line_pattern_back_color_edits.items()
    )
    line_color_edits = list(self._shape_line_color_edits.items())
    line_width_edits = list(self._shape_line_width_edits.items())
    line_dash_edits = list(self._shape_line_dash_edits.items())
    connector_connection_edits = list(self._connector_connection_edits.items())
    shadow_inherit_edits = list(self._shape_shadow_inherit_edits.items())
    hyperlink_edits = list(self._shape_hyperlink_edits.items())
    target_slide_edits = list(self._shape_target_slide_edits.items())
    rotation_edits = list(self._shape_rotation_edits.items())
    name_edits = list(self._shape_name_edits.items())
    line_element_edits = list(self._shape_line_element_edits)
    picture_crop_edits = list(self._picture_crop_edits.items())
    picture_replace_edits = list(self._picture_replace_edits.items())
    chart_data_edits = list(self._chart_data_edits.items())
    chart_title_edits = list(self._chart_title_edits.items())
    chart_legend_edits = list(self._chart_legend_edits.items())
    chart_font_edits = list(self._chart_font_edits.items())
    chart_data_label_edits = list(self._chart_data_label_edits.items())
    chart_plot_property_edits = list(self._chart_plot_property_edits.items())
    chart_axis_title_edits = list(self._chart_axis_title_edits.items())
    chart_axis_property_edits = list(self._chart_axis_property_edits.items())
    chart_style_edits = list(self._chart_style_edits.items())
    presentation_size_edits = dict(self._presentation_size_edits)
    slide_name_edits = list(self._slide_name_edits.items())
    core_properties_edits = (
        None
        if self._core_properties_edits is None
        else dict(self._core_properties_edits)
    )
    return SimpleNamespace(
        **{
            name: value
            for name, value in locals().items()
            if name not in {"self", "ops"}
        }
    )
