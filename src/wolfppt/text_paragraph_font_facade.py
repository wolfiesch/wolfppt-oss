"""Paragraph-level text font facade helpers."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .dml.color import ColorTextAndTransforms, fill_color_element
from .dml_fill import A_NS, gradient_payload_from_fill_parent
from .dml_fill import brightness_from_color_element as _brightness_from_color_element
from .dml_fill import default_gradient_payload as _default_gradient_payload
from .dml_fill import set_color_brightness as _set_color_brightness
from .dml_fill import validate_text_color_element as _validate_text_color_element
from .facade_values import (
    LANGUAGE_ID_NONE as _LANGUAGE_ID_NONE,
)
from .facade_values import (
    fill_type_value as _fill_type_value,
)
from .facade_values import (
    language_id_value as _language_id_value,
)
from .facade_values import (
    normalize_language_id as _normalize_language_id,
)
from .facade_values import (
    normalize_pattern_type as _normalize_pattern_type,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_theme_color as _normalize_theme_color,
)
from .facade_values import (
    pattern_type_value as _pattern_type_value,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .facade_values import (
    theme_color_value as _theme_color_value,
)
from .shape_format_facade import GradientStops as _GradientStops
from .shape_payloads import (
    _set_shape_paragraph_font_payload,
)
from .text_facade_inspection import (
    _shape_paragraph_font_bold,
    _shape_paragraph_font_fill_type,
    _shape_paragraph_font_italic,
    _shape_paragraph_font_language,
    _shape_paragraph_font_name,
    _shape_paragraph_font_rgb,
    _shape_paragraph_font_size,
    _shape_paragraph_font_strike,
    _shape_text_paragraph_default_run_properties,
    _shape_text_paragraph_font_gradient_payload,
    _shape_text_paragraph_font_pattern,
    _shape_text_paragraph_font_pattern_rgb,
    _shape_text_paragraph_font_theme_color,
)
from .text_facade_queue import _queue_paragraph_font_state
from .text_run_facade import (
    _normalize_underline,
    _text_color_type,
    _underline_queue_value,
    _underline_value,
)

if TYPE_CHECKING:
    from .text_facade import TextParagraph


class TextParagraphFont:
    def __init__(self, paragraph: TextParagraph) -> None:
        self._paragraph = paragraph

    @property
    def bold(self) -> bool | None:
        return _shape_paragraph_font_bold(
            self._paragraph._shape,
            self._paragraph._index,
        )

    @bold.setter
    def bold(self, value: bool | None) -> None:
        bold = None if value is None else bool(value)
        if bold == self.bold:
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_bold",
            bold,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "bold",
            bold,
        )

    @property
    def italic(self) -> bool | None:
        return _shape_paragraph_font_italic(
            self._paragraph._shape,
            self._paragraph._index,
        )

    @italic.setter
    def italic(self, value: bool | None) -> None:
        italic = None if value is None else bool(value)
        if italic == self.italic:
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_italic",
            italic,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "italic",
            italic,
        )

    @property
    def underline(self) -> Any:
        return _underline_value(self._underline_token())

    @underline.setter
    def underline(self, value: Any) -> None:
        token = _normalize_underline(value)
        if token == self._underline_token():
            return
        underline = _underline_queue_value(token)
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_underline",
            underline,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "underline",
            underline,
        )

    def _underline_token(self) -> str | None:
        default_run_properties = _shape_text_paragraph_default_run_properties(
            self._paragraph._shape,
            self._paragraph._index,
        )
        if default_run_properties is None:
            return None
        return default_run_properties.get("u")

    @property
    def strike(self) -> bool | None:
        return _shape_paragraph_font_strike(
            self._paragraph._shape,
            self._paragraph._index,
        )

    @strike.setter
    def strike(self, value: bool | None) -> None:
        strike = None if value is None else bool(value)
        if strike == self.strike:
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_strike",
            strike,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "strike",
            strike,
        )

    @property
    def size(self) -> int | None:
        return _shape_paragraph_font_size(
            self._paragraph._shape,
            self._paragraph._index,
        )

    @size.setter
    def size(self, value: int | None) -> None:
        size = None if value is None else int(value)
        if size == self.size:
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_size",
            size,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "size",
            size,
        )

    @property
    def name(self) -> str | None:
        return _shape_paragraph_font_name(
            self._paragraph._shape,
            self._paragraph._index,
        )

    @name.setter
    def name(self, value: str | None) -> None:
        name = None if value is None else str(value)
        if name == self.name:
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_name",
            name,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "name",
            name,
        )

    @property
    def color(self) -> TextParagraphFontColorFormat:
        return TextParagraphFontColorFormat(self._paragraph)

    @property
    def fill(self) -> TextParagraphFontFillFormat:
        return TextParagraphFontFillFormat(self._paragraph)

    @property
    def language_id(self) -> Any:
        value = _shape_paragraph_font_language(
            self._paragraph._shape,
            self._paragraph._index,
        )
        return _language_id_value(value)

    @language_id.setter
    def language_id(self, value: Any) -> None:
        language_id = _normalize_language_id(value)
        current = _shape_paragraph_font_language(
            self._paragraph._shape,
            self._paragraph._index,
        )
        if language_id is None and current in (None, _LANGUAGE_ID_NONE):
            return
        if language_id == current:
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_language",
            _LANGUAGE_ID_NONE if language_id is None else language_id,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "language_id",
            language_id,
        )


class TextParagraphFontFillFormat:
    def __init__(self, paragraph: TextParagraph) -> None:
        self._paragraph = paragraph

    def solid(self) -> None:
        if (
            _shape_paragraph_font_fill_type(
                self._paragraph._shape,
                self._paragraph._index,
            )
            == "solid"
        ):
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_fill_type",
            "solid",
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_rgb",
            None,
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_theme_color",
            None,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "fill_type",
            "solid",
        )

    def background(self) -> None:
        if (
            _shape_paragraph_font_fill_type(
                self._paragraph._shape,
                self._paragraph._index,
            )
            == "background"
        ):
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_fill_type",
            "background",
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_rgb",
            None,
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_theme_color",
            None,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "fill_type",
            "background",
        )

    def patterned(self) -> None:
        if self._fill_type() == "patterned":
            return
        self._queue_payload({"type": "patterned", "pattern": None})

    def gradient(self) -> None:
        if self._fill_type() == "gradient":
            return
        self._queue_payload({"type": "gradient", "gradient": _default_gradient_payload()})

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> TextParagraphFontColorFormat:
        return TextParagraphFontColorFormat(self._paragraph, "fore")

    @property
    def back_color(self) -> TextParagraphFontColorFormat:
        return TextParagraphFontColorFormat(self._paragraph, "back")

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
        return _shape_paragraph_font_fill_type(
            self._paragraph._shape,
            self._paragraph._index,
        )

    def _payload(self) -> dict[str, Any]:
        fill_type = self._fill_type()
        payload = {"type": fill_type}
        if fill_type == "patterned":
            payload["pattern"] = _shape_text_paragraph_font_pattern(
                self._paragraph._shape,
                self._paragraph._index,
            )
            payload["pattern_fore_rgb"] = _shape_text_paragraph_font_pattern_rgb(
                self._paragraph._shape,
                self._paragraph._index,
                "fgClr",
            )
            payload["pattern_back_rgb"] = _shape_text_paragraph_font_pattern_rgb(
                self._paragraph._shape,
                self._paragraph._index,
                "bgClr",
            )
        elif fill_type == "gradient":
            payload["gradient"] = (
                _shape_text_paragraph_font_gradient_payload(
                    self._paragraph._shape,
                    self._paragraph._index,
                )
                or _default_gradient_payload()
            )
        return payload

    def _queue_payload(self, payload: dict[str, Any]) -> None:
        payload = deepcopy(payload)
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_fill_type",
            payload.get("type"),
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_rgb",
            None,
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_theme_color",
            None,
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "fill_type",
            payload,
        )

    def _gradient_payload(self) -> dict[str, Any]:
        properties = _shape_text_paragraph_default_run_properties(
            self._paragraph._shape, self._paragraph._index
        )
        token = None if properties is None else ET.tostring(properties)
        # GradientStop mutators fetch, mutate, then fetch again before queuing.
        # Keep that working object only while the effective source is unchanged.
        if not hasattr(self, "_gradient_source") or self._gradient_source != token:
            self._gradient_source = token
            self._gradient_state = (
                None if properties is None else gradient_payload_from_fill_parent(properties)
            ) or _default_gradient_payload()
        return self._gradient_state

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        payload = self._payload()
        payload["type"] = "gradient"
        payload["gradient"] = gradient
        self._queue_payload(payload)


class TextParagraphFontColorFormat(ColorTextAndTransforms):
    def __init__(self, paragraph: TextParagraph, target: str = "font") -> None:
        self._paragraph = paragraph
        self._target = target

    def _set_color_element(self, color: ET.Element) -> None:
        self._queue_color(color)

    @property
    def rgb(self) -> Any:
        fill = TextParagraphFontFillFormat(self._paragraph)
        if fill._fill_type() == "patterned" and self._target in {"fore", "back"}:
            key = "pattern_back_rgb" if self._target == "back" else "pattern_fore_rgb"
            rgb = fill._payload().get(key)
            return None if rgb is None else _rgb_value(rgb)
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        rgb = _shape_paragraph_font_rgb(
            self._paragraph._shape,
            self._paragraph._index,
        )
        if rgb is None:
            return None
        return _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        fill = TextParagraphFontFillFormat(self._paragraph)
        rgb = _normalize_rgb(value)
        if fill._fill_type() == "patterned" and self._target in {"fore", "back"}:
            key = "pattern_back_rgb" if self._target == "back" else "pattern_fore_rgb"
            payload = fill._payload()
            if payload.get(key) == rgb:
                return
            payload[key] = rgb
            fill._queue_payload(payload)
            return
        if self._target == "back":
            raise TypeError("fill is not patterned, call .patterned() first")
        if (
            _shape_paragraph_font_rgb(self._paragraph._shape, self._paragraph._index) == rgb
            and _shape_paragraph_font_fill_type(
                self._paragraph._shape,
                self._paragraph._index,
            )
            == "solid"
        ):
            return
        existing = self._color_element()
        if existing is not None and existing.tag == f"{{{A_NS}}}srgbClr" and len(existing):
            # Same-type change keeps luminance transforms, as python-pptx does.
            color = deepcopy(existing)
            color.set("val", rgb)
            self._queue_color(color)
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_rgb",
            rgb,
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_theme_color",
            None,
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_fill_type",
            "solid",
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "color",
            rgb,
        )

    @property
    def theme_color(self) -> Any:
        value = _shape_text_paragraph_font_theme_color(
            self._paragraph._shape, self._paragraph._index
        )
        return _theme_color_value("" if value is None else value)

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        theme_color = _normalize_theme_color(value)
        current = _shape_text_paragraph_font_theme_color(
            self._paragraph._shape, self._paragraph._index
        )
        if (
            current == theme_color
            and _shape_paragraph_font_fill_type(
                self._paragraph._shape,
                self._paragraph._index,
            )
            == "solid"
        ):
            return
        existing = self._color_element()
        if existing is not None and existing.tag == f"{{{A_NS}}}schemeClr" and len(existing):
            # Same-type change keeps luminance transforms, as python-pptx does.
            color = deepcopy(existing)
            color.set("val", theme_color)
            self._queue_color(color)
            return
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_theme_color",
            theme_color,
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_rgb",
            None,
        )
        _set_shape_paragraph_font_payload(
            self._paragraph._shape,
            self._paragraph._index,
            "paragraph_font_fill_type",
            "solid",
        )
        _queue_paragraph_font_state(
            self._paragraph._shape,
            self._paragraph._index,
            "color",
            {"type": "scheme", "value": theme_color},
        )

    @property
    def type(self) -> Any:
        return _text_color_type(self._color_element())

    @property
    def brightness(self) -> float:
        color = self._color_element()
        return 0.0 if color is None else _brightness_from_color_element(color)

    @brightness.setter
    def brightness(self, value: Any) -> None:
        brightness = float(value)
        if not math.isfinite(brightness) or not -1.0 <= brightness <= 1.0:
            raise ValueError("brightness must be a finite number between -1.0 and 1.0")
        color = self._color_element()
        if color is None:
            raise ValueError("brightness requires an explicit solid text color")
        color = deepcopy(color)
        _set_color_brightness(color, brightness)
        self._queue_color(color)

    def _is_patterned(self) -> bool:
        return (
            _shape_paragraph_font_fill_type(self._paragraph._shape, self._paragraph._index)
            == "patterned"
        )

    def _color_element(self) -> ET.Element | None:
        """Read the selected color from the owner-aware effective paragraph XML."""
        properties = _shape_text_paragraph_default_run_properties(
            self._paragraph._shape, self._paragraph._index
        )
        return fill_color_element(properties, "back" if self._target == "back" else "fore")

    def _queue_color(self, color: ET.Element) -> None:
        _validate_text_color_element(color)
        if self._is_patterned():
            fill = TextParagraphFontFillFormat(self._paragraph)
            payload = fill._payload()
            properties = _shape_text_paragraph_default_run_properties(
                self._paragraph._shape, self._paragraph._index
            )
            for role in ("fore", "back"):
                existing = fill_color_element(properties, role)
                if existing is not None:
                    payload[f"pattern_{role}_color"] = deepcopy(existing)
            role = "back" if self._target == "back" else "fore"
            payload[f"pattern_{role}_color"] = deepcopy(color)
            payload.pop(f"pattern_{role}_rgb", None)
            fill._queue_payload(payload)
            return
        shape, index = self._paragraph._shape, self._paragraph._index
        is_rgb = color.tag == f"{{{A_NS}}}srgbClr"
        is_scheme = color.tag == f"{{{A_NS}}}schemeClr"
        _set_shape_paragraph_font_payload(
            shape, index, "paragraph_font_rgb", color.get("val") if is_rgb else None
        )
        _set_shape_paragraph_font_payload(
            shape,
            index,
            "paragraph_font_theme_color",
            color.get("val") if is_scheme else None,
        )
        _set_shape_paragraph_font_payload(shape, index, "paragraph_font_fill_type", "solid")
        _queue_paragraph_font_state(
            shape,
            index,
            "color",
            {"type": "xml", "value": ET.tostring(color, encoding="unicode")},
        )
