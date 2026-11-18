"""DrawingML-related enumerations."""

from __future__ import annotations

from .base import BaseEnum, BaseXmlEnum


class MSO_COLOR_TYPE(BaseEnum):
    """python-pptx compatible `MSO_COLOR_TYPE` enumeration."""

    RGB = (1,)
    SCHEME = (2,)
    HSL = (101,)
    PRESET = (102,)
    SCRGB = (103,)
    SYSTEM = (104,)


class MSO_FILL_TYPE(BaseEnum):
    """python-pptx compatible `MSO_FILL_TYPE` enumeration."""

    BACKGROUND = (5,)
    GRADIENT = (3,)
    GROUP = (101,)
    PATTERNED = (2,)
    PICTURE = (6,)
    SOLID = (1,)
    TEXTURED = (4,)


class MSO_LINE_DASH_STYLE(BaseXmlEnum):
    """python-pptx compatible `MSO_LINE_DASH_STYLE` enumeration."""

    DASH = (4, "dash")
    DASH_DOT = (5, "dashDot")
    DASH_DOT_DOT = (6, "lgDashDotDot")
    LONG_DASH = (7, "lgDash")
    LONG_DASH_DOT = (8, "lgDashDot")
    ROUND_DOT = (3, "sysDot")
    SOLID = (1, "solid")
    SQUARE_DOT = (2, "sysDash")
    DASH_STYLE_MIXED = (-2, "")


class MSO_PATTERN_TYPE(BaseXmlEnum):
    """python-pptx compatible `MSO_PATTERN_TYPE` enumeration."""

    CROSS = (51, "cross")
    DARK_DOWNWARD_DIAGONAL = (15, "dkDnDiag")
    DARK_HORIZONTAL = (13, "dkHorz")
    DARK_UPWARD_DIAGONAL = (16, "dkUpDiag")
    DARK_VERTICAL = (14, "dkVert")
    DASHED_DOWNWARD_DIAGONAL = (28, "dashDnDiag")
    DASHED_HORIZONTAL = (32, "dashHorz")
    DASHED_UPWARD_DIAGONAL = (27, "dashUpDiag")
    DASHED_VERTICAL = (31, "dashVert")
    DIAGONAL_BRICK = (40, "diagBrick")
    DIAGONAL_CROSS = (54, "diagCross")
    DIVOT = (46, "divot")
    DOTTED_DIAMOND = (24, "dotDmnd")
    DOTTED_GRID = (45, "dotGrid")
    DOWNWARD_DIAGONAL = (52, "dnDiag")
    HORIZONTAL = (49, "horz")
    HORIZONTAL_BRICK = (35, "horzBrick")
    LARGE_CHECKER_BOARD = (36, "lgCheck")
    LARGE_CONFETTI = (33, "lgConfetti")
    LARGE_GRID = (34, "lgGrid")
    LIGHT_DOWNWARD_DIAGONAL = (21, "ltDnDiag")
    LIGHT_HORIZONTAL = (19, "ltHorz")
    LIGHT_UPWARD_DIAGONAL = (22, "ltUpDiag")
    LIGHT_VERTICAL = (20, "ltVert")
    NARROW_HORIZONTAL = (30, "narHorz")
    NARROW_VERTICAL = (29, "narVert")
    OUTLINED_DIAMOND = (41, "openDmnd")
    PERCENT_10 = (2, "pct10")
    PERCENT_20 = (3, "pct20")
    PERCENT_25 = (4, "pct25")
    PERCENT_30 = (5, "pct30")
    ERCENT_40 = (6, "pct40")
    PERCENT_5 = (1, "pct5")
    PERCENT_50 = (7, "pct50")
    PERCENT_60 = (8, "pct60")
    PERCENT_70 = (9, "pct70")
    PERCENT_75 = (10, "pct75")
    PERCENT_80 = (11, "pct80")
    PERCENT_90 = (12, "pct90")
    PLAID = (42, "plaid")
    SHINGLE = (47, "shingle")
    SMALL_CHECKER_BOARD = (17, "smCheck")
    SMALL_CONFETTI = (37, "smConfetti")
    SMALL_GRID = (23, "smGrid")
    SOLID_DIAMOND = (39, "solidDmnd")
    SPHERE = (43, "sphere")
    TRELLIS = (18, "trellis")
    UPWARD_DIAGONAL = (53, "upDiag")
    VERTICAL = (50, "vert")
    WAVE = (48, "wave")
    WEAVE = (44, "weave")
    WIDE_DOWNWARD_DIAGONAL = (25, "wdDnDiag")
    WIDE_UPWARD_DIAGONAL = (26, "wdUpDiag")
    ZIG_ZAG = (38, "zigZag")
    MIXED = (-2, "")


class MSO_THEME_COLOR_INDEX(BaseXmlEnum):
    """python-pptx compatible `MSO_THEME_COLOR_INDEX` enumeration."""

    NOT_THEME_COLOR = (0, "")
    ACCENT_1 = (5, "accent1")
    ACCENT_2 = (6, "accent2")
    ACCENT_3 = (7, "accent3")
    ACCENT_4 = (8, "accent4")
    ACCENT_5 = (9, "accent5")
    ACCENT_6 = (10, "accent6")
    BACKGROUND_1 = (14, "bg1")
    BACKGROUND_2 = (16, "bg2")
    DARK_1 = (1, "dk1")
    DARK_2 = (3, "dk2")
    FOLLOWED_HYPERLINK = (12, "folHlink")
    HYPERLINK = (11, "hlink")
    LIGHT_1 = (2, "lt1")
    LIGHT_2 = (4, "lt2")
    TEXT_1 = (13, "tx1")
    TEXT_2 = (15, "tx2")
    MIXED = (-2, "")


MSO_FILL = MSO_FILL_TYPE
MSO_LINE = MSO_LINE_DASH_STYLE
MSO_PATTERN = MSO_PATTERN_TYPE
MSO_THEME_COLOR = MSO_THEME_COLOR_INDEX

__all__ = [
    "MSO_COLOR_TYPE",
    "MSO_FILL",
    "MSO_FILL_TYPE",
    "MSO_LINE",
    "MSO_LINE_DASH_STYLE",
    "MSO_PATTERN",
    "MSO_PATTERN_TYPE",
    "MSO_THEME_COLOR",
    "MSO_THEME_COLOR_INDEX",
    "BaseEnum",
    "BaseXmlEnum",
]
