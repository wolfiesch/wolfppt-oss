"""Rebase helper for presentation pending edits following a slide deletion."""

from __future__ import annotations

from typing import Any

# Partname-keyed, layout-keyed, or presentation-global queues that MUST NOT
# have slide-index remapping applied:
PRESERVED_GLOBAL_OR_PARTNAME_FIELDS: tuple[str, ...] = (
    "_slide_creations",
    "_slide_deletions",
    "_slide_layout_removals",
    "_part_placeholder_adds",
    "_presentation_size_edits",
    "_background_fill_solid_edits",
    "_background_fill_background_edits",
    "_background_fill_color_edits",
    "_part_shape_text_edits",
    "_part_paragraph_alignment_edits",
    "_part_paragraph_level_edits",
    "_part_paragraph_spacing_edits",
    "_part_paragraph_font_edits",
    "_part_run_font_edits",
    "_part_run_hyperlink_edits",
    "_part_shape_hyperlink_edits",
    "_part_text_frame_margin_edits",
    "_part_text_frame_word_wrap_edits",
    "_part_text_frame_vertical_anchor_edits",
    "_part_text_frame_auto_size_edits",
)

# Queues handled by named special-case logic in rebase_presentation_edits_after_slide_delete:
SPECIAL_REBASE_HANDLED_FIELDS: tuple[str, ...] = (
    "_slide_order",
    "_notes_slide_adds",
    "_shape_adds",
    "_table_row_column_edits",
    "_table_cell_merge_edits",
    "_shape_target_slide_edits",
)

# Queues whose items are dictionaries keyed by slide index (int) or tuple with slide index as first element:
SLIDE_INDEX_DICT_FIELDS: tuple[str, ...] = (
    "_slide_name_edits",
    "_table_cell_edits",
    "_table_row_height_edits",
    "_table_column_width_edits",
    "_table_cell_margin_edits",
    "_table_cell_vertical_anchor_edits",
    "_table_cell_text_frame_margin_edits",
    "_table_cell_text_frame_vertical_anchor_edits",
    "_table_cell_text_frame_content_edits",
    "_table_cell_text_frame_word_wrap_edits",
    "_table_cell_text_frame_auto_size_edits",
    "_table_cell_text_frame_fit_edits",
    "_table_cell_text_frame_paragraph_alignment_edits",
    "_table_cell_text_frame_paragraph_level_edits",
    "_table_cell_text_frame_paragraph_spacing_edits",
    "_table_cell_text_frame_paragraph_font_edits",
    "_table_cell_text_frame_paragraph_run_edits",
    "_table_cell_text_frame_paragraph_run_font_edits",
    "_table_cell_text_frame_paragraph_run_hyperlink_edits",
    "_table_cell_fill_pattern_edits",
    "_table_cell_fill_pattern_fore_color_edits",
    "_table_cell_fill_pattern_back_color_edits",
    "_table_cell_fill_color_edits",
    "_table_cell_fill_gradient_edits",
    "_table_style_edits",
    "_text_run_edits",
    "_text_run_bold_edits",
    "_text_run_italic_edits",
    "_text_run_underline_edits",
    "_text_run_font_size_edits",
    "_text_run_font_name_edits",
    "_text_run_font_color_edits",
    "_text_run_font_fill_type_edits",
    "_text_run_font_language_edits",
    "_text_run_hyperlink_edits",
    "_text_run_appends",
    "_paragraph_text_edits",
    "_paragraph_appends",
    "_paragraph_alignment_edits",
    "_paragraph_level_edits",
    "_paragraph_spacing_edits",
    "_paragraph_font_edits",
    "_text_frame_margin_edits",
    "_text_frame_word_wrap_edits",
    "_text_frame_vertical_anchor_edits",
    "_text_frame_auto_size_edits",
    "_text_frame_fit_edits",
    "_group_child_text_frame_margin_edits",
    "_group_child_text_frame_word_wrap_edits",
    "_group_child_text_frame_vertical_anchor_edits",
    "_group_child_text_frame_auto_size_edits",
    "_group_child_text_frame_fit_edits",
    "_shape_text_edits",
    "_group_child_text_edits",
    "_nested_group_child_text_edits",
    "_deeper_group_child_text_edits",
    "_group_child_paragraph_text_edits",
    "_group_child_run_text_edits",
    "_group_child_run_font_edits",
    "_group_child_run_hyperlink_edits",
    "_group_child_paragraph_alignment_edits",
    "_group_child_paragraph_font_edits",
    "_group_child_paragraph_level_edits",
    "_group_child_paragraph_spacing_edits",
    "_shape_geometry_edits",
    "_group_child_geometry_edits",
    "_nested_group_child_geometry_edits",
    "_deeper_group_child_geometry_edits",
    "_shape_fill_pattern_edits",
    "_shape_fill_pattern_fore_color_edits",
    "_shape_fill_pattern_back_color_edits",
    "_shape_fill_color_edits",
    "_shape_fill_gradient_edits",
    "_shape_line_pattern_edits",
    "_shape_line_pattern_fore_color_edits",
    "_shape_line_pattern_back_color_edits",
    "_shape_line_color_edits",
    "_shape_line_width_edits",
    "_shape_line_dash_edits",
    "_connector_connection_edits",
    "_shape_shadow_inherit_edits",
    "_shape_hyperlink_edits",
    "_shape_rotation_edits",
    "_shape_name_edits",
    "_shape_adjustment_edits",
    "_picture_crop_edits",
    "_picture_replace_edits",
    "_chart_data_edits",
    "_chart_title_edits",
    "_chart_legend_edits",
    "_chart_font_edits",
    "_chart_data_label_edits",
    "_chart_plot_property_edits",
    "_chart_axis_title_edits",
    "_chart_axis_property_edits",
    "_chart_style_edits",
)

