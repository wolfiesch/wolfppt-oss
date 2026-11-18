"""Chart font formatting facade helpers."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any
from xml.etree import ElementTree as ET

from .chart_title_text_xml import (
    _set_title_paragraph_spacing,
)
from .chart_title_text_xml import (
    title_paragraph_spacing_value as _paragraph_spacing_value,
)
from .dml.color import (
    ColorFormatRefusal,
    ColorTextAndTransforms,
    fill_color_element,
    replace_fill_color_element,
)
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
    run_gradient_fill_element as _run_gradient_fill_element,
)
from .dml_fill import (
    run_no_fill_element as _run_no_fill_element,
)
from .dml_fill import (
    run_pattern_fill_element as _run_pattern_fill_element,
)
from .dml_fill import (
    run_solid_fill_element as _run_solid_fill_element,
)
from .dml_fill import (
    set_run_gradient_fill as _set_run_gradient_fill,
)
from .dml_fill import (
    set_run_pattern_fill as _set_run_pattern_fill,
)
from .dml_fill import (
    set_run_pattern_fill_color as _set_run_pattern_fill_color,
)
from .dml_fill import (
    set_solid_fill_rgb as _set_solid_fill_rgb,
)
from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
)
from .facade_values import (
    centipoints_value as _centipoints_value,
)
from .facade_values import (
    emu_to_centipoints as _emu_to_centipoints,
)
from .facade_values import (
    emu_value as _emu_value,
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
    normalize_line_spacing as _normalize_line_spacing,
)
from .facade_values import (
    normalize_paragraph_alignment as _normalize_paragraph_alignment,
)
from .facade_values import (
    normalize_paragraph_indent as _normalize_paragraph_indent,
)
from .facade_values import (
    normalize_paragraph_spacing_length as _normalize_paragraph_spacing_length,
)
from .facade_values import (
    normalize_pattern_type as _normalize_pattern_type,
)
from .facade_values import (
    normalize_rgb as _normalize_rgb,
)
from .facade_values import (
    normalize_text_frame_auto_size as _normalize_text_frame_auto_size,
)
from .facade_values import (
    normalize_text_frame_vertical_anchor as _normalize_text_frame_vertical_anchor,
)
from .facade_values import (
    normalize_text_frame_word_wrap as _normalize_text_frame_word_wrap,
)
from .facade_values import (
    paragraph_alignment_value as _paragraph_alignment_value,
)
from .facade_values import (
    pattern_type_value as _pattern_type_value,
)
from .facade_values import (
    rgb_value as _rgb_value,
)
from .facade_values import (
    text_frame_auto_size_value as _text_frame_auto_size_value,
)
from .facade_values import (
    text_frame_vertical_anchor_value as _text_frame_vertical_anchor_value,
)
from .shape_format_facade import GradientStops as _GradientStops
from .xml_helpers import optional_bool_xml_attr as _optional_bool_xml_attr

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


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
    def color(self) -> ChartFontColorFormat:
        return ChartFontColorFormat(
            self._run_properties_provider,
            self._mutation_callback,
            fill_type_provider=self._fill_type_provider,
        )

    @property
    def fill(self) -> ChartFontFillFormat:
        return ChartFontFillFormat(
            self._run_properties_provider,
            self._mutation_callback,
            self._fill_type_provider,
            self._pattern_provider,
            self._gradient_provider,
        )


class ChartFontColorFormat(ColorTextAndTransforms):
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

    def _color_element(self) -> ET.Element | None:
        return fill_color_element(self._run_properties_provider(), self._target)

    def _set_color_element(self, color: ET.Element) -> None:
        raise ColorFormatRefusal(
            "chart font color edits require owner callback and serializer support in "
            "chart_facade, chart_axis_facade, chart_point_facade, chart_font_xml, "
            "chart_legend_xml, chart_axis_xml and chart_data_label_xml; "
            "rich chart text can use text_format.portion_format.color"
        )

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
            else None
            if run_properties is None
            else _run_properties_fill_type(run_properties)
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
    def fore_color(self) -> ChartFontColorFormat:
        return ChartFontColorFormat(
            self._run_properties_provider,
            self._mutation_callback,
            fill_type_provider=self._fill_type_provider,
        )

    @property
    def back_color(self) -> ChartFontColorFormat:
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
            else None
            if run_properties is None
            else _run_properties_pattern(run_properties)
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
            else None
            if run_properties is None
            else _run_properties_pattern(run_properties)
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
            _gradient_payload_from_fill_parent(run_properties) or _default_gradient_payload()
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
    set_run_typeface(run_properties, "latin", value)


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


# Shared chart text formatting.  Chart titles, axis titles, legends, data labels
# and tick labels all store text as a DrawingML text body (``c:rich`` for
# overridable rich text, ``c:txPr`` for text properties).  The classes below
# read and write portion (run), paragraph and text-block (``a:bodyPr``) formats
# on any of those bodies.  Every setter applies an XML-ready delta to the
# in-memory chart XML through the ``apply_*`` helpers and then hands the same
# ``(scope, delta)`` to the owner's commit callback, so a save-time replay can
# call :func:`apply_chart_text_format` with identical results.  An optional
# ``check`` callback runs before any XML is touched so owners can refuse deltas
# their save path cannot persist.

TextFormatCommit = Callable[[str, dict[str, Any]], None]
TextFormatCheck = Callable[[str, dict[str, Any]], None]
TextFormatTargets = Callable[[bool], list[ET.Element]]

PORTION_FORMAT_SCOPE = "portion"
PARAGRAPH_FORMAT_SCOPE = "paragraph"
TEXT_BLOCK_FORMAT_SCOPE = "text_block"

VERTICAL_TEXT_TYPES = (
    "horz",
    "vert",
    "vert270",
    "wordArtVert",
    "eaVert",
    "mongolianVert",
    "wordArtVertRtl",
)
_TEXT_BLOCK_MARGINS = {
    "margin_left": ("lIns", 91440),
    "margin_right": ("rIns", 91440),
    "margin_top": ("tIns", 45720),
    "margin_bottom": ("bIns", 45720),
}
_RUN_PROPERTIES_CHILD_ORDER = (
    "ln",
    "noFill",
    "solidFill",
    "gradFill",
    "blipFill",
    "pattFill",
    "grpFill",
    "effectLst",
    "effectDag",
    "highlight",
    "uLnTx",
    "uLn",
    "uFillTx",
    "uFill",
    "latin",
    "ea",
    "cs",
    "sym",
    "hlinkClick",
    "hlinkMouseOver",
    "rtl",
    "extLst",
)
_AUTO_FIT_TAGS = ("noAutofit", "normAutofit", "spAutoFit")
_BODY_PROPERTIES_AFTER_AUTO_FIT = ("scene3d", "sp3d", "flatTx", "extLst")
_MIN_FONT_SIZE_CENTIPOINTS = 100
_MAX_TEXT_POINT_CENTIPOINTS = 400000
_MAX_TEXT_ROTATION_DEGREES = 90.0


class ChartPortionColorFormat(ColorTextAndTransforms):
    def __init__(self, portion_format: ChartPortionFormat) -> None:
        self._portion_format = portion_format

    def _color_element(self) -> ET.Element | None:
        return _portion_color_element(self._portion_format)

    def _set_color_element(self, color: ET.Element) -> None:
        _set_portion_color_element(self._portion_format, color)

    @property
    def rgb(self) -> Any:
        rgb = self._portion_format._raw("rgb")
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        self._portion_format._set("rgb", None if value is None else _normalize_rgb(value))


class ChartPortionFormat:
    """Character formatting shared by every chart text element.

    ``targets(create)`` returns the run-property elements (``a:rPr``,
    ``a:defRPr``) the format governs; values are read from the first one.
    """

    def __init__(
        self,
        targets: TextFormatTargets,
        commit: TextFormatCommit,
        check: TextFormatCheck | None = None,
    ) -> None:
        self._targets = targets
        self._commit = commit
        self._check = check

    @property
    def name(self) -> str | None:
        return self._raw("name")

    @name.setter
    def name(self, value: str | None) -> None:
        self._set("name", _normalize_typeface(value, "name"))

    @property
    def east_asian_name(self) -> str | None:
        return self._raw("east_asian_name")

    @east_asian_name.setter
    def east_asian_name(self, value: str | None) -> None:
        self._set("east_asian_name", _normalize_typeface(value, "east_asian_name"))

    @property
    def complex_script_name(self) -> str | None:
        return self._raw("complex_script_name")

    @complex_script_name.setter
    def complex_script_name(self, value: str | None) -> None:
        self._set(
            "complex_script_name",
            _normalize_typeface(value, "complex_script_name"),
        )

    @property
    def size(self) -> Any:
        size = self._raw("size")
        return None if size is None else _centipoints_value(_emu_to_centipoints(size))

    @size.setter
    def size(self, value: Any) -> None:
        self._set("size", _normalize_font_size(value))

    @property
    def spacing(self) -> Any:
        spacing = self._raw("spacing")
        return None if spacing is None else _centipoints_value(_emu_to_centipoints(spacing))

    @spacing.setter
    def spacing(self, value: Any) -> None:
        self._set("spacing", _normalize_character_spacing(value))

    @property
    def bold(self) -> bool | None:
        return self._raw("bold")

    @bold.setter
    def bold(self, value: bool | None) -> None:
        self._set("bold", _normalize_optional_bool(value, "bold"))

    @property
    def italic(self) -> bool | None:
        return self._raw("italic")

    @italic.setter
    def italic(self, value: bool | None) -> None:
        self._set("italic", _normalize_optional_bool(value, "italic"))

    @property
    def underline(self) -> bool | None:
        return self._raw("underline")

    @underline.setter
    def underline(self, value: bool | None) -> None:
        self._set("underline", _normalize_optional_bool(value, "underline"))

    @property
    def color(self) -> ChartPortionColorFormat:
        return ChartPortionColorFormat(self)

    def _raw(self, key: str) -> Any:
        targets = self._targets(False)
        return None if not targets else portion_format_value(targets[0], key)

    def _set(self, key: str, value: Any) -> None:
        targets = self._targets(False)
        if targets and all(portion_format_value(target, key) == value for target in targets):
            return
        delta = {key: value}
        if self._check is not None:
            self._check(PORTION_FORMAT_SCOPE, delta)
        for target in self._targets(True):
            apply_portion_format(target, delta)
        self._commit(PORTION_FORMAT_SCOPE, delta)


def _portion_color_element(portion: ChartPortionFormat, role: str = "fore") -> ET.Element | None:
    targets = portion._targets(False)
    return fill_color_element(None if not targets else targets[0], role)


def _set_portion_color_element(
    portion: ChartPortionFormat, color: ET.Element, role: str = "fore"
) -> None:
    # Validate a detached owner before creating targets or touching chart XML.
    targets = portion._targets(False)
    for target in targets or [ET.Element(f"{{{A_NS}}}rPr")]:
        replace_fill_color_element(deepcopy(target), color, role)
    delta = {"color_element": {"role": role, "xml": ET.tostring(color, encoding="unicode")}}
    if portion._check is not None:
        portion._check(PORTION_FORMAT_SCOPE, delta)
    for target in portion._targets(True):
        apply_portion_format(target, delta)
    portion._commit(PORTION_FORMAT_SCOPE, delta)


class ChartParagraphFormat:
    """Paragraph alignment, indentation and spacing for chart text."""

    def __init__(
        self,
        targets: TextFormatTargets,
        commit: TextFormatCommit,
        check: TextFormatCheck | None = None,
    ) -> None:
        self._targets = targets
        self._commit = commit
        self._check = check

    @property
    def alignment(self) -> Any:
        return _paragraph_alignment_value(self._raw("alignment"))

    @alignment.setter
    def alignment(self, value: Any) -> None:
        self._set("alignment", _normalize_paragraph_alignment(value))

    @property
    def indent(self) -> Any:
        indent = self._raw("indent")
        return None if indent is None else _emu_value(indent)

    @indent.setter
    def indent(self, value: Any) -> None:
        self._set("indent", _normalize_paragraph_indent(value, "indent"))

    @property
    def margin_left(self) -> Any:
        margin = self._raw("margin_left")
        return None if margin is None else _emu_value(margin)

    @margin_left.setter
    def margin_left(self, value: Any) -> None:
        self._set("margin_left", _normalize_paragraph_indent(value, "margin_left"))

    @property
    def space_before(self) -> Any:
        return self._spacing("space_before")

    @space_before.setter
    def space_before(self, value: Any) -> None:
        self._set(
            "space_before",
            _normalize_paragraph_spacing_length(value, "space_before"),
        )

    @property
    def space_after(self) -> Any:
        return self._spacing("space_after")

    @space_after.setter
    def space_after(self, value: Any) -> None:
        self._set(
            "space_after",
            _normalize_paragraph_spacing_length(value, "space_after"),
        )

    @property
    def line_spacing(self) -> Any:
        return self._spacing("line_spacing")

    @line_spacing.setter
    def line_spacing(self, value: Any) -> None:
        self._set("line_spacing", _normalize_line_spacing(value))

    def _spacing(self, key: str) -> Any:
        value = self._raw(key)
        if value is None or isinstance(value, float):
            return value
        return _centipoints_value(_emu_to_centipoints(int(value)))

    def _raw(self, key: str) -> Any:
        targets = self._targets(False)
        return None if not targets else paragraph_format_value(targets[0], key)

    def _set(self, key: str, value: Any) -> None:
        targets = self._targets(False)
        if targets and all(paragraph_format_value(target, key) == value for target in targets):
            return
        delta = {key: value}
        if self._check is not None:
            self._check(PARAGRAPH_FORMAT_SCOPE, delta)
        for target in self._targets(True):
            apply_paragraph_format(target, delta)
        self._commit(PARAGRAPH_FORMAT_SCOPE, delta)


class ChartTextBlockFormat:
    """Text-block (``a:bodyPr``) rotation, autofit, margins, wrap and anchor."""

    def __init__(
        self,
        body_properties: Callable[[bool], ET.Element | None],
        commit: TextFormatCommit,
        check: TextFormatCheck | None = None,
    ) -> None:
        self._body_properties = body_properties
        self._commit = commit
        self._check = check

    @property
    def rotation(self) -> float | None:
        return self._raw("rotation")

    @rotation.setter
    def rotation(self, value: Any) -> None:
        self._set("rotation", _normalize_text_rotation(value))

    @property
    def vertical_text(self) -> str | None:
        return self._raw("vertical_text")

    @vertical_text.setter
    def vertical_text(self, value: str | None) -> None:
        self._set("vertical_text", _normalize_vertical_text(value))

    @property
    def auto_size(self) -> Any:
        auto_size = self._raw("auto_size")
        return None if auto_size is None else _text_frame_auto_size_value(auto_size)

    @auto_size.setter
    def auto_size(self, value: Any) -> None:
        self._set("auto_size", _normalize_text_frame_auto_size(value))

    @property
    def word_wrap(self) -> bool | None:
        return self._raw("word_wrap")

    @word_wrap.setter
    def word_wrap(self, value: Any) -> None:
        self._set("word_wrap", _normalize_text_frame_word_wrap(value))

    @property
    def vertical_anchor(self) -> Any:
        return _text_frame_vertical_anchor_value(self._raw("vertical_anchor"))

    @vertical_anchor.setter
    def vertical_anchor(self, value: Any) -> None:
        self._set("vertical_anchor", _normalize_text_frame_vertical_anchor(value))

    @property
    def margin_left(self) -> Any:
        return self._margin("margin_left")

    @margin_left.setter
    def margin_left(self, value: Any) -> None:
        self._set("margin_left", _normalize_text_margin(value, "margin_left"))

    @property
    def margin_right(self) -> Any:
        return self._margin("margin_right")

    @margin_right.setter
    def margin_right(self, value: Any) -> None:
        self._set("margin_right", _normalize_text_margin(value, "margin_right"))

    @property
    def margin_top(self) -> Any:
        return self._margin("margin_top")

    @margin_top.setter
    def margin_top(self, value: Any) -> None:
        self._set("margin_top", _normalize_text_margin(value, "margin_top"))

    @property
    def margin_bottom(self) -> Any:
        return self._margin("margin_bottom")

    @margin_bottom.setter
    def margin_bottom(self, value: Any) -> None:
        self._set("margin_bottom", _normalize_text_margin(value, "margin_bottom"))

    def _margin(self, key: str) -> Any:
        value = self._raw(key)
        return _emu_value(_TEXT_BLOCK_MARGINS[key][1] if value is None else value)

    def _raw(self, key: str) -> Any:
        body_properties = self._body_properties(False)
        if body_properties is None:
            return None
        return text_block_format_value(body_properties, key)

    def _set(self, key: str, value: Any) -> None:
        if self._raw(key) == value:
            return
        delta = {key: value}
        if self._check is not None:
            self._check(TEXT_BLOCK_FORMAT_SCOPE, delta)
        body_properties = self._body_properties(True)
        assert body_properties is not None
        apply_text_block_format(body_properties, delta)
        self._commit(TEXT_BLOCK_FORMAT_SCOPE, delta)


class ChartTextFormat:
    """Portion, paragraph and text-block formats of one chart text body.

    ``text_body(create)`` returns the ``c:rich`` or ``c:txPr`` element; with
    ``create`` it must return an attached element.  Portion and paragraph
    formats govern every paragraph of the body.
    """

    def __init__(
        self,
        text_body: Callable[[bool], ET.Element | None],
        commit: TextFormatCommit,
        check: TextFormatCheck | None = None,
    ) -> None:
        self._text_body = text_body
        self._commit = commit
        self._check = check

    @property
    def portion_format(self) -> ChartPortionFormat:
        return ChartPortionFormat(
            lambda create: text_body_portion_targets(self._text_body(create), create),
            self._commit,
            self._check,
        )

    @property
    def paragraph_format(self) -> ChartParagraphFormat:
        return ChartParagraphFormat(
            lambda create: text_body_paragraph_targets(self._text_body(create), create),
            self._commit,
            self._check,
        )

    @property
    def text_block_format(self) -> ChartTextBlockFormat:
        return ChartTextBlockFormat(
            lambda create: text_body_body_properties(self._text_body(create), create),
            self._commit,
            self._check,
        )


def chart_text_body(
    element: ET.Element,
    create: bool,
    insert_index: Callable[[ET.Element, str], int],
) -> ET.Element | None:
    """Get rich text, or formatting-only text without creating automatic text."""
    rich = element.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is not None:
        return rich
    body = element.find(f"{{{C_NS}}}txPr")
    if body is None and create:
        body = ET.Element(f"{{{C_NS}}}txPr")
        element.insert(insert_index(element, "txPr"), body)
        _text_body_paragraphs(body, True)
    return body


def chart_text_xml(element: ET.Element) -> list[bytes]:
    """Snapshot only text children; preserve layout and shape/axis formatting."""
    order_chart_text_typefaces(element)
    return [
        ET.tostring(child, encoding="utf-8")
        for child in element
        if child.tag in {f"{{{C_NS}}}tx", f"{{{C_NS}}}txPr"}
    ]


def replace_chart_text_xml(
    element: ET.Element,
    children: list[bytes],
    insert_index: Callable[[ET.Element, str], int],
) -> None:
    """Replay the final text state, including removals and rich-run properties."""
    for child in list(element):
        if child.tag in {f"{{{C_NS}}}tx", f"{{{C_NS}}}txPr"}:
            element.remove(child)
    for xml in children:
        child = ET.fromstring(xml)
        name = child.tag.rsplit("}", 1)[-1]
        if child.tag not in {f"{{{C_NS}}}tx", f"{{{C_NS}}}txPr"}:
            raise ValueError("chart text snapshots must contain c:tx or c:txPr")
        element.insert(insert_index(element, name), child)


def order_chart_text_typefaces(element: ET.Element) -> None:
    """Keep legacy font setters schema-valid alongside script-font setters."""
    for properties in element.iter():
        if properties.tag not in {f"{{{A_NS}}}rPr", f"{{{A_NS}}}defRPr", f"{{{A_NS}}}endParaRPr"}:
            continue
        for tag in ("latin", "ea", "cs"):
            font = properties.find(f"{{{A_NS}}}{tag}")
            if font is not None and font.get("typeface") is not None:
                set_run_typeface(properties, tag, font.get("typeface"))


def update_chart_rich_run_texts(element: ET.Element, paragraph_runs: list[list[str]]) -> bool:
    """Update/append rich runs without rebuilding their formatting or fields."""
    rich = element.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        return False
    paragraphs = rich.findall(f"{{{A_NS}}}p")
    for index, texts in enumerate(paragraph_runs or [[]]):
        paragraph = (
            paragraphs[index] if index < len(paragraphs) else ET.SubElement(rich, f"{{{A_NS}}}p")
        )
        runs = paragraph.findall(f"{{{A_NS}}}r")
        for run_index, value in enumerate(texts):
            if run_index < len(runs):
                run = runs[run_index]
            else:
                run = ET.Element(f"{{{A_NS}}}r")
                end = paragraph.find(f"{{{A_NS}}}endParaRPr")
                paragraph.insert(len(paragraph) if end is None else list(paragraph).index(end), run)
            text = run.find(f"{{{A_NS}}}t")
            if text is None:
                text = ET.SubElement(run, f"{{{A_NS}}}t")
            text.text = value
        for run in runs[len(texts) :]:
            paragraph.remove(run)
    for paragraph in paragraphs[len(paragraph_runs or [[]]) :]:
        rich.remove(paragraph)
    return True


def apply_chart_text_format(
    text_body: ET.Element,
    scope: str,
    delta: dict[str, Any],
) -> None:
    """Apply one committed text-format delta to a ``c:rich``/``c:txPr`` body."""
    if scope == TEXT_BLOCK_FORMAT_SCOPE:
        body_properties = text_body_body_properties(text_body, True)
        assert body_properties is not None
        apply_text_block_format(body_properties, delta)
        return
    if scope == PARAGRAPH_FORMAT_SCOPE:
        for paragraph_properties in text_body_paragraph_targets(text_body, True):
            apply_paragraph_format(paragraph_properties, delta)
        return
    if scope == PORTION_FORMAT_SCOPE:
        for run_properties in text_body_portion_targets(text_body, True):
            apply_portion_format(run_properties, delta)
        return
    raise ValueError(f"unsupported chart text format scope: {scope!r}")


def text_body_body_properties(
    text_body: ET.Element | None,
    create: bool,
) -> ET.Element | None:
    if text_body is None:
        return None
    body_properties = text_body.find(f"{{{A_NS}}}bodyPr")
    if body_properties is None and create:
        body_properties = ET.Element(f"{{{A_NS}}}bodyPr")
        text_body.insert(0, body_properties)
    return body_properties


def text_body_paragraph_targets(
    text_body: ET.Element | None,
    create: bool,
) -> list[ET.Element]:
    if text_body is None:
        return []
    targets: list[ET.Element] = []
    for paragraph in _text_body_paragraphs(text_body, create):
        paragraph_properties = paragraph_properties_element(paragraph, create)
        if paragraph_properties is not None:
            targets.append(paragraph_properties)
    return targets


def text_body_portion_targets(
    text_body: ET.Element | None,
    create: bool,
) -> list[ET.Element]:
    """Paragraph default run properties first, then explicit run properties."""
    if text_body is None:
        return []
    defaults: list[ET.Element] = []
    runs: list[ET.Element] = []
    for paragraph in _text_body_paragraphs(text_body, create):
        paragraph_properties = paragraph_properties_element(paragraph, create)
        if paragraph_properties is not None:
            default_run_properties = default_run_properties_element(
                paragraph_properties,
                create,
            )
            if default_run_properties is not None:
                defaults.append(default_run_properties)
        for run in paragraph.findall(f"{{{A_NS}}}r"):
            run_properties = run_properties_element(run, create)
            if run_properties is not None:
                runs.append(run_properties)
    return defaults + runs


def paragraph_properties_element(
    paragraph: ET.Element,
    create: bool,
) -> ET.Element | None:
    paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None and create:
        paragraph_properties = ET.Element(f"{{{A_NS}}}pPr")
        paragraph.insert(0, paragraph_properties)
    return paragraph_properties


def default_run_properties_element(
    paragraph_properties: ET.Element,
    create: bool,
) -> ET.Element | None:
    default_run_properties = paragraph_properties.find(f"{{{A_NS}}}defRPr")
    if default_run_properties is None and create:
        default_run_properties = ET.Element(f"{{{A_NS}}}defRPr")
        extension_list = paragraph_properties.find(f"{{{A_NS}}}extLst")
        if extension_list is None:
            paragraph_properties.append(default_run_properties)
        else:
            paragraph_properties.insert(
                list(paragraph_properties).index(extension_list),
                default_run_properties,
            )
    return default_run_properties


def run_properties_element(run: ET.Element, create: bool) -> ET.Element | None:
    run_properties = run.find(f"{{{A_NS}}}rPr")
    if run_properties is None and create:
        run_properties = ET.Element(f"{{{A_NS}}}rPr")
        run.insert(0, run_properties)
    return run_properties


def portion_format_value(run_properties: ET.Element, key: str) -> Any:
    if key in {"name", "east_asian_name", "complex_script_name"}:
        typeface = run_properties.find(f"{{{A_NS}}}{_PORTION_TYPEFACE_TAGS[key]}")
        return None if typeface is None else typeface.attrib.get("typeface")
    if key == "size":
        raw = run_properties.attrib.get("sz")
        return None if raw is None else _centipoints_to_emu(int(raw))
    if key == "spacing":
        raw = run_properties.attrib.get("spc")
        return None if raw is None else _centipoints_to_emu(int(raw))
    if key in {"bold", "italic"}:
        return _optional_bool_xml_attr(run_properties, "b" if key == "bold" else "i")
    if key == "underline":
        raw = run_properties.attrib.get("u")
        return None if raw is None else raw != "none"
    if key == "rgb":
        return _run_properties_rgb(run_properties)
    raise KeyError(f"unsupported chart portion format property: {key!r}")


def apply_portion_format(run_properties: ET.Element, delta: dict[str, Any]) -> None:
    for key, value in delta.items():
        if key in _PORTION_TYPEFACE_TAGS:
            set_run_typeface(run_properties, _PORTION_TYPEFACE_TAGS[key], value)
        elif key in {"size", "spacing"}:
            attr = "sz" if key == "size" else "spc"
            if value is None:
                run_properties.attrib.pop(attr, None)
            else:
                run_properties.set(attr, str(_emu_to_centipoints(int(value))))
        elif key in {"bold", "italic"}:
            _set_font_bool_attribute(
                run_properties,
                "b" if key == "bold" else "i",
                value,
            )
        elif key == "underline":
            _set_font_underline(run_properties, value)
        elif key == "rgb":
            _set_font_rgb(run_properties, value)
        elif key == "color_element":
            replace_fill_color_element(run_properties, ET.fromstring(value["xml"]), value["role"])
        else:
            raise ValueError(f"unsupported chart portion format property: {key!r}")


def paragraph_format_value(paragraph_properties: ET.Element, key: str) -> Any:
    if key == "alignment":
        return paragraph_properties.attrib.get("algn")
    if key in {"indent", "margin_left"}:
        raw = paragraph_properties.attrib.get("indent" if key == "indent" else "marL")
        return None if raw is None else int(raw)
    if key in {"line_spacing", "space_before", "space_after"}:
        return _paragraph_spacing_value(paragraph_properties, key)
    raise KeyError(f"unsupported chart paragraph format property: {key!r}")


def apply_paragraph_format(
    paragraph_properties: ET.Element,
    delta: dict[str, Any],
) -> None:
    spacing: dict[str, int | float | None] = {}
    for key, value in delta.items():
        if key in {"alignment", "indent", "margin_left"}:
            attr = {"alignment": "algn", "indent": "indent", "margin_left": "marL"}[key]
            if value is None:
                paragraph_properties.attrib.pop(attr, None)
            else:
                paragraph_properties.set(attr, str(value))
        elif key in {"line_spacing", "space_before", "space_after"}:
            spacing[key] = value
        else:
            raise ValueError(f"unsupported chart paragraph format property: {key!r}")
    if spacing:
        _set_title_paragraph_spacing(paragraph_properties, spacing)


def text_block_format_value(body_properties: ET.Element, key: str) -> Any:
    if key == "rotation":
        raw = body_properties.attrib.get("rot")
        return None if raw is None else int(raw) / 60000.0
    if key == "vertical_text":
        return body_properties.attrib.get("vert")
    if key == "auto_size":
        for child in body_properties:
            local_name = child.tag.rsplit("}", 1)[-1]
            if local_name in _AUTO_FIT_TAGS:
                return local_name
        return None
    if key == "word_wrap":
        raw = body_properties.attrib.get("wrap")
        return True if raw == "square" else False if raw == "none" else None
    if key == "vertical_anchor":
        return body_properties.attrib.get("anchor")
    if key in _TEXT_BLOCK_MARGINS:
        raw = body_properties.attrib.get(_TEXT_BLOCK_MARGINS[key][0])
        return None if raw is None else int(raw)
    raise KeyError(f"unsupported chart text-block format property: {key!r}")


def apply_text_block_format(body_properties: ET.Element, delta: dict[str, Any]) -> None:
    for key, value in delta.items():
        if key == "rotation":
            _set_optional_attr(
                body_properties,
                "rot",
                None if value is None else str(int(round(float(value) * 60000))),
            )
        elif key == "vertical_text":
            _set_optional_attr(body_properties, "vert", value)
        elif key == "word_wrap":
            _set_optional_attr(
                body_properties,
                "wrap",
                None if value is None else "square" if value else "none",
            )
        elif key == "vertical_anchor":
            _set_optional_attr(body_properties, "anchor", value)
        elif key == "auto_size":
            _set_body_auto_fit(body_properties, value)
        elif key in _TEXT_BLOCK_MARGINS:
            _set_optional_attr(
                body_properties,
                _TEXT_BLOCK_MARGINS[key][0],
                None if value is None else str(int(value)),
            )
        else:
            raise ValueError(f"unsupported chart text-block format property: {key!r}")


def set_run_typeface(run_properties: ET.Element, tag: str, value: str | None) -> None:
    """Set ``a:latin``/``a:ea``/``a:cs`` keeping CT_TextCharacterProperties order."""
    element = run_properties.find(f"{{{A_NS}}}{tag}")
    if value is None:
        if element is not None:
            run_properties.remove(element)
        return
    if element is None:
        element = ET.Element(f"{{{A_NS}}}{tag}")
    else:
        run_properties.remove(element)
    order = _RUN_PROPERTIES_CHILD_ORDER.index(tag)
    insert_at = len(run_properties)
    for index, child in enumerate(list(run_properties)):
        local_name = child.tag.rsplit("}", 1)[-1]
        if (
            local_name in _RUN_PROPERTIES_CHILD_ORDER
            and _RUN_PROPERTIES_CHILD_ORDER.index(local_name) > order
        ):
            insert_at = index
            break
    run_properties.insert(insert_at, element)
    element.set("typeface", value)


_PORTION_TYPEFACE_TAGS = {
    "name": "latin",
    "east_asian_name": "ea",
    "complex_script_name": "cs",
}


def _text_body_paragraphs(text_body: ET.Element, create: bool) -> list[ET.Element]:
    paragraphs = text_body.findall(f"{{{A_NS}}}p")
    if paragraphs or not create:
        return paragraphs
    if text_body.find(f"{{{A_NS}}}bodyPr") is None:
        text_body.insert(0, ET.Element(f"{{{A_NS}}}bodyPr"))
    if text_body.find(f"{{{A_NS}}}lstStyle") is None:
        body_properties = text_body.find(f"{{{A_NS}}}bodyPr")
        assert body_properties is not None
        text_body.insert(
            list(text_body).index(body_properties) + 1,
            ET.Element(f"{{{A_NS}}}lstStyle"),
        )
    return [ET.SubElement(text_body, f"{{{A_NS}}}p")]


def _set_optional_attr(element: ET.Element, attr: str, value: str | None) -> None:
    if value is None:
        element.attrib.pop(attr, None)
    else:
        element.set(attr, value)


def _set_body_auto_fit(body_properties: ET.Element, value: str | None) -> None:
    for child in list(body_properties):
        if child.tag.rsplit("}", 1)[-1] in _AUTO_FIT_TAGS:
            body_properties.remove(child)
    if value is None:
        return
    insert_at = len(body_properties)
    for index, child in enumerate(list(body_properties)):
        if child.tag.rsplit("}", 1)[-1] in _BODY_PROPERTIES_AFTER_AUTO_FIT:
            insert_at = index
            break
    body_properties.insert(insert_at, ET.Element(f"{{{A_NS}}}{value}"))


def _normalize_typeface(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a typeface string or None")
    typeface = value.strip()
    if not typeface:
        raise ValueError(f"{name} must not be empty")
    return typeface


def _normalize_optional_bool(value: Any, name: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise TypeError(f"{name} must be True, False or None")


def _normalize_font_size(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("size must be a Length (EMU integer) or None")
    centipoints = _emu_to_centipoints(int(value))
    if not _MIN_FONT_SIZE_CENTIPOINTS <= centipoints <= _MAX_TEXT_POINT_CENTIPOINTS:
        raise ValueError("size must be between 1 and 4000 points")
    return _centipoints_to_emu(centipoints)


def _normalize_character_spacing(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("spacing must be a Length (EMU integer) or None")
    centipoints = _emu_to_centipoints(int(value))
    if abs(centipoints) > _MAX_TEXT_POINT_CENTIPOINTS:
        raise ValueError("spacing must be between -4000 and 4000 points")
    return _centipoints_to_emu(centipoints)


def _normalize_text_rotation(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("rotation must be a number of degrees or None")
    degrees = float(value)
    if not -_MAX_TEXT_ROTATION_DEGREES <= degrees <= _MAX_TEXT_ROTATION_DEGREES:
        raise ValueError("chart text rotation must be between -90 and 90 degrees")
    return int(round(degrees * 60000)) / 60000.0


def _normalize_vertical_text(value: Any) -> str | None:
    if value is None:
        return None
    if value not in VERTICAL_TEXT_TYPES:
        raise ValueError(f"vertical_text must be one of {', '.join(VERTICAL_TEXT_TYPES)} or None")
    return str(value)


def _normalize_text_margin(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an EMU integer or None")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return int(value)
