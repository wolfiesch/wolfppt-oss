"""Snapshot pending facade edits before save orchestration mutates them."""

from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from xml.etree import ElementTree as ET

from .extractor import _shape_child_elements
from .presentation_save_ops import PresentationSaveOps
from .presentation_text_queue import GROUP_TEXT_XML_FIELDS
from .shape_payloads import _invalidate_shape_text_cache
from .slide_payloads import load_slide_payloads, load_slide_shell_payloads


def _resolve_native_group_text_references(edits: Any, current: Path) -> None:
    """Lower whole-shape group text to native group/direct-sp ordinals.

    Paragraph/run mutations use the shared ShapeEditRef XML path, including
    empty paragraphs and runs that native ordinal rewriting cannot address.
    Geometry and insertion queues retain their existing contracts.
    """
    fields = ("group_child_text_edits",)
    if not any(getattr(edits, field) for field in fields):
        return
    slides = load_slide_shell_payloads(current)
    p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    groups_by_slide: dict[int, tuple[list[ET.Element], dict[ET.Element, int]]] = {}
    targets: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    with zipfile.ZipFile(current) as package:
        for field in fields:
            records = getattr(edits, field)
            for index, (key, text) in enumerate(records):
                target = key[:3]
                if target not in targets:
                    slide_index, group_index, child_index = target
                    if slide_index not in groups_by_slide:
                        root = ET.fromstring(package.read(slides[slide_index]["part"]))
                        tree = root.find(f"{{{p_ns}}}cSld/{{{p_ns}}}spTree")
                        if tree is None:
                            raise ValueError("group text slide has no shape tree")
                        groups_by_slide[slide_index] = (
                            tree.findall(f"{{{p_ns}}}grpSp"),
                            {
                                group: ordinal
                                for ordinal, group in enumerate(root.iter(f"{{{p_ns}}}grpSp"))
                            },
                        )
                    groups, native_ordinals = groups_by_slide[slide_index]
                    group = groups[group_index]
                    child = _shape_child_elements(group)[child_index]
                    if child.tag != f"{{{p_ns}}}sp":
                        raise ValueError("group text target is not a shape text body")
                    targets[target] = (
                        slide_index,
                        native_ordinals[group],
                        group.findall(f"{{{p_ns}}}sp").index(child),
                    )
                records[index] = ((*targets[target], *key[3:]), text)


