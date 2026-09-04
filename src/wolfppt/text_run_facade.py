"""Text run facade helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from copy import deepcopy
from typing import Any

from .dml_fill import default_gradient_payload as _default_gradient_payload
from .facade_values import (
    LANGUAGE_ID_NONE as _LANGUAGE_ID_NONE,
    fill_type_value as _fill_type_value,
    language_id_value as _language_id_value,
    normalize_language_id as _normalize_language_id,
    normalize_pattern_type as _normalize_pattern_type,
    normalize_rgb as _normalize_rgb,
    normalize_theme_color as _normalize_theme_color,
    pattern_type_value as _pattern_type_value,
    rgb_value as _rgb_value,
    theme_color_value as _theme_color_value,
)
from .package_parts import PackagePart
from .shape_format_facade import GradientStops as _GradientStops
from .shape_payloads import (
    _shape_paragraph_run_bold,
    _shape_paragraph_run_font_fill_type,
    _shape_paragraph_run_font_language,
    _shape_paragraph_run_font_name,
    _shape_paragraph_run_font_rgb,
    _shape_paragraph_run_font_theme_color,
    _shape_paragraph_run_font_size,
    _shape_paragraph_run_hyperlink_address,
    _shape_paragraph_run_italic,
    _shape_paragraph_run_property_matrix,
    _shape_paragraph_run_underline,
    _shape_paragraph_runs,
    _sync_shape_text_from_paragraph_runs,
)
from .text_facade_inspection import (
    _shape_text_run_gradient_payload,
    _shape_text_run_fill_type,
    _shape_text_run_hyperlink_address,
    _shape_text_run_language_id,
    _shape_text_run_pattern,
    _shape_text_run_pattern_rgb,
    _shape_text_run_rgb,
    _shape_text_run_theme_color,
)
from .text_facade_queue import (
    _group_child_key,
    _is_group_child_text_shape,
    _is_part_scoped_text_shape,
    _queue_run_bold_state,
    _queue_run_font_color_state,
    _queue_run_font_fill_type_state,
    _queue_run_font_language_state,
    _queue_run_font_name_state,
    _queue_run_font_size_state,
    _queue_run_italic_state,
    _queue_run_state,
    _queue_run_underline_state,
)


class TextRunCollection(Sequence["TextRun"]):
    def __init__(self, shape: Shape, paragraph_index: int) -> None:
        self._shape = shape
        self._paragraph_index = paragraph_index

    def __getitem__(self, index: int | slice) -> "TextRun | list[TextRun]":
        runs = _shape_paragraph_runs(self._shape)[self._paragraph_index]
        if isinstance(index, slice):
            return [
                TextRun(self._shape, self._paragraph_index, run_index)
                for run_index in range(*index.indices(len(runs)))
            ]
        if index < 0:
            index += len(runs)
        if index < 0 or index >= len(runs):
            raise IndexError("run index out of range")
        return TextRun(self._shape, self._paragraph_index, index)

    def __iter__(self) -> Iterator["TextRun"]:
        for index in range(len(self)):
            yield TextRun(self._shape, self._paragraph_index, index)

    def __len__(self) -> int:
        return len(_shape_paragraph_runs(self._shape)[self._paragraph_index])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return [run.text for run in self] == other
        return super().__eq__(other)


class TextRun:
    def __init__(self, shape: Shape, paragraph_index: int, index: int) -> None:
        self._shape = shape
        self._paragraph_index = paragraph_index
        self._index = index

    @property
    def text(self) -> str:
        return _shape_paragraph_runs(self._shape)[self._paragraph_index][self._index]

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        paragraph_runs = _shape_paragraph_runs(self._shape)
        paragraph_runs[self._paragraph_index][self._index] = text
        _sync_shape_text_from_paragraph_runs(self._shape, paragraph_runs)
        _queue_run_state(self._shape, self._paragraph_index, self._index)

    @property
    def font(self) -> "TextRunFont":
        return TextRunFont(self)

    @property
    def hyperlink(self) -> "TextRunHyperlink":
        return TextRunHyperlink(self)


class TextRunHyperlink:
    def __init__(self, run: TextRun) -> None:
        self._run = run

    @property
    def address(self) -> str | None:
        if _is_part_scoped_text_shape(self._run._shape):
            key = (
                self._run._shape._slide.partname,
                self._run._shape._index,
                self._run._paragraph_index,
                self._run._index,
            )
            queued = self._run._shape._slide._presentation._part_run_hyperlink_edits
            if key in queued:
                return queued[key]
        elif _is_group_child_text_shape(self._run._shape):
            group_key = (
                *_group_child_key(self._run._shape),
                self._run._paragraph_index,
                self._run._index,
            )
            queued = (
                self._run._shape._slide._presentation._group_child_run_hyperlink_edits
            )
            if group_key in queued:
                return queued[group_key]
        else:
            key = (
                self._run._shape._slide._index,
                self._run._shape._index,
                self._run._paragraph_index,
                self._run._index,
            )
            queued = self._run._shape._slide._presentation._text_run_hyperlink_edits
            if key in queued:
                return queued[key]
        hyperlinks = _shape_paragraph_run_hyperlink_address(self._run._shape)
        address = hyperlinks[self._run._paragraph_index][self._run._index]
        if address is None:
            address = _shape_text_run_hyperlink_address(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            hyperlinks[self._run._paragraph_index][self._run._index] = address
        return str(address) if address else None

    @property
    def part(self) -> PackagePart:
        return self._run.part

    @address.setter
    def address(self, value: str | None) -> None:
        address = str(value) if value else None
        if address == self.address:
            return
        hyperlinks = _shape_paragraph_run_hyperlink_address(self._run._shape)
        hyperlinks[self._run._paragraph_index][self._run._index] = address
        if _is_part_scoped_text_shape(self._run._shape):
            self._run._shape._slide._presentation._queue_part_run_hyperlink(
                self._run._shape._slide.partname,
                self._run._shape._index,
                self._run._paragraph_index,
                self._run._index,
                address,
            )
        elif _is_group_child_text_shape(self._run._shape):
            self._run._shape._slide._presentation._queue_group_child_run_hyperlink(
                *_group_child_key(self._run._shape),
                self._run._paragraph_index,
                self._run._index,
                address,
            )
        else:
            self._run._shape._slide._presentation._queue_text_run_hyperlink(
                self._run._shape._slide._index,
                self._run._shape._index,
                self._run._paragraph_index,
                self._run._index,
                address,
            )


class TextRunFont:
    def __init__(self, run: TextRun) -> None:
        self._run = run

    @property
    def bold(self) -> bool | None:
        run_bold = _shape_paragraph_run_bold(self._run._shape)
        return run_bold[self._run._paragraph_index][self._run._index]

    @bold.setter
    def bold(self, value: bool | None) -> None:
        bold = None if value is None else bool(value)
        run_bold = _shape_paragraph_run_bold(self._run._shape)
        if bold == run_bold[self._run._paragraph_index][self._run._index]:
            return
        run_bold[self._run._paragraph_index][self._run._index] = bold
        _queue_run_bold_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            bold,
        )

    @property
    def italic(self) -> bool | None:
        run_italic = _shape_paragraph_run_italic(self._run._shape)
        return run_italic[self._run._paragraph_index][self._run._index]

    @italic.setter
    def italic(self, value: bool | None) -> None:
        italic = None if value is None else bool(value)
        run_italic = _shape_paragraph_run_italic(self._run._shape)
        if italic == run_italic[self._run._paragraph_index][self._run._index]:
            return
        run_italic[self._run._paragraph_index][self._run._index] = italic
        _queue_run_italic_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            italic,
        )

    @property
    def underline(self) -> bool | None:
        run_underline = _shape_paragraph_run_underline(self._run._shape)
        return run_underline[self._run._paragraph_index][self._run._index]

    @underline.setter
    def underline(self, value: bool | None) -> None:
        underline = None if value is None else bool(value)
        run_underline = _shape_paragraph_run_underline(self._run._shape)
        if (
            underline is not None
            and underline == run_underline[self._run._paragraph_index][self._run._index]
        ):
            return
        run_underline[self._run._paragraph_index][self._run._index] = underline
        _queue_run_underline_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            underline,
        )

    @property
    def size(self) -> int | None:
        run_size = _shape_paragraph_run_font_size(self._run._shape)
        return run_size[self._run._paragraph_index][self._run._index]

    @size.setter
    def size(self, value: int | None) -> None:
        size = None if value is None else int(value)
        run_size = _shape_paragraph_run_font_size(self._run._shape)
        if (
            size is not None
            and size == run_size[self._run._paragraph_index][self._run._index]
        ):
            return
        run_size[self._run._paragraph_index][self._run._index] = size
        _queue_run_font_size_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            size,
        )

    @property
    def name(self) -> str | None:
        run_name = _shape_paragraph_run_font_name(self._run._shape)
        return run_name[self._run._paragraph_index][self._run._index]

    @name.setter
    def name(self, value: str | None) -> None:
        name = None if value is None else str(value)
        run_name = _shape_paragraph_run_font_name(self._run._shape)
        if (
            name is not None
            and name == run_name[self._run._paragraph_index][self._run._index]
        ):
            return
        run_name[self._run._paragraph_index][self._run._index] = name
        _queue_run_font_name_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            name,
        )

    @property
    def color(self) -> "TextRunColorFormat":
        return TextRunColorFormat(self._run)

    @property
    def fill(self) -> "TextRunFillFormat":
        return TextRunFillFormat(self._run)

    @property
    def language_id(self) -> Any:
        run_language = _shape_paragraph_run_font_language(self._run._shape)
        value = run_language[self._run._paragraph_index][self._run._index]
        if value is None:
            value = _shape_text_run_language_id(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_language[self._run._paragraph_index][self._run._index] = value
        return _language_id_value(value)

    @language_id.setter
    def language_id(self, value: Any) -> None:
        language_id = _normalize_language_id(value)
        run_language = _shape_paragraph_run_font_language(self._run._shape)
        current = run_language[self._run._paragraph_index][self._run._index]
        if current is None:
            current = _shape_text_run_language_id(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_language[self._run._paragraph_index][self._run._index] = current
        if language_id is None and current in (None, _LANGUAGE_ID_NONE):
            return
        if language_id == current:
            return
        run_language[self._run._paragraph_index][self._run._index] = (
            _LANGUAGE_ID_NONE if language_id is None else language_id
        )
        _queue_run_font_language_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            language_id,
        )


def _shape_paragraph_run_font_fill_payload(
    shape: Shape,
) -> list[list[dict[str, Any] | None]]:
    return _shape_paragraph_run_property_matrix(
        shape,
        "paragraph_run_font_fill_payload",
        filter_fn=lambda val: val if isinstance(val, dict) else None,
    )

class TextRunFillFormat:
    def __init__(self, run: TextRun) -> None:
        self._run = run

    def solid(self) -> None:
        if self._fill_type() == "solid":
            return
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        run_fill_types[self._run._paragraph_index][self._run._index] = "solid"
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        run_rgb[self._run._paragraph_index][self._run._index] = None
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        run_theme[self._run._paragraph_index][self._run._index] = None
        self._set_payload({"type": "solid"})
        _queue_run_font_fill_type_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            "solid",
        )

    def background(self) -> None:
        if self._fill_type() == "background":
            return
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        run_fill_types[self._run._paragraph_index][self._run._index] = "background"
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        run_rgb[self._run._paragraph_index][self._run._index] = None
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        run_theme[self._run._paragraph_index][self._run._index] = None
        self._set_payload({"type": "background"})
        _queue_run_font_fill_type_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            "background",
        )

    def patterned(self) -> None:
        if self._fill_type() == "patterned":
            return
        payload = {"type": "patterned", "pattern": None}
        self._queue_payload(payload)

    def gradient(self) -> None:
        if self._fill_type() == "gradient":
            return
        payload = {"type": "gradient", "gradient": _default_gradient_payload()}
        self._queue_payload(payload)

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> "TextRunFillColorFormat":
        return TextRunFillColorFormat(self._run, "fore")

    @property
    def back_color(self) -> "TextRunFillColorFormat":
        return TextRunFillColorFormat(self._run, "back")

    @property
    def pattern(self) -> Any:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(self._payload().get("pattern"))

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        payload = self._payload()
        if payload.get("pattern") == pattern:
            return
        payload["pattern"] = pattern
        self._queue_payload(payload)

    @property
    def gradient_angle(self) -> float | None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        return gradient.get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if self._fill_type() != "gradient":
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
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return _GradientStops(self)

    def _fill_type(self) -> str | None:
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        value = run_fill_types[self._run._paragraph_index][self._run._index]
        if value is None:
            value = _shape_text_run_fill_type(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_fill_types[self._run._paragraph_index][self._run._index] = value
        return value

    def _payload(self) -> dict[str, Any]:
        payloads = _shape_paragraph_run_font_fill_payload(self._run._shape)
        payload = payloads[self._run._paragraph_index][self._run._index]
        if isinstance(payload, dict):
            return payload
        fill_type = self._fill_type()
        payload = {"type": fill_type}
        if fill_type == "patterned":
            payload["pattern"] = _shape_text_run_pattern(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            payload["pattern_fore_rgb"] = _shape_text_run_pattern_rgb(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
                "fgClr",
            )
            payload["pattern_back_rgb"] = _shape_text_run_pattern_rgb(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
                "bgClr",
            )
        elif fill_type == "gradient":
            payload["gradient"] = (
                _shape_text_run_gradient_payload(
                    self._run._shape,
                    self._run._paragraph_index,
                    self._run._index,
                )
                or _default_gradient_payload()
            )
        payloads[self._run._paragraph_index][self._run._index] = payload
        return payload

    def _set_payload(self, payload: dict[str, Any]) -> None:
        payloads = _shape_paragraph_run_font_fill_payload(self._run._shape)
        payloads[self._run._paragraph_index][self._run._index] = payload

    def _queue_payload(self, payload: dict[str, Any]) -> None:
        payload = deepcopy(payload)
        self._set_payload(payload)
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        run_fill_types[self._run._paragraph_index][self._run._index] = payload.get(
            "type"
        )
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        run_rgb[self._run._paragraph_index][self._run._index] = None
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        run_theme[self._run._paragraph_index][self._run._index] = None
        _queue_run_font_fill_type_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            payload,
        )

    def _gradient_payload(self) -> dict[str, Any]:
        payload = self._payload()
        gradient = payload.get("gradient")
        if not isinstance(gradient, dict):
            gradient = _default_gradient_payload()
            payload["gradient"] = gradient
        return gradient

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        payload = self._payload()
        payload["type"] = "gradient"
        payload["gradient"] = gradient
        self._queue_payload(payload)


class TextRunFillColorFormat:
    def __init__(self, run: TextRun, target: str) -> None:
        self._run = run
        self._target = target

    @property
    def rgb(self) -> Any:
        fill = TextRunFillFormat(self._run)
        if fill._fill_type() == "patterned":
            key = (
                "pattern_back_rgb"
                if self._target == "back"
                else "pattern_fore_rgb"
            )
            rgb = fill._payload().get(key)
            return None if rgb is None else _rgb_value(rgb)
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        return TextRunColorFormat(self._run).rgb

    @rgb.setter
    def rgb(self, value: Any) -> None:
        fill = TextRunFillFormat(self._run)
        rgb = _normalize_rgb(value)
        if fill._fill_type() == "patterned":
            key = (
                "pattern_back_rgb"
                if self._target == "back"
                else "pattern_fore_rgb"
            )
            payload = fill._payload()
            if payload.get(key) == rgb:
                return
            payload[key] = rgb
            fill._queue_payload(payload)
            return
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        TextRunColorFormat(self._run).rgb = rgb


class TextRunColorFormat:
    def __init__(self, run: TextRun) -> None:
        self._run = run

    @property
    def rgb(self) -> Any:
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        rgb = run_rgb[self._run._paragraph_index][self._run._index]
        if rgb is None:
            rgb = _shape_text_run_rgb(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_rgb[self._run._paragraph_index][self._run._index] = rgb
        if rgb is None:
            return None
        return _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        current = run_rgb[self._run._paragraph_index][self._run._index]
        if current is None:
            current = _shape_text_run_rgb(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_rgb[self._run._paragraph_index][self._run._index] = current
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        fill_type = run_fill_types[self._run._paragraph_index][self._run._index]
        if fill_type is None:
            fill_type = _shape_text_run_fill_type(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_fill_types[self._run._paragraph_index][self._run._index] = fill_type
        if current == rgb and fill_type == "solid":
            return
        run_rgb[self._run._paragraph_index][self._run._index] = rgb
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        run_theme[self._run._paragraph_index][self._run._index] = None
        run_fill_types[self._run._paragraph_index][self._run._index] = "solid"
        _queue_run_font_color_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            rgb,
        )

    @property
    def theme_color(self) -> Any:
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        value = run_theme[self._run._paragraph_index][self._run._index]
        if value is None:
            value = _shape_text_run_theme_color(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_theme[self._run._paragraph_index][self._run._index] = value
        return _theme_color_value("" if value is None else value)

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        theme_color = _normalize_theme_color(value)
        run_theme = _shape_paragraph_run_font_theme_color(self._run._shape)
        current = run_theme[self._run._paragraph_index][self._run._index]
        if current is None:
            current = _shape_text_run_theme_color(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_theme[self._run._paragraph_index][self._run._index] = current
        run_fill_types = _shape_paragraph_run_font_fill_type(self._run._shape)
        fill_type = run_fill_types[self._run._paragraph_index][self._run._index]
        if fill_type is None:
            fill_type = _shape_text_run_fill_type(
                self._run._shape,
                self._run._paragraph_index,
                self._run._index,
            )
            run_fill_types[self._run._paragraph_index][self._run._index] = fill_type
        if current == theme_color and fill_type == "solid":
            return
        run_theme[self._run._paragraph_index][self._run._index] = theme_color
        run_rgb = _shape_paragraph_run_font_rgb(self._run._shape)
        run_rgb[self._run._paragraph_index][self._run._index] = None
        run_fill_types[self._run._paragraph_index][self._run._index] = "solid"
        _queue_run_font_color_state(
            self._run._shape,
            self._run._paragraph_index,
            self._run._index,
            {"type": "scheme", "value": theme_color},
        )
