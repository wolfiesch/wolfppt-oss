"""Benchmark data models and markdown reporting helpers."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from json import dumps as json_dumps
from pathlib import Path
from typing import Any, Callable


BenchmarkFn = Callable[[str, Path, Path, Path, bool], tuple[float, dict[str, Any]]]


@dataclass(frozen=True)
class BenchmarkAdapter:
    name: str
    operation: str
    role: str
    available: Callable[[], bool]
    run: BenchmarkFn
    unavailable_reason: Callable[[], str | None] | None = None


@dataclass(frozen=True)
class BenchmarkSample:
    iteration: int
    elapsed_ms: float
    rss_mb: float | None
    status: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkResult:
    fixture_id: str
    path: str
    adapter: str
    operation: str
    status: str
    samples: list[BenchmarkSample] = field(default_factory=list)
    skip_reason: str | None = None

    def latency_stats(self) -> dict[str, float | None]:
        values = [sample.elapsed_ms for sample in self.samples]
        if not values:
            return {
                "count": 0,
                "min": None,
                "median": None,
                "mean": None,
                "p95": None,
                "max": None,
                "stdev": None,
            }
        sorted_values = sorted(values)
        p95_index = max(0, math.ceil(len(sorted_values) * 0.95) - 1)
        return {
            "count": len(values),
            "min": round(min(values), 3),
            "median": round(statistics.median(values), 3),
            "mean": round(statistics.mean(values), 3),
            "p95": round(sorted_values[p95_index], 3),
            "max": round(max(values), 3),
            "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "path": self.path,
            "adapter": self.adapter,
            "operation": self.operation,
            "status": self.status,
            "skip_reason": self.skip_reason,
            "latency_ms": self.latency_stats(),
            "samples": [sample.to_dict() for sample in self.samples],
        }


@dataclass(frozen=True)
class BenchmarkRun:
    run_id: str
    iterations: int
    warmup: int
    validate_openxml: bool
    adapters: list[str]
    fixture_ids: list[str]
    tool_availability: list[dict[str, Any]]
    results: list[BenchmarkResult]
    required_adapters: list[str] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)
    elapsed_wall_ms: float | None = None

    @property
    def status(self) -> str:
        return "fail" if any(result.status == "fail" for result in self.results) else "pass"

    @property
    def status_counts(self) -> dict[str, int]:
        return _status_counts(self.results)

    @property
    def validation_cache_stats(self) -> dict[str, int]:
        return validation_cache_stats(self.results)

    @property
    def failed_results(self) -> list[dict[str, Any]]:
        return failed_result_rows(self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "status_counts": self.status_counts,
            "elapsed_wall_ms": None
            if self.elapsed_wall_ms is None
            else round(self.elapsed_wall_ms, 3),
            "validation_cache": self.validation_cache_stats,
            "iterations": self.iterations,
            "warmup": self.warmup,
            "validate_openxml": self.validate_openxml,
            "adapters": self.adapters,
            "required_adapters": self.required_adapters,
            "environment": self.environment,
            "fixture_ids": self.fixture_ids,
            "tool_availability": self.tool_availability,
            "failed_results": self.failed_results,
            "results": [result.to_dict() for result in self.results],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# WolfPPT Benchmark Run {self.run_id}",
            "",
            f"Status: **{self.status}**",
            "",
            "## Configuration",
            "",
            "| setting | value |",
            "|---|---:|",
            f"| measured iterations | {self.iterations} |",
            f"| warmup iterations | {self.warmup} |",
            f"| Open XML validation | {self.validate_openxml} |",
            f"| fixtures | {len(self.fixture_ids)} |",
            f"| adapters | {len(self.adapters)} |",
            f"| required adapters | {', '.join(self.required_adapters) if self.required_adapters else 'none'} |",
            f"| git HEAD | {_git_summary(self.environment)} |",
            f"| native binding | {_native_summary(self.environment)} |",
            f"| elapsed wall time | {_fmt(self.elapsed_wall_ms)} ms |",
            f"| passing results | {self.status_counts['pass']} |",
            f"| skipped results | {self.status_counts['skip']} |",
            f"| failing results | {self.status_counts['fail']} |",
        ]
        cache_stats = self.validation_cache_stats
        if cache_stats["samples"]:
            lines.extend(
                [
                    f"| Open XML validation samples | {cache_stats['samples']} |",
                    f"| Open XML validation cache hits | {cache_stats['hits']} |",
                    f"| Open XML validation cache misses | {cache_stats['misses']} |",
                ]
            )
        lines.extend(
            [
                "",
                "## Adapter Summary",
                "",
                "| adapter | operation | results | pass | skip | fail | median ms | p95 ms | semantic pass | package clean | Open XML valid | Open XML accepted | source-invalid preserved |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in _adapter_summary(self.results):
            lines.append(
                "| {adapter} | {operation} | {results} | {pass_count} | {skip_count} | {fail_count} | "
                "{median_ms} | {p95_ms} | "
                "{semantic_pass} | {package_clean} | {openxml_valid} | "
                "{openxml_accepted} | {source_invalid_preserved} |".format(**row)
            )
        lines.extend(
            [
                "",
                "## Fixture Results",
                "",
                "| fixture | adapter | status | samples | median ms | mean ms | p95 ms |",
                "|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for result in self.results:
            stats = result.latency_stats()
            lines.append(
                f"| `{result.fixture_id}` | {result.adapter} | {result.status} | "
                f"{stats['count']} | {_fmt(stats['median'])} | {_fmt(stats['mean'])} | {_fmt(stats['p95'])} |"
            )
        skipped = _skipped_summary(self.results)
        if skipped:
            lines.extend(
                [
                    "",
                    "## Skipped Adapters",
                    "",
                    "| adapter | operation | count | reason |",
                    "|---|---|---:|---|",
                ]
            )
            for row in skipped:
                lines.append(
                    "| {adapter} | {operation} | {count} | {reason} |".format(**row)
                )
        failed = self.failed_results
        if failed:
            lines.extend(
                [
                    "",
                    "## Failed Results",
                    "",
                    "| fixture | adapter | operation | failed samples | reason | details |",
                    "|---|---|---|---:|---|---|",
                ]
            )
            for row in failed:
                lines.append(
                    f"| `{row['fixture_id']}` | {row['adapter']} | "
                    f"{row['operation']} | {row['failed_samples']} | "
                    f"{_markdown_cell(row['reason'])} | "
                    f"{_markdown_cell(format_failure_preview(row['detail_preview']))} |"
                )
        lines.extend(["", "## Tools", "", "| tool | available | role |", "|---|---:|---|"])
        for tool in self.tool_availability:
            lines.append(f"| {tool['name']} | {tool['available']} | {tool['role']} |")
        lines.extend(
            [
                "",
                "Note: timings measure the candidate adapter call only. Semantic diffs, package diffs, and optional Open XML validation run after timing so correctness checks do not inflate latency.",
            ]
        )
        return "\n".join(lines) + "\n"


def _adapter_summary(results: list[BenchmarkResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[BenchmarkResult]] = defaultdict(list)
    for result in results:
        grouped[(result.adapter, result.operation)].append(result)

    rows: list[dict[str, Any]] = []
    for (adapter, operation), group in sorted(grouped.items()):
        samples = [sample for result in group for sample in result.samples]
        values = [sample.elapsed_ms for sample in samples]
        statuses = _status_counts(group)
        rows.append(
            {
                "adapter": adapter,
                "operation": operation,
                "results": len(group),
                "pass_count": statuses["pass"],
                "skip_count": statuses["skip"],
                "fail_count": statuses["fail"],
                "median_ms": _fmt(statistics.median(values) if values else None),
                "p95_ms": _fmt(_p95(values) if values else None),
                "semantic_pass": _ratio(samples, "semantic_pass"),
                "package_clean": _ratio(samples, "package_clean"),
                "openxml_valid": _ratio(samples, "openxml_valid"),
                "openxml_accepted": _ratio(samples, "openxml_validation_accepted"),
                "source_invalid_preserved": _ratio(samples, "openxml_source_invalid_preserved"),
            }
        )
    return rows


def _status_counts(results: list[BenchmarkResult]) -> dict[str, int]:
    return {
        "pass": sum(1 for result in results if result.status == "pass"),
        "skip": sum(1 for result in results if result.status == "skip"),
        "fail": sum(1 for result in results if result.status == "fail"),
    }


def validation_cache_stats(results: list[BenchmarkResult]) -> dict[str, int]:
    values = [
        sample.details.get("openxml_validation", {}).get("cache_hit")
        for result in results
        for sample in result.samples
        if isinstance(sample.details.get("openxml_validation"), dict)
        and sample.details["openxml_validation"].get("cache_hit") is not None
    ]
    return {
        "samples": len(values),
        "hits": sum(1 for value in values if value is True),
        "misses": sum(1 for value in values if value is False),
    }


def failed_result_rows(results: list[BenchmarkResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if result.status != "fail":
            continue
        failed_samples = [sample for sample in result.samples if sample.status == "fail"]
        rows.append(
            {
                "fixture_id": result.fixture_id,
                "adapter": result.adapter,
                "operation": result.operation,
                "failed_samples": len(failed_samples),
                "reason": _failure_reason(result),
                "detail_preview": _failure_detail_preview(result),
            }
        )
    return rows


def _skipped_summary(results: list[BenchmarkResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], int] = defaultdict(int)
    for result in results:
        if result.status != "skip":
            continue
        reason = result.skip_reason or "adapter unavailable"
        grouped[(result.adapter, result.operation, reason)] += 1
    return [
        {
            "adapter": adapter,
            "operation": operation,
            "reason": reason,
            "count": count,
        }
        for (adapter, operation, reason), count in sorted(grouped.items())
    ]


def _failure_reason(result: BenchmarkResult) -> str:
    for sample in result.samples:
        if sample.status != "fail":
            continue
        details = sample.details
        openxml = details.get("openxml_validation")
        if isinstance(openxml, dict) and openxml.get("valid") is False:
            errors = openxml.get("errors")
            if isinstance(errors, list) and errors:
                first_error = errors[0]
                if isinstance(first_error, dict):
                    part = first_error.get("part")
                    description = first_error.get("description")
                    if part and description:
                        return _truncate(f"Open XML {part}: {description}")
                    if description:
                        return _truncate(f"Open XML: {description}")
            error_count = openxml.get("error_count")
            if error_count is not None:
                return f"Open XML validation failed with {error_count} errors"
            return "Open XML validation failed"
        if details.get("semantic_pass") is False:
            mismatch_count = details.get("mismatch_count")
            if mismatch_count is not None:
                return f"semantic diff failed with {mismatch_count} mismatches"
            return "semantic diff failed"
        if details.get("package_clean") is False:
            added = details.get("package_added_count", 0)
            changed = details.get("package_changed_count", 0)
            removed = details.get("package_removed_count", 0)
            return f"package diff changed: +{added} ~{changed} -{removed}"
        if details.get("ok") is False:
            return "benchmark validation failed"
    return result.skip_reason or "benchmark failed"


def _failure_detail_preview(result: BenchmarkResult) -> list[str]:
    for sample in result.samples:
        if sample.status != "fail":
            continue
        details = sample.details
        mismatches = details.get("semantic_mismatches")
        if isinstance(mismatches, list) and mismatches:
            preview = [
                _format_mismatch_preview(mismatch)
                for mismatch in mismatches
                if isinstance(mismatch, dict)
            ]
            if details.get("semantic_mismatch_preview_truncated"):
                preview.append("additional semantic mismatches omitted")
            return preview
        if details.get("package_clean") is False:
            return [
                "package parts +{added} ~{changed} -{removed}".format(
                    added=details.get("package_added_count", 0),
                    changed=details.get("package_changed_count", 0),
                    removed=details.get("package_removed_count", 0),
                )
            ]
    return []


def _format_mismatch_preview(mismatch: dict[str, Any]) -> str:
    path = mismatch.get("path", "<unknown>")
    expected = _compact_value(mismatch.get("expected"))
    actual = _compact_value(mismatch.get("actual"))
    return f"{path}: expected {expected}, actual {actual}"


def format_failure_preview(preview: list[str]) -> str:
    if not preview:
        return "n/a"
    return "; ".join(preview)


def _compact_value(value: Any, *, limit: int = 80) -> str:
    try:
        rendered = json_dumps(value, ensure_ascii=True, sort_keys=True)
    except TypeError:
        rendered = repr(value)
    return _truncate(rendered, limit=limit)


def _ratio(samples: list[BenchmarkSample], key: str) -> str:
    values = [
        sample.details.get(key)
        for sample in samples
        if sample.details.get(key) is not None
    ]
    if not values:
        return "n/a"
    passed = sum(1 for value in values if value is True)
    return f"{passed}/{len(values)}"


def _p95(values: list[float]) -> float:
    sorted_values = sorted(values)
    return sorted_values[max(0, math.ceil(len(sorted_values) * 0.95) - 1)]


def _fmt(value: float | int | None) -> str:
    return "n/a" if value is None else f"{float(value):.3f}"


def _markdown_cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def _truncate(value: str, *, limit: int = 240) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _native_summary(environment: dict[str, Any]) -> str:
    native = environment.get("native_binding")
    if not isinstance(native, dict):
        return "unknown"
    if not native.get("installed"):
        return "not installed"
    profile = native.get("build_profile") or "unknown"
    version = native.get("version") or "unknown"
    return f"{profile} ({version})"


def _git_summary(environment: dict[str, Any]) -> str:
    git = environment.get("git")
    if not isinstance(git, dict) or not git.get("available"):
        return "unknown"
    short_head = git.get("short_head") or "unknown"
    suffix = " dirty" if git.get("dirty") else ""
    return f"{short_head}{suffix}"
