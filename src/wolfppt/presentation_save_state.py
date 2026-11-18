"""State inspection helpers for presentation saves."""

from __future__ import annotations

from typing import Any

_PENDING_EDIT_FIELDS = (
    "_slide_creations",
    "_slide_deletions",
    "_slide_order",
    "_slide_layout_removals",
    "_slide_layout_changes",
    "_notes_slide_adds",
    "_custom_show_edits",
    "_pending_handout_master_partname",
    "_part_placeholder_adds",
    "_slide_master_authoring_requests",
    "_shape_adds",
    "_zoom_edits",
    "_media_playback_edits",
    "_shape_deletes",
    "_group_child_shape_deletes",
    "_table_cell_edits",
    "_table_row_column_edits",
    "_table_row_height_edits",
    "_table_column_width_edits",
    "_table_cell_margin_edits",
    "_table_cell_vertical_anchor_edits",
    "_table_cell_border_edits",
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
    "_table_cell_text_frame_paragraph_line_break_edits",
    "_table_cell_text_frame_paragraph_run_font_edits",
    "_table_cell_text_frame_paragraph_run_hyperlink_edits",
    "_table_cell_fill_solid_edits",
    "_table_cell_fill_background_edits",
    "_table_cell_fill_pattern_edits",
    "_table_cell_fill_pattern_fore_color_edits",
    "_table_cell_fill_pattern_back_color_edits",
    "_table_cell_fill_color_edits",
    "_table_cell_fill_gradient_edits",
    "_background_fill_solid_edits",
    "_background_fill_background_edits",
    "_background_fill_color_edits",
    "_table_cell_merge_edits",
    "_table_style_edits",
    "_text_run_edits",
    "_text_run_bold_edits",
    "_text_run_italic_edits",
    "_text_run_underline_edits",
    "_text_run_strike_edits",
    "_text_run_font_size_edits",
    "_text_run_font_name_edits",
    "_text_run_font_color_edits",
    "_text_run_font_fill_type_edits",
    "_text_run_font_language_edits",
    "_text_run_hyperlink_edits",
    "_text_run_advanced_edits",
    "_paragraph_tab_stop_edits",
    "_group_child_paragraph_tab_stop_edits",
    "_part_paragraph_tab_stop_edits",
    "_text_frame_advanced_edits",
    "_group_child_text_frame_advanced_edits",
    "_part_text_frame_advanced_edits",
    "_text_run_appends",
    "_paragraph_text_edits",
    "_paragraph_clear_edits",
    "_paragraph_line_break_edits",
    "_paragraph_appends",
    "_paragraph_alignment_edits",
    "_paragraph_level_edits",
    "_paragraph_spacing_edits",
    "_paragraph_font_edits",
    "_paragraph_bullet_edits",
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
    "_group_child_paragraph_clear_edits",
    "_group_child_paragraph_line_break_edits",
    "_group_child_run_text_edits",
    "_group_child_run_font_edits",
    "_group_child_run_hyperlink_edits",
    "_group_child_paragraph_alignment_edits",
    "_group_child_paragraph_font_edits",
    "_group_child_paragraph_level_edits",
    "_group_child_paragraph_spacing_edits",
    "_group_child_paragraph_bullet_edits",
    "_part_shape_text_edits",
    "_part_paragraph_text_edits",
    "_part_paragraph_clear_edits",
    "_part_paragraph_line_break_edits",
    "_part_run_text_edits",
    "_part_paragraph_alignment_edits",
    "_part_paragraph_level_edits",
    "_part_paragraph_spacing_edits",
    "_part_paragraph_font_edits",
    "_part_paragraph_bullet_edits",
    "_part_run_font_edits",
    "_part_run_hyperlink_edits",
    "_part_shape_hyperlink_edits",
    "_part_text_frame_margin_edits",
    "_part_text_frame_word_wrap_edits",
    "_part_text_frame_vertical_anchor_edits",
    "_part_text_frame_auto_size_edits",
    "_shape_geometry_edits",
    "_group_child_geometry_edits",
    "_nested_group_child_geometry_edits",
    "_deeper_group_child_geometry_edits",
    "_shape_fill_solid_edits",
    "_shape_fill_background_edits",
    "_shape_fill_pattern_edits",
    "_shape_fill_pattern_fore_color_edits",
    "_shape_fill_pattern_back_color_edits",
    "_shape_fill_color_edits",
    "_shape_fill_gradient_edits",
    "_shape_line_solid_edits",
    "_shape_line_background_edits",
    "_shape_line_pattern_edits",
    "_shape_line_pattern_fore_color_edits",
    "_shape_line_pattern_back_color_edits",
    "_shape_line_color_edits",
    "_shape_line_width_edits",
    "_shape_line_dash_edits",
    "_shape_line_end_edits",
    "_connector_connection_edits",
    "_shape_shadow_inherit_edits",
    "_shape_effect_edits",
    "_shape_glow_edits",
    "_shape_hyperlink_edits",
    "_shape_target_slide_edits",
    "_shape_rotation_edits",
    "_shape_flip_edits",
    "_shape_lock_edits",
    "_shape_name_edits",
    "_shape_adjustment_edits",
    "_shape_preset_edits",
    "_shape_z_order_edits",
    "_shape_line_element_edits",
    "_picture_crop_edits",
    "_picture_transparency_edits",
    "_picture_correction_edits",
    "_picture_recolor_edits",
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
    "_chart_trendline_edits",
    "_chart_error_bar_edits",
    "_presentation_size_edits",
    "_slide_name_edits",
    "_slide_hidden_edits",
    "_slide_transition_edits",
    "_slide_animation_edits",
    "_table_style_id_edits",
)

