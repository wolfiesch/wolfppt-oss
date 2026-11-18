"""Slide and shape-add pipeline for presentation saves."""

from __future__ import annotations

import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements
from .presentation_save_ops import PresentationSaveOps
from .presentation_save_planning import (
    CHART_ADD_KINDS as _CHART_ADD_KINDS,
)
from .presentation_save_planning import (
    has_edits_after_shape_adds as _has_edits_after_shape_adds,
)
from .presentation_save_planning import (
    has_edits_after_slide_creations as _has_edits_after_slide_creations,
)
from .presentation_save_planning import (
    shape_add_as_chart_add as _shape_add_as_chart_add,
)
from .section_xml import read_sections_from_element
from .slide_payloads import load_slide_payloads
from .slide_zoom_targets import (
    ZoomTargetError,
    presentation_slide_parts,
    reconcile_section_zoom_targets,
    zoom_references,
)

_PRESENTATION_PART = "ppt/presentation.xml"


def _refuse_deleting_slide_zoom_targets(
    current: Path, deleted_parts: Iterable[str]
) -> None:
    """Refuse a deletion that would leave a surviving slide zoom without its target.

    A slide zoom names its target by presentation slide id and links its
    fallback picture to the target part; deleting the target would leave both
    dangling, which PowerPoint renders as a broken zoom and Open XML rejects.
    """
    deleted = {str(part).lstrip("/") for part in deleted_parts}
    with zipfile.ZipFile(current) as package:
        root = ET.fromstring(package.read(_PRESENTATION_PART))
        parts_by_id = presentation_slide_parts(package, root)
        deleted_ids = {str(slide_id) for slide_id, part in parts_by_id.items() if part in deleted}
        survivors = [part for part in parts_by_id.values() if part not in deleted]
        for reference in zoom_references(package, survivors):
            if reference.kind == "slide" and reference.target.strip() in deleted_ids:
                raise ZoomTargetError(
                    f"cannot delete slide id {reference.target.strip()}: slide zoom "
                    f"{reference.name!r} on {reference.slide_part} targets it; delete "
                    "or retarget the zoom first"
                )


def _reconcile_section_zooms_after_deletion(current: Path, step: Path) -> Path:
    """Move section zoom fallbacks onto each section's first surviving slide."""
    with zipfile.ZipFile(current) as package:
        root = ET.fromstring(package.read(_PRESENTATION_PART))
        replacements = reconcile_section_zoom_targets(
            package,
            presentation_slide_parts(package, root),
            [(record.id, record.slide_ids) for record in read_sections_from_element(root)],
        )
    if not replacements:
        return current
    copy_package_with_replacements(current, step, replacements)
    return step


def _animation_timing_reservations(
    edits: Any,
    presentation: Any,
) -> dict[int, int]:
    """Return each slide's highest queued public animation timing ID."""
    part_to_index = {
        str(slide.partname).lstrip("/"): int(slide._index)
        for slide in getattr(presentation, "_slides", ())
        if getattr(slide, "partname", None)
    }
    reservations: dict[int, int] = {}
    for identifier, spec in getattr(edits, "slide_animation_edits", ()):
        if isinstance(identifier, int):
            slide_index = identifier
        elif isinstance(identifier, str):
            slide_index = part_to_index.get(identifier.lstrip("/"))
            if slide_index is None:
                continue
        else:
            continue
        effects = (
            spec.get("added_effects", ())
            if isinstance(spec, dict)
            else getattr(spec, "added_effects", ())
        )
        for effect in effects:
            timing_id = effect.get("timing_id") if isinstance(effect, dict) else None
            if isinstance(timing_id, int) and not isinstance(timing_id, bool):
                reservations[slide_index] = max(
                    reservations.get(slide_index, 0),
                    timing_id,
                )
    return reservations


