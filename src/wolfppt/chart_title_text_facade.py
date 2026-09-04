"""python-pptx-style text-frame facade for chart and axis titles."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from typing import Any
from xml.etree import ElementTree as ET

from .chart_title_text_font_facade import (
    ChartTitleParagraphFont,
    ChartTitleRun,
)
from .chart_title_text_xml import (
    set_title_auto_size as _set_title_auto_size,
    set_title_body_margin as _set_title_body_margin,
    set_title_paragraph_format as _set_title_paragraph_format,
    set_title_paragraph_runs as _set_title_paragraph_runs,
    set_title_paragraphs as _set_title_paragraphs,
    set_title_run_font as _set_title_run_font,
    set_title_text as _set_title_text,
    set_title_text_frame_fit as _set_title_text_frame_fit,
    set_title_vertical_anchor as _set_title_vertical_anchor,
    set_title_word_wrap as _set_title_word_wrap,
    title_body_properties as _title_body_properties,
    title_paragraph_properties as _title_paragraph_properties,
    title_paragraph_run_texts as _title_paragraph_run_texts,
    title_paragraph_spacing_value as _title_paragraph_spacing_value,
    title_paragraph_texts as _title_paragraph_texts,
    title_text as _title_text,
)
from .facade_values import (
    centipoints_value as _centipoints_value,
    centipoints_to_emu as _centipoints_to_emu,
    coerce_paragraph_level as _coerce_paragraph_level,
    emu_to_centipoints as _emu_to_centipoints,
    normalize_line_spacing as _normalize_line_spacing,
    normalize_paragraph_alignment as _normalize_paragraph_alignment,
    normalize_paragraph_spacing_length as _normalize_paragraph_spacing_length,
    normalize_text_frame_auto_size as _normalize_text_frame_auto_size,
    normalize_text_frame_vertical_anchor as _normalize_text_frame_vertical_anchor,
    normalize_text_frame_word_wrap as _normalize_text_frame_word_wrap,
    paragraph_alignment_value as _paragraph_alignment_value,
    text_frame_auto_size_value as _text_frame_auto_size_value,
    text_frame_vertical_anchor_value as _text_frame_vertical_anchor_value,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class ChartTitleTextFrame:
    def __init__(
        self,
        title_element: Callable[[bool], ET.Element],
        queue: Callable[[dict[str, Any]], None],
    ) -> None:
        self._title_element = title_element
        self._queue = queue

    @property
    def text(self) -> str:
        return _title_text(self._title_element(False))

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        title = self._title_element(True)
        _set_title_text(title, text)
        self._queue({"text": text})

    @property
    def paragraphs(self) -> "ChartTitleParagraphCollection":
        return ChartTitleParagraphCollection(self)

    @property
    def part(self) -> None:
        return None

    @property
    def auto_size(self) -> Any:
        body_pr = self._body_pr()
        if body_pr is None:
            return None
        for child in body_pr:
            local_name = child.tag.rsplit("}", 1)[-1]
            if local_name in {"noAutofit", "spAutoFit", "normAutofit"}:
                return _text_frame_auto_size_value(local_name)
        return None

    @auto_size.setter
    def auto_size(self, value: Any) -> None:
        auto_size = _normalize_text_frame_auto_size(value)
        if auto_size == _normalize_text_frame_auto_size(self.auto_size):
            return
        title = self._title_element(True)
        _set_title_auto_size(title, auto_size)
        self._queue({"auto_size": auto_size})

    @property
    def word_wrap(self) -> bool | None:
        body_pr = self._body_pr()
        if body_pr is None:
            return None
        raw = body_pr.attrib.get("wrap")
        if raw == "square":
            return True
        if raw == "none":
            return False
        return None

    @word_wrap.setter
    def word_wrap(self, value: Any) -> None:
        word_wrap = _normalize_text_frame_word_wrap(value)
        if word_wrap == self.word_wrap:
            return
        title = self._title_element(True)
        _set_title_word_wrap(title, word_wrap)
        self._queue({"word_wrap": word_wrap})

    @property
    def vertical_anchor(self) -> Any:
        body_pr = self._body_pr()
        return _text_frame_vertical_anchor_value(
            None if body_pr is None else body_pr.attrib.get("anchor")
        )

    @vertical_anchor.setter
    def vertical_anchor(self, value: Any) -> None:
        anchor = _normalize_text_frame_vertical_anchor(value)
        if anchor == _normalize_text_frame_vertical_anchor(self.vertical_anchor):
            return
        title = self._title_element(True)
        _set_title_vertical_anchor(title, anchor)
        self._queue({"vertical_anchor": anchor})

    @property
    def margin_left(self) -> int:
        return self._body_pr_margin("lIns", 91440)

    @margin_left.setter
    def margin_left(self, value: Any) -> None:
        self._set_body_pr_margin("lIns", "margin_left", value, default=91440)

    @property
    def margin_right(self) -> int:
        return self._body_pr_margin("rIns", 91440)

    @margin_right.setter
    def margin_right(self, value: Any) -> None:
        self._set_body_pr_margin("rIns", "margin_right", value, default=91440)

    @property
    def margin_top(self) -> int:
        return self._body_pr_margin("tIns", 45720)

    @margin_top.setter
    def margin_top(self, value: Any) -> None:
        self._set_body_pr_margin("tIns", "margin_top", value, default=45720)

    @property
    def margin_bottom(self) -> int:
        return self._body_pr_margin("bIns", 45720)

    @margin_bottom.setter
    def margin_bottom(self, value: Any) -> None:
        self._set_body_pr_margin("bIns", "margin_bottom", value, default=45720)

    def clear(self) -> None:
        self.text = ""

    def fit_text(
        self,
        font_family: str = "Calibri",
        max_size: int = 18,
        bold: bool = False,
        italic: bool = False,
        font_file: str | None = None,
    ) -> None:
        if self.text == "":
            return
        try:
            max_point_size = int(max_size)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"max_size must be an integer, got {max_size!r}") from exc
        if max_point_size < 1:
            raise ValueError("max_size must be greater than zero")
        size_emu = _centipoints_to_emu(max_point_size * 100)
        fit = {
            "font_family": str(font_family),
            "size": size_emu,
            "bold": bool(bold),
            "italic": bool(italic),
        }
        title = self._title_element(True)
        _set_title_text_frame_fit(title, fit)
        self._queue({"fit": fit})

    def add_paragraph(self) -> "ChartTitleParagraph":
        paragraph_runs = _title_paragraph_run_texts(self._title_element(False))
        paragraph_runs.append([])
        self._set_paragraph_runs(paragraph_runs)
        return ChartTitleParagraph(self, len(paragraph_runs) - 1)

    def _set_paragraphs(self, paragraphs: list[str]) -> None:
        normalized = [str(paragraph) for paragraph in paragraphs] or [""]
        if normalized == _title_paragraph_texts(self._title_element(False)):
            return
        title = self._title_element(True)
        _set_title_paragraphs(title, normalized)
        self._queue({"paragraphs": normalized})

    def _set_paragraph_runs(self, paragraph_runs: list[list[str]]) -> None:
        normalized = [[str(run) for run in runs] for runs in paragraph_runs] or [[]]
        if normalized == _title_paragraph_run_texts(self._title_element(False)):
            return
        title = self._title_element(True)
        _set_title_paragraph_runs(title, normalized)
        self._queue({"paragraph_runs": normalized})

    def _queue_run_font(
        self,
        paragraph_index: int,
        run_index: int,
        properties: dict[str, Any],
    ) -> None:
        title = self._title_element(True)
        _set_title_run_font(title, paragraph_index, run_index, properties)
        self._queue(
            {
                "run_formats": [
                    {
                        "paragraph_index": paragraph_index,
                        "run_index": run_index,
                        "properties": properties,
                    }
                ]
            }
        )

    def _queue_paragraph_format(
        self,
        paragraph_index: int,
        properties: dict[str, Any],
    ) -> None:
        title = self._title_element(True)
        _set_title_paragraph_format(title, paragraph_index, properties)
        self._queue(
            {
                "paragraph_formats": [
                    {
                        "paragraph_index": paragraph_index,
                        "properties": properties,
                    }
                ]
            }
        )

    def _body_pr(self) -> ET.Element | None:
        return _title_body_properties(self._title_element(False), create=False)

    def _body_pr_margin(self, attr: str, default: int) -> int:
        body_pr = self._body_pr()
        if body_pr is None:
            return default
        raw = body_pr.attrib.get(attr)
        return default if raw is None else int(raw)

    def _set_body_pr_margin(
        self,
        xml_attr: str,
        property_name: str,
        value: Any,
        *,
        default: int,
    ) -> None:
        margin = int(value)
        if margin == self._body_pr_margin(xml_attr, default):
            return
        title = self._title_element(True)
        _set_title_body_margin(title, xml_attr, margin)
        self._queue({property_name: margin})


class ChartTitleParagraphCollection(Sequence["ChartTitleParagraph"]):
    def __init__(self, text_frame: ChartTitleTextFrame) -> None:
        self._text_frame = text_frame

    def __getitem__(
        self,
        index: int | slice,
    ) -> "ChartTitleParagraph | list[ChartTitleParagraph]":
        paragraphs = _title_paragraph_texts(self._text_frame._title_element(False))
        if isinstance(index, slice):
            return [
                ChartTitleParagraph(self._text_frame, paragraph_index)
                for paragraph_index in range(*index.indices(len(paragraphs)))
            ]
        if index < 0:
            index += len(paragraphs)
        if index < 0 or index >= len(paragraphs):
            raise IndexError("paragraph index out of range")
        return ChartTitleParagraph(self._text_frame, index)

    def __iter__(self) -> Iterator["ChartTitleParagraph"]:
        for index in range(len(self)):
            yield ChartTitleParagraph(self._text_frame, index)

    def __len__(self) -> int:
        return len(_title_paragraph_texts(self._text_frame._title_element(False)))


class ChartTitleParagraph:
    def __init__(self, text_frame: ChartTitleTextFrame, index: int) -> None:
        self._text_frame = text_frame
        self._index = index

    @property
    def text(self) -> str:
        return _title_paragraph_texts(self._text_frame._title_element(False))[
            self._index
        ]

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        paragraph_runs = _title_paragraph_run_texts(
            self._text_frame._title_element(False)
        )
        paragraph_runs[self._index] = [text] if text else []
        self._text_frame._set_paragraph_runs(paragraph_runs)

    def clear(self) -> "ChartTitleParagraph":
        self.text = ""
        return self

    @property
    def part(self) -> None:
        return None

    @property
    def font(self) -> "ChartTitleParagraphFont":
        return ChartTitleParagraphFont(self)

    @property
    def alignment(self) -> Any:
        properties = self._paragraph_properties(False)
        return _paragraph_alignment_value(
            None if properties is None else properties.attrib.get("algn")
        )

    @alignment.setter
    def alignment(self, value: Any) -> None:
        alignment = _normalize_paragraph_alignment(value)
        if alignment == _normalize_paragraph_alignment(self.alignment):
            return
        self._text_frame._queue_paragraph_format(
            self._index,
            {"alignment": alignment},
        )

    @property
    def level(self) -> int:
        properties = self._paragraph_properties(False)
        if properties is None:
            return 0
        raw = properties.attrib.get("lvl")
        if raw in (None, ""):
            return 0
        try:
            return _coerce_paragraph_level(int(raw))
        except (TypeError, ValueError):
            return 0

    @level.setter
    def level(self, value: Any) -> None:
        level = _coerce_paragraph_level(value)
        if level == self.level:
            return
        self._text_frame._queue_paragraph_format(self._index, {"level": level})

    @property
    def space_before(self) -> Any:
        return self._spacing_value("space_before")

    @space_before.setter
    def space_before(self, value: Any) -> None:
        spacing = _normalize_paragraph_spacing_length(value, "space_before")
        self._set_spacing_value("space_before", spacing)

    @property
    def space_after(self) -> Any:
        return self._spacing_value("space_after")

    @space_after.setter
    def space_after(self, value: Any) -> None:
        spacing = _normalize_paragraph_spacing_length(value, "space_after")
        self._set_spacing_value("space_after", spacing)

    @property
    def line_spacing(self) -> Any:
        return self._spacing_value("line_spacing")

    @line_spacing.setter
    def line_spacing(self, value: Any) -> None:
        spacing = _normalize_line_spacing(value)
        self._set_spacing_value("line_spacing", spacing)

    @property
    def runs(self) -> "ChartTitleRunCollection":
        return ChartTitleRunCollection(self._text_frame, self._index)

    def add_run(self) -> "ChartTitleRun":
        paragraph_runs = _title_paragraph_run_texts(
            self._text_frame._title_element(False)
        )
        paragraph_runs[self._index].append("")
        run_index = len(paragraph_runs[self._index]) - 1
        self._text_frame._set_paragraph_runs(paragraph_runs)
        return ChartTitleRun(self._text_frame, self._index, run_index)

    def _paragraph_properties(self, create: bool) -> ET.Element | None:
        return _title_paragraph_properties(
            self._text_frame._title_element(create),
            self._index,
            create=create,
        )

    def _spacing_value(self, attr: str) -> Any:
        value = _title_paragraph_spacing_value(self._paragraph_properties(False), attr)
        if value is None:
            return None
        if attr == "line_spacing" and isinstance(value, float):
            return value
        return _centipoints_value(_emu_to_centipoints(int(value)))

    def _set_spacing_value(self, attr: str, value: int | float | None) -> None:
        if value == _title_paragraph_spacing_value(
            self._paragraph_properties(False),
            attr,
        ):
            return
        self._text_frame._queue_paragraph_format(self._index, {attr: value})


class ChartTitleRunCollection(Sequence["ChartTitleRun"]):
    def __init__(self, text_frame: ChartTitleTextFrame, paragraph_index: int) -> None:
        self._text_frame = text_frame
        self._paragraph_index = paragraph_index

    def __getitem__(self, index: int | slice) -> "ChartTitleRun | list[ChartTitleRun]":
        runs = _title_paragraph_run_texts(self._text_frame._title_element(False))[
            self._paragraph_index
        ]
        if isinstance(index, slice):
            return [
                ChartTitleRun(self._text_frame, self._paragraph_index, run_index)
                for run_index in range(*index.indices(len(runs)))
            ]
        if index < 0:
            index += len(runs)
        if index < 0 or index >= len(runs):
            raise IndexError("run index out of range")
        return ChartTitleRun(self._text_frame, self._paragraph_index, index)

    def __iter__(self) -> Iterator["ChartTitleRun"]:
        for index in range(len(self)):
            yield ChartTitleRun(self._text_frame, self._paragraph_index, index)

    def __len__(self) -> int:
        return len(
            _title_paragraph_run_texts(self._text_frame._title_element(False))[
                self._paragraph_index
            ]
        )
