"""Shape text and geometry payload normalizers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .facade_values import LANGUAGE_ID_NONE as _LANGUAGE_ID_NONE

if TYPE_CHECKING:
    from .shape_core_facade import Shape

def _shape_paragraph_runs(shape: Shape) -> list[list[str]]:
    raw_runs = shape._payload.get("paragraph_runs")
    if raw_runs is None:
        raw_paragraphs = list(shape._payload.get("paragraphs", []))
        paragraph_runs = []
        paragraph_line_breaks = []
        for paragraph in raw_paragraphs:
            runs, line_breaks = _paragraph_runs_and_line_breaks(str(paragraph))
            paragraph_runs.append(runs)
            paragraph_line_breaks.append(line_breaks)
        if "paragraph_line_breaks" not in shape._payload:
            shape._payload["paragraph_line_breaks"] = paragraph_line_breaks
    else:
        paragraph_runs = [
            [str(run) for run in paragraph]
            for paragraph in raw_runs
        ]
    return _sync_shape_text_from_paragraph_runs(shape, paragraph_runs)

def _invalidate_shape_text_cache(shape: Any) -> None:
    payload = getattr(shape, "_payload", None)
    if not isinstance(payload, dict):
        return
    payload.pop("_paragraph_runs_normalized", None)
    payload.pop("_paragraph_runs_token", None)
    payload.pop("_paragraph_run_offsets", None)
    payload.pop("_normalized_run_keys", None)


def _shape_paragraph_run_matrix(shape: Shape) -> list[list[str]]:
    raw_runs = shape._payload.get("paragraph_runs")
    if raw_runs is None:
        return _shape_paragraph_runs(shape)
    token = shape._payload.get("_paragraph_runs_token")
    if (
        token is not None
        and shape._payload.get("_paragraph_runs_normalized") is True
        and isinstance(raw_runs, list)
        and token == (id(raw_runs), tuple(len(p) for p in raw_runs if isinstance(p, list)))
    ):
        return raw_runs
    _invalidate_shape_text_cache(shape)
    if (
        isinstance(raw_runs, list)
        and all(isinstance(paragraph, list) for paragraph in raw_runs)
        and all(
            isinstance(run, str)
            for paragraph in raw_runs
            for run in paragraph
        )
    ):
        paragraph_runs = raw_runs
    else:
        paragraph_runs = [
            [str(run) for run in paragraph]
            for paragraph in raw_runs
        ]
        shape._payload["paragraph_runs"] = paragraph_runs
    shape._payload["_paragraph_runs_normalized"] = True
    shape._payload["_paragraph_runs_token"] = (
        id(paragraph_runs),
        tuple(len(p) for p in paragraph_runs),
    )
    return paragraph_runs
def _shape_paragraph_line_breaks(shape: Shape) -> list[list[int]]:
    _shape_paragraph_runs(shape)
    raw_line_breaks = shape._payload.get("paragraph_line_breaks") or []
    paragraph_count = len(shape._payload.get("paragraph_runs", []))
    normalized: list[list[int]] = []
    for paragraph_index in range(paragraph_count):
        raw_paragraph = (
            raw_line_breaks[paragraph_index]
            if paragraph_index < len(raw_line_breaks)
            else []
        )
        normalized.append([int(slot) for slot in raw_paragraph])
    shape._payload["paragraph_line_breaks"] = normalized
    return normalized
def _normalize_property_matrix(
    shape: Shape,
    payload_key: str,
    filter_fn: Callable[[Any], Any] | None = None,
) -> list[list[Any]]:
    paragraph_runs = _shape_paragraph_run_matrix(shape)
    raw_values = shape._payload.get(payload_key) or []
    normalized: list[list[Any]] = []
    for paragraph_index, runs in enumerate(paragraph_runs):
        raw_paragraph = (
            raw_values[paragraph_index] if paragraph_index < len(raw_values) else []
        )
        if filter_fn is not None:
            normalized.append(
                [
                    filter_fn(raw_paragraph[run_index])
                    if run_index < len(raw_paragraph)
                    else None
                    for run_index, _ in enumerate(runs)
                ]
            )
        else:
            normalized.append(
                [
                    raw_paragraph[run_index] if run_index < len(raw_paragraph) else None
                    for run_index, _ in enumerate(runs)
                ]
            )
    shape._payload[payload_key] = normalized
    return normalized


def _shape_paragraph_run_property_matrix(
    shape: Shape,
    payload_key: str,
    filter_fn: Callable[[Any], Any] | None = None,
) -> list[list[Any]]:
    normalized_keys = shape._payload.get("_normalized_run_keys")
    if normalized_keys is not None and payload_key in normalized_keys:
        matrix = shape._payload.get(payload_key)
        if isinstance(matrix, list):
            return matrix
    normalized = _normalize_property_matrix(shape, payload_key, filter_fn)
    if normalized_keys is None:
        normalized_keys = set()
        shape._payload["_normalized_run_keys"] = normalized_keys
    normalized_keys.add(payload_key)
    return normalized


def _shape_paragraph_run_bold(shape: Shape) -> list[list[bool | None]]:
    return _shape_paragraph_run_bool_property(shape, "paragraph_run_bold")


def _shape_paragraph_run_italic(shape: Shape) -> list[list[bool | None]]:
    return _shape_paragraph_run_bool_property(shape, "paragraph_run_italic")


def _shape_paragraph_run_underline(shape: Shape) -> list[list[bool | None]]:
    return _shape_paragraph_run_bool_property(shape, "paragraph_run_underline")


def _shape_paragraph_run_font_size(shape: Shape) -> list[list[int | None]]:
    return _shape_paragraph_run_property_matrix(shape, "paragraph_run_font_size")


def _shape_paragraph_run_font_name(shape: Shape) -> list[list[str | None]]:
    return _shape_paragraph_run_property_matrix(shape, "paragraph_run_font_name")


def _shape_paragraph_run_font_rgb(shape: Shape) -> list[list[str | None]]:
    return _shape_paragraph_run_property_matrix(shape, "paragraph_run_font_rgb")


def _shape_paragraph_run_font_theme_color(shape: Shape) -> list[list[str | None]]:
    return _shape_paragraph_run_property_matrix(shape, "paragraph_run_font_theme_color")


def _shape_paragraph_run_font_fill_type(shape: Shape) -> list[list[str | None]]:
    return _shape_paragraph_run_property_matrix(shape, "paragraph_run_font_fill_type")


def _shape_paragraph_run_font_language(shape: Shape) -> list[list[str | None]]:
    return _shape_paragraph_run_property_matrix(shape, "paragraph_run_font_language")


def _shape_paragraph_run_hyperlink_address(shape: Shape) -> list[list[str | None]]:
    return _shape_paragraph_run_property_matrix(shape, "paragraph_run_hyperlink_address")

def _shape_paragraph_font_value(
    shape: Shape,
    paragraph_index: int,
    payload_key: str,
    reader: Callable[[], Any],
) -> Any:
    raw_values = shape._payload.get(payload_key)
    if isinstance(raw_values, list) and paragraph_index < len(raw_values):
        value = raw_values[paragraph_index]
        if payload_key == "paragraph_font_language" and value == _LANGUAGE_ID_NONE:
            return None
        return value
    value = reader()
    _set_shape_paragraph_font_payload(shape, paragraph_index, payload_key, value)
    return value

def _set_shape_paragraph_font_payload(
    shape: Shape,
    paragraph_index: int,
    payload_key: str,
    value: Any,
) -> None:
    values = _shape_paragraph_font_values(shape, payload_key)
    values[paragraph_index] = value
    shape._payload[payload_key] = values

def _shape_paragraph_font_values(shape: Shape, payload_key: str) -> list[Any]:
    paragraphs = _shape_paragraphs(shape)
    raw_values = shape._payload.get(payload_key)
    if not isinstance(raw_values, list):
        raw_values = []
    values = [
        raw_values[index] if index < len(raw_values) else None
        for index, _ in enumerate(paragraphs)
    ]
    shape._payload[payload_key] = values
    return values

def _shape_paragraph_alignments(shape: Shape) -> list[str | None]:
    paragraphs = _shape_paragraphs(shape)
    raw_values = shape._payload.get("paragraph_alignment") or []
    normalized = [
        raw_values[index] if index < len(raw_values) else None
        for index, _ in enumerate(paragraphs)
    ]
    shape._payload["paragraph_alignment"] = normalized
    return normalized

def _shape_paragraph_levels(shape: Shape) -> list[int | None]:
    paragraphs = _shape_paragraphs(shape)
    raw_values = shape._payload.get("paragraph_level")
    if not isinstance(raw_values, list):
        raw_values = []
    normalized = [
        raw_values[index] if index < len(raw_values) else None
        for index, _ in enumerate(paragraphs)
    ]
    shape._payload["paragraph_level"] = normalized
    return normalized

def _shape_paragraph_spacing_values(
    shape: Shape,
    payload_key: str,
) -> list[int | float | None]:
    paragraphs = _shape_paragraphs(shape)
    raw_values = shape._payload.get(payload_key)
    if not isinstance(raw_values, list):
        raw_values = []
    normalized = [
        raw_values[index] if index < len(raw_values) else None
        for index, _ in enumerate(paragraphs)
    ]
    shape._payload[payload_key] = normalized
    return normalized

def _shape_paragraph_run_bool_property(
    shape: Shape, payload_key: str
) -> list[list[bool | None]]:
    return _shape_paragraph_run_property_matrix(shape, payload_key)

def _sync_shape_text_from_paragraph_runs(
    shape: Shape, paragraph_runs: list[list[str]]
) -> list[list[str]]:
    line_breaks = _normalize_paragraph_line_breaks(
        shape._payload.get("paragraph_line_breaks"),
        len(paragraph_runs),
    )
    paragraphs = [
        _paragraph_text_from_runs_and_line_breaks(runs, line_breaks[index])
        for index, runs in enumerate(paragraph_runs)
    ]
    shape._payload["paragraph_runs"] = paragraph_runs
    shape._payload["paragraph_line_breaks"] = line_breaks
    shape._payload["paragraphs"] = paragraphs
    shape._payload["text"] = "\n".join(paragraphs)
    _invalidate_shape_text_cache(shape)
    shape._payload["_paragraph_runs_normalized"] = True
    shape._payload["_paragraph_runs_token"] = (
        id(paragraph_runs),
        tuple(len(p) for p in paragraph_runs),
    )
    return paragraph_runs
def _normalize_paragraph_line_breaks(
    raw_line_breaks: Any,
    paragraph_count: int,
) -> list[list[int]]:
    if not isinstance(raw_line_breaks, list):
        raw_line_breaks = []
    normalized: list[list[int]] = []
    for paragraph_index in range(paragraph_count):
        raw_paragraph = (
            raw_line_breaks[paragraph_index]
            if paragraph_index < len(raw_line_breaks)
            else []
        )
        if not isinstance(raw_paragraph, list):
            raw_paragraph = []
        normalized.append([int(slot) for slot in raw_paragraph])
    return normalized

def _paragraph_runs_and_line_breaks(text: str) -> tuple[list[str], list[int]]:
    parts = text.split("\v")
    runs = [part for part in parts if part]
    line_breaks: list[int] = []
    run_slot = 0
    for part in parts[:-1]:
        if part:
            run_slot += 1
        line_breaks.append(run_slot)
    return runs, line_breaks

def _paragraph_text_from_runs_and_line_breaks(
    runs: list[str],
    line_breaks: list[int],
) -> str:
    parts: list[str] = []
    for run_slot in range(len(runs) + 1):
        parts.extend("\v" for slot in line_breaks if slot == run_slot)
        if run_slot < len(runs):
            parts.append(runs[run_slot])
    return "".join(parts)

def _shape_paragraphs(shape: Shape) -> list[str]:
    _shape_paragraph_runs(shape)
    return list(shape._payload.get("paragraphs", []))

def _shape_transform(shape: Shape) -> dict[str, int]:
    raw = shape._payload.get("transform") or shape._payload.get("effective_transform") or {}
    return {
        "x": int(raw.get("x", 0)),
        "y": int(raw.get("y", 0)),
        "cx": int(raw.get("cx", 0)),
        "cy": int(raw.get("cy", 0)),
    }

def _shape_transform_value(shape: Shape, key: str) -> int:
    return _shape_transform(shape)[key]
