"""Append-only result evidence for benchmark and parity runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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