# Queued edits that only rewrite text and text formatting inside shapes that
# already exist. Applying them never adds, removes, reorders, or renumbers a
# slide's shapes, so saved shape identities equal the held facades' identities.
_SHAPE_IDENTITY_PRESERVING_EDIT_FIELDS = frozenset(
    (
        "_text_run_edits",
        "_text_run_bold_edits",
        "_text_run_italic_edits",
        "_text_run_underline_edits",
        "_text_run_strike_edits",
        "_text_run_font_size_edits",
        "_text_run_font_name_edits",
        "_text_run_font_color_edits",
        "_text_run_font_fill_type_edits",
        "_text_run_font_language_edits",
        "_text_run_advanced_edits",
        "_text_run_appends",
        "_paragraph_text_edits",
        "_paragraph_clear_edits",
        "_paragraph_line_break_edits",
        "_paragraph_appends",
        "_paragraph_alignment_edits",
        "_paragraph_level_edits",
        "_paragraph_spacing_edits",
        "_paragraph_font_edits",
        "_paragraph_bullet_edits",
        "_paragraph_tab_stop_edits",
        "_text_frame_margin_edits",
        "_text_frame_word_wrap_edits",
        "_text_frame_vertical_anchor_edits",
        "_text_frame_auto_size_edits",
        "_text_frame_fit_edits",
        "_text_frame_advanced_edits",
        "_shape_text_edits",
        "_group_child_text_edits",
        "_nested_group_child_text_edits",
        "_deeper_group_child_text_edits",
        "_group_child_paragraph_text_edits",
        "_group_child_paragraph_clear_edits",
        "_group_child_paragraph_line_break_edits",
        "_group_child_paragraph_alignment_edits",
        "_group_child_paragraph_font_edits",
        "_group_child_paragraph_level_edits",
        "_group_child_paragraph_spacing_edits",
        "_group_child_paragraph_bullet_edits",
        "_group_child_paragraph_tab_stop_edits",
        "_group_child_run_text_edits",
        "_group_child_run_font_edits",
        "_group_child_text_frame_margin_edits",
        "_group_child_text_frame_word_wrap_edits",
        "_group_child_text_frame_vertical_anchor_edits",
        "_group_child_text_frame_auto_size_edits",
        "_group_child_text_frame_fit_edits",
        "_group_child_text_frame_advanced_edits",
    )
)


def has_pending_save_edits(presentation: Any) -> bool:
    """Return whether save needs to rewrite anything beyond copying the source."""
    if has_pending_lifecycle_edits(presentation):
        return True
    if getattr(presentation, "_core_properties_edits", None) is not None:
        return True
    if getattr(presentation, "_custom_properties_edits", None) is not None:
        return True
    if getattr(presentation, "_extended_properties_edits", None) is not None:
        return True
    if getattr(presentation, "_section_edits", None) is not None:
        return True
    if getattr(presentation, "_custom_show_edits", None) is not None:
        return True
    return any(getattr(presentation, field, None) for field in _PENDING_EDIT_FIELDS)


