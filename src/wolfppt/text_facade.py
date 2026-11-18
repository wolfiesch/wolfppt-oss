"""Text frame, paragraph, and run facade helpers."""
# ruff: noqa: F401

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any, NamedTuple, overload
from xml.etree import ElementTree as ET

from .enum.text import ParagraphFontAlignment
from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
)
from .facade_values import (
    centipoints_value as _centipoints_value,
)
from .facade_values import (
    coerce_emu as _coerce_emu,
)
from .facade_values import (
    coerce_paragraph_level as _coerce_paragraph_level,
)
from .facade_values import (
    emu_to_centipoints as _emu_to_centipoints,
)
from .facade_values import (
    emu_value as _emu_value,
)
from .facade_values import (
    normalize_line_spacing as _normalize_line_spacing,
)
from .facade_values import (
    normalize_paragraph_alignment as _normalize_paragraph_alignment,
)
from .facade_values import (
    normalize_paragraph_indent as _normalize_paragraph_indent,
)
from .facade_values import (
    normalize_paragraph_spacing_length as _normalize_paragraph_spacing_length,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_text_frame_auto_size as _normalize_text_frame_auto_size,
)
from .facade_values import (
    normalize_text_frame_vertical_anchor as _normalize_text_frame_vertical_anchor,
)
from .facade_values import (
    normalize_text_frame_word_wrap as _normalize_text_frame_word_wrap,
)
from .facade_values import (
    paragraph_alignment_value as _paragraph_alignment_value,
)
from .facade_values import (
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
)
from .facade_values import (
    rotation_degrees_from_units as _rotation_degrees_from_units,
)
from .facade_values import (
    text_frame_auto_size_value as _text_frame_auto_size_value,
)
from .facade_values import (
    text_frame_vertical_anchor_value as _text_frame_vertical_anchor_value,
)
from .math_text import (
    Equation,
    forget_paragraph_equation,
    paragraph_equation,
    queue_paragraph_equation,
)
from .package_parts import PackagePart
from .shape_locks import check_text_edit_lock
from .shape_payloads import (
    _paragraph_runs_and_line_breaks,
    _shape_paragraph_alignments,
    _shape_paragraph_levels,
    _shape_paragraph_line_breaks,
    _shape_paragraph_run_bold,
    _shape_paragraph_run_font_fill_type,
    _shape_paragraph_run_font_language,
    _shape_paragraph_run_font_name,
    _shape_paragraph_run_font_rgb,
    _shape_paragraph_run_font_size,
    _shape_paragraph_run_hyperlink_address,
    _shape_paragraph_run_italic,
    _shape_paragraph_run_matrix,
    _shape_paragraph_run_underline,
    _shape_paragraph_runs,
    _shape_paragraph_spacing_values,
    _shape_paragraphs,
    _shape_transform,
    _sync_shape_text_from_paragraph_runs,
)
from .shape_xml import (
    _find_shape_transform_xml_element,
    _find_text_body_properties_element,
    _paragraph_xml_element,
    _shape_xml_element,
    _text_run_xml_element,
)
from .slide_relationships import slide_relationship_target as _slide_relationship_target
from .text_autofit import TextAutofitScale
from .text_facade_inspection import (
    _best_fit_text_font_size,
    _paragraph_spacing_value,
    _set_paragraph_spacing_payload,
    _set_text_frame_fit_payload,
    _set_text_frame_margin,
    _shape_paragraph_font_bold,
    _shape_paragraph_font_fill_type,
    _shape_paragraph_font_italic,
    _shape_paragraph_font_language,
    _shape_paragraph_font_name,
    _shape_paragraph_font_rgb,
    _shape_paragraph_font_size,
    _shape_paragraph_font_underline,
    _shape_rotation,
    _shape_run_count_payload,
    _shape_text_frame_margins,
    _shape_text_paragraph_alignment,
    _shape_text_paragraph_default_run_properties,
    _shape_text_paragraph_font_bool,
    _shape_text_paragraph_font_fill_type,
    _shape_text_paragraph_font_language,
    _shape_text_paragraph_font_name,
    _shape_text_paragraph_font_rgb,
    _shape_text_paragraph_font_size,
    _shape_text_paragraph_font_underline,
    _shape_text_paragraph_level,
    _shape_text_paragraph_spacing,
    _shape_text_run_fill_type,
    _shape_text_run_hyperlink_address,
    _shape_text_run_language_id,
    _shape_text_run_rgb,
    _text_frame_auto_size,
    _text_frame_autofit_scale,
    _text_frame_extents,
    _text_frame_margin,
    _text_frame_margin_name,
    _text_frame_vertical_anchor,
    _text_frame_word_wrap,
)
from .text_facade_queue import (
    _group_child_key,
    _group_child_shape_index,
    _is_appended_paragraph,
    _is_appended_run,
    _is_group_child_text_shape,
    _is_part_scoped_text_shape,
    _queue_paragraph_alignment_state,
    _queue_paragraph_clear_state,
    _queue_paragraph_font_state,
    _queue_paragraph_level_state,
    _queue_paragraph_line_break_state,
    _queue_paragraph_spacing_state,
    _queue_paragraph_state,
    _queue_pending_paragraph_text,
    _queue_run_bold_state,
    _queue_run_font_color_state,
    _queue_run_font_fill_type_state,
    _queue_run_font_language_state,
    _queue_run_font_name_state,
    _queue_run_font_size_state,
    _queue_run_italic_state,
    _queue_run_state,
    _queue_run_underline_state,
    _raise_if_part_scoped_text_formatting,
    _shape_paragraph_text,
    _shape_run_index,
)
from .text_facade_xml_inspection import (
    _paragraph_edit_source,
    _shape_text_paragraph_tab_stops,
    _shape_text_part_root,
    _shape_text_run_properties,
)
from .text_paragraph_font_facade import (
    TextParagraphFont,
    TextParagraphFontColorFormat,
    TextParagraphFontFillFormat,
)
from .text_run_facade import (
    TextRun,
    TextRunCollection,
    TextRunColorFormat,
    TextRunFillFormat,
    TextRunFont,
    TextRunHyperlink,
)
from .text_text import TextFrame as _ElementTextFrame
from .text_text import _Paragraph
from .text_xml import (
    _add_paragraph_tab_stop,
    _insert_run_property_child,
    _set_font_baseline,
    _set_font_caps,
    _set_font_highlight,
    _set_font_spacing,
    _set_text_body_columns,
    _set_text_body_overflow,
    _set_text_body_vertical,
    _text_body_overflow,
    _text_character_properties_element,
)
from .xml_helpers import find_ooxml
from .xml_helpers import ooxml_namespace as _ooxml_namespace
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

if TYPE_CHECKING:
    from .shape_core_facade import Shape


