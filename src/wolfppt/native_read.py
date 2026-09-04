"""Native binding wrappers split from wolfppt.native."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import (
    NativeInspectResult,
    NativePresentationSummary,
)


def inspect(path: str | Path) -> NativeInspectResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(wolfppt_native.inspect_package_json(str(path)))
    parts = list(payload["parts"])
    return NativeInspectResult(
        path=payload["path"],
        part_count=len(parts),
        has_vba=any(part["kind"] == "vba" for part in parts),
        parts=parts,
    )


def summarize(path: str | Path) -> NativePresentationSummary:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(wolfppt_native.summarize_presentation_json(str(path)))
    return NativePresentationSummary(
        path=payload["path"],
        slide_count=int(payload["slide_count"]),
        has_vba=bool(payload["has_vba"]),
        slides=list(payload["slides"]),
    )


def summarize_slide(path: str | Path, slide_index: int) -> dict[str, Any]:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    return dict(
        json.loads(wolfppt_native.summarize_slide_at_index_json(str(path), slide_index))
    )


def roundtrip(input_path: str | Path, output_path: str | Path) -> NativeInspectResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(wolfppt_native.roundtrip_package_json(str(input_path), str(output_path)))
    parts = list(payload["parts"])
    return NativeInspectResult(
        path=payload["path"],
        part_count=len(parts),
        has_vba=any(part["kind"] == "vba" for part in parts),
        parts=parts,
    )
