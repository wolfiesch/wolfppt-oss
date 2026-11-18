"""Align and distribute slide shapes with PowerPoint's Arrange semantics.

The rules below were measured against Microsoft PowerPoint 16.113.3 (see
``tests/test_shape_arrange.py``):

* Align moves the bounding box of each shape's rotated frame. A ``w x h`` frame rotated by
  ``theta`` about its centre covers ``w*|cos theta| + h*|sin theta|`` by
  ``w*|sin theta| + h*|cos theta|``.
* Distribute uses the frame snapped to the nearest quarter turn instead: when the rotation
  modulo 180 degrees lies in ``[45, 135)`` the frame's width and height swap about its centre,
  otherwise the unrotated frame counts. Shapes are ordered by their centres. Relative to the
  selection, the first and last shapes stay put and the ``n - 1`` gaps between neighbours become
  equal; relative to the slide, the ``n + 1`` gaps including both slide edges become equal.
* Flips never change either box. A group is arranged as one object through its own frame;
  only the group's ``a:off`` moves, so its children keep their XML.

Only ``a:off`` of shapes whose position actually changes is rewritten, so every other shape
keeps its XML byte for byte.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from .shape_core_facade import Shape

ALIGN_MODES = ("left", "center", "right", "top", "middle", "bottom")
DISTRIBUTE_MODES = ("horizontal", "vertical")
RELATIVE_TO = ("selection", "slide")


class ArrangementError(ValueError):
    """An unsupported arrangement request was refused before moving any shape."""


class _Box(NamedTuple):
    """Axis-aligned box in EMU, kept as floats until the final rounding."""

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


def _rotated_box(shape: Shape) -> _Box:
    """Bounding box of the rotated frame (Align)."""
    x, y, cx, cy = shape.left, shape.top, shape.width, shape.height
    radians = math.radians(shape.rotation % 360.0)
    cos, sin = abs(math.cos(radians)), abs(math.sin(radians))
    width = cx * cos + cy * sin
    height = cx * sin + cy * cos
    return _Box(x + (cx - width) / 2, y + (cy - height) / 2, width, height)


def _quarter_turn_box(shape: Shape) -> _Box:
    """Frame snapped to the nearest quarter turn (Distribute)."""
    x, y, cx, cy = shape.left, shape.top, shape.width, shape.height
    if 45.0 <= shape.rotation % 180.0 < 135.0:
        return _Box(x + (cx - cy) / 2, y + (cy - cx) / 2, float(cy), float(cx))
    return _Box(float(x), float(y), float(cx), float(cy))


def _checked_shapes(shapes: Sequence[Shape], relative_to: str) -> list[Shape]:
    if relative_to not in RELATIVE_TO:
        raise ArrangementError(
            f"relative_to must be one of {', '.join(RELATIVE_TO)}, got {relative_to!r}"
        )
    selected = list(shapes)
    if not selected:
        raise ArrangementError("shapes must name at least one shape")
    slide = selected[0]._slide
    seen: set[int] = set()
    for shape in selected:
        if shape._slide is not slide:
            raise ArrangementError("shapes must all belong to the same slide")
        if shape._payload.get("_deleted"):
            raise ArrangementError(f"shape {shape.name!r} was deleted")
        if shape._payload.get("_group_child"):
            raise ArrangementError(
                f"shape {shape.name!r} is inside a group; arrange the group or ungroup it first"
            )
        if id(shape) in seen:
            raise ArrangementError(f"shape {shape.name!r} is listed twice")
        seen.add(id(shape))
    return selected


def _slide_size(shape: Shape) -> tuple[int, int]:
    presentation = shape._slide._presentation
    return int(presentation.slide_width), int(presentation.slide_height)


def _move(shape: Shape, dx: float, dy: float) -> None:
    left = round(shape.left + dx)
    top = round(shape.top + dy)
    if left != shape.left:
        shape.left = left
    if top != shape.top:
        shape.top = top


def align(shapes: Sequence[Shape], mode: str, *, relative_to: str = "selection") -> None:
    """Align ``shapes`` like PowerPoint's Arrange > Align command.

    ``mode`` is ``left``, ``center``, ``right``, ``top``, ``middle``, or ``bottom``.
    ``relative_to="selection"`` aligns to the union of the shapes' rotated bounding boxes;
    ``relative_to="slide"`` aligns to the slide edges or centre.
    """
    if mode not in ALIGN_MODES:
        raise ArrangementError(f"mode must be one of {', '.join(ALIGN_MODES)}, got {mode!r}")
    selected = _checked_shapes(shapes, relative_to)
    boxes = [_rotated_box(shape) for shape in selected]
    if relative_to == "slide":
        width, height = _slide_size(selected[0])
        bounds = _Box(0.0, 0.0, float(width), float(height))
    else:
        left = min(box.left for box in boxes)
        top = min(box.top for box in boxes)
        bounds = _Box(
            left,
            top,
            max(box.right for box in boxes) - left,
            max(box.bottom for box in boxes) - top,
        )
    for shape, box in zip(selected, boxes, strict=True):
        if mode == "left":
            _move(shape, bounds.left - box.left, 0.0)
        elif mode == "center":
            _move(shape, (bounds.left + bounds.right - box.left - box.right) / 2, 0.0)
        elif mode == "right":
            _move(shape, bounds.right - box.right, 0.0)
        elif mode == "top":
            _move(shape, 0.0, bounds.top - box.top)
        elif mode == "middle":
            _move(shape, 0.0, (bounds.top + bounds.bottom - box.top - box.bottom) / 2)
        else:
            _move(shape, 0.0, bounds.bottom - box.bottom)


def distribute(shapes: Sequence[Shape], mode: str, *, relative_to: str = "selection") -> None:
    """Space ``shapes`` evenly like PowerPoint's Arrange > Distribute command.

    ``mode`` is ``horizontal`` or ``vertical``. Relative to the selection the outermost shapes
    (by centre) stay put and the gaps between neighbours become equal; fewer than three shapes
    leave nothing to distribute. Relative to the slide the gaps between the slide edges and
    the shapes become equal too.
    """
    if mode not in DISTRIBUTE_MODES:
        raise ArrangementError(f"mode must be one of {', '.join(DISTRIBUTE_MODES)}, got {mode!r}")
    selected = _checked_shapes(shapes, relative_to)
    horizontal = mode == "horizontal"
    boxes = [_quarter_turn_box(shape) for shape in selected]
    starts = [box.left if horizontal else box.top for box in boxes]
    sizes = [box.width if horizontal else box.height for box in boxes]
    order = sorted(range(len(selected)), key=lambda index: starts[index] + sizes[index] / 2)
    if relative_to == "slide":
        width, height = _slide_size(selected[0])
        extent = float(width if horizontal else height)
        gap = (extent - sum(sizes)) / (len(selected) + 1)
        position = gap
    else:
        if len(selected) < 3:
            return
        first, last = order[0], order[-1]
        span = starts[last] + sizes[last] - starts[first]
        gap = (span - sum(sizes)) / (len(selected) - 1)
        position = starts[first]
    for index in order:
        offset = position - starts[index]
        _move(
            selected[index],
            offset if horizontal else 0.0,
            0.0 if horizontal else offset,
        )
        position += sizes[index] + gap
