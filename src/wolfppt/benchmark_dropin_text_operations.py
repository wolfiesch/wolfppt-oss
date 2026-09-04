"""Text drop-in benchmark operation implementations."""

from __future__ import annotations

from typing import Any, Callable

from .benchmark_dropin_actions import (
    _apply_python_pptx_dropin_add_paragraph_format_edit,
    _apply_python_pptx_dropin_add_paragraph_run_formatting_edit,
    _apply_python_pptx_dropin_add_run_formatting_edit,
    _apply_python_pptx_dropin_font_fill_edit,
    _apply_python_pptx_dropin_font_language_edit,
    _apply_python_pptx_dropin_formatting_edit,
    _apply_python_pptx_dropin_paragraph_clear_edit,
    _apply_python_pptx_dropin_paragraph_font_edit,
    _apply_python_pptx_dropin_paragraph_format_edit,
    _apply_python_pptx_dropin_paragraph_level_edit,
    _apply_python_pptx_dropin_paragraph_line_break_edit,
    _apply_python_pptx_dropin_paragraph_spacing_edit,
    _apply_python_pptx_dropin_replace_run_formatting_edit,
    _apply_python_pptx_dropin_text_frame_auto_size_edit,
    _apply_python_pptx_dropin_text_frame_fit_text_edit,
    _apply_python_pptx_dropin_text_frame_margin_edit,
    _apply_python_pptx_dropin_text_frame_vertical_anchor_edit,
    _apply_python_pptx_dropin_text_frame_word_wrap_edit,
    _apply_python_pptx_dropin_text_run_hyperlink_edit,
    _apply_wolfppt_dropin_add_paragraph_format_edit,
    _apply_wolfppt_dropin_add_paragraph_run_formatting_edit,
    _apply_wolfppt_dropin_add_run_formatting_edit,
    _apply_wolfppt_dropin_font_fill_edit,
    _apply_wolfppt_dropin_font_language_edit,
    _apply_wolfppt_dropin_formatting_edit,
    _apply_wolfppt_dropin_paragraph_clear_edit,
    _apply_wolfppt_dropin_paragraph_font_edit,
    _apply_wolfppt_dropin_paragraph_format_edit,
    _apply_wolfppt_dropin_paragraph_level_edit,
    _apply_wolfppt_dropin_paragraph_line_break_edit,
    _apply_wolfppt_dropin_paragraph_spacing_edit,
    _apply_wolfppt_dropin_replace_run_formatting_edit,
    _apply_wolfppt_dropin_text_frame_auto_size_edit,
    _apply_wolfppt_dropin_text_frame_fit_text_edit,
    _apply_wolfppt_dropin_text_frame_margin_edit,
    _apply_wolfppt_dropin_text_frame_vertical_anchor_edit,
    _apply_wolfppt_dropin_text_frame_word_wrap_edit,
    _apply_wolfppt_dropin_text_run_hyperlink_edit,
)
from .benchmark_dropin_operation_helpers import (
    make_python_pptx_dropin_bench,
    make_wolfppt_dropin_bench,
)
from .benchmark_dropin_text_details import (
    _dropin_add_paragraph_format_edit_details,
    _dropin_add_paragraph_run_formatting_edit_details,
    _dropin_add_run_formatting_edit_details,
    _dropin_font_fill_edit_details,
    _dropin_font_language_edit_details,
    _dropin_formatting_edit_details,
    _dropin_paragraph_clear_edit_details,
    _dropin_paragraph_font_edit_details,
    _dropin_paragraph_format_edit_details,
    _dropin_paragraph_level_edit_details,
    _dropin_paragraph_line_break_edit_details,
    _dropin_paragraph_spacing_edit_details,
    _dropin_replace_run_formatting_edit_details,
    _dropin_text_frame_auto_size_edit_details,
    _dropin_text_frame_fit_text_edit_details,
    _dropin_text_frame_margin_edit_details,
    _dropin_text_frame_vertical_anchor_edit_details,
    _dropin_text_frame_word_wrap_edit_details,
    _dropin_text_run_hyperlink_edit_details,
)


def _define_text_bench_pair(
    suffix: str,
    slug: str,
    python_action: Callable[[str, Any], None],
    wolfppt_action: Callable[[str, Any], None],
    details: Callable[..., dict[str, Any]],
) -> None:
    python_name = f"_bench_python_pptx_dropin_{suffix}"
    wolfppt_name = f"_bench_wolfppt_facade_dropin_{suffix}"
    globals()[python_name] = make_python_pptx_dropin_bench(
        slug=slug,
        action=python_action,
        details=details,
        name=python_name,
    )
    globals()[wolfppt_name] = make_wolfppt_dropin_bench(
        slug=slug,
        action=wolfppt_action,
        details=details,
        name=wolfppt_name,
    )


