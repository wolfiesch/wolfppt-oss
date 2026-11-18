"""Harness evidence and immutable results for callback-controlled deck loading/saving."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .presentation import Presentation


class WarningAction(Enum):
    """Explicit caller decision; missing callbacks abort rather than silently repair."""

    CONTINUE = "continue"
    ABORT = "abort"


class WarningCategory(StrEnum):
    """Typed diagnostic families shared by load, save and export operations."""

    PACKAGE_REPAIR = "package_repair"
    SECURITY = "security"
    OBSOLETE_OPTION = "obsolete_option"
    FONT_SUBSTITUTION = "font_substitution"
    UNSUPPORTED_FEATURE = "unsupported_feature"


@dataclass(frozen=True)
class LoadSaveWarning:
    """Stable code, phase, affected part and typed diagnostic category."""

    phase: str
    code: str
    message: str
    part: str | None = None
    category: WarningCategory = WarningCategory.UNSUPPORTED_FEATURE

    def row(self) -> dict[str, Any]:
        """JSON-compatible receipt diagnostic, without losing the typed API."""
        return {**asdict(self), "category": self.category.value}


class LoadSaveWarningRefusal(ValueError):
    """Unsupported input or caller abort; destination bytes have not been written."""

    def __init__(self, code: str, message: str, warnings: tuple[LoadSaveWarning, ...] = ()) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.warnings = warnings
        self.diagnostic = warnings[-1] if warnings else LoadSaveWarning("load_save", code, message)


def observe_warnings(
    warnings: list[LoadSaveWarning],
    callback: Callable[[LoadSaveWarning], WarningAction] | None,
    *,
    require_decision: bool = True,
) -> None:
    """Apply decisions before publication; observer exceptions propagate unchanged."""
    for index, warning in enumerate(warnings):
        observed = tuple(warnings[: index + 1])
        if callback is None and not require_decision:
            continue
        decision = WarningAction.ABORT if callback is None else callback(warning)
        if decision is WarningAction.ABORT:
            raise LoadSaveWarningRefusal("warning_aborted", warning.message, observed)
        if decision is not WarningAction.CONTINUE:
            raise LoadSaveWarningRefusal(
                "warning_decision_invalid", "callback must return a WarningAction", observed
            )


@dataclass(frozen=True)
class LoadSaveResult:
    """Owned presentation snapshot and warnings observed in operation order."""

    presentation: Presentation
    warnings: tuple[LoadSaveWarning, ...]


@dataclass(frozen=True)
class HarnessResult:
    fixture: str
    adapter: str
    operation: str
    status: str
    run_id: str | None = None
    semantic_score: float | None = None
    openxml_error_count: int | None = None
    package_diff_count: int | None = None
    render_score: float | None = None
    elapsed_ms: float | None = None
    rss_mb: float | None = None
    known_gap: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        data = asdict(self)
        if data["run_id"] is None:
            data["run_id"] = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return data


def append_result(result: HarnessResult, path: str | Path = "results/runs.jsonl") -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result.row(), sort_keys=True) + "\n")


def read_results(path: str | Path = "results/runs.jsonl") -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    rows: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