def resolve_shape_edit_references(edits: Any, current: Path) -> None:
    """Lower shared facade refs to the all-shape paths used by XML applicators.

    Direct-child refs already start with an all-shape index. Nested/deeper refs
    start with a top-level group ordinal, followed by all-child indices. Native
    insertion and group geometry queues retain their group-ordinal contracts.
    The nested text XML consumer, like shared XML refs, takes all-shape paths.
    Only this save snapshot is changed, never the live queues, so a failed
    publication can retry the same transaction.
    """
    _resolve_native_group_text_references(edits, current)
    group_indices: dict[int, list[int]] = {}
    group_text_fields = (
        *GROUP_TEXT_XML_FIELDS,
        "group_child_paragraph_clear_edits",
        "group_child_paragraph_line_break_edits",
    )
    slides = (
        load_slide_payloads(current)
        if any(getattr(edits, field) for field in group_text_fields)
        else None
    )
    # Freeze payload IDs before native shape deletion or slide reordering.
    # Shared XML application locates the frozen shape ID in its original part.
    edits.group_text_slide_payloads = slides

    def resolve(key: tuple[int, Any]) -> tuple[int, Any]:
        nonlocal slides
        slide_index, ref = key
        if not isinstance(ref, tuple) or len(ref) < 3:
            return key
        if slides is None:
            slides = load_slide_payloads(current)
        if slide_index not in group_indices:
            group_indices[slide_index] = [
                index
                for index, shape in enumerate(slides[slide_index]["shapes"])
                if shape.get("kind") == "group"
            ]
        return slide_index, (group_indices[slide_index][ref[0]], *ref[1:])

    def resolve_group_text_key(key: tuple[Any, ...]) -> tuple[Any, ...]:
        slide_index, parent, child_index, *indices = key
        ref = (*parent, child_index) if isinstance(parent, tuple) else (parent, child_index)
        _, ref = resolve((slide_index, ref))
        return (slide_index, ref[:-1], ref[-1], *indices)

    for field in GROUP_TEXT_XML_FIELDS:
        records = getattr(edits, field)
        for index, (key, value) in enumerate(records):
            records[index] = (resolve_group_text_key(key), value)
    for field in (
        "group_child_paragraph_clear_edits",
        "group_child_paragraph_line_break_edits",
    ):
        records = getattr(edits, field)
        for index, key in enumerate(records):
            records[index] = resolve_group_text_key(key)

    for field in (
        "fill_pattern_edits",
        "fill_pattern_fore_color_edits",
        "fill_pattern_back_color_edits",
        "fill_color_edits",
        "fill_gradient_edits",
        "line_pattern_edits",
        "line_pattern_fore_color_edits",
        "line_pattern_back_color_edits",
        "line_color_edits",
        "line_width_edits",
        "line_dash_edits",
        "shape_line_end_edits",
        "connector_connection_edits",
        "shadow_inherit_edits",
        "shape_effect_edits",
        "shape_glow_edits",
        "hyperlink_edits",
        "target_slide_edits",
        "rotation_edits",
        "shape_flip_edits",
        "shape_lock_edits",
        "name_edits",
        "adjustment_edits",
        "picture_crop_edits",
        "media_playback_edits",
    ):
        records = getattr(edits, field)
        for index, (key, value) in enumerate(records):
            resolved = resolve(key)
            if resolved is not key:
                records[index] = (resolved, value)
    for field in (
        "fill_solid_edits",
        "fill_background_edits",
        "line_solid_edits",
        "line_background_edits",
        "line_element_edits",
    ):
        records = getattr(edits, field)
        for index, key in enumerate(records):
            records[index] = resolve(key)
    for index, (slide_index, ref, action) in enumerate(edits.shape_z_order_edits):
        slide_index, ref = resolve((slide_index, ref))
        edits.shape_z_order_edits[index] = (slide_index, ref, action)
    for field in ("nested_group_child_text_edits", "deeper_group_child_text_edits"):
        records = getattr(edits, field)
        for index, (key, text) in enumerate(records):
            slide_index, ref = resolve((key[0], key[1:]))
            records[index] = ((slide_index, *ref), text)
    # Rotation refs keep this queue-time index space; a removed shape's
    # rotation is dropped rather than applied to its successor.
    removed = set(edits.shape_deletes)
    edits.rotation_edits = [
        ((slide_index, ref), rotation)
        for (slide_index, ref), rotation in edits.rotation_edits
        if (slide_index, ref if isinstance(ref, int) else ref[0]) not in removed
    ]
    edits.rotation_slide_payloads = (
        (slides if slides is not None else load_slide_payloads(current))
        if edits.rotation_edits
        else None
    )


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
    deleted_slide_parts_set = {str(part).lstrip("/") for part in slide_deletions}
    slide_order = None if self._slide_order is None else list(self._slide_order)
    slide_layout_removals = list(self._slide_layout_removals)
    slide_layout_changes = [
        (slide_part, layout_part)
        for slide_part, layout_part in getattr(self, "_slide_layout_changes", {}).items()
        if not (isinstance(slide_part, str) and slide_part.lstrip("/") in deleted_slide_parts_set)
    ]
    notes_slide_adds = [
        (slide_index, slide_part, notes_part)
        for slide_index, (slide_part, notes_part) in self._notes_slide_adds.items()
    ]
    custom_show_edits = (
        None if getattr(self, "_custom_show_edits", None) is None else list(self._custom_show_edits)
    )
    handout_master_partname = getattr(
        self,
        "_pending_handout_master_partname",
        None,
    )
    part_placeholder_adds = list(self._part_placeholder_adds)
    slide_master_authoring_requests = list(getattr(self, "_slide_master_authoring_requests", []))
    shape_adds = list(self._shape_adds)
    media_playback_edits = list(self._media_playback_edits.items())
    shape_deletes = sorted(self._shape_deletes)
    group_child_shape_deletes = sorted(self._group_child_shape_deletes)
    table_cell_edits = list(self._table_cell_edits.items())
    table_row_column_edits = list(self._table_row_column_edits)
    table_row_height_edits = list(self._table_row_height_edits.items())
    table_column_width_edits = list(self._table_column_width_edits.items())
    table_cell_margin_edits = list(self._table_cell_margin_edits.items())
    table_cell_vertical_anchor_edits = list(self._table_cell_vertical_anchor_edits.items())
    table_cell_border_edits = list(self._table_cell_border_edits.items())
    table_cell_text_frame_margin_edits = list(self._table_cell_text_frame_margin_edits.items())
    table_cell_text_frame_vertical_anchor_edits = list(
        self._table_cell_text_frame_vertical_anchor_edits.items()
    )
    table_cell_text_frame_content_edits = list(self._table_cell_text_frame_content_edits.items())
    table_cell_text_frame_word_wrap_edits = list(
        self._table_cell_text_frame_word_wrap_edits.items()
    )
    table_cell_text_frame_auto_size_edits = list(
        self._table_cell_text_frame_auto_size_edits.items()
    )
    table_cell_text_frame_fit_edits = list(self._table_cell_text_frame_fit_edits.items())
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
    table_cell_fill_background_edits = list(self._table_cell_fill_background_edits)
    table_cell_fill_pattern_edits = list(self._table_cell_fill_pattern_edits.items())
    table_cell_fill_pattern_fore_color_edits = list(
        self._table_cell_fill_pattern_fore_color_edits.items()
    )
    table_cell_fill_pattern_back_color_edits = list(
        self._table_cell_fill_pattern_back_color_edits.items()
    )
    table_cell_fill_color_edits = list(self._table_cell_fill_color_edits.items())
    table_cell_fill_gradient_edits = list(self._table_cell_fill_gradient_edits.items())
    background_fill_solid_edits = list(self._background_fill_solid_edits)
    background_fill_background_edits = list(self._background_fill_background_edits)
    background_fill_color_edits = list(self._background_fill_color_edits.items())
    table_cell_merge_edits = [dict(edit) for edit in self._table_cell_merge_edits]
    table_style_edits = list(self._table_style_edits.items())
    text_run_edits = list(self._text_run_edits.items())
    text_run_bold_edits = list(self._text_run_bold_edits.items())
    text_run_italic_edits = list(self._text_run_italic_edits.items())
    text_run_underline_edits = list(self._text_run_underline_edits.items())
    text_run_strike_edits = list(self._text_run_strike_edits.items())
    text_run_font_size_edits = list(self._text_run_font_size_edits.items())
    text_run_font_name_edits = list(self._text_run_font_name_edits.items())
    text_run_font_color_edits = list(self._text_run_font_color_edits.items())
    text_run_font_fill_type_edits = list(self._text_run_font_fill_type_edits.items())
    text_run_font_language_edits = list(self._text_run_font_language_edits.items())
    text_run_hyperlink_edits = list(self._text_run_hyperlink_edits.items())
    text_run_advanced_edits = list(self._text_run_advanced_edits.items())
    text_run_appends = list(self._text_run_appends.items())
    paragraph_text_edits = list(self._paragraph_text_edits.items())
    paragraph_clear_edits = list(self._paragraph_clear_edits)
    paragraph_line_break_edits = list(self._paragraph_line_break_edits)
    paragraph_appends = list(self._paragraph_appends.items())
    paragraph_alignment_edits = list(self._paragraph_alignment_edits.items())
    paragraph_level_edits = list(self._paragraph_level_edits.items())
    paragraph_spacing_edits = list(self._paragraph_spacing_edits.items())
    paragraph_font_edits = list(self._paragraph_font_edits.items())
    paragraph_bullet_edits = list(self._paragraph_bullet_edits.items())
    paragraph_tab_stop_edits = list(self._paragraph_tab_stop_edits.items())
    group_child_paragraph_tab_stop_edits = list(self._group_child_paragraph_tab_stop_edits.items())
    part_paragraph_tab_stop_edits = list(self._part_paragraph_tab_stop_edits.items())
    text_frame_margin_edits = list(self._text_frame_margin_edits.items())
    text_frame_word_wrap_edits = list(self._text_frame_word_wrap_edits.items())
    text_frame_vertical_anchor_edits = list(self._text_frame_vertical_anchor_edits.items())
    text_frame_auto_size_edits = list(self._text_frame_auto_size_edits.items())
    text_frame_fit_edits = list(self._text_frame_fit_edits.items())
    text_frame_advanced_edits = list(self._text_frame_advanced_edits.items())
    group_child_text_frame_advanced_edits = list(
        self._group_child_text_frame_advanced_edits.items()
    )
    part_text_frame_advanced_edits = list(self._part_text_frame_advanced_edits.items())
    group_child_text_frame_margin_edits = list(self._group_child_text_frame_margin_edits.items())
    group_child_text_frame_word_wrap_edits = list(
        self._group_child_text_frame_word_wrap_edits.items()
    )
    group_child_text_frame_vertical_anchor_edits = list(
        self._group_child_text_frame_vertical_anchor_edits.items()
    )
    group_child_text_frame_auto_size_edits = list(
        self._group_child_text_frame_auto_size_edits.items()
    )
    group_child_text_frame_fit_edits = list(self._group_child_text_frame_fit_edits.items())
    text_edits = list(self._shape_text_edits.items())
    group_child_text_edits = list(self._group_child_text_edits.items())
    nested_group_child_text_edits = list(self._nested_group_child_text_edits.items())
    deeper_group_child_text_edits = list(self._deeper_group_child_text_edits.items())
    group_child_paragraph_text_edits = list(self._group_child_paragraph_text_edits.items())
    group_child_paragraph_clear_edits = list(self._group_child_paragraph_clear_edits)
    group_child_paragraph_line_break_edits = list(self._group_child_paragraph_line_break_edits)
    group_child_run_text_edits = list(self._group_child_run_text_edits.items())
    group_child_run_font_edits = list(self._group_child_run_font_edits.items())
    group_child_run_hyperlink_edits = list(self._group_child_run_hyperlink_edits.items())
    group_child_paragraph_alignment_edits = list(
        self._group_child_paragraph_alignment_edits.items()
    )
    group_child_paragraph_font_edits = list(self._group_child_paragraph_font_edits.items())
    group_child_paragraph_level_edits = list(self._group_child_paragraph_level_edits.items())
    group_child_paragraph_spacing_edits = list(self._group_child_paragraph_spacing_edits.items())
    group_child_paragraph_bullet_edits = list(self._group_child_paragraph_bullet_edits.items())
    part_shape_text_edits = list(self._part_shape_text_edits.items())
    part_paragraph_text_edits = list(self._part_paragraph_text_edits.items())
    part_paragraph_clear_edits = sorted(self._part_paragraph_clear_edits)
    part_paragraph_line_break_edits = list(self._part_paragraph_line_break_edits)
    part_run_text_edits = list(self._part_run_text_edits.items())
    part_paragraph_alignment_edits = list(self._part_paragraph_alignment_edits.items())
    part_paragraph_level_edits = list(self._part_paragraph_level_edits.items())
    part_paragraph_spacing_edits = list(self._part_paragraph_spacing_edits.items())
    part_paragraph_font_edits = list(self._part_paragraph_font_edits.items())
    part_paragraph_bullet_edits = list(self._part_paragraph_bullet_edits.items())
    part_run_font_edits = list(self._part_run_font_edits.items())
    part_run_hyperlink_edits = list(self._part_run_hyperlink_edits.items())
    part_shape_hyperlink_edits = list(self._part_shape_hyperlink_edits.items())
    part_text_frame_margin_edits = list(self._part_text_frame_margin_edits.items())
    part_text_frame_word_wrap_edits = list(self._part_text_frame_word_wrap_edits.items())
    part_text_frame_vertical_anchor_edits = list(
        self._part_text_frame_vertical_anchor_edits.items()
    )
    part_text_frame_auto_size_edits = list(self._part_text_frame_auto_size_edits.items())
    adjustment_edits = list(self._shape_adjustment_edits.items())
    shape_adds, text_edits = ops._coalesce_auto_shape_text(shape_adds, text_edits)
    shape_adds, adjustment_edits = ops._coalesce_auto_shape_adjustments(
        shape_adds,
        adjustment_edits,
    )
    shape_adds = ops._coalesce_connected_connector_auto_shapes(shape_adds)
    shape_adds, table_cell_edits = ops._coalesce_table_cell_text(shape_adds, table_cell_edits)
    geometry_edits = []
    part_geometry_edits = []
    for key, geometry in self._shape_geometry_edits.items():
        target = part_geometry_edits if isinstance(key[0], str) else geometry_edits
        target.append((key, geometry))
    group_child_geometry_edits = list(self._group_child_geometry_edits.items())
    nested_group_child_geometry_edits = list(self._nested_group_child_geometry_edits.items())
    deeper_group_child_geometry_edits = list(self._deeper_group_child_geometry_edits.items())
    fill_solid_edits = list(self._shape_fill_solid_edits)
    fill_background_edits = list(self._shape_fill_background_edits)
    fill_pattern_edits = list(self._shape_fill_pattern_edits.items())
    fill_pattern_fore_color_edits = list(self._shape_fill_pattern_fore_color_edits.items())
    fill_pattern_back_color_edits = list(self._shape_fill_pattern_back_color_edits.items())
    fill_color_edits = list(self._shape_fill_color_edits.items())
    fill_gradient_edits = list(self._shape_fill_gradient_edits.items())
    line_solid_edits = list(self._shape_line_solid_edits)
    line_background_edits = list(self._shape_line_background_edits)
    line_pattern_edits = list(self._shape_line_pattern_edits.items())
    line_pattern_fore_color_edits = list(self._shape_line_pattern_fore_color_edits.items())
    line_pattern_back_color_edits = list(self._shape_line_pattern_back_color_edits.items())
    line_color_edits = list(self._shape_line_color_edits.items())
    line_width_edits = list(self._shape_line_width_edits.items())
    line_dash_edits = list(self._shape_line_dash_edits.items())
    shape_line_end_edits = list(self._shape_line_end_edits.items())
    connector_connection_edits = list(self._connector_connection_edits.items())
    shadow_inherit_edits = list(self._shape_shadow_inherit_edits.items())
    shape_effect_edits = list(self._shape_effect_edits.items())
    shape_glow_edits = list(self._shape_glow_edits.items())
    hyperlink_edits = list(self._shape_hyperlink_edits.items())
    target_slide_edits = list(self._shape_target_slide_edits.items())
    rotation_edits = list(self._shape_rotation_edits.items())
    shape_flip_edits = list(self._shape_flip_edits.items())
    shape_lock_edits = list(self._shape_lock_edits.items())
    name_edits = list(self._shape_name_edits.items())
    shape_preset_edits = [
        (slide_part, shape_id, preset)
        for (slide_part, shape_id), preset in self._shape_preset_edits.items()
        if str(slide_part).lstrip("/") not in deleted_slide_parts_set
    ]
    shape_z_order_edits = list(self._shape_z_order_edits)
    line_element_edits = list(self._shape_line_element_edits)
    picture_crop_edits = list(self._picture_crop_edits.items())
    picture_replace_edits = list(self._picture_replace_edits.items())
    picture_transparency_edits = [
        (slide_part, shape_id, val)
        for (slide_part, shape_id), val in getattr(self, "_picture_transparency_edits", {}).items()
        if str(slide_part).lstrip("/") not in deleted_slide_parts_set
    ]
    picture_correction_edits = [
        (slide_part, shape_id, dict(patch))
        for (slide_part, shape_id), patch in self._picture_correction_edits.items()
        if str(slide_part).lstrip("/") not in deleted_slide_parts_set
    ]
    picture_recolor_edits = [
        (slide_part, shape_id, list(transforms))
        for (slide_part, shape_id), transforms in self._picture_recolor_edits.items()
        if str(slide_part).lstrip("/") not in deleted_slide_parts_set
    ]
    chart_data_edits = list(self._chart_data_edits.items())
    chart_title_edits = list(self._chart_title_edits.items())
    chart_legend_edits = list(self._chart_legend_edits.items())
    chart_font_edits = list(self._chart_font_edits.items())
    chart_data_label_edits = list(self._chart_data_label_edits.items())
    chart_plot_property_edits = list(self._chart_plot_property_edits.items())
    chart_axis_title_edits = list(self._chart_axis_title_edits.items())
    chart_axis_property_edits = list(self._chart_axis_property_edits.items())
    chart_style_edits = list(self._chart_style_edits.items())
    chart_trendline_edits = [
        (chart_part, series_index, spec)
        for (chart_part, series_index), spec in getattr(self, "_chart_trendline_edits", {}).items()
    ]
    chart_error_bar_edits = [
        (chart_part, series_index, spec)
        for (chart_part, series_index), spec in getattr(self, "_chart_error_bar_edits", {}).items()
    ]
    presentation_size_edits = dict(self._presentation_size_edits)
    slide_name_edits = [
        (identifier, name)
        for identifier, name in self._slide_name_edits.items()
        if not (isinstance(identifier, str) and identifier.lstrip("/") in deleted_slide_parts_set)
    ]
    slide_hidden_edits = [
        (identifier, hidden)
        for identifier, hidden in getattr(self, "_slide_hidden_edits", {}).items()
        if not (isinstance(identifier, str) and identifier.lstrip("/") in deleted_slide_parts_set)
    ]
    slide_transition_edits = list(self._slide_transition_edits.items())
    slide_animation_edits = [
        (identifier, spec)
        for identifier, spec in getattr(self, "_slide_animation_edits", {}).items()
        if not (isinstance(identifier, str) and identifier.lstrip("/") in deleted_slide_parts_set)
    ]
    core_properties_edits = (
        None if self._core_properties_edits is None else dict(self._core_properties_edits)
    )
    custom_properties_edits = (
        None if self._custom_properties_edits is None else self._custom_properties_edits
    )
    extended_properties_edits = (
        None
        if getattr(self, "_extended_properties_edits", None) is None
        else self._extended_properties_edits
    )
    section_edits = None if getattr(self, "_section_edits", None) is None else self._section_edits
    table_style_id_edits = (
        list(getattr(self, "_table_style_id_edits", {}).items())
        if getattr(self, "_table_style_id_edits", None)
        else []
    )
    return SimpleNamespace(
        **{name: value for name, value in locals().items() if name not in {"self", "ops"}}
    )