class TextFrame(_ElementTextFrame):
    """A shape's text frame, edited through the presentation package writer."""

    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @property
    def text(self) -> str:
        return self._shape.text

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @text.setter
    def text(self, value: str) -> None:
        self._shape.text = value

    @property
    def paragraphs(self) -> ParagraphCollection:
        return ParagraphCollection(self._shape)

    @property
    def margin_left(self) -> Any:
        return _emu_value(_text_frame_margin(self._shape, "lIns"))

    @margin_left.setter
    def margin_left(self, value: Any) -> None:
        _set_text_frame_margin(self._shape, "lIns", value)

    @property
    def margin_right(self) -> Any:
        return _emu_value(_text_frame_margin(self._shape, "rIns"))

    @margin_right.setter
    def margin_right(self, value: Any) -> None:
        _set_text_frame_margin(self._shape, "rIns", value)

    @property
    def margin_top(self) -> Any:
        return _emu_value(_text_frame_margin(self._shape, "tIns"))

    @margin_top.setter
    def margin_top(self, value: Any) -> None:
        _set_text_frame_margin(self._shape, "tIns", value)

    @property
    def margin_bottom(self) -> Any:
        return _emu_value(_text_frame_margin(self._shape, "bIns"))

    @margin_bottom.setter
    def margin_bottom(self, value: Any) -> None:
        _set_text_frame_margin(self._shape, "bIns", value)

    @property
    def word_wrap(self) -> bool | None:
        return _text_frame_word_wrap(self._shape)

    @word_wrap.setter
    def word_wrap(self, value: Any) -> None:
        word_wrap = _normalize_text_frame_word_wrap(value)
        if word_wrap == _text_frame_word_wrap(self._shape):
            return
        self._shape._payload["text_frame_word_wrap"] = word_wrap
        if _is_part_scoped_text_shape(self._shape):
            self._shape._slide._presentation._queue_part_text_frame_word_wrap(
                self._shape._slide.partname,
                self._shape._index,
                word_wrap,
            )
            return
        if _is_group_child_text_shape(self._shape):
            self._shape._slide._presentation._queue_group_child_text_frame_word_wrap(
                self._shape._slide._index,
                _group_child_shape_index(self._shape),
                int(self._shape._payload["_group_child_index"]),
                word_wrap,
            )
            return
        self._shape._slide._presentation._queue_text_frame_word_wrap(
            self._shape._slide._index,
            self._shape._index,
            word_wrap,
        )

    @property
    def vertical_anchor(self) -> Any:
        return _text_frame_vertical_anchor(self._shape)

    @vertical_anchor.setter
    def vertical_anchor(self, value: Any) -> None:
        anchor = _normalize_text_frame_vertical_anchor(value)
        if "text_frame_vertical_anchor" not in self._shape._payload:
            _text_frame_vertical_anchor(self._shape)
        if anchor == self._shape._payload.get("text_frame_vertical_anchor"):
            return
        self._shape._payload["text_frame_vertical_anchor"] = anchor
        if _is_part_scoped_text_shape(self._shape):
            self._shape._slide._presentation._queue_part_text_frame_vertical_anchor(
                self._shape._slide.partname,
                self._shape._index,
                anchor,
            )
            return
        if _is_group_child_text_shape(self._shape):
            self._shape._slide._presentation._queue_group_child_text_frame_vertical_anchor(
                self._shape._slide._index,
                _group_child_shape_index(self._shape),
                int(self._shape._payload["_group_child_index"]),
                anchor,
            )
            return
        self._shape._slide._presentation._queue_text_frame_vertical_anchor(
            self._shape._slide._index,
            self._shape._index,
            anchor,
        )

    @property
    def auto_size(self) -> Any:
        return _text_frame_auto_size(self._shape)

    @auto_size.setter
    def auto_size(self, value: Any) -> None:
        auto_size = _normalize_text_frame_auto_size(value)
        if "text_frame_auto_size" not in self._shape._payload:
            _text_frame_auto_size(self._shape)
        if auto_size == self._shape._payload.get("text_frame_auto_size"):
            return
        self._shape._payload["text_frame_auto_size"] = auto_size
        self._shape._payload["text_frame_autofit_scale"] = None
        if _is_part_scoped_text_shape(self._shape):
            self._shape._slide._presentation._queue_part_text_frame_auto_size(
                self._shape._slide.partname,
                self._shape._index,
                auto_size,
            )
            return
        if _is_group_child_text_shape(self._shape):
            self._shape._slide._presentation._queue_group_child_text_frame_auto_size(
                self._shape._slide._index,
                _group_child_shape_index(self._shape),
                int(self._shape._payload["_group_child_index"]),
                auto_size,
            )
            return
        self._shape._slide._presentation._queue_text_frame_auto_size(
            self._shape._slide._index,
            self._shape._index,
            auto_size,
        )

    @property
    def vertical(self) -> str | None:
        if "text_frame_vertical" in self._shape._payload:
            return self._shape._payload["text_frame_vertical"]
        if not str(getattr(self._shape._slide, "partname", "")):
            return None
        root = _shape_text_part_root(self._shape)
        shape_el = _shape_xml_element(root, self._shape._payload)
        body_pr = find_ooxml(shape_el, f".//{{{A_NS}}}bodyPr")
        if body_pr is not None:
            val = body_pr.get("vert")
            self._shape._payload["text_frame_vertical"] = val
            return val
        return None

    @vertical.setter
    def vertical(self, value: str | None) -> None:
        probe = ET.Element(f"{{{A_NS}}}bodyPr")
        _set_text_body_vertical(probe, value)
        normalized = None if value in (None, "horz") else value
        if normalized == self.vertical:
            return
        self._shape._payload["text_frame_vertical"] = normalized
        _queue_advanced_text_frame(self._shape, "vertical", normalized)

    @property
    def vertical_overflow(self) -> str | None:
        """Text past the bottom edge: ``"overflow"``, ``"ellipsis"`` or
        ``"clip"`` (``a:bodyPr/@vertOverflow``); None inherits (overflow)."""
        return _text_frame_overflow(self._shape)["vertOverflow"]

    @vertical_overflow.setter
    def vertical_overflow(self, value: str | None) -> None:
        _set_text_frame_overflow(self._shape, "vertOverflow", value)

    @property
    def horizontal_overflow(self) -> str | None:
        """Unwrapped text past the side edges: ``"overflow"`` or ``"clip"``
        (``a:bodyPr/@horzOverflow``); None inherits (overflow)."""
        return _text_frame_overflow(self._shape)["horzOverflow"]

    @horizontal_overflow.setter
    def horizontal_overflow(self, value: str | None) -> None:
        _set_text_frame_overflow(self._shape, "horzOverflow", value)

    def set_text_format(self, **fields: Any) -> None:
        """Set run font fields on every run; see :func:`set_text_format`."""
        set_text_format(self, **fields)

    def set_paragraph_format(self, **fields: Any) -> None:
        """Set paragraph fields on every paragraph; see :func:`set_paragraph_format`."""
        set_paragraph_format(self, **fields)

    def set_text_frame_format(self, **fields: Any) -> None:
        """Set text frame fields; see :func:`set_text_frame_format`."""
        set_text_frame_format(self, **fields)

    def highlight_text(
        self,
        text: str,
        color: Any,
        *,
        whole_word: bool = False,
        ignore_case: bool = False,
    ) -> int:
        """Highlight every match of ``text`` in this frame; see :func:`highlight_text`."""
        return highlight_text(self, text, color, whole_word=whole_word, ignore_case=ignore_case)

    def highlight_regex(
        self,
        pattern: str | re.Pattern[str],
        color: Any,
        *,
        whole_word: bool = False,
        ignore_case: bool = False,
    ) -> int:
        """Highlight every match of ``pattern`` in this frame; see :func:`highlight_regex`."""
        return highlight_regex(self, pattern, color, whole_word=whole_word, ignore_case=ignore_case)

    @property
    def column_count(self) -> int:
        if "text_frame_column_count" in self._shape._payload:
            return int(self._shape._payload["text_frame_column_count"])
        if not str(getattr(self._shape._slide, "partname", "")):
            return 1
        root = _shape_text_part_root(self._shape)
        shape_el = _shape_xml_element(root, self._shape._payload)
        body_pr = find_ooxml(shape_el, f".//{{{A_NS}}}bodyPr")
        if body_pr is not None:
            num_col = body_pr.get("numCol")
            if num_col:
                val = int(num_col)
                self._shape._payload["text_frame_column_count"] = val
                return val
        return 1

    @column_count.setter
    def column_count(self, value: int) -> None:
        probe = ET.Element(f"{{{A_NS}}}bodyPr")
        _set_text_body_columns(probe, value, self.column_spacing)
        normalized = int(value)
        if normalized == self.column_count:
            return
        self._shape._payload["text_frame_column_count"] = normalized
        _queue_advanced_text_frame(
            self._shape,
            "column_count",
            normalized,
        )
        _queue_advanced_text_frame(
            self._shape,
            "column_spacing",
            self.column_spacing,
        )

    @property
    def column_spacing(self) -> int | None:
        if "text_frame_column_spacing" in self._shape._payload:
            return self._shape._payload["text_frame_column_spacing"]
        if not str(getattr(self._shape._slide, "partname", "")):
            return None
        root = _shape_text_part_root(self._shape)
        shape_el = _shape_xml_element(root, self._shape._payload)
        body_pr = find_ooxml(shape_el, f".//{{{A_NS}}}bodyPr")
        if body_pr is not None:
            spc_col = body_pr.get("spcCol")
            if spc_col:
                val = int(spc_col)
                self._shape._payload["text_frame_column_spacing"] = val
                return val
        return None

    @column_spacing.setter
    def column_spacing(self, value: int | None) -> None:
        probe = ET.Element(f"{{{A_NS}}}bodyPr")
        _set_text_body_columns(probe, self.column_count, value)
        normalized = None if value is None else int(value)
        if normalized == self.column_spacing:
            return
        self._shape._payload["text_frame_column_spacing"] = normalized
        _queue_advanced_text_frame(
            self._shape,
            "column_count",
            self.column_count,
        )
        _queue_advanced_text_frame(
            self._shape,
            "column_spacing",
            normalized,
        )

    @property
    def autofit_scale(self) -> TextAutofitScale | None:
        return _text_frame_autofit_scale(self._shape)

    def set_autofit_scale(
        self,
        font_scale: float,
        line_spacing_reduction: float = 0.0,
    ) -> None:
        scale = TextAutofitScale(font_scale, line_spacing_reduction)
        current_scale = _text_frame_autofit_scale(self._shape)
        if (
            self._shape._payload.get("text_frame_auto_size") == "normAutofit"
            and current_scale == scale
        ):
            return
        self._shape._payload["text_frame_auto_size"] = "normAutofit"
        self._shape._payload["text_frame_autofit_scale"] = scale
        scale_dict = {
            "font_scale": scale.font_scale,
            "line_spacing_reduction": scale.line_spacing_reduction,
        }
        if _is_part_scoped_text_shape(self._shape):
            self._shape._slide._presentation._queue_part_text_frame_auto_size(
                self._shape._slide.partname,
                self._shape._index,
                "normAutofit",
                autofit_scale=scale_dict,
            )
            return
        if _is_group_child_text_shape(self._shape):
            self._shape._slide._presentation._queue_group_child_text_frame_auto_size(
                self._shape._slide._index,
                _group_child_shape_index(self._shape),
                int(self._shape._payload["_group_child_index"]),
                "normAutofit",
                autofit_scale=scale_dict,
            )
            return
        self._shape._slide._presentation._queue_text_frame_auto_size(
            self._shape._slide._index,
            self._shape._index,
            "normAutofit",
            autofit_scale=scale_dict,
        )

    def clear_autofit_scale(self) -> None:
        current_scale = _text_frame_autofit_scale(self._shape)
        if current_scale is None:
            return
        if "text_frame_auto_size" not in self._shape._payload:
            _text_frame_auto_size(self._shape)
        current_mode = self._shape._payload.get("text_frame_auto_size")
        self._shape._payload["text_frame_autofit_scale"] = None
        clear_dict = {"font_scale": None, "line_spacing_reduction": None}
        if _is_part_scoped_text_shape(self._shape):
            self._shape._slide._presentation._queue_part_text_frame_auto_size(
                self._shape._slide.partname,
                self._shape._index,
                current_mode,
                autofit_scale=clear_dict,
            )
            return
        if _is_group_child_text_shape(self._shape):
            self._shape._slide._presentation._queue_group_child_text_frame_auto_size(
                self._shape._slide._index,
                _group_child_shape_index(self._shape),
                int(self._shape._payload["_group_child_index"]),
                current_mode,
                autofit_scale=clear_dict,
            )
            return
        self._shape._slide._presentation._queue_text_frame_auto_size(
            self._shape._slide._index,
            self._shape._index,
            current_mode,
            autofit_scale=clear_dict,
        )

    def fit_text(
        self,
        font_family: str = "Calibri",
        max_size: int = 18,
        bold: bool = False,
        italic: bool = False,
        font_file: str | None = None,
    ) -> None:
        _raise_if_part_scoped_text_formatting(self._shape, "text frame fit_text")
        if self.text == "":
            return
        point_size = _best_fit_text_font_size(
            self._shape,
            font_family,
            max_size,
            bool(bold),
            bool(italic),
            font_file,
        )
        size_emu = _centipoints_to_emu(point_size * 100)
        _set_text_frame_fit_payload(
            self._shape,
            font_family,
            size_emu,
            bool(bold),
            bool(italic),
        )
        fit = {
            "font_family": str(font_family),
            "size": size_emu,
            "bold": bool(bold),
            "italic": bool(italic),
        }
        if _is_group_child_text_shape(self._shape):
            self._shape._slide._presentation._queue_group_child_text_frame_fit(
                *_group_child_key(self._shape),
                fit,
            )
            return
        self._shape._slide._presentation._queue_text_frame_fit(
            self._shape._slide._index,
            self._shape._index,
            fit,
        )

    def clear(self) -> None:
        self._shape.text = ""

    def add_paragraph(self) -> TextParagraph:
        check_text_edit_lock(self._shape)
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs.append([])
        _shape_paragraph_line_breaks(self._shape).append([])
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        index = len(paragraph_runs) - 1
        _queue_paragraph_state(self._shape, index)
        return TextParagraph(self._shape, index)

    def add_equation(self, equation: Equation) -> TextParagraph:
        """Add a display or inline equation paragraph (``a14:m``) and return it.

        A frame whose only paragraph is empty puts the equation there, as typing an
        equation into an empty text box does.
        """
        check_text_edit_lock(self._shape)
        paragraphs = _shape_paragraphs(self._shape)
        first = TextParagraph(self._shape, 0)
        if len(paragraphs) == 1 and paragraphs[0] == "" and first.equation is None:
            paragraph = first
        else:
            paragraph = self.add_paragraph()
        paragraph.equation = equation
        return paragraph


