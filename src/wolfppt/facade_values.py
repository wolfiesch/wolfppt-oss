"""python-pptx facade value normalization helpers."""

from __future__ import annotations

from importlib.util import find_spec
from numbers import Number
from typing import Any, Self

from .dml.color import RGBColor
from .enum.dml import (
    MSO_COLOR_TYPE,
    MSO_FILL,
    MSO_LINE_DASH_STYLE,
    MSO_PATTERN_TYPE,
    MSO_THEME_COLOR,
)
from .enum.lang import MSO_LANGUAGE_ID
from .enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from .facade_chart_values import (
    axis_crosses_value,
    axis_tick_mark_value,
    category_axis_type_value,
    data_label_position_value,
    legend_position_value,
    normalize_axis_crosses,
    normalize_axis_tick_mark,
    normalize_data_label_position,
    normalize_legend_position,
    normalize_tick_label_position,
    tick_label_position_value,
)
from .util import Centipoints, Emu, Length

LANGUAGE_ID_NONE = "__wolfppt_language_id_none__"
MAX_PARAGRAPH_SPACING_EMU = 20116800
MAX_LINE_SPACING_MULTIPLE = 132.0
MAX_PARAGRAPH_INDENT_EMU = 51206400


def normalize_rgb(value: Any) -> str:
    if isinstance(value, str):
        cleaned = value.strip().lstrip("#").upper()
        if len(cleaned) == 6 and all(char in "0123456789ABCDEF" for char in cleaned):
            return cleaned
        raise ValueError("RGB color strings must use six hexadecimal digits")
    try:
        red, green, blue = value
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "rgb must be an RGBColor, RGB tuple, or six-digit hex string"
        ) from exc
    channels = (int(red), int(green), int(blue))
    if any(channel < 0 or channel > 255 for channel in channels):
        raise ValueError("RGB channels must be between 0 and 255")
    return "{:02X}{:02X}{:02X}".format(*channels)


