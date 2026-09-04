"""Native binding wrappers split from wolfppt.native."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import (
    NativeParagraphTextSetResult,
    NativeShapeTextSetResult,
    NativeTextReplacementResult,
    NativeTextRunReplacementResult,
)


def replace_text(
    input_path: str | Path,
    output_path: str | Path,
    search: str,
    replacement: str,
    slide_index: int | None = None,
) -> NativeTextReplacementResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    if slide_index is None:
        payload = json.loads(
            wolfppt_native.replace_slide_text_json(str(input_path), str(output_path), search, replacement)
        )
    else:
        payload = json.loads(
            wolfppt_native.replace_slide_text_at_index_json(
                str(input_path),
                str(output_path),
                slide_index,
                search,
                replacement,
            )
        )
    return NativeTextReplacementResult(
        path=payload["path"],
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def replace_text_run(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    run_index: int,
    replacement: str,
) -> NativeTextRunReplacementResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.replace_slide_text_run_at_index_json(
            str(input_path),
            str(output_path),
            slide_index,
            run_index,
            replacement,
        )
    )
    return NativeTextRunReplacementResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        run_index=int(payload["run_index"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def set_shape_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    shape_index: int,
    replacement: str,
) -> NativeShapeTextSetResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.set_slide_shape_text_at_index_json(
            str(input_path),
            str(output_path),
            slide_index,
            shape_index,
            replacement,
        )
    )
    return NativeShapeTextSetResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        shape_index=int(payload["shape_index"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def set_paragraph_text(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    shape_index: int,
    paragraph_index: int,
    replacement: str,
) -> NativeParagraphTextSetResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.set_slide_shape_paragraph_text_at_index_json(
            str(input_path),
            str(output_path),
            slide_index,
            shape_index,
            paragraph_index,
            replacement,
        )
    )
    return NativeParagraphTextSetResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        shape_index=int(payload["shape_index"]),
        paragraph_index=int(payload["paragraph_index"]),
        replacements=int(payload["replacements"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )
