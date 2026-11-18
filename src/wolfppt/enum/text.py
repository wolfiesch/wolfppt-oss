"""Text-related enumerations."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from .base import BaseEnum, BaseXmlEnum


class ParagraphFontAlignmentRefusal(ValueError):
    """Unsupported paragraph font alignment, refused before queueing an edit."""


class ParagraphFontAlignment(StrEnum):
    """DrawingML paragraph font alignment, independent of text-frame anchoring."""

    AUTO = "auto"
    TOP = "t"
    CENTER = "ctr"
    BASELINE = "base"
    BOTTOM = "b"

    @classmethod
    def from_xml(cls, value: object) -> Self:
        """Convert a supported XML token or refuse without coercing other types."""
        if isinstance(value, str):
            try:
                return cls(value)
            except ValueError:
                pass
        raise ParagraphFontAlignmentRefusal(
            f"font_alignment must be auto, t, ctr, base, b or None, got {value!r}"
        )


class MSO_AUTO_SIZE(BaseEnum):
    """python-pptx compatible `MSO_AUTO_SIZE` enumeration."""

    NONE = (0,)
    SHAPE_TO_FIT_TEXT = (1,)
    TEXT_TO_FIT_SHAPE = (2,)
    MIXED = (-2,)


class MSO_TEXT_UNDERLINE_TYPE(BaseXmlEnum):
    """python-pptx compatible `MSO_TEXT_UNDERLINE_TYPE` enumeration."""

    NONE = (0, "none")
    DASH_HEAVY_LINE = (8, "dashHeavy")
    DASH_LINE = (7, "dash")
    DASH_LONG_HEAVY_LINE = (10, "dashLongHeavy")
    DASH_LONG_LINE = (9, "dashLong")
    DOT_DASH_HEAVY_LINE = (12, "dotDashHeavy")
    DOT_DASH_LINE = (11, "dotDash")
    DOT_DOT_DASH_HEAVY_LINE = (14, "dotDotDashHeavy")
    DOT_DOT_DASH_LINE = (13, "dotDotDash")
    DOTTED_HEAVY_LINE = (6, "dottedHeavy")
    DOTTED_LINE = (5, "dotted")
    DOUBLE_LINE = (3, "dbl")
    HEAVY_LINE = (4, "heavy")
    SINGLE_LINE = (2, "sng")
    WAVY_DOUBLE_LINE = (17, "wavyDbl")
    WAVY_HEAVY_LINE = (16, "wavyHeavy")
    WAVY_LINE = (15, "wavy")
    WORDS = (1, "words")
    MIXED = (-2, "")


class MSO_VERTICAL_ANCHOR(BaseXmlEnum):
    """python-pptx compatible `MSO_VERTICAL_ANCHOR` enumeration."""

    TOP = (1, "t")
    MIDDLE = (3, "ctr")
    BOTTOM = (4, "b")
    MIXED = (-2, "")


class PP_PARAGRAPH_ALIGNMENT(BaseXmlEnum):
    """python-pptx compatible `PP_PARAGRAPH_ALIGNMENT` enumeration."""

    CENTER = (2, "ctr")
    DISTRIBUTE = (5, "dist")
    JUSTIFY = (4, "just")
    JUSTIFY_LOW = (7, "justLow")
    LEFT = (1, "l")
    RIGHT = (3, "r")
    THAI_DISTRIBUTE = (6, "thaiDist")
    MIXED = (-2, "")


MSO_UNDERLINE = MSO_TEXT_UNDERLINE_TYPE
MSO_ANCHOR = MSO_VERTICAL_ANCHOR
PP_ALIGN = PP_PARAGRAPH_ALIGNMENT

__all__ = [
    "MSO_ANCHOR",
    "MSO_AUTO_SIZE",
    "MSO_TEXT_UNDERLINE_TYPE",
    "MSO_UNDERLINE",
    "MSO_VERTICAL_ANCHOR",
    "PP_ALIGN",
    "PP_PARAGRAPH_ALIGNMENT",
    "BaseEnum",
    "BaseXmlEnum",
    "ParagraphFontAlignment",
    "ParagraphFontAlignmentRefusal",
]
