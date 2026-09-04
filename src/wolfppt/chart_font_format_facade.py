"""Chart font formatting facade helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    default_gradient_payload as _default_gradient_payload,
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
    fill_type_from_xml_children as _fill_type_from_xml_children,
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
    run_gradient_fill_element as _run_gradient_fill_element,
    run_no_fill_element as _run_no_fill_element,
    run_pattern_fill_element as _run_pattern_fill_element,
    run_solid_fill_element as _run_solid_fill_element,
    set_run_gradient_fill as _set_run_gradient_fill,
    set_run_pattern_fill as _set_run_pattern_fill,
    set_run_pattern_fill_color as _set_run_pattern_fill_color,
    set_solid_fill_rgb as _set_solid_fill_rgb,
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
from .xml_helpers import optional_bool_xml_attr as _optional_bool_xml_attr

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class ChartFont:
    def __init__(
        self,
        run_properties_provider: Callable[[], ET.Element | None],
        mutation_callback: Callable[[dict[str, Any]], None] | None = None,
        size_provider: Callable[[], Any] | None = None,
        fill_type_provider: Callable[[], str | None] | None = None,
        pattern_provider: Callable[[], str | None] | None = None,
        gradient_provider: Callable[[], dict[str, Any] | None] | None = None,
    ) -> None:
        self._run_properties_provider = run_properties_provider
        self._mutation_callback = mutation_callback
        self._size_provider = size_provider
        self._fill_type_provider = fill_type_provider
        self._pattern_provider = pattern_provider
        self._gradient_provider = gradient_provider

    @property
    def bold(self) -> bool | None:
        run_properties = self._run_properties_provider()
        return None if run_properties is None else _optional_bool_xml_attr(run_properties, "b")

    @bold.setter
    def bold(self, value: bool | None) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font bold is read-only")
        bold = None if value is None else bool(value)
        if bold == self.bold:
            return
        self._mutation_callback({"font_bold": bold})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            _set_font_bool_attribute(run_properties, "b", bold)

    @property
    def italic(self) -> bool | None:
        run_properties = self._run_properties_provider()
        return None if run_properties is None else _optional_bool_xml_attr(run_properties, "i")

    @italic.setter
    def italic(self, value: bool | None) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font italic is read-only")
        italic = None if value is None else bool(value)
        if italic == self.italic:
            return
        self._mutation_callback({"font_italic": italic})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            _set_font_bool_attribute(run_properties, "i", italic)

    @property
    def underline(self) -> bool | None:
        run_properties = self._run_properties_provider()
        if run_properties is None:
            return None
        value = run_properties.attrib.get("u")
        if value is None:
            return None
        if value == "none":
            return False
        if value == "sng":
            return True
        return None

    @underline.setter
    def underline(self, value: bool | None) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font underline is read-only")
        underline = None if value is None else bool(value)
        if underline == self.underline:
            return
        self._mutation_callback({"font_underline": underline})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            _set_font_underline(run_properties, underline)

    @property
    def size(self) -> Any:
        run_properties = self._run_properties_provider()
        if run_properties is None:
            if self._size_provider is None:
                return None
            value = self._size_provider()
            return None if value is None else _font_size_value_from_emu(int(value))
        value = run_properties.attrib.get("sz")
        return None if value is None else _centipoints_value(int(value))

    @size.setter
    def size(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font size is read-only")
        size = None if value is None else int(value)
        if size == self.size:
            return
        self._mutation_callback({"font_size": size})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            if size is None:
                run_properties.attrib.pop("sz", None)
            else:
                from .facade_values import emu_to_centipoints as _emu_to_centipoints

                run_properties.set("sz", str(_emu_to_centipoints(size)))

    @property
    def name(self) -> str | None:
        run_properties = self._run_properties_provider()
        if run_properties is None:
            return None
        latin = run_properties.find(f"{{{A_NS}}}latin")
        return None if latin is None else latin.attrib.get("typeface")

    @name.setter
    def name(self, value: str | None) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font name is read-only")
        name = None if value is None else str(value)
        if name == self.name:
            return
        self._mutation_callback({"font_name": name})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            _set_font_name(run_properties, name)

    @property
    def language_id(self) -> Any:
        run_properties = self._run_properties_provider()
        if run_properties is None:
            return _language_id_value(None)
        return _language_id_value(run_properties.attrib.get("lang"))

    @language_id.setter
    def language_id(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font language_id is read-only")
        language_id = _normalize_language_id(value)
        if _normalize_language_id(self.language_id) == language_id:
            return
        self._mutation_callback({"font_language_id": language_id})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            if language_id is None:
                run_properties.attrib.pop("lang", None)
            else:
                run_properties.set("lang", language_id)

    @property
    def color(self) -> "ChartFontColorFormat":
        return ChartFontColorFormat(
            self._run_properties_provider,
            self._mutation_callback,
            fill_type_provider=self._fill_type_provider,
        )

    @property
    def fill(self) -> "ChartFontFillFormat":
        return ChartFontFillFormat(
            self._run_properties_provider,
            self._mutation_callback,
            self._fill_type_provider,
            self._pattern_provider,
            self._gradient_provider,
        )


class ChartFontColorFormat:
    def __init__(
        self,
        run_properties_provider: Callable[[], ET.Element | None],
        mutation_callback: Callable[[dict[str, Any]], None] | None = None,
        target: str = "fore",
        fill_type_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self._run_properties_provider = run_properties_provider
        self._mutation_callback = mutation_callback
        self._target = target
        self._fill_type_provider = fill_type_provider

    @property
    def rgb(self) -> Any:
        run_properties = self._run_properties_provider()
        if run_properties is None:
            rgb = None
        elif self._target == "back":
            rgb = _run_properties_pattern_rgb(run_properties, "bgClr")
        elif _run_properties_fill_type(run_properties) == "patterned":
            rgb = _run_properties_pattern_rgb(run_properties, "fgClr")
        else:
            rgb = _run_properties_rgb(run_properties)
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font color is read-only")
        run_properties = self._run_properties_provider()
        fill_type = (
            self._fill_type_provider()
            if run_properties is None and self._fill_type_provider is not None
            else None if run_properties is None else _run_properties_fill_type(run_properties)
        )
        rgb = None if value is None else _normalize_rgb(value)
        if self._target == "back":
            if fill_type != "patterned":
                raise TypeError("fill is not patterned, call .patterned() first")
            if _run_properties_pattern_rgb_or_none(run_properties, "bgClr") == rgb:
                return
            self._mutation_callback({"font_pattern_back_rgb": rgb})
            if run_properties is not None and rgb is not None:
                _set_font_pattern_rgb(run_properties, "bgClr", rgb)
            return
        if fill_type == "patterned":
            if _run_properties_pattern_rgb_or_none(run_properties, "fgClr") == rgb:
                return
            self._mutation_callback({"font_pattern_fore_rgb": rgb})
            if run_properties is not None and rgb is not None:
                _set_font_pattern_rgb(run_properties, "fgClr", rgb)
            return
        if _run_properties_rgb_or_none(run_properties) == rgb:
            return
        self._mutation_callback({"font_rgb": rgb})
        if run_properties is not None:
            _set_font_rgb(run_properties, rgb)


class ChartFontFillFormat:
    def __init__(
        self,
        run_properties_provider: Callable[[], ET.Element | None],
        mutation_callback: Callable[[dict[str, Any]], None] | None = None,
        fill_type_provider: Callable[[], str | None] | None = None,
        pattern_provider: Callable[[], str | None] | None = None,
        gradient_provider: Callable[[], dict[str, Any] | None] | None = None,
    ) -> None:
        self._run_properties_provider = run_properties_provider
        self._mutation_callback = mutation_callback
        self._fill_type_provider = fill_type_provider
        self._pattern_provider = pattern_provider
        self._gradient_provider = gradient_provider
        self._gradient_cache: dict[str, Any] | None = None

    def solid(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font fill is read-only")
        if self._fill_type() == "solid":
            return
        self._gradient_cache = None
        self._mutation_callback({"font_fill_type": "solid"})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            _set_font_fill_type(run_properties, "solid")

    def background(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font fill is read-only")
        if self._fill_type() == "background":
            return
        self._gradient_cache = None
        self._mutation_callback({"font_fill_type": "background"})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            _set_font_fill_type(run_properties, "background")

    def patterned(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font fill is read-only")
        if self._fill_type() == "patterned":
            return
        self._gradient_cache = None
        self._mutation_callback({"font_fill_type": "patterned", "font_rgb": None})
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            _set_font_fill_type(run_properties, "patterned")

    def gradient(self) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font fill is read-only")
        if self._fill_type() == "gradient":
            return
        gradient = _default_gradient_payload()
        self._gradient_cache = gradient
        self._queue_gradient(gradient, include_fill_type=True)

    @property
    def type(self) -> Any:
        return _fill_type_value(self._fill_type())

    @property
    def fore_color(self) -> "ChartFontColorFormat":
        return ChartFontColorFormat(
            self._run_properties_provider,
            self._mutation_callback,
            fill_type_provider=self._fill_type_provider,
        )

    @property
    def back_color(self) -> "ChartFontColorFormat":
        return ChartFontColorFormat(
            self._run_properties_provider,
            self._mutation_callback,
            "back",
            self._fill_type_provider,
        )

    @property
    def pattern(self) -> Any:
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        run_properties = self._run_properties_provider()
        return _pattern_type_value(
            self._pattern_provider()
            if run_properties is None and self._pattern_provider is not None
            else None if run_properties is None else _run_properties_pattern(run_properties)
        )

    @pattern.setter
    def pattern(self, value: Any) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font fill pattern is read-only")
        if self._fill_type() != "patterned":
            raise TypeError("fill is not patterned, call .patterned() first")
        pattern = _normalize_pattern_type(value)
        run_properties = self._run_properties_provider()
        if (
            self._pattern_provider()
            if run_properties is None and self._pattern_provider is not None
            else None if run_properties is None else _run_properties_pattern(run_properties)
        ) == pattern:
            return
        self._mutation_callback({"font_pattern": pattern})
        if run_properties is not None:
            _set_font_pattern(run_properties, pattern)

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
        if self._mutation_callback is None:
            raise AttributeError("chart font fill gradient is read-only")
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
        run_properties = self._run_properties_provider()
        if run_properties is None:
            return None if self._fill_type_provider is None else self._fill_type_provider()
        return _run_properties_fill_type(run_properties)

    def _gradient_payload(self) -> dict[str, Any]:
        if self._gradient_cache is not None:
            return self._gradient_cache
        run_properties = self._run_properties_provider()
        if run_properties is None:
            provider_payload = (
                None if self._gradient_provider is None else self._gradient_provider()
            )
            self._gradient_cache = (
                provider_payload
                if isinstance(provider_payload, dict)
                else _default_gradient_payload()
            )
            return self._gradient_cache
        self._gradient_cache = (
            _gradient_payload_from_fill_parent(run_properties)
            or _default_gradient_payload()
        )
        return self._gradient_cache

    def _queue_gradient(
        self,
        gradient: dict[str, Any],
        *,
        include_fill_type: bool = False,
    ) -> None:
        if self._mutation_callback is None:
            raise AttributeError("chart font fill gradient is read-only")
        properties: dict[str, Any] = {"font_gradient": gradient}
        if include_fill_type:
            properties["font_fill_type"] = "gradient"
            properties["font_rgb"] = None
        self._mutation_callback(properties)
        run_properties = self._run_properties_provider()
        if run_properties is not None:
            _set_font_gradient(run_properties, gradient)


def _font_size_value_from_emu(value: int) -> Any:
    centipoints = value // 127 if value % 127 == 0 else value
    return _centipoints_value(centipoints)


def _run_properties_rgb(run_properties: ET.Element) -> str | None:
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    if color is None:
        return None
    value = color.attrib.get("val")
    return value.upper() if value else None


def _run_properties_pattern(run_properties: ET.Element) -> str | None:
    pattern_fill = run_properties.find(f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def _run_properties_pattern_rgb(
    run_properties: ET.Element,
    color_tag: str,
) -> str | None:
    return _fill_rgb_from_xml_children(run_properties, color_tag)


def _run_properties_rgb_or_none(run_properties: ET.Element | None) -> str | None:
    return None if run_properties is None else _run_properties_rgb(run_properties)


def _run_properties_pattern_rgb_or_none(
    run_properties: ET.Element | None,
    color_tag: str,
) -> str | None:
    if run_properties is None:
        return None
    return _run_properties_pattern_rgb(run_properties, color_tag)


def _set_font_bool_attribute(
    run_properties: ET.Element,
    attr: str,
    value: bool | None,
) -> None:
    if value is None:
        run_properties.attrib.pop(attr, None)
        return
    run_properties.set(attr, "1" if value else "0")


def _set_font_underline(run_properties: ET.Element, value: bool | None) -> None:
    if value is None:
        run_properties.attrib.pop("u", None)
        return
    run_properties.set("u", "sng" if value else "none")


def _set_font_name(run_properties: ET.Element, value: str | None) -> None:
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if value is None:
        if latin is not None:
            run_properties.remove(latin)
        return
    if latin is None:
        latin = ET.Element(f"{{{A_NS}}}latin")
        run_properties.append(latin)
    latin.set("typeface", value)


def _set_font_rgb(run_properties: ET.Element, value: str | None) -> None:
    if value is None:
        solid_fill = run_properties.find(f"{{{A_NS}}}solidFill")
        if solid_fill is not None:
            run_properties.remove(solid_fill)
        return
    solid_fill = _run_solid_fill_element(run_properties)
    _set_solid_fill_rgb(solid_fill, value)


def _set_font_pattern(run_properties: ET.Element, value: str | None) -> None:
    _set_run_pattern_fill(run_properties, value)


def _set_font_pattern_rgb(
    run_properties: ET.Element,
    color_tag: str,
    value: str,
) -> None:
    _set_run_pattern_fill_color(run_properties, color_tag, value)


def _set_font_gradient(run_properties: ET.Element, value: dict[str, Any]) -> None:
    _set_run_gradient_fill(run_properties, value)


def _set_font_fill_type(run_properties: ET.Element, value: str) -> None:
    if value == "solid":
        if run_properties.find(f"{{{A_NS}}}solidFill") is None:
            _run_solid_fill_element(run_properties)
        no_fill = run_properties.find(f"{{{A_NS}}}noFill")
        if no_fill is not None:
            run_properties.remove(no_fill)
        return
    if value == "background":
        _run_no_fill_element(run_properties)
        return
    if value == "patterned":
        if run_properties.find(f"{{{A_NS}}}pattFill") is None:
            _run_pattern_fill_element(run_properties)
        return
    if value == "gradient":
        if run_properties.find(f"{{{A_NS}}}gradFill") is None:
            _run_gradient_fill_element(run_properties)
        return
    raise ValueError(f"unsupported chart font fill type: {value!r}")


def _run_properties_fill_type(run_properties: ET.Element) -> str | None:
    return _fill_type_from_xml_children(run_properties)
