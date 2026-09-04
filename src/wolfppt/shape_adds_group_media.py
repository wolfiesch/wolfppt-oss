"""Dispatch grouped media and OLE shape-add operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import native
from .image_inputs import InMemoryFile, InMemoryImage


def apply_group_media_shape_add(
    add_kind: str,
    args: tuple[Any, ...],
    current: Path,
    step: Path,
) -> bool:
    if add_kind == "group_picture":
        (
            slide_index,
            group_index,
            _child_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        if isinstance(image_path, InMemoryImage):
            image_path = image_path.materialize(step.parent, f"{step.stem}-image")
        native.add_group_image(
            current,
            step,
            slide_index,
            group_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        return True
    if add_kind == "nested_group_picture":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        if isinstance(image_path, InMemoryImage):
            image_path = image_path.materialize(step.parent, f"{step.stem}-image")
        native.add_nested_group_image(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        return True
    if add_kind == "deeper_nested_group_picture":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        if isinstance(image_path, InMemoryImage):
            image_path = image_path.materialize(step.parent, f"{step.stem}-image")
        native.add_deeper_nested_group_image(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        return True
    if add_kind == "nested_group_picture_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        if isinstance(image_path, InMemoryImage):
            image_path = image_path.materialize(step.parent, f"{step.stem}-image")
        native.add_nested_group_image_in_new_group(
            current,
            step,
            slide_index,
            group_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        return True
    if add_kind == "group_ole_object":
        (
            slide_index,
            group_index,
            _child_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        ) = args
        if isinstance(object_path, InMemoryFile):
            object_path = object_path.materialize(step.parent)
        if isinstance(icon_path, InMemoryImage):
            icon_path = icon_path.materialize(step.parent, f"{step.stem}-icon")
        native.add_group_ole_object(
            current,
            step,
            slide_index,
            group_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        )
        return True
    if add_kind == "nested_group_ole_object":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        ) = args
        if isinstance(object_path, InMemoryFile):
            object_path = object_path.materialize(step.parent)
        if isinstance(icon_path, InMemoryImage):
            icon_path = icon_path.materialize(step.parent, f"{step.stem}-icon")
        native.add_nested_group_ole_object(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        )
        return True
    if add_kind == "deeper_nested_group_ole_object":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        ) = args
        if isinstance(object_path, InMemoryFile):
            object_path = object_path.materialize(step.parent)
        if isinstance(icon_path, InMemoryImage):
            icon_path = icon_path.materialize(step.parent, f"{step.stem}-icon")
        native.add_deeper_nested_group_ole_object(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        )
        return True
    if add_kind == "nested_group_ole_object_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        ) = args
        if isinstance(object_path, InMemoryFile):
            object_path = object_path.materialize(step.parent)
        if isinstance(icon_path, InMemoryImage):
            icon_path = icon_path.materialize(step.parent, f"{step.stem}-icon")
        native.add_nested_group_ole_object_in_new_group(
            current,
            step,
            slide_index,
            group_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        )
        return True
    return False
