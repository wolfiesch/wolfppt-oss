"""Queue-routing helpers for text facade mutations."""

from __future__ import annotations

from typing import Any

from .shape_edit_refs import ShapeEditRef, shape_edit_ref
from .shape_payloads import (
    _normalize_paragraph_line_breaks,
    _shape_paragraph_line_breaks,
    _shape_paragraph_run_matrix,
    _shape_paragraph_runs,
    _shape_paragraphs,
)
from .text_facade_xml_inspection import _shape_run_count_payload

# Slide-global run-format queues keyed by (slide_index, slide_run_index) whose
# values start with the (shape_index, paragraph_index, run_index) they target.
_RUN_FORMAT_QUEUES = (
    "text_run_bold_edits",
    "text_run_italic_edits",
    "text_run_underline_edits",
    "text_run_strike_edits",
    "text_run_font_size_edits",
    "text_run_font_name_edits",
)


def _shape_run_index(shape: Any, paragraph_index: int, run_index: int) -> int:
    paragraph_runs = _shape_paragraph_run_matrix(shape)
    paragraph_offset = sum(len(paragraph_runs[index]) for index in range(paragraph_index))
    return _shape_run_start_index(shape) + paragraph_offset + run_index


def _is_pending_shape(shape: Any) -> bool:
    payload = getattr(shape, "_payload", None)
    return isinstance(payload, dict) and bool(payload.get("_pending_shape"))


def _shape_run_start_index(shape: Any) -> int:
    """Slide-global index of the shape's first run once queued text edits land.

    Runs added to or removed from earlier shapes shift every later run, so the
    start is summed from live run counts. A queued delete of an earlier shape
    hides its runs from the live collection; the load-time start is kept then.
    """
    shapes = getattr(shape._slide, "_shapes", None)
    if shapes is None:
        return shape._run_start_index
    if _is_pending_shape(shape):
        preceding_runs = 0
        for candidate in shapes:
            if candidate is shape:
                return preceding_runs
            preceding_runs += sum(len(runs) for runs in _shape_paragraph_run_matrix(candidate))
        return shape._run_start_index
    preceding_runs = 0
    preceding_shapes = 0
    for candidate in shapes:
        if candidate._index < shape._index and not _is_pending_shape(candidate):
            preceding_runs += _shape_run_count_payload(candidate._payload)
            preceding_shapes += 1
    if preceding_shapes != shape._index:
        return shape._run_start_index
    return preceding_runs


def _live_slide_shape(presentation: Any, slide_index: int, shape_index: Any) -> Any:
    for slide in getattr(presentation, "_slides", None) or ():
        if getattr(slide, "_index", None) != slide_index:
            continue
        for shape in getattr(slide, "_shapes", None) or ():
            if shape._index == shape_index:
                return shape
        return None
    return None


def _resolved_slide_run_index(
    presentation: Any,
    slide_index: int,
    target: tuple[Any, int, int],
    queued_run_index: int,
) -> int:
    """Re-derive a queued run's slide-global index from its shape-local address.

    Keeps the queued index when the shape or run is no longer live, so an
    unresolvable entry behaves exactly as it was queued.
    """
    shape_index, paragraph_index, run_index = target
    shape = _live_slide_shape(presentation, slide_index, shape_index)
    if shape is None:
        return queued_run_index
    paragraph_runs = _shape_paragraph_run_matrix(shape)
    if paragraph_index >= len(paragraph_runs) or run_index >= len(paragraph_runs[paragraph_index]):
        return queued_run_index
    return _shape_run_index(shape, paragraph_index, run_index)


def _resolved_run_format_items(
    presentation: Any, items: list[tuple[tuple[int, int], tuple[Any, ...]]]
) -> dict[tuple[int, int], tuple[Any, ...]]:
    # Entries that now name the same run merge in queue order, so the later
    # setter wins exactly as it would on a live run.
    resolved: dict[tuple[int, int], tuple[Any, ...]] = {}
    for (slide_index, slide_run_index), value in items:
        key = (
            slide_index,
            _resolved_slide_run_index(presentation, slide_index, tuple(value[:3]), slide_run_index),
        )
        resolved[key] = value
    return resolved


