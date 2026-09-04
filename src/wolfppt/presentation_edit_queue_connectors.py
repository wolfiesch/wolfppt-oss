"""Queued connector-add operations for the presentation facade."""

from __future__ import annotations

from typing import Any


class PresentationConnectorAddQueueMixin:
    def _queue_connector_add(
        self,
        slide_index: int,
        shape_index: int,
        preset_geometry: str,
        begin_x_emu: int,
        begin_y_emu: int,
        end_x_emu: int,
        end_y_emu: int,
    ) -> None:
        self._shape_adds.append(
            (
                "connector",
                (
                    slide_index,
                    shape_index,
                    preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    end_x_emu,
                    end_y_emu,
                ),
            )
        )

    def _queue_pending_connector_connection(
        self,
        slide_index: int,
        shape_index: Any,
        endpoint: str,
        connection: dict[str, Any],
        begin_x_emu: int,
        begin_y_emu: int,
        end_x_emu: int,
        end_y_emu: int,
    ) -> bool:
        for index, (add_kind, args) in enumerate(self._shape_adds):
            if add_kind == "connector":
                (
                    queued_slide_index,
                    queued_shape_index,
                    preset_geometry,
                    _queued_begin_x_emu,
                    _queued_begin_y_emu,
                    _queued_end_x_emu,
                    _queued_end_y_emu,
                ) = args
                begin_connection = None
                end_connection = None
            elif add_kind == "connected_connector":
                (
                    queued_slide_index,
                    queued_shape_index,
                    preset_geometry,
                    _queued_begin_x_emu,
                    _queued_begin_y_emu,
                    _queued_end_x_emu,
                    _queued_end_y_emu,
                    begin_connection,
                    end_connection,
                ) = args
            elif add_kind == "group_connector":
                (
                    queued_slide_index,
                    queued_group_index,
                    queued_group_shape_index,
                    queued_child_index,
                    preset_geometry,
                    _queued_begin_x_emu,
                    _queued_begin_y_emu,
                    _queued_end_x_emu,
                    _queued_end_y_emu,
                ) = args
                if shape_index != (queued_group_shape_index, queued_child_index):
                    continue
                begin_connection = None
                end_connection = None
            elif add_kind == "connected_group_connector":
                (
                    queued_slide_index,
                    queued_group_index,
                    queued_group_shape_index,
                    queued_child_index,
                    preset_geometry,
                    _queued_begin_x_emu,
                    _queued_begin_y_emu,
                    _queued_end_x_emu,
                    _queued_end_y_emu,
                    begin_connection,
                    end_connection,
                ) = args
                if shape_index != (queued_group_shape_index, queued_child_index):
                    continue
            else:
                continue
            if add_kind in {"connector", "connected_connector"}:
                if (queued_slide_index, queued_shape_index) != (slide_index, shape_index):
                    continue
                replacement_kind = "connected_connector"
                replacement_args = (
                    slide_index,
                    shape_index,
                    preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    end_x_emu,
                    end_y_emu,
                )
            else:
                if queued_slide_index != slide_index:
                    continue
                replacement_kind = "connected_group_connector"
                replacement_args = (
                    slide_index,
                    queued_group_index,
                    queued_group_shape_index,
                    queued_child_index,
                    preset_geometry,
                    begin_x_emu,
                    begin_y_emu,
                    end_x_emu,
                    end_y_emu,
                )
            connection_ref = (
                int(connection["shape_id"]),
                int(connection["cxn_pt_idx"]),
            )
            if endpoint == "begin":
                begin_connection = connection_ref
            else:
                end_connection = connection_ref
            self._shape_adds[index] = (
                replacement_kind,
                (*replacement_args, begin_connection, end_connection),
            )
            return True
        return False
