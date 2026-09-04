"""Slide and shape-add pipeline for presentation saves."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .presentation_save_ops import PresentationSaveOps
from .presentation_save_planning import (
    CHART_ADD_KINDS as _CHART_ADD_KINDS,
    has_edits_after_shape_adds as _has_edits_after_shape_adds,
    has_edits_after_slide_creations as _has_edits_after_slide_creations,
    shape_add_as_chart_add as _shape_add_as_chart_add,
)


def apply_slide_and_shape_adds(
    current: Path,
    final_output: Path,
    tmp_dir: Path,
    step_index: int,
    edits: Any,
    ops: PresentationSaveOps,
) -> tuple[Path, int]:
    slide_creations_are_final = not _has_edits_after_slide_creations(edits)
    last_slide_creation_index = len(edits.slide_creations) - 1
    for creation_index, item in enumerate(
        edits.slide_creations
    ):
        creation_kind = item[0]
        creation_payload = item[1]
        step = (
            final_output
            if slide_creations_are_final
            and creation_index == last_slide_creation_index
            else tmp_dir / f"step-{step_index}.pptx"
        )
        if creation_kind == "blank":
            ops.native.add_slide(
                current,
                step,
                layout_index=creation_payload.index,
            )
        elif creation_kind == "duplicate":
            ops.native.duplicate_slide(current, step, creation_payload)
        else:
            raise ValueError(f"unknown slide creation kind: {creation_kind}")
        current = step
        if current != final_output:
            step_index += 1

    shape_adds_are_final = not _has_edits_after_shape_adds(edits)
    last_shape_add_index = len(edits.shape_adds) - 1
    shape_add_index = 0
    while shape_add_index < len(edits.shape_adds):
        add_kind, args = edits.shape_adds[shape_add_index]
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