def resolve_queued_run_format_indices(presentation: Any, edits: Any) -> None:
    """Point slide-global run formatting at each run's final save position.

    Keys were computed when the setter ran; a later ``add_run`` or text edit in
    an earlier paragraph or shape moves the target run, so re-derive every key
    from the stored (shape, paragraph, run) address against the live layout.
    """
    for name in _RUN_FORMAT_QUEUES:
        setattr(
            edits,
            name,
            list(_resolved_run_format_items(presentation, getattr(edits, name)).items()),
        )
    edits.text_run_font_color_edits = [
        (
            key,
            (
                _resolved_slide_run_index(presentation, key[0], key[1:], run_index),
                color,
            ),
        )
        for key, (run_index, color) in edits.text_run_font_color_edits
    ]


def _format_run_index(shape: Any, queue_name: str, paragraph_index: int, run_index: int) -> int:
    """Return the run's current slide-global key for one run-format queue.

    Keys queued before a later run insertion still name the old position. When
    one collides with this run, re-resolve that queue first so the new entry
    cannot overwrite formatting meant for a different run.
    """
    presentation = shape._slide._presentation
    slide_index = shape._slide._index
    slide_run_index = _shape_run_index(shape, paragraph_index, run_index)
    queue = getattr(presentation, f"_{queue_name}")
    queued = queue.get((slide_index, slide_run_index))
    if queued is not None and tuple(queued[:3]) != (
        shape._index,
        paragraph_index,
        run_index,
    ):
        resolved = _resolved_run_format_items(presentation, list(queue.items()))
        queue.clear()
        queue.update(resolved)
    return slide_run_index


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


def _group_child_key(shape: Any) -> tuple[int, ShapeEditRef, int]:
    return (
        shape._slide._index,
        _group_child_shape_index(shape),
        int(shape._payload["_group_child_index"]),
    )


def _group_child_shape_index(shape: Any) -> tuple[int, ...]:
    """Keep the shared parent path, including a one-item direct-group path."""
    return shape_edit_ref(shape)[:-1]


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


def _queue_pending_shape_text(shape: Any) -> None:
    """Re-queue whole-shape replacement with separate runs and soft breaks.

    Whole-shape text is a native XML text payload, so it cannot contain a raw
    vertical tab. Replay every break as a structural edit after appending the
    runs, preserving their indices for queued formatting and hyperlinks.
    """
    paragraph_runs = _shape_paragraph_runs(shape)
    line_breaks = _normalize_paragraph_line_breaks(
        shape._payload.get("paragraph_line_breaks"), len(paragraph_runs)
    )
    paragraphs: list[str] = []
    appended_runs: list[tuple[int, int, str]] = []
    for paragraph_index, runs in enumerate(paragraph_runs):
        paragraphs.append(runs[0] if runs else "")
        appended_runs.extend(
            (paragraph_index, run_index, runs[run_index]) for run_index in range(1, len(runs))
        )
    presentation = shape._slide._presentation
    presentation._queue_shape_text_with_appended_runs(
        shape._slide._index, shape._index, "\n".join(paragraphs), appended_runs
    )
    presentation._paragraph_line_break_edits.extend(
        (shape._slide._index, shape._index, paragraph_index, slot)
        for paragraph_index, slots in enumerate(line_breaks)
        for slot in slots
    )


def _queue_pending_paragraph_text(shape: Any, paragraph_index: int) -> None:
    """Re-queue pending paragraph text, keeping later runs separate.

    The paragraph writer leaves one run holding the replacement; every later
    run is replayed as its own appended run, so run formatting, hyperlinks, and
    queued line breaks keep addressing the run they were set on.
    """
    presentation = shape._slide._presentation
    paragraph_key = (shape._slide._index, shape._index, paragraph_index)
    runs = _shape_paragraph_runs(shape)[paragraph_index]
    presentation._paragraph_text_edits[paragraph_key] = runs[0] if runs else ""
    for key in list(presentation._text_run_appends):
        if key[:3] == paragraph_key:
            del presentation._text_run_appends[key]
    for run_index in range(1, len(runs)):
        presentation._text_run_appends[(*paragraph_key, run_index)] = runs[run_index]


