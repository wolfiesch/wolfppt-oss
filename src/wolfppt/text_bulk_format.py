"""Validated bulk run formatting for WolfPPT shapes, tables and slides.

Import ``set_text_format`` from this module to format a whole slide, including
text in grouped shapes and unmerged table cells. Every requested field and every
target font are checked before queuing an edit. Save with ``Presentation.save``.
Fields absent from the request and unrelated package parts remain untouched.
"""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree as ET

from .facade_values import normalize_rgb
from .text_facade import _bulk_text_frames, _check_bulk_fields
from .text_run_facade import _STRIKETHROUGH_TOKENS
from .text_xml import A_NS, _set_portion_format


class TextFormattingRefusal(ValueError):
    """A bulk target or format cannot be represented without partial edits."""


_PORTION_FIELDS = {
    "kerning": "kern",
    "caps": "cap",
    "strikethrough_type": "strike",
    "east_asian_font": "ea",
    "complex_script_font": "cs",
}
_SUPPORTED_FIELDS = frozenset(_PORTION_FIELDS) | {
    "bold",
    "italic",
    "size",
    "name",
    "color",
    "highlight_color",
}
_XML_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def _validated_fields(fields: dict[str, Any]) -> dict[str, Any]:
    if not fields:
        raise TextFormattingRefusal("pass at least one format field")
    unknown = fields.keys() - _SUPPORTED_FIELDS
    if unknown:
        raise TextFormattingRefusal(f"unsupported format fields: {', '.join(sorted(unknown))}")
    normalized = dict(fields)
    try:
        properties = ET.Element(f"{{{A_NS}}}rPr")
        for name, value in fields.items():
            if isinstance(value, str) and _XML_ILLEGAL.search(value):
                raise ValueError(f"{name} contains a character forbidden in XML")
            if name in _PORTION_FIELDS:
                token = value
                if name == "strikethrough_type" and value is not None:
                    if not isinstance(value, str) or value not in _STRIKETHROUGH_TOKENS:
                        raise ValueError("strikethrough_type must be none, single, double or None")
                    token = _STRIKETHROUGH_TOKENS[value]
                _set_portion_format(properties, {_PORTION_FIELDS[name]: token})
            elif name in {"bold", "italic"}:
                if value is not None and not isinstance(value, bool):
                    raise TypeError(f"{name} must be bool or None")
            elif name == "size":
                if value is not None and (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or not 12700 <= value <= 50800000
                    or value % 127 != 0
                ):
                    raise ValueError(
                        "size must be 1..4000 points in integral hundredths of a point"
                    )
            elif name == "name":
                if value is not None and (not isinstance(value, str) or not value.strip()):
                    raise TypeError("name must be a non-empty string or None")
            elif name == "color" or (name == "highlight_color" and value is not None):
                normalized[name] = normalize_rgb(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TextFormattingRefusal(str(exc)) from exc
    return normalized


def _frames(target: Any) -> list[Any]:
    if (
        getattr(target, "has_table", False)
        or getattr(target, "has_text_frame", False)
        or hasattr(target, "paragraphs")
        or (hasattr(target, "rows") and hasattr(target, "columns"))
    ):
        return _bulk_text_frames(target)
    if hasattr(target, "shapes"):
        frames = []
        for shape in target.shapes:
            if (
                getattr(shape, "has_table", False)
                or getattr(shape, "has_text_frame", False)
                or hasattr(shape, "shapes")
            ):
                frames.extend(_frames(shape))
        return frames
    raise TextFormattingRefusal("pass a slide, text shape, table or text frame")


def set_text_format(target: Any, **fields: Any) -> None:
    """Set run properties across a shape, table, frame or entire slide.

    Supported fields: ``bold``, ``italic``, ``size`` (EMU), ``name``, ``color``
    (RGB), ``kerning`` (hundredths of a point), ``caps``, ``strikethrough_type``,
    ``east_asian_font``, ``complex_script_font`` and ``highlight_color``. Use
    ``None`` for inheritance, except ``color`` which requires an RGB value.
    Font sizes must be 1..4000 points, exactly representable in hundredths of
    a point (127 EMU); unrepresentable sizes refuse before any target changes.
    A field unsupported by any target font raises :class:`TextFormattingRefusal`
    before any run changes. For example, advanced run properties unavailable on
    table cells refuse a mixed slide rather than formatting only its shapes.
    """
    normalized = _validated_fields(fields)
    fonts = [
        run.font
        for frame in _frames(target)
        for paragraph in frame.paragraphs
        for run in paragraph.runs
    ]
    try:
        _check_bulk_fields(fonts, normalized, {"color": lambda font: True})
    except (TypeError, ValueError) as exc:
        raise TextFormattingRefusal(str(exc)) from exc
    for font in fonts:
        for name, value in normalized.items():
            if name == "color":
                font.color.rgb = value
            else:
                setattr(font, name, value)
