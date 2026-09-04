"""Chart-related save steps for the Python presentation facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .presentation_save_ops import PresentationSaveOps
from .presentation_save_payloads import full_slide_payloads_for_save


def apply_chart_save_edits(
    owner: Any,
    current: Path,
    final_output: Path,
    tmp_dir: Path,
    step_index: int,
    edits: Any,
    ops: PresentationSaveOps,
) -> tuple[Path, int]:
    for chart_index, ((slide_index, shape_index), chart_data) in enumerate(
        edits.chart_data_edits
    ):
        step = tmp_dir / f"step-{step_index}.pptx"
        extra_replacements = None
        if (
            edits.part_shape_text_edits
            and chart_index == len(edits.chart_data_edits) - 1
        ):
            extra_replacements = ops._part_shape_text_replacements(
                current,
                edits.part_shape_text_edits,
            )
        ops._apply_chart_data_replace(
            current,
            step,
            slide_index,
            shape_index,
            chart_data,
            extra_replacements=extra_replacements,
        )
        current = step
        step_index += 1
        if extra_replacements:
            edits.part_shape_text_edits = []
    if edits.chart_title_edits:
        step = tmp_dir / f"step-{step_index}.pptx"
        ops._apply_chart_title_edits(current, step, edits.chart_title_edits)
        current = step
        step_index += 1
    if edits.chart_legend_edits:
        step = tmp_dir / f"step-{step_index}.pptx"
        ops._apply_chart_legend_edits(current, step, edits.chart_legend_edits)
        current = step
        step_index += 1
    if edits.chart_font_edits:
        step = tmp_dir / f"step-{step_index}.pptx"
        ops._apply_chart_font_edits(current, step, edits.chart_font_edits)
        current = step
        step_index += 1
    if edits.chart_data_label_edits:
        step = tmp_dir / f"step-{step_index}.pptx"
        ops._apply_chart_data_label_edits(
            current,
            step,
            edits.chart_data_label_edits,
        )
        current = step
        step_index += 1
    if edits.chart_plot_property_edits:
        step = tmp_dir / f"step-{step_index}.pptx"
        ops._apply_chart_plot_property_edits(
            current,
            step,
            edits.chart_plot_property_edits,
        )
        current = step
        step_index += 1
    if edits.chart_axis_title_edits:
        step = tmp_dir / f"step-{step_index}.pptx"
        ops._apply_chart_axis_title_edits(
            current,
            step,
            edits.chart_axis_title_edits,
            slide_payloads=full_slide_payloads_for_save(owner, edits),
        )
        current = step
        step_index += 1
    if edits.chart_axis_property_edits:
        step = tmp_dir / f"step-{step_index}.pptx"
        ops._apply_chart_axis_property_edits(
            current,
            step,
            edits.chart_axis_property_edits,
        )
        current = step
        step_index += 1
    if edits.chart_style_edits:
        step = tmp_dir / f"step-{step_index}.pptx"
        ops._apply_chart_style_edits(
            current,
            step,
            edits.chart_style_edits,
            slide_payloads=full_slide_payloads_for_save(owner, edits),
        )
        current = step
        step_index += 1
    return current, step_index