class ParagraphCollection(Sequence["TextParagraph"]):
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @overload
    def __getitem__(self, index: int) -> TextParagraph: ...

    @overload
    def __getitem__(self, index: slice) -> list[TextParagraph]: ...

    def __getitem__(self, index: int | slice) -> TextParagraph | list[TextParagraph]:
        paragraphs = _shape_paragraphs(self._shape)
        if isinstance(index, slice):
            return [
                TextParagraph(self._shape, paragraph_index)
                for paragraph_index in range(*index.indices(len(paragraphs)))
            ]
        if index < 0:
            index += len(paragraphs)
        if index < 0 or index >= len(paragraphs):
            raise IndexError("paragraph index out of range")
        return TextParagraph(self._shape, index)

    def __iter__(self) -> Iterator[TextParagraph]:
        for index in range(len(self)):
            yield TextParagraph(self._shape, index)

    def __len__(self) -> int:
        return len(_shape_paragraphs(self._shape))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return [paragraph.text for paragraph in self] == other
        return super().__eq__(other)


class TextParagraph(_Paragraph):
    def __init__(self, shape: Shape, index: int) -> None:
        self._shape = shape
        self._index = index

    def get_effective(self) -> Any:
        """Return this paragraph's effective formatting and its sources
        (commercial edition; see
        :func:`wolfppt.effective_format_readback.paragraph_effective`)."""
        from .editions import commercial_module

        readback = commercial_module("effective_format_readback", "Reading effective formatting")
        return readback.paragraph_effective(self)

    @property
    def text(self) -> str:
        return _shape_paragraphs(self._shape)[self._index]

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        check_text_edit_lock(self._shape)
        # A vertical tab is a soft line break (a:br) between runs, as in python-pptx.
        runs, line_breaks = _paragraph_runs_and_line_breaks(text) if "\v" in text else ([text], [])
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs[self._index] = runs
        _shape_paragraph_line_breaks(self._shape)[self._index] = line_breaks
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        _queue_paragraph_state(self._shape, self._index)
        if line_breaks:
            self._queue_soft_line_breaks(line_breaks)
        forget_paragraph_equation(self)

    def _queue_soft_line_breaks(self, line_breaks: list[int]) -> None:
        """Replay queued paragraph text as separate runs with structural breaks.

        Pending whole-shape text already replays every break; only a queued
        slide paragraph text edit still holds the joined text.
        """
        shape = self._shape
        if _is_part_scoped_text_shape(shape) or _is_group_child_text_shape(shape):
            return
        presentation = shape._slide._presentation
        key = (shape._slide._index, shape._index, self._index)
        if key not in presentation._paragraph_text_edits:
            return
        _queue_pending_paragraph_text(shape, self._index)
        for run_slot in line_breaks:
            presentation._queue_paragraph_line_break(*key, run_slot)

    def clear(self) -> TextParagraph:
        check_text_edit_lock(self._shape)
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs[self._index] = []
        _shape_paragraph_line_breaks(self._shape)[self._index] = []
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        _queue_paragraph_clear_state(self._shape, self._index)
        forget_paragraph_equation(self)
        return self

    @property
    def equation(self) -> Equation | None:
        """The paragraph's Office Math equation (``a14:m``), or None."""
        return paragraph_equation(self)

    @equation.setter
    def equation(self, value: Equation | None) -> None:
        check_text_edit_lock(self._shape)
        queue_paragraph_equation(self, value)

    @property
    def equations(self) -> tuple[Equation, ...]:
        """Every equation in document order, including queued edits."""
        from .math_text_builder import paragraph_plan

        return tuple(equation for _, equation in paragraph_plan(self).slots)

    @property
    def content_runs(self) -> tuple[str | Equation, ...]:
        """Ordered ordinary text, soft breaks (``\\v``), and equation trees."""
        from .math_text_builder import paragraph_content

        return paragraph_content(self)

    def add_equation(self, equation: Equation, index: int | None = None) -> None:
        """Insert before ``content_runs[index]``; omit index to append.

        Ordinary runs keep their run indexes and formatting. Unsupported tree
        content raises ``UnsupportedEquationError`` before queuing a change.
        """
        from .math_text_builder import insert_equation

        check_text_edit_lock(self._shape)
        insert_equation(self, equation, index)

    def set_equation(self, index: int, equation: Equation | None) -> None:
        """Replace/remove one equation by its index in ``equations``."""
        from .math_text_builder import edit_equation

        check_text_edit_lock(self._shape)
        edit_equation(self, index, equation)

    def add_line_break(self) -> None:
        check_text_edit_lock(self._shape)
        paragraph_runs = _shape_paragraph_runs(self._shape)
        line_breaks = _shape_paragraph_line_breaks(self._shape)
        run_slot = len(paragraph_runs[self._index])
        line_breaks[self._index].append(run_slot)
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        _queue_paragraph_line_break_state(self._shape, self._index, run_slot)

    @property
    def font(self) -> TextParagraphFont:
        return TextParagraphFont(self)

    @property
    def runs(self) -> TextRunCollection:
        return TextRunCollection(self._shape, self._index)

    @property
    def alignment(self) -> Any:
        return _paragraph_alignment_value(_shape_text_paragraph_alignment(self._shape, self._index))

    @alignment.setter
    def alignment(self, value: Any) -> None:
        alignment = _normalize_paragraph_alignment(value)
        current = _normalize_paragraph_alignment(self.alignment)
        if alignment == current:
            return
        alignments = _shape_paragraph_alignments(self._shape)
        alignments[self._index] = alignment
        _queue_paragraph_alignment_state(self._shape, self._index, alignment)

    @property
    def font_alignment(self) -> ParagraphFontAlignment | None:
        """Direct ``a:pPr/@fontAlgn``; None when inherited.

        Assign a :class:`ParagraphFontAlignment` or its XML token to author a
        value. Assign None to remove only the direct declaration. After saving,
        use ``get_effective().font_alignment`` for inherited value and provenance.
        Unsupported inputs raise ``ParagraphFontAlignmentRefusal`` before edits.
        """
        value = _shape_text_paragraph_spacing(self._shape, self._index, "font_alignment")
        return None if value is None else ParagraphFontAlignment.from_xml(value)

    @font_alignment.setter
    def font_alignment(self, value: ParagraphFontAlignment | str | None) -> None:
        alignment = None if value is None else ParagraphFontAlignment.from_xml(value)
        if alignment == self.font_alignment:
            return
        _queue_paragraph_spacing_state(
            self._shape,
            self._index,
            "font_alignment",
            None if alignment is None else alignment.value,
        )

    @property
    def level(self) -> int:
        return _shape_text_paragraph_level(self._shape, self._index)

    @level.setter
    def level(self, value: Any) -> None:
        level = _coerce_paragraph_level(value)
        if level == self.level:
            return
        levels = _shape_paragraph_levels(self._shape)
        levels[self._index] = level
        _queue_paragraph_level_state(self._shape, self._index, level)

    @property
    def rtl(self) -> bool | None:
        """Right-to-left paragraph direction (``a:pPr/@rtl``); None when inherited."""
        return _shape_text_paragraph_rtl(self._shape, self._index)

    @rtl.setter
    def rtl(self, value: bool | None) -> None:
        if value is not None and not isinstance(value, bool):
            raise TypeError(f"rtl must be bool or None, got {type(value).__name__}")
        if value is self.rtl:
            return
        _queue_paragraph_spacing_state(self._shape, self._index, "rtl", value)

    @property
    def margin_left(self) -> Any:
        return _paragraph_spacing_value(self._shape, self._index, "margin_left")

    @margin_left.setter
    def margin_left(self, value: Any) -> None:
        _set_paragraph_spacing_payload(
            self._shape,
            self._index,
            "margin_left",
            _normalize_paragraph_indent(value, "margin_left"),
        )

    @property
    def margin_right(self) -> Any:
        return _paragraph_spacing_value(self._shape, self._index, "margin_right")

    @margin_right.setter
    def margin_right(self, value: Any) -> None:
        _set_paragraph_spacing_payload(
            self._shape,
            self._index,
            "margin_right",
            _normalize_paragraph_indent(value, "margin_right"),
        )

    @property
    def indent(self) -> Any:
        return _paragraph_spacing_value(self._shape, self._index, "indent")

    @indent.setter
    def indent(self, value: Any) -> None:
        _set_paragraph_spacing_payload(
            self._shape,
            self._index,
            "indent",
            _normalize_paragraph_indent(value, "indent"),
        )

    @property
    def space_before(self) -> Any:
        return _paragraph_spacing_value(self._shape, self._index, "space_before")

    @space_before.setter
    def space_before(self, value: Any) -> None:
        spacing = _normalize_paragraph_spacing_length(value, "space_before")
        _set_paragraph_spacing_payload(
            self._shape,
            self._index,
            "space_before",
            spacing,
        )

    @property
    def space_after(self) -> Any:
        return _paragraph_spacing_value(self._shape, self._index, "space_after")

    @space_after.setter
    def space_after(self, value: Any) -> None:
        spacing = _normalize_paragraph_spacing_length(value, "space_after")
        _set_paragraph_spacing_payload(
            self._shape,
            self._index,
            "space_after",
            spacing,
        )

    @property
    def line_spacing(self) -> Any:
        return _paragraph_spacing_value(self._shape, self._index, "line_spacing")

    @line_spacing.setter
    def line_spacing(self, value: Any) -> None:
        spacing = _normalize_line_spacing(value)
        _set_paragraph_spacing_payload(
            self._shape,
            self._index,
            "line_spacing",
            spacing,
        )

    @property
    def bullet(self) -> Any:
        from .paragraph_bullet import BulletFormat

        return BulletFormat(self)

    @bullet.setter
    def bullet(self, value: Any) -> None:
        if value is None:
            self.bullet.clear()
        elif isinstance(value, str):
            self.bullet.character(value)
        elif isinstance(value, dict):
            btype = value.get("type") or value.get("kind")
            if btype == "char":
                self.bullet.character(
                    value.get("char", "•"),
                    font=value.get("font"),
                    color=value.get("color"),
                )
            elif btype == "auto_number":
                self.bullet.auto_number_set(
                    style=value.get("style", "arabicPeriod"),
                    start_at=value.get("start_at", 1),
                    font=value.get("font"),
                    color=value.get("color"),
                )
            elif btype == "none":
                self.bullet.none()
            elif btype in (None, "clear"):
                self.bullet.clear()
            else:
                raise ValueError(f"unsupported bullet type: {btype}")
        else:
            raise TypeError(f"bullet must be None, str, or dict, got {type(value).__name__}")

    @property
    def autonumber(self) -> ParagraphAutonumber | None:
        """Auto-number scheme and start value (``a:buAutoNum``), or None."""
        bullet = self.bullet
        if bullet.type != "auto_number":
            return None
        return ParagraphAutonumber(bullet.auto_number_style, bullet.start_at)

    @autonumber.setter
    def autonumber(self, value: str | tuple[str, int] | None) -> None:
        bullet = self.bullet
        if value is None:
            if bullet.type == "auto_number":
                bullet.clear()
            return
        if isinstance(value, str):
            scheme, start_at = value, 1
        elif isinstance(value, tuple) and len(value) == 2:
            scheme, start_at = value
        else:
            raise TypeError("autonumber must be a scheme str, a (scheme, start_at) tuple, or None")
        bullet.auto_number_set(scheme, start_at, font=bullet.font, color=bullet.color)

    def add_run(self) -> TextRun:
        check_text_edit_lock(self._shape)
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs[self._index].append("")
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        index = len(paragraph_runs[self._index]) - 1
        _queue_run_state(self._shape, self._index, index)
        return TextRun(self._shape, self._index, index)

    @property
    def tab_stops(self) -> list[int]:
        return [
            int(stop["pos"]) for stop in _shape_text_paragraph_tab_stops(self._shape, self._index)
        ]

    @property
    def tab_stop_list(self) -> list[TabStop]:
        """Tab stops with their alignment (``"left"``, ``"center"``,
        ``"right"`` or ``"decimal"``), in position order."""
        return [
            TabStop(int(stop["pos"]), _TAB_ALIGNMENT_NAMES[stop.get("align", "l")])
            for stop in _shape_text_paragraph_tab_stops(self._shape, self._index)
        ]

    def add_tab_stop(self, pos: int, align: str = "l") -> None:
        """Add (or move) a tab stop at ``pos`` EMU aligned ``left``/``l``,
        ``center``/``centre``/``ctr``, ``right``/``r`` or ``decimal``/``dec``."""
        current = _shape_text_paragraph_tab_stops(self._shape, self._index)
        self._write_tab_stops([(stop["pos"], stop["align"]) for stop in current] + [(pos, align)])

    def set_tab_stops(self, stops: Iterable[TabStop | tuple[int, str]]) -> None:
        """Replace every tab stop with ``(position, alignment)`` pairs."""
        self._write_tab_stops([(int(pos), align) for pos, align in stops])

    def clear_tab_stops(self) -> None:
        """Remove the paragraph's own tab stops."""
        self._write_tab_stops([])

    def _write_tab_stops(self, stops: list[tuple[int, str]]) -> None:
        probe = ET.Element(f"{{{A_NS}}}pPr")
        for pos, align in stops:
            _add_paragraph_tab_stop(probe, pos, align)
        tab_list = probe.find(f"{{{A_NS}}}tabLst")
        normalized = (
            []
            if tab_list is None
            else [
                {"pos": int(tab.get("pos", "0")), "align": tab.get("algn", "l")} for tab in tab_list
            ]
        )
        self._shape._payload.setdefault("_paragraph_tab_stops", {})[self._index] = normalized
        _queue_paragraph_tab_stops(self._shape, self._index, normalized)


