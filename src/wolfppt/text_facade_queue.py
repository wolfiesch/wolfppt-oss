"""Queue-routing helpers for text facade mutations."""

from __future__ import annotations

from typing import Any

from .shape_payloads import (
    _shape_paragraph_run_matrix,
    _shape_paragraph_runs,
    _shape_paragraphs,
)


def _shape_run_index(shape: Any, paragraph_index: int, run_index: int) -> int:
    payload = getattr(shape, "_payload", None)
    if isinstance(payload, dict):
        offsets = payload.get("_paragraph_run_offsets")
        if offsets is not None and paragraph_index < len(offsets):
            return shape._run_start_index + offsets[paragraph_index] + run_index
        paragraph_runs = _shape_paragraph_run_matrix(shape)
        offsets = []
        total = 0
        for runs in paragraph_runs:
            offsets.append(total)
            total += len(runs)
        payload["_paragraph_run_offsets"] = offsets
        if paragraph_index < len(offsets):
            return shape._run_start_index + offsets[paragraph_index] + run_index
    paragraph_runs = _shape_paragraph_run_matrix(shape)
    preceding = sum(len(runs) for runs in paragraph_runs[:paragraph_index])
    return shape._run_start_index + preceding + run_index

def _shape_paragraph_text(shape: Any, paragraph_index: int) -> str:
    return _shape_paragraphs(shape)[paragraph_index]


def _is_appended_paragraph(shape: Any, paragraph_index: int) -> bool:
    return paragraph_index >= shape._existing_paragraph_count


def _is_appended_run(shape: Any, paragraph_index: int, run_index: int) -> bool:
    if _is_appended_paragraph(shape, paragraph_index):
        return True
    if paragraph_index >= len(shape._existing_run_counts):
        return True
    return run_index >= shape._existing_run_counts[paragraph_index]


def _is_part_scoped_text_shape(shape: Any) -> bool:
    return bool(getattr(shape._slide, "_is_notes_slide", False))


def _is_group_child_text_shape(shape: Any) -> bool:
    return bool(shape._payload.get("_group_child"))


def _group_child_key(shape: Any) -> tuple[int, int, int]:
    return (
        shape._slide._index,
        _group_child_shape_index(shape),
        int(shape._payload["_group_child_index"]),
    )


def _group_child_shape_index(shape: Any) -> int:
    return int(
        shape._payload.get(
            "_group_shape_index",
            shape._payload["_group_index"],
        )
    )


def _is_pending_group_child_text_shape(shape: Any) -> bool:
    return bool(shape._payload.get("_pending_group_child"))


def _queue_pending_group_child_text(shape: Any) -> None:
    if shape._payload.get("_deep_nested_group_child"):
        queue_method = (
            shape._slide._presentation._queue_deeper_nested_group_auto_shape_text
            if shape._payload.get("_pending_group_child_kind") == "auto_shape"
            else shape._slide._presentation._queue_deeper_nested_group_text_box_text
        )
        queue_method(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_nested_group_child_index"]),
            int(shape._payload["_deeper_group_child_index"]),
            int(shape._payload["_group_child_index"]),
            shape.text,
        )
        return
    if shape._payload.get("_nested_group_child"):
        queue_method = (
            shape._slide._presentation._queue_nested_group_auto_shape_text
            if shape._payload.get("_pending_group_child_kind") == "auto_shape"
            else shape._slide._presentation._queue_nested_group_text_box_text
        )
        queue_method(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_nested_group_child_index"]),
            int(shape._payload["_group_child_index"]),
            shape.text,
        )
        return
    queue_method = (
        shape._slide._presentation._queue_group_auto_shape_text
        if shape._payload.get("_pending_group_child_kind") == "auto_shape"
        else shape._slide._presentation._queue_group_text_box_text
    )
    queue_method(
        shape._slide._index,
        int(shape._payload["_group_index"]),
        int(shape._payload["_group_child_index"]),
        shape.text,
    )


def _queue_part_scoped_shape_text(shape: Any) -> None:
    shape._slide._presentation._queue_shape_text_for_shape(shape, shape.text)


def _raise_if_part_scoped_text_formatting(shape: Any, feature: str) -> None:
    if _is_part_scoped_text_shape(shape):
        raise AttributeError(f"{feature} editing is unavailable for notes text frames")


