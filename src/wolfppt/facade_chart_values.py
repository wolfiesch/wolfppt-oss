"""Chart enum normalization helpers for python-pptx facade compatibility."""

from __future__ import annotations

from typing import Any


def normalize_legend_position(value: Any) -> str:
    try:
        from pptx.enum.chart import XL_LEGEND_POSITION
    except ImportError:
        XL_LEGEND_POSITION = None  # type: ignore[assignment]

    if isinstance(value, str):
        raw = value.strip()
        if raw in _legend_position_xml_values():
            return raw
        raw_name = raw.rsplit(".", 1)[-1].upper()
        if XL_LEGEND_POSITION is not None:
            for member in XL_LEGEND_POSITION:
                if member.name == raw_name and getattr(member, "xml_value", None):
                    return str(member.xml_value)
        raise ValueError(f"unsupported legend position: {value!r}")

    if XL_LEGEND_POSITION is not None:
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
    try:
        from pptx.enum.chart import XL_LEGEND_POSITION
    except ImportError:
        return value
    for member in XL_LEGEND_POSITION:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def category_axis_type_value() -> Any:
    try:
        from pptx.enum.chart import XL_CATEGORY_TYPE
    except ImportError:
        return 2
    return XL_CATEGORY_TYPE.CATEGORY_SCALE


def axis_tick_mark_value(value: str) -> Any:
    try:
        from pptx.enum.chart import XL_TICK_MARK
    except ImportError:
        return value
    for member in XL_TICK_MARK:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def tick_label_position_value(value: str) -> Any:
    try:
        from pptx.enum.chart import XL_TICK_LABEL_POSITION
    except ImportError:
        return value
    for member in XL_TICK_LABEL_POSITION:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def data_label_position_value(value: str | None) -> Any:
    if value is None:
        return None
    try:
        from pptx.enum.chart import XL_LABEL_POSITION
    except ImportError:
        return value
    for member in XL_LABEL_POSITION:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def axis_crosses_value(value: str | None) -> Any:
    try:
        from pptx.enum.chart import XL_AXIS_CROSSES
    except ImportError:
        return None if value is None else value
    if value is None:
        return XL_AXIS_CROSSES.CUSTOM
    for member in XL_AXIS_CROSSES:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def marker_style_value(value: str | None) -> Any:
    if value is None:
        return None
    try:
        from pptx.enum.chart import XL_MARKER_STYLE
    except ImportError:
        return value
    for member in XL_MARKER_STYLE:
        if getattr(member, "xml_value", None) == value:
            return member
    return value


def normalize_axis_tick_mark(value: Any) -> str:
    try:
        from pptx.enum.chart import XL_TICK_MARK
    except ImportError:
        XL_TICK_MARK = None  # type: ignore[assignment]

    if isinstance(value, str):
        raw = value.strip()
        if raw in _axis_tick_mark_xml_values():
            return raw
        raw_name = raw.split("(", 1)[0].strip().rsplit(".", 1)[-1].upper()
        if XL_TICK_MARK is not None:
            for member in XL_TICK_MARK:
                if member.name == raw_name and getattr(member, "xml_value", None):
                    return str(member.xml_value)
        try:
            numeric_value = int(raw)
        except ValueError:
            numeric_value = None
        if numeric_value is not None and XL_TICK_MARK is not None:
            for member in XL_TICK_MARK:
                if numeric_value == int(member):
                    return str(member.xml_value)
        raise ValueError(f"unsupported axis tick mark: {value!r}")

    if XL_TICK_MARK is not None:
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
    try:
        from pptx.enum.chart import XL_TICK_LABEL_POSITION
    except ImportError:
        XL_TICK_LABEL_POSITION = None  # type: ignore[assignment]

    if isinstance(value, str):
        raw = value.strip()
        if raw in _tick_label_position_xml_values():
            return raw
        raw_name = raw.split("(", 1)[0].strip().rsplit(".", 1)[-1].upper()
        if XL_TICK_LABEL_POSITION is not None:
            for member in XL_TICK_LABEL_POSITION:
                if member.name == raw_name and getattr(member, "xml_value", None):
                    return str(member.xml_value)
        try:
            numeric_value = int(raw)
        except ValueError:
            numeric_value = None
        if numeric_value is not None and XL_TICK_LABEL_POSITION is not None:
            for member in XL_TICK_LABEL_POSITION:
                if numeric_value == int(member):
                    return str(member.xml_value)
        raise ValueError(f"unsupported tick label position: {value!r}")

    if XL_TICK_LABEL_POSITION is not None:
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
    try:
        from pptx.enum.chart import XL_LABEL_POSITION
    except ImportError:
        XL_LABEL_POSITION = None  # type: ignore[assignment]

    if isinstance(value, str):
        raw = value.strip()
        if raw in _data_label_position_xml_values():
            return raw
        raw_name = raw.split("(", 1)[0].strip().rsplit(".", 1)[-1].upper()
        if XL_LABEL_POSITION is not None:
            for member in XL_LABEL_POSITION:
                if member.name == raw_name and getattr(member, "xml_value", None):
                    return str(member.xml_value)
        try:
            numeric_value = int(raw)
        except ValueError:
            numeric_value = None
        if numeric_value is not None and XL_LABEL_POSITION is not None:
            for member in XL_LABEL_POSITION:
                if numeric_value == int(member):
                    xml_value = getattr(member, "xml_value", None)
                    if not xml_value:
                        raise ValueError(f"{member} has no XML representation")
                    return str(xml_value)
        raise ValueError(f"unsupported data label position: {value!r}")

    if XL_LABEL_POSITION is not None:
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
    try:
        from pptx.enum.chart import XL_MARKER_STYLE
    except ImportError:
        XL_MARKER_STYLE = None  # type: ignore[assignment]

    if XL_MARKER_STYLE is not None:
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
    try:
        from pptx.enum.chart import XL_AXIS_CROSSES
    except ImportError:
        XL_AXIS_CROSSES = None  # type: ignore[assignment]

    if isinstance(value, str):
        raw = value.strip()
        if raw in _axis_crosses_xml_values():
            return raw
        raw_name = raw.split("(", 1)[0].strip().rsplit(".", 1)[-1].upper()
        if raw_name == "CUSTOM":
            return None
        if XL_AXIS_CROSSES is not None:
            for member in XL_AXIS_CROSSES:
                if member.name == raw_name:
                    return _axis_crosses_member_xml(member)
        try:
            numeric_value = int(raw)
        except ValueError:
            numeric_value = None
        if numeric_value is not None and XL_AXIS_CROSSES is not None:
            for member in XL_AXIS_CROSSES:
                if numeric_value == int(member):
                    return _axis_crosses_member_xml(member)
        raise ValueError(f"unsupported axis crossing value: {value!r}")

    if XL_AXIS_CROSSES is not None:
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
