"""Core queued presentation operations and queue cleanup."""

from __future__ import annotations

from typing import Any

from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .presentation_size import (
    coerce_slide_size_emu as _coerce_slide_size_emu,
    presentation_slide_size as _presentation_slide_size,
)

class PresentationCoreQueueMixin:
    def _queue_slide_reorder(self, slide_order: list[int]) -> None:
        self._slide_order = list(slide_order)

    def _queue_slide_delete(self, slide_part: str) -> None:
        self._slide_deletions.append(str(slide_part))

    def _set_slide_size(self, attr: str, value: Any, name: str) -> None:
        size = _presentation_slide_size(self)
        coerced = _coerce_slide_size_emu(value, name)
        if size.get(attr) == coerced:
            return
        size[attr] = coerced
        self._slide_size = size
        self._presentation_size_edits[attr] = size[attr]

    def _queue_slide_name(self, slide_index: int, name: str) -> None:
        self._slide_name_edits[slide_index] = name

    def _queue_core_properties(self, values: dict[str, Any]) -> None:
        self._core_properties_edits = dict(values)

    def _queue_background_fill_solid(self, partname: str) -> None:
        normalized = _normalize_package_partname(partname)
        self._background_fill_background_edits.discard(normalized)
        self._background_fill_color_edits.pop(normalized, None)
        self._background_fill_solid_edits.add(normalized)

    def _queue_background_fill_background(self, partname: str) -> None:
        normalized = _normalize_package_partname(partname)
        self._background_fill_solid_edits.discard(normalized)
        self._background_fill_color_edits.pop(normalized, None)
        self._background_fill_background_edits.add(normalized)

    def _queue_background_fill_color(
        self,
        partname: str,
        color: str | dict[str, Any],
    ) -> None:
        normalized = _normalize_package_partname(partname)
        self._background_fill_background_edits.discard(normalized)
        self._background_fill_solid_edits.discard(normalized)
        self._background_fill_color_edits[normalized] = color

    def _clear_pending_edits(self) -> None:
        self._slide_creations.clear()
        self._slide_deletions.clear()
        self._slide_order = None
        self._slide_layout_removals.clear()
        self._notes_slide_adds.clear()
        self._pending_notes_slide_payloads.clear()
        self._part_placeholder_adds.clear()
        self._shape_adds.clear()
        self._shape_deletes.clear()
        self._group_child_shape_deletes.clear()
        self._table_cell_edits.clear()
        self._table_row_column_edits.clear()
        self._table_row_height_edits.clear()
        self._table_column_width_edits.clear()
        self._table_cell_margin_edits.clear()
        self._table_cell_vertical_anchor_edits.clear()
        self._table_cell_text_frame_margin_edits.clear()
        self._table_cell_text_frame_vertical_anchor_edits.clear()
        self._table_cell_text_frame_content_edits.clear()
        self._table_cell_text_frame_word_wrap_edits.clear()
        self._table_cell_text_frame_auto_size_edits.clear()
        self._table_cell_text_frame_fit_edits.clear()
        self._table_cell_text_frame_paragraph_alignment_edits.clear()
        self._table_cell_text_frame_paragraph_level_edits.clear()
        self._table_cell_text_frame_paragraph_spacing_edits.clear()
        self._table_cell_text_frame_paragraph_font_edits.clear()
        self._table_cell_text_frame_paragraph_run_edits.clear()
        self._table_cell_text_frame_paragraph_line_break_edits.clear()
        self._table_cell_text_frame_paragraph_run_font_edits.clear()
        self._table_cell_text_frame_paragraph_run_hyperlink_edits.clear()
        self._table_cell_fill_solid_edits.clear()
        self._table_cell_fill_background_edits.clear()
        self._table_cell_fill_pattern_edits.clear()
        self._table_cell_fill_pattern_fore_color_edits.clear()
        self._table_cell_fill_pattern_back_color_edits.clear()
        self._table_cell_fill_color_edits.clear()
        self._table_cell_fill_gradient_edits.clear()
        self._background_fill_solid_edits.clear()
        self._background_fill_background_edits.clear()
        self._background_fill_color_edits.clear()
        self._table_cell_merge_edits.clear()
        self._table_style_edits.clear()
        self._text_run_edits.clear()
        self._text_run_bold_edits.clear()
        self._text_run_italic_edits.clear()
        self._text_run_underline_edits.clear()
        self._text_run_font_size_edits.clear()
        self._text_run_font_name_edits.clear()
        self._text_run_font_color_edits.clear()
        self._text_run_font_fill_type_edits.clear()
        self._text_run_font_language_edits.clear()
        self._text_run_hyperlink_edits.clear()
        self._text_run_appends.clear()
        self._paragraph_text_edits.clear()
        self._paragraph_clear_edits.clear()
        self._paragraph_line_break_edits.clear()
        self._paragraph_appends.clear()
        self._paragraph_alignment_edits.clear()
        self._paragraph_level_edits.clear()
        self._paragraph_spacing_edits.clear()
        self._paragraph_font_edits.clear()
        self._text_frame_margin_edits.clear()
        self._text_frame_word_wrap_edits.clear()
        self._text_frame_vertical_anchor_edits.clear()
        self._text_frame_auto_size_edits.clear()
        self._text_frame_fit_edits.clear()
        self._group_child_text_frame_margin_edits.clear()
        self._group_child_text_frame_word_wrap_edits.clear()
        self._group_child_text_frame_vertical_anchor_edits.clear()
        self._group_child_text_frame_auto_size_edits.clear()
        self._group_child_text_frame_fit_edits.clear()
        self._shape_text_edits.clear()
        self._group_child_text_edits.clear()
        self._nested_group_child_text_edits.clear()
        self._deeper_group_child_text_edits.clear()
        self._group_child_paragraph_text_edits.clear()
        self._group_child_paragraph_clear_edits.clear()
        self._group_child_paragraph_line_break_edits.clear()
        self._group_child_run_text_edits.clear()
        self._group_child_run_font_edits.clear()
        self._group_child_run_hyperlink_edits.clear()
        self._group_child_paragraph_alignment_edits.clear()
        self._group_child_paragraph_font_edits.clear()
        self._group_child_paragraph_level_edits.clear()
        self._group_child_paragraph_spacing_edits.clear()
        self._part_shape_text_edits.clear()
        self._part_paragraph_alignment_edits.clear()
        self._part_paragraph_level_edits.clear()
        self._part_paragraph_spacing_edits.clear()
        self._part_paragraph_font_edits.clear()
        self._part_run_font_edits.clear()
        self._part_run_hyperlink_edits.clear()
        self._part_shape_hyperlink_edits.clear()
        self._part_text_frame_margin_edits.clear()
        self._part_text_frame_word_wrap_edits.clear()
        self._part_text_frame_vertical_anchor_edits.clear()
        self._part_text_frame_auto_size_edits.clear()
        self._shape_geometry_edits.clear()
        self._group_child_geometry_edits.clear()
        self._nested_group_child_geometry_edits.clear()
        self._deeper_group_child_geometry_edits.clear()
        self._shape_fill_solid_edits.clear()
        self._shape_fill_background_edits.clear()
        self._shape_fill_pattern_edits.clear()
        self._shape_fill_pattern_fore_color_edits.clear()
        self._shape_fill_pattern_back_color_edits.clear()
        self._shape_fill_color_edits.clear()
        self._shape_fill_gradient_edits.clear()
        self._shape_line_solid_edits.clear()
        self._shape_line_background_edits.clear()
        self._shape_line_pattern_edits.clear()
        self._shape_line_pattern_fore_color_edits.clear()
        self._shape_line_pattern_back_color_edits.clear()
        self._shape_line_color_edits.clear()
        self._shape_line_width_edits.clear()
        self._shape_line_dash_edits.clear()
        self._connector_connection_edits.clear()
        self._shape_shadow_inherit_edits.clear()
        self._shape_hyperlink_edits.clear()
        self._shape_target_slide_edits.clear()
        self._shape_rotation_edits.clear()
        self._shape_name_edits.clear()
        self._shape_adjustment_edits.clear()
        self._shape_line_element_edits.clear()
        self._picture_crop_edits.clear()
        self._picture_replace_edits.clear()
        self._chart_data_edits.clear()
        self._chart_title_edits.clear()
        self._chart_legend_edits.clear()
        self._chart_font_edits.clear()
        self._chart_data_label_edits.clear()
        self._chart_plot_property_edits.clear()
        self._chart_axis_title_edits.clear()
        self._chart_axis_property_edits.clear()
        self._chart_style_edits.clear()
        self._presentation_size_edits.clear()
        self._slide_name_edits.clear()
        self._core_properties_edits = None
        self._facade_xml_root_cache.clear()