def _queue_group_child_run_font_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    attr: str,
    value: Any,
) -> None:
    shape._slide._presentation._queue_group_child_run_font(
        shape._slide._index,
        int(shape._payload["_group_index"]),
        int(shape._payload["_group_child_index"]),
        paragraph_index,
        run_index,
        attr,
        value,
    )


def _queue_part_run_font_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    attr: str,
    value: Any,
) -> None:
    shape._slide._presentation._queue_part_run_font(
        shape._slide.partname,
        shape._index,
        paragraph_index,
        run_index,
        attr,
        value,
    )


def _queue_paragraph_state(shape: Any, paragraph_index: int) -> None:
    if _is_pending_group_child_text_shape(shape):
        _queue_pending_group_child_text(shape)
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_paragraph_text(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            _shape_paragraph_text(shape, paragraph_index),
        )
        return
    if _is_part_scoped_text_shape(shape):
        _queue_part_scoped_shape_text(shape)
        return
    presentation = shape._slide._presentation
    slide_index = shape._slide._index
    shape_index = shape._index
    text = _shape_paragraph_text(shape, paragraph_index)
    if (slide_index, shape_index) in presentation._shape_text_edits:
        presentation._queue_shape_text(slide_index, shape_index, shape.text)
    elif _is_appended_paragraph(shape, paragraph_index):
        presentation._queue_paragraph_append(
            slide_index, shape_index, paragraph_index, text
        )
    else:
        presentation._queue_paragraph_text(
            slide_index, shape_index, paragraph_index, text
        )


def _queue_run_state(shape: Any, paragraph_index: int, run_index: int) -> None:
    if _is_pending_group_child_text_shape(shape):
        _queue_pending_group_child_text(shape)
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_run_text(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            run_index,
            _shape_paragraph_runs(shape)[paragraph_index][run_index],
        )
        return
    if _is_part_scoped_text_shape(shape):
        _queue_part_scoped_shape_text(shape)
        return
    presentation = shape._slide._presentation
    slide_index = shape._slide._index
    shape_index = shape._index
    paragraph_key = (slide_index, shape_index, paragraph_index)
    if (slide_index, shape_index) in presentation._shape_text_edits:
        presentation._queue_shape_text(slide_index, shape_index, shape.text)
    elif paragraph_key in presentation._paragraph_text_edits:
        presentation._queue_paragraph_text(
            slide_index,
            shape_index,
            paragraph_index,
            _shape_paragraph_text(shape, paragraph_index),
        )
    elif paragraph_key in presentation._paragraph_appends:
        presentation._queue_paragraph_append(
            slide_index,
            shape_index,
            paragraph_index,
            _shape_paragraph_text(shape, paragraph_index),
        )
    elif _is_appended_run(shape, paragraph_index, run_index):
        presentation._queue_text_run_append(
            slide_index,
            shape_index,
            paragraph_index,
            run_index,
            _shape_paragraph_runs(shape)[paragraph_index][run_index],
        )
    else:
        presentation._queue_text_run(
            slide_index,
            shape_index,
            paragraph_index,
            _shape_run_index(shape, paragraph_index, run_index),
            _shape_paragraph_runs(shape)[paragraph_index][run_index],
        )


def _queue_run_bold_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    bold: bool | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(shape, paragraph_index, run_index, "bold", bold)
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape, paragraph_index, run_index, "bold", bold
        )
        return
    shape._slide._presentation._queue_text_run_bold(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _shape_run_index(shape, paragraph_index, run_index),
        bold,
    )


def _queue_run_italic_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    italic: bool | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(shape, paragraph_index, run_index, "italic", italic)
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape,
            paragraph_index,
            run_index,
            "italic",
            italic,
        )
        return
    shape._slide._presentation._queue_text_run_italic(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _shape_run_index(shape, paragraph_index, run_index),
        italic,
    )


def _queue_run_underline_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    underline: bool | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(
            shape, paragraph_index, run_index, "underline", underline
        )
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape,
            paragraph_index,
            run_index,
            "underline",
            underline,
        )
        return
    shape._slide._presentation._queue_text_run_underline(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _shape_run_index(shape, paragraph_index, run_index),
        underline,
    )


def _queue_run_font_size_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    size: int | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(shape, paragraph_index, run_index, "size", size)
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape, paragraph_index, run_index, "size", size
        )
        return
    shape._slide._presentation._queue_text_run_font_size(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _shape_run_index(shape, paragraph_index, run_index),
        size,
    )


