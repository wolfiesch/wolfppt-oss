"""Facade helpers for chart point data-label run formatting."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .chart_data_label_run_xml import (
    data_label_run_fill_type as _data_label_run_fill_type,
    data_label_run_font_name as _data_label_run_font_name,
    data_label_run_gradient_payload as _data_label_run_gradient_payload,
    data_label_run_pattern as _data_label_run_pattern,
    data_label_run_pattern_rgb as _data_label_run_pattern_rgb,
    data_label_run_properties as _data_label_run_properties,
    data_label_run_rgb as _data_label_run_rgb,
    set_data_label_run_font as _set_data_label_run_font,
)
from .dml_fill import default_gradient_payload as _default_gradient_payload
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


class DataLabelRunHyperlink:
    @property
    def address(self) -> None:
        return None

    @address.setter
    def address(self, value: str | None) -> None:
        raise AttributeError("'DataLabel' object has no attribute 'part'")

    @property
    def part(self) -> None:
        raise AttributeError("'DataLabel' object has no attribute 'part'")


class DataLabelRunFont:
    def __init__(self, run: Any) -> None:
        self._run = run

    @property
    def bold(self) -> bool | None:
        value = _data_label_run_properties(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ).get("b")
        return None if value is None else value in {"1", "true"}

    @bold.setter
    def bold(self, value: bool | None) -> None:
        bold = None if value is None else bool(value)
        if bold == self.bold:
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"bold": bold},
        )
        self._run._queue_font({"bold": bold})

    @property
    def italic(self) -> bool | None:
        value = _data_label_run_properties(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ).get("i")
        return None if value is None else value in {"1", "true"}

    @italic.setter
    def italic(self, value: bool | None) -> None:
        italic = None if value is None else bool(value)
        if italic == self.italic:
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"italic": italic},
        )
        self._run._queue_font({"italic": italic})

    @property
    def underline(self) -> bool | None:
        value = _data_label_run_properties(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ).get("u")
        return None if value is None else value != "none"

    @underline.setter
    def underline(self, value: bool | None) -> None:
        underline = None if value is None else bool(value)
        if underline == self.underline:
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"underline": underline},
        )
        self._run._queue_font({"underline": underline})

    @property
    def size(self) -> int | None:
        value = _data_label_run_properties(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ).get("sz")
        return None if value is None else _centipoints_value(int(value))

    @size.setter
    def size(self, value: int | None) -> None:
        size = None if value is None else int(value)
        if size == self.size:
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"size": size},
        )
        self._run._queue_font({"size": size})

    @property
    def color(self) -> "DataLabelRunColorFormat":
        return DataLabelRunColorFormat(self._run)

    @property
    def fill(self) -> "DataLabelRunFontFillFormat":
        payload = self._run._label.__dict__.setdefault(
            "_run_font_fill_payloads",
            {},
        ).setdefault((self._run._paragraph_index, self._run._index), {})
        return DataLabelRunFontFillFormat(self._run, payload)

    @property
    def name(self) -> str | None:
        return _data_label_run_font_name(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        )

    @name.setter
    def name(self, value: str | None) -> None:
        name = None if value is None else str(value)
        if name == self.name:
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"name": name},
        )
        self._run._queue_font({"name": name})

    @property
    def language_id(self) -> Any:
        return _language_id_value(
            _data_label_run_properties(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            ).get("lang")
        )

    @language_id.setter
    def language_id(self, value: Any) -> None:
        language_id = _normalize_language_id(value)
        if language_id == _normalize_language_id(self.language_id):
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"language_id": language_id},
        )
        self._run._queue_font({"language_id": language_id})


class DataLabelRunColorFormat:
    def __init__(self, run: Any) -> None:
        self._run = run

    @property
    def rgb(self) -> Any:
        rgb = _data_label_run_rgb(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        )
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if _data_label_run_rgb(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ) == rgb:
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"rgb": rgb},
        )
        self._run._queue_font({"rgb": rgb})


class DataLabelRunFontFillFormat:
    def __init__(self, run: Any, payload: dict[str, Any]) -> None:
        self._run = run
        self._payload = payload

    def solid(self) -> None:
        if _data_label_run_fill_type(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ) == "solid":
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"fill_type": "solid"},
        )
        self._run._queue_font({"fill_type": "solid"})

    def background(self) -> None:
        if _data_label_run_fill_type(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ) == "background":
            return
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            {"fill_type": "background"},
        )
        self._run._queue_font({"fill_type": "background"})

    def patterned(self) -> None:
        if _data_label_run_fill_type(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ) == "patterned":
            return
        self._queue_fill({"fill_type": "patterned"})

    def gradient(self) -> None:
        if _data_label_run_fill_type(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ) == "gradient":
            return
        self._payload["gradient"] = _default_gradient_payload()
        self._queue_fill(
            {"fill_type": "gradient", "gradient": self._payload["gradient"]}
        )

    @property
    def type(self) -> Any:
        return _fill_type_value(
            _data_label_run_fill_type(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
        )

    @property
    def fore_color(self) -> "DataLabelRunFontFillColorFormat":
        return DataLabelRunFontFillColorFormat(self._run, "fore")

    @property
    def back_color(self) -> "DataLabelRunFontFillColorFormat":
        return DataLabelRunFontFillColorFormat(self._run, "back")

    @property
    def pattern(self) -> Any:
        if (
            _data_label_run_fill_type(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
            != "patterned"
        ):
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(
            _data_label_run_pattern(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
        )

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if (
            _data_label_run_fill_type(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
            != "patterned"
        ):
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern != _data_label_run_pattern(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
        ):
            self._queue_fill({"pattern": pattern})

    @property
    def gradient_angle(self) -> float | None:
        if (
            _data_label_run_fill_type(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
            != "gradient"
        ):
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        return gradient.get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if (
            _data_label_run_fill_type(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
            != "gradient"
        ):
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
        if (
            _data_label_run_fill_type(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
            != "gradient"
        ):
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return _GradientStops(self)

    def _gradient_payload(self) -> dict[str, Any]:
        gradient = self._payload.get("gradient")
        if not isinstance(gradient, dict):
            gradient = (
                _data_label_run_gradient_payload(
                    self._run._label,
                    self._run._paragraph_index,
                    self._run._index,
                )
                or _default_gradient_payload()
            )
            self._payload["gradient"] = gradient
        return gradient

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        self._payload["gradient"] = gradient
        self._queue_fill({"fill_type": "gradient", "gradient": gradient})

    def _queue_fill(self, properties: dict[str, Any]) -> None:
        queued = deepcopy(properties)
        _set_data_label_run_font(
            self._run._label,
            self._run._paragraph_index,
            self._run._index,
            queued,
        )
        self._run._queue_font(queued)


class DataLabelRunFontFillColorFormat:
    def __init__(self, run: Any, target: str) -> None:
        self._run = run
        self._target = target

    @property
    def rgb(self) -> Any:
        if (
            _data_label_run_fill_type(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
            == "patterned"
        ):
            rgb = _data_label_run_pattern_rgb(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
                "bgClr" if self._target == "back" else "fgClr",
            )
            return None if rgb is None else _rgb_value(rgb)
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        return DataLabelRunColorFormat(self._run).rgb

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if (
            _data_label_run_fill_type(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
            )
            == "patterned"
        ):
            color_tag = "bgClr" if self._target == "back" else "fgClr"
            if rgb != _data_label_run_pattern_rgb(
                self._run._label,
                self._run._paragraph_index,
                self._run._index,
                color_tag,
            ):
                key = (
                    "pattern_back_rgb"
                    if self._target == "back"
                    else "pattern_fore_rgb"
                )
                _set_data_label_run_font(
                    self._run._label,
                    self._run._paragraph_index,
                    self._run._index,
                    {key: rgb},
                )
                self._run._queue_font({key: rgb})
            return
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        DataLabelRunColorFormat(self._run).rgb = rgb
