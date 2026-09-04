"""Chart fixture and shape lookup helpers for drop-in benchmarks."""

from __future__ import annotations

from typing import Any

from .benchmark_cases import CHART_READ_EXPECTED_METADATA
from .shape_core_facade import Shape

CHART_EDIT_FIXTURES = (
    *CHART_READ_EXPECTED_METADATA,
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)


def _first_chart_shape(prs: Any) -> Any:
    for slide in prs.slides:
        if not _slide_may_have_chart(slide):
            continue
        shell_shape = _first_shell_chart_shape(slide)
        if shell_shape is not None:
            return shell_shape
        for shape in slide.shapes:
            if getattr(shape, "has_chart", False):
                return shape
    raise RuntimeError("fixture does not contain a chart shape")


def _slide_may_have_chart(slide: Any) -> bool:
    payload = getattr(slide, "_payload", None)
    if not isinstance(payload, dict) or "has_chart_relationship" not in payload:
        return True
    return bool(payload["has_chart_relationship"])


def _first_shell_chart_shape(slide: Any) -> Any | None:
    payload = getattr(slide, "_payload", None)
    if not isinstance(payload, dict):
        return None
    hints = payload.get("chart_shape_hints")
    if not isinstance(hints, list):
        return None
    for hint in hints:
        if not isinstance(hint, dict) or not hint.get("has_chart"):
            continue
        return Shape(slide, int(hint.get("_shape_index", 0)), hint)
    return None
