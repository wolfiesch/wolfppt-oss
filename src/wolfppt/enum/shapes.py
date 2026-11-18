"""Shape-related enumerations."""

from __future__ import annotations

import enum

from .base import BaseEnum, BaseXmlEnum


class MSO_AUTO_SHAPE_TYPE(BaseXmlEnum):
    """python-pptx compatible `MSO_AUTO_SHAPE_TYPE` enumeration."""

    ACTION_BUTTON_BACK_OR_PREVIOUS = (129, "actionButtonBackPrevious")
    ACTION_BUTTON_BEGINNING = (131, "actionButtonBeginning")
    ACTION_BUTTON_CUSTOM = (125, "actionButtonBlank")
    ACTION_BUTTON_DOCUMENT = (134, "actionButtonDocument")
    ACTION_BUTTON_END = (132, "actionButtonEnd")
    ACTION_BUTTON_FORWARD_OR_NEXT = (130, "actionButtonForwardNext")
    ACTION_BUTTON_HELP = (127, "actionButtonHelp")
    ACTION_BUTTON_HOME = (126, "actionButtonHome")
    ACTION_BUTTON_INFORMATION = (128, "actionButtonInformation")
    ACTION_BUTTON_MOVIE = (136, "actionButtonMovie")
    ACTION_BUTTON_RETURN = (133, "actionButtonReturn")
    ACTION_BUTTON_SOUND = (135, "actionButtonSound")
    ARC = (25, "arc")
    BALLOON = (137, "wedgeRoundRectCallout")
    BENT_ARROW = (41, "bentArrow")
    BENT_UP_ARROW = (44, "bentUpArrow")
    BEVEL = (15, "bevel")
    BLOCK_ARC = (20, "blockArc")
    CAN = (13, "can")
    CHART_PLUS = (182, "chartPlus")
    CHART_STAR = (181, "chartStar")
    CHART_X = (180, "chartX")
    CHEVRON = (52, "chevron")
    CHORD = (161, "chord")
    CIRCULAR_ARROW = (60, "circularArrow")
    CLOUD = (179, "cloud")
    CLOUD_CALLOUT = (108, "cloudCallout")
    CORNER = (162, "corner")
    CORNER_TABS = (169, "cornerTabs")
    CROSS = (11, "plus")
    CUBE = (14, "cube")
    CURVED_DOWN_ARROW = (48, "curvedDownArrow")
    CURVED_DOWN_RIBBON = (100, "ellipseRibbon")
    CURVED_LEFT_ARROW = (46, "curvedLeftArrow")
    CURVED_RIGHT_ARROW = (45, "curvedRightArrow")
    CURVED_UP_ARROW = (47, "curvedUpArrow")
    CURVED_UP_RIBBON = (99, "ellipseRibbon2")
    DECAGON = (144, "decagon")
    DIAGONAL_STRIPE = (141, "diagStripe")
    DIAMOND = (4, "diamond")
    DODECAGON = (146, "dodecagon")
    DONUT = (18, "donut")
    DOUBLE_BRACE = (27, "bracePair")
    DOUBLE_BRACKET = (26, "bracketPair")
    DOUBLE_WAVE = (104, "doubleWave")
    DOWN_ARROW = (36, "downArrow")
    DOWN_ARROW_CALLOUT = (56, "downArrowCallout")
    DOWN_RIBBON = (98, "ribbon")
    EXPLOSION1 = (89, "irregularSeal1")
    EXPLOSION2 = (90, "irregularSeal2")
    FLOWCHART_ALTERNATE_PROCESS = (62, "flowChartAlternateProcess")
    FLOWCHART_CARD = (75, "flowChartPunchedCard")
    FLOWCHART_COLLATE = (79, "flowChartCollate")
    FLOWCHART_CONNECTOR = (73, "flowChartConnector")
    FLOWCHART_DATA = (64, "flowChartInputOutput")
    FLOWCHART_DECISION = (63, "flowChartDecision")
    FLOWCHART_DELAY = (84, "flowChartDelay")
    FLOWCHART_DIRECT_ACCESS_STORAGE = (87, "flowChartMagneticDrum")
    FLOWCHART_DISPLAY = (88, "flowChartDisplay")
    FLOWCHART_DOCUMENT = (67, "flowChartDocument")
    FLOWCHART_EXTRACT = (81, "flowChartExtract")
    FLOWCHART_INTERNAL_STORAGE = (66, "flowChartInternalStorage")
    FLOWCHART_MAGNETIC_DISK = (86, "flowChartMagneticDisk")
    FLOWCHART_MANUAL_INPUT = (71, "flowChartManualInput")
    FLOWCHART_MANUAL_OPERATION = (72, "flowChartManualOperation")
    FLOWCHART_MERGE = (82, "flowChartMerge")
    FLOWCHART_MULTIDOCUMENT = (68, "flowChartMultidocument")
    FLOWCHART_OFFLINE_STORAGE = (139, "flowChartOfflineStorage")
    FLOWCHART_OFFPAGE_CONNECTOR = (74, "flowChartOffpageConnector")
    FLOWCHART_OR = (78, "flowChartOr")
    FLOWCHART_PREDEFINED_PROCESS = (65, "flowChartPredefinedProcess")
    FLOWCHART_PREPARATION = (70, "flowChartPreparation")
    FLOWCHART_PROCESS = (61, "flowChartProcess")
    FLOWCHART_PUNCHED_TAPE = (76, "flowChartPunchedTape")
    FLOWCHART_SEQUENTIAL_ACCESS_STORAGE = (85, "flowChartMagneticTape")
    FLOWCHART_SORT = (80, "flowChartSort")
    FLOWCHART_STORED_DATA = (83, "flowChartOnlineStorage")
    FLOWCHART_SUMMING_JUNCTION = (77, "flowChartSummingJunction")
    FLOWCHART_TERMINATOR = (69, "flowChartTerminator")
    FOLDED_CORNER = (16, "foldedCorner")
    FRAME = (158, "frame")
    FUNNEL = (174, "funnel")
    GEAR_6 = (172, "gear6")
    GEAR_9 = (173, "gear9")
    HALF_FRAME = (159, "halfFrame")
    HEART = (21, "heart")
    HEPTAGON = (145, "heptagon")
    HEXAGON = (10, "hexagon")
    HORIZONTAL_SCROLL = (102, "horizontalScroll")
    ISOSCELES_TRIANGLE = (7, "triangle")
    LEFT_ARROW = (34, "leftArrow")
    LEFT_ARROW_CALLOUT = (54, "leftArrowCallout")
    LEFT_BRACE = (31, "leftBrace")
    LEFT_BRACKET = (29, "leftBracket")
    LEFT_CIRCULAR_ARROW = (176, "leftCircularArrow")
    LEFT_RIGHT_ARROW = (37, "leftRightArrow")
    LEFT_RIGHT_ARROW_CALLOUT = (57, "leftRightArrowCallout")
    LEFT_RIGHT_CIRCULAR_ARROW = (177, "leftRightCircularArrow")
    LEFT_RIGHT_RIBBON = (140, "leftRightRibbon")
    LEFT_RIGHT_UP_ARROW = (40, "leftRightUpArrow")
    LEFT_UP_ARROW = (43, "leftUpArrow")
    LIGHTNING_BOLT = (22, "lightningBolt")
    LINE_CALLOUT_1 = (109, "borderCallout1")
    LINE_CALLOUT_1_ACCENT_BAR = (113, "accentCallout1")
    LINE_CALLOUT_1_BORDER_AND_ACCENT_BAR = (121, "accentBorderCallout1")
    LINE_CALLOUT_1_NO_BORDER = (117, "callout1")
    LINE_CALLOUT_2 = (110, "borderCallout2")
    LINE_CALLOUT_2_ACCENT_BAR = (114, "accentCallout2")
    LINE_CALLOUT_2_BORDER_AND_ACCENT_BAR = (122, "accentBorderCallout2")
    LINE_CALLOUT_2_NO_BORDER = (118, "callout2")
    LINE_CALLOUT_3 = (111, "borderCallout3")
    LINE_CALLOUT_3_ACCENT_BAR = (115, "accentCallout3")
    LINE_CALLOUT_3_BORDER_AND_ACCENT_BAR = (123, "accentBorderCallout3")
    LINE_CALLOUT_3_NO_BORDER = (119, "callout3")
    LINE_CALLOUT_4 = (112, "borderCallout3")
    LINE_CALLOUT_4_ACCENT_BAR = (116, "accentCallout3")
    LINE_CALLOUT_4_BORDER_AND_ACCENT_BAR = (124, "accentBorderCallout3")
    LINE_CALLOUT_4_NO_BORDER = (120, "callout3")
    LINE_INVERSE = (183, "lineInv")
    MATH_DIVIDE = (166, "mathDivide")
    MATH_EQUAL = (167, "mathEqual")
    MATH_MINUS = (164, "mathMinus")
    MATH_MULTIPLY = (165, "mathMultiply")
    MATH_NOT_EQUAL = (168, "mathNotEqual")
    MATH_PLUS = (163, "mathPlus")
    MOON = (24, "moon")
    NON_ISOSCELES_TRAPEZOID = (143, "nonIsoscelesTrapezoid")
    NOTCHED_RIGHT_ARROW = (50, "notchedRightArrow")
    NO_SYMBOL = (19, "noSmoking")
    OCTAGON = (6, "octagon")
    OVAL = (9, "ellipse")
    OVAL_CALLOUT = (107, "wedgeEllipseCallout")
    PARALLELOGRAM = (2, "parallelogram")
    PENTAGON = (51, "homePlate")
    PIE = (142, "pie")
    PIE_WEDGE = (175, "pieWedge")
    PLAQUE = (28, "plaque")
    PLAQUE_TABS = (171, "plaqueTabs")
    QUAD_ARROW = (39, "quadArrow")
    QUAD_ARROW_CALLOUT = (59, "quadArrowCallout")
    RECTANGLE = (1, "rect")
    RECTANGULAR_CALLOUT = (105, "wedgeRectCallout")
    REGULAR_PENTAGON = (12, "pentagon")
    RIGHT_ARROW = (33, "rightArrow")
    RIGHT_ARROW_CALLOUT = (53, "rightArrowCallout")
    RIGHT_BRACE = (32, "rightBrace")
    RIGHT_BRACKET = (30, "rightBracket")
    RIGHT_TRIANGLE = (8, "rtTriangle")
    ROUNDED_RECTANGLE = (5, "roundRect")
    ROUNDED_RECTANGULAR_CALLOUT = (106, "wedgeRoundRectCallout")
    ROUND_1_RECTANGLE = (151, "round1Rect")
    ROUND_2_DIAG_RECTANGLE = (153, "round2DiagRect")
    ROUND_2_SAME_RECTANGLE = (152, "round2SameRect")
    SMILEY_FACE = (17, "smileyFace")
    SNIP_1_RECTANGLE = (155, "snip1Rect")
    SNIP_2_DIAG_RECTANGLE = (157, "snip2DiagRect")
    SNIP_2_SAME_RECTANGLE = (156, "snip2SameRect")
    SNIP_ROUND_RECTANGLE = (154, "snipRoundRect")
    SQUARE_TABS = (170, "squareTabs")
    STAR_10_POINT = (149, "star10")
    STAR_12_POINT = (150, "star12")
    STAR_16_POINT = (94, "star16")
    STAR_24_POINT = (95, "star24")
    STAR_32_POINT = (96, "star32")
    STAR_4_POINT = (91, "star4")
    STAR_5_POINT = (92, "star5")
    STAR_6_POINT = (147, "star6")
    STAR_7_POINT = (148, "star7")
    STAR_8_POINT = (93, "star8")
    STRIPED_RIGHT_ARROW = (49, "stripedRightArrow")
    SUN = (23, "sun")
    SWOOSH_ARROW = (178, "swooshArrow")
    TEAR = (160, "teardrop")
    TRAPEZOID = (3, "trapezoid")
    UP_ARROW = (35, "upArrow")
    UP_ARROW_CALLOUT = (55, "upArrowCallout")
    UP_DOWN_ARROW = (38, "upDownArrow")
    UP_DOWN_ARROW_CALLOUT = (58, "upDownArrowCallout")
    UP_RIBBON = (97, "ribbon2")
    U_TURN_ARROW = (42, "uturnArrow")
    VERTICAL_SCROLL = (101, "verticalScroll")
    WAVE = (103, "wave")