def _queue_run_font_name_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    name: str | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(shape, paragraph_index, run_index, "name", name)
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape, paragraph_index, run_index, "name", name
        )
        return
    shape._slide._presentation._queue_text_run_font_name(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _shape_run_index(shape, paragraph_index, run_index),
        name,
    )


def _queue_run_font_color_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    color: Any,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(shape, paragraph_index, run_index, "color", color)
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape, paragraph_index, run_index, "color", color
        )
        return
    shape._slide._presentation._queue_text_run_font_color(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _shape_run_index(shape, paragraph_index, run_index),
        color,
    )


def _queue_run_font_fill_type_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    fill_type: Any,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(
            shape,
            paragraph_index,
            run_index,
            "fill_type",
            fill_type,
        )
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape,
            paragraph_index,
            run_index,
            "fill_type",
            fill_type,
        )
        return
    shape._slide._presentation._queue_text_run_font_fill_type(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        fill_type,
    )


def _queue_run_font_language_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    value: str | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(
            shape,
            paragraph_index,
            run_index,
            "language_id",
            value,
        )
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape,
            paragraph_index,
            run_index,
            "language_id",
            value,
        )
        return
    shape._slide._presentation._queue_text_run_font_language(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        value,
    )


def _queue_paragraph_alignment_state(
    shape: Any,
    paragraph_index: int,
    alignment: str | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        shape._slide._presentation._queue_part_paragraph_alignment(
            shape._slide.partname,
            shape._index,
            paragraph_index,
            alignment,
        )
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_paragraph_alignment(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            alignment,
        )
        return
    shape._slide._presentation._queue_paragraph_alignment(
        shape._slide._index,
        shape._index,
        paragraph_index,
        alignment,
    )


def _queue_paragraph_clear_state(shape: Any, paragraph_index: int) -> None:
    if _is_pending_group_child_text_shape(shape):
        _queue_pending_group_child_text(shape)
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_paragraph_clear(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
        )
        return
    if _is_part_scoped_text_shape(shape):
        _queue_part_scoped_shape_text(shape)
        return
    shape._slide._presentation._queue_paragraph_clear(
        shape._slide._index,
        shape._index,
        paragraph_index,
    )


def _queue_paragraph_line_break_state(
    shape: Any,
    paragraph_index: int,
    run_slot: int,
) -> None:
    if _is_pending_group_child_text_shape(shape):
        _queue_pending_group_child_text(shape)
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_paragraph_line_break(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            run_slot,
        )
        return
    if _is_part_scoped_text_shape(shape):
        _queue_part_scoped_shape_text(shape)
        return
    shape._slide._presentation._queue_paragraph_line_break(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_slot,
    )


def _queue_paragraph_level_state(
    shape: Any,
    paragraph_index: int,
    level: int,
) -> None:
    if _is_part_scoped_text_shape(shape):
        shape._slide._presentation._queue_part_paragraph_level(
            shape._slide.partname,
            shape._index,
            paragraph_index,
            level,
        )
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_paragraph_level(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            level,
        )
        return
    shape._slide._presentation._queue_paragraph_level(
        shape._slide._index,
        shape._index,
        paragraph_index,
        level,
    )


def _queue_paragraph_spacing_state(
    shape: Any,
    paragraph_index: int,
    attr: str,
    value: int | float | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        shape._slide._presentation._queue_part_paragraph_spacing(
            shape._slide.partname,
            shape._index,
            paragraph_index,
            attr,
            value,
        )
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_paragraph_spacing(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            attr,
            value,
        )
        return
    shape._slide._presentation._queue_paragraph_spacing(
        shape._slide._index,
        shape._index,
        paragraph_index,
        attr,
        value,
    )


def _queue_paragraph_font_state(
    shape: Any,
    paragraph_index: int,
    attr: str,
    value: Any,
) -> None:
    if _is_part_scoped_text_shape(shape):
        shape._slide._presentation._queue_part_paragraph_font(
            shape._slide.partname,
            shape._index,
            paragraph_index,
            attr,
            value,
        )
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_paragraph_font(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            attr,
            value,
        )
        return
    shape._slide._presentation._queue_paragraph_font(
        shape._slide._index,
        shape._index,
        paragraph_index,
        attr,
        value,
    )