class TabStop(NamedTuple):
    """A paragraph tab stop: ``position`` in EMU and its ``alignment``."""

    position: int
    alignment: str


_TAB_ALIGNMENT_NAMES = {"l": "left", "ctr": "center", "r": "right", "dec": "decimal"}


class ParagraphAutonumber(NamedTuple):
    scheme: str
    start_at: int


def _shape_text_paragraph_rtl(shape: Shape, paragraph_index: int) -> bool | None:
    replaced, prefix, key = _paragraph_edit_source(shape, paragraph_index)
    pending = getattr(shape._slide._presentation, f"{prefix}_paragraph_spacing_edits").get(key, {})
    if "rtl" in pending:
        return pending["rtl"]
    if replaced or shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    root = _shape_text_part_root(shape)
    paragraph = _paragraph_xml_element(_shape_xml_element(root, shape._payload), paragraph_index)
    paragraph_properties = find_ooxml(paragraph, f"{{{A_NS}}}pPr")
    raw = None if paragraph_properties is None else paragraph_properties.get("rtl")
    if raw in ("1", "true"):
        return True
    if raw in ("0", "false"):
        return False
    return None


def _queue_advanced_text_frame(shape: Shape, attr: str, value: Any) -> None:
    presentation = shape._slide._presentation
    if _is_part_scoped_text_shape(shape):
        presentation._queue_part_text_frame_advanced(
            shape._slide.partname, shape._index, attr, value
        )
    elif _is_group_child_text_shape(shape):
        presentation._queue_group_child_text_frame_advanced(
            shape._slide._index,
            _group_child_shape_index(shape),
            int(shape._payload["_group_child_index"]),
            attr,
            value,
        )
    else:
        presentation._queue_text_frame_advanced(shape._slide._index, shape._index, attr, value)