def has_pending_lifecycle_edits(presentation: Any) -> bool:
    """Lazy inspection must not turn an unchanged package into an edited one."""
    tags = getattr(presentation, "_lifecycle_tags", {})
    view = getattr(presentation, "_lifecycle_view_state", None)
    fields = getattr(presentation, "_lifecycle_fields", None)
    return (
        any(collection.dirty for collection in tags.values())
        or (view is not None and view.dirty)
        or (fields is not None and fields.dirty)
    )


def snapshot_lifecycle_edits(presentation: Any) -> Any:
    """Capture immutable operation values without consuming live owner state.

    Capture once before ordinary staging. Owners in the records are identity
    handles, never deep-copied facades or positional indexes.
    """
    from types import SimpleNamespace

    tags = tuple(
        (collection, collection.snapshot())
        for collection in getattr(presentation, "_lifecycle_tags", {}).values()
        if collection.dirty
    )
    view = getattr(presentation, "_lifecycle_view_state", None)
    view_record = (view, view.snapshot()) if view is not None and view.dirty else None
    fields = getattr(presentation, "_lifecycle_fields", None)
    field_records = (
        ()
        if fields is None
        else tuple(
            (collection, collection.snapshot())
            for collection in fields._collections.values()
            if collection.dirty
        )
    )
    return SimpleNamespace(
        presentation=presentation, tags=tags, view=view_record, fields=field_records
    )


def apply_lifecycle_edits(
    input_path: Any,
    output_path: Any,
    snapshot: Any,
    *,
    staged_slide_parts: Any = None,
    resolve_owner: Any = None,
) -> Any:
    """Apply all domains to a private stage; return a publication receipt.

    resolve_owner(OwnerRef) -> (partname, cNvPr_id_or_None) | None is the
    authoritative shape materialization bridge. For authored shapes it is
    required; no guessed ordinal or provisional cNvPr id is used. Returning
    None permits the stable loaded-id / slide-creation-token path.

    No live queues, source paths or owner payloads change here. Pass a fresh
    scratch output, never the user's source or final destination.
    """
    from pathlib import Path
    from types import SimpleNamespace

    from .custom_properties import _CustomXmlRoots, _prune_detached_custom_xml
    from .package_parts import copy_open_package_with_replacements, open_package_source
    from .presentation_fields import _signature, apply_field_edits
    from .presentation_tags import (
        LifecycleRefusal,
        apply_tag_edits,
        parse_xml,
        serialize_xml,
    )
    from .presentation_view_state import apply_view_edits
    from .slide_metadata import presentation_partname

    input_path, output_path = Path(input_path), Path(output_path)
    if input_path.resolve() == output_path.resolve() or output_path.exists():
        raise LifecycleRefusal("lifecycle staging requires a fresh distinct scratch output")
    roots = _CustomXmlRoots()
    staged_parts = staged_slide_parts or {}
    identities: dict = {}

    def resolve(ref: Any) -> Any:
        if ref not in identities:
            identities[ref] = ref.resolve(staged_parts, resolve_owner)
        return identities[ref]

    with open_package_source(input_path) as package:
        for _, record in snapshot.tags:
            apply_tag_edits(package, roots, record, staged_parts, resolve)
        view_part = None
        if snapshot.view is not None:
            view_part, _ = apply_view_edits(
                package, roots, snapshot.view[1], presentation_partname(input_path)
            )
        records = tuple(record for _, values in snapshot.fields for record in values)
        if records:
            apply_field_edits(package, roots, records, staged_parts, resolve)
        removals = _prune_detached_custom_xml(package, roots)
        # Traversal alone never rewrites a member, even if its original prefixes
        # or whitespace differ from ElementTree's serialization conventions.
        replacements = {
            part: serialize_xml(root)
            for part, root in roots.items()
            if part not in package.namelist()
            or _signature(root) != _signature(parse_xml(package.read(part)))
        }
        view_payload = None if view_part is None else replacements.get(view_part)
        if view_part is not None and view_payload is None:
            view_payload = package.read(view_part)
        copy_open_package_with_replacements(package, output_path, replacements, removals)
    return SimpleNamespace(
        snapshot=snapshot,
        identities=identities,
        view_part=view_part,
        view_payload=view_payload,
        acknowledged=False,
    )