def _queue_pending_paragraph_append(shape: Any, paragraph_index: int) -> None:
    """Re-queue an appended paragraph as its first run, later runs and breaks.

    The paragraph append writer emits one run; every later run is replayed as
    its own appended run and every soft break as a structural edit, so run
    formatting addresses the run it was set on and no vertical tab reaches a:t.
    """
    presentation = shape._slide._presentation
    paragraph_key = (shape._slide._index, shape._index, paragraph_index)
    runs = _shape_paragraph_runs(shape)[paragraph_index]
    presentation._queue_paragraph_append(*paragraph_key, runs[0] if runs else "")
    for run_index in range(1, len(runs)):
        presentation._text_run_appends[(*paragraph_key, run_index)] = runs[run_index]
    presentation._remove_paragraph_line_break_edits(*paragraph_key)
    for run_slot in _shape_paragraph_line_breaks(shape)[paragraph_index]:
        presentation._queue_paragraph_line_break(*paragraph_key, run_slot)


def _retire_paragraph_run_payload(shape: Any, paragraph_index: int) -> None:
    """Retire cached properties only for the runs replaced in this paragraph.

    Replacing a paragraph's text leaves one plain run, as python-pptx does; a
    run added afterward must not inherit the old properties at its index.
    """
    for name, values in shape._payload.items():
        if (
            name.startswith("paragraph_run_")
            and isinstance(values, list)
            and paragraph_index < len(values)
        ):
            values[paragraph_index] = []
    from .shape_payloads import _invalidate_shape_text_cache

    _invalidate_shape_text_cache(shape)


def _replace_slide_paragraph_runs(shape: Any, paragraph_index: int) -> None:
    """Forget every queued run edit addressed to a slide paragraph being replaced.

    ``p.text`` and ``p.clear()`` remove the paragraph's runs, so hyperlinks and
    advanced run properties queued on them must not land on the runs that
    replace them.
    """
    _retire_paragraph_run_payload(shape, paragraph_index)
    presentation = shape._slide._presentation
    paragraph_key = (shape._slide._index, shape._index, paragraph_index)
    for queue in (
        presentation._text_run_hyperlink_edits,
        presentation._text_run_advanced_edits,
    ):
        for key in [key for key in queue if key[:3] == paragraph_key]:
            del queue[key]


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
        _group_child_shape_index(shape),
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
            _group_child_shape_index(shape),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            _shape_paragraph_text(shape, paragraph_index),
        )
        return
    if _is_part_scoped_text_shape(shape):
        _retire_paragraph_run_payload(shape, paragraph_index)
        shape._slide._presentation._queue_part_paragraph_text(
            shape._slide.partname,
            shape._index,
            paragraph_index,
            _shape_paragraph_text(shape, paragraph_index),
        )
        return
    _replace_slide_paragraph_runs(shape, paragraph_index)
    presentation = shape._slide._presentation
    slide_index = shape._slide._index
    shape_index = shape._index
    text = _shape_paragraph_text(shape, paragraph_index)
    if (slide_index, shape_index) in presentation._shape_text_edits:
        _queue_pending_shape_text(shape)
    elif _is_appended_paragraph(shape, paragraph_index):
        _queue_pending_paragraph_append(shape, paragraph_index)
    else:
        presentation._queue_paragraph_text(slide_index, shape_index, paragraph_index, text)


