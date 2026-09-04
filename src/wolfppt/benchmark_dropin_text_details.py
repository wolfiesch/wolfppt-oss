"""Compatibility imports for text drop-in benchmark detail readers."""

from __future__ import annotations

from .benchmark_dropin_paragraph_details import (
    _dropin_add_paragraph_format_edit_details,
    _dropin_paragraph_clear_edit_details,
    _dropin_paragraph_font_edit_details,
    _dropin_paragraph_format_edit_details,
    _dropin_paragraph_level_edit_details,
    _dropin_paragraph_line_break_edit_details,
    _dropin_paragraph_spacing_edit_details,
)
from .benchmark_dropin_text_frame_details import (
    _dropin_text_frame_auto_size_edit_details,
    _dropin_text_frame_fit_text_edit_details,
    _dropin_text_frame_margin_edit_details,
    _dropin_text_frame_vertical_anchor_edit_details,
    _dropin_text_frame_word_wrap_edit_details,
)
from .benchmark_dropin_text_run_details import (
    _dropin_add_paragraph_run_formatting_edit_details,
    _dropin_add_run_formatting_edit_details,
    _dropin_font_fill_edit_details,
    _dropin_font_language_edit_details,
    _dropin_formatting_edit_details,
    _dropin_replace_run_formatting_edit_details,
    _dropin_text_run_hyperlink_edit_details,
)

__all__ = [
    "_dropin_add_paragraph_format_edit_details",
    "_dropin_add_paragraph_run_formatting_edit_details",
    "_dropin_add_run_formatting_edit_details",
    "_dropin_font_fill_edit_details",
    "_dropin_font_language_edit_details",
    "_dropin_formatting_edit_details",
    "_dropin_paragraph_clear_edit_details",
    "_dropin_paragraph_font_edit_details",
    "_dropin_paragraph_format_edit_details",
    "_dropin_paragraph_level_edit_details",
    "_dropin_paragraph_line_break_edit_details",
    "_dropin_paragraph_spacing_edit_details",
    "_dropin_replace_run_formatting_edit_details",
    "_dropin_text_frame_auto_size_edit_details",
    "_dropin_text_frame_fit_text_edit_details",
    "_dropin_text_frame_margin_edit_details",
    "_dropin_text_frame_vertical_anchor_edit_details",
    "_dropin_text_frame_word_wrap_edit_details",
    "_dropin_text_run_hyperlink_edit_details",
]