def acknowledge_lifecycle_edits(presentation: Any, receipt: Any) -> None:
    """Acknowledge only after the *outermost* destination publication succeeds.

    First materialize/rebase identities and establish the new package
    baseline (also for stream output), then calls this exactly once. Ordinary
    queue cleanup must not clear these domains before this point.
    """
    from dataclasses import replace

    from .presentation_tags import LifecycleRefusal

    snapshot = receipt.snapshot
    if snapshot.presentation is not presentation or receipt.acknowledged:
        raise LifecycleRefusal("foreign or already acknowledged lifecycle receipt")
    for collection, record in snapshot.tags:
        _part, shape_id = receipt.identities[record[0]]
        collection._ref = replace(collection._ref, shape_id=shape_id, creation_token=None)
        collection.acknowledge(record[1])
    if snapshot.view is not None:
        snapshot.view[0].acknowledge(snapshot.view[1], receipt.view_payload, receipt.view_part)
    for collection, records in snapshot.fields:
        _part, shape_id = receipt.identities[collection._ref]
        collection._ref = replace(collection._ref, shape_id=shape_id, creation_token=None)
        collection.acknowledge(records)
    receipt.acknowledged = True


def prepare_saved_owners(presentation: Any, path: Any) -> tuple[dict, list]:
    """Finalize the staged package, then bind held objects to final IDs.

    The staged package first drops the parts and timing that only shapes
    deleted in this save used (see remove_deleted_shape_closure); owner
    binding then reads that final package without changing live state. A save
    whose queued edits only rewrite text inside existing shapes cannot change
    any slide's shape identities, so it binds held slides to their own
    identities instead of re-summarizing every staged slide.

    Loaded siblings bind by cNvPr ID. Layout placeholders on a new blank slide
    bind by placeholder idx because their facade IDs are provisional. Authored
    siblings bind to remaining native insertions in authoring order within their
    actual parent, never to provisional IDs or a flattened group ordinal.
    """
    from .presentation_tags import LifecycleRefusal
    from .slide_metadata import slide_notes_partname_for_part
    from .slide_payloads import load_shape_payloads, load_slide_payloads

    remove_deleted_shape_closure(presentation, path)
    staged = getattr(presentation, "_staged_slide_materializations", {})
    held_shapes = _identity_preserved_shape_payloads(presentation)
    by_part = (
        None
        if held_shapes is not None
        else {slide["part"]: slide for slide in load_slide_payloads(path)}
    )
    identities: dict = {}
    plans: list = []

    def bind(
        collection: Any,
        payloads: list,
        part: str,
        ancestry: tuple,
        group_ordinal: int | None = None,
        *,
        pending_layout_placeholders: bool = False,
    ) -> None:
        by_id: dict = {}
        for index, payload in enumerate(payloads):
            identifier = str(payload.get("id", ""))
            if not identifier or identifier in by_id:
                raise LifecycleRefusal("missing or ambiguous saved shape identity")
            by_id[identifier] = (index, payload)
        placeholders: dict | None = {} if pending_layout_placeholders else None
        if placeholders is not None:
            for identifier, (_, payload) in by_id.items():
                if payload.get("is_placeholder"):
                    idx = str(payload.get("placeholder_idx") or "0")
                    if idx in placeholders:
                        raise LifecycleRefusal("missing or ambiguous saved placeholder identity")
                    placeholders[idx] = identifier
        loaded = {}
        pending = []
        for shape in collection:
            if shape._payload.get("_pending_shape") or shape._payload.get("_pending_group_child"):
                pending.append(shape)
            else:
                identifier = str(shape.shape_id)
                if placeholders is not None and shape._payload.get("is_placeholder"):
                    idx = str(shape._payload.get("placeholder_idx") or "0")
                    identifier = placeholders.get(idx)
                if identifier not in by_id or identifier in loaded:
                    raise LifecycleRefusal("held shape has no unique saved identity")
                loaded[identifier] = shape
        inserted = [
            (identifier, value) for identifier, value in by_id.items() if identifier not in loaded
        ]
        if len(inserted) != len(pending):
            raise LifecycleRefusal("authored shapes do not match staged parent insertions")
        matched = dict(loaded)
        matched.update(
            (identifier, shape) for shape, (identifier, _) in zip(pending, inserted, strict=True)
        )
        ordered = []
        ordinal = 0
        for identifier, (index, payload) in by_id.items():
            shape = matched[identifier]
            identities[shape] = (part, identifier)
            ordered.append((shape, payload, index, ancestry, group_ordinal))
            children = getattr(shape, "_group_shapes", None)
            if children is not None:
                bind(
                    children,
                    payload.get("children", []),
                    part,
                    (*ancestry, index),
                    ordinal if not ancestry else group_ordinal,
                )
            if payload.get("kind") == "group":
                ordinal += 1
        plans.append((collection, ordered))

    for slide in presentation._slides:
        part = staged.get(slide._payload.get("_creation_token"), slide.partname)
        if by_part is None:
            shape_payloads = held_shapes.get(slide, [])
        else:
            payload = by_part.get(part)
            if payload is None:
                raise LifecycleRefusal("held slide has no saved part")
            shape_payloads = payload.get("shapes", [])
        identities[slide] = (part, None)
        if slide._shapes is not None:
            bind(
                slide._shapes,
                shape_payloads,
                part,
                (),
                pending_layout_placeholders=bool(
                    slide._payload.get("_pending_creation") and not slide.partname
                ),
            )
        notes = getattr(slide, "_notes_slide", None)
        if notes is not None:
            notes_part = slide_notes_partname_for_part(path, part)
            identities[notes] = (notes_part, None)
            bind(notes.shapes, load_shape_payloads(path, notes_part), notes_part, ())
    return identities, plans