def apply_slide_and_shape_adds(
    current: Path,
    final_output: Path,
    tmp_dir: Path,
    step_index: int,
    edits: Any,
    ops: PresentationSaveOps,
    presentation: Any = None,
) -> tuple[Path, int]:
    slide_creations_are_final = not _has_edits_after_slide_creations(edits)
    if presentation is not None and (
        edits.slide_deletions or edits.slide_order is not None
    ):
        slide_creations_are_final = False
    last_slide_creation_index = len(edits.slide_creations) - 1
    materialized_parts_by_token: dict[Any, str] = {}
    for creation_index, item in enumerate(edits.slide_creations):
        creation_kind = item[0]
        creation_payload = item[1]
        token = item[2] if len(item) > 2 else None
        step = (
            final_output
            if slide_creations_are_final and creation_index == last_slide_creation_index
            else tmp_dir / f"step-{step_index}.pptx"
        )
        if creation_kind == "blank":
            add_res = ops.native.add_slide(
                current,
                step,
                layout_index=creation_payload.index,
            )
            if token is not None:
                materialized_parts_by_token[token] = add_res.slide_part
        elif creation_kind == "duplicate":
            dup_res = ops.native.duplicate_slide(current, step, creation_payload)
            if token is not None:
                materialized_parts_by_token[token] = dup_res.slide_part
        else:
            raise ValueError(f"unknown slide creation kind: {creation_kind}")
        current = step
        if current != final_output:
            step_index += 1

    if materialized_parts_by_token:
        if presentation is not None:
            presentation._staged_slide_materializations = dict(
                materialized_parts_by_token
            )
        if getattr(edits, "background_fill_solid_edits", None):
            edits.background_fill_solid_edits = [
                materialized_parts_by_token.get(key, key)
                for key in edits.background_fill_solid_edits
            ]
        if getattr(edits, "background_fill_background_edits", None):
            edits.background_fill_background_edits = [
                materialized_parts_by_token.get(key, key)
                for key in edits.background_fill_background_edits
            ]
        if getattr(edits, "background_fill_color_edits", None):
            edits.background_fill_color_edits = [
                (materialized_parts_by_token.get(key, key), val)
                for key, val in edits.background_fill_color_edits
            ]

    # Creation tokens, unlike a pending duplicate's source partname, identify
    # actual new parts. Materialize before deleting so a duplicate may outlive
    # its source, then put survivors in the index space used by queued edits.
    if presentation is not None and (
        edits.slide_deletions or edits.slide_order is not None
    ):
        indexed_slides = sorted(presentation._slides, key=lambda slide: slide._index)
        survivor_parts = [
            materialized_parts_by_token[slide._payload["_creation_token"]]
            if slide._payload.get("_pending_creation")
            else slide.partname
            for slide in indexed_slides
        ]
        if edits.slide_deletions:
            _refuse_deleting_slide_zoom_targets(current, edits.slide_deletions)
            step = tmp_dir / f"step-{step_index}.pptx"
            ops.native.delete_slides(
                current,
                step,
                edits.slide_deletions,
                ordered_survivor_parts=survivor_parts,
            )
            current = step
            step_index += 1
            # A queued section edit reconciles section zooms against its own
            # settled layout; without one, the deletion's layout is final.
            if getattr(edits, "section_edits", None) is None:
                step = tmp_dir / f"step-{step_index}.pptx"
                reconciled = _reconcile_section_zooms_after_deletion(current, step)
                if reconciled != current:
                    current = reconciled
                    step_index += 1
        else:
            current_parts = [
                str(slide["part"]) for slide in load_slide_payloads(current)
            ]
            if current_parts != survivor_parts:
                part_indices = {
                    part: index for index, part in enumerate(current_parts)
                }
                step = tmp_dir / f"step-{step_index}.pptx"
                ops.native.apply_edit_batch(
                    current,
                    step,
                    [{
                        "type": "reorder_slides",
                        "slide_indices": [part_indices[part] for part in survivor_parts],
                    }],
                )
                current = step
                step_index += 1
        slide_order = [slide._index for slide in presentation._slides]
        edits.slide_order = (
            None if slide_order == list(range(len(slide_order))) else slide_order
        )

    shape_adds_are_final = not _has_edits_after_shape_adds(edits)
    animation_timing_reservations = _animation_timing_reservations(
        edits,
        presentation,
    )
    last_shape_add_index = len(edits.shape_adds) - 1
    shape_add_index = 0
    while shape_add_index < len(edits.shape_adds):
        add_kind, args = edits.shape_adds[shape_add_index]
        if add_kind in {"audio", "movie"}:
            minimum_timing_id = animation_timing_reservations.get(args[0], 0)
            if minimum_timing_id:
                args = (*args, minimum_timing_id)
        if add_kind in _CHART_ADD_KINDS:
            batch_last_index = shape_add_index
            chart_adds = [_shape_add_as_chart_add(add_kind, args)]
            while batch_last_index + 1 < len(edits.shape_adds):
                next_kind, next_args = edits.shape_adds[batch_last_index + 1]
                if next_kind not in _CHART_ADD_KINDS:
                    break
                chart_adds.append(_shape_add_as_chart_add(next_kind, next_args))
                batch_last_index += 1
            step = (
                final_output
                if shape_adds_are_final and batch_last_index == last_shape_add_index
                else tmp_dir / f"step-{step_index}.pptx"
            )
            ops._apply_chart_adds(current, step, chart_adds)
            current = step
            if current != final_output:
                step_index += 1
            shape_add_index = batch_last_index + 1
            continue
        step = (
            final_output
            if shape_adds_are_final and shape_add_index == last_shape_add_index
            else tmp_dir / f"step-{step_index}.pptx"
        )
        ops._apply_shape_add(add_kind, args, current, step, ops._apply_chart_add)
        current = step
        if current != final_output:
            step_index += 1
        shape_add_index += 1

    return current, step_index
