"""Coalesce connector shape-add operations into native fused adds."""

from __future__ import annotations

from typing import Any

ShapeAdd = tuple[str, tuple[Any, ...]]


def coalesce_connected_connector_auto_shapes(
    shape_adds: list[ShapeAdd],
) -> list[ShapeAdd]:
    coalesced: list[ShapeAdd] = []
    index = 0
    while index < len(shape_adds):
        if index + 2 >= len(shape_adds):
            coalesced.append(shape_adds[index])
            index += 1
            continue
        first = shape_adds[index]
        second = shape_adds[index + 1]
        connector = shape_adds[index + 2]
        combined = (
            _connected_connector_auto_shape_add(first, second, connector)
            or _connected_group_connector_auto_shape_add(first, second, connector)
        )
        if combined is None:
            coalesced.append(first)
            index += 1
            continue
        coalesced.append(combined)
        index += 3
    return coalesced


def _connected_connector_auto_shape_add(
    first: ShapeAdd,
    second: ShapeAdd,
    connector: ShapeAdd,
) -> ShapeAdd | None:
    first_kind, first_args = first
    second_kind, second_args = second
    connector_kind, connector_args = connector
    if (
        first_kind != "auto_shape"
        or second_kind != "auto_shape"
        or connector_kind != "connected_connector"
    ):
        return None
    first_auto = _plain_auto_shape_args(first_args)
    second_auto = _plain_auto_shape_args(second_args)
    if first_auto is None or second_auto is None:
        return None
    (
        first_slide_index,
        first_shape_index,
        first_preset_geometry,
        first_x_emu,
        first_y_emu,
        first_cx_emu,
        first_cy_emu,
        first_shape_id,
    ) = first_auto
    (
        second_slide_index,
        second_shape_index,
        second_preset_geometry,
        second_x_emu,
        second_y_emu,
        second_cx_emu,
        second_cy_emu,
        second_shape_id,
    ) = second_auto
    (
        connector_slide_index,
        connector_shape_index,
        connector_preset_geometry,
        connector_begin_x_emu,
        connector_begin_y_emu,
        connector_end_x_emu,
        connector_end_y_emu,
        begin_connection,
        end_connection,
    ) = connector_args
    if (
        first_slide_index != second_slide_index
        or first_slide_index != connector_slide_index
        or begin_connection is None
        or end_connection is None
    ):
        return None
    if begin_connection[0] != first_shape_id or end_connection[0] != second_shape_id:
        return None
    return (
        "connected_connector_with_auto_shapes",
        (
            connector_slide_index,
            first_shape_index,
            first_preset_geometry,
            first_x_emu,
            first_y_emu,
            first_cx_emu,
            first_cy_emu,
            second_shape_index,
            second_preset_geometry,
            second_x_emu,
            second_y_emu,
            second_cx_emu,
            second_cy_emu,
            connector_shape_index,
            connector_preset_geometry,
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_connection[1],
            end_connection[1],
        ),
    )


def _plain_auto_shape_args(args: tuple[Any, ...]) -> tuple[Any, ...] | None:
    if len(args) != 8:
        return None
    (
        slide_index,
        shape_index,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        shape_id,
    ) = args
    if not isinstance(shape_id, int):
        return None
    return (
        slide_index,
        shape_index,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        shape_id,
    )


def _connected_group_connector_auto_shape_add(
    first: ShapeAdd,
    second: ShapeAdd,
    connector: ShapeAdd,
) -> ShapeAdd | None:
    first_kind, first_args = first
    second_kind, second_args = second
    connector_kind, connector_args = connector
    if (
        first_kind != "group_auto_shape"
        or second_kind != "group_auto_shape"
        or connector_kind != "connected_group_connector"
    ):
        return None
    first_auto = _plain_group_auto_shape_args(first_args)
    second_auto = _plain_group_auto_shape_args(second_args)
    if first_auto is None or second_auto is None:
        return None
    (
        first_slide_index,
        first_group_index,
        first_child_index,
        first_preset_geometry,
        first_x_emu,
        first_y_emu,
        first_cx_emu,
        first_cy_emu,
        first_shape_id,
    ) = first_auto
    (
        second_slide_index,
        second_group_index,
        second_child_index,
        second_preset_geometry,
        second_x_emu,
        second_y_emu,
        second_cx_emu,
        second_cy_emu,
        second_shape_id,
    ) = second_auto
    (
        connector_slide_index,
        connector_group_index,
        connector_group_shape_index,
        connector_child_index,
        connector_preset_geometry,
        connector_begin_x_emu,
        connector_begin_y_emu,
        connector_end_x_emu,
        connector_end_y_emu,
        begin_connection,
        end_connection,
    ) = connector_args
    if (
        first_slide_index != second_slide_index
        or first_slide_index != connector_slide_index
        or first_group_index != second_group_index
        or first_group_index != connector_group_index
        or begin_connection is None
        or end_connection is None
    ):
        return None
    if begin_connection[0] != first_shape_id or end_connection[0] != second_shape_id:
        return None
    return (
        "connected_group_connector_with_auto_shapes",
        (
            connector_slide_index,
            connector_group_index,
            first_child_index,
            first_preset_geometry,
            first_x_emu,
            first_y_emu,
            first_cx_emu,
            first_cy_emu,
            second_child_index,
            second_preset_geometry,
            second_x_emu,
            second_y_emu,
            second_cx_emu,
            second_cy_emu,
            connector_group_shape_index,
            connector_child_index,
            connector_preset_geometry,
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_connection[1],
            end_connection[1],
        ),
    )


def _plain_group_auto_shape_args(args: tuple[Any, ...]) -> tuple[Any, ...] | None:
    if len(args) != 10:
        return None
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
        shape_id,
    ) = args
    if text or not isinstance(shape_id, int):
        return None
    return (
        slide_index,
        group_index,
        child_index,
        preset_geometry,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        shape_id,
    )
