"""Font, color, and fill helpers for chart title text facades."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .chart_title_text_xml import (
    title_paragraph_run_texts as _title_paragraph_run_texts,
    title_paragraph_default_run_properties as _title_paragraph_default_run_properties,
    title_run_properties as _title_run_properties,
)
from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
    fill_type_from_xml_children as _fill_type_from_xml_children,
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)
from .facade_values import (
    centipoints_value as _centipoints_value,
    fill_type_value as _fill_type_value,
    language_id_value as _language_id_value,
    normalize_language_id as _normalize_language_id,
    normalize_pattern_type as _normalize_pattern_type,
    normalize_rgb as _normalize_rgb,
    pattern_type_value as _pattern_type_value,
    rgb_value as _rgb_value,
)
from .shape_format_facade import GradientStops as _GradientStops

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class ChartTitleParagraphFont:
    def __init__(self, paragraph: Any) -> None:
        self._paragraph = paragraph

    @property
    def bold(self) -> bool | None:
        value = _paragraph_font_properties(self._paragraph).get("b")
        return None if value is None else value in {"1", "true"}

    @bold.setter
    def bold(self, value: bool | None) -> None:
        bold = None if value is None else bool(value)
        if bold != self.bold:
            self._queue_font({"bold": bold})

    @property
    def italic(self) -> bool | None:
        value = _paragraph_font_properties(self._paragraph).get("i")
        return None if value is None else value in {"1", "true"}

    @italic.setter
    def italic(self, value: bool | None) -> None:
        italic = None if value is None else bool(value)
        if italic != self.italic:
            self._queue_font({"italic": italic})

    @property
    def underline(self) -> bool | None:
        value = _paragraph_font_properties(self._paragraph).get("u")
        return None if value is None else value != "none"

    @underline.setter
    def underline(self, value: bool | None) -> None:
        underline = None if value is None else bool(value)
        if underline != self.underline:
            self._queue_font({"underline": underline})

    @property
    def size(self) -> int | None:
        value = _paragraph_font_properties(self._paragraph).get("sz")
        return None if value is None else _centipoints_value(int(value))

    @size.setter
    def size(self, value: int | None) -> None:
        size = None if value is None else int(value)
        if size != self.size:
            self._queue_font({"size": size})

    @property
    def color(self) -> "ChartTitleParagraphColorFormat":
        return ChartTitleParagraphColorFormat(self._paragraph)

    @property
    def fill(self) -> "ChartTitleParagraphFontFillFormat":
        payload = self._paragraph._text_frame.__dict__.setdefault(
            "_paragraph_font_fill_payloads",
            {},
        ).setdefault(self._paragraph._index, {})
        return ChartTitleParagraphFontFillFormat(self._paragraph, payload)

    @property
    def name(self) -> str | None:
        default_run_properties = _paragraph_font_element(self._paragraph, create=False)
        if default_run_properties is None:
            return None
        latin = default_run_properties.find(f"{{{A_NS}}}latin")
        return None if latin is None else latin.attrib.get("typeface")

    @name.setter
    def name(self, value: str | None) -> None:
        name = None if value is None else str(value)
        if name != self.name:
            self._queue_font({"name": name})

    @property
    def language_id(self) -> Any:
        return _language_id_value(
            _paragraph_font_properties(self._paragraph).get("lang")
        )

    @language_id.setter
    def language_id(self, value: Any) -> None:
        language_id = _normalize_language_id(value)
        if language_id != _paragraph_font_properties(self._paragraph).get("lang"):
            self._queue_font({"language_id": language_id})

    def _queue_font(self, properties: dict[str, Any]) -> None:
        self._paragraph._text_frame._queue_paragraph_format(
            self._paragraph._index,
            {"font": properties},
        )


class ChartTitleRun:
    def __init__(
        self,
        text_frame: Any,
        paragraph_index: int,
        index: int,
    ) -> None:
        self._text_frame = text_frame
        self._paragraph_index = paragraph_index
        self._index = index

    @property
    def text(self) -> str:
        return _title_paragraph_run_texts(self._text_frame._title_element(False))[
            self._paragraph_index
        ][self._index]

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        paragraph_runs = _title_paragraph_run_texts(
            self._text_frame._title_element(False)
        )
        paragraph_runs[self._paragraph_index][self._index] = text
        self._text_frame._set_paragraph_runs(paragraph_runs)

    @property
    def font(self) -> "ChartTitleRunFont":
        return ChartTitleRunFont(self)

    @property
    def part(self) -> None:
        return None


class ChartTitleRunFont:
    def __init__(self, run: Any) -> None:
        self._run = run

    @property
    def bold(self) -> bool | None:
        value = _run_properties(self._run).get("b")
        return None if value is None else value in {"1", "true"}

    @bold.setter
    def bold(self, value: bool | None) -> None:
        bold = None if value is None else bool(value)
        if bold != self.bold:
            self._run._text_frame._queue_run_font(
                self._run._paragraph_index,
                self._run._index,
                {"bold": bold},
            )

    @property
    def italic(self) -> bool | None:
        value = _run_properties(self._run).get("i")
        return None if value is None else value in {"1", "true"}

    @italic.setter
    def italic(self, value: bool | None) -> None:
        italic = None if value is None else bool(value)
        if italic != self.italic:
            self._run._text_frame._queue_run_font(
                self._run._paragraph_index,
                self._run._index,
                {"italic": italic},
            )

    @property
    def underline(self) -> bool | None:
        value = _run_properties(self._run).get("u")
        return None if value is None else value != "none"

    @underline.setter
    def underline(self, value: bool | None) -> None:
        underline = None if value is None else bool(value)
        if underline != self.underline:
            self._run._text_frame._queue_run_font(
                self._run._paragraph_index,
                self._run._index,
                {"underline": underline},
            )

    @property
    def size(self) -> int | None:
        value = _run_properties(self._run).get("sz")
        return None if value is None else _centipoints_value(int(value))

    @size.setter
    def size(self, value: int | None) -> None:
        size = None if value is None else int(value)
        if size != self.size:
            self._run._text_frame._queue_run_font(
                self._run._paragraph_index,
                self._run._index,
                {"size": size},
            )

    @property
    def color(self) -> "ChartTitleRunColorFormat":
        return ChartTitleRunColorFormat(self._run)

    @property
    def fill(self) -> "ChartTitleRunFontFillFormat":
        payload = self._run._text_frame.__dict__.setdefault(
            "_run_font_fill_payloads",
            {},
        ).setdefault((self._run._paragraph_index, self._run._index), {})
        return ChartTitleRunFontFillFormat(self._run, payload)

    @property
    def name(self) -> str | None:
        run_properties = _run_properties_element(self._run, create=False)
        if run_properties is None:
            return None
        latin = run_properties.find(f"{{{A_NS}}}latin")
        return None if latin is None else latin.attrib.get("typeface")

    @name.setter
    def name(self, value: str | None) -> None:
        name = None if value is None else str(value)
        if name != self.name:
            self._run._text_frame._queue_run_font(
                self._run._paragraph_index,
                self._run._index,
                {"name": name},
            )

    @property
    def language_id(self) -> Any:
        return _language_id_value(_run_properties(self._run).get("lang"))

    @language_id.setter
    def language_id(self, value: Any) -> None:
        language_id = _normalize_language_id(value)
        if language_id != _run_properties(self._run).get("lang"):
            self._run._text_frame._queue_run_font(
                self._run._paragraph_index,
                self._run._index,
                {"language_id": language_id},
            )


class ChartTitleRunColorFormat:
    def __init__(self, run: Any) -> None:
        self._run = run

    @property
    def rgb(self) -> Any:
        rgb = _run_rgb(self._run)
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if rgb != _run_rgb(self._run):
            self._run._text_frame._queue_run_font(
                self._run._paragraph_index,
                self._run._index,
                {"rgb": rgb},
            )


class ChartTitleRunFontFillFormat:
    def __init__(self, run: Any, payload: dict[str, Any]) -> None:
        self._run = run
        self._payload = payload

    def solid(self) -> None:
        if _run_fill_type(self._run) == "solid":
            return
        self._run._text_frame._queue_run_font(
            self._run._paragraph_index,
            self._run._index,
            {"fill_type": "solid"},
        )

    def background(self) -> None:
        if _run_fill_type(self._run) == "background":
            return
        self._run._text_frame._queue_run_font(
            self._run._paragraph_index,
            self._run._index,
            {"fill_type": "background"},
        )

    def patterned(self) -> None:
        if _run_fill_type(self._run) == "patterned":
            return
        self._queue_fill({"fill_type": "patterned"})

    def gradient(self) -> None:
        if _run_fill_type(self._run) == "gradient":
            return
        self._payload["gradient"] = _default_gradient_payload()
        self._queue_fill(
            {"fill_type": "gradient", "gradient": self._payload["gradient"]}
        )

    @property
    def type(self) -> Any:
        return _fill_type_value(_run_fill_type(self._run) or "solid")

    @property
    def fore_color(self) -> "ChartTitleRunFontFillColorFormat":
        return ChartTitleRunFontFillColorFormat(self._run, "fore")

    @property
    def back_color(self) -> "ChartTitleRunFontFillColorFormat":
        return ChartTitleRunFontFillColorFormat(self._run, "back")

    @property
    def pattern(self) -> Any:
        if _run_fill_type(self._run) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(_run_pattern(self._run))

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if _run_fill_type(self._run) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern != _run_pattern(self._run):
            self._queue_fill({"pattern": pattern})

    @property
    def gradient_angle(self) -> float | None:
        if _run_fill_type(self._run) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        return gradient.get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if _run_fill_type(self._run) != "gradient":
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
        if _run_fill_type(self._run) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return _GradientStops(self)

    def _gradient_payload(self) -> dict[str, Any]:
        gradient = self._payload.get("gradient")
        if not isinstance(gradient, dict):
            gradient = _run_gradient_payload(self._run) or _default_gradient_payload()
            self._payload["gradient"] = gradient
        return gradient

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        self._payload["gradient"] = gradient
        self._queue_fill({"fill_type": "gradient", "gradient": gradient})

    def _queue_fill(self, properties: dict[str, Any]) -> None:
        self._run._text_frame._queue_run_font(
            self._run._paragraph_index,
            self._run._index,
            deepcopy(properties),
        )


class ChartTitleRunFontFillColorFormat:
    def __init__(self, run: Any, target: str) -> None:
        self._run = run
        self._target = target

    @property
    def rgb(self) -> Any:
        if _run_fill_type(self._run) == "patterned":
            rgb = _run_pattern_rgb(
                self._run,
                "bgClr" if self._target == "back" else "fgClr",
            )
            return None if rgb is None else _rgb_value(rgb)
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        return ChartTitleRunColorFormat(self._run).rgb

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if _run_fill_type(self._run) == "patterned":
            color_tag = "bgClr" if self._target == "back" else "fgClr"
            if rgb != _run_pattern_rgb(self._run, color_tag):
                key = (
                    "pattern_back_rgb" if self._target == "back" else "pattern_fore_rgb"
                )
                self._run._text_frame._queue_run_font(
                    self._run._paragraph_index,
                    self._run._index,
                    {key: rgb},
                )
            return
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        ChartTitleRunColorFormat(self._run).rgb = rgb


class ChartTitleParagraphColorFormat:
    def __init__(self, paragraph: Any) -> None:
        self._paragraph = paragraph

    @property
    def rgb(self) -> Any:
        rgb = _paragraph_font_rgb(self._paragraph)
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if rgb != _paragraph_font_rgb(self._paragraph):
            self._paragraph._text_frame._queue_paragraph_format(
                self._paragraph._index,
                {"font": {"rgb": rgb}},
            )


class ChartTitleParagraphFontFillFormat:
    def __init__(self, paragraph: Any, payload: dict[str, Any]) -> None:
        self._paragraph = paragraph
        self._payload = payload

    def solid(self) -> None:
        if _paragraph_font_fill_type(self._paragraph) == "solid":
            return
        _set_paragraph_font(self._paragraph, {"fill_type": "solid"})

    def background(self) -> None:
        if _paragraph_font_fill_type(self._paragraph) == "background":
            return
        _set_paragraph_font(self._paragraph, {"fill_type": "background"})

    def patterned(self) -> None:
        if _paragraph_font_fill_type(self._paragraph) == "patterned":
            return
        _set_paragraph_font(self._paragraph, {"fill_type": "patterned"})

    def gradient(self) -> None:
        if _paragraph_font_fill_type(self._paragraph) == "gradient":
            return
        self._payload["gradient"] = _default_gradient_payload()
        _set_paragraph_font(
            self._paragraph,
            {"fill_type": "gradient", "gradient": self._payload["gradient"]},
        )

    @property
    def type(self) -> Any:
        return _fill_type_value(_paragraph_font_fill_type(self._paragraph))

    @property
    def fore_color(self) -> "ChartTitleParagraphFontFillColorFormat":
        return ChartTitleParagraphFontFillColorFormat(self._paragraph, "fore")

    @property
    def back_color(self) -> "ChartTitleParagraphFontFillColorFormat":
        return ChartTitleParagraphFontFillColorFormat(self._paragraph, "back")

    @property
    def pattern(self) -> Any:
        if _paragraph_font_fill_type(self._paragraph) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(_paragraph_font_pattern(self._paragraph))

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if _paragraph_font_fill_type(self._paragraph) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern != _paragraph_font_pattern(self._paragraph):
            _set_paragraph_font(self._paragraph, {"pattern": pattern})

    @property
    def gradient_angle(self) -> float | None:
        if _paragraph_font_fill_type(self._paragraph) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        return gradient.get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if _paragraph_font_fill_type(self._paragraph) != "gradient":
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
        if _paragraph_font_fill_type(self._paragraph) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return _GradientStops(self)

    def _gradient_payload(self) -> dict[str, Any]:
        gradient = self._payload.get("gradient")
        if not isinstance(gradient, dict):
            gradient = (
                _paragraph_font_gradient_payload(
                    self._paragraph,
                )
                or _default_gradient_payload()
            )
            self._payload["gradient"] = gradient
        return gradient

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        self._payload["gradient"] = gradient
        _set_paragraph_font(
            self._paragraph,
            {"fill_type": "gradient", "gradient": gradient},
        )


class ChartTitleParagraphFontFillColorFormat:
    def __init__(self, paragraph: Any, target: str) -> None:
        self._paragraph = paragraph
        self._target = target

    @property
    def rgb(self) -> Any:
        if _paragraph_font_fill_type(self._paragraph) == "patterned":
            rgb = _paragraph_font_pattern_rgb(
                self._paragraph,
                "bgClr" if self._target == "back" else "fgClr",
            )
            return None if rgb is None else _rgb_value(rgb)
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        return ChartTitleParagraphColorFormat(self._paragraph).rgb

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if _paragraph_font_fill_type(self._paragraph) == "patterned":
            color_tag = "bgClr" if self._target == "back" else "fgClr"
            if rgb != _paragraph_font_pattern_rgb(self._paragraph, color_tag):
                key = (
                    "pattern_back_rgb" if self._target == "back" else "pattern_fore_rgb"
                )
                _set_paragraph_font(self._paragraph, {key: rgb})
            return
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        ChartTitleParagraphColorFormat(self._paragraph).rgb = rgb


def _paragraph_font_properties(paragraph: Any) -> dict[str, str]:
    default_run_properties = _paragraph_font_element(paragraph, create=False)
    return {} if default_run_properties is None else dict(default_run_properties.attrib)


def _paragraph_font_rgb(paragraph: Any) -> str | None:
    default_run_properties = _paragraph_font_element(paragraph, create=False)
    if default_run_properties is None:
        return None
    color = default_run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    return None if color is None else color.attrib.get("val")


def _paragraph_font_fill_type(paragraph: Any) -> str | None:
    default_run_properties = _paragraph_font_element(paragraph, create=False)
    return (
        None
        if default_run_properties is None
        else _fill_type_from_xml_children(default_run_properties)
    )


def _paragraph_font_pattern(paragraph: Any) -> str | None:
    default_run_properties = _paragraph_font_element(paragraph, create=False)
    if default_run_properties is None:
        return None
    pattern_fill = default_run_properties.find(f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def _paragraph_font_pattern_rgb(
    paragraph: Any,
    color_tag: str,
) -> str | None:
    default_run_properties = _paragraph_font_element(paragraph, create=False)
    if default_run_properties is None:
        return None
    return _fill_rgb_from_xml_children(default_run_properties, color_tag)


def _paragraph_font_gradient_payload(
    paragraph: Any,
) -> dict[str, Any] | None:
    default_run_properties = _paragraph_font_element(paragraph, create=False)
    if default_run_properties is None:
        return None
    return _gradient_payload_from_fill_parent(default_run_properties)


def _set_paragraph_font(
    paragraph: Any,
    properties: dict[str, Any],
) -> None:
    paragraph._text_frame._queue_paragraph_format(
        paragraph._index,
        {"font": properties},
    )


def _paragraph_font_element(
    paragraph: Any,
    *,
    create: bool,
) -> ET.Element | None:
    return _title_paragraph_default_run_properties(
        paragraph._text_frame._title_element(create),
        paragraph._index,
        create=create,
    )


def _run_properties(run: Any) -> dict[str, str]:
    run_properties = _run_properties_element(run, create=False)
    return {} if run_properties is None else dict(run_properties.attrib)


def _run_rgb(run: Any) -> str | None:
    run_properties = _run_properties_element(run, create=False)
    if run_properties is None:
        return None
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    return None if color is None else color.attrib.get("val")


def _run_fill_type(run: Any) -> str | None:
    run_properties = _run_properties_element(run, create=False)
    return (
        None if run_properties is None else _fill_type_from_xml_children(run_properties)
    )


def _run_pattern(run: Any) -> str | None:
    run_properties = _run_properties_element(run, create=False)
    if run_properties is None:
        return None
    pattern_fill = run_properties.find(f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def _run_pattern_rgb(run: Any, color_tag: str) -> str | None:
    run_properties = _run_properties_element(run, create=False)
    if run_properties is None:
        return None
    return _fill_rgb_from_xml_children(run_properties, color_tag)


def _run_gradient_payload(run: Any) -> dict[str, Any] | None:
    run_properties = _run_properties_element(run, create=False)
    if run_properties is None:
        return None
    return _gradient_payload_from_fill_parent(run_properties)


def _run_properties_element(
    run: Any,
    *,
    create: bool,
) -> ET.Element | None:
    return _title_run_properties(
        run._text_frame._title_element(create),
        run._paragraph_index,
        run._index,
        create=create,
    )
