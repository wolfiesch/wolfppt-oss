"""Indexed slide insertion for :class:`~wolfppt.presentation_slides.SlideCollection`."""

from __future__ import annotations

from operator import index as _index
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .presentation import Presentation
    from .presentation_slides import Slide, SlideLayout


def _require_open_presentation(presentation: Presentation) -> None:
    if presentation._disposed:
        raise RuntimeError("presentation is disposed")


def _normalize_insert_index(value: int, length: int) -> int:
    try:
        normalized = _index(value)
    except TypeError as exc:
        raise TypeError("index must be an integer") from exc
    if normalized < 0:
        normalized += length
    if normalized < 0 or normalized > length:
        raise IndexError("index out of range")
    return normalized


class SlideInsertMixin:
    """Adds :meth:`insert` on top of the collection's append and move primitives."""

    if TYPE_CHECKING:
        _presentation: Presentation
        _slides: list[Slide]

        def _require_attached(self, allowed: Slide | None = None) -> None: ...

        def _move_slide(self, old_index: int, new_index: int) -> None: ...

        def add_slide(self, slide_layout: SlideLayout) -> Slide: ...

    def insert(self, index: int, slide_layout: SlideLayout) -> Slide:
        """Create a slide from ``slide_layout`` and place it at ``index``.

        ``index`` follows ``list.insert`` bounds without clamping: ``0`` through
        ``len(slides)`` (the end), with negative values counted from the end.
        A bad index raises ``IndexError`` or ``TypeError``, and a bad layout raises
        ``TypeError`` or ``ValueError`` as in :meth:`add_slide`, before any edit is
        queued, so a refused insert leaves the saved package unchanged.
        """
        with self._presentation._mutation_lock:
            self._require_attached()
            position = _normalize_insert_index(index, len(self._slides))
            slide = self.add_slide(slide_layout)
            self._move_slide(len(self._slides) - 1, position)
            return slide
