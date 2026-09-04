"""Queued grouped connector operations for the presentation facade."""

from __future__ import annotations

from .presentation_edit_queue_group_freeform import PresentationGroupFreeformQueueMixin


class PresentationGroupConnectorQueueMixin(PresentationGroupFreeformQueueMixin):
    def _queue_group_connector_add(
        self,
        slide_index: int,
        group_index: int,
        group_shape_index: int,
        child_index: int,
        preset_geometry: str,
        begin_x_emu: int,
        begin_y_emu: int,
        end_x_emu: int,
        end_y_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "group_connector",
                (
                    slide_index,
                    group_index,
                    group_shape_index,
                    child_index,
                    preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    end_x_emu,
                    end_y_emu,
                ),
            )
        )

    def _queue_nested_group_connector_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        preset_geometry: str,
        begin_x_emu: int,
        begin_y_emu: int,
        end_x_emu: int,
        end_y_emu: int,
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
                    "nested_group_connector_in_new_group",
                    (
                        slide_index,
                        group_index,
                        nested_group_child_index,
                        child_index,
                        preset_geometry,
                        begin_x_emu,
                        begin_y_emu,
                        end_x_emu,
                        end_y_emu,
                    ),
                )
                return
        self._shape_adds.append(
            (
                "nested_group_connector",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    child_index,
                    preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    end_x_emu,
                    end_y_emu,
                ),
            )
        )

    def _queue_deeper_nested_group_connector_add(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        preset_geometry: str,
        begin_x_emu: int,
        begin_y_emu: int,
        end_x_emu: int,
        end_y_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "deeper_nested_group_connector",
                (
                    slide_index,
                    group_index,
                    nested_group_child_index,
                    deeper_group_child_index,
                    child_index,
                    preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    end_x_emu,
                    end_y_emu,
                ),
            )
        )
