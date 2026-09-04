"""Shape adjustment, placeholder, and click-action facade helpers."""

from __future__ import annotations

import posixpath
import re
from collections.abc import Sequence
from numbers import Number
from typing import Any

from .package_parts import PackagePart
from .package_parts import XmlElementProxy
from .shape_inspection import (
    _placeholder_type_value,
    _placeholder_type_xml,
    _shape_adjustment_guides,
    _shape_click_action_value,
    _shape_hyperlink_address,
    _shape_target_slide,
)
from .shape_edit_refs import (
    ShapeEditRef,
    shape_edit_ref as _shape_edit_ref,
)

_SLIDE_PART_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")


def _shape_action_ref(shape: Any) -> ShapeEditRef:
    return _shape_edit_ref(shape)


class AdjustmentCollection(Sequence[float]):
    """python-pptx-style adjustment handle values for an auto shape."""

    def __init__(self, shape: Any) -> None:
        self._shape = shape

    def __getitem__(self, index: int) -> float:
        return _shape_adjustment_guides(self._shape)[index][1] / 100000.0

    def __setitem__(self, index: int, value: float) -> None:
        if not isinstance(value, Number):
            raise ValueError(f"adjustment value must be numeric, got {value!r}")
        guides = _shape_adjustment_guides(self._shape)
        name, current = guides[index]
        adjusted = int(value * 100000.0)
        if current == adjusted:
            return
        guides[index] = (name, adjusted)
        self._shape._payload["adjustment_guides"] = list(guides)
        self._shape._slide._presentation._queue_shape_adjustments(
            self._shape._slide._index,
            _shape_action_ref(self._shape),
            guides,
        )

    def __len__(self) -> int:
        return len(_shape_adjustment_guides(self._shape))


class PlaceholderFormat:
    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def idx(self) -> int:
        raw = self._shape._payload.get("placeholder_idx")
        if raw in (None, ""):
            return 0
        return int(raw)

    @property
    def type(self) -> Any:
        return _placeholder_type_value(_placeholder_type_xml(self._shape))

    @property
    def element(self) -> XmlElementProxy:
        element = self._shape.element.find(".//p:ph")
        if element is None:
            raise AttributeError("placeholder XML element is unavailable")
        return element


class ActionSetting:
    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def action(self) -> Any:
        return _shape_click_action_value(self._shape)

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @property
    def hyperlink(self) -> "Hyperlink":
        return Hyperlink(self._shape)

    @property
    def target_slide(self) -> Any | None:
        return _shape_target_slide(self._shape)

    @target_slide.setter
    def target_slide(self, value: Any | None) -> None:
        if value is None:
            if self.target_slide is None and self.hyperlink.address is None:
                return
            target_index = None
            target_ref = None
        else:
            from .presentation import Slide

            if not isinstance(value, Slide):
                raise TypeError("target_slide must be a wolfppt Slide or None")
            if value._presentation is not self._shape._slide._presentation:
                raise ValueError("target_slide belongs to a different presentation")
            target_index = value._index
            if self.target_slide == value:
                return
            target_partname = _resolved_slide_partname(value)
            target_ref = posixpath.relpath(
                target_partname,
                posixpath.dirname(self._shape._slide.partname),
            )
        self._shape._payload["target_slide_index"] = target_index
        self._shape._payload["hyperlink_address"] = target_ref
        self._shape._slide._presentation._queue_shape_target_slide(
            self._shape._slide._index,
            _shape_action_ref(self._shape),
            target_index,
        )


def _resolved_slide_partname(slide: Any) -> str:
    if slide.partname:
        return slide.partname
    next_slide_number = _next_pending_slide_number(slide)
    for pending_slide in slide._presentation.slides:
        if pending_slide.partname:
            continue
        if pending_slide is slide:
            return f"ppt/slides/slide{next_slide_number}.xml"
        next_slide_number += 1
    raise ValueError("target_slide is not in this presentation")


def _next_pending_slide_number(slide: Any) -> int:
    existing_numbers = []
    for candidate in slide._presentation.slides:
        match = _SLIDE_PART_RE.match(candidate.partname)
        if match is not None:
            existing_numbers.append(int(match.group(1)))
    return max(existing_numbers, default=0) + 1


class Hyperlink:
    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def address(self) -> str | None:
        return _shape_hyperlink_address(self._shape)

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @address.setter
    def address(self, value: str | None) -> None:
        address = str(value) if value else None
        if (
            address == self.address
            and _shape_target_slide(self._shape) is None
        ):
            return
        self._shape._payload["hyperlink_address"] = address
        self._shape._payload["target_slide_index"] = None
        if getattr(self._shape._slide, "_is_notes_slide", False):
            self._shape._slide._presentation._queue_part_shape_hyperlink(
                self._shape._slide.partname,
                self._shape._index,
                address,
            )
        else:
            self._shape._slide._presentation._queue_shape_hyperlink(
                self._shape._slide._index,
                _shape_action_ref(self._shape),
                address,
            )