def _queue_paragraph_tab_stops(
    shape: Shape, paragraph_index: int, stops: list[dict[str, Any]]
) -> None:
    presentation = shape._slide._presentation
    if _is_part_scoped_text_shape(shape):
        presentation._queue_part_paragraph_tab_stops(
            shape._slide.partname, shape._index, paragraph_index, stops
        )
    elif _is_group_child_text_shape(shape):
        presentation._queue_group_child_paragraph_tab_stops(
            shape._slide._index,
            _group_child_shape_index(shape),
            int(shape._payload["_group_child_index"]),
            paragraph_index,
            stops,
        )
    else:
        presentation._queue_paragraph_tab_stops(
            shape._slide._index, shape._index, paragraph_index, stops
        )


def _advanced_run_value(font: TextRunFont, attr: str) -> Any:
    shape = font._run._shape
    key = (font._run._paragraph_index, font._run._index)
    cached = shape._payload.setdefault("_advanced_run_font", {})
    if key in cached and attr in cached[key]:
        return cached[key][attr]
    try:
        run_properties = _shape_text_run_properties(
            shape, font._run._paragraph_index, font._run._index
        )
        if run_properties is None:
            return None
        if attr == "baseline":
            raw = run_properties.get("baseline")
            return None if raw is None else int(raw)
        if attr == "spacing":
            raw = run_properties.get("spc")
            return None if raw is None else int(raw)
        if attr == "small_caps":
            cap = run_properties.get("cap")
            return True if cap == "small" else None if cap is None else False
        if attr == "highlight_color":
            highlight = run_properties.find(f"{{{A_NS}}}highlight")
            if highlight is not None:
                srgb = highlight.find(f"{{{A_NS}}}srgbClr")
                return None if srgb is None else srgb.get("val")
    except (AttributeError, TypeError, ValueError):
        return None
    return None


