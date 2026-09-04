"""Semantic comparison helpers for extracted PPTX facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SemanticMismatch:
    path: str
    expected: Any
    actual: Any


@dataclass
class SemanticComparison:
    fixture_id: str
    mismatches: list[SemanticMismatch] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.mismatches

    @property
    def score(self) -> float:
        if not self.mismatches:
            return 1.0
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "passed": self.passed,
            "score": self.score,
            "mismatches": [asdict(mismatch) for mismatch in self.mismatches],
        }


def compare_semantics(
    fixture_id: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    ignore_paths: set[str] | None = None,
) -> SemanticComparison:
    """Compare two semantic oracle dictionaries.

    The extractor includes file paths and full package manifests, which can
    legitimately differ across round-trip outputs. Callers can ignore those
    paths while keeping slide, shape, text, table, notes, relationship, and VBA
    facts strict.
    """

    comparison = SemanticComparison(fixture_id=fixture_id)
    ignored = ignore_paths or set()
    _compare_value("$", expected, actual, comparison, ignored)
    return comparison


def semantic_mismatch_preview(
    comparison: SemanticComparison, *, limit: int = 3
) -> list[dict[str, Any]]:
    """Return a bounded, serializable preview of semantic mismatches."""

    return [asdict(mismatch) for mismatch in comparison.mismatches[:limit]]


DEFAULT_ROUNDTRIP_IGNORES = {
    "$.path",
    "$.part_count",
    "$.parts",
}


def _compare_value(
    path: str,
    expected: Any,
    actual: Any,
    comparison: SemanticComparison,
    ignored: set[str],
) -> None:
    if path in ignored:
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            _compare_value(
                f"{path}.{key}",
                expected.get(key, _Missing),
                actual.get(key, _Missing),
                comparison,
                ignored,
            )
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            comparison.mismatches.append(SemanticMismatch(f"{path}.length", len(expected), len(actual)))
            return
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=True)):
            _compare_value(f"{path}[{index}]", expected_item, actual_item, comparison, ignored)
        return
    if expected != actual:
        comparison.mismatches.append(SemanticMismatch(path, _display(expected), _display(actual)))


class _MissingValue:
    pass


_Missing = _MissingValue()


def _display(value: Any) -> Any:
    if value is _Missing:
        return "<missing>"
    return value