class MSO_CONNECTOR_TYPE(BaseXmlEnum):
    """python-pptx compatible `MSO_CONNECTOR_TYPE` enumeration."""

    CURVE = (3, "curvedConnector3")
    ELBOW = (2, "bentConnector3")
    STRAIGHT = (1, "line")
    MIXED = (-2, "")


class MSO_SHAPE_TYPE(BaseEnum):
    """python-pptx compatible `MSO_SHAPE_TYPE` enumeration."""

    AUTO_SHAPE = (1,)
    CALLOUT = (2,)
    CANVAS = (20,)
    CHART = (3,)
    COMMENT = (4,)
    DIAGRAM = (21,)
    EMBEDDED_OLE_OBJECT = (7,)
    FORM_CONTROL = (8,)
    FREEFORM = (5,)
    GROUP = (6,)
    IGX_GRAPHIC = (24,)
    INK = (22,)
    INK_COMMENT = (23,)
    LINE = (9,)
    LINKED_OLE_OBJECT = (10,)
    LINKED_PICTURE = (11,)
    MEDIA = (16,)
    OLE_CONTROL_OBJECT = (12,)
    PICTURE = (13,)
    PLACEHOLDER = (14,)
    SCRIPT_ANCHOR = (18,)
    TABLE = (19,)
    TEXT_BOX = (17,)
    TEXT_EFFECT = (15,)
    WEB_VIDEO = (26,)
    MIXED = (-2,)


