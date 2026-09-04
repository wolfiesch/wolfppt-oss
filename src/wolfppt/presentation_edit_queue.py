"""Composed edit-queue mixin for the PowerPoint presentation facade."""

from __future__ import annotations

from .presentation_edit_queue_adds import PresentationAddQueueMixin
from .presentation_edit_queue_chart import PresentationChartQueueMixin
from .presentation_edit_queue_core import PresentationCoreQueueMixin
from .presentation_edit_queue_shape import PresentationShapeQueueMixin
from .presentation_edit_queue_table import PresentationTableQueueMixin
from .presentation_edit_queue_text import PresentationTextQueueMixin


class PresentationEditQueueMixin(
    PresentationAddQueueMixin,
    PresentationTableQueueMixin,
    PresentationTextQueueMixin,
    PresentationShapeQueueMixin,
    PresentationChartQueueMixin,
    PresentationCoreQueueMixin,
):
    pass