_TEXT_BENCHMARKS: tuple[
    tuple[
        str,
        str,
        Callable[[str, Any], None],
        Callable[[str, Any], None],
        Callable[..., dict[str, Any]],
    ],
    ...,
] = (
    (
        "formatting_edit",
        "formatting",
        _apply_python_pptx_dropin_formatting_edit,
        _apply_wolfppt_dropin_formatting_edit,
        _dropin_formatting_edit_details,
    ),
    (
        "font_language_edit",
        "font-language",
        _apply_python_pptx_dropin_font_language_edit,
        _apply_wolfppt_dropin_font_language_edit,
        _dropin_font_language_edit_details,
    ),
    (
        "font_fill_edit",
        "font-fill",
        _apply_python_pptx_dropin_font_fill_edit,
        _apply_wolfppt_dropin_font_fill_edit,
        _dropin_font_fill_edit_details,
    ),
    (
        "add_run_formatting_edit",
        "add-run-formatting",
        _apply_python_pptx_dropin_add_run_formatting_edit,
        _apply_wolfppt_dropin_add_run_formatting_edit,
        _dropin_add_run_formatting_edit_details,
    ),
    (
        "add_paragraph_run_formatting_edit",
        "add-paragraph-run-formatting",
        _apply_python_pptx_dropin_add_paragraph_run_formatting_edit,
        _apply_wolfppt_dropin_add_paragraph_run_formatting_edit,
        _dropin_add_paragraph_run_formatting_edit_details,
    ),
    (
        "replace_run_formatting_edit",
        "replace-run-formatting",
        _apply_python_pptx_dropin_replace_run_formatting_edit,
        _apply_wolfppt_dropin_replace_run_formatting_edit,
        _dropin_replace_run_formatting_edit_details,
    ),
    (
        "paragraph_format_edit",
        "paragraph-format",
        _apply_python_pptx_dropin_paragraph_format_edit,
        _apply_wolfppt_dropin_paragraph_format_edit,
        _dropin_paragraph_format_edit_details,
    ),
    (
        "paragraph_level_edit",
        "paragraph-level",
        _apply_python_pptx_dropin_paragraph_level_edit,
        _apply_wolfppt_dropin_paragraph_level_edit,
        _dropin_paragraph_level_edit_details,
    ),
    (
        "paragraph_spacing_edit",
        "paragraph-spacing",
        _apply_python_pptx_dropin_paragraph_spacing_edit,
        _apply_wolfppt_dropin_paragraph_spacing_edit,
        _dropin_paragraph_spacing_edit_details,
    ),
    (
        "paragraph_clear_edit",
        "paragraph-clear",
        _apply_python_pptx_dropin_paragraph_clear_edit,
        _apply_wolfppt_dropin_paragraph_clear_edit,
        _dropin_paragraph_clear_edit_details,
    ),
    (
        "paragraph_line_break_edit",
        "paragraph-line-break",
        _apply_python_pptx_dropin_paragraph_line_break_edit,
        _apply_wolfppt_dropin_paragraph_line_break_edit,
        _dropin_paragraph_line_break_edit_details,
    ),
    (
        "paragraph_font_edit",
        "paragraph-font",
        _apply_python_pptx_dropin_paragraph_font_edit,
        _apply_wolfppt_dropin_paragraph_font_edit,
        _dropin_paragraph_font_edit_details,
    ),
    (
        "add_paragraph_format_edit",
        "add-paragraph-format",
        _apply_python_pptx_dropin_add_paragraph_format_edit,
        _apply_wolfppt_dropin_add_paragraph_format_edit,
        _dropin_add_paragraph_format_edit_details,
    ),
    (
        "text_run_hyperlink_edit",
        "text-run-hyperlink",
        _apply_python_pptx_dropin_text_run_hyperlink_edit,
        _apply_wolfppt_dropin_text_run_hyperlink_edit,
        _dropin_text_run_hyperlink_edit_details,
    ),
    (
        "text_frame_margin_edit",
        "text-frame-margin",
        _apply_python_pptx_dropin_text_frame_margin_edit,
        _apply_wolfppt_dropin_text_frame_margin_edit,
        _dropin_text_frame_margin_edit_details,
    ),
    (
        "text_frame_word_wrap_edit",
        "text-frame-word-wrap",
        _apply_python_pptx_dropin_text_frame_word_wrap_edit,
        _apply_wolfppt_dropin_text_frame_word_wrap_edit,
        _dropin_text_frame_word_wrap_edit_details,
    ),
    (
        "text_frame_vertical_anchor_edit",
        "text-frame-anchor",
        _apply_python_pptx_dropin_text_frame_vertical_anchor_edit,
        _apply_wolfppt_dropin_text_frame_vertical_anchor_edit,
        _dropin_text_frame_vertical_anchor_edit_details,
    ),
    (
        "text_frame_auto_size_edit",
        "text-frame-auto-size",
        _apply_python_pptx_dropin_text_frame_auto_size_edit,
        _apply_wolfppt_dropin_text_frame_auto_size_edit,
        _dropin_text_frame_auto_size_edit_details,
    ),
    (
        "text_frame_fit_text_edit",
        "text-frame-fit-text",
        _apply_python_pptx_dropin_text_frame_fit_text_edit,
        _apply_wolfppt_dropin_text_frame_fit_text_edit,
        _dropin_text_frame_fit_text_edit_details,
    ),
)

for _benchmark in _TEXT_BENCHMARKS:
    _define_text_bench_pair(*_benchmark)

del _benchmark