# Queues whose items are sets of tuples with slide index as first element:
SLIDE_INDEX_SET_FIELDS: tuple[str, ...] = (
    "_shape_deletes",
    "_group_child_shape_deletes",
    "_table_cell_fill_solid_edits",
    "_table_cell_fill_background_edits",
    "_paragraph_clear_edits",
    "_group_child_paragraph_clear_edits",
    "_group_child_paragraph_line_break_edits",
    "_shape_fill_solid_edits",
    "_shape_fill_background_edits",
    "_shape_line_solid_edits",
    "_shape_line_background_edits",
    "_shape_line_element_edits",
)

# Queues whose items are lists of tuples with slide index as first element:
SLIDE_INDEX_TUPLE_LIST_FIELDS: tuple[str, ...] = (
    "_paragraph_line_break_edits",
    "_table_cell_text_frame_paragraph_line_break_edits",
)


def rebase_presentation_edits_after_slide_delete(
    presentation: Any,
    deleted_index: int | None = None,
    *,
    index_remap: dict[int, int] | None = None,
    deleted_slide_index: int | None = None,
) -> None:
    """Rebase all slide-index-keyed pending edits in-place when a slide is removed.

    When index_remap is provided, it maps each surviving slide's pre-deletion
    _index to its new live collection index in 0..len(survivors)-1.
    Any queued edit whose slide index is not in index_remap belonged to a deleted
    slide and is discarded.
    """
    if index_remap is None:
        if deleted_index is not None:
            # Fallback if index_remap was not directly computed by caller
            slides_col = getattr(presentation, "_slides", None)
            raw_slides = getattr(slides_col, "_slides", None) if slides_col else None
            if isinstance(raw_slides, list) and raw_slides:
                index_remap = {
                    survivor._index: idx for idx, survivor in enumerate(raw_slides)
                }
            else:
                # Contiguous slide shift heuristic
                index_remap = {}
        else:
            return

    # 1. Slide order: if deleting a persisted slide, survivor order is handled
    # directly by delete_slides, so _slide_order is cleared.
    # If is_pending is True, _slide_order was already updated/unwound by caller.
    if not getattr(presentation, "_pending_slide_delete_in_progress", False):
        presentation._slide_order = None

    # 2. _notes_slide_adds: dict[int, tuple[str, str]]
    notes_adds = getattr(presentation, "_notes_slide_adds", None)
    if isinstance(notes_adds, dict) and notes_adds:
        new_notes_adds: dict[int, tuple[str, str]] = {}
        deleted_notes_parts: list[str] = []
        for s_idx, val in notes_adds.items():
            if s_idx in index_remap:
                new_notes_adds[index_remap[s_idx]] = val
            else:
                if isinstance(val, tuple) and len(val) >= 2:
                    deleted_notes_parts.append(val[1])
        presentation._notes_slide_adds = new_notes_adds
        pending_notes = getattr(presentation, "_pending_notes_slide_payloads", None)
        if isinstance(pending_notes, dict):
            for part in deleted_notes_parts:
                pending_notes.pop(part, None)
        part_cache = getattr(presentation, "_part_shape_payload_cache", None)
        if isinstance(part_cache, dict):
            for part in deleted_notes_parts:
                part_cache.pop(part, None)

    # 3. _shape_adds: list[tuple[str, tuple[Any, ...]]]
    shape_adds = getattr(presentation, "_shape_adds", None)
    if isinstance(shape_adds, list) and shape_adds:
        new_shape_adds: list[tuple[str, tuple[Any, ...]]] = []
        for kind, args in shape_adds:
            if isinstance(args, tuple) and args and isinstance(args[0], int):
                s_idx = args[0]
                if s_idx in index_remap:
                    new_shape_adds.append((kind, (index_remap[s_idx],) + args[1:]))
            else:
                new_shape_adds.append((kind, args))
        presentation._shape_adds = new_shape_adds

    # 4. _table_row_column_edits: list[dict[str, Any]]
    row_col_edits = getattr(presentation, "_table_row_column_edits", None)
    if isinstance(row_col_edits, list) and row_col_edits:
        new_rc: list[dict[str, Any]] = []
        for edit in row_col_edits:
            if isinstance(edit, dict) and "slide_index" in edit:
                s_idx = edit["slide_index"]
                if s_idx in index_remap:
                    new_edit = dict(edit)
                    new_edit["slide_index"] = index_remap[s_idx]
                    new_rc.append(new_edit)
            else:
                new_rc.append(edit)
        presentation._table_row_column_edits = new_rc

    # 5. _table_cell_merge_edits: list[dict[str, Any]]
    merge_edits = getattr(presentation, "_table_cell_merge_edits", None)
    if isinstance(merge_edits, list) and merge_edits:
        new_merges: list[dict[str, Any]] = []
        for edit in merge_edits:
            if isinstance(edit, dict) and "slide_index" in edit:
                s_idx = edit["slide_index"]
                if s_idx in index_remap:
                    new_edit = dict(edit)
                    new_edit["slide_index"] = index_remap[s_idx]
                    new_merges.append(new_edit)
            else:
                new_merges.append(edit)
        presentation._table_cell_merge_edits = new_merges

    # 6. _shape_target_slide_edits: dict[tuple[int, int], int | None]
    target_edits = getattr(presentation, "_shape_target_slide_edits", None)
    if isinstance(target_edits, dict) and target_edits:
        new_targets: dict[tuple[int, int], int | None] = {}
        for (s_idx, shape_idx), target_slide_idx in target_edits.items():
            if s_idx in index_remap:
                remapped_target = (
                    index_remap.get(target_slide_idx)
                    if target_slide_idx is not None
                    else None
                )
                new_targets[(index_remap[s_idx], shape_idx)] = remapped_target
        presentation._shape_target_slide_edits = new_targets

    # 7. SLIDE_INDEX_TUPLE_LIST_FIELDS: list of tuples starting with slide_index
    for attr in SLIDE_INDEX_TUPLE_LIST_FIELDS:
        val = getattr(presentation, attr, None)
        if isinstance(val, list) and val:
            new_list: list[tuple[Any, ...]] = []
            for item in val:
                if isinstance(item, tuple) and item and isinstance(item[0], int):
                    s_idx = item[0]
                    if s_idx in index_remap:
                        new_list.append((index_remap[s_idx],) + item[1:])
                else:
                    new_list.append(item)
            setattr(presentation, attr, new_list)

    # 8. SLIDE_INDEX_SET_FIELDS: set of tuples starting with slide_index
    for attr in SLIDE_INDEX_SET_FIELDS:
        val = getattr(presentation, attr, None)
        if isinstance(val, set) and val:
            new_set: set[tuple[Any, ...]] = set()
            for item in val:
                if isinstance(item, tuple) and item and isinstance(item[0], int):
                    s_idx = item[0]
                    if s_idx in index_remap:
                        new_set.add((index_remap[s_idx],) + item[1:])
                else:
                    new_set.add(item)
            setattr(presentation, attr, new_set)

    # 9. SLIDE_INDEX_DICT_FIELDS: dict keyed by int or tuple starting with slide_index
    for attr in SLIDE_INDEX_DICT_FIELDS:
        val = getattr(presentation, attr, None)
        if isinstance(val, dict) and val:
            new_dict: dict[Any, Any] = {}
            for k, v in val.items():
                if isinstance(k, int):
                    if k in index_remap:
                        new_dict[index_remap[k]] = v
                elif isinstance(k, tuple) and k and isinstance(k[0], int):
                    s_idx = k[0]
                    if s_idx in index_remap:
                        new_dict[(index_remap[s_idx],) + k[1:]] = v
                else:
                    new_dict[k] = v
            setattr(presentation, attr, new_dict)


__all__ = [
    "PRESERVED_GLOBAL_OR_PARTNAME_FIELDS",
    "SLIDE_INDEX_DICT_FIELDS",
    "SLIDE_INDEX_SET_FIELDS",
    "SLIDE_INDEX_TUPLE_LIST_FIELDS",
    "SPECIAL_REBASE_HANDLED_FIELDS",
    "rebase_presentation_edits_after_slide_delete",
]
