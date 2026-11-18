"""Save orchestration for the Python presentation facade."""

from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .comment_edits import (
    apply_legacy_comment_edits as _apply_legacy_comment_edits,
)
from .comment_edits import (
    has_pending_comment_edits as _has_pending_comment_edits,
)
from .comment_edits import (
    pending_comment_edits as _pending_comment_edits,
)
from .comment_edits import (
    reset_comment_state as _reset_comment_state,
)
from .custom_shows import (
    apply_custom_show_edits as _apply_custom_show_edits,
)
from .editions import commercial_module
from .handout_master_edits import (
    apply_handout_master_add as _apply_handout_master_add,
)
from .image_inputs import InMemoryImage
from .notes_slide_edits import (
    apply_notes_slide_adds as _apply_notes_slide_adds,
)
from .package_parts import InMemoryPackageSource
from .part_placeholder_edits import (
    apply_part_placeholder_adds as _apply_part_placeholder_adds,
)
from .presentation_formats import (
    BINARY_PPT_SUFFIXES,
    SPLIT_OOXML_SUFFIXES,
    main_content_type_differs,
    retarget_main_content_type,
)
from .presentation_input import release_input_snapshot as _release_input_snapshot
from .presentation_save_adds import (
    apply_slide_and_shape_adds as _apply_slide_and_shape_adds,
)
from .presentation_save_chart_pipeline import (
    apply_chart_save_edits as _apply_chart_save_edits,
)
from .presentation_save_edits import collect_save_edits as _collect_save_edits
from .presentation_save_edits import (
    resolve_shape_edit_references as _resolve_shape_edit_references,
)
from .presentation_save_fast_path import (
    apply_simple_package_fast_path as _apply_simple_package_fast_path,
)
from .presentation_save_io import (
    apply_core_properties_edits as _apply_core_properties_edits,
)
from .presentation_save_io import (
    is_file_like_output as _is_file_like_output,
)
from .presentation_save_io import (
    publish_staged_output as _publish_staged_output,
)
from .presentation_save_ops import PresentationSaveOps
from .presentation_save_payloads import (
    full_slide_payloads_for_save as _full_slide_payloads_for_save,
)
from .presentation_save_payloads import (
    slide_part_payloads_for_save as _slide_part_payloads_for_save,
)
from .presentation_save_planning import (
    has_edits_after_native_batch as _has_edits_after_native_batch,
)
from .presentation_save_state import (
    acknowledge_lifecycle_edits,
    apply_lifecycle_edits,
    materialize_saved_owners,
    prepare_saved_owners,
    snapshot_lifecycle_edits,
)
from .presentation_save_state import has_pending_save_edits as _has_pending_save_edits
from .slide_edits import _apply_group_text_edits
from .slide_layout_edits import (
    apply_slide_layout_edits as _apply_slide_layout_edits,
)
from .slide_layout_edits import (
    apply_slide_layout_removals as _apply_slide_layout_removals,
)
from .slide_master_facade import (
    apply_slide_master_authoring as _apply_slide_master_authoring,
)
from .slide_payloads import load_slide_payloads as _load_slide_payloads
from .text_facade_queue import (
    resolve_queued_run_format_indices as _resolve_queued_run_format_indices,
)


def _apply_picture_replace_edits(
    current: Path,
    step: Path,
    edits: list[tuple[tuple[int, str], Any]],
) -> None:
    from .picture_image_edits import apply_picture_image_replace

    working = current
    tmp_dir = step.parent
    for edit_index, ((slide_index, shape_id), image_path) in enumerate(edits):
        target = (
            step if edit_index == len(edits) - 1 else tmp_dir / f"image-replace-{edit_index}.pptx"
        )
        if isinstance(image_path, InMemoryImage):
            image_path = image_path.materialize(
                tmp_dir,
                f"image-replace-{edit_index}",
            )
        apply_picture_image_replace(working, target, slide_index, shape_id, image_path)
        working = target