def _queue_run_state(shape: Any, paragraph_index: int, run_index: int) -> None:
    if _is_pending_group_child_text_shape(shape):
        _queue_pending_group_child_text(shape)
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_run_text(
            shape._slide._index,
            _group_child_shape_index(shape),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            run_index,
            _shape_paragraph_runs(shape)[paragraph_index][run_index],
        )
        return
    if _is_part_scoped_text_shape(shape):
        shape._slide._presentation._queue_part_run_text(
            shape._slide.partname,
            shape._index,
            paragraph_index,
            run_index,
            _shape_paragraph_runs(shape)[paragraph_index][run_index],
        )
        return
    presentation = shape._slide._presentation
    slide_index = shape._slide._index
    shape_index = shape._index
    paragraph_key = (slide_index, shape_index, paragraph_index)
    if (slide_index, shape_index) in presentation._shape_text_edits:
        _queue_pending_shape_text(shape)
    elif paragraph_key in presentation._paragraph_text_edits:
        _queue_pending_paragraph_text(shape, paragraph_index)
    elif paragraph_key in presentation._paragraph_clear_edits:
        # The clear runs after the native batch and would drop this run;
        # paragraph text clears the same content before the run lands.
        presentation._paragraph_clear_edits.discard(paragraph_key)
        _queue_pending_paragraph_text(shape, paragraph_index)
    elif paragraph_key in presentation._paragraph_appends:
        _queue_pending_paragraph_append(shape, paragraph_index)
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
        _queue_group_child_run_font_state(shape, paragraph_index, run_index, "bold", bold)
        return
    shape._slide._presentation._queue_text_run_bold(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _format_run_index(shape, "text_run_bold_edits", paragraph_index, run_index),
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
        _format_run_index(shape, "text_run_italic_edits", paragraph_index, run_index),
        italic,
    )


def _queue_run_underline_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    underline: bool | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(shape, paragraph_index, run_index, "underline", underline)
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
        _format_run_index(shape, "text_run_underline_edits", paragraph_index, run_index),
        underline,
    )


def _queue_run_strike_state(
    shape: Any,
    paragraph_index: int,
    run_index: int,
    strike: bool | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        _queue_part_run_font_state(shape, paragraph_index, run_index, "strike", strike)
        return
    if _is_group_child_text_shape(shape):
        _queue_group_child_run_font_state(
            shape,
            paragraph_index,
            run_index,
            "strike",
            strike,
        )
        return
    shape._slide._presentation._queue_text_run_strike(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _format_run_index(shape, "text_run_strike_edits", paragraph_index, run_index),
        strike,
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
        _queue_group_child_run_font_state(shape, paragraph_index, run_index, "size", size)
        return
    shape._slide._presentation._queue_text_run_font_size(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _format_run_index(shape, "text_run_font_size_edits", paragraph_index, run_index),
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
        _queue_group_child_run_font_state(shape, paragraph_index, run_index, "name", name)
        return
    shape._slide._presentation._queue_text_run_font_name(
        shape._slide._index,
        shape._index,
        paragraph_index,
        run_index,
        _format_run_index(shape, "text_run_font_name_edits", paragraph_index, run_index),
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
        _queue_group_child_run_font_state(shape, paragraph_index, run_index, "color", color)
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
            _group_child_shape_index(shape),
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
            _group_child_shape_index(shape),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
        )
        return
    if _is_part_scoped_text_shape(shape):
        _retire_paragraph_run_payload(shape, paragraph_index)
        shape._slide._presentation._queue_part_paragraph_clear(
            shape._slide.partname, shape._index, paragraph_index
        )
        return
    _replace_slide_paragraph_runs(shape, paragraph_index)
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
            _group_child_shape_index(shape),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            run_slot,
        )
        return
    if _is_part_scoped_text_shape(shape):
        shape._slide._presentation._queue_part_paragraph_line_break(
            shape._slide.partname, shape._index, paragraph_index, run_slot
        )
        return
    if (shape._slide._index, shape._index) in shape._slide._presentation._shape_text_edits:
        _queue_pending_shape_text(shape)
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
            _group_child_shape_index(shape),
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
    value: float | str | None,
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
            _group_child_shape_index(shape),
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
            _group_child_shape_index(shape),
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


def _queue_paragraph_bullet_state(
    shape: Any,
    paragraph_index: int,
    bullet: dict[str, Any] | None,
) -> None:
    if _is_part_scoped_text_shape(shape):
        shape._slide._presentation._queue_part_paragraph_bullet(
            shape._slide.partname,
            shape._index,
            paragraph_index,
            bullet,
        )
        return
    if _is_group_child_text_shape(shape):
        shape._slide._presentation._queue_group_child_paragraph_bullet(
            shape._slide._index,
            _group_child_shape_index(shape),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            bullet,
        )
        return
    shape._slide._presentation._queue_paragraph_bullet(
        shape._slide._index,
        shape._index,
        paragraph_index,
        bullet,
    )
