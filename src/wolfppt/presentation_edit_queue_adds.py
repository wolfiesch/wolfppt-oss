"""Queued slide and shape-add operations for the presentation facade."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .presentation_edit_queue_group_text_boxes import (
    PresentationGroupTextBoxAddQueueMixin,
)

if TYPE_CHECKING:
    from .presentation_slides import SlideLayout


class PresentationAddQueueMixin(PresentationGroupTextBoxAddQueueMixin):
    def _queue_slide_add(
        self, slide_layout: "SlideLayout", token: Any = None
    ) -> None:
        self._slide_creations.append(("blank", slide_layout, token))

    def _queue_slide_duplicate(
        self, source_partname: str, token: Any = None
    ) -> None:
        self._slide_creations.append(("duplicate", source_partname, token))

    def _queue_slide_layout_remove(self, partname: str) -> None:
        self._slide_layout_removals.append(partname)

    def _queue_part_placeholder_add(
        self,
        partname: str,
        spec: dict[str, str | bool | None],
    ) -> None:
        self._part_placeholder_adds.append((partname, dict(spec)))

    def _queue_table_add(
        self,
        slide_index: int,
        table_index: int,
        rows: int,
        cols: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "table",
                (slide_index, table_index, rows, cols, x_emu, y_emu, cx_emu, cy_emu),
            )
        )

    def _queue_chart_add(
        self,
        slide_index: int,
        chart_type: Any,
        chart_data: Any,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "chart",
                (slide_index, chart_type, chart_data, x_emu, y_emu, cx_emu, cy_emu),
            )
        )

    def _queue_text_box_add(
        self,
        slide_index: int,
        shape_index: int,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._shape_adds.append(
            ("text_box", (slide_index, x_emu, y_emu, cx_emu, cy_emu, shape_index))
        )

    def _queue_group_chart_add(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        chart_type: Any,
        chart_data: Any,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "group_chart",
                (
                    slide_index,
                    group_index,
                    child_index,
                    chart_type,
                    chart_data,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                ),
            )
        )

    def _queue_nested_group_chart_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        chart_type: Any,
        chart_data: Any,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
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
                    "nested_group_chart_in_new_group",
                    (
                        slide_index,
                        group_index,
                        nested_group_child_index,
                        child_index,
                        chart_type,
                        chart_data,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                    ),
                )
                return
        self._shape_adds.append(
            (
                "nested_group_chart",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    child_index,
                    chart_type,
                    chart_data,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                ),
            )
        )

    def _queue_deeper_nested_group_chart_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        chart_type: Any,
        chart_data: Any,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "deeper_nested_group_chart",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_index,
                    chart_type,
                    chart_data,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                ),
            )
        )

    def _queue_group_auto_shape_add(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        preset_geometry: str,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
        shape_id: int,
    ) -> None:
        self._shape_adds.append(
            (
                "group_auto_shape",
                (
                    slide_index,
                    group_index,
                    child_index,
                    preset_geometry,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    "",
                    shape_id,
                ),
            )
        )

    def _queue_nested_group_auto_shape_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        preset_geometry: str,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        if self._shape_adds:
            previous_kind, previous_args = self._shape_adds[-1]
            if (
                previous_kind == "nested_group_shape"
                and previous_args == (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                )
            ):
                self._shape_adds[-1] = (
                    "nested_group_auto_shape_in_new_group",
                    (
                        slide_index,
                        group_index,
                        nested_group_child_index,
                        child_index,
                        preset_geometry,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        "",
                    ),
                )
                return
        self._shape_adds.append(
            (
                "nested_group_auto_shape",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    child_index,
                    preset_geometry,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    "",
                ),
            )
        )

    def _queue_deeper_nested_group_auto_shape_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        preset_geometry: str,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "deeper_nested_group_auto_shape",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_index,
                    preset_geometry,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    "",
                ),
            )
        )

    def _queue_group_auto_shape_text(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        text: str,
    ) -> None:
        for index, (add_kind, args) in enumerate(self._shape_adds):
            if add_kind != "group_auto_shape":
                continue
            (
                queued_slide_index,
                queued_group_index,
                queued_child_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                _queued_text,
                *shape_id_tail,
            ) = args
            shape_id_tail_tuple = tuple(shape_id_tail)
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
                        preset_geometry,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        text,
                        *shape_id_tail_tuple,
                    ),
                )
                return

    def _queue_nested_group_auto_shape_text(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        text: str,
    ) -> None:
        for index, (add_kind, args) in enumerate(self._shape_adds):
            if add_kind not in {
                "nested_group_auto_shape",
                "nested_group_auto_shape_in_new_group",
            }:
                continue
            (
                queued_slide_index,
                queued_group_index,
                queued_nested_group_child_index,
                queued_child_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
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
                        preset_geometry,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        text,
                    ),
                )
                return

    def _queue_deeper_nested_group_auto_shape_text(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        text: str,
    ) -> None:
        for index, (add_kind, args) in enumerate(self._shape_adds):
            if add_kind != "deeper_nested_group_auto_shape":
                continue
            (
                queued_slide_index,
                queued_group_index,
                queued_nested_group_child_index,
                queued_deeper_group_child_index,
                queued_child_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
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
                        preset_geometry,
                        x_emu,
                        y_emu,
                        cx_emu,
                        cy_emu,
                        text,
                    ),
                )
                return

    def _queue_freeform_shape_add(
        self,
        slide_index: int,
        shape_index: int,
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
                "freeform_shape",
                (
                    slide_index,
                    shape_index,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    path_w,
                    path_h,
                    [dict(operation) for operation in operations],
                ),
            )
        )

    def _queue_placeholder_shape_add(
        self,
        slide_index: int,
        shape_index: int,
        placeholder_type: str | None,
        placeholder_orient: str | None,
        placeholder_size: str | None,
        placeholder_idx: str | None,
    ) -> None:
        self._shape_adds.append(
            (
                "placeholder_shape",
                (
                    slide_index,
                    shape_index,
                    placeholder_type,
                    placeholder_orient,
                    placeholder_size,
                    placeholder_idx,
                ),
            )
        )

    def _queue_placeholder_shapes_add(
        self,
        slide_index: int,
        placeholders: list[dict[str, str | None]],
    ) -> None:
        self._shape_adds.append(
            (
                "placeholder_shapes",
                (
                    slide_index,
                    [dict(placeholder) for placeholder in placeholders],
                ),
            )
        )

    def _queue_layout_placeholders_add(
        self,
        slide_index: int,
        layout_index: int,
    ) -> None:
        self._shape_adds.append(
            (
                "layout_placeholders",
                (
                    slide_index,
                    layout_index,
                ),
            )
        )

    def _queue_auto_shape_add(
        self,
        slide_index: int,
        shape_index: int,
        shape_id: int,
        preset_geometry: str,
        x_emu: int,
        y_emu: int,
        cx_emu: int,
        cy_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "auto_shape",
                (
                    slide_index,
                    shape_index,
                    preset_geometry,
                    x_emu,
                    y_emu,
                    cx_emu,
                    cy_emu,
                    shape_id,
                ),
            )
        )
