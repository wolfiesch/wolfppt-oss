"""Queued grouped freeform-shape operations for the presentation facade."""

from __future__ import annotations

from typing import Any

from .presentation_edit_queue_media import PresentationMediaAddQueueMixin


class PresentationGroupFreeformQueueMixin(PresentationMediaAddQueueMixin):
    def _queue_group_freeform_shape_add(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        path_w: int,
        path_h: int,
        operations: list[dict[str, Any]],
    ) -> None:
        self._shape_adds.append(
            (
                "group_freeform_shape",
                (
                    slide_index,
                    group_index,
                    child_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    [dict(operation) for operation in operations],
                    "",
                ),
            )
        )

    def _queue_group_freeform_shape_text(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        text: str,
    ) -> None:
        for index, (add_kind, args) in enumerate(self._shape_adds):
            if add_kind != "group_freeform_shape":
                continue
            (
                queued_slide_index,
                queued_group_index,
                queued_child_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                path_w,
                path_h,
                operations,
                _queued_text,
            ) = args
            if (
                queued_slide_index,
                queued_group_index,
                queued_child_index,
            ) == (slide_index, group_index, child_index):
                self._shape_adds[index] = (
                    add_kind,
                    (
                        slide_index,
                        group_index,
                        child_index,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        path_w,
                        path_h,
                        operations,
                        text,
                    ),
                )
                return

    def _queue_nested_group_freeform_shape_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        path_w: int,
        path_h: int,
        operations: list[dict[str, Any]],
    ) -> None:
        if self._shape_adds:
            previous_kind, previous_args = self._shape_adds[-1]
            if (
                previous_kind == "nested_group_shape"
                and previous_args
                == (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                )
            ):
                self._shape_adds[-1] = (
                    "nested_group_freeform_shape_in_new_group",
                    (
                        slide_index,
                        group_index,
                        nested_group_child_index,
                        child_index,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        path_w,
                        path_h,
                        [dict(operation) for operation in operations],
                        "",
                    ),
                )
                return
        self._shape_adds.append(
            (
                "nested_group_freeform_shape",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    child_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    [dict(operation) for operation in operations],
                    "",
                ),
            )
        )

    def _queue_nested_group_freeform_shape_text(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        text: str,
    ) -> None:
        for index, (add_kind, args) in enumerate(self._shape_adds):
            if add_kind not in {
                "nested_group_freeform_shape",
                "nested_group_freeform_shape_in_new_group",
            }:
                continue
            (
                queued_slide_index,
                queued_group_index,
                queued_nested_group_child_index,
                queued_child_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                path_w,
                path_h,
                operations,
                _queued_text,
            ) = args
            if (
                queued_slide_index,
                queued_group_index,
                queued_nested_group_child_index,
                queued_child_index,
            ) == (slide_index, group_index, nested_group_child_index, child_index):
                self._shape_adds[index] = (
                    add_kind,
                    (
                        slide_index,
                        group_index,
                        nested_group_child_index,
                        child_index,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        path_w,
                        path_h,
                        operations,
                        text,
                    ),
                )
                return

    def _queue_deeper_nested_group_freeform_shape_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        path_w: int,
        path_h: int,
        operations: list[dict[str, Any]],
    ) -> None:
        self._shape_adds.append(
            (
                "deeper_nested_group_freeform_shape",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    [dict(operation) for operation in operations],
                    "",
                ),
            )
        )

    def _queue_deeper_nested_group_freeform_shape_text(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        text: str,
    ) -> None:
        for index, (add_kind, args) in enumerate(self._shape_adds):
            if add_kind != "deeper_nested_group_freeform_shape":
                continue
            (
                queued_slide_index,
                queued_group_index,
                queued_nested_group_child_index,
                queued_deeper_group_child_index,
                queued_child_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                path_w,
                path_h,
                operations,
                _queued_text,
            ) = args
            if (
                queued_slide_index,
                queued_group_index,
                queued_nested_group_child_index,
                queued_deeper_group_child_index,
                queued_child_index,
            ) == (
                slide_index,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                child_index,
            ):
                self._shape_adds[index] = (
                    add_kind,
                    (
                        slide_index,
                        group_index,
                        nested_group_child_index,
                        deeper_group_child_index,
                        child_index,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        path_w,
                        path_h,
                        operations,
                        text,
                    ),
                )
                return