def _resolve_notes_slide_adds(
    presentation: Any,
    adds: list[tuple[int, str, str]],
) -> list[tuple[int, str, str]]:
    """Resolve pending slide parts after their creation has been staged."""
    staged = getattr(presentation, "_staged_slide_materializations", {})
    resolved: list[tuple[int, str, str]] = []
    for slide_index, slide_part, notes_part in adds:
        slide = next(
            (slide for slide in presentation._slides if slide._index == slide_index),
            None,
        )
        token = None if slide is None else slide._payload.get("_creation_token")
        if token is not None:
            slide_part = staged.get(token, "")
        if not slide_part:
            raise ValueError("notes slide source part is unavailable")
        resolved.append((slide_index, slide_part, notes_part))
    return resolved


def _media_playback_shape_id(
    slide_payloads: list[dict[str, Any]],
    slide_index: int,
    shape_ref: int | tuple[int, ...],
) -> int:
    try:
        shapes = slide_payloads[slide_index]["shapes"]
        if isinstance(shape_ref, tuple):
            shape_payload = shapes[shape_ref[0]]
            for child_index in shape_ref[1:]:
                shape_payload = shape_payload["children"][child_index]
        else:
            shape_payload = shapes[shape_ref]
    except (IndexError, KeyError, TypeError) as exc:
        raise IndexError("media playback shape reference is out of range") from exc
    try:
        return int(shape_payload["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("media playback shape payload is missing an id") from exc


def _apply_media_playback_edits(
    current: Path,
    step: Path,
    playback_edits: list[
        tuple[
            tuple[int, int | tuple[int, ...]],
            tuple[bool, bool, int, bool, dict[str, Any]],
        ]
    ],
    ops: PresentationSaveOps,
) -> None:
    slide_payloads = _load_slide_payloads(current)
    working = current
    for edit_index, ((slide_index, shape_ref), playback) in enumerate(playback_edits):
        target = (
            step
            if edit_index == len(playback_edits) - 1
            else step.parent / f"media-playback-{edit_index}.pptx"
        )
        shape_id = _media_playback_shape_id(slide_payloads, slide_index, shape_ref)
        ops.native.set_media_playback(
            working,
            target,
            slide_index,
            shape_id,
            *playback,
        )
        working = target


def _publish_stream(candidate: Path, output: Any) -> None:
    with candidate.open("rb") as source:
        while chunk := source.read(65536):
            _publish_bytes(chunk, output)


def _publish_bytes(data: bytes, output: Any) -> None:
    for offset in range(0, len(data), 65536):
        chunk = data[offset : offset + 65536]
        written = output.write(chunk)
        if written is not None and written != len(chunk):
            raise OSError("presentation stream did not accept the complete package")


def _in_memory_package_bytes(source: InMemoryPackageSource) -> bytes:
    return source.read_bytes()


def _publish_in_memory_package(
    data: bytes, path: Any, output: Path | None, destination: Path | None
) -> None:
    """Publish owned package bytes; streams receive them without staging."""
    if output is None or destination is None:
        _publish_bytes(data, path)
        return
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}.",
        dir=destination.parent,
    ) as tmp:
        candidate = Path(tmp) / "output.pptx"
        candidate.write_bytes(data)
        _publish_staged_output(candidate, destination)


def _needs_retarget(source: Any, suffix: str) -> bool:
    if isinstance(source, InMemoryPackageSource):
        return main_content_type_differs(io.BytesIO(source.read_bytes()), suffix)
    return main_content_type_differs(source, suffix)


