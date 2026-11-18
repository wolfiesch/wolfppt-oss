"""Chart-related enumerations."""

from __future__ import annotations

from .base import BaseEnum, BaseXmlEnum


class XL_AXIS_CROSSES(BaseXmlEnum):
    """python-pptx compatible `XL_AXIS_CROSSES` enumeration."""

    AUTOMATIC = (-4105, "autoZero")
    CUSTOM = (-4114, "")
    MAXIMUM = (2, "max")
    MINIMUM = (4, "min")


class XL_CATEGORY_TYPE(BaseEnum):
    """python-pptx compatible `XL_CATEGORY_TYPE` enumeration."""

    AUTOMATIC_SCALE = (-4105,)
    CATEGORY_SCALE = (2,)
    TIME_SCALE = (3,)


class XL_CHART_TYPE(BaseEnum):
    """python-pptx compatible `XL_CHART_TYPE` enumeration."""

    THREE_D_AREA = (-4098,)
    THREE_D_AREA_STACKED = (78,)
    THREE_D_AREA_STACKED_100 = (79,)
    THREE_D_BAR_CLUSTERED = (60,)
    THREE_D_BAR_STACKED = (61,)
    THREE_D_BAR_STACKED_100 = (62,)
    THREE_D_COLUMN = (-4100,)
    THREE_D_COLUMN_CLUSTERED = (54,)
    THREE_D_COLUMN_STACKED = (55,)
    THREE_D_COLUMN_STACKED_100 = (56,)
    THREE_D_LINE = (-4101,)
    THREE_D_PIE = (-4102,)
    THREE_D_PIE_EXPLODED = (70,)
    AREA = (1,)
    AREA_STACKED = (76,)
    AREA_STACKED_100 = (77,)
    BAR_CLUSTERED = (57,)
    BAR_OF_PIE = (71,)
    BAR_STACKED = (58,)
    BAR_STACKED_100 = (59,)
    BUBBLE = (15,)
    BUBBLE_THREE_D_EFFECT = (87,)
    COLUMN_CLUSTERED = (51,)
    COLUMN_STACKED = (52,)
    COLUMN_STACKED_100 = (53,)
    CONE_BAR_CLUSTERED = (102,)
    CONE_BAR_STACKED = (103,)
    CONE_BAR_STACKED_100 = (104,)
    CONE_COL = (105,)
    CONE_COL_CLUSTERED = (99,)
    CONE_COL_STACKED = (100,)
    CONE_COL_STACKED_100 = (101,)
    CYLINDER_BAR_CLUSTERED = (95,)
    CYLINDER_BAR_STACKED = (96,)
    CYLINDER_BAR_STACKED_100 = (97,)
    CYLINDER_COL = (98,)
    CYLINDER_COL_CLUSTERED = (92,)
    CYLINDER_COL_STACKED = (93,)
    CYLINDER_COL_STACKED_100 = (94,)
    DOUGHNUT = (-4120,)
    DOUGHNUT_EXPLODED = (80,)
    LINE = (4,)
    LINE_MARKERS = (65,)
    LINE_MARKERS_STACKED = (66,)
    LINE_MARKERS_STACKED_100 = (67,)
    LINE_STACKED = (63,)
    LINE_STACKED_100 = (64,)
    PIE = (5,)
    PIE_EXPLODED = (69,)
    PIE_OF_PIE = (68,)
    PYRAMID_BAR_CLUSTERED = (109,)
    PYRAMID_BAR_STACKED = (110,)
    PYRAMID_BAR_STACKED_100 = (111,)
    PYRAMID_COL = (112,)
    PYRAMID_COL_CLUSTERED = (106,)
    PYRAMID_COL_STACKED = (107,)
    PYRAMID_COL_STACKED_100 = (108,)
    RADAR = (-4151,)
    RADAR_FILLED = (82,)
    RADAR_MARKERS = (81,)
    STOCK_HLC = (88,)
    STOCK_OHLC = (89,)
    STOCK_VHLC = (90,)
    STOCK_VOHLC = (91,)
    SURFACE = (83,)
    SURFACE_TOP_VIEW = (85,)
    SURFACE_TOP_VIEW_WIREFRAME = (86,)
    SURFACE_WIREFRAME = (84,)
    XY_SCATTER = (-4169,)
    XY_SCATTER_LINES = (74,)
    XY_SCATTER_LINES_NO_MARKERS = (75,)
    XY_SCATTER_SMOOTH = (72,)
    XY_SCATTER_SMOOTH_NO_MARKERS = (73,)


class XL_DATA_LABEL_POSITION(BaseXmlEnum):
    """python-pptx compatible `XL_DATA_LABEL_POSITION` enumeration."""

    ABOVE = (0, "t")
    BELOW = (1, "b")
    BEST_FIT = (5, "bestFit")
    CENTER = (-4108, "ctr")
    INSIDE_BASE = (4, "inBase")
    INSIDE_END = (3, "inEnd")
    LEFT = (-4131, "l")
    MIXED = (6, "")
    OUTSIDE_END = (2, "outEnd")
    RIGHT = (-4152, "r")


class XL_LEGEND_POSITION(BaseXmlEnum):
    """python-pptx compatible `XL_LEGEND_POSITION` enumeration."""

    BOTTOM = (-4107, "b")
    CORNER = (2, "tr")
    CUSTOM = (-4161, "")
    LEFT = (-4131, "l")
    RIGHT = (-4152, "r")
    TOP = (-4160, "t")


class XL_MARKER_STYLE(BaseXmlEnum):
    """python-pptx compatible `XL_MARKER_STYLE` enumeration."""

    AUTOMATIC = (-4105, "auto")
    CIRCLE = (8, "circle")
    DASH = (-4115, "dash")
    DIAMOND = (2, "diamond")
    DOT = (-4118, "dot")
    NONE = (-4142, "none")
    PICTURE = (-4147, "picture")
    PLUS = (9, "plus")
    SQUARE = (1, "square")
    STAR = (5, "star")
    TRIANGLE = (3, "triangle")
    X = (-4168, "x")


class XL_TICK_MARK(BaseXmlEnum):
    """python-pptx compatible `XL_TICK_MARK` enumeration."""

    CROSS = (4, "cross")
    INSIDE = (2, "in")
    NONE = (-4142, "none")
    OUTSIDE = (3, "out")


class XL_TICK_LABEL_POSITION(BaseXmlEnum):
    """python-pptx compatible `XL_TICK_LABEL_POSITION` enumeration."""

    HIGH = (-4127, "high")
    LOW = (-4134, "low")
    NEXT_TO_AXIS = (4, "nextTo")
    NONE = (-4142, "none")


XL_LABEL_POSITION = XL_DATA_LABEL_POSITION

__all__ = [
    "XL_AXIS_CROSSES",
    "XL_CATEGORY_TYPE",
    "XL_CHART_TYPE",
    "XL_DATA_LABEL_POSITION",
    "XL_LABEL_POSITION",
    "XL_LEGEND_POSITION",
    "XL_MARKER_STYLE",
    "XL_TICK_LABEL_POSITION",
    "XL_TICK_MARK",
    "BaseEnum",
    "BaseXmlEnum",
]
