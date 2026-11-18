"""Chart formatting facade helpers."""
# ruff: noqa: F401

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from xml.etree import ElementTree as ET

from .chart_element_format_xml import chart_color_payload as _chart_color_payload
from .chart_font_format_facade import (
    ChartFont,
    ChartFontColorFormat,
    ChartFontFillFormat,
    _run_properties_fill_type,
    _run_properties_rgb,
)
from .dml.color import ColorFormatRefusal, ColorTextAndTransforms, fill_color_element
from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
)
from .dml_fill import (
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
)
from .dml_fill import (
    fill_type_from_xml_children as _fill_type_from_xml_children,
)
from .dml_fill import (
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)
from .dml_fill import (
    set_shape_gradient_fill as _set_shape_gradient_fill,
)
from .facade_values import (
    coerce_emu as _coerce_emu,
)
from .facade_values import (
    emu_value as _emu_value,
)
from .facade_values import (
    fill_type_value as _fill_type_value,
)
from .facade_values import (
    line_dash_style_value as _line_dash_style_value,
)
from .facade_values import (
    normalize_line_dash_style as _normalize_line_dash_style,
)
from .facade_values import (
    normalize_pattern_type as _normalize_pattern_type,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    pattern_type_value as _pattern_type_value,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .package_parts import XmlElementProxy
from .shape_format_facade import _FRIENDLY_COMPOUND, LINE_COMPOUND_STYLES
from .shape_format_facade import GradientStops as _GradientStops
from .shape_format_facade import _choice as _line_choice
from .shape_line_end_edits import validate_line_end_spec as _validate_line_end_spec

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


class ChartLineFormatRefusal(ValueError):
    """An unsupported chart outline edit was refused before changing its owner."""


class ChartFormat:
    def __init__(
        self,
        element_provider: Callable[[], ET.Element],
        mutation_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._element_provider = element_provider
        self._mutation_callback = mutation_callback

    @property
    def element(self) -> XmlElementProxy:
        return XmlElementProxy(self._element_provider())

    @property
    def fill(self) -> ChartFillFormat:
        return ChartFillFormat(self._element_provider, self._mutation_callback)

    @property
    def line(self) -> ChartLineFormat:
        return ChartLineFormat(self._element_provider, self._mutation_callback)


class ChartFillFormat:
    def __init__(
        self,
        element_provider: Callable[[], ET.Element],
        mutation_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._element_provider = element_provider
        self._mutation_callback = mutation_callback
        self._gradient_cache: dict[str, Any] | None = None

    def solid(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart format fill is read-only")
        if _chart_format_fill_type(self._element_provider()) == "solid":
            return
        self._mutation_callback({"fill_type": "solid"})

    def patterned(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart format fill is read-only")
        if _chart_format_fill_type(self._element_provider()) == "patterned":
            return
        self._mutation_callback({"fill_type": "patterned"})

    def background(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart format fill is read-only")
        if _chart_format_fill_type(self._element_provider()) == "background":
            return
        self._gradient_cache = None
        self._mutation_callback({"fill_type": "background"})

    def gradient(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart format fill is read-only")
        if _chart_format_fill_type(self._element_provider()) == "gradient":
            return
        gradient = _default_gradient_payload()
        self._gradient_cache = gradient
        self._queue_gradient(gradient, include_fill_type=True)

    @property
    def type(self) -> Any:
        return _fill_type_value(_chart_format_fill_type(self._element_provider()))

    @property
    def fore_color(self) -> ChartColorFormat:
        return ChartColorFormat(
            self._element_provider,
            "fill_fore",
            self._mutation_callback,
        )

    @property
    def back_color(self) -> ChartColorFormat:
        return ChartColorFormat(
            self._element_provider,
            "fill_back",
            self._mutation_callback,
        )

    @property
    def pattern(self) -> Any:
        if _chart_format_fill_type(self._element_provider()) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(_chart_format_pattern(self._element_provider()))

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart format fill pattern is read-only")
        if _chart_format_fill_type(self._element_provider()) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if _chart_format_pattern(self._element_provider()) == pattern:
            return
        self._mutation_callback({"fill_pattern": pattern})

    @property
    def gradient_angle(self) -> float | None:
        if _chart_format_fill_type(self._element_provider()) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        gradient = self._gradient_payload()
        if gradient.get("path") is not None:
            raise ValueError("not a linear gradient")
        return gradient.get("angle")

    @gradient_angle.setter
    def gradient_angle(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart format fill gradient is read-only")
        if _chart_format_fill_type(self._element_provider()) != "gradient":
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
        if _chart_format_fill_type(self._element_provider()) != "gradient":
            raise TypeError("Fill is not of type MSO_FILL_TYPE.GRADIENT")
        return _GradientStops(self)

    def _gradient_payload(self) -> dict[str, Any]:
        if self._gradient_cache is not None:
            return self._gradient_cache
        shape_properties = _chart_format_shape_properties(self._element_provider())
        self._gradient_cache = (
            None
            if shape_properties is None
            else _gradient_payload_from_fill_parent(shape_properties)
        ) or _default_gradient_payload()
        return self._gradient_cache

    def _queue_gradient(
        self,
        gradient: dict[str, Any],
        *,
        include_fill_type: bool = False,
    ) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart format fill gradient is read-only")
        self._gradient_cache = gradient
        properties: dict[str, Any] = {"fill_gradient": gradient}
        if include_fill_type:
            properties["fill_type"] = "gradient"
        self._mutation_callback(properties)
        shape_properties = _chart_format_shape_properties(self._element_provider())
        if shape_properties is not None:
            _set_shape_gradient_fill(shape_properties, gradient)


class ChartLineFormat:
    def __init__(
        self,
        element_provider: Callable[[], ET.Element],
        mutation_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._element_provider = element_provider
        self._mutation_callback = mutation_callback

    @property
    def color(self) -> ChartColorFormat:
        return ChartColorFormat(
            self._element_provider,
            "line",
            self._mutation_callback,
        )

    @property
    def fill(self) -> ChartLineFillFormat:
        return ChartLineFillFormat(self._element_provider, self._mutation_callback)

    @property
    def width(self) -> Any:
        line = _chart_format_line_element(self._element_provider())
        if line is None:
            return None
        raw = line.attrib.get("w")
        return None if raw is None else _emu_value(int(raw))

    @width.setter
    def width(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart line width is read-only")
        width = _coerce_emu(value, "line width")
        if self.width is not None and int(self.width) == width:
            return
        self._mutation_callback({"line_width": width})

    @property
    def dash_style(self) -> Any:
        line = _chart_format_line_element(self._element_provider())
        if line is None:
            return None
        preset_dash = line.find(f"{{{A_NS}}}prstDash")
        return _line_dash_style_value(
            None if preset_dash is None else preset_dash.attrib.get("val")
        )

    @dash_style.setter
    def dash_style(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart line dash style is read-only")
        dash_style = _normalize_line_dash_style(value)
        if _chart_format_line_dash_style(self._element_provider()) == dash_style:
            return
        self._mutation_callback({"line_dash": dash_style})

    @property
    def compound_style(self) -> str | None:
        """single, double, thick_thin, thin_thick or triple; None when unset."""
        line = _chart_format_line_element(self._element_provider())
        raw = None if line is None else line.get("cmpd")
        return None if raw is None else _FRIENDLY_COMPOUND.get(raw, raw)

    @compound_style.setter
    def compound_style(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart line compound style is read-only")
        try:
            compound = _line_choice(value, LINE_COMPOUND_STYLES, "chart line compound style")
        except (TypeError, ValueError) as error:
            raise ChartLineFormatRefusal(str(error)) from error
        line = _chart_format_line_element(self._element_provider())
        if (None if line is None else line.get("cmpd")) == compound:
            return
        self._mutation_callback({"line_compound": compound})

    @property
    def head_end(self) -> dict[str, str | None]:
        """The start arrow as ``{"type", "width", "length"}``; all None when unset."""
        return _chart_format_line_end(self._element_provider(), "headEnd")

    @head_end.setter
    def head_end(self, value: Any) -> None:
        self._set_line_end("headEnd", "line_head_end", value)

    @property
    def tail_end(self) -> dict[str, str | None]:
        """The end arrow as ``{"type", "width", "length"}``; all None when unset."""
        return _chart_format_line_end(self._element_provider(), "tailEnd")

    @tail_end.setter
    def tail_end(self, value: Any) -> None:
        self._set_line_end("tailEnd", "line_tail_end", value)

    def _set_line_end(self, end_name: str, attr: str, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError(f"chart line {end_name} is read-only")
        try:
            spec = _validate_line_end_spec(value)
        except (TypeError, ValueError) as error:
            raise ChartLineFormatRefusal(str(error)) from error
        if spec is not None and all(item is None for item in spec.values()):
            spec = None
        current = _chart_format_line_end(self._element_provider(), end_name)
        if current == (spec or {"type": None, "width": None, "length": None}):
            return
        self._mutation_callback({attr: spec})


class ChartLineFillFormat:
    def __init__(
        self,
        element_provider: Callable[[], ET.Element],
        mutation_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._element_provider = element_provider
        self._mutation_callback = mutation_callback

    def solid(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart line fill is read-only")
        if _chart_format_line_fill_type(self._element_provider()) == "solid":
            return
        self._mutation_callback({"line_fill_type": "solid"})

    def background(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart line fill is read-only")
        if _chart_format_line_fill_type(self._element_provider()) == "background":
            return
        self._mutation_callback({"line_fill_type": "background"})

    def patterned(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart line fill is read-only")
        if _chart_format_line_fill_type(self._element_provider()) == "patterned":
            return
        self._mutation_callback({"line_fill_type": "patterned"})

    @property
    def type(self) -> Any:
        return _fill_type_value(_chart_format_line_fill_type(self._element_provider()))

    @property
    def fore_color(self) -> ChartColorFormat:
        return ChartColorFormat(
            self._element_provider,
            "line_fill_fore",
            self._mutation_callback,
        )

    @property
    def back_color(self) -> ChartColorFormat:
        return ChartColorFormat(
            self._element_provider,
            "line_fill_back",
            self._mutation_callback,
        )

    @property
    def pattern(self) -> Any:
        if _chart_format_line_fill_type(self._element_provider()) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        return _pattern_type_value(_chart_format_line_pattern(self._element_provider()))

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart line fill pattern is read-only")
        if _chart_format_line_fill_type(self._element_provider()) != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        if _chart_format_line_pattern(self._element_provider()) == pattern:
            return
        self._mutation_callback({"line_pattern": pattern})


class ChartColorFormat(ColorTextAndTransforms):
    def __init__(
        self,
        element_provider: Callable[[], ET.Element],
        target: str,
        mutation_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._element_provider = element_provider
        self._target = target
        self._mutation_callback = mutation_callback

    def _color_element(self) -> ET.Element | None:
        properties = _chart_format_shape_properties(self._element_provider())
        if self._target in {"line", "line_fill_fore", "line_fill_back"}:
            properties = None if properties is None else properties.find(f"{{{A_NS}}}ln")
        role = "back" if self._target in {"fill_back", "line_fill_back"} else "fore"
        return fill_color_element(properties, role)

    def _set_color_element(self, color: ET.Element) -> None:
        if self._mutation_callback is None:
            raise ColorFormatRefusal("chart color is read-only")
        try:
            attr = self._mutation_attr()
        except (AttributeError, TypeError) as error:
            raise ColorFormatRefusal(str(error)) from error
        current = self._color_element()
        if current is not None and ET.tostring(current) == ET.tostring(color):
            return
        self._mutation_callback({attr: _chart_color_payload(color)})

    @property
    def rgb(self) -> Any:
        rgb = _chart_format_rgb(self._element_provider(), self._target)
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart color is read-only")
        attr = self._mutation_attr()
        rgb = _normalize_rgb(value)
        if _chart_format_rgb(self._element_provider(), self._target) == rgb:
            return
        self._mutation_callback({attr: rgb})

    def _mutation_attr(self) -> str:
        """The queued property that replaces this target's color, by current fill type."""
        if self._target in {"fill_fore", "fill_back"}:
            if _chart_format_fill_type(self._element_provider()) == "patterned":
                return f"fill_pattern_{self._target.removeprefix('fill_')}_rgb"
            if self._target == "fill_back":
                raise TypeError("fill is not patterned, call .patterned() first")
            return "fill_rgb"
        if self._target in {"line_fill_fore", "line_fill_back"}:
            if _chart_format_line_fill_type(self._element_provider()) == "patterned":
                return f"line_pattern_{self._target.removeprefix('line_fill_')}_rgb"
            if self._target == "line_fill_back":
                raise TypeError("fill is not patterned, call .patterned() first")
        return "line_rgb"


def _chart_format_shape_properties(element: ET.Element) -> ET.Element | None:
    if element.tag == f"{{{C_NS}}}spPr":
        return element
    return element.find(f"{{{C_NS}}}spPr")


def _chart_format_fill_type(element: ET.Element) -> str | None:
    shape_properties = _chart_format_shape_properties(element)
    if shape_properties is None:
        return None
    return _fill_type_from_xml_children(shape_properties)


def _chart_format_pattern(element: ET.Element) -> str | None:
    shape_properties = _chart_format_shape_properties(element)
    if shape_properties is None:
        return None
    pattern_fill = shape_properties.find(f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def _chart_format_line_element(element: ET.Element) -> ET.Element | None:
    shape_properties = _chart_format_shape_properties(element)
    if shape_properties is None:
        return None
    return shape_properties.find(f"{{{A_NS}}}ln")


def _chart_format_line_fill_type(element: ET.Element) -> str | None:
    line = _chart_format_line_element(element)
    if line is None:
        return None
    return _fill_type_from_xml_children(line)


def _chart_format_line_pattern(element: ET.Element) -> str | None:
    line = _chart_format_line_element(element)
    if line is None:
        return None
    pattern_fill = line.find(f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def _chart_format_line_dash_style(element: ET.Element) -> str | None:
    line = _chart_format_line_element(element)
    if line is None:
        return None
    preset_dash = line.find(f"{{{A_NS}}}prstDash")
    return None if preset_dash is None else preset_dash.attrib.get("val")


def _chart_format_line_end(element: ET.Element, end_name: str) -> dict[str, str | None]:
    line = _chart_format_line_element(element)
    end = None if line is None else line.find(f"{{{A_NS}}}{end_name}")
    if end is None:
        return {"type": None, "width": None, "length": None}
    return {"type": end.get("type"), "width": end.get("w"), "length": end.get("len")}


def _chart_format_rgb(element: ET.Element, target: str) -> str | None:
    shape_properties = _chart_format_shape_properties(element)
    if shape_properties is None:
        return None
    if target == "fill_fore":
        return _fill_rgb_from_xml_children(shape_properties, "fgClr")
    if target == "fill_back":
        return _fill_rgb_from_xml_children(shape_properties, "bgClr")
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        return None
    if target == "line_fill_back":
        return _fill_rgb_from_xml_children(line, "bgClr")
    return _fill_rgb_from_xml_children(line, "fgClr")
