"""Shape fill, line, shadow, and color formatting facade."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
    gradient_stop_element as _gradient_stop_element,
    set_shape_gradient_fill as _set_shape_gradient_fill,
    set_shape_no_fill as _set_shape_no_fill,
    set_shape_pattern_fill as _set_shape_pattern_fill,
    set_shape_solid_fill as _set_shape_solid_fill,
)
from .facade_values import (
    coerce_emu as _coerce_emu,
    color_type_value as _color_type_value,
    emu_value as _emu_value,
    fill_type_value as _fill_type_value,
    line_dash_style_value as _line_dash_style_value,
    normalize_line_dash_style as _normalize_line_dash_style,
    normalize_pattern_type as _normalize_pattern_type,
    normalize_rgb as _normalize_rgb,
    normalize_theme_color as _normalize_theme_color,
    pattern_type_value as _pattern_type_value,
    rgb_value as _rgb_value,
    theme_color_value as _theme_color_value,
)
from .shape_format_inspection import (
    _detached_fill_parent,
    _shape_fill_pattern,
    _shape_fill_type,
    _shape_gradient_fill_payload,
    _shape_line_dash_style,
    _shape_line_fill_pattern,
    _shape_line_fill_type,
    _shape_line_width,
    _shape_pattern_rgb,
    _shape_style_color_payload,
    _shape_shadow_inherit,
    _shape_style_rgb,
    _supports_shape_line_style,
)
from .shape_edit_refs import (
    ShapeEditRef,
    shape_edit_ref as _shape_edit_ref,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _shape_style_ref(shape: Any) -> ShapeEditRef:
    return _shape_edit_ref(shape)


class FillFormat:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @classmethod
    def from_fill_parent(cls, eg_fillProperties_parent: Any) -> "FillFormat":
        return cls(_DetachedFillShape(eg_fillProperties_parent))

    def solid(self) -> None:
        if self._fill_type() == "solid":
            return
        self._shape._payload["fill_type"] = "solid"
        self._shape._payload.pop("fill_rgb", None)
        self._shape._payload.pop("fill_pattern", None)
        self._shape._payload.pop("fill_pattern_fore_rgb", None)
        self._shape._payload.pop("fill_pattern_back_rgb", None)
        self._shape._payload.pop("fill_gradient", None)
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_solid_fill(detached_parent)
            return
        self._shape._slide._presentation._queue_shape_fill_solid(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
        )

    def background(self) -> None:
        if self._fill_type() == "background":
            return
        self._shape._payload["fill_type"] = "background"
        self._shape._payload.pop("fill_rgb", None)
        self._shape._payload.pop("fill_pattern", None)
        self._shape._payload.pop("fill_pattern_fore_rgb", None)
        self._shape._payload.pop("fill_pattern_back_rgb", None)
        self._shape._payload.pop("fill_gradient", None)
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_no_fill(detached_parent)
            return
        self._shape._slide._presentation._queue_shape_fill_background(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
        )

    def patterned(self) -> None:
        if self._fill_type() == "patterned":
            return
        pattern = None
        self._shape._payload["fill_type"] = "patterned"
        self._shape._payload.pop("fill_rgb", None)
        self._shape._payload["fill_pattern"] = pattern
        self._shape._payload.pop("fill_gradient", None)
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_pattern_fill(detached_parent, pattern)
            return
        self._shape._slide._presentation._queue_shape_fill_patterned(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            pattern,
        )

    def gradient(self) -> None:
        if self._fill_type() == "gradient":
            return
        gradient = _default_gradient_payload()
        self._shape._payload["fill_type"] = "gradient"
        self._shape._payload.pop("fill_rgb", None)
        self._shape._payload.pop("fill_pattern", None)
        self._shape._payload.pop("fill_pattern_fore_rgb", None)
        self._shape._payload.pop("fill_pattern_back_rgb", None)
        self._shape._payload["fill_gradient"] = gradient
        self._queue_gradient(gradient)

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> "ColorFormat":
        return ColorFormat(self._shape, "fill_fore")

    @property
    def back_color(self) -> "ColorFormat":
        return ColorFormat(self._shape, "fill_back")

    @property
    def pattern(self) -> Any:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(self._pattern_raw())

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern == self._pattern_raw():
            return
        self._shape._payload["fill_pattern"] = pattern
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_pattern_fill(detached_parent, pattern)
            return
        self._shape._slide._presentation._queue_shape_fill_patterned(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            pattern,
        )

    @property
    def gradient_angle(self) -> float | None:
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return self._gradient_payload().get("angle")

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
    def gradient_stops(self) -> "GradientStops":
        if self._fill_type() != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return GradientStops(self)

    def _fill_type(self) -> str | None:
        if "fill_type" not in self._shape._payload:
            self._shape._payload["fill_type"] = _shape_fill_type(self._shape)
        return self._shape._payload["fill_type"]

    def _pattern_raw(self) -> str | None:
        if "fill_pattern" not in self._shape._payload:
            self._shape._payload["fill_pattern"] = _shape_fill_pattern(self._shape)
        return self._shape._payload["fill_pattern"]

    def _gradient_payload(self) -> dict[str, Any]:
        if "fill_gradient" not in self._shape._payload:
            payload = _shape_gradient_fill_payload(self._shape)
            if payload is None:
                payload = _default_gradient_payload()
            self._shape._payload["fill_gradient"] = payload
        return self._shape._payload["fill_gradient"]

    def _queue_gradient(self, gradient: dict[str, Any]) -> None:
        detached_parent = _detached_fill_parent(self._shape)
        if detached_parent is not None:
            _set_shape_gradient_fill(detached_parent, gradient)
            return
        self._shape._slide._presentation._queue_shape_fill_gradient(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            gradient,
        )


class GradientStops(Sequence):
    def __init__(self, fill: FillFormat) -> None:
        self._fill = fill

    def __getitem__(self, index: int) -> "GradientStop":
        stops = self._stops()
        if index < 0:
            index += len(stops)
        if index < 0 or index >= len(stops):
            raise IndexError("gradient stop index out of range")
        return GradientStop(self._fill, index)

    def __len__(self) -> int:
        return len(self._stops())

    def _stops(self) -> list[dict[str, Any]]:
        return self._fill._gradient_payload().setdefault("stops", [])


class GradientStop:
    def __init__(self, fill: FillFormat, index: int) -> None:
        self._fill = fill
        self._index = index

    @property
    def color(self) -> "GradientStopColorFormat":
        return GradientStopColorFormat(self)

    @property
    def element(self) -> ET.Element:
        return _gradient_stop_element(self._stop())

    @property
    def position(self) -> float:
        return float(self._stop().get("position", 0.0))

    @position.setter
    def position(self, value: Any) -> None:
        position = float(value)
        if self.position == position:
            return
        self._stop()["position"] = position
        self._fill._queue_gradient(self._fill._gradient_payload())

    def _stop(self) -> dict[str, Any]:
        return self._fill._gradient_payload()["stops"][self._index]


class GradientStopColorFormat:
    def __init__(self, stop: GradientStop) -> None:
        self._stop = stop

    @property
    def brightness(self) -> float:
        return 0

    @brightness.setter
    def brightness(self, value: Any) -> None:
        if not -1.0 <= float(value) <= 1.0:
            raise ValueError("brightness must be between -1.0 and 1.0")

    @property
    def rgb(self) -> Any:
        color = self._color_element()
        if color.tag != f"{{{A_NS}}}srgbClr":
            raise AttributeError("no .rgb property on color type '_SchemeColor'")
        value = color.attrib.get("val")
        return None if value is None else _rgb_value(value.upper())

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        color = self._color_element()
        if color.tag == f"{{{A_NS}}}srgbClr" and color.attrib.get("val") == rgb:
            return
        color = ET.Element(f"{{{A_NS}}}srgbClr")
        color.set("val", rgb)
        self._stop._stop()["color"] = color
        self._stop._fill._queue_gradient(self._stop._fill._gradient_payload())

    @property
    def theme_color(self) -> Any:
        color = self._color_element()
        if color.tag != f"{{{A_NS}}}schemeClr":
            return _theme_color_value("")
        return _theme_color_value(color.attrib.get("val", ""))

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        xml_value = _normalize_theme_color(value)
        color = self._color_element()
        if (
            color.tag == f"{{{A_NS}}}schemeClr"
            and color.attrib.get("val") == xml_value
        ):
            return
        color = ET.Element(f"{{{A_NS}}}schemeClr")
        color.set("val", xml_value)
        self._stop._stop()["color"] = color
        self._stop._fill._queue_gradient(self._stop._fill._gradient_payload())

    @property
    def type(self) -> Any:
        color = self._color_element()
        if color.tag == f"{{{A_NS}}}srgbClr":
            return _color_type_value("rgb")
        if color.tag == f"{{{A_NS}}}schemeClr":
            return _color_type_value("scheme")
        return None

    def _color_element(self) -> ET.Element:
        color = self._stop._stop().get("color")
        if isinstance(color, ET.Element):
            return color
        return ET.Element(f"{{{A_NS}}}schemeClr", {"val": "accent1"})


class _DetachedFillShape:
    def __init__(self, fill_parent: Any) -> None:
        element = getattr(fill_parent, "_element", fill_parent)
        if not hasattr(element, "find") or not hasattr(element, "insert"):
            raise TypeError("fill parent must be an XML element")
        self._payload = {"kind": "shape", "fill_parent": element}


class LineFormat:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @property
    def color(self) -> "ColorFormat":
        return ColorFormat(self._shape, "line")

    @property
    def fill(self) -> "LineFillFormat":
        return LineFillFormat(self._shape)

    @property
    def width(self) -> Any:
        raw = self._shape._payload.get("line_width")
        if not isinstance(raw, int):
            raw = _shape_line_width(self._shape)
            self._shape._payload["line_width"] = raw
        return _emu_value(raw)

    @width.setter
    def width(self, value: Any) -> None:
        width = _coerce_emu(value, "line width")
        if width == int(self.width):
            return
        self._shape._payload["line_width"] = width
        self._shape._slide._presentation._queue_shape_line_width(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            width,
        )

    @property
    def dash_style(self) -> Any:
        if "line_dash_style" not in self._shape._payload:
            self._shape._payload["line_dash_style"] = _shape_line_dash_style(self._shape)
        return _line_dash_style_value(self._shape._payload["line_dash_style"])

    @dash_style.setter
    def dash_style(self, value: Any) -> None:
        dash_style = _normalize_line_dash_style(value)
        if "line_dash_style" not in self._shape._payload:
            self._shape._payload["line_dash_style"] = _shape_line_dash_style(self._shape)
        if dash_style == self._shape._payload["line_dash_style"]:
            return
        self._shape._payload["line_dash_style"] = dash_style
        self._shape._slide._presentation._queue_shape_line_dash(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            dash_style,
        )


class ShadowFormat:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    @property
    def inherit(self) -> bool:
        raw = self._shape._payload.get("shadow_inherit")
        if not isinstance(raw, bool):
            raw = _shape_shadow_inherit(self._shape)
            self._shape._payload["shadow_inherit"] = raw
        return raw

    @inherit.setter
    def inherit(self, value: Any) -> None:
        inherit = bool(value)
        if inherit == self.inherit:
            return
        self._shape._payload["shadow_inherit"] = inherit
        self._shape._slide._presentation._queue_shape_shadow_inherit(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            inherit,
        )


class LineFillFormat:
    def __init__(self, shape: Shape) -> None:
        self._shape = shape

    def solid(self) -> None:
        if self._fill_type() == "solid":
            return
        self._shape._payload["line_fill_type"] = "solid"
        self._shape._payload.pop("line_rgb", None)
        self._shape._payload.pop("line_pattern", None)
        self._shape._payload.pop("line_pattern_fore_rgb", None)
        self._shape._payload.pop("line_pattern_back_rgb", None)
        self._shape._slide._presentation._queue_shape_line_solid(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
        )

    def background(self) -> None:
        if self._fill_type() == "background":
            return
        self._shape._payload["line_fill_type"] = "background"
        self._shape._payload.pop("line_rgb", None)
        self._shape._payload.pop("line_pattern", None)
        self._shape._payload.pop("line_pattern_fore_rgb", None)
        self._shape._payload.pop("line_pattern_back_rgb", None)
        self._shape._slide._presentation._queue_shape_line_background(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
        )

    def patterned(self) -> None:
        if self._fill_type() == "patterned":
            return
        pattern = None
        self._shape._payload["line_fill_type"] = "patterned"
        self._shape._payload.pop("line_rgb", None)
        self._shape._payload["line_pattern"] = pattern
        self._shape._slide._presentation._queue_shape_line_patterned(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            pattern,
        )

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> "ColorFormat":
        return ColorFormat(self._shape, "line_fill_fore")

    @property
    def back_color(self) -> "ColorFormat":
        return ColorFormat(self._shape, "line_fill_back")

    @property
    def pattern(self) -> Any:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(self._pattern_raw())

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if pattern == self._pattern_raw():
            return
        self._shape._payload["line_pattern"] = pattern
        self._shape._slide._presentation._queue_shape_line_patterned(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            pattern,
        )

    def _fill_type(self) -> str | None:
        if "line_fill_type" not in self._shape._payload:
            self._shape._payload["line_fill_type"] = _shape_line_fill_type(self._shape)
        return self._shape._payload["line_fill_type"]

    def _pattern_raw(self) -> str | None:
        if "line_pattern" not in self._shape._payload:
            self._shape._payload["line_pattern"] = _shape_line_fill_pattern(self._shape)
        return self._shape._payload["line_pattern"]


class ColorFormat:
    def __init__(self, shape: Shape, target: str) -> None:
        self._shape = shape
        self._target = target

    @property
    def rgb(self) -> Any:
        if self.type == _color_type_value("scheme"):
            raise AttributeError("no .rgb property on color type '_SchemeColor'")
        raw = self._rgb_raw()
        if raw is None:
            return None
        return _rgb_value(raw)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if self._target == "fill_fore":
            if self._fill_type() == "patterned":
                if self._pattern_rgb("fill", "fore", "000000") == rgb:
                    return
                self._shape._payload["fill_pattern_fore_rgb"] = rgb
                self._shape._slide._presentation._queue_shape_fill_pattern_fore_color(
                    self._shape._slide._index,
                    _shape_style_ref(self._shape),
                    rgb,
                )
                return
            self._set_solid_fill_rgb(rgb)
            return
        if self._target == "fill_back":
            if self._fill_type() != "patterned":
                raise TypeError("fill is not patterned, call .patterned() first")
            if self._pattern_rgb("fill", "back", "FFFFFF") == rgb:
                return
            self._shape._payload["fill_pattern_back_rgb"] = rgb
            self._shape._slide._presentation._queue_shape_fill_pattern_back_color(
                self._shape._slide._index,
                _shape_style_ref(self._shape),
                rgb,
            )
            return
        if self._target == "line_fill_fore":
            if self._line_fill_type() == "patterned":
                if self._pattern_rgb("line", "fore", "000000") == rgb:
                    return
                self._shape._payload["line_pattern_fore_rgb"] = rgb
                self._shape._slide._presentation._queue_shape_line_pattern_fore_color(
                    self._shape._slide._index,
                    _shape_style_ref(self._shape),
                    rgb,
                )
                return
            self._set_solid_line_rgb(rgb)
            return
        if self._target == "line_fill_back":
            if self._line_fill_type() != "patterned":
                raise TypeError("fill is not patterned, call .patterned() first")
            if self._pattern_rgb("line", "back", "FFFFFF") == rgb:
                return
            self._shape._payload["line_pattern_back_rgb"] = rgb
            self._shape._slide._presentation._queue_shape_line_pattern_back_color(
                self._shape._slide._index,
                _shape_style_ref(self._shape),
                rgb,
            )
            return
        if self._target == "fill":
            self._set_solid_fill_rgb(rgb)
            return
        self._set_solid_line_rgb(rgb)

    @property
    def brightness(self) -> float:
        payload = self._color_payload()
        if payload is None:
            return 0.0
        return float(payload.get("brightness", 0.0))

    @brightness.setter
    def brightness(self, value: Any) -> None:
        brightness = float(value)
        if not -1.0 <= brightness <= 1.0:
            raise ValueError("brightness must be between -1.0 and 1.0")
        self._require_solid_color_target()
        payload = self._color_payload()
        if payload is None:
            return
        if float(payload.get("brightness", 0.0)) == brightness:
            return
        color = dict(payload)
        color["brightness"] = brightness
        self._set_solid_color(color)

    @property
    def theme_color(self) -> Any:
        payload = self._color_payload()
        if payload is None or payload.get("type") != "scheme":
            return _theme_color_value("")
        return _theme_color_value(str(payload["value"]))

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        self._require_solid_color_target()
        xml_value = _normalize_theme_color(value)
        payload = self._color_payload()
        brightness = 0.0 if payload is None else float(payload.get("brightness", 0.0))
        if (
            payload is not None
            and payload.get("type") == "scheme"
            and payload.get("value") == xml_value
        ):
            return
        self._set_solid_color(
            {"type": "scheme", "value": xml_value, "brightness": brightness}
        )

    @property
    def type(self) -> Any:
        payload = self._color_payload()
        if payload is None:
            return None
        if payload.get("type") == "rgb":
            return _color_type_value("rgb")
        if payload.get("type") == "scheme":
            return _color_type_value("scheme")
        return None

    def _rgb_raw(self) -> str | None:
        if self._target == "fill_fore":
            if self._fill_type() == "patterned":
                return self._pattern_rgb("fill", "fore", "000000")
            return self._solid_rgb("fill")
        if self._target == "fill_back":
            if self._fill_type() != "patterned":
                raise TypeError("fill is not patterned, call .patterned() first")
            return self._pattern_rgb("fill", "back", "FFFFFF")
        if self._target == "line_fill_fore":
            if self._line_fill_type() == "patterned":
                return self._pattern_rgb("line", "fore", "000000")
            return self._solid_rgb("line")
        if self._target == "line_fill_back":
            if self._line_fill_type() != "patterned":
                raise TypeError("fill is not patterned, call .patterned() first")
            return self._pattern_rgb("line", "back", "FFFFFF")
        return self._solid_rgb(self._target)

    def _solid_rgb(self, target: str) -> str | None:
        payload = self._shape._payload.get(f"{target}_color_payload")
        if isinstance(payload, dict):
            return payload.get("value") if payload.get("type") == "rgb" else None
        raw = self._shape._payload.get(f"{target}_rgb")
        if not isinstance(raw, str):
            raw = _shape_style_rgb(self._shape, target)
            if raw is not None:
                self._shape._payload[f"{target}_rgb"] = raw
        return raw

    def _color_payload(self) -> dict[str, Any] | None:
        target = {
            "fill_fore": "fill",
            "line_fill_fore": "line",
            "fill": "fill",
            "line": "line",
        }.get(self._target)
        if target is None:
            return None
        payload_key = f"{target}_color_payload"
        cached = self._shape._payload.get(payload_key)
        if isinstance(cached, dict):
            return cached
        payload = _shape_style_color_payload(self._shape, target)
        if payload is not None:
            self._shape._payload[payload_key] = dict(payload)
        return payload

    def _require_solid_color_target(self) -> None:
        if self._target == "fill_back":
            raise TypeError("fill is not patterned, call .patterned() first")
        if self._target == "line_fill_back":
            raise TypeError("fill is not patterned, call .patterned() first")

    def _pattern_rgb(self, target: str, role: str, default: str) -> str:
        payload_key = f"{target}_pattern_{role}_rgb"
        raw = self._shape._payload.get(payload_key)
        if not isinstance(raw, str):
            raw = _shape_pattern_rgb(self._shape, target, role)
            if raw is None:
                raw = default
            self._shape._payload[payload_key] = raw
        return raw

    def _fill_type(self) -> str | None:
        if "fill_type" not in self._shape._payload:
            self._shape._payload["fill_type"] = _shape_fill_type(self._shape)
        return self._shape._payload["fill_type"]

    def _line_fill_type(self) -> str | None:
        if "line_fill_type" not in self._shape._payload:
            self._shape._payload["line_fill_type"] = _shape_line_fill_type(self._shape)
        return self._shape._payload["line_fill_type"]

    def _set_solid_fill_rgb(self, rgb: str) -> None:
        if self._fill_type() == "solid" and self._solid_rgb("fill") == rgb:
            return
        self._shape._payload["fill_rgb"] = rgb
        self._shape._payload["fill_color_payload"] = {
            "type": "rgb",
            "value": rgb,
            "brightness": 0.0,
        }
        self._shape._payload["fill_type"] = "solid"
        self._shape._payload.pop("fill_pattern", None)
        self._shape._payload.pop("fill_pattern_fore_rgb", None)
        self._shape._payload.pop("fill_pattern_back_rgb", None)
        self._shape._payload.pop("fill_gradient", None)
        self._shape._slide._presentation._queue_shape_fill_color(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            rgb,
        )

    def _set_solid_line_rgb(self, rgb: str) -> None:
        if self._line_fill_type() == "solid" and self._solid_rgb("line") == rgb:
            return
        self._shape._payload["line_rgb"] = rgb
        self._shape._payload["line_color_payload"] = {
            "type": "rgb",
            "value": rgb,
            "brightness": 0.0,
        }
        self._shape._payload["line_fill_type"] = "solid"
        self._shape._payload.pop("line_pattern", None)
        self._shape._payload.pop("line_pattern_fore_rgb", None)
        self._shape._payload.pop("line_pattern_back_rgb", None)
        self._shape._slide._presentation._queue_shape_line_color(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            rgb,
        )

    def _set_solid_color(self, color: dict[str, Any]) -> None:
        self._require_solid_color_target()
        target = "fill" if self._target in {"fill_fore", "fill"} else "line"
        self._shape._payload[f"{target}_color_payload"] = dict(color)
        self._shape._payload[f"{target}_rgb"] = (
            color["value"] if color.get("type") == "rgb" else None
        )
        self._shape._payload.pop(f"{target}_pattern", None)
        self._shape._payload.pop(f"{target}_pattern_fore_rgb", None)
        self._shape._payload.pop(f"{target}_pattern_back_rgb", None)
        if target == "fill":
            self._shape._payload["fill_type"] = "solid"
            self._shape._payload.pop("fill_gradient", None)
            self._shape._slide._presentation._queue_shape_fill_color(
                self._shape._slide._index,
                _shape_style_ref(self._shape),
                dict(color),
            )
            return
        self._shape._payload["line_fill_type"] = "solid"
        self._shape._slide._presentation._queue_shape_line_color(
            self._shape._slide._index,
            _shape_style_ref(self._shape),
            dict(color),
        )
