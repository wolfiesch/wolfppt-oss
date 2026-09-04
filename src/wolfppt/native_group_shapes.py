"""Native binding wrappers for grouped-shape operations."""

from __future__ import annotations

import json
from pathlib import Path

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import NativeGroupShapeAddResult


def add_group_shape(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
) -> NativeGroupShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_group_shape_json(
            str(input_path),
            str(output_path),
            slide_index,
        )
    )
    return NativeGroupShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_nested_group_shape(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
) -> NativeGroupShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_nested_group_shape_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
        )
    )
    return NativeGroupShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_group_shape_to_nested_group(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
) -> NativeGroupShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_group_shape_to_nested_group_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
        )
    )
    return NativeGroupShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_group_shape_to_deeper_nested_group(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
) -> NativeGroupShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_group_shape_to_deeper_nested_group_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
        )
    )
    return NativeGroupShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def group_existing_group_children(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    child_indices: tuple[int, ...],
) -> NativeGroupShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.group_slide_existing_group_children_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            list(child_indices),
        )
    )
    return NativeGroupShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def group_existing_nested_group_children(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    child_indices: tuple[int, ...],
) -> NativeGroupShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.group_slide_existing_nested_group_children_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            list(child_indices),
        )
    )
    return NativeGroupShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def group_existing_deeper_nested_group_children(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
    child_indices: tuple[int, ...],
) -> NativeGroupShapeAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.group_slide_existing_deeper_nested_group_children_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            list(child_indices),
        )
    )
    return NativeGroupShapeAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )
