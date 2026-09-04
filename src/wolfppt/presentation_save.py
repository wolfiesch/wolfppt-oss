"""Save orchestration for the Python presentation facade."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from .image_inputs import InMemoryImage
from .part_placeholder_edits import (
    apply_part_placeholder_adds as _apply_part_placeholder_adds,
)
from .notes_slide_edits import (
    apply_notes_slide_adds as _apply_notes_slide_adds,
)
from .presentation_input import release_input_snapshot as _release_input_snapshot
from .presentation_save_edits import collect_save_edits as _collect_save_edits
from .presentation_save_adds import (
    apply_slide_and_shape_adds as _apply_slide_and_shape_adds,
)
from .presentation_save_chart_pipeline import (
    apply_chart_save_edits as _apply_chart_save_edits,
)
from .presentation_save_fast_path import (
    apply_simple_package_fast_path as _apply_simple_package_fast_path,
)
from .presentation_save_io import (
    apply_core_properties_edits as _apply_core_properties_edits,
    is_file_like_output as _is_file_like_output,
    write_path_to_file_like as _write_path_to_file_like,
)
from .presentation_save_ops import PresentationSaveOps
from .presentation_save_planning import (
    has_edits_after_native_batch as _has_edits_after_native_batch,
    has_edits_after_slide_deletions as _has_edits_after_slide_deletions,
)
from .presentation_save_payloads import (
    full_slide_payloads_for_save as _full_slide_payloads_for_save,
    slide_part_payloads_for_save as _slide_part_payloads_for_save,
)
from .presentation_save_state import has_pending_save_edits as _has_pending_save_edits
from .slide_layout_edits import (
    apply_slide_layout_removals as _apply_slide_layout_removals,
)


def _apply_picture_replace_edits(
    current: Path,
    step: Path,
    edits: list[tuple[tuple[int, str], Any]],
    ops: PresentationSaveOps,
) -> None:
    working = current
    tmp_dir = step.parent
    for edit_index, ((slide_index, relationship_id), image_path) in enumerate(edits):
        target = (
            step
            if edit_index == len(edits) - 1
            else tmp_dir / f"image-replace-{edit_index}.pptx"
        )
        if isinstance(image_path, InMemoryImage):
            image_path = image_path.materialize(
                tmp_dir,
                f"image-replace-{edit_index}",
            )
        ops.native.replace_image(
            working,
            target,
            relationship_id,
            image_path,
            slide_index=slide_index,
        )
        working = target


def save_presentation(
    self: Any,
    path: Any,
    ops: PresentationSaveOps,
) -> None:
    file_like_output = _is_file_like_output(path)
    output = None if file_like_output else Path(path)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
    previous_source_path = self._source_path

    if not _has_pending_save_edits(self):
        if file_like_output:
            _write_path_to_file_like(self._source_path, path)
        elif output.resolve() != self._source_path.resolve():
            shutil.copy2(self._source_path, output)
        if output is not None:
            self._source_path = output
            _release_input_snapshot(self, previous_source_path)
        return

    edits = _collect_save_edits(self, ops)
    with tempfile.TemporaryDirectory(prefix="wolfppt-save-") as tmp:
        current = self._source_path
        tmp_dir = Path(tmp)
        final_output = output if output is not None else tmp_dir / "output.pptx"
        step_index = 0
        if edits.slide_deletions:
            step = (
                tmp_dir / f"step-{step_index}.pptx"
                if _has_edits_after_slide_deletions(edits)
                else final_output
            )
            survivor_order = [
                s.partname
                for s in self._slides
                if s.partname and s.partname not in edits.slide_deletions
            ]
            ops.native.delete_slides(
                current,
                step,
                edits.slide_deletions,
                ordered_survivor_parts=survivor_order if survivor_order else None,
            )
            current = step
            edits.slide_order = None
            if current != final_output:
                step_index += 1
        current, step_index = _apply_slide_and_shape_adds(
            current,
            final_output,
            tmp_dir,
            step_index,
            edits,
            ops,
        )
        if edits.picture_replace_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_picture_replace_edits(
                current,
                step,
                edits.picture_replace_edits,
                ops,
            )
            current = step
            step_index += 1
        if edits.notes_slide_adds:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_notes_slide_adds(current, step, edits.notes_slide_adds)
            current = step
            step_index += 1
        if edits.part_placeholder_adds:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_part_placeholder_adds(current, step, edits.part_placeholder_adds)
            current = step
            step_index += 1
        current, step_index = _apply_simple_package_fast_path(
            self,
            current,
            final_output,
            tmp_dir,
            step_index,
            edits,
            ops,
        )
        current, step_index = _apply_chart_save_edits(
            self,
            current,
            final_output,
            tmp_dir,
            step_index,
            edits,
            ops,
        )
        native_batch_required = bool(
            edits.shape_deletes
            or edits.group_child_shape_deletes
            or edits.slide_order is not None
            or edits.table_cell_edits
            or edits.table_row_column_edits
            or edits.text_run_edits
            or edits.text_run_bold_edits
            or edits.text_run_italic_edits
            or edits.text_run_underline_edits
            or edits.text_run_font_size_edits
            or edits.text_run_font_name_edits
            or edits.text_run_font_color_edits
            or edits.text_run_appends
            or edits.paragraph_text_edits
            or edits.paragraph_appends
            or edits.text_edits
            or edits.group_child_text_edits
            or edits.group_child_paragraph_text_edits
            or edits.group_child_run_text_edits
            or edits.geometry_edits
            or edits.group_child_geometry_edits
        )
        native_module_available = ops.native.native_available()
        table_cell_merges_in_native_batch = bool(
            edits.table_cell_merge_edits
            and (native_module_available or native_batch_required)
        )
        table_style_in_native_batch = bool(
            edits.table_style_edits and (native_module_available or native_batch_required)
        )
        line_breaks_in_native_batch = bool(
            edits.paragraph_line_break_edits
            and (native_module_available or native_batch_required)
        )
        paragraph_font_xml_edits = [
            edit for edit in edits.paragraph_font_edits
            if isinstance(edit[1].get("color"), dict)
            or isinstance(edit[1].get("fill_type"), dict)
        ]
        paragraph_properties_in_native_batch = bool(
            (
                edits.paragraph_alignment_edits
                or edits.paragraph_level_edits
                or edits.paragraph_spacing_edits
            )
            and (
                native_module_available
                or native_batch_required
                or line_breaks_in_native_batch
            )
        )
        paragraph_font_in_native_batch = bool(
            edits.paragraph_font_edits
            and not paragraph_font_xml_edits
            and (
                native_module_available
                or native_batch_required
                or line_breaks_in_native_batch
                or paragraph_properties_in_native_batch
            )
        )
        text_frame_properties_in_native_batch = bool(
            (
                edits.text_frame_margin_edits
                or edits.text_frame_word_wrap_edits
                or edits.text_frame_vertical_anchor_edits
                or edits.text_frame_auto_size_edits
            )
            and (
                native_module_available
                or native_batch_required
                or line_breaks_in_native_batch
                or paragraph_properties_in_native_batch
                or paragraph_font_in_native_batch
            )
        )
        text_run_font_color_native_edits = [
            edit for edit in edits.text_run_font_color_edits
            if isinstance(edit[1][1], str)
        ]
        text_run_font_color_xml_edits = [
            edit for edit in edits.text_run_font_color_edits
            if not isinstance(edit[1][1], str)
        ]
        batch_edits = ops._native_batch_edits(
            edits.table_cell_edits,
            edits.table_cell_merge_edits if table_cell_merges_in_native_batch else [],
            edits.table_style_edits if table_style_in_native_batch else [],
            edits.text_run_edits,
            edits.text_run_bold_edits,
            edits.text_run_italic_edits,
            edits.text_run_underline_edits,
            edits.text_run_font_size_edits,
            edits.text_run_font_name_edits,
            text_run_font_color_native_edits,
            edits.text_run_appends,
            edits.paragraph_line_break_edits if line_breaks_in_native_batch else [],
            edits.paragraph_text_edits,
            edits.paragraph_appends,
            edits.paragraph_alignment_edits
            if paragraph_properties_in_native_batch
            else [],
            edits.paragraph_level_edits if paragraph_properties_in_native_batch else [],
            edits.paragraph_spacing_edits if paragraph_properties_in_native_batch else [],
            edits.paragraph_font_edits if paragraph_font_in_native_batch else [],
            edits.text_frame_margin_edits
            if text_frame_properties_in_native_batch
            else [],
            edits.text_frame_word_wrap_edits
            if text_frame_properties_in_native_batch
            else [],
            edits.text_frame_vertical_anchor_edits
            if text_frame_properties_in_native_batch
            else [],
            edits.text_frame_auto_size_edits
            if text_frame_properties_in_native_batch
            else [],
            edits.text_edits,
            edits.group_child_text_edits,
            edits.group_child_paragraph_text_edits,
            edits.group_child_run_text_edits,
            edits.geometry_edits,
            edits.group_child_geometry_edits,
            edits.shape_deletes,
            edits.slide_order,
            edits.table_row_column_edits,
            edits.group_child_shape_deletes,
        )
        if batch_edits:
            step = (
                tmp_dir / f"step-{step_index}.pptx"
                if _has_edits_after_native_batch(
                    edits,
                    table_cell_merges_in_native_batch=table_cell_merges_in_native_batch,
                    table_style_in_native_batch=table_style_in_native_batch,
                    line_breaks_in_native_batch=line_breaks_in_native_batch,
                    paragraph_properties_in_native_batch=(
                        paragraph_properties_in_native_batch
                    ),
                    paragraph_font_in_native_batch=paragraph_font_in_native_batch,
                    text_frame_properties_in_native_batch=(
                        text_frame_properties_in_native_batch
                    ),
                    text_run_font_color_xml_edits=bool(
                        text_run_font_color_xml_edits
                    ),
                )
                else final_output
            )
            ops.native.apply_edit_batch(current, step, batch_edits)
            current = step
            if current != final_output:
                step_index += 1
            if line_breaks_in_native_batch:
                edits.paragraph_line_break_edits = []
            if table_cell_merges_in_native_batch:
                edits.table_cell_merge_edits = []
            if table_style_in_native_batch:
                edits.table_style_edits = []
            if paragraph_properties_in_native_batch:
                edits.paragraph_alignment_edits = []
                edits.paragraph_level_edits = []
                edits.paragraph_spacing_edits = []
            if paragraph_font_in_native_batch:
                edits.paragraph_font_edits = []
            if text_frame_properties_in_native_batch:
                edits.text_frame_margin_edits = []
                edits.text_frame_word_wrap_edits = []
                edits.text_frame_vertical_anchor_edits = []
                edits.text_frame_auto_size_edits = []
            edits.table_row_column_edits = []
            edits.group_child_shape_deletes = []
        if text_run_font_color_xml_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_run_font_color_edits(
                current,
                step,
                [
                    (key, color)
                    for key, (_, color) in text_run_font_color_xml_edits
                ],
            )
            current = step
            step_index += 1
        if (
            edits.nested_group_child_geometry_edits
            or edits.deeper_group_child_geometry_edits
        ):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_nested_group_child_geometry_edits(
                current,
                step,
                edits.nested_group_child_geometry_edits,
                edits.deeper_group_child_geometry_edits,
                slide_payloads=_full_slide_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if edits.group_child_run_font_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_text_run_font_edits(
                current,
                step,
                edits.group_child_run_font_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_paragraph_clear_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_paragraph_clear_edits(
                current,
                step,
                edits.group_child_paragraph_clear_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_paragraph_line_break_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_paragraph_line_break_edits(
                current,
                step,
                edits.group_child_paragraph_line_break_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_paragraph_alignment_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_paragraph_alignment_edits(
                current,
                step,
                edits.group_child_paragraph_alignment_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_paragraph_font_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_paragraph_font_edits(
                current,
                step,
                edits.group_child_paragraph_font_edits,
            )
            current = step
            step_index += 1
        group_child_paragraph_property_edit_count = sum(
            bool(edits)
            for edits in (
                edits.group_child_paragraph_level_edits,
                edits.group_child_paragraph_spacing_edits,
            )
        )
        if group_child_paragraph_property_edit_count:
            if edits.group_child_paragraph_level_edits:
                step = tmp_dir / f"step-{step_index}.pptx"
                ops._apply_group_child_paragraph_level_edits(
                    current,
                    step,
                    edits.group_child_paragraph_level_edits,
                )
                current = step
                step_index += 1
            if edits.group_child_paragraph_spacing_edits:
                step = tmp_dir / f"step-{step_index}.pptx"
                ops._apply_group_child_paragraph_spacing_edits(
                    current,
                    step,
                    edits.group_child_paragraph_spacing_edits,
                )
                current = step
                step_index += 1
        if (
            edits.nested_group_child_text_edits
            or edits.deeper_group_child_text_edits
        ):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_nested_group_child_shape_text_edits(
                current,
                step,
                edits.nested_group_child_text_edits,
                edits.deeper_group_child_text_edits,
                slide_payloads=_full_slide_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if (
            edits.part_shape_text_edits
            or edits.part_run_font_edits
            or edits.part_run_hyperlink_edits
            or edits.part_paragraph_font_edits
            or edits.part_paragraph_alignment_edits
            or edits.part_paragraph_level_edits
            or edits.part_paragraph_spacing_edits
        ):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_part_text_edits(
                current,
                step,
                edits.part_shape_text_edits,
                edits.part_run_font_edits,
                edits.part_run_hyperlink_edits,
                edits.part_paragraph_font_edits,
                edits.part_paragraph_alignment_edits,
                edits.part_paragraph_level_edits,
                edits.part_paragraph_spacing_edits,
            )
            current = step
            step_index += 1
        if (
            edits.part_text_frame_margin_edits
            or edits.part_text_frame_word_wrap_edits
            or edits.part_text_frame_vertical_anchor_edits
            or edits.part_text_frame_auto_size_edits
        ):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_part_text_frame_edits(
                current,
                step,
                edits.part_text_frame_margin_edits,
                edits.part_text_frame_word_wrap_edits,
                edits.part_text_frame_vertical_anchor_edits,
                edits.part_text_frame_auto_size_edits,
            )
            current = step
            step_index += 1
        table_cell_property_edit_count = sum(
            bool(edits)
            for edits in (
                edits.table_cell_margin_edits,
                edits.table_cell_vertical_anchor_edits,
                edits.table_cell_text_frame_margin_edits,
                edits.table_cell_text_frame_vertical_anchor_edits,
                edits.table_cell_text_frame_content_edits,
                edits.table_cell_text_frame_word_wrap_edits,
                edits.table_cell_text_frame_auto_size_edits,
                edits.table_cell_text_frame_fit_edits,
                edits.table_cell_text_frame_paragraph_alignment_edits,
                edits.table_cell_text_frame_paragraph_level_edits,
                edits.table_cell_text_frame_paragraph_spacing_edits,
                edits.table_cell_text_frame_paragraph_font_edits,
                edits.table_cell_text_frame_paragraph_run_edits,
                edits.table_cell_text_frame_paragraph_line_break_edits,
                edits.table_cell_text_frame_paragraph_run_font_edits,
                edits.table_cell_text_frame_paragraph_run_hyperlink_edits,
                edits.table_cell_fill_solid_edits,
                edits.table_cell_fill_background_edits,
                edits.table_cell_fill_pattern_edits,
                edits.table_cell_fill_pattern_fore_color_edits,
                edits.table_cell_fill_pattern_back_color_edits,
                edits.table_cell_fill_color_edits,
                edits.table_cell_fill_gradient_edits,
            )
        )
        if edits.table_row_height_edits or edits.table_column_width_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_table_dimension_edits(
                current,
                step,
                edits.table_row_height_edits,
                edits.table_column_width_edits,
            )
            current = step
            step_index += 1
        if table_cell_property_edit_count:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_table_cell_property_edits(
                current,
                step,
                edits.table_cell_margin_edits,
                edits.table_cell_vertical_anchor_edits,
                edits.table_cell_text_frame_margin_edits,
                edits.table_cell_text_frame_vertical_anchor_edits,
                edits.table_cell_text_frame_content_edits,
                edits.table_cell_text_frame_word_wrap_edits,
                edits.table_cell_text_frame_auto_size_edits,
                edits.table_cell_text_frame_fit_edits,
                edits.table_cell_text_frame_paragraph_alignment_edits,
                edits.table_cell_text_frame_paragraph_level_edits,
                edits.table_cell_text_frame_paragraph_spacing_edits,
                edits.table_cell_text_frame_paragraph_font_edits,
                edits.table_cell_text_frame_paragraph_run_edits,
                edits.table_cell_text_frame_paragraph_line_break_edits,
                edits.table_cell_text_frame_paragraph_run_font_edits,
                edits.table_cell_text_frame_paragraph_run_hyperlink_edits,
                edits.table_cell_fill_solid_edits,
                edits.table_cell_fill_background_edits,
                edits.table_cell_fill_pattern_edits,
                edits.table_cell_fill_pattern_fore_color_edits,
                edits.table_cell_fill_pattern_back_color_edits,
                edits.table_cell_fill_color_edits,
                edits.table_cell_fill_gradient_edits,
                slide_payloads=_slide_part_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if (
            edits.background_fill_solid_edits
            or edits.background_fill_background_edits
            or edits.background_fill_color_edits
        ):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_background_fill_edits(
                current,
                step,
                edits.background_fill_solid_edits,
                edits.background_fill_background_edits,
                edits.background_fill_color_edits,
            )
            current = step
            step_index += 1
        if edits.table_cell_merge_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_table_cell_merge_edits(current, step, edits.table_cell_merge_edits)
            current = step
            step_index += 1
        if edits.table_style_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_table_style_edits(current, step, edits.table_style_edits)
            current = step
            step_index += 1
        if edits.paragraph_clear_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_clear_edits(current, step, edits.paragraph_clear_edits)
            current = step
            step_index += 1
        if edits.paragraph_line_break_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_line_break_edits(
                current,
                step,
                edits.paragraph_line_break_edits,
            )
            current = step
            step_index += 1
        paragraph_property_edit_count = sum(
            bool(edits)
            for edits in (
                edits.paragraph_alignment_edits,
                edits.paragraph_level_edits,
                edits.paragraph_spacing_edits,
            )
        )
        if paragraph_property_edit_count > 1:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_property_edits(
                current,
                step,
                edits.paragraph_alignment_edits,
                edits.paragraph_level_edits,
                edits.paragraph_spacing_edits,
            )
            current = step
            step_index += 1
        elif edits.paragraph_alignment_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_alignment_edits(current, step, edits.paragraph_alignment_edits)
            current = step
            step_index += 1
        elif edits.paragraph_level_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_level_edits(current, step, edits.paragraph_level_edits)
            current = step
            step_index += 1
        elif edits.paragraph_spacing_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_spacing_edits(current, step, edits.paragraph_spacing_edits)
            current = step
            step_index += 1
        if edits.paragraph_font_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_font_edits(current, step, edits.paragraph_font_edits)
            current = step
            step_index += 1
        if edits.text_frame_margin_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_frame_margin_edits(current, step, edits.text_frame_margin_edits)
            current = step
            step_index += 1
        if edits.text_frame_word_wrap_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_frame_word_wrap_edits(current, step, edits.text_frame_word_wrap_edits)
            current = step
            step_index += 1
        if edits.text_frame_vertical_anchor_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_frame_vertical_anchor_edits(
                current,
                step,
                edits.text_frame_vertical_anchor_edits,
            )
            current = step
            step_index += 1
        if edits.text_frame_auto_size_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_frame_auto_size_edits(
                current,
                step,
                edits.text_frame_auto_size_edits,
            )
            current = step
            step_index += 1
        if edits.text_frame_fit_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_frame_fit_edits(current, step, edits.text_frame_fit_edits)
            current = step
            step_index += 1
        if edits.group_child_text_frame_margin_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_text_frame_margin_edits(
                current,
                step,
                edits.group_child_text_frame_margin_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_text_frame_word_wrap_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_text_frame_word_wrap_edits(
                current,
                step,
                edits.group_child_text_frame_word_wrap_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_text_frame_vertical_anchor_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_text_frame_vertical_anchor_edits(
                current,
                step,
                edits.group_child_text_frame_vertical_anchor_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_text_frame_auto_size_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_text_frame_auto_size_edits(
                current,
                step,
                edits.group_child_text_frame_auto_size_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_text_frame_fit_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_text_frame_fit_edits(
                current,
                step,
                edits.group_child_text_frame_fit_edits,
            )
            current = step
            step_index += 1
        if edits.text_run_font_fill_type_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_run_font_fill_type_edits(
                current,
                step,
                edits.text_run_font_fill_type_edits,
            )
            current = step
            step_index += 1
        if edits.text_run_font_language_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_run_font_language_edits(
                current,
                step,
                edits.text_run_font_language_edits,
            )
            current = step
            step_index += 1
        if edits.text_run_hyperlink_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_run_hyperlink_edits(
                current,
                step,
                edits.text_run_hyperlink_edits,
                slide_payloads=_full_slide_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if edits.part_shape_hyperlink_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_part_shape_hyperlink_edits(
                current,
                step,
                edits.part_shape_hyperlink_edits,
            )
            current = step
            step_index += 1
        if edits.group_child_run_hyperlink_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_group_child_text_run_hyperlink_edits(
                current,
                step,
                edits.group_child_run_hyperlink_edits,
            )
            current = step
            step_index += 1
        style_edits = ops._shape_style_edits(
            edits.fill_solid_edits,
            edits.fill_background_edits,
            edits.fill_pattern_edits,
            edits.fill_pattern_fore_color_edits,
            edits.fill_pattern_back_color_edits,
            edits.fill_color_edits,
            edits.fill_gradient_edits,
            edits.line_solid_edits,
            edits.line_background_edits,
            edits.line_pattern_edits,
            edits.line_pattern_fore_color_edits,
            edits.line_pattern_back_color_edits,
            edits.line_color_edits,
            edits.line_width_edits,
            edits.line_dash_edits,
            edits.shadow_inherit_edits,
        )
        if style_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_style_edits(
                current,
                step,
                style_edits,
                slide_payloads=_full_slide_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if edits.connector_connection_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_connector_connection_edits(
                current,
                step,
                edits.connector_connection_edits,
            )
            current = step
            step_index += 1
        if edits.hyperlink_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_hyperlink_edits(current, step, edits.hyperlink_edits)
            current = step
            step_index += 1
        if edits.target_slide_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_target_slide_edits(current, step, edits.target_slide_edits)
            current = step
            step_index += 1
        if edits.rotation_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_rotation_edits(current, step, edits.rotation_edits)
            current = step
            step_index += 1
        if edits.name_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_name_edits(
                current,
                step,
                edits.name_edits,
                slide_payloads=_full_slide_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if edits.adjustment_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_adjustment_edits(current, step, edits.adjustment_edits)
            current = step
            step_index += 1
        if edits.line_element_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_line_element_edits(current, step, edits.line_element_edits)
            current = step
            step_index += 1
        if edits.picture_crop_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_picture_crop_edits(current, step, edits.picture_crop_edits)
            current = step
            step_index += 1
        if edits.slide_name_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_slide_name_edits(current, step, edits.slide_name_edits)
            current = step
            step_index += 1
        if edits.presentation_size_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_presentation_size_edits(current, step, edits.presentation_size_edits)
            current = step
            step_index += 1
        if edits.core_properties_edits is not None:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_core_properties_edits(current, step, edits.core_properties_edits)
            current = step
            step_index += 1
        if edits.slide_layout_removals:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_slide_layout_removals(current, step, edits.slide_layout_removals)
            current = step
            step_index += 1
        if current != final_output:
            shutil.copy2(current, final_output)
        if file_like_output:
            _write_path_to_file_like(final_output, path)
            return

    self._clear_pending_edits()
    for slide_index, slide in enumerate(self._slides):
        slide._rebase_live_indices(slide_index)
    self._source_path = output
    _release_input_snapshot(self, previous_source_path)
