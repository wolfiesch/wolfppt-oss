"""Text frame, paragraph, and run facade helpers."""
# ruff: noqa: F401

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
    centipoints_value as _centipoints_value,
    coerce_emu as _coerce_emu,
    coerce_paragraph_level as _coerce_paragraph_level,
    emu_to_centipoints as _emu_to_centipoints,
    emu_value as _emu_value,
    normalize_line_spacing as _normalize_line_spacing,
    normalize_paragraph_alignment as _normalize_paragraph_alignment,
    normalize_paragraph_spacing_length as _normalize_paragraph_spacing_length,
    normalize_text_frame_auto_size as _normalize_text_frame_auto_size,
    normalize_text_frame_vertical_anchor as _normalize_text_frame_vertical_anchor,
    normalize_text_frame_word_wrap as _normalize_text_frame_word_wrap,
    paragraph_alignment_value as _paragraph_alignment_value,
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
    rotation_degrees_from_units as _rotation_degrees_from_units,
    text_frame_auto_size_value as _text_frame_auto_size_value,
    text_frame_vertical_anchor_value as _text_frame_vertical_anchor_value,
)
from .package_parts import PackagePart
from .shape_payloads import (
    _shape_paragraph_alignments,
    _shape_paragraph_line_breaks,
    _shape_paragraph_levels,
    _shape_paragraph_run_bold,
    _shape_paragraph_run_font_fill_type,
    _shape_paragraph_run_font_language,
    _shape_paragraph_run_font_name,
    _shape_paragraph_run_font_rgb,
    _shape_paragraph_run_font_size,
    _shape_paragraph_run_hyperlink_address,
    _shape_paragraph_run_matrix,
    _shape_paragraph_run_italic,
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
from .text_facade_inspection import (
    _shape_paragraph_font_bold,
    _shape_paragraph_font_fill_type,
    _shape_paragraph_font_italic,
    _shape_paragraph_font_language,
    _shape_paragraph_font_name,
    _shape_paragraph_font_rgb,
    _shape_paragraph_font_size,
    _shape_paragraph_font_underline,
    _shape_rotation,
    _text_frame_margin,
    _set_text_frame_margin,
    _text_frame_margin_name,
    _shape_text_frame_margins,
    _text_frame_word_wrap,
    _text_frame_vertical_anchor,
    _text_frame_auto_size,
    _best_fit_text_font_size,
    _text_frame_extents,
    _set_text_frame_fit_payload,
    _shape_text_run_hyperlink_address,
    _shape_text_paragraph_alignment,
    _shape_text_paragraph_level,
    _paragraph_spacing_value,
    _set_paragraph_spacing_payload,
    _shape_text_paragraph_spacing,
    _shape_text_run_rgb,
    _shape_text_run_fill_type,
    _shape_text_run_language_id,
    _shape_text_paragraph_default_run_properties,
    _shape_text_paragraph_font_bool,
    _shape_text_paragraph_font_underline,
    _shape_text_paragraph_font_size,
    _shape_text_paragraph_font_name,
    _shape_text_paragraph_font_rgb,
    _shape_text_paragraph_font_fill_type,
    _shape_text_paragraph_font_language,
    _shape_run_count_payload,
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
from .xml_helpers import xml_local_name as _xml_local_name

if TYPE_CHECKING:
    from .shape_core_facade import Shape


class TextFrame:
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
    def paragraphs(self) -> "ParagraphCollection":
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

    def add_paragraph(self) -> "TextParagraph":
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs.append([])
        _shape_paragraph_line_breaks(self._shape).append([])
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        index = len(paragraph_runs) - 1
        _queue_paragraph_state(self._shape, index)
        return TextParagraph(self._shape, index)


class ParagraphCollection(Sequence["TextParagraph"]):
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    def __getitem__(self, index: int | slice) -> "TextParagraph | list[TextParagraph]":
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

    def __iter__(self) -> Iterator["TextParagraph"]:
        for index in range(len(self)):
            yield TextParagraph(self._shape, index)

    def __len__(self) -> int:
        return len(_shape_paragraphs(self._shape))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return [paragraph.text for paragraph in self] == other
        return super().__eq__(other)


class TextParagraph:
    def __init__(self, shape: Shape, index: int) -> None:
        self._shape = shape
        self._index = index

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
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs[self._index] = [text]
        _shape_paragraph_line_breaks(self._shape)[self._index] = []
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        _queue_paragraph_state(self._shape, self._index)

    def clear(self) -> "TextParagraph":
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs[self._index] = []
        _shape_paragraph_line_breaks(self._shape)[self._index] = []
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        _queue_paragraph_clear_state(self._shape, self._index)
        return self

    def add_line_break(self) -> None:
        paragraph_runs = _shape_paragraph_runs(self._shape)
        line_breaks = _shape_paragraph_line_breaks(self._shape)
        run_slot = len(paragraph_runs[self._index])
        line_breaks[self._index].append(run_slot)
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        _queue_paragraph_line_break_state(self._shape, self._index, run_slot)

    @property
    def font(self) -> "TextParagraphFont":
        return TextParagraphFont(self)

    @property
    def runs(self) -> "TextRunCollection":
        return TextRunCollection(self._shape, self._index)

    @property
    def alignment(self) -> Any:
        alignments = _shape_paragraph_alignments(self._shape)
        alignment = alignments[self._index]
        if alignment is None:
            alignment = _shape_text_paragraph_alignment(self._shape, self._index)
            alignments[self._index] = alignment
        return _paragraph_alignment_value(alignment)

    @alignment.setter
    def alignment(self, value: Any) -> None:
        alignment = _normalize_paragraph_alignment(value)
        alignments = _shape_paragraph_alignments(self._shape)
        current = alignments[self._index]
        if current is None:
            current = _shape_text_paragraph_alignment(self._shape, self._index)
            alignments[self._index] = current
        if alignment == current:
            return
        alignments[self._index] = alignment
        _queue_paragraph_alignment_state(self._shape, self._index, alignment)

    @property
    def level(self) -> int:
        levels = _shape_paragraph_levels(self._shape)
        level = levels[self._index]
        if level is None:
            level = _shape_text_paragraph_level(self._shape, self._index)
            levels[self._index] = level
        return level

    @level.setter
    def level(self, value: Any) -> None:
        level = _coerce_paragraph_level(value)
        if level == self.level:
            return
        levels = _shape_paragraph_levels(self._shape)
        levels[self._index] = level
        _queue_paragraph_level_state(self._shape, self._index, level)

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

    def add_run(self) -> "TextRun":
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs[self._index].append("")
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        index = len(paragraph_runs[self._index]) - 1
        _queue_run_state(self._shape, self._index, index)
        return TextRun(self._shape, self._index, index)
