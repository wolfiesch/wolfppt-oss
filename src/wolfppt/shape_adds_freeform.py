"""Dispatch freeform shape-add operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import native


def apply_freeform_shape_add(
    add_kind: str,
    args: tuple[Any, ...],
    current: Path,
    step: Path,
) -> bool:
    if add_kind == "freeform_shape":
        (
            slide_index,
            _shape_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            *text,
        ) = args
        if text:
            native.add_freeform_shape_with_text(
                current,
                step,
                slide_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                path_w,
                path_h,
                operations,
                text[0],
            )
        else:
            native.add_freeform_shape(
                current,
                step,
                slide_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                path_w,
                path_h,
                operations,
            )
        return True
    if add_kind == "group_freeform_shape":
        (
            slide_index,
            group_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            text,
        ) = args
        native.add_group_freeform_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            text,
        )
        return True
    if add_kind == "nested_group_freeform_shape":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            text,
        ) = args
        native.add_nested_group_freeform_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            text,
        )
        return True
    if add_kind == "deeper_nested_group_freeform_shape":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            text,
        ) = args
        native.add_deeper_nested_group_freeform_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            text,
        )
        return True
    if add_kind == "nested_group_freeform_shape_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            text,
        ) = args
        native.add_nested_group_freeform_shape_in_new_group_with_text(
            current,
            step,
            slide_index,
            group_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            operations,
            text,
        )
        return True
    return False
