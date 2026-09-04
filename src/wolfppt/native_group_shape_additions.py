"""Native binding wrappers for adding shapes inside groups."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import (
    NativeAutoShapeAddResult,
    NativeFreeformShapeAddResult,
    NativeTextBoxAddResult,
)


def add_group_text_box_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
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
        wolfppt_native.add_slide_group_text_box_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
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


def add_nested_group_text_box_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
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
        wolfppt_native.add_slide_nested_group_text_box_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
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


def add_deeper_nested_group_text_box_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
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
        wolfppt_native.add_slide_deeper_nested_group_text_box_with_text_json(
            str(input_path),
            str(output_path),
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
    )
    return NativeTextBoxAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_nested_group_text_box_in_new_group_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
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
        wolfppt_native.add_slide_nested_group_text_box_in_new_group_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
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


def add_group_auto_shape_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
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
        wolfppt_native.add_slide_group_auto_shape_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
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


def add_nested_group_auto_shape_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
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
        wolfppt_native.add_slide_nested_group_auto_shape_with_text_json(
            str(input_path),
            str(output_path),
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


def add_deeper_nested_group_auto_shape_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
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
        wolfppt_native.add_slide_deeper_nested_group_auto_shape_with_text_json(
            str(input_path),
            str(output_path),
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


def add_nested_group_auto_shape_in_new_group_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
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
        wolfppt_native.add_slide_nested_group_auto_shape_in_new_group_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
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


def add_group_freeform_shape_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
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
        wolfppt_native.add_slide_group_freeform_shape_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
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


def add_nested_group_freeform_shape_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
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
        wolfppt_native.add_slide_nested_group_freeform_shape_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
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


def add_deeper_nested_group_freeform_shape_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
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
        wolfppt_native.add_slide_deeper_nested_group_freeform_shape_with_text_json(
            str(input_path),
            str(output_path),
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


def add_nested_group_freeform_shape_in_new_group_with_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
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
        wolfppt_native.add_slide_nested_group_freeform_shape_in_new_group_with_text_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
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
