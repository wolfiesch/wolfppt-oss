"""Coalescing helpers for queued text edits."""

from __future__ import annotations

from typing import Any


def remove_paragraph_run_edits(
    queue: Any,
    slide_index: int,
    shape_index: int,
    paragraph_index: int,
) -> None:
    paragraph_key = (slide_index, shape_index, paragraph_index)
    for key, (queued_shape_index, queued_paragraph_index, _) in list(
        queue._text_run_edits.items()
    ):
        if key[0] == slide_index and (
            queued_shape_index,
            queued_paragraph_index,
        ) == (shape_index, paragraph_index):
            del queue._text_run_edits[key]
    for key in list(queue._text_run_appends):
        if key[:3] == paragraph_key:
            del queue._text_run_appends[key]
    for key, (queued_shape_index, queued_paragraph_index, _, _) in list(
        queue._text_run_bold_edits.items()
    ):
        if key[0] == slide_index and (
            queued_shape_index,
            queued_paragraph_index,
        ) == (shape_index, paragraph_index):
            del queue._text_run_bold_edits[key]
    for key, (queued_shape_index, queued_paragraph_index, _, _) in list(
        queue._text_run_italic_edits.items()
    ):
        if key[0] == slide_index and (
            queued_shape_index,
            queued_paragraph_index,
        ) == (shape_index, paragraph_index):
            del queue._text_run_italic_edits[key]
    for key, (queued_shape_index, queued_paragraph_index, _, _) in list(
        queue._text_run_underline_edits.items()
    ):
        if key[0] == slide_index and (
            queued_shape_index,
            queued_paragraph_index,
        ) == (shape_index, paragraph_index):
            del queue._text_run_underline_edits[key]
    for key, (queued_shape_index, queued_paragraph_index, _, _) in list(
        queue._text_run_font_size_edits.items()
    ):
        if key[0] == slide_index and (
            queued_shape_index,
            queued_paragraph_index,
        ) == (shape_index, paragraph_index):
            del queue._text_run_font_size_edits[key]
    for key, (queued_shape_index, queued_paragraph_index, _, _) in list(
        queue._text_run_font_name_edits.items()
    ):
        if key[0] == slide_index and (
            queued_shape_index,
            queued_paragraph_index,
        ) == (shape_index, paragraph_index):
            del queue._text_run_font_name_edits[key]
    for key in list(queue._text_run_font_color_edits):
        if key[:3] == paragraph_key:
            del queue._text_run_font_color_edits[key]
    for key in list(queue._text_run_font_fill_type_edits):
        if key[:3] == paragraph_key:
            del queue._text_run_font_fill_type_edits[key]
    for key in list(queue._text_run_font_language_edits):
        if key[:3] == paragraph_key:
            del queue._text_run_font_language_edits[key]
