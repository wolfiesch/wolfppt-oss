"""Dispatch grouped connector shape-add operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import native


def apply_group_connector_shape_add(
    add_kind: str,
    args: tuple[Any, ...],
    current: Path,
    step: Path,
) -> bool:
    if add_kind == "connected_group_connector_with_auto_shapes":
        (
            slide_index,
            group_index,
            _begin_child_index,
            begin_preset_geometry,
            begin_x_emu,
            begin_y_emu,
            begin_cx_emu,
            begin_cy_emu,
            _end_child_index,
            end_preset_geometry,
            end_x_emu,
            end_y_emu,
            end_cx_emu,
            end_cy_emu,
            _connector_group_shape_index,
            _connector_child_index,
            connector_preset_geometry,
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_cxn_pt_idx,
            end_cxn_pt_idx,
        ) = args
        native.add_connected_group_connector_with_auto_shapes(
            current,
            step,
            slide_index,
            group_index,
            begin_preset_geometry,
            begin_x_emu,
            begin_y_emu,
            begin_cx_emu,
            begin_cy_emu,
            end_preset_geometry,
            end_x_emu,
            end_y_emu,
            end_cx_emu,
            end_cy_emu,
            connector_preset_geometry,
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_cxn_pt_idx,
            end_cxn_pt_idx,
        )
        return True
    if add_kind == "group_connector":
        (
            slide_index,
            group_index,
            _group_shape_index,
            _child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        ) = args
        native.add_group_connector(
            current,
            step,
            slide_index,
            group_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
        return True
    if add_kind == "connected_group_connector":
        (
            slide_index,
            group_index,
            _group_shape_index,
            _child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
            begin_connection,
            end_connection,
        ) = args
        native.add_connected_group_connector(
            current,
            step,
            slide_index,
            group_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
            begin_connection,
            end_connection,
        )
        return True
    if add_kind == "nested_group_connector":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        ) = args
        native.add_nested_group_connector(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
        return True
    if add_kind == "deeper_nested_group_connector":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        ) = args
        native.add_deeper_nested_group_connector(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
        return True
    if add_kind == "nested_group_connector_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        ) = args
        native.add_nested_group_connector_in_new_group(
            current,
            step,
            slide_index,
            group_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
        return True
    return False