def _identity_preserved_shape_payloads(presentation: Any) -> dict | None:
    """Saved shape identities of held slides when this save cannot change them.

    Returns ``None`` (read the staged package) unless every queued edit is in
    _SHAPE_IDENTITY_PRESERVING_EDIT_FIELDS, no slide is being created, and
    every held shape already has a unique persisted ID. Group-child edits also
    need the staged package when a held group's children are not loaded,
    because binding refreshes that group's child payloads from the save. The
    returned payloads carry only what binding reads: ID, kind, and children.
    """
    if has_pending_lifecycle_edits(presentation) or getattr(
        presentation, "_staged_slide_materializations", None
    ):
        return None
    if any(
        getattr(presentation, field, None)
        for field in _PENDING_EDIT_FIELDS
        if field not in _SHAPE_IDENTITY_PRESERVING_EDIT_FIELDS
    ):
        return None
    refresh_unloaded_groups = any(
        getattr(presentation, field, None)
        for field in _SHAPE_IDENTITY_PRESERVING_EDIT_FIELDS
        if "group_child" in field
    )
    held: dict = {}
    for slide in presentation._slides:
        if not slide.partname or slide._payload.get("_pending_creation"):
            return None
        if slide._shapes is not None:
            payloads = _held_shape_payloads(slide._shapes, refresh_unloaded_groups)
            if payloads is None:
                return None
            held[slide] = payloads
    return held


def _held_shape_payloads(collection: Any, refresh_unloaded_groups: bool) -> list | None:
    payloads: list = []
    seen: set = set()
    for shape in collection:
        payload = shape._payload
        identifier = payload.get("id")
        if (
            payload.get("_pending_shape")
            or payload.get("_pending_group_child")
            or identifier is None
            or str(identifier) != str(shape.shape_id)
            or str(identifier) in seen
        ):
            return None
        seen.add(str(identifier))
        saved = {"id": identifier, "kind": payload.get("kind")}
        children = getattr(shape, "_group_shapes", None)
        if children is not None:
            nested = _held_shape_payloads(children, refresh_unloaded_groups)
            if nested is None:
                return None
            saved["children"] = nested
        elif payload.get("kind") == "group":
            if refresh_unloaded_groups:
                return None
            saved["children"] = payload.get("children", [])
        payloads.append(saved)
    return payloads


def materialize_saved_owners(identities: dict, plans: list) -> None:
    """Commit prepared identities in place, preserving every held facade."""
    for owner, (part, identifier) in identities.items():
        if getattr(owner, "_payload", {}).get("_pending_creation"):
            owner._materialize_pending_creation(part)
        if identifier is not None:
            owner._payload["id"] = identifier
        if getattr(owner, "_is_notes_slide", False):
            owner._partname = part
            owner._index = owner._slide._index
    for collection, ordered in plans:
        collection._shapes[:] = [record[0] for record in ordered]
        for shape, payload, index, ancestry, group_ordinal in ordered:
            shape._index = index
            shape._payload["id"] = payload["id"]
            shape._payload.pop("_pending_shape", None)
            shape._payload.pop("_pending_group_child", None)
            shape._payload.pop("_pending_group_child_kind", None)
            if payload.get("kind") == "group" and getattr(shape, "_group_shapes", None) is None:
                shape._payload["children"] = payload.get("children", [])
            if ancestry:
                shape._payload["_group_shape_index"] = ancestry[-1]
                shape._payload["_group_index"] = group_ordinal
                shape._payload["_group_child_index"] = index
                shape._payload["_group_shape_id"] = shape._parent_group.shape_id
                if len(ancestry) >= 2:
                    shape._payload["_nested_group_child_index"] = ancestry[1]
                if len(ancestry) >= 3:
                    shape._payload["_deeper_group_child_index"] = ancestry[2]
        if hasattr(collection, "_group_shape"):
            collection._group_shape._payload["children"] = [shape._payload for shape, *_ in ordered]
        elif hasattr(collection, "_slide"):
            collection._slide._payload["shapes"] = [shape._payload for shape, *_ in ordered]


