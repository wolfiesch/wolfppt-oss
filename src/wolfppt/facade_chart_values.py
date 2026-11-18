"""Chart enum normalization helpers for python-pptx facade compatibility."""

from __future__ import annotations

from typing import Any

from .enum.chart import (
    XL_AXIS_CROSSES,
    XL_CATEGORY_TYPE,
    XL_LABEL_POSITION,
    XL_LEGEND_POSITION,
    XL_MARKER_STYLE,
    XL_TICK_LABEL_POSITION,
    XL_TICK_MARK,
)


def normalize_legend_position(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if raw in _legend_position_xml_values():
            return raw
        raw_name = raw.rsplit(".", 1)[-1].upper()
        for member in XL_LEGEND_POSITION:
            if member.name == raw_name and getattr(member, "xml_value", None):
                return str(member.xml_value)
        raise ValueError(f"unsupported legend position: {value!r}")

    for member in XL_LEGEND_POSITION:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            xml_value = getattr(member, "xml_value", None)
            if not xml_value:
                raise ValueError(f"{member} has no XML representation")
            return str(xml_value)
    raise TypeError("legend position must be an XL_LEGEND_POSITION value or XML value")


def legend_position_value(value: str) -> Any:
    for member in XL_LEGEND_POSITION:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def category_axis_type_value(value: Any = None) -> Any:
    if value is None:
        return XL_CATEGORY_TYPE.CATEGORY_SCALE
    if isinstance(value, str):
        upper = value.strip().upper()
        if upper in {"TIME_SCALE", "DATE", "TIME", "DATEAX"}:
            return XL_CATEGORY_TYPE.TIME_SCALE
        if upper in {"AUTOMATIC_SCALE", "AUTO"}:
            return XL_CATEGORY_TYPE.AUTOMATIC_SCALE
        return XL_CATEGORY_TYPE.CATEGORY_SCALE
    try:
        int_val = int(value)
        if int_val == 3:
            return XL_CATEGORY_TYPE.TIME_SCALE
        if int_val == -4105:
            return XL_CATEGORY_TYPE.AUTOMATIC_SCALE
    except (TypeError, ValueError):
        pass
    return XL_CATEGORY_TYPE.CATEGORY_SCALE


def normalize_category_axis_type(value: Any) -> str:
    if value == XL_CATEGORY_TYPE.TIME_SCALE:
        return "dateAx"
    if value in (XL_CATEGORY_TYPE.CATEGORY_SCALE, XL_CATEGORY_TYPE.AUTOMATIC_SCALE):
        return "catAx"
    if isinstance(value, str):
        upper = value.strip().upper()
        if upper in {"TIME_SCALE", "DATE", "TIME", "DATEAX"}:
            return "dateAx"
        if upper in {
            "CATEGORY_SCALE",
            "CATEGORY",
            "CATAX",
            "STANDARD",
            "AUTOMATIC_SCALE",
            "AUTO",
        }:
            return "catAx"
    try:
        int_val = int(value)
        if int_val == 3:
            return "dateAx"
        if int_val in (2, -4105):
            return "catAx"
    except (TypeError, ValueError):
        pass
    raise ValueError(f"unsupported category axis type: {value!r}")


def normalize_time_unit(value: Any) -> str:
    if not isinstance(value, str):
        if hasattr(value, "name"):
            value = value.name
        elif hasattr(value, "xml_value"):
            value = value.xml_value
        else:
            value = str(value)
    val = str(value).strip().lower()
    if val in {"days", "day", "d", "0"}:
        return "days"
    if val in {"months", "month", "m", "1"}:
        return "months"
    if val in {"years", "year", "y", "2"}:
        return "years"
    raise ValueError(f"unsupported time unit: {value!r}")


def time_unit_value(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return normalize_time_unit(value)
    except ValueError:
        return str(value)


def axis_tick_mark_value(value: str) -> Any:
    for member in XL_TICK_MARK:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def tick_label_position_value(value: str) -> Any:
    for member in XL_TICK_LABEL_POSITION:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def data_label_position_value(value: str | None) -> Any:
    if value is None:
        return None
    for member in XL_LABEL_POSITION:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def axis_crosses_value(value: str | None) -> Any:
    if value is None:
        return XL_AXIS_CROSSES.CUSTOM
    for member in XL_AXIS_CROSSES:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def marker_style_value(value: str | None) -> Any:
    if value is None:
        return None
    for member in XL_MARKER_STYLE:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def normalize_axis_tick_mark(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if raw in _axis_tick_mark_xml_values():
            return raw
        raw_name = raw.split("(", 1)[0].strip().rsplit(".", 1)[-1].upper()
        for member in XL_TICK_MARK:
            if member.name == raw_name and getattr(member, "xml_value", None):
                return str(member.xml_value)
        try:
            numeric_value = int(raw)
        except ValueError:
            numeric_value = None
        if numeric_value is not None:
            for member in XL_TICK_MARK:
                if numeric_value == int(member):
                    return str(member.xml_value)
        raise ValueError(f"unsupported axis tick mark: {value!r}")

    for member in XL_TICK_MARK:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            xml_value = getattr(member, "xml_value", None)
            if not xml_value:
                raise ValueError(f"{member} has no XML representation")
            return str(xml_value)
    raise TypeError("axis tick mark must be an XL_TICK_MARK value or XML value")


def normalize_tick_label_position(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if raw in _tick_label_position_xml_values():
            return raw
        raw_name = raw.split("(", 1)[0].strip().rsplit(".", 1)[-1].upper()
        for member in XL_TICK_LABEL_POSITION:
            if member.name == raw_name and getattr(member, "xml_value", None):
                return str(member.xml_value)
        try:
            numeric_value = int(raw)
        except ValueError:
            numeric_value = None
        if numeric_value is not None:
            for member in XL_TICK_LABEL_POSITION:
                if numeric_value == int(member):
                    return str(member.xml_value)
        raise ValueError(f"unsupported tick label position: {value!r}")

    for member in XL_TICK_LABEL_POSITION:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            xml_value = getattr(member, "xml_value", None)
            if not xml_value:
                raise ValueError(f"{member} has no XML representation")
            return str(xml_value)
    raise TypeError(
        "tick label position must be an XL_TICK_LABEL_POSITION value or XML value"
    )


def normalize_data_label_position(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        raw = value.strip()
        if raw in _data_label_position_xml_values():
            return raw
        raw_name = raw.split("(", 1)[0].strip().rsplit(".", 1)[-1].upper()
        for member in XL_LABEL_POSITION:
            if member.name == raw_name and getattr(member, "xml_value", None):
                return str(member.xml_value)
        try:
            numeric_value = int(raw)
        except ValueError:
            numeric_value = None
        if numeric_value is not None:
            for member in XL_LABEL_POSITION:
                if numeric_value == int(member):
                    xml_value = getattr(member, "xml_value", None)
                    if not xml_value:
                        raise ValueError(f"{member} has no XML representation")
                    return str(xml_value)
        raise ValueError(f"unsupported data label position: {value!r}")

    for member in XL_LABEL_POSITION:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            xml_value = getattr(member, "xml_value", None)
            if not xml_value:
                raise ValueError(f"{member} has no XML representation")
            return str(xml_value)
    raise TypeError("data label position must be an XL_LABEL_POSITION value or None")


def normalize_marker_style(value: Any) -> str | None:
    if value is None:
        return None

    for member in XL_MARKER_STYLE:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            xml_value = getattr(member, "xml_value", None)
            if not xml_value:
                raise ValueError(f"{member} has no XML representation")
            return str(xml_value)
    if isinstance(value, str):
        raw = value.strip()
        if raw in _marker_style_xml_values():
            return raw
    raise ValueError(f"{value!r} is not a valid XL_MARKER_STYLE")


def normalize_marker_size(value: Any) -> int | None:
    if value is None:
        return None
    try:
        size = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("marker size must be an integer in the range 2 to 72") from exc
    if size < 2 or size > 72:
        raise ValueError(f"value must be in range 2 to 72 inclusive, got {size}")
    return size


def normalize_axis_crosses(value: Any) -> str | None:
    if isinstance(value, str):
        raw = value.strip()
        if raw in _axis_crosses_xml_values():
            return raw
        raw_name = raw.split("(", 1)[0].strip().rsplit(".", 1)[-1].upper()
        if raw_name == "CUSTOM":
            return None
        for member in XL_AXIS_CROSSES:
            if member.name == raw_name:
                return _axis_crosses_member_xml(member)
        try:
            numeric_value = int(raw)
        except ValueError:
            numeric_value = None
        if numeric_value is not None:
            for member in XL_AXIS_CROSSES:
                if numeric_value == int(member):
                    return _axis_crosses_member_xml(member)
        raise ValueError(f"unsupported axis crossing value: {value!r}")

    for member in XL_AXIS_CROSSES:
        try:
            matches = value == member or int(value) == int(member)
        except (TypeError, ValueError):
            matches = value == member
        if matches:
            return _axis_crosses_member_xml(member)
    raise TypeError("axis crossing must be an XL_AXIS_CROSSES value or XML value")


def _axis_crosses_member_xml(member: Any) -> str | None:
    xml_value = getattr(member, "xml_value", None)
    return None if not xml_value else str(xml_value)


def _legend_position_xml_values() -> set[str]:
    return {"b", "tr", "l", "r", "t"}


def _axis_tick_mark_xml_values() -> set[str]:
    return {"cross", "in", "none", "out"}


def _tick_label_position_xml_values() -> set[str]:
    return {"high", "low", "nextTo", "none"}


def _data_label_position_xml_values() -> set[str]:
    return {"bestFit", "b", "ctr", "inBase", "inEnd", "l", "outEnd", "r", "t"}


def _axis_crosses_xml_values() -> set[str]:
    return {"autoZero", "max", "min"}


def _marker_style_xml_values() -> set[str]:
    return {
        "auto",
        "circle",
        "dash",
        "diamond",
        "dot",
        "none",
        "picture",
        "plus",
        "square",
        "star",
        "triangle",
        "x",
    }