def _set_advanced_run_value(font: TextRunFont, attr: str, value: Any) -> None:
    shape = font._run._shape
    normalized = value
    probe = ET.Element(f"{{{A_NS}}}rPr")
    if attr == "baseline":
        _set_font_baseline(probe, value)
        normalized = None if value is None else int(value)
    elif attr == "spacing":
        _set_font_spacing(probe, value)
        normalized = None if value is None else int(value)
    elif attr == "small_caps":
        if value is not None and not isinstance(value, bool):
            raise TypeError("small_caps must be bool or None")
        _set_font_caps(probe, "small" if value else None)
        normalized = value
    elif attr == "highlight_color":
        _set_font_highlight(probe, value)
        normalized = value
    if normalized == _advanced_run_value(font, attr):
        return
    key = (font._run._paragraph_index, font._run._index)
    shape._payload.setdefault("_advanced_run_font", {}).setdefault(key, {})[attr] = normalized
    if attr == "small_caps" and "cap" in font._portion_overrides():
        # A pending ``caps`` value would be written after ``small_caps``.
        font._portion_overrides()["cap"] = "small" if normalized else None
        font._queue_portion()
    presentation = shape._slide._presentation
    if _is_part_scoped_text_shape(shape):
        presentation._queue_part_run_font(
            shape._slide.partname,
            shape._index,
            font._run._paragraph_index,
            font._run._index,
            attr,
            normalized,
        )
    elif _is_group_child_text_shape(shape):
        presentation._queue_group_child_run_font(
            shape._slide._index,
            _group_child_shape_index(shape),
            int(shape._payload["_group_child_index"]),
            font._run._paragraph_index,
            font._run._index,
            attr,
            normalized,
        )
    else:
        presentation._queue_text_run_advanced(
            shape._slide._index,
            shape._index,
            font._run._paragraph_index,
            font._run._index,
            attr,
            normalized,
        )


def _font_get_baseline(font: TextRunFont) -> int | None:
    return _advanced_run_value(font, "baseline")


def _font_set_baseline(font: TextRunFont, value: int | None) -> None:
    _set_advanced_run_value(font, "baseline", value)


def _font_get_superscript(font: TextRunFont) -> bool:
    baseline = _font_get_baseline(font)
    return baseline is not None and baseline > 0


