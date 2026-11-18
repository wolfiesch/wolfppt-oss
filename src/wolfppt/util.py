"""Length units compatible with ``pptx.util``.

Every length is an ``int`` count of English Metric Units (EMU), so values are
interchangeable with python-pptx lengths and plain integers. ``Length`` also
recognises python-pptx ``Length`` instances in ``isinstance`` checks, without
importing python-pptx.
"""

from __future__ import annotations

import functools
from abc import ABCMeta
from collections.abc import Callable
from typing import Any, Generic, Self, TypeVar, cast


class Length(int, metaclass=ABCMeta):
    """Base class for length classes Inches, Emu, Cm, Mm, Pt, and Centipoints."""

    _EMUS_PER_INCH = 914400
    _EMUS_PER_CENTIPOINT = 127
    _EMUS_PER_CM = 360000
    _EMUS_PER_MM = 36000
    _EMUS_PER_PT = 12700

    def __new__(cls, emu: int) -> Self:
        return int.__new__(cls, emu)

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        # python-pptx lengths are the same EMU integers; accept them as Length.
        if cls is Length and any(
            base.__name__ == "Length" and base.__module__ == "pptx.util"
            for base in subclass.__mro__
        ):
            return True
        return NotImplemented

    @property
    def inches(self) -> float:
        """Floating point length in inches."""
        return self / float(self._EMUS_PER_INCH)

    @property
    def centipoints(self) -> int:
        """Integer length in hundredths of a point (1/7200 inch)."""
        return self // self._EMUS_PER_CENTIPOINT

    @property
    def cm(self) -> float:
        """Floating point length in centimeters."""
        return self / float(self._EMUS_PER_CM)

    @property
    def emu(self) -> int:
        """Integer length in English Metric Units."""
        return self

    @property
    def mm(self) -> float:
        """Floating point length in millimeters."""
        return self / float(self._EMUS_PER_MM)

    @property
    def pt(self) -> float:
        """Floating point length in points."""
        return self / float(self._EMUS_PER_PT)


class Inches(Length):
    """Convenience constructor for length in inches."""

    def __new__(cls, inches: float) -> Self:
        return Length.__new__(cls, int(inches * Length._EMUS_PER_INCH))


class Centipoints(Length):
    """Convenience constructor for length in hundredths of a point."""

    def __new__(cls, centipoints: int) -> Self:
        return Length.__new__(cls, int(centipoints * Length._EMUS_PER_CENTIPOINT))


class Cm(Length):
    """Convenience constructor for length in centimeters."""

    def __new__(cls, cm: float) -> Self:
        return Length.__new__(cls, int(cm * Length._EMUS_PER_CM))


class Emu(Length):
    """Convenience constructor for length in English Metric Units."""

    def __new__(cls, emu: int) -> Self:
        return Length.__new__(cls, int(emu))


class Mm(Length):
    """Convenience constructor for length in millimeters."""

    def __new__(cls, mm: float) -> Self:
        return Length.__new__(cls, int(mm * Length._EMUS_PER_MM))


class Pt(Length):
    """Convenience constructor for length in points."""

    def __new__(cls, points: float) -> Self:
        return Length.__new__(cls, int(points * Length._EMUS_PER_PT))


_T = TypeVar("_T")


class lazyproperty(Generic[_T]):
    """Read-only ``@property`` evaluated on first access and cached on the instance."""

    def __init__(self, fget: Callable[..., _T]) -> None:
        self._fget = fget
        self._name = fget.__name__
        functools.update_wrapper(self, fget)  # type: ignore[arg-type]

    def __get__(self, obj: Any, type: Any = None) -> _T:
        if obj is None:
            return self  # type: ignore[return-value]
        value = obj.__dict__.get(self._name)
        if value is None:
            value = obj.__dict__[self._name] = self._fget(obj)
        return cast(_T, value)

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError("can't set attribute")


__all__ = ["Centipoints", "Cm", "Emu", "Inches", "Length", "Mm", "Pt", "lazyproperty"]