_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_SLIDE_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
_MEDIA_FILE_TAGS = frozenset(
    f"{{{_A_NS}}}{name}" for name in ("videoFile", "audioFile", "quickTimeFile", "wavAudioFile")
)
_MEDIA_FILE_MARKERS = tuple(
    name.encode() for name in ("videoFile", "audioFile", "quickTimeFile", "wavAudioFile")
)
_TIMING_MARKER = b"timing"
_TIMING_TARGET_TAGS = frozenset(f"{{{_P_NS}}}{name}" for name in ("spTgt", "inkTgt"))
_EFFECT_NODE_TYPES = frozenset(("clickEffect", "withEffect", "afterEffect"))


def remove_deleted_shape_closure(presentation: Any, path: Any) -> None:
    """Drop what only this save's deleted shapes used.

    Native shape deletion removes the shape and its now-unused slide
    relationships, but leaves the media and poster-frame parts those
    relationships targeted and every timing node (animation effects, media
    calls, build entries, ``p:audio``/``p:video`` nodes) that targets the
    removed shape ID. Rewrite the staged package in place so that:

    * a part is removed only when a media shape deleted in this save
      referenced it and no relationship anywhere in the staged package still
      does, so shared clips and pre-existing orphans are preserved;
    * a timing node is removed only when every shape it targets was deleted
      in this save (see _drop_deleted_shape_timing); references that were
      already dangling in the source are left alone.
    """
    from pathlib import Path

    if not (
        getattr(presentation, "_shape_deletes", None)
        or getattr(presentation, "_group_child_shape_deletes", None)
    ):
        return
    import os
    import tempfile
    import zipfile

    from .package_parts import copy_open_package_with_replacements, open_package_source

    source = presentation._source_path
    staged_path = Path(path)
    if isinstance(source, (str, Path)) and staged_path.resolve() == Path(source).resolve():
        raise RuntimeError("deleted shape cleanup must not rewrite the source package")
    with open_package_source(source) as package, zipfile.ZipFile(staged_path) as staged:
        names = set(staged.namelist())
        slides = _slide_parts(package)
        media_by_slide = _media_shapes_by_slide(package, slides)
        replacements: dict[str, bytes] = {}
        candidates: set[str] = set()
        for part in slides:
            if part not in names:
                continue
            payload = staged.read(part)
            media = media_by_slide.get(part, {})
            has_timing = _TIMING_MARKER in payload
            if not media and not has_timing:
                continue
            live_ids = _shape_ids(payload)
            for shape_id, parts in media.items():
                if shape_id not in live_ids:
                    candidates |= parts
            if not has_timing:
                continue
            deleted = _shape_ids(package.read(part)) - live_ids
            pruned = _drop_deleted_shape_timing(payload, deleted) if deleted else None
            if pruned is not None:
                replacements[part] = pruned
        orphans = candidates & names
        if orphans:
            orphans -= _relationship_targets(staged, names)
        removals = set(orphans)
        removals.update(rels for rels in map(_rels_part_name, orphans) if rels in names)
        if orphans and "[Content_Types].xml" in names:
            content_types = staged.read("[Content_Types].xml")
            pruned_types = _drop_content_type_overrides(content_types, orphans)
            if pruned_types is not None:
                replacements["[Content_Types].xml"] = pruned_types
        if not replacements and not removals:
            return
        descriptor, scratch = tempfile.mkstemp(
            prefix=f".{staged_path.name}.", suffix=".pptx", dir=staged_path.parent
        )
        os.close(descriptor)
        try:
            copy_open_package_with_replacements(staged, Path(scratch), replacements, removals)
        except BaseException:
            os.unlink(scratch)
            raise
    os.replace(scratch, staged_path)


def _xml(payload: bytes) -> Any:
    from xml.etree import ElementTree as ET

    return ET.fromstring(payload)


def _rels_part_name(part: str) -> str:
    import posixpath

    parent, filename = posixpath.split(part)
    return posixpath.join(parent, "_rels", f"{filename}.rels")


