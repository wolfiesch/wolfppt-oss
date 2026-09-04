"""Media, table, and chart shape-add dispatch helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import native
from .image_inputs import InMemoryFile, InMemoryImage
from .table_adds import apply_table_add

ChartAddFn = Callable[..., None]


def apply_media_or_chart_shape_add(
    add_kind: str,
    args: tuple[Any, ...],
    current: Path,
    step: Path,
    apply_chart_add: ChartAddFn,
) -> bool:
    if add_kind == "picture":
        slide_index, image_path, x_emu, y_emu, cx_emu, cy_emu = args
        if isinstance(image_path, InMemoryImage):
            image_path = image_path.materialize(step.parent, f"{step.stem}-image")
        native.add_image(
            current,
            step,
            slide_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        return True
    if add_kind == "movie":
        (
            slide_index,
            movie_path,
            poster_frame_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type,
        ) = args
        if isinstance(movie_path, InMemoryFile):
            movie_path = movie_path.materialize(step.parent)
        if isinstance(poster_frame_path, InMemoryImage):
            poster_frame_path = poster_frame_path.materialize(
                step.parent,
                f"{step.stem}-poster",
            )
        native.add_movie(
            current,
            step,
            slide_index,
            movie_path,
            poster_frame_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type,
        )
        return True
    if add_kind == "ole_object":
        (
            slide_index,
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
        native.add_ole_object(
            current,
            step,
            slide_index,
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
    if add_kind == "table":
        (
            slide_index,
            _table_index,
            rows,
            cols,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            *cell_texts,
        ) = args
        apply_table_add(
            current,
            step,
            slide_index,
            rows,
            cols,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            cell_texts[0] if cell_texts else None,
        )
        return True
    if add_kind == "chart":
        slide_index, chart_type, chart_data, x_emu, y_emu, cx_emu, cy_emu = args
        apply_chart_add(
            current,
            step,
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        return True
    if add_kind == "group_chart":
        (
            slide_index,
            group_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        apply_chart_add(
            current,
            step,
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index=group_index,
        )
        return True
    if add_kind == "nested_group_chart":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        apply_chart_add(
            current,
            step,
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index=group_index,
            nested_group_child_index=nested_group_child_index,
        )
        return True
    if add_kind == "deeper_nested_group_chart":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        apply_chart_add(
            current,
            step,
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index=group_index,
            nested_group_child_index=nested_group_child_index,
            deeper_group_child_index=deeper_group_child_index,
        )
        return True
    return False
