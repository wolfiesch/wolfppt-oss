"""Chart point data-label text-frame facade helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .chart_data_label_paragraph_font_xml import (
    data_label_paragraph_fill_type as _data_label_paragraph_fill_type,
    data_label_paragraph_font_element as _data_label_paragraph_font_element,
    data_label_paragraph_font_properties as _data_label_paragraph_font_properties,
    data_label_paragraph_gradient_payload as _data_label_paragraph_gradient_payload,
    data_label_paragraph_pattern as _data_label_paragraph_pattern,
    data_label_paragraph_pattern_rgb as _data_label_paragraph_pattern_rgb,
    data_label_paragraph_rgb as _data_label_paragraph_rgb,
    set_data_label_paragraph_font as _set_data_label_paragraph_font,
)
from .chart_data_label_run_facade import DataLabelRunFont, DataLabelRunHyperlink
from .chart_data_label_text_xml import (
    chart_data_label_body_properties as _point_data_label_body_properties,
    chart_data_label_paragraph_properties as _point_data_label_paragraph_properties,
    chart_data_label_paragraph_spacing_value as _point_data_label_paragraph_spacing_value,
    set_chart_data_label_auto_size as _set_point_data_label_auto_size,
    set_chart_data_label_body_margin as _set_point_data_label_body_margin,
    set_chart_data_label_paragraph_format as _set_point_data_label_paragraph_format,
    set_chart_data_label_vertical_anchor as _set_point_data_label_vertical_anchor,
    set_chart_data_label_word_wrap as _set_point_data_label_word_wrap,
)
from .chart_point_data_label_xml import (
    insert_point_data_label_paragraph_line_break as _insert_point_data_label_paragraph_line_break,
    point_data_label_paragraph_line_breaks as _point_data_label_paragraph_line_breaks,
    point_data_label_paragraph_run_texts as _point_data_label_paragraph_run_texts,
    point_data_label_paragraph_texts as _point_data_label_paragraph_texts,
    point_data_label_text as _point_data_label_text,
    set_point_data_label_paragraph_runs as _set_point_data_label_paragraph_runs,
    set_point_data_label_paragraphs as _set_point_data_label_paragraphs,
    set_point_data_label_text as _set_point_data_label_text,
    set_point_data_label_text_frame_fit as _set_point_data_label_text_frame_fit,
)
from .chart_point_facade_xml import _chart_point_data_label_element
from .dml_fill import default_gradient_payload as _default_gradient_payload
from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
    centipoints_value as _centipoints_value,
    coerce_paragraph_level as _coerce_paragraph_level,
    emu_to_centipoints as _emu_to_centipoints,
    fill_type_value as _fill_type_value,
    language_id_value as _language_id_value,
    normalize_language_id as _normalize_language_id,
    normalize_line_spacing as _normalize_line_spacing,
    normalize_paragraph_alignment as _normalize_paragraph_alignment,
    normalize_paragraph_spacing_length as _normalize_paragraph_spacing_length,
    normalize_pattern_type as _normalize_pattern_type,
    normalize_rgb as _normalize_rgb,
    normalize_text_frame_auto_size as _normalize_text_frame_auto_size,
    normalize_text_frame_vertical_anchor as _normalize_text_frame_vertical_anchor,
    normalize_text_frame_word_wrap as _normalize_text_frame_word_wrap,
    paragraph_alignment_value as _paragraph_alignment_value,
    pattern_type_value as _pattern_type_value,
    rgb_value as _rgb_value,
    text_frame_auto_size_value as _text_frame_auto_size_value,
    text_frame_vertical_anchor_value as _text_frame_vertical_anchor_value,
)
from .shape_format_facade import GradientStops as _GradientStops
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


class DataLabelTextFrame:
    def __init__(self, label: Any) -> None:
        self._label = label

    @property
    def auto_size(self) -> Any:
        body_pr = self._body_pr()
        if body_pr is None:
            return None
        for child in body_pr:
            local_name = _xml_local_name(child.tag)
            if local_name in {"noAutofit", "spAutoFit", "normAutofit"}:
                return _text_frame_auto_size_value(local_name)
        return None

    @auto_size.setter
    def auto_size(self, value: Any) -> None:
        auto_size = _normalize_text_frame_auto_size(value)
        if auto_size == _normalize_text_frame_auto_size(self.auto_size):
            return
        element = self._label_element(create=True)
        _set_point_data_label_auto_size(element, auto_size)
        self._label._queue({"auto_size": auto_size})

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
        element = self._label_element(create=True)
        _set_point_data_label_word_wrap(element, word_wrap)
        self._label._queue({"word_wrap": word_wrap})

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
        element = self._label_element(create=True)
        _set_point_data_label_vertical_anchor(element, anchor)
        self._label._queue({"vertical_anchor": anchor})

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

    @property
    def part(self) -> None:
        raise AttributeError("'DataLabel' object has no attribute 'part'")

    @property
    def text(self) -> str:
        element = _chart_point_data_label_element(
            self._label._point._series._chart._shape,
            self._label._point._series.index,
            self._label._point._index,
        )
        return _point_data_label_text(element)

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        element = _chart_point_data_label_element(
            self._label._point._series._chart._shape,
            self._label._point._series.index,
            self._label._point._index,
            create=True,
        )
        _set_point_data_label_text(element, text)
        self._label._queue({"text": text})

    @property
    def paragraphs(self) -> "DataLabelParagraphCollection":
        return DataLabelParagraphCollection(self._label)

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
        fit = {
            "font_family": str(font_family),
            "size": _centipoints_to_emu(max_point_size * 100),
            "bold": bool(bold),
            "italic": bool(italic),
        }
        element = self._label_element(create=True)
        _set_point_data_label_text_frame_fit(element, fit)
        self._label._queue({"fit": fit})

    def add_paragraph(self) -> "DataLabelParagraph":
        paragraph_runs = _point_data_label_paragraph_run_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )
        paragraph_runs.append([])
        self._set_paragraph_runs(paragraph_runs)
        return DataLabelParagraph(self._label, len(paragraph_runs) - 1)

    def _set_paragraphs(self, paragraphs: list[str]) -> None:
        normalized = [str(paragraph) for paragraph in paragraphs] or [""]
        current = _point_data_label_paragraph_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )
        if normalized == current:
            return
        element = _chart_point_data_label_element(
            self._label._point._series._chart._shape,
            self._label._point._series.index,
            self._label._point._index,
            create=True,
        )
        _set_point_data_label_paragraphs(element, normalized)
        self._label._queue({"paragraphs": normalized})

    def _set_paragraph_runs(self, paragraph_runs: list[list[str]]) -> None:
        normalized = [[str(run) for run in runs] for runs in paragraph_runs] or [[]]
        current = _point_data_label_paragraph_run_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )
        if normalized == current:
            return
        element = _chart_point_data_label_element(
            self._label._point._series._chart._shape,
            self._label._point._series.index,
            self._label._point._index,
            create=True,
        )
        _set_point_data_label_paragraph_runs(element, normalized)
        line_breaks = _point_data_label_paragraph_line_breaks(element)
        payload: dict[str, Any] = {"paragraph_runs": normalized}
        if line_breaks:
            payload["paragraph_line_breaks"] = line_breaks
        self._label._queue(payload)

    def _body_pr(self) -> ET.Element | None:
        return _point_data_label_body_properties(self._label_element(), create=False)

    def _body_pr_margin(self, attr: str, default: int) -> int:
        body_pr = self._body_pr()
        if body_pr is None:
            return default
        raw = body_pr.attrib.get(attr)
        if raw is None:
            return default
        return int(raw)

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
        element = self._label_element(create=True)
        _set_point_data_label_body_margin(element, xml_attr, margin)
        self._label._queue({property_name: margin})

    def _label_element(self, *, create: bool = False) -> ET.Element:
        return _chart_point_data_label_element(
            self._label._point._series._chart._shape,
            self._label._point._series.index,
            self._label._point._index,
            create=create,
        )


class DataLabelParagraphCollection(Sequence["DataLabelParagraph"]):
    def __init__(self, label: Any) -> None:
        self._label = label

    def __getitem__(
        self,
        index: int | slice,
    ) -> "DataLabelParagraph | list[DataLabelParagraph]":
        paragraphs = _point_data_label_paragraph_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )
        if isinstance(index, slice):
            return [
                DataLabelParagraph(self._label, paragraph_index)
                for paragraph_index in range(*index.indices(len(paragraphs)))
            ]
        if index < 0:
            index += len(paragraphs)
        if index < 0 or index >= len(paragraphs):
            raise IndexError("paragraph index out of range")
        return DataLabelParagraph(self._label, index)

    def __iter__(self) -> Iterator["DataLabelParagraph"]:
        for index in range(len(self)):
            yield DataLabelParagraph(self._label, index)

    def __len__(self) -> int:
        return len(
            _point_data_label_paragraph_texts(
                _chart_point_data_label_element(
                    self._label._point._series._chart._shape,
                    self._label._point._series.index,
                    self._label._point._index,
                )
            )
        )


class DataLabelParagraph:
    def __init__(self, label: Any, index: int) -> None:
        self._label = label
        self._index = index

    @property
    def text(self) -> str:
        return _point_data_label_paragraph_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )[self._index]

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        paragraphs = _point_data_label_paragraph_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )
        paragraphs[self._index] = text
        DataLabelTextFrame(self._label)._set_paragraphs(paragraphs)

    @property
    def part(self) -> None:
        raise AttributeError("'DataLabel' object has no attribute 'part'")

    def clear(self) -> "DataLabelParagraph":
        self.text = ""
        return self

    def add_line_break(self) -> None:
        paragraph_runs = _point_data_label_paragraph_run_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )
        if self._index < 0 or self._index >= len(paragraph_runs):
            raise IndexError("paragraph index out of range")
        run_slot = len(paragraph_runs[self._index])
        label_element = _chart_point_data_label_element(
            self._label._point._series._chart._shape,
            self._label._point._series.index,
            self._label._point._index,
            create=True,
        )
        _insert_point_data_label_paragraph_line_break(
            label_element,
            self._index,
            run_slot,
        )
        line_breaks = _point_data_label_paragraph_line_breaks(label_element)
        self._label._queue(
            {
                "paragraph_line_breaks": line_breaks,
            }
        )

    @property
    def runs(self) -> "DataLabelRunCollection":
        return DataLabelRunCollection(self._label, self._index)

    @property
    def font(self) -> "DataLabelParagraphFont":
        return DataLabelParagraphFont(self)

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
        self._queue_format({"alignment": alignment})

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
        self._queue_format({"level": level})

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

    def add_run(self) -> "DataLabelRun":
        paragraph_runs = _point_data_label_paragraph_run_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )
        paragraph_runs[self._index].append("")
        run_index = len(paragraph_runs[self._index]) - 1
        DataLabelTextFrame(self._label)._set_paragraph_runs(paragraph_runs)
        return DataLabelRun(self._label, self._index, run_index)

    def _queue_format(self, properties: dict[str, Any]) -> None:
        label_element = _chart_point_data_label_element(
            self._label._point._series._chart._shape,
            self._label._point._series.index,
            self._label._point._index,
            create=True,
        )
        _set_point_data_label_paragraph_format(label_element, self._index, properties)
        self._label._queue(
            {
                "paragraph_formats": [
                    {
                        "paragraph_index": self._index,
                        "properties": properties,
                    }
                ]
            }
        )

    def _paragraph_properties(self, create: bool) -> ET.Element | None:
        label_element = _chart_point_data_label_element(
            self._label._point._series._chart._shape,
            self._label._point._series.index,
            self._label._point._index,
            create=create,
        )
        return _point_data_label_paragraph_properties(
            label_element,
            self._index,
            create=create,
        )

    def _spacing_value(self, attr: str) -> Any:
        value = _point_data_label_paragraph_spacing_value(
            self._paragraph_properties(False),
            attr,
        )
        if value is None:
            return None
        if attr == "line_spacing" and isinstance(value, float):
            return value
        return _centipoints_value(_emu_to_centipoints(int(value)))

    def _set_spacing_value(self, attr: str, value: int | float | None) -> None:
        if value == _point_data_label_paragraph_spacing_value(
            self._paragraph_properties(False),
            attr,
        ):
            return
        self._queue_format({attr: value})


class DataLabelParagraphFont:
    def __init__(self, paragraph: DataLabelParagraph) -> None:
        self._paragraph = paragraph

    @property
    def bold(self) -> bool | None:
        value = _data_label_paragraph_font_properties(self._paragraph).get("b")
        return None if value is None else value in {"1", "true"}

    @bold.setter
    def bold(self, value: bool | None) -> None:
        bold = None if value is None else bool(value)
        if bold != self.bold:
            self._queue_font({"bold": bold})

    @property
    def italic(self) -> bool | None:
        value = _data_label_paragraph_font_properties(self._paragraph).get("i")
        return None if value is None else value in {"1", "true"}

    @italic.setter
    def italic(self, value: bool | None) -> None:
        italic = None if value is None else bool(value)
        if italic != self.italic:
            self._queue_font({"italic": italic})

    @property
    def underline(self) -> bool | None:
        value = _data_label_paragraph_font_properties(self._paragraph).get("u")
        return None if value is None else value != "none"

    @underline.setter
    def underline(self, value: bool | None) -> None:
        underline = None if value is None else bool(value)
        if underline != self.underline:
            self._queue_font({"underline": underline})

    @property
    def size(self) -> int | None:
        value = _data_label_paragraph_font_properties(self._paragraph).get("sz")
        return None if value is None else _centipoints_value(int(value))

    @size.setter
    def size(self, value: int | None) -> None:
        size = None if value is None else int(value)
        if size != self.size:
            self._queue_font({"size": size})

    @property
    def color(self) -> "DataLabelParagraphColorFormat":
        return DataLabelParagraphColorFormat(self._paragraph)

    @property
    def fill(self) -> "DataLabelParagraphFontFillFormat":
        payload = self._paragraph._label.__dict__.setdefault(
            "_paragraph_font_fill_payloads",
            {},
        ).setdefault(self._paragraph._index, {})
        return DataLabelParagraphFontFillFormat(self._paragraph, payload)

    @property
    def name(self) -> str | None:
        run_properties = _data_label_paragraph_font_element(
            self._paragraph,
            create=False,
        )
        if run_properties is None:
            return None
        latin = run_properties.find(f"{{{A_NS}}}latin")
        return None if latin is None else latin.attrib.get("typeface")

    @name.setter
    def name(self, value: str | None) -> None:
        name = None if value is None else str(value)
        if name != self.name:
            self._queue_font({"name": name})

    @property
    def language_id(self) -> Any:
        return _language_id_value(
            _data_label_paragraph_font_properties(self._paragraph).get("lang")
        )

    @language_id.setter
    def language_id(self, value: Any) -> None:
        language_id = _normalize_language_id(value)
        if language_id != _data_label_paragraph_font_properties(self._paragraph).get(
            "lang"
        ):
            self._queue_font({"language_id": language_id})

    def _queue_font(self, properties: dict[str, Any]) -> None:
        self._paragraph._queue_format({"font": properties})


class DataLabelParagraphColorFormat:
    def __init__(self, paragraph: DataLabelParagraph) -> None:
        self._paragraph = paragraph

    @property
    def rgb(self) -> Any:
        rgb = _data_label_paragraph_rgb(self._paragraph)
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if rgb != _data_label_paragraph_rgb(self._paragraph):
            _set_data_label_paragraph_font(self._paragraph, {"rgb": rgb})
            DataLabelParagraphFont(self._paragraph)._queue_font({"rgb": rgb})


class DataLabelParagraphFontFillFormat:
    def __init__(self, paragraph: DataLabelParagraph, payload: dict[str, Any]) -> None:
        self._paragraph = paragraph
        self._payload = payload

    def solid(self) -> None:
        if _data_label_paragraph_fill_type(self._paragraph) == "solid":
            return
        self._queue_fill({"fill_type": "solid"})

    def background(self) -> None:
        if _data_label_paragraph_fill_type(self._paragraph) == "background":
            return
        self._queue_fill({"fill_type": "background"})

    def patterned(self) -> None:
        if _data_label_paragraph_fill_type(self._paragraph) == "patterned":
            return
        self._queue_fill({"fill_type": "patterned"})

    def gradient(self) -> None:
        if _data_label_paragraph_fill_type(self._paragraph) == "gradient":
            return
        self._payload["gradient"] = _default_gradient_payload()
        self._queue_fill(
            {"fill_type": "gradient", "gradient": self._payload["gradient"]}
        )

    @property
    def type(self) -> Any:
        return _fill_type_value(_data_label_paragraph_fill_type(self._paragraph))

    @property
    def fore_color(self) -> "DataLabelParagraphFontFillColorFormat":
        return DataLabelParagraphFontFillColorFormat(self._paragraph, "fore")

    @property
    def back_color(self) -> "DataLabelParagraphFontFillColorFormat":
        return DataLabelParagraphFontFillColorFormat(self._paragraph, "back")

    @property
    def pattern(self) -> Any:
        if _data_label_paragraph_fill_type(self._paragraph) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(_data_label_paragraph_pattern(self._paragraph))

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if _data_label_paragraph_fill_type(self._paragraph) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern != _data_label_paragraph_pattern(self._paragraph):
            self._queue_fill({"pattern": pattern})

    @property
    def gradient_angle(self) -> float | None:
        if _data_label_paragraph_fill_type(self._paragraph) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        return gradient.get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if _data_label_paragraph_fill_type(self._paragraph) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        angle = float(value)
        if gradient.get("angle") == angle:
            return
        gradient["angle"] = angle
        self._queue_gradient(gradient)

    @property
    def gradient_stops(self) -> _GradientStops:
        if _data_label_paragraph_fill_type(self._paragraph) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return _GradientStops(self)

    def _gradient_payload(self) -> dict[str, Any]:
        gradient = self._payload.get("gradient")
        if not isinstance(gradient, dict):
            gradient = (
                _data_label_paragraph_gradient_payload(self._paragraph)
                or _default_gradient_payload()
            )
            self._payload["gradient"] = gradient
        return gradient

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        self._payload["gradient"] = gradient
        self._queue_fill({"fill_type": "gradient", "gradient": gradient})

    def _queue_fill(self, properties: dict[str, Any]) -> None:
        queued = deepcopy(properties)
        _set_data_label_paragraph_font(self._paragraph, queued)
        DataLabelParagraphFont(self._paragraph)._queue_font(queued)


class DataLabelParagraphFontFillColorFormat:
    def __init__(self, paragraph: DataLabelParagraph, target: str) -> None:
        self._paragraph = paragraph
        self._target = target

    @property
    def rgb(self) -> Any:
        if _data_label_paragraph_fill_type(self._paragraph) == "patterned":
            rgb = _data_label_paragraph_pattern_rgb(
                self._paragraph,
                "bgClr" if self._target == "back" else "fgClr",
            )
            return None if rgb is None else _rgb_value(rgb)
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        return DataLabelParagraphColorFormat(self._paragraph).rgb

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if _data_label_paragraph_fill_type(self._paragraph) == "patterned":
            color_tag = "bgClr" if self._target == "back" else "fgClr"
            if rgb != _data_label_paragraph_pattern_rgb(
                self._paragraph,
                color_tag,
            ):
                key = (
                    "pattern_back_rgb" if self._target == "back" else "pattern_fore_rgb"
                )
                _set_data_label_paragraph_font(self._paragraph, {key: rgb})
                DataLabelParagraphFont(self._paragraph)._queue_font({key: rgb})
            return
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        DataLabelParagraphColorFormat(self._paragraph).rgb = rgb


class DataLabelRunCollection(Sequence["DataLabelRun"]):
    def __init__(self, label: Any, paragraph_index: int) -> None:
        self._label = label
        self._paragraph_index = paragraph_index

    def __getitem__(self, index: int | slice) -> "DataLabelRun | list[DataLabelRun]":
        runs = _point_data_label_paragraph_run_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )[self._paragraph_index]
        if isinstance(index, slice):
            return [
                DataLabelRun(self._label, self._paragraph_index, run_index)
                for run_index in range(*index.indices(len(runs)))
            ]
        if index < 0:
            index += len(runs)
        if index < 0 or index >= len(runs):
            raise IndexError("run index out of range")
        return DataLabelRun(self._label, self._paragraph_index, index)

    def __iter__(self) -> Iterator["DataLabelRun"]:
        for index in range(len(self)):
            yield DataLabelRun(self._label, self._paragraph_index, index)

    def __len__(self) -> int:
        return len(
            _point_data_label_paragraph_run_texts(
                _chart_point_data_label_element(
                    self._label._point._series._chart._shape,
                    self._label._point._series.index,
                    self._label._point._index,
                )
            )[self._paragraph_index]
        )


class DataLabelRun:
    def __init__(self, label: Any, paragraph_index: int, index: int) -> None:
        self._label = label
        self._paragraph_index = paragraph_index
        self._index = index

    @property
    def text(self) -> str:
        return _point_data_label_paragraph_run_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )[self._paragraph_index][self._index]

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        paragraph_runs = _point_data_label_paragraph_run_texts(
            _chart_point_data_label_element(
                self._label._point._series._chart._shape,
                self._label._point._series.index,
                self._label._point._index,
            )
        )
        paragraph_runs[self._paragraph_index][self._index] = text
        DataLabelTextFrame(self._label)._set_paragraph_runs(paragraph_runs)

    @property
    def hyperlink(self) -> "DataLabelRunHyperlink":
        return DataLabelRunHyperlink()

    @property
    def part(self) -> None:
        raise AttributeError("'DataLabel' object has no attribute 'part'")

    @property
    def font(self) -> "DataLabelRunFont":
        return DataLabelRunFont(self)

    def _queue_font(self, properties: dict[str, Any]) -> None:
        self._label._queue(
            {
                "run_formats": [
                    {
                        "paragraph_index": self._paragraph_index,
                        "run_index": self._index,
                        "properties": properties,
                    }
                ]
            }
        )
