"""List fitting helpers for table cell text-frame properties."""

from __future__ import annotations

from typing import Any


def _fit_paragraph_property_list(
    values: list[str | None],
    paragraph_count: int,
    default: str | None,
) -> list[str | None]:
    fitted = list(values[:paragraph_count])
    if len(fitted) < paragraph_count:
        fitted.extend([default] * (paragraph_count - len(fitted)))
    return fitted


def _fit_dict_property_list(
    values: list[dict[str, Any]],
    paragraph_count: int,
) -> list[dict[str, Any]]:
    fitted = [dict(value) for value in values[:paragraph_count]]
    if len(fitted) < paragraph_count:
        fitted.extend({} for _index in range(paragraph_count - len(fitted)))
    return fitted


def _fit_run_property_list(
    values: list[list[str]],
    paragraphs: list[str],
) -> list[list[str]]:
    fitted = [
        [str(run) for run in value]
        for value in values[: len(paragraphs)]
        if isinstance(value, list)
    ]
    if len(fitted) < len(paragraphs):
        fitted.extend(
            [paragraph] if paragraph else [] for paragraph in paragraphs[len(fitted) :]
        )
    return fitted


def _fit_run_font_property_list(
    values: list[list[dict[str, Any]]],
    paragraph_runs: list[list[str]],
) -> list[list[dict[str, Any]]]:
    fitted: list[list[dict[str, Any]]] = []
    for paragraph_index, runs in enumerate(paragraph_runs):
        raw_fonts = values[paragraph_index] if paragraph_index < len(values) else []
        if not isinstance(raw_fonts, list):
            raw_fonts = []
        paragraph_fonts = [
            dict(font) if isinstance(font, dict) else {}
            for font in raw_fonts[: len(runs)]
        ]
        if len(paragraph_fonts) < len(runs):
            paragraph_fonts.extend(
                {} for _index in range(len(runs) - len(paragraph_fonts))
            )
        fitted.append(paragraph_fonts)
    return fitted


def _fit_line_break_property_list(
    values: list[list[int]],
    paragraph_runs: list[list[str]],
) -> list[list[int]]:
    fitted: list[list[int]] = []
    for paragraph_index, runs in enumerate(paragraph_runs):
        raw_values = values[paragraph_index] if paragraph_index < len(values) else []
        if not isinstance(raw_values, list):
            raw_values = []
        fitted.append([int(slot) for slot in raw_values if 0 <= int(slot) <= len(runs)])
    return fitted


def _fit_run_optional_string_property_list(
    values: list[list[str | None]],
    paragraph_runs: list[list[str]],
) -> list[list[str | None]]:
    fitted: list[list[str | None]] = []
    for paragraph_index, runs in enumerate(paragraph_runs):
        raw_values = values[paragraph_index] if paragraph_index < len(values) else []
        if not isinstance(raw_values, list):
            raw_values = []
        paragraph_values = [
            str(value) if value else None for value in raw_values[: len(runs)]
        ]
        if len(paragraph_values) < len(runs):
            paragraph_values.extend(
                None for _index in range(len(runs) - len(paragraph_values))
            )
        fitted.append(paragraph_values)
    return fitted
