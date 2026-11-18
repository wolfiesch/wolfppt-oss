"""Action-related enumerations."""

from __future__ import annotations

from .base import BaseEnum, BaseXmlEnum


class PP_ACTION_TYPE(BaseEnum):
    """python-pptx compatible `PP_ACTION_TYPE` enumeration."""

    END_SHOW = (6,)
    FIRST_SLIDE = (3,)
    HYPERLINK = (7,)
    LAST_SLIDE = (4,)
    LAST_SLIDE_VIEWED = (5,)
    NAMED_SLIDE = (101,)
    NAMED_SLIDE_SHOW = (10,)
    NEXT_SLIDE = (1,)
    NONE = (0,)
    OPEN_FILE = (102,)
    OLE_VERB = (11,)
    PLAY = (12,)
    PREVIOUS_SLIDE = (2,)
    RUN_MACRO = (8,)
    RUN_PROGRAM = (9,)


PP_ACTION = PP_ACTION_TYPE


class PP_HYPERLINK_COLOR_SOURCE(BaseXmlEnum):
    """Where hyperlink text takes its color (``hlinkClr/@val`` on ``a:hlinkClick``).

    WolfPPT-defined members; there is no python-pptx counterpart.
    """

    HYPERLINK = (1, "hlink", "Theme hyperlink color.")
    TEXT = (2, "tx", "The run's own text color.")


__all__ = [
    "PP_ACTION",
    "PP_ACTION_TYPE",
    "PP_HYPERLINK_COLOR_SOURCE",
    "BaseEnum",
]