class PP_MEDIA_TYPE(BaseEnum):
    """python-pptx compatible `PP_MEDIA_TYPE` enumeration."""

    MOVIE = (3,)
    OTHER = (1,)
    SOUND = (1,)
    MIXED = (-2,)


class PP_PLACEHOLDER_TYPE(BaseXmlEnum):
    """python-pptx compatible `PP_PLACEHOLDER_TYPE` enumeration."""

    BITMAP = (9, "clipArt")
    BODY = (2, "body")
    CENTER_TITLE = (3, "ctrTitle")
    CHART = (8, "chart")
    DATE = (16, "dt")
    FOOTER = (15, "ftr")
    HEADER = (14, "hdr")
    MEDIA_CLIP = (10, "media")
    OBJECT = (7, "obj")
    ORG_CHART = (11, "dgm")
    PICTURE = (18, "pic")
    SLIDE_IMAGE = (101, "sldImg")
    SLIDE_NUMBER = (13, "sldNum")
    SUBTITLE = (4, "subTitle")
    TABLE = (12, "tbl")
    TITLE = (1, "title")
    VERTICAL_BODY = (6, "")
    VERTICAL_OBJECT = (17, "")
    VERTICAL_TITLE = (5, "")
    MIXED = (-2, "")


class PP_MEDIA_START_MODE(enum.StrEnum):
    """Named saved-package start modes for audio and video."""

    ON_CLICK = "on_click"
    AUTOMATICALLY = "automatically"
    IN_CLICK_SEQUENCE = "in_click_sequence"