def _save_transaction(
    self: Any,
    path: Any,
    ops: PresentationSaveOps,
) -> None:
    file_like_output = _is_file_like_output(path)
    output = None if file_like_output else Path(path)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
    destination = output.resolve() if output is not None else None
    previous_source_path = self._source_path
    in_memory_source = (
        previous_source_path if isinstance(previous_source_path, InMemoryPackageSource) else None
    )
    suffix = output.suffix.casefold() if output is not None else ""
    odp_output = suffix == ".odp"
    binary_output = suffix in BINARY_PPT_SUFFIXES
    ooxml_output = output is not None and not odp_output and not binary_output
    # A save that leaves the source's family (presentation, slideshow,
    # template) needs a new main content type even without other edits.
    family_change = ooxml_output and _needs_retarget(previous_source_path, suffix)
    # Slideshow/template suffixes also encode the macro state, so an edited
    # package saved to one is rechecked. Other OOXML saves keep the source
    # content type and are not reopened.
    retarget_output = family_change or (ooxml_output and suffix in SPLIT_OOXML_SUFFIXES)
    lifecycle = snapshot_lifecycle_edits(self)
    vba_modules = tuple(self._pending_vba_modules)
    vba_removal = self._pending_vba_removal
    web_extensions = tuple(self._pending_web_extensions)
    package_edits = bool(vba_modules or vba_removal or web_extensions)

    if (
        not _has_pending_save_edits(self)
        and not _has_pending_comment_edits(self)
        and not package_edits
        and not odp_output
        and not binary_output
        and not family_change
    ):
        if in_memory_source is not None:
            # No-disk inputs stay in memory; the caller's target only receives bytes.
            _publish_in_memory_package(
                _in_memory_package_bytes(in_memory_source), path, output, destination
            )
        elif file_like_output:
            _publish_stream(self._source_path, path)
        elif destination != self._source_path.resolve():
            with tempfile.TemporaryDirectory(
                prefix=f".{output.name}.",
                dir=destination.parent,
            ) as tmp:
                candidate = Path(tmp) / "output.pptx"
                shutil.copy2(self._source_path, candidate)
                _publish_staged_output(candidate, destination)
        if output is not None and in_memory_source is None:
            self._source_path = output
            _release_input_snapshot(self, previous_source_path)
        return

    edits = _collect_save_edits(self, ops)
    _resolve_queued_run_format_indices(self, edits)
    staging_directory = destination.parent if destination is not None else None
    staging_prefix = f".{output.name}." if output is not None else "wolfppt-save-"
    with tempfile.TemporaryDirectory(
        prefix=staging_prefix,
        dir=staging_directory,
    ) as tmp:
        tmp_dir = Path(tmp)
        if in_memory_source is not None:
            # Native edit steps are path-based, so stage the owned snapshot in
            # the same transient directory every edited save already uses.
            current = tmp_dir / "source.pptx"
            current.write_bytes(_in_memory_package_bytes(in_memory_source))
        else:
            current = self._source_path
        final_output = tmp_dir / "output.pptx"
        step_index = 0
        if edits.slide_master_authoring_requests:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_slide_master_authoring(
                current,
                step,
                edits.slide_master_authoring_requests,
            )
            current = step
            step_index += 1
        current, step_index = _apply_slide_and_shape_adds(
            current,
            final_output,
            tmp_dir,
            step_index,
            edits,
            ops,
            presentation=self,
        )
        _resolve_shape_edit_references(edits, current)
        if edits.nested_group_child_text_edits or edits.deeper_group_child_text_edits:
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
        if edits.connector_connection_edits and (
            edits.shape_deletes or edits.group_child_shape_deletes or edits.slide_order is not None
        ):
            # Resolve attachments in the pre-delete/pre-reorder index space.
            # Native deletion then detaches exactly the removed subtree IDs,
            # retaining queued coordinates and surviving endpoint references.
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_connector_connection_edits(current, step, edits.connector_connection_edits)
            current = step
            step_index += 1
            edits.connector_connection_edits = []
        if getattr(edits, "slide_animation_edits", None):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_slide_animation_edits(current, step, edits.slide_animation_edits)
            current = step
            step_index += 1
        if edits.media_playback_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_media_playback_edits(
                current,
                step,
                edits.media_playback_edits,
                ops,
            )
            current = step
            step_index += 1
        if edits.picture_replace_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_picture_replace_edits(
                current,
                step,
                edits.picture_replace_edits,
            )
            current = step
            step_index += 1
        if edits.notes_slide_adds:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_notes_slide_adds(
                current,
                step,
                _resolve_notes_slide_adds(self, edits.notes_slide_adds),
            )
            current = step
            step_index += 1
        if edits.handout_master_partname is not None:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_handout_master_add(current, step, edits.handout_master_partname)
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
            or edits.text_run_strike_edits
            or edits.text_run_font_size_edits
            or edits.text_run_font_name_edits
            or edits.text_run_font_color_edits
            or edits.text_run_appends
            or edits.paragraph_text_edits
            or edits.paragraph_appends
            or edits.text_edits
            or edits.group_child_text_edits
            or edits.geometry_edits
            or edits.group_child_geometry_edits
        )
        native_module_available = ops.native.native_available()
        table_cell_merges_in_native_batch = bool(
            edits.table_cell_merge_edits and (native_module_available or native_batch_required)
        )
        table_style_in_native_batch = bool(
            edits.table_style_edits
            and not any("tableStyleId" in flags for _, flags in edits.table_style_edits)
            and (native_module_available or native_batch_required)
        )
        line_breaks_in_native_batch = bool(
            edits.paragraph_line_break_edits and (native_module_available or native_batch_required)
        )
        paragraph_font_xml_edits = [
            edit
            for edit in edits.paragraph_font_edits
            if isinstance(edit[1].get("color"), dict) or isinstance(edit[1].get("fill_type"), dict)
        ]
        paragraph_properties_in_native_batch = bool(
            (
                edits.paragraph_alignment_edits
                or edits.paragraph_level_edits
                or edits.paragraph_spacing_edits
            )
            and all(
                set(spacing).issubset({"line_spacing", "space_before", "space_after"})
                for _, spacing in edits.paragraph_spacing_edits
            )
            and (native_module_available or native_batch_required or line_breaks_in_native_batch)
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
            edit for edit in edits.text_run_font_color_edits if isinstance(edit[1][1], str)
        ]
        text_run_font_color_xml_edits = [
            edit for edit in edits.text_run_font_color_edits if not isinstance(edit[1][1], str)
        ]
        batch_edits = ops._native_batch_edits(
            edits.table_cell_edits,
            edits.table_cell_merge_edits if table_cell_merges_in_native_batch else [],
            edits.table_style_edits if table_style_in_native_batch else [],
            edits.text_run_edits,
            edits.text_run_bold_edits,
            edits.text_run_italic_edits,
            edits.text_run_underline_edits,
            edits.text_run_strike_edits,
            edits.text_run_font_size_edits,
            edits.text_run_font_name_edits,
            text_run_font_color_native_edits,
            edits.text_run_appends,
            edits.paragraph_line_break_edits if line_breaks_in_native_batch else [],
            edits.paragraph_text_edits,
            edits.paragraph_appends,
            edits.paragraph_alignment_edits if paragraph_properties_in_native_batch else [],
            edits.paragraph_level_edits if paragraph_properties_in_native_batch else [],
            edits.paragraph_spacing_edits if paragraph_properties_in_native_batch else [],
            edits.paragraph_font_edits if paragraph_font_in_native_batch else [],
            edits.text_frame_margin_edits if text_frame_properties_in_native_batch else [],
            edits.text_frame_word_wrap_edits if text_frame_properties_in_native_batch else [],
            edits.text_frame_vertical_anchor_edits if text_frame_properties_in_native_batch else [],
            edits.text_frame_auto_size_edits if text_frame_properties_in_native_batch else [],
            edits.text_edits,
            edits.group_child_text_edits,
            [],
            [],
            edits.geometry_edits,
            edits.group_child_geometry_edits,
            edits.shape_deletes,
            None,  # Reorder only after all original-index edits have been applied.
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
                    paragraph_properties_in_native_batch=(paragraph_properties_in_native_batch),
                    paragraph_font_in_native_batch=paragraph_font_in_native_batch,
                    text_frame_properties_in_native_batch=(text_frame_properties_in_native_batch),
                    text_run_font_color_xml_edits=bool(text_run_font_color_xml_edits),
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
        if getattr(self, "_zoom_edits", None):
            from .zoom_frames import apply_queued_zoom_edits

            step = tmp_dir / f"step-{step_index}.pptx"
            apply_queued_zoom_edits(self, current, step)
            current = step
            step_index += 1
        if text_run_font_color_xml_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_run_font_color_edits(
                current,
                step,
                [(key, color) for key, (_, color) in text_run_font_color_xml_edits],
            )
            current = step
            step_index += 1
        if edits.nested_group_child_geometry_edits or edits.deeper_group_child_geometry_edits:
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
        if edits.part_geometry_edits:
            from .slide_edits import _apply_part_shape_geometry_edits

            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_part_shape_geometry_edits(current, step, edits.part_geometry_edits)
            current = step
            step_index += 1
        for operation in (
            "paragraph_clear",
            "paragraph_text",
            "run_text",
            "run_font",
            "paragraph_line_break",
            "paragraph_alignment",
            "paragraph_font",
            "paragraph_level",
            "paragraph_spacing",
            "paragraph_bullet",
        ):
            records = getattr(edits, f"group_child_{operation}_edits")
            if records:
                step = tmp_dir / f"step-{step_index}.pptx"
                _apply_group_text_edits(
                    current,
                    step,
                    records,
                    operation,
                    slide_payloads=edits.group_text_slide_payloads,
                )
                current = step
                step_index += 1
        if (
            edits.part_shape_text_edits
            or edits.part_paragraph_text_edits
            or edits.part_paragraph_clear_edits
            or edits.part_paragraph_line_break_edits
            or edits.part_run_text_edits
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
                edits.part_paragraph_text_edits,
                edits.part_paragraph_clear_edits,
                edits.part_paragraph_line_break_edits,
                edits.part_run_text_edits,
                edits.part_run_font_edits,
                edits.part_run_hyperlink_edits,
                edits.part_paragraph_font_edits,
                edits.part_paragraph_alignment_edits,
                edits.part_paragraph_level_edits,
                edits.part_paragraph_spacing_edits,
            )
            current = step
            step_index += 1
        if edits.part_paragraph_bullet_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_part_paragraph_bullet_edits(
                current,
                step,
                edits.part_paragraph_bullet_edits,
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
        if edits.table_cell_border_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_table_cell_border_edits(
                current,
                step,
                edits.table_cell_border_edits,
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
        if getattr(edits, "table_style_id_edits", None):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_table_style_id_edits(current, step, edits.table_style_id_edits)
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
        if edits.paragraph_bullet_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_bullet_edits(current, step, edits.paragraph_bullet_edits)
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
        for operation in (
            "text_frame_margin",
            "text_frame_word_wrap",
            "text_frame_vertical_anchor",
            "text_frame_auto_size",
            "text_frame_fit",
        ):
            records = getattr(edits, f"group_child_{operation}_edits")
            if records:
                step = tmp_dir / f"step-{step_index}.pptx"
                _apply_group_text_edits(
                    current,
                    step,
                    records,
                    operation,
                    slide_payloads=edits.group_text_slide_payloads,
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
            _apply_group_text_edits(
                current,
                step,
                edits.group_child_run_hyperlink_edits,
                "run_hyperlink",
                slide_payloads=edits.group_text_slide_payloads,
            )
            current = step
            step_index += 1
        if edits.text_run_advanced_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_run_advanced_edits(current, step, edits.text_run_advanced_edits)
            current = step
            step_index += 1
        if edits.text_frame_advanced_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_text_frame_advanced_edits(current, step, edits.text_frame_advanced_edits)
            current = step
            step_index += 1
        if edits.paragraph_tab_stop_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_paragraph_tab_stop_edits(current, step, edits.paragraph_tab_stop_edits)
            current = step
            step_index += 1
        if edits.group_child_text_frame_advanced_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_group_text_edits(
                current,
                step,
                edits.group_child_text_frame_advanced_edits,
                "text_frame_advanced",
                slide_payloads=edits.group_text_slide_payloads,
            )
            current = step
            step_index += 1
        if edits.part_text_frame_advanced_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_part_text_frame_advanced_edits(
                current, step, edits.part_text_frame_advanced_edits
            )
            current = step
            step_index += 1
        if edits.group_child_paragraph_tab_stop_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_group_text_edits(
                current,
                step,
                edits.group_child_paragraph_tab_stop_edits,
                "paragraph_tab_stop",
                slide_payloads=edits.group_text_slide_payloads,
            )
            current = step
            step_index += 1
        if edits.part_paragraph_tab_stop_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_part_paragraph_tab_stop_edits(
                current, step, edits.part_paragraph_tab_stop_edits
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
        if edits.shape_line_end_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_line_end_edits(
                current,
                step,
                edits.shape_line_end_edits,
                slide_payloads=_full_slide_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if edits.shape_effect_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_effect_edits(
                current,
                step,
                edits.shape_effect_edits,
                slide_payloads=_full_slide_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if getattr(edits, "shape_glow_edits", None):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_glow_edits(
                current,
                step,
                edits.shape_glow_edits,
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
            ops._apply_shape_rotation_edits(
                current,
                step,
                edits.rotation_edits,
                slide_payloads=edits.rotation_slide_payloads,
            )
            current = step
            step_index += 1
        if getattr(edits, "shape_flip_edits", None):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_flip_edits(
                current,
                step,
                edits.shape_flip_edits,
            )
            current = step
            step_index += 1
        if getattr(edits, "shape_lock_edits", None):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_lock_edits(
                current,
                step,
                edits.shape_lock_edits,
            )
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
        # After adjustments: the new preset keeps only the adjust guides it declares.
        if edits.shape_preset_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_preset_edits(current, step, edits.shape_preset_edits)
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
        if edits.picture_recolor_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_picture_recolor_edits(current, step, edits.picture_recolor_edits)
            current = step
            step_index += 1
        if getattr(edits, "picture_transparency_edits", None):
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_picture_transparency_edits(current, step, edits.picture_transparency_edits)
            current = step
            step_index += 1
        if edits.picture_correction_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_picture_correction_edits(current, step, edits.picture_correction_edits)
            current = step
            step_index += 1
        if edits.shape_z_order_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_shape_z_order_edits(
                current,
                step,
                edits.shape_z_order_edits,
                slide_payloads=_full_slide_payloads_for_save(self, edits),
            )
            current = step
            step_index += 1
        if edits.slide_name_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            staged = getattr(self, "_staged_slide_materializations", {})
            resolved_name_edits = [
                (staged.get(target, target), name) for target, name in edits.slide_name_edits
            ]
            ops._apply_slide_name_edits(current, step, resolved_name_edits)
            current = step
            step_index += 1
        if getattr(edits, "slide_hidden_edits", None):
            step = tmp_dir / f"step-{step_index}.pptx"
            apply_hidden = getattr(ops, "_apply_slide_hidden_edits", None)
            if apply_hidden is None:
                from .slide_edits import _apply_slide_hidden_edits as apply_hidden
            staged = getattr(self, "_staged_slide_materializations", {})
            resolved_hidden_edits = [
                (staged.get(target, target), hidden) for target, hidden in edits.slide_hidden_edits
            ]
            apply_hidden(current, step, resolved_hidden_edits)
            current = step
            step_index += 1
        if edits.slide_transition_edits:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_slide_transition_edits(current, step, edits.slide_transition_edits)
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
        if edits.custom_properties_edits is not None:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_custom_properties_edits(current, step, edits.custom_properties_edits)
            current = step
            step_index += 1
        if getattr(edits, "extended_properties_edits", None) is not None:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_extended_properties_edits(current, step, edits.extended_properties_edits)
            current = step
            step_index += 1
        if getattr(edits, "slide_layout_changes", None):
            step = tmp_dir / f"step-{step_index}.pptx"
            apply_layout_fn = (
                getattr(ops, "_apply_slide_layout_edits", None) or _apply_slide_layout_edits
            )
            apply_layout_fn(
                current,
                step,
                edits.slide_layout_changes,
            )
            current = step
            step_index += 1
        if edits.slide_layout_removals:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_slide_layout_removals(current, step, edits.slide_layout_removals)
            current = step
            step_index += 1
        if _has_pending_comment_edits(self):
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_legacy_comment_edits(
                current,
                step,
                _pending_comment_edits(self),
                deleted_slide_parts=edits.slide_deletions,
            )
            current = step
            step_index += 1
        if edits.custom_show_edits is not None or edits.slide_deletions:
            step = tmp_dir / f"step-{step_index}.pptx"
            _apply_custom_show_edits(
                current,
                step,
                edits.custom_show_edits,
                getattr(self, "_staged_slide_materializations", {}),
            )
            current = step
            step_index += 1
        if package_edits:
            from .package_parts import (
                add_standard_vba_module,
                add_web_extensions,
                remove_vba_project,
            )

            if vba_removal:
                step = tmp_dir / "stripped.pptx"
                remove_vba_project(current, step)
                current = step
            for index, (name, source) in enumerate(vba_modules):
                step = tmp_dir / f"macro-{index}.pptm"
                add_standard_vba_module(current, step, name, source)
                current = step
            if web_extensions:
                step = tmp_dir / "web-extensions.pptx"
                add_web_extensions(current, step, list(web_extensions))
                current = step
        if edits.slide_order is not None:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops.native.apply_edit_batch(
                current,
                step,
                [{"type": "reorder_slides", "slide_indices": edits.slide_order}],
            )
            current = step
            step_index += 1
        if getattr(edits, "section_edits", None) is not None:
            step = tmp_dir / f"step-{step_index}.pptx"
            ops._apply_section_edits(current, step, edits.section_edits)
            current = step
            step_index += 1
        identities, owner_plans = prepare_saved_owners(self, current)
        receipt = None
        if lifecycle.tags or lifecycle.view is not None or lifecycle.fields:
            step = tmp_dir / "lifecycle.pptx"
            receipt = apply_lifecycle_edits(
                current,
                step,
                lifecycle,
                staged_slide_parts=getattr(self, "_staged_slide_materializations", {}),
                resolve_owner=lambda ref: identities.get(ref.owner),
            )
            current = step
        if current != final_output:
            shutil.copy2(current, final_output)
        if retarget_output:
            retarget_main_content_type(final_output, suffix)
        candidate = final_output
        if odp_output:
            odp = commercial_module("odp", "Saving as ODP")
            candidate = tmp_dir / "output.odp"
            odp.save_pptx_as_odp(final_output, candidate)
        elif binary_output:
            candidate = tmp_dir / "output.ppt"
            binary_ppt = commercial_module("binary_ppt", "Saving as binary PowerPoint")
            binary_ppt.save_pptx_as_binary_ppt(final_output, candidate)

        # Prepare a durable PPTX baseline before touching an external stream or
        # publishing an ODP. No fallible package copy remains after publication.
        baseline_dir = None
        saved_package = None
        if in_memory_source is not None:
            saved_package = InMemoryPackageSource(final_output.read_bytes())
            if file_like_output:
                _publish_stream(candidate, path)
            else:
                _publish_staged_output(candidate, destination)
        elif file_like_output or odp_output or binary_output:
            baseline_dir = tempfile.TemporaryDirectory(prefix="wolfppt-saved-")
            baseline = Path(baseline_dir.name) / "presentation.pptx"
            try:
                shutil.copy2(final_output, baseline)
                if file_like_output:
                    _publish_stream(candidate, path)
                else:
                    _publish_staged_output(candidate, destination)
            except BaseException:
                baseline_dir.cleanup()
                raise
        else:
            _publish_staged_output(candidate, destination)

        materialize_saved_owners(identities, owner_plans)
        self._clear_pending_edits()
        _reset_comment_state(self)
        for slide_index, slide in enumerate(self._slides):
            slide._rebase_live_indices(slide_index)
        if saved_package is not None:
            # Keep the no-disk contract: the new baseline is owned bytes, not
            # the caller's destination file or a retained temporary copy.
            self._source_path = saved_package
        elif baseline_dir is not None:
            old_baseline = self._source_tempdir
            self._source_path = baseline
            self._source_tempdir = baseline_dir
            if old_baseline is not None:
                old_baseline.cleanup()
        else:
            self._source_path = output
            _release_input_snapshot(self, previous_source_path)
        self._slide_metadata = None
        if receipt is not None:
            acknowledge_lifecycle_edits(self, receipt)
        # Collections inspected while owners were authored also need their
        # persisted identity, even when they had no edits in this snapshot.
        from .presentation_tags import OwnerRef

        collections = list(self._lifecycle_tags.values())
        if self._lifecycle_fields is not None:
            collections.extend(self._lifecycle_fields._collections.values())
        for collection in collections:
            if collection._ref.owner in identities:
                collection._ref = OwnerRef.capture(self, collection._ref.owner)
        if tuple(self._pending_vba_modules[: len(vba_modules)]) == vba_modules:
            del self._pending_vba_modules[: len(vba_modules)]
        if vba_removal:
            self._pending_vba_removal = False
        if tuple(self._pending_web_extensions[: len(web_extensions)]) == web_extensions:
            del self._pending_web_extensions[: len(web_extensions)]
        if self._web_extensions is not None and web_extensions:
            self._web_extensions._mark_saved()


def save_presentation(self: Any, path: Any, ops: PresentationSaveOps) -> None:
    """Stage and publish once; never carry materialization maps across retries."""
    if getattr(self, "_save_in_progress", False):
        raise RuntimeError("presentation save is already in progress")
    from .zoom_frames import validate_queued_zoom_edits

    validate_queued_zoom_edits(self)
    self._save_in_progress = True
    self.__dict__.pop("_staged_slide_materializations", None)
    try:
        _save_transaction(self, path, ops)
    finally:
        self.__dict__.pop("_staged_slide_materializations", None)
        self._save_in_progress = False