def _internal_targets(owner: str, payload: bytes) -> dict[str, str]:
    """Map relationship IDs of one part to the internal part names they target."""
    from urllib.parse import unquote

    from .render_package import resolve_target

    targets: dict[str, str] = {}
    for relationship in _xml(payload):
        target = relationship.get("Target")
        if not target or relationship.get("TargetMode", "").casefold() == "external":
            continue
        targets[relationship.get("Id", "")] = resolve_target(owner, unquote(target))
    return targets


def _slide_parts(package: Any) -> list[str]:
    """Slide part names the package declares and contains."""
    names = set(package.namelist())
    if "[Content_Types].xml" not in names:
        return []
    return [
        part
        for part in (
            element.get("PartName", "").lstrip("/")
            for element in _xml(package.read("[Content_Types].xml"))
            if element.tag == f"{{{_CT_NS}}}Override"
            and element.get("ContentType") == _SLIDE_CONTENT_TYPE
        )
        if part in names
    ]


def _shape_ids(payload: bytes) -> set[str]:
    """Every cNvPr ID in one slide, including group children."""
    return {
        element.get("id")
        for element in _xml(payload).iter(f"{{{_P_NS}}}cNvPr")
        if element.get("id") is not None
    }


def _media_shapes_by_slide(package: Any, slides: list[str]) -> dict[str, dict[str, set[str]]]:
    """Return slide part -> media shape cNvPr ID -> parts that shape references."""
    names = set(package.namelist())
    found: dict[str, dict[str, set[str]]] = {}
    for part in slides:
        rels = _rels_part_name(part)
        if rels not in names:
            continue
        payload = package.read(part)
        if not any(marker in payload for marker in _MEDIA_FILE_MARKERS):
            continue
        targets = _internal_targets(part, package.read(rels))
        media: dict[str, set[str]] = {}
        for picture in _xml(payload).iter(f"{{{_P_NS}}}pic"):
            if not any(element.tag in _MEDIA_FILE_TAGS for element in picture.iter()):
                continue
            properties = picture.find(f"{{{_P_NS}}}nvPicPr/{{{_P_NS}}}cNvPr")
            if properties is None or properties.get("id") is None:
                continue
            media[properties.get("id")] = {
                targets[value]
                for element in picture.iter()
                for name, value in element.attrib.items()
                if name.startswith(f"{{{_R_NS}}}") and value in targets
            }
        if media:
            found[part] = media
    return found


def _relationship_targets(package: Any, names: set[str]) -> set[str]:
    """Every internal part some relationship in the package still targets."""
    import posixpath

    referenced: set[str] = set()
    for name in names:
        parent, filename = posixpath.split(name)
        if posixpath.basename(parent) != "_rels" or not filename.endswith(".rels"):
            continue
        owner = posixpath.join(posixpath.dirname(parent), filename[: -len(".rels")])
        referenced.update(_internal_targets(owner, package.read(name)).values())
    return referenced


def _element_spans(payload: bytes) -> list[dict[str, Any]]:
    """Return every element with its expanded name, attributes, parent and byte span.

    Spans let a caller cut elements out of the original bytes, so everything
    else keeps its prefixes, declarations and formatting.
    """
    from xml.parsers import expat

    parser = expat.ParserCreate(namespace_separator="}")
    nodes: list[dict[str, Any]] = []
    stack: list[int] = []

    def start(name: str, attributes: dict[str, str]) -> None:
        nodes.append(
            {
                "tag": "{" + name if "}" in name else name,
                "attrib": attributes,
                "parent": stack[-1] if stack else None,
                "start": parser.CurrentByteIndex,
                "end": None,
            }
        )
        stack.append(len(nodes) - 1)

    def end(_name: str) -> None:
        node = nodes[stack.pop()]
        # expat reports a self-closing element's end *after* its tag, where the
        # next tag (possibly the parent's end tag) begins.
        opening_end = _tag_end(payload, node["start"])
        node["end"] = (
            opening_end
            if payload[opening_end - 2 : opening_end] == b"/>"
            else _tag_end(payload, parser.CurrentByteIndex)
        )

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(payload, True)
    return nodes


def _tag_end(payload: bytes, index: int) -> int:
    """Return the offset just past the tag starting at ``index``."""
    quote = None
    for offset in range(index, len(payload)):
        byte = payload[offset : offset + 1]
        if quote is not None:
            if byte == quote:
                quote = None
        elif byte in (b'"', b"'"):
            quote = byte
        elif byte == b">":
            return offset + 1
    raise ValueError("unterminated XML tag")


