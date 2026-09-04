"""Native binding wrappers split from wolfppt.native."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .native_binding import NATIVE_INSTALL_HINT
from .native_group_shape_additions import (
    add_deeper_nested_group_auto_shape_with_text,
    add_deeper_nested_group_freeform_shape_with_text,
    add_deeper_nested_group_text_box_with_text,
    add_group_auto_shape_with_text,
    add_group_freeform_shape_with_text,
    add_group_text_box_with_text,
    add_nested_group_auto_shape_in_new_group_with_text,
    add_nested_group_auto_shape_with_text,
    add_nested_group_freeform_shape_in_new_group_with_text,
    add_nested_group_freeform_shape_with_text,
    add_nested_group_text_box_in_new_group_with_text,
    add_nested_group_text_box_with_text,
)
from .native_shape_connectors import (
    add_connected_connector,
    add_connected_connector_with_auto_shapes,
    add_connected_group_connector,
    add_connected_group_connector_with_auto_shapes,
    add_connector,
    add_deeper_nested_group_connector,
    add_group_connector,
    add_nested_group_connector,
    add_nested_group_connector_in_new_group,
)
from .native_results import (
    NativeAutoShapeAddResult,
    NativeEditBatchResult,
    NativeFreeformShapeAddResult,
    NativePlaceholderShapeAddResult,
    NativePlaceholderShapeBatchAddResult,
    NativeSlideAddResult,
    NativeSlideDeleteResult,
    NativeTableAddResult,
    NativeTableCellReplacementResult,
    NativeTextBoxAddResult,
)


def add_slide(
    input_path: str | Path,
    output_path: str | Path,
    layout_index: int | None = None,
) -> NativeSlideAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    if layout_index is None:
        payload = json.loads(
            wolfppt_native.add_blank_slide_json(str(input_path), str(output_path))
        )
    else:
        payload = json.loads(
            wolfppt_native.add_blank_slide_with_layout_json(
                str(input_path),
                str(output_path),
                layout_index,
            )
        )
    return NativeSlideAddResult(
        path=payload["path"],
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        layout_target=payload["layout_target"],
        slide_id=int(payload["slide_id"]),
        slide_count=int(payload["slide_count"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )

def duplicate_slide(
    input_path: str | Path,
    output_path: str | Path,
    source_slide_part: str,
) -> NativeSlideAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.duplicate_slide_json(
            str(input_path),
            str(output_path),
            source_slide_part,
        )
    )
    return NativeSlideAddResult(
        path=payload["path"],
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        layout_target=payload["layout_target"],
        slide_id=int(payload["slide_id"]),
        slide_count=int(payload["slide_count"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )

def delete_slide(
    input_path: str | Path,
    output_path: str | Path,
    target_slide_part: str,
) -> NativeSlideDeleteResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.delete_slide_json(
            str(input_path),
            str(output_path),
            target_slide_part,
        )
    )
    return NativeSlideDeleteResult(
        path=payload["path"],
        deleted_slide_parts=list(payload["deleted_slide_parts"]),
        deleted_relationship_ids=list(payload["deleted_relationship_ids"]),
        survivor_count=int(payload["survivor_count"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def delete_slides(
    input_path: str | Path,
    output_path: str | Path,
    target_slide_parts: list[str],
    ordered_survivor_parts: list[str] | None = None,
) -> NativeSlideDeleteResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.delete_slides_json(
            str(input_path),
            str(output_path),
            [str(part) for part in target_slide_parts],
            [str(part) for part in ordered_survivor_parts]
            if ordered_survivor_parts is not None
            else None,
        )
    )
    return NativeSlideDeleteResult(
        path=payload["path"],
        deleted_slide_parts=list(payload["deleted_slide_parts"]),
        deleted_relationship_ids=list(payload["deleted_relationship_ids"]),
        survivor_count=int(payload["survivor_count"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def replace_table_cell(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    table_index: int,
    row_index: int,
    col_index: int,
    replacement: str,
) -> NativeTableCellReplacementResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.replace_table_cell_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            table_index,
            row_index,
            col_index,
            replacement,
        )
    )
    return NativeTableCellReplacementResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        table_index=int(payload["table_index"]),
        row_index=int(payload["row_index"]),
        col_index=int(payload["col_index"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_table(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    rows: int,
    cols: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> NativeTableAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_table_json(
            str(input_path),
            str(output_path),
            slide_index,
            rows,
            cols,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    )
    return NativeTableAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        table_index=int(payload["table_index"]),
        shape_id=int(payload["shape_id"]),
        rows=int(payload["rows"]),
        cols=int(payload["cols"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_table_with_cell_texts(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    rows: int,
    cols: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    cell_texts: list[tuple[int, int, str]],
) -> NativeTableAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_table_with_cell_texts_json(
            str(input_path),
            str(output_path),
            slide_index,
            rows,
            cols,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            json.dumps(cell_texts),
        )
    )
    return NativeTableAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        table_index=int(payload["table_index"]),
        shape_id=int(payload["shape_id"]),
        rows=int(payload["rows"]),
        cols=int(payload["cols"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_text_box(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> NativeTextBoxAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_text_box_json(
            str(input_path),
            str(output_path),
            slide_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    )
    return NativeTextBoxAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_text_box_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    text: str,
) -> NativeTextBoxAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_text_box_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
    )
    return NativeTextBoxAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_freeform_shape(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    path_w: int,
    path_h: int,
    operations: list[dict[str, Any]],
) -> NativeFreeformShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_freeform_shape_json(
            str(input_path),
            str(output_path),
            slide_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            json.dumps(operations),
        )
    )
    return NativeFreeformShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_freeform_shape_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    path_w: int,
    path_h: int,
    operations: list[dict[str, Any]],
    text: str,
) -> NativeFreeformShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_freeform_shape_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            path_w,
            path_h,
            json.dumps(operations),
            text,
        )
    )
    return NativeFreeformShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_placeholder_shape(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    placeholder_type: str | None,
    placeholder_orient: str | None,
    placeholder_size: str | None,
    placeholder_idx: str | None,
) -> NativePlaceholderShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_placeholder_shape_json(
            str(input_path),
            str(output_path),
            slide_index,
            placeholder_type,
            placeholder_orient,
            placeholder_size,
            placeholder_idx,
        )
    )
    return NativePlaceholderShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        placeholder_type=payload.get("placeholder_type"),
        placeholder_idx=payload.get("placeholder_idx"),
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_placeholder_shapes(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    placeholders: list[dict[str, str | None]],
) -> NativePlaceholderShapeBatchAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_placeholder_shapes_json(
            str(input_path),
            str(output_path),
            slide_index,
            json.dumps(placeholders),
        )
    )
    return NativePlaceholderShapeBatchAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_ids=[int(value) for value in payload["shape_ids"]],
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_layout_placeholders(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    layout_index: int,
) -> NativePlaceholderShapeBatchAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_layout_placeholders_json(
            str(input_path),
            str(output_path),
            slide_index,
            layout_index,
        )
    )
    return NativePlaceholderShapeBatchAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_ids=[int(value) for value in payload["shape_ids"]],
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_auto_shape(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    preset_geometry: str,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> NativeAutoShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_auto_shape_json(
            str(input_path),
            str(output_path),
            slide_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    )
    return NativeAutoShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_auto_shape_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    preset_geometry: str,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    text: str,
) -> NativeAutoShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_auto_shape_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
        )
    )
    return NativeAutoShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_auto_shape_with_options(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    preset_geometry: str,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    text: str | None,
    adjustment_guides: list[tuple[str, int]],
) -> NativeAutoShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_auto_shape_with_options_json(
            str(input_path),
            str(output_path),
            slide_index,
            preset_geometry,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            text,
            json.dumps(adjustment_guides),
        )
    )
    return NativeAutoShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        preset_geometry=payload["preset_geometry"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def apply_edit_batch(
    input_path: str | Path,
    output_path: str | Path,
    edits: list[dict[str, Any]],
) -> NativeEditBatchResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.apply_edit_batch_json(
            str(input_path),
            str(output_path),
            json.dumps(edits, separators=(",", ":")),
        )
    )
    return NativeEditBatchResult(
        path=payload["path"],
        edits=int(payload["edits"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )
