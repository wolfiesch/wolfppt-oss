"""Base classes for python-pptx compatible enumerations.

Members are ``int`` subclasses whose values are the Microsoft API integers used
by python-pptx, so a WolfPPT member and the matching python-pptx member compare
equal, hash equal, and are accepted interchangeably by either library.
"""

from __future__ import annotations

import enum
from typing import Self


class BaseEnum(int, enum.Enum):
    """Enumeration whose members carry only an MS API integer value."""

    def __new__(cls, ms_api_value: int, docstr: str = "") -> Self:
        self = int.__new__(cls, ms_api_value)
        self._value_ = ms_api_value
        self.__doc__ = docstr
        return self

    def __str__(self) -> str:
        """The symbolic name and value of this member, e.g. 'MIDDLE (3)'."""
        return f"{self.name} ({self.value})"


class BaseXmlEnum(int, enum.Enum):
    """Enumeration whose members also map to an Open XML attribute value."""

    xml_value: str | None

    def __new__(
        cls, ms_api_value: int, xml_value: str | None, docstr: str = ""
    ) -> Self:
        self = int.__new__(cls, ms_api_value)
        self._value_ = ms_api_value
        self.xml_value = xml_value
        self.__doc__ = docstr
        return self

    def __str__(self) -> str:
        """The symbolic name and value of this member, e.g. 'MIDDLE (3)'."""
        return f"{self.name} ({self.value})"

    @classmethod
    def from_xml(cls, xml_value: str) -> Self:
        """Member mapped to ``xml_value``; ``ValueError`` when there is none.

        The empty string never maps to a member: return-value-only members
        (``xml_value == ""``) must be selected explicitly.
        """
        member = (
            next((member for member in cls if member.xml_value == xml_value), None)
            if xml_value
            else None
        )
        if member is None:
            raise ValueError(f"{cls.__name__} has no XML mapping for {xml_value!r}")
        return member

    @classmethod
    def to_xml(cls, value: int) -> str:
        """XML attribute value of the member equal to ``value``."""
        member = cls(value)
        xml_value = member.xml_value
        if not xml_value:
            raise ValueError(f"{cls.__name__}.{member.name} has no XML representation")
        return xml_value

    @classmethod
    def validate(cls, value: int) -> None:
        """Raise ``ValueError`` if ``value`` is not an assignable member value."""
        if value not in cls:
            raise ValueError(f"{value} not a member of {cls.__name__} enumeration")


__all__ = ["BaseEnum", "BaseXmlEnum"]
