"""Dispatch native shape-add operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import native
from .group_shape_edits import (
    apply_existing_deeper_nested_group_child_grouping,
    apply_existing_group_child_grouping,
    apply_existing_nested_group_child_grouping,
    apply_existing_shape_grouping,
)
from .shape_adds_freeform import apply_freeform_shape_add
from .shape_adds_group_connectors import apply_group_connector_shape_add
from .shape_adds_group_media import apply_group_media_shape_add
from .shape_adds_media_chart import apply_media_or_chart_shape_add
from .shape_connector_adds import coalesce_connected_connector_auto_shapes


ChartAddFn = Callable[..., None]
ShapeAdd = tuple[str, tuple[Any, ...]]
ShapeTextEdit = tuple[tuple[int, int], str]
TableCellTextEdit = tuple[tuple[int, int, int, int], str]
ShapeRef = int | tuple[int, int]
ShapeAdjustmentEdit = tuple[tuple[int, ShapeRef], list[tuple[str, int]]]


def coalesce_auto_shape_text(
    shape_adds: list[ShapeAdd],
    text_edits: list[ShapeTextEdit],
) -> tuple[list[ShapeAdd], list[ShapeTextEdit]]:
    text_by_shape = dict(text_edits)
    consumed: set[tuple[int, int]] = set()
    coalesced: list[ShapeAdd] = []
    for add_kind, args in shape_adds:
        if add_kind == "auto_shape":
            slide_index, shape_index, *_ = args
            key = (slide_index, shape_index)
            if key in text_by_shape:
                coalesced.append((add_kind, (*args, text_by_shape[key])))
                consumed.add(key)
                continue
        if add_kind == "freeform_shape":
            slide_index, shape_index, *_ = args
            key = (slide_index, shape_index)
            if key in text_by_shape:
                coalesced.append((add_kind, (*args, text_by_shape[key])))
                consumed.add(key)
                continue
        if add_kind == "text_box":
            slide_index, _x_emu, _y_emu, _cx_emu, _cy_emu, shape_index = args
            key = (slide_index, shape_index)
            if key in text_by_shape:
                coalesced.append((add_kind, (*args, text_by_shape[key])))
                consumed.add(key)
                continue
        coalesced.append((add_kind, args))
    remaining_text_edits = [
        (key, text) for key, text in text_edits if key not in consumed
    ]
    return coalesced, remaining_text_edits


def coalesce_table_cell_text(
    shape_adds: list[ShapeAdd],
    table_cell_edits: list[TableCellTextEdit],
) -> tuple[list[ShapeAdd], list[TableCellTextEdit]]:
    edits_by_table: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
    for (slide_index, table_index, row_index, col_index), text in table_cell_edits:
        edits_by_table.setdefault((slide_index, table_index), []).append(
            (row_index, col_index, text)
        )

    consumed: set[tuple[int, int]] = set()
    coalesced: list[ShapeAdd] = []
    for add_kind, args in shape_adds:
        if add_kind == "table":
            slide_index, table_index, *_ = args
            key = (slide_index, table_index)
            if key in edits_by_table:
                coalesced.append((add_kind, (*args, edits_by_table[key])))
                consumed.add(key)
                continue
        coalesced.append((add_kind, args))

    remaining_table_cell_edits = [
        (key, text)
        for key, text in table_cell_edits
        if (key[0], key[1]) not in consumed
    ]
    return coalesced, remaining_table_cell_edits


def coalesce_auto_shape_adjustments(
    shape_adds: list[ShapeAdd],
    adjustment_edits: list[ShapeAdjustmentEdit],
) -> tuple[list[ShapeAdd], list[ShapeAdjustmentEdit]]:
    adjustments_by_shape = dict(adjustment_edits)
    consumed: set[tuple[int, int]] = set()
    coalesced: list[ShapeAdd] = []
    for add_kind, args in shape_adds:
        if add_kind == "auto_shape":
            slide_index, shape_index, *_ = args
            key = (slide_index, shape_index)
            if key in adjustments_by_shape:
                coalesced.append((add_kind, (*args, adjustments_by_shape[key])))
                consumed.add(key)
                continue
        coalesced.append((add_kind, args))
    remaining_adjustment_edits = [
        (key, guides) for key, guides in adjustment_edits if key not in consumed
    ]
    return coalesced, remaining_adjustment_edits


def apply_shape_add(
    add_kind: str,
    args: tuple[Any, ...],
    current: Path,
    step: Path,
    apply_chart_add: ChartAddFn,
) -> None:
    if apply_media_or_chart_shape_add(add_kind, args, current, step, apply_chart_add):
        return
    if apply_group_connector_shape_add(add_kind, args, current, step):
        return
    if apply_group_media_shape_add(add_kind, args, current, step):
        return
    if apply_freeform_shape_add(add_kind, args, current, step):
        return
    if add_kind == "text_box":
        slide_index, x_emu, y_emu, cx_emu, cy_emu, *_shape_index_and_text = args
        text = _shape_index_and_text[1:] if len(_shape_index_and_text) > 1 else ()
        if text:
            native.add_text_box_with_text(
                current,
                step,
                slide_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                text[0],
            )
        else:
            native.add_text_box(
                current,
                step,
                slide_index,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        return
    if add_kind == "group_text_box":
        (
            slide_index,
            group_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_group_text_box_with_text(
            current,
            step,
            slide_index,
            group_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "nested_group_text_box":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_nested_group_text_box_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "nested_group_text_box_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_nested_group_text_box_in_new_group_with_text(
            current,
            step,
            slide_index,
            group_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "deeper_nested_group_text_box":
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
            text,
        ) = args
        native.add_deeper_nested_group_text_box_with_text(
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
            text,
        )
        return
    if add_kind == "group_auto_shape":
        (
            slide_index,
            group_index,
            _child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
            *_shape_id_tail,
        ) = args
        native.add_group_auto_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "nested_group_auto_shape":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_nested_group_auto_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "deeper_nested_group_auto_shape":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_deeper_nested_group_auto_shape_with_text(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "nested_group_auto_shape_in_new_group":
        (
            slide_index,
            group_index,
            _nested_group_child_index,
            _child_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        ) = args
        native.add_nested_group_auto_shape_in_new_group_with_text(
            current,
            step,
            slide_index,
            group_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
        return
    if add_kind == "group_shape":
        (slide_index,) = args
        native.add_group_shape(current, step, slide_index)
        return
    if add_kind == "group_existing_shapes":
        slide_index, shape_indices = args
        apply_existing_shape_grouping(current, step, slide_index, tuple(shape_indices))
        return
    if add_kind == "group_existing_child_shapes":
        slide_index, group_index, child_indices = args
        apply_existing_group_child_grouping(
            current,
            step,
            slide_index,
            group_index,
            tuple(child_indices),
        )
        return
    if add_kind == "group_existing_nested_child_shapes":
        slide_index, group_index, nested_group_child_index, child_indices = args
        apply_existing_nested_group_child_grouping(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            tuple(child_indices),
        )
        return
    if add_kind == "group_existing_deeper_nested_child_shapes":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            child_indices,
        ) = args
        apply_existing_deeper_nested_group_child_grouping(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            tuple(child_indices),
        )
        return
    if add_kind == "nested_group_shape":
        slide_index, group_index, _child_index = args
        native.add_nested_group_shape(current, step, slide_index, group_index)
        return
    if add_kind == "group_shape_to_nested_group":
        slide_index, group_index, nested_group_child_index, _child_index = args
        native.add_group_shape_to_nested_group(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
        )
        return
    if add_kind == "group_shape_to_deeper_nested_group":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
        ) = args
        native.add_group_shape_to_deeper_nested_group(
            current,
            step,
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
        )
        return
    if add_kind == "placeholder_shape":
        (
            slide_index,
            _shape_index,
            placeholder_type,
            placeholder_orient,
            placeholder_size,
            placeholder_idx,
        ) = args
        native.add_placeholder_shape(
            current,
            step,
            slide_index,
            placeholder_type,
            placeholder_orient,
            placeholder_size,
            placeholder_idx,
        )
        return
    if add_kind == "placeholder_shapes":
        slide_index, placeholders = args
        native.add_placeholder_shapes(
            current,
            step,
            slide_index,
            placeholders,
        )
        return
    if add_kind == "layout_placeholders":
        slide_index, layout_index = args
        native.add_layout_placeholders(
            current,
            step,
            slide_index,
            layout_index,
        )
        return
    if add_kind == "auto_shape":
        (
            slide_index,
            _shape_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            *extras,
        ) = args
        text = next((extra for extra in extras if isinstance(extra, str)), None)
        adjustment_guides = next(
            (extra for extra in extras if isinstance(extra, list)),
            [],
        )
        if adjustment_guides:
            native.add_auto_shape_with_options(
                current,
                step,
                slide_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                text,
                adjustment_guides,
            )
        elif text is not None:
            native.add_auto_shape_with_text(
                current,
                step,
                slide_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                text,
            )
        else:
            native.add_auto_shape(
                current,
                step,
                slide_index,
                preset_geometry,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
        return
    if add_kind == "connector":
        (
            slide_index,
            _shape_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        ) = args
        native.add_connector(
            current,
            step,
            slide_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
        )
        return
    if add_kind == "connected_connector":
        (
            slide_index,
            _shape_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
            begin_connection,
            end_connection,
        ) = args
        native.add_connected_connector(
            current,
            step,
            slide_index,
            preset_geometry,
            begin_x_emu,
            begin_y_emu,
            end_x_emu,
            end_y_emu,
            begin_connection,
            end_connection,
        )
        return
    if add_kind == "connected_connector_with_auto_shapes":
        (
            slide_index,
            _begin_shape_index,
            begin_preset_geometry,
            begin_x_emu,
            begin_y_emu,
            begin_cx_emu,
            begin_cy_emu,
            _end_shape_index,
            end_preset_geometry,
            end_x_emu,
            end_y_emu,
            end_cx_emu,
            end_cy_emu,
            _connector_shape_index,
            connector_preset_geometry,
            connector_begin_x_emu,
            connector_begin_y_emu,
            connector_end_x_emu,
            connector_end_y_emu,
            begin_cxn_pt_idx,
            end_cxn_pt_idx,
        ) = args
        native.add_connected_connector_with_auto_shapes(
            current,
            step,
            slide_index,
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
        return
    raise ValueError(f"unknown shape add kind: {add_kind}")
