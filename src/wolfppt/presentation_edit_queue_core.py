"""Core queued presentation operations and queue cleanup."""

from __future__ import annotations

from typing import Any

from .background_facade import (
    normalize_background_target as _normalize_background_target,
)
from .image_inputs import (
    InMemoryImage as _InMemoryImage,
)
from .image_inputs import (
    image_source_for_queue as _image_source_for_queue,
)
from .presentation_size import (
    coerce_slide_size_emu as _coerce_slide_size_emu,
)
from .presentation_size import (
    presentation_slide_size as _presentation_slide_size,
)


class PresentationCoreQueueMixin:
    def _queue_slide_reorder(self, slide_order: list[int]) -> None:
        self._slide_order = list(slide_order)

    def _queue_slide_delete(self, slide_part: str) -> None:
        self._slide_deletions.append(str(slide_part))

    def _queue_slide_layout_change(self, slide_partname: str, layout_partname: str) -> None:
        changes = getattr(self, "_slide_layout_changes", None)
        if changes is None:
            changes = {}
            self._slide_layout_changes = changes
        changes[slide_partname] = layout_partname

    def _set_slide_size(self, attr: str, value: Any, name: str) -> None:
        size = _presentation_slide_size(self)
        coerced = _coerce_slide_size_emu(value, name)
        if size.get(attr) == coerced:
            return
        size[attr] = coerced
        self._slide_size = size
        self._presentation_size_edits[attr] = size[attr]

    def _queue_slide_name(self, slide: Any, name: str) -> None:
        target = (
            slide._payload["_creation_token"]
            if slide._payload.get("_pending_creation")
            else slide.partname.lstrip("/")
        )
        self._slide_name_edits[target] = name

    def _queue_slide_hidden(self, slide_identifier: Any, hidden: bool) -> None:
        if type(hidden) is not bool:
            raise TypeError(f"hidden must be a bool, got {type(hidden).__name__}")
        if hasattr(slide_identifier, "_payload") and slide_identifier._payload.get(
            "_pending_creation"
        ):
            target: Any = slide_identifier._payload["_creation_token"]
        elif hasattr(slide_identifier, "partname") and slide_identifier.partname:
            target = slide_identifier.partname.lstrip("/")
        elif isinstance(slide_identifier, int):
            slides = getattr(self, "_slides", None)
            if slides is not None and 0 <= slide_identifier < len(slides):
                s = slides[slide_identifier]
                if s._payload.get("_pending_creation"):
                    target = s._payload["_creation_token"]
                elif s.partname:
                    target = s.partname.lstrip("/")
                else:
                    target = slide_identifier
            else:
                target = slide_identifier
        elif isinstance(slide_identifier, str):
            target = slide_identifier.strip().lstrip("/")
        else:
            target = slide_identifier
        self._slide_hidden_edits[target] = hidden

    def _queue_slide_transition(self, slide_identifier: int | str, spec: Any) -> None:
        self._slide_transition_edits[slide_identifier] = spec

    def _queue_slide_animation(self, slide_identifier: int | str, spec: Any) -> None:
        self._slide_animation_edits[slide_identifier] = spec

    def _queue_core_properties(self, values: dict[str, Any]) -> None:
        self._core_properties_edits = dict(values)

    def _queue_custom_properties(self, edits: Any) -> None:
        self._custom_properties_edits = edits

    def _queue_extended_properties(self, edits: Any) -> None:
        self._extended_properties_edits = edits

    def _queue_section_edits(self, edits: Any) -> None:
        self._section_edits = edits

    def _queue_custom_show_edits(self, edits: Any) -> None:
        self._custom_show_edits = list(edits)

    def _queue_background_fill_solid(self, target: Any) -> None:
        normalized = _normalize_background_target(target)
        self._background_fill_background_edits.discard(normalized)
        self._background_fill_color_edits.pop(normalized, None)
        self._background_fill_solid_edits.add(normalized)

    def _queue_background_fill_background(self, target: Any) -> None:
        normalized = _normalize_background_target(target)
        self._background_fill_solid_edits.discard(normalized)
        self._background_fill_color_edits.pop(normalized, None)
        self._background_fill_background_edits.add(normalized)

    def _queue_background_fill_color(
        self,
        target: Any,
        color: str | dict[str, Any],
    ) -> None:
        normalized = _normalize_background_target(target)
        self._background_fill_background_edits.discard(normalized)
        self._background_fill_solid_edits.discard(normalized)
        self._background_fill_color_edits[normalized] = color

    def _queue_background_fill_picture(
        self,
        target: Any,
        image_source: Any,
        crop: tuple[float, float, float, float] | dict[str, float] | None = None,
    ) -> None:
        normalized = _normalize_background_target(target)
        self._background_fill_background_edits.discard(normalized)
        self._background_fill_solid_edits.discard(normalized)
        if isinstance(image_source, (bytes, bytearray)):
            queued_source = _InMemoryImage(bytes(image_source))
        elif isinstance(image_source, _InMemoryImage):
            queued_source = image_source
        else:
            queued_source = _image_source_for_queue(image_source)
        self._background_fill_color_edits[normalized] = {
            "type": "picture",
            "image_source": queued_source,
            "crop": crop or (0.0, 0.0, 0.0, 0.0),
        }

    def _queue_zoom_edit(self, shape: Any, state: dict[str, Any]) -> None:
        edits = getattr(self, "_zoom_edits", None)
        if edits is None:
            edits = self._zoom_edits = {}
        edits[shape] = state

    def _clear_pending_edits(self) -> None:
        self._slide_creations.clear()
        self._slide_deletions.clear()
        self._slide_order = None
        self._slide_layout_removals.clear()
        if hasattr(self, "_slide_layout_changes") and self._slide_layout_changes is not None:
            self._slide_layout_changes.clear()
        self._notes_slide_adds.clear()
        self._pending_notes_slide_payloads.clear()
        self._pending_handout_master_partname = None
        self._part_placeholder_adds.clear()
        self._slide_master_authoring_requests.clear()
        self._shape_adds.clear()
        getattr(self, "_zoom_edits", {}).clear()
        self._shape_deletes.clear()
        self._group_child_shape_deletes.clear()
        self._table_cell_edits.clear()
        self._table_row_column_edits.clear()
        self._table_row_height_edits.clear()
        self._table_column_width_edits.clear()
        self._table_cell_margin_edits.clear()
        self._table_cell_vertical_anchor_edits.clear()
        self._table_cell_border_edits.clear()
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
        self._text_run_strike_edits.clear()
        self._text_run_font_size_edits.clear()
        self._text_run_font_name_edits.clear()
        self._text_run_font_color_edits.clear()
        self._text_run_font_fill_type_edits.clear()
        self._text_run_font_language_edits.clear()
        self._text_run_hyperlink_edits.clear()
        self._text_run_advanced_edits.clear()
        self._text_run_appends.clear()
        self._paragraph_text_edits.clear()
        self._paragraph_clear_edits.clear()
        self._paragraph_line_break_edits.clear()
        self._paragraph_appends.clear()
        self._paragraph_alignment_edits.clear()
        self._paragraph_level_edits.clear()
        self._paragraph_spacing_edits.clear()
        self._paragraph_font_edits.clear()
        self._paragraph_bullet_edits.clear()
        self._paragraph_tab_stop_edits.clear()
        self._group_child_paragraph_tab_stop_edits.clear()
        self._part_paragraph_tab_stop_edits.clear()
        self._text_frame_margin_edits.clear()
        self._text_frame_word_wrap_edits.clear()
        self._text_frame_vertical_anchor_edits.clear()
        self._text_frame_auto_size_edits.clear()
        self._text_frame_fit_edits.clear()
        self._text_frame_advanced_edits.clear()
        self._group_child_text_frame_advanced_edits.clear()
        self._part_text_frame_advanced_edits.clear()
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
        self._group_child_paragraph_bullet_edits.clear()
        self._part_shape_text_edits.clear()
        self._part_paragraph_text_edits.clear()
        self._part_paragraph_clear_edits.clear()
        self._part_paragraph_line_break_edits.clear()
        self._part_run_text_edits.clear()
        self._part_paragraph_alignment_edits.clear()
        self._part_paragraph_level_edits.clear()
        self._part_paragraph_spacing_edits.clear()
        self._part_paragraph_font_edits.clear()
        self._part_paragraph_bullet_edits.clear()
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
        self._shape_line_end_edits.clear()
        self._connector_connection_edits.clear()
        self._shape_shadow_inherit_edits.clear()
        self._shape_effect_edits.clear()
        self._shape_glow_edits.clear()
        self._shape_hyperlink_edits.clear()
        self._shape_target_slide_edits.clear()
        self._shape_rotation_edits.clear()
        self._shape_flip_edits.clear()
        self._shape_lock_edits.clear()
        self._shape_name_edits.clear()
        self._shape_adjustment_edits.clear()
        self._shape_preset_edits.clear()
        self._shape_z_order_edits.clear()
        self._shape_line_element_edits.clear()
        self._picture_crop_edits.clear()
        self._picture_transparency_edits.clear()
        self._picture_correction_edits.clear()
        self._picture_recolor_edits.clear()
        self._picture_replace_edits.clear()
        self._media_playback_edits.clear()
        self._chart_data_edits.clear()
        self._chart_title_edits.clear()
        self._chart_legend_edits.clear()
        self._chart_font_edits.clear()
        self._chart_data_label_edits.clear()
        self._chart_plot_property_edits.clear()
        self._chart_axis_title_edits.clear()
        self._chart_axis_property_edits.clear()
        self._chart_style_edits.clear()
        self._chart_trendline_edits.clear()
        self._chart_error_bar_edits.clear()
        self._presentation_size_edits.clear()
        self._slide_name_edits.clear()
        self._slide_hidden_edits.clear()
        self._slide_transition_edits.clear()
        self._slide_animation_edits.clear()
        self._core_properties_edits = None
        self._custom_properties_edits = None
        self._extended_properties_edits = None
        self._section_edits = None
        self._custom_show_edits = None
        if hasattr(self, "_table_style_id_edits") and isinstance(self._table_style_id_edits, dict):
            self._table_style_id_edits.clear()
        self._facade_xml_root_cache.clear()