def normalize_paragraph_alignment(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("paragraph alignment must not be empty")
        for xml_value in _paragraph_alignment_xml_values():
            if raw == xml_value:
                return raw
        raw_name = raw.rsplit(".", 1)[-1].upper()
        for member in PP_ALIGN:
            if member.name == raw_name and member.xml_value:
                return member.xml_value
        raise ValueError(f"unsupported paragraph alignment: {value!r}")

    for member in PP_ALIGN:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            if not member.xml_value:
                raise ValueError(f"{member} has no XML representation")
            return member.xml_value
    raise TypeError("paragraph alignment must be a PP_ALIGN value, XML value, or None")


def coerce_paragraph_level(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"invalid literal for int() with base 10: {str(value)!r}")
    if not isinstance(value, int):
        raise TypeError(f"value must be an integral type, got {type(value)!r}")
    if value < 0 or value > 8:
        raise ValueError(f"value must be in range 0 to 8 inclusive, got {value}")
    return int(value)


def normalize_paragraph_spacing_length(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise TypeError(f"value must be an integral type, got {type(value)!r}")
    value = int(value)
    if value < 0 or value > MAX_PARAGRAPH_SPACING_EMU:
        raise ValueError(
            f"value must be in range 0 to {MAX_PARAGRAPH_SPACING_EMU} inclusive, got {value}"
        )
    return value


def normalize_paragraph_indent(value: Any, name: str) -> int | None:
    """Validate CT_TextParagraphProperties margin or indent EMUs."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integral EMU value, got {type(value)!r}")
    minimum = -MAX_PARAGRAPH_INDENT_EMU if name == "indent" else 0
    if value < minimum or value > MAX_PARAGRAPH_INDENT_EMU:
        raise ValueError(
            f"{name} must be in range {minimum} to {MAX_PARAGRAPH_INDENT_EMU} inclusive, got {value}"
        )
    return int(value)


def normalize_line_spacing(value: Any) -> int | float | None:
    if value is None:
        return None
    if _is_length_value(value):
        spacing = int(value)
        if spacing < 0 or spacing > MAX_PARAGRAPH_SPACING_EMU:
            raise ValueError(
                f"value must be in range 0 to {MAX_PARAGRAPH_SPACING_EMU} inclusive, got {spacing}"
            )
        return spacing
    if not isinstance(value, (int, float)):
        raise TypeError(f"value must be a number, got {type(value)!r}")
    multiple = float(value)
    if multiple < 0 or multiple > MAX_LINE_SPACING_MULTIPLE:
        raise ValueError(
            f"value must be in range 0.0 to {MAX_LINE_SPACING_MULTIPLE:.1f} inclusive, got {value}"
        )
    return multiple


def normalize_line_dash_style(value: Any) -> str | None:
    if value is None:
        return None
    xml_values = _line_dash_style_xml_values()
    if isinstance(value, str):
        raw = value.strip()
        if raw in xml_values:
            return raw
        raw_name = raw.rsplit(".", 1)[-1].upper()
        for member in MSO_LINE_DASH_STYLE:
            if member.name == raw_name and member.xml_value:
                return member.xml_value
        raise ValueError(f"unsupported line dash style: {value!r}")

    for member in MSO_LINE_DASH_STYLE:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            if not member.xml_value:
                raise ValueError(f"{member} has no XML representation")
            return member.xml_value
    raise TypeError(
        "line dash style must be an MSO_LINE_DASH_STYLE value, XML value, or None"
    )


def normalize_pattern_type(value: Any) -> str | None:
    if value is None:
        return None
    xml_values = _pattern_type_xml_values()
    if isinstance(value, str):
        raw = value.strip()
        if raw in xml_values:
            return raw
        raw_name = raw.rsplit(".", 1)[-1].upper()
        for member in MSO_PATTERN_TYPE:
            if member.name == raw_name and member.xml_value:
                return member.xml_value
        raise ValueError(f"unsupported pattern type: {value!r}")

    for member in MSO_PATTERN_TYPE:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            if not member.xml_value:
                raise ValueError(f"{member} has no XML representation")
            return member.xml_value
    raise TypeError(
        "pattern type must be an MSO_PATTERN_TYPE value, XML value, or None"
    )


def normalize_theme_color(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if raw in _theme_color_xml_values():
            return raw
        raw_name = raw.rsplit(".", 1)[-1].upper()
        for member in MSO_THEME_COLOR:
            if member.name == raw_name and member.xml_value:
                return member.xml_value
        raise ValueError(f"unsupported theme color: {value!r}")

    for member in MSO_THEME_COLOR:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            if not member.xml_value:
                raise ValueError(f"{member} has no XML representation")
            return member.xml_value
    raise TypeError("theme_color must be an MSO_THEME_COLOR value or XML value")


def normalize_language_id(value: Any) -> str | None:
    if value is None:
        return None
    language_id = MSO_LANGUAGE_ID(value)
    if language_id == MSO_LANGUAGE_ID.NONE:
        return None
    return str(language_id.xml_value)


def paragraph_alignment_value(value: str | None) -> Any:
    if value is None:
        return None
    for member in PP_ALIGN:
        if member.xml_value == value:
            return member
    return value


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def normalize_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Number):
        raise TypeError(f"value must be a number or None, got {type(value)!r}")
    return float(value)


def line_dash_style_value(value: str | None) -> Any:
    if value is None:
        return None
    for member in MSO_LINE_DASH_STYLE:
        if member.xml_value == value:
            return member
    return value


def pattern_type_value(value: str | None) -> Any:
    if value is None:
        return None
    for member in MSO_PATTERN_TYPE:
        if member.xml_value == value:
            return member
    return value


def language_id_value(value: str | None) -> Any:
    if value == LANGUAGE_ID_NONE:
        value = None
    if value is None:
        return MSO_LANGUAGE_ID.NONE
    for member in MSO_LANGUAGE_ID:
        if member.xml_value == value:
            return member
    return value


def fill_type_value(value: str | None) -> Any:
    if value is None:
        return None
    mapping = {
        "solid": MSO_FILL.SOLID,
        "background": MSO_FILL.BACKGROUND,
        "patterned": MSO_FILL.PATTERNED,
        "gradient": MSO_FILL.GRADIENT,
        "picture": MSO_FILL.PICTURE,
        "group": MSO_FILL.GROUP,
    }
    return mapping.get(value, value)


def color_type_value(value: str | None) -> Any:
    if value is None:
        return None
    if value == "rgb":
        return MSO_COLOR_TYPE.RGB
    if value == "scheme":
        return MSO_COLOR_TYPE.SCHEME
    return value


def theme_color_value(value: str) -> Any:
    if value == "":
        return MSO_THEME_COLOR.NOT_THEME_COLOR
    for member in MSO_THEME_COLOR:
        if member.xml_value == value:
            return member
    return value


def normalize_text_frame_word_wrap(value: Any) -> bool | None:
    if value is None:
        return None
    if value in (True, False):
        return bool(value)
    raise ValueError(f"assigned value must be True, False, or None, got {value}")


def normalize_text_frame_vertical_anchor(value: Any) -> str | None:
    if value is None:
        return None
    for member in MSO_ANCHOR:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches and member.xml_value:
            return member.xml_value
    raise ValueError(f"{value!r} is not a valid MSO_VERTICAL_ANCHOR")


def text_frame_vertical_anchor_value(value: str | None) -> Any:
    if value is None:
        return None
    for member in MSO_ANCHOR:
        if member.xml_value == value:
            return member
    return value


_TEXT_FRAME_AUTO_SIZE_XML_VALUES = frozenset({"noAutofit", "spAutoFit", "normAutofit"})
# python-pptx MSO_AUTO_SIZE member values; MIXED (-2) clears the setting.
_TEXT_FRAME_AUTO_SIZE_BY_NUMBER: dict[int, str | None] = {
    -2: None,
    0: "noAutofit",
    1: "spAutoFit",
    2: "normAutofit",
}
_TEXT_FRAME_AUTO_SIZE_MEMBERS: dict[str, tuple[str, int]] = {
    "noAutofit": ("NONE", 0),
    "spAutoFit": ("SHAPE_TO_FIT_TEXT", 1),
    "normAutofit": ("TEXT_TO_FIT_SHAPE", 2),
}


class TextFrameAutoSize(str):
    """Text frame auto-size read back as both an MSO_AUTO_SIZE value and an XML token.

    Compares equal to the matching ``MSO_AUTO_SIZE`` member, its integer value,
    and the legacy ``a:bodyPr`` child token (``"normAutofit"``). Remains a
    ``str`` so JSON output keeps the token. The hash follows ``MSO_AUTO_SIZE``
    when python-pptx is installed (so enum-keyed lookups resolve) and the token
    otherwise (so token-keyed lookups resolve), matching what earlier releases
    returned in each runtime. Detection uses ``find_spec`` and never imports it.
    """

    name: str
    value: int
    xml_value: str
    _hash: int

    def __new__(cls, xml_value: str) -> Self:
        name, number = _TEXT_FRAME_AUTO_SIZE_MEMBERS[xml_value]
        self = super().__new__(cls, xml_value)
        self.name = name
        self.value = number
        self.xml_value = xml_value
        self._hash = (
            hash(MSO_AUTO_SIZE[name])
            if find_spec("pptx") is not None
            else hash(xml_value)
        )
        return self

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.xml_value == str.__str__(other)
        if isinstance(other, int):
            return self.value == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        equal = self.__eq__(other)
        return equal if equal is NotImplemented else not equal

    def __hash__(self) -> int:
        return self._hash

    def __int__(self) -> int:
        return self.value

    def __index__(self) -> int:
        return self.value

    def __repr__(self) -> str:
        return f"<MSO_AUTO_SIZE.{self.name}: {self.value}>"


_TEXT_FRAME_AUTO_SIZE_VALUES: dict[str, TextFrameAutoSize] = {}


def normalize_text_frame_auto_size(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, TextFrameAutoSize):
        return value.xml_value
    if isinstance(value, str):
        if value in _TEXT_FRAME_AUTO_SIZE_XML_VALUES:
            return value
    elif not (isinstance(value, float) and not value.is_integer()):
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = None
        if numeric in _TEXT_FRAME_AUTO_SIZE_BY_NUMBER:
            return _TEXT_FRAME_AUTO_SIZE_BY_NUMBER[numeric]
    raise ValueError(f"{value!r} is not a valid MSO_AUTO_SIZE")


def text_frame_auto_size_value(value: str | None) -> Any:
    if value not in _TEXT_FRAME_AUTO_SIZE_MEMBERS:
        return value
    cached = _TEXT_FRAME_AUTO_SIZE_VALUES.get(value)
    if cached is None:
        cached = _TEXT_FRAME_AUTO_SIZE_VALUES[value] = TextFrameAutoSize(value)
    return cached


def rgb_value(rgb: str) -> RGBColor:
    return RGBColor.from_string(rgb)


def centipoints_value(value: int) -> Centipoints:
    return Centipoints(value)


def emu_to_centipoints(value: int) -> int:
    return int(round(value / 127))


def centipoints_to_emu(value: int) -> int:
    return int(value) * 127


def paragraph_spacing_xml_tag(attr: str) -> str:
    mapping = {
        "line_spacing": "lnSpc",
        "space_before": "spcBef",
        "space_after": "spcAft",
    }
    return mapping[attr]


def emu_value(value: int) -> Emu:
    return Emu(value)


def coerce_emu(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be an integer EMU value") from exc


def coerce_crop_fraction(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"value must be a number, got {type(value)!r}")
    return float(value)


def coerce_rotation_degrees(value: Any) -> float:
    if not isinstance(value, (int, float)):
        raise TypeError(f"value must be a number, got {type(value)!r}")
    units = int(round(float(value) * 60000)) % (360 * 60000)
    return rotation_degrees_from_units(units)


def rotation_openxml_units(value: float) -> int:
    return int(round(float(value) * 60000)) % (360 * 60000)


def rotation_degrees_from_units(value: int) -> float:
    return (int(value) % (360 * 60000)) / 60000.0


def coerce_positive_int(value: Any, name: str) -> int:
    coerced = coerce_emu(value, name)
    if coerced < 1:
        raise ValueError(f"{name} must be greater than zero")
    return coerced


def _is_length_value(value: Any) -> bool:
    return isinstance(value, Length) or (
        isinstance(value, int) and not isinstance(value, bool) and abs(value) > 132
    )


def _axis_crosses_member_xml(member: Any) -> str | None:
    xml_value = getattr(member, "xml_value", None)
    return None if not xml_value else str(xml_value)


def _paragraph_alignment_xml_values() -> set[str]:
    return {"l", "ctr", "r", "just", "dist", "thaiDist", "justLow"}


def _line_dash_style_xml_values() -> set[str]:
    return {
        "solid",
        "dot",
        "dash",
        "lgDash",
        "dashDot",
        "lgDashDot",
        "lgDashDotDot",
        "sysDash",
        "sysDot",
        "sysDashDot",
        "sysDashDotDot",
    }


def _pattern_type_xml_values() -> set[str]:
    return {member.xml_value for member in MSO_PATTERN_TYPE if member.xml_value}


def _theme_color_xml_values() -> set[str]:
    return {member.xml_value for member in MSO_THEME_COLOR if member.xml_value}
