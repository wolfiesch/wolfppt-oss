"""Queued group-shape creation operations for the presentation facade."""

from __future__ import annotations

from .presentation_edit_queue_group_connectors import (
    PresentationGroupConnectorQueueMixin,
)


class PresentationGroupShapeAddQueueMixin(PresentationGroupConnectorQueueMixin):
    def _queue_group_shape_add(self, slide_index: int) -> None:
        self._shape_adds.append(("group_shape", (slide_index,)))

    def _queue_existing_shape_group_add(
        self,
        slide_index: int,
        shape_indices: tuple[int, ...],
    ) -> None:
        self._shape_adds.append(("group_existing_shapes", (slide_index, shape_indices)))

    def _queue_existing_group_child_group_add(
        self,
        slide_index: int,
        group_index: int,
        child_indices: tuple[int, ...],
    ) -> None:
        self._shape_adds.append(
            ("group_existing_child_shapes", (slide_index, group_index, child_indices))
        )

    def _queue_existing_nested_group_child_group_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_indices: tuple[int, ...],
    ) -> None:
        self._shape_adds.append(
            (
                "group_existing_nested_child_shapes",
                (slide_index, group_index, nested_group_child_index, child_indices),
            )
        )

    def _queue_existing_deeper_nested_group_child_group_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_indices: tuple[int, ...],
    ) -> None:
        self._shape_adds.append(
            (
                "group_existing_deeper_nested_child_shapes",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_indices,
                ),
            )
        )

    def _queue_nested_group_shape_add(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
    ) -> None:
        self._shape_adds.append(
            ("nested_group_shape", (slide_index, group_index, child_index))
        )

    def _queue_group_shape_to_nested_group_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
    ) -> None:
        self._shape_adds.append(
            (
                "group_shape_to_nested_group",
                (slide_index, group_index, nested_group_child_index, child_index),
            )
        )

    def _queue_group_shape_to_deeper_nested_group_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
    ) -> None:
        self._shape_adds.append(
            (
                "group_shape_to_deeper_nested_group",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_index,
                ),
            )
        )