def _font_set_superscript(font: TextRunFont, value: bool) -> None:
    if not isinstance(value, bool):
        raise TypeError("superscript must be bool")
    if value:
        _font_set_baseline(font, 30000)
    elif _font_get_superscript(font):
        _font_set_baseline(font, None)


def _font_get_subscript(font: TextRunFont) -> bool:
    baseline = _font_get_baseline(font)
    return baseline is not None and baseline < 0


def _font_set_subscript(font: TextRunFont, value: bool) -> None:
    if not isinstance(value, bool):
        raise TypeError("subscript must be bool")
    if value:
        _font_set_baseline(font, -25000)
    elif _font_get_subscript(font):
        _font_set_baseline(font, None)


def _font_get_spacing(font: TextRunFont) -> int | None:
    return _advanced_run_value(font, "spacing")


def _font_set_spacing(font: TextRunFont, value: int | None) -> None:
    _set_advanced_run_value(font, "spacing", value)


def _font_get_small_caps(font: TextRunFont) -> bool | None:
    return _advanced_run_value(font, "small_caps")


def _font_set_small_caps(font: TextRunFont, value: bool | None) -> None:
    _set_advanced_run_value(font, "small_caps", value)


def _font_get_highlight(font: TextRunFont) -> str | None:
    return _advanced_run_value(font, "highlight_color")


def _font_set_highlight(font: TextRunFont, value: str | None) -> None:
    _set_advanced_run_value(font, "highlight_color", value)


TextRunFont.baseline = property(_font_get_baseline, _font_set_baseline)
TextRunFont.superscript = property(_font_get_superscript, _font_set_superscript)
TextRunFont.subscript = property(_font_get_subscript, _font_set_subscript)
TextRunFont.spacing = property(_font_get_spacing, _font_set_spacing)
TextRunFont.small_caps = property(_font_get_small_caps, _font_set_small_caps)
TextRunFont.highlight_color = property(_font_get_highlight, _font_set_highlight)


# -- text frame overflow ---------------------------------------------------


def _text_frame_overflow(shape: Shape) -> dict[str, str | None]:
    cached = shape._payload.get("text_frame_overflow")
    if cached is not None:
        return cached
    body = None
    if str(getattr(shape._slide, "partname", "")):
        try:
            root = _shape_text_part_root(shape)
            body = find_ooxml(_shape_xml_element(root, shape._payload), f".//{{{A_NS}}}bodyPr")
        except (AttributeError, KeyError, IndexError, FileNotFoundError):
            body = None
    cached = _text_body_overflow(body)
    shape._payload["text_frame_overflow"] = cached
    return cached


def _set_text_frame_overflow(shape: Shape, attr: str, value: str | None) -> None:
    _set_text_body_overflow(ET.Element(f"{{{A_NS}}}bodyPr"), {attr: value})
    current = _text_frame_overflow(shape)
    if current[attr] == value:
        return
    current[attr] = value
    pending = shape._payload.setdefault("_text_frame_overflow_edits", {})
    pending[attr] = value
    _queue_advanced_text_frame(shape, "overflow", dict(pending))


# -- bulk formatting -------------------------------------------------------


def _bulk_text_frames(target: Any) -> list[Any]:
    """Text frames of a shape, a table (or table shape), or a text frame."""
    if getattr(target, "has_table", False):
        target = target.table
    if hasattr(target, "rows") and hasattr(target, "columns"):
        return [cell.text_frame for row in target.rows for cell in row if not cell.is_spanned]
    if hasattr(target, "paragraphs"):
        return [target]
    if getattr(target, "has_text_frame", False):
        return [target.text_frame]
    raise TypeError(
        f"{type(target).__name__} has no text: pass a shape with text, a table, or a text frame"
    )


def _settable(obj: Any, name: str) -> bool:
    attribute = getattr(type(obj), name, None)
    return isinstance(attribute, property) and attribute.fset is not None


def _check_bulk_fields(
    objects: Sequence[Any],
    fields: dict[str, Any],
    special: dict[str, Callable[[Any], bool]],
) -> None:
    """Refuse unknown fields before any target changes.

    A field is supported by an object when it names a settable property, or
    when ``special`` has a predicate for it that accepts the object.
    """
    if not fields:
        raise ValueError("pass at least one field to set")
    unsupported = sorted(
        {
            f"{type(obj).__name__}.{name}"
            for obj in objects
            for name in fields
            if not (special[name](obj) if name in special else _settable(obj, name))
        }
    )
    if unsupported:
        raise ValueError(f"unsupported format fields: {', '.join(unsupported)}")


def set_text_format(target: Any, **fields: Any) -> None:
    """Set run font fields on every run of a shape, table or text frame.

    Each keyword names a run font property (``bold``, ``size``, ``name``,
    ``strikethrough_type``, ``kerning``, ``east_asian_font`` ...); ``color``
    takes an RGB value for ``font.color.rgb``. A table applies the fields to
    each unmerged cell. Unknown fields raise before anything changes.
    """
    fonts = [
        run.font
        for frame in _bulk_text_frames(target)
        for paragraph in frame.paragraphs
        for run in paragraph.runs
    ]
    _check_bulk_fields(fonts, fields, {"color": lambda font: _settable(font.color, "rgb")})
    for font in fonts:
        for name, value in fields.items():
            if name == "color":
                font.color.rgb = value
            else:
                setattr(font, name, value)


def set_paragraph_format(target: Any, **fields: Any) -> None:
    """Set paragraph fields on every paragraph of a shape, table or text frame.

    Each keyword names a paragraph property (``alignment``, ``level``,
    ``line_spacing``, ``space_before``, ``margin_left``, ``rtl``, ``bullet``
    ...); ``tab_stops`` takes ``(position, alignment)`` pairs that replace
    each paragraph's tab stops. Unknown fields raise before anything changes.
    """
    paragraphs = [
        paragraph for frame in _bulk_text_frames(target) for paragraph in frame.paragraphs
    ]
    _check_bulk_fields(
        paragraphs,
        fields,
        {"tab_stops": lambda paragraph: hasattr(paragraph, "set_tab_stops")},
    )
    if "tab_stops" in fields:
        fields["tab_stops"] = list(fields["tab_stops"])
    for paragraph in paragraphs:
        for name, value in fields.items():
            if name == "tab_stops":
                paragraph.set_tab_stops(value)
            else:
                setattr(paragraph, name, value)


def set_text_frame_format(target: Any, **fields: Any) -> None:
    """Set text frame fields on a shape, each cell of a table, or a text frame.

    Each keyword names a text frame property (``margin_left`` ...,
    ``word_wrap``, ``vertical_anchor``, ``auto_size``, ``vertical``,
    ``column_count``, ``vertical_overflow`` ...). Unknown fields raise before
    anything changes.
    """
    frames = _bulk_text_frames(target)
    _check_bulk_fields(frames, fields, {})
    for frame in frames:
        for name, value in fields.items():
            setattr(frame, name, value)