def _cut(payload: bytes, spans: list[tuple[int, int]]) -> bytes:
    for start, end in sorted(spans, reverse=True):
        payload = payload[:start] + payload[end:]
    return payload


def _drop_deleted_shape_timing(payload: bytes, shape_ids: set[str]) -> bytes | None:
    """Cut timing that targets only ``shape_ids``; None if nothing does.

    Leaves go when every shape they target is in ``shape_ids``: an effect
    ``p:par`` (its ``p:cTn`` has ``presetClass`` or an effect ``nodeType``,
    which includes ``mediacall`` playback), a ``p:audio``/``p:video`` media
    node, an interactive ``p:seq`` whose trigger condition targets the shape,
    and a ``p:bldLst`` entry. A container (click-group or sub-group ``p:par``,
    ``p:seq``, ``p:excl``, ``p:bldLst``, ``p:tnLst``) goes when all of its
    children go, and an emptied timeline takes the whole ``p:timing`` with
    it. Everything else keeps its original bytes.
    """
    nodes = _element_spans(payload)
    timing = next(
        (
            index
            for index, node in enumerate(nodes)
            if node["tag"] == f"{{{_P_NS}}}timing" and node["parent"] == 0
        ),
        None,
    )
    if timing is None:
        return None

    def subtree(index: int) -> range:
        end = index + 1
        while end < len(nodes) and nodes[end]["start"] < nodes[index]["end"]:
            end += 1
        return range(index + 1, end)

    children: dict[int, list[int]] = {}
    for index in subtree(timing):
        children.setdefault(nodes[index]["parent"], []).append(index)

    def child(index: int | None, name: str) -> int | None:
        return next(
            (
                item
                for item in children.get(index, ())
                if nodes[item]["tag"] == f"{{{_P_NS}}}{name}"
            ),
            None,
        )

    def only_deleted(index: int) -> bool:
        targets = {
            nodes[item]["attrib"].get("spid")
            for item in subtree(index)
            if nodes[item]["tag"] in _TIMING_TARGET_TAGS
        }
        return bool(targets) and targets <= shape_ids

    def emptied(index: int | None) -> bool:
        items = children.get(index, ()) if index is not None else ()
        return bool(items) and all(item in doomed for item in items)

    doomed: set[int] = set()
    # Reverse document order settles every descendant before its container.
    for index in reversed(subtree(timing)):
        tag = nodes[index]["tag"].removeprefix(f"{{{_P_NS}}}")
        if nodes[nodes[index]["parent"]]["tag"] == f"{{{_P_NS}}}bldLst":
            if nodes[index]["attrib"].get("spid") in shape_ids:
                doomed.add(index)
        elif tag in ("audio", "video"):
            if only_deleted(index):
                doomed.add(index)
        elif tag in ("bldLst", "tnLst"):
            if emptied(index):
                doomed.add(index)
        elif tag in ("par", "seq", "excl"):
            timeline = child(index, "cTn")
            if timeline is None:
                continue
            attributes = nodes[timeline]["attrib"]
            if tag == "par" and (
                "presetClass" in attributes or attributes.get("nodeType") in _EFFECT_NODE_TYPES
            ):
                if only_deleted(index):
                    doomed.add(index)
                continue
            trigger = child(timeline, "stCondLst")
            if (
                tag == "seq"
                and attributes.get("nodeType") == "interactiveSeq"
                and trigger is not None
                and only_deleted(trigger)
            ) or emptied(child(timeline, "childTnLst")):
                doomed.add(index)
    if not doomed:
        return None
    if child(timing, "tnLst") in doomed:
        doomed = {timing}

    def outermost(index: int) -> bool:
        parent = nodes[index]["parent"]
        while parent is not None:
            if parent in doomed:
                return False
            parent = nodes[parent]["parent"]
        return True

    return _cut(
        payload,
        [(nodes[index]["start"], nodes[index]["end"]) for index in doomed if outermost(index)],
    )


def _drop_content_type_overrides(payload: bytes, parts: set[str]) -> bytes | None:
    """Cut ``Override`` entries naming removed parts; None if there are none."""
    from urllib.parse import unquote

    spans = [
        (node["start"], node["end"])
        for node in _element_spans(payload)
        if node["tag"] == f"{{{_CT_NS}}}Override"
        and unquote(node["attrib"].get("PartName", "")).lstrip("/") in parts
    ]
    return _cut(payload, spans) if spans else None