class PP_MEDIA_VOLUME(enum.IntEnum):
    """Volume presets in percent; MUTE is zero volume, independent of mute."""

    MUTE = 0
    LOW = 25
    MEDIUM = 50
    HIGH = 100


class PlaceholderSize(enum.StrEnum):
    """PresentationML placeholder size classes, independent of shape geometry."""

    FULL = "full"
    HALF = "half"
    QUARTER = "quarter"


class PROG_ID(enum.Enum):
    """OLE object program identifiers usable with `add_ole_object()`."""

    _progId: str
    _icon_filename: str
    _width: int
    _height: int

    def __new__(cls, value: str, progId: str, icon_filename: str, width: int, height: int):
        self = object.__new__(cls)
        self._value_ = value
        self._progId = progId
        self._icon_filename = icon_filename
        self._width = width
        self._height = height
        return self

    @property
    def height(self) -> int:
        return self._height

    @property
    def icon_filename(self) -> str:
        return self._icon_filename

    @property
    def progId(self) -> str:
        return self._progId

    @property
    def width(self) -> int:
        return self._width

    DOCX = ("DOCX", "Word.Document.12", "docx-icon.emf", 965200, 609600)
    PPTX = ("PPTX", "PowerPoint.Show.12", "pptx-icon.emf", 965200, 609600)
    XLSX = ("XLSX", "Excel.Sheet.12", "xlsx-icon.emf", 965200, 609600)


MSO_SHAPE = MSO_AUTO_SHAPE_TYPE
MSO_CONNECTOR = MSO_CONNECTOR_TYPE
MSO = MSO_SHAPE_TYPE
PP_PLACEHOLDER = PP_PLACEHOLDER_TYPE

__all__ = [
    "MSO",
    "MSO_AUTO_SHAPE_TYPE",
    "MSO_CONNECTOR",
    "MSO_CONNECTOR_TYPE",
    "MSO_SHAPE",
    "MSO_SHAPE_TYPE",
    "PP_MEDIA_TYPE",
    "PP_MEDIA_START_MODE",
    "PP_MEDIA_VOLUME",
    "PP_PLACEHOLDER",
    "PP_PLACEHOLDER_TYPE",
    "PlaceholderSize",
    "PROG_ID",
    "BaseEnum",
    "BaseXmlEnum",
]