# -- highlight by search ---------------------------------------------------


def highlight_text(
    target: Any,
    text: str,
    color: Any,
    *,
    whole_word: bool = False,
    ignore_case: bool = False,
) -> int:
    """Highlight every occurrence of ``text`` in a deck, slide, shape or frame.

    ``target`` is a ``Presentation`` (every slide), a slide, a shape, or a
    text frame; ``color`` is an RGB value. Matches may span runs; runs are
    split so only the matched characters carry ``a:highlight``. A line break
    or field ends a matchable stretch. Like the other package-rewriting
    utilities this edits the saved package and rebases the facade, so queued
    edits must be saved first and shape handles taken before the call are
    stale. Returns the number of matches highlighted.
    """
    if not isinstance(text, str) or not text:
        raise ValueError("search text must be a non-empty string")
    return _highlight(target, re.escape(text), 0, color, whole_word, ignore_case)


def highlight_regex(
    target: Any,
    pattern: str | re.Pattern[str],
    color: Any,
    *,
    whole_word: bool = False,
    ignore_case: bool = False,
) -> int:
    """Highlight every match of a regular expression; see :func:`highlight_text`.

    ``pattern`` is a pattern string or a compiled ``re.Pattern`` (its flags
    are kept). Zero-length matches select no text and are skipped.
    """
    if isinstance(pattern, re.Pattern):
        source, flags = pattern.pattern, pattern.flags
    elif isinstance(pattern, str) and pattern:
        source, flags = pattern, 0
    else:
        raise ValueError("pattern must be a non-empty string or a compiled pattern")
    if not isinstance(source, str):
        raise TypeError("pattern must match text, not bytes")
    return _highlight(target, source, flags, color, whole_word, ignore_case)


def _highlight(
    target: Any,
    source: str,
    flags: int,
    color: Any,
    whole_word: bool,
    ignore_case: bool,
) -> int:
    rgb = _normalize_rgb(color)
    if whole_word:
        source = rf"(?<!\w)(?:{source})(?!\w)"
    if ignore_case:
        flags |= re.IGNORECASE
    try:
        pattern = re.compile(source, flags)
    except re.error as exc:
        raise ValueError(f"invalid regular expression: {exc}") from exc
    presentation, parts, shape_payload = _highlight_scope(target)
    return presentation._rewrite_package(
        "highlighting text",
        lambda package: _highlight_plan(package, parts, shape_payload, pattern, rgb),
    )


def _highlight_scope(target: Any) -> tuple[Any, list[str], dict[str, Any] | None]:
    if hasattr(target, "_rewrite_package"):
        return target, [slide.partname for slide in target.slides], None
    shape = getattr(target, "_shape", None)
    if shape is None and hasattr(target, "_payload") and hasattr(target, "_slide"):
        shape = target
    if shape is not None:
        return shape._slide._presentation, [shape._slide.partname], shape._payload
    if hasattr(target, "_presentation") and getattr(target, "partname", ""):
        return target._presentation, [target.partname], None
    raise TypeError(
        f"cannot highlight text in {type(target).__name__}: pass a presentation, "
        "slide, shape or text frame"
    )


def _highlight_plan(
    package: Any,
    parts: list[str],
    shape_payload: dict[str, Any] | None,
    pattern: re.Pattern[str],
    rgb: str,
) -> tuple[dict[str, bytes], set[str], int]:
    from .presentation_tags import parse_xml, serialize_xml

    replacements: dict[str, bytes] = {}
    total = 0
    for part in parts:
        root = parse_xml(package.read(part.lstrip("/")))
        scope = root if shape_payload is None else _shape_xml_element(root, shape_payload)
        a_ns = _ooxml_namespace(root, A_NS)
        count = sum(
            _highlight_paragraph(paragraph, pattern, rgb, a_ns)
            for paragraph in list(scope.iter(f"{{{a_ns}}}p"))
        )
        if count:
            replacements[part.lstrip("/")] = serialize_xml(root)
            total += count
    return replacements, set(), total


def _highlight_paragraph(
    paragraph: ET.Element, pattern: re.Pattern[str], rgb: str, a_ns: str
) -> int:
    """Highlight the matches of one paragraph; returns the match count."""
    stretches: list[list[tuple[ET.Element, str]]] = [[]]
    for child in list(paragraph):
        name = _xml_local_name(child.tag) if isinstance(child.tag, str) else ""
        if name == "r":
            text = child.find(f"{{{a_ns}}}t")
            stretches[-1].append((child, "" if text is None else text.text or ""))
        elif name not in {"pPr", "endParaRPr"}:
            stretches.append([])  # a:br, a:fld or other content ends a stretch
    count = 0
    for pieces in stretches:
        text = "".join(piece for _, piece in pieces)
        spans = [
            (match.start(), match.end())
            for match in pattern.finditer(text)
            if match.end() > match.start()
        ]
        count += len(spans)
        offset = 0
        for run, run_text in pieces:
            start, end = offset, offset + len(run_text)
            offset = end
            local: list[tuple[int, int]] = []
            for span_start, span_end in spans:
                if span_start < end and span_end > start:
                    piece = (max(span_start, start) - start, min(span_end, end) - start)
                    if local and piece[0] <= local[-1][1]:
                        local[-1] = (local[-1][0], piece[1])
                    else:
                        local.append(piece)
            if local:
                _split_highlighted_run(paragraph, run, run_text, local, rgb, a_ns)
    return count


def _split_highlighted_run(
    paragraph: ET.Element,
    run: ET.Element,
    run_text: str,
    spans: list[tuple[int, int]],
    rgb: str,
    a_ns: str,
) -> None:
    if spans == [(0, len(run_text))]:
        _set_run_highlight(run, rgb, a_ns)
        return
    chunks: list[tuple[str, bool]] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            chunks.append((run_text[cursor:start], False))
        chunks.append((run_text[start:end], True))
        cursor = end
    if cursor < len(run_text):
        chunks.append((run_text[cursor:], False))
    index = list(paragraph).index(run)
    paragraph.remove(run)
    for position, (chunk, highlighted) in enumerate(chunks):
        clone = deepcopy(run)
        clone.find(f"{{{a_ns}}}t").text = chunk  # type: ignore[union-attr]
        if highlighted:
            _set_run_highlight(clone, rgb, a_ns)
        paragraph.insert(index + position, clone)


def _set_run_highlight(run: ET.Element, rgb: str, a_ns: str) -> None:
    properties = run.find(f"{{{a_ns}}}rPr")
    if properties is None:
        properties = ET.Element(f"{{{a_ns}}}rPr")
        run.insert(0, properties)
    for existing in properties.findall(f"{{{a_ns}}}highlight"):
        properties.remove(existing)
    highlight = ET.Element(f"{{{a_ns}}}highlight")
    ET.SubElement(highlight, f"{{{a_ns}}}srgbClr", {"val": rgb})
    _insert_run_property_child(properties, highlight)
