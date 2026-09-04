"""Row helpers for benchmark profile reports."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .benchmark_models import (
    BenchmarkResult,
    BenchmarkSample,
    failed_result_rows,
)

SPEEDUP_GATE_IMMATERIAL_SLOWDOWN_MS = 0.1


def _adapter_summary(results: list[BenchmarkResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[BenchmarkResult]] = defaultdict(list)
    for result in results:
        grouped[(result.adapter, result.operation)].append(result)

    rows: list[dict[str, Any]] = []
    for (adapter, operation), group in sorted(grouped.items()):
        samples = [sample for result in group for sample in result.samples]
        values = [sample.elapsed_ms for sample in samples]
        statuses = [result.status for result in group]
        rows.append(
            {
                "adapter": adapter,
                "operation": operation,
                "results": len(group),
                "median_ms": _fmt(_median(values)),
                "p95_ms": _fmt(_p95(values)),
                "pass_count": statuses.count("pass"),
                "skip_count": statuses.count("skip"),
                "fail_count": statuses.count("fail"),
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


def _skipped_result_rows(results: list[BenchmarkResult]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], int] = defaultdict(int)
    for result in results:
        if result.status != "skip":
            continue
        reason = result.skip_reason or "skipped"
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


def _failed_result_rows(batch_runs: tuple[Any, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch_run in batch_runs:
        rows.extend(
            {"batch": batch_run.batch.name, **row}
            for row in failed_result_rows(batch_run.run.results)
        )
    return rows


def _speedup_rows(batch_runs: tuple[Any, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch_run in batch_runs:
        by_fixture_adapter = {
            (result.fixture_id, result.adapter): result for result in batch_run.run.results
        }
        for result in batch_run.run.results:
            if not result.adapter.startswith("python-pptx-") or result.status != "pass":
                continue
            wolf_adapter = f"wolfppt-facade-{result.adapter.removeprefix('python-pptx-')}"
            wolf_result = by_fixture_adapter.get((result.fixture_id, wolf_adapter))
            if wolf_result is None or wolf_result.status != "pass":
                continue
            python_median = result.latency_stats()["median"]
            wolf_median = wolf_result.latency_stats()["median"]
            if python_median is None or wolf_median in (None, 0):
                continue
            rows.append(
                {
                    "batch": batch_run.batch.name,
                    "fixture_id": result.fixture_id,
                    "operation": result.operation,
                    "python_pptx_adapter": result.adapter,
                    "wolfppt_adapter": wolf_result.adapter,
                    "python_pptx_median_ms": python_median,
                    "wolfppt_median_ms": wolf_median,
                    "wolfppt_slower_by_ms": round(
                        float(wolf_median) - float(python_median), 3
                    ),
                    "wolfppt_speedup": round(float(python_median) / float(wolf_median), 3),
                }
            )
    return rows


def _sdk_speedup_rows(
    batch_runs: tuple[Any, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch_run in batch_runs:
        by_fixture_operation_adapter = {
            (result.fixture_id, result.operation, result.adapter): result
            for result in batch_run.run.results
        }
        for result in batch_run.run.results:
            if result.adapter == "native-rust-roundtrip" or result.status != "pass":
                continue
            native_result = by_fixture_operation_adapter.get(
                (result.fixture_id, result.operation, "native-rust-roundtrip")
            )
            if native_result is None or native_result.status != "pass":
                continue
            baseline_median = result.latency_stats()["median"]
            native_median = native_result.latency_stats()["median"]
            if baseline_median is None or native_median in (None, 0):
                continue
            rows.append(
                {
                    "batch": batch_run.batch.name,
                    "fixture_id": result.fixture_id,
                    "operation": result.operation,
                    "baseline_adapter": result.adapter,
                    "baseline_sdk_versions": _sdk_versions(result),
                    "wolfppt_adapter": native_result.adapter,
                    "baseline_median_ms": baseline_median,
                    "wolfppt_median_ms": native_median,
                    "wolfppt_speedup": round(
                        float(baseline_median) / float(native_median), 3
                    ),
                    "baseline_package_changed_count": _package_changed_count(result),
                    "wolfppt_package_changed_count": _package_changed_count(native_result),
                }
            )
    return rows


def _sdk_preservation_rows(
    speedup_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in speedup_rows:
        baseline_changed = row.get("baseline_package_changed_count")
        wolfppt_changed = row.get("wolfppt_package_changed_count")
        if not isinstance(baseline_changed, int) or not isinstance(wolfppt_changed, int):
            continue
        rows.append(
            {
                "batch": row["batch"],
                "fixture_id": row["fixture_id"],
                "operation": row["operation"],
                "baseline_adapter": row["baseline_adapter"],
                "wolfppt_adapter": row["wolfppt_adapter"],
                "baseline_package_changed_count": baseline_changed,
                "wolfppt_package_changed_count": wolfppt_changed,
                "wolfppt_fewer_changed_parts": max(
                    0,
                    baseline_changed - wolfppt_changed,
                ),
            }
        )
    return rows


def _sdk_failed_preservation_rows(
    batch_runs: tuple[Any, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch_run in batch_runs:
        by_fixture_operation_adapter = {
            (result.fixture_id, result.operation, result.adapter): result
            for result in batch_run.run.results
        }
        for result in batch_run.run.results:
            if result.adapter == "native-rust-roundtrip" or result.status != "fail":
                continue
            if not result.adapter.endswith("-roundtrip"):
                continue
            native_result = by_fixture_operation_adapter.get(
                (result.fixture_id, result.operation, "native-rust-roundtrip")
            )
            if native_result is None or native_result.status != "pass":
                continue
            rows.append(
                {
                    "batch": batch_run.batch.name,
                    "fixture_id": result.fixture_id,
                    "operation": result.operation,
                    "baseline_adapter": result.adapter,
                    "wolfppt_adapter": native_result.adapter,
                    "reason": _result_failure_reason(result),
                    "baseline_mismatch_count": _mismatch_count(result),
                    "baseline_package_changed_count": _package_changed_count(result),
                    "baseline_openxml_accepted": _ratio(
                        result.samples,
                        "openxml_validation_accepted",
                    ),
                    "wolfppt_package_changed_count": _package_changed_count(native_result),
                }
            )
    return rows


def _result_failure_reason(result: BenchmarkResult) -> str:
    rows = failed_result_rows([result])
    if not rows:
        return "benchmark failed"
    return str(rows[0]["reason"])


def _mismatch_count(result: BenchmarkResult) -> int | None:
    counts = [
        sample.details.get("mismatch_count")
        for sample in result.samples
        if isinstance(sample.details.get("mismatch_count"), int)
    ]
    return max(counts) if counts else None


def _speedup_row_fails_gate(row: dict[str, Any], min_speedup: float) -> bool:
    speedup = float(row["wolfppt_speedup"])
    if speedup >= min_speedup:
        return False
    return not _speedup_row_is_near_miss(row, min_speedup)


def _speedup_row_is_near_miss(row: dict[str, Any], min_speedup: float) -> bool:
    if min_speedup > 1.0:
        return False
    speedup = float(row["wolfppt_speedup"])
    slower_by_ms = float(row["wolfppt_slower_by_ms"])
    return 0.0 < slower_by_ms <= SPEEDUP_GATE_IMMATERIAL_SLOWDOWN_MS and speedup < min_speedup


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    mid = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    return sorted_values[max(0, math.ceil(len(sorted_values) * 0.95) - 1)]


def _package_changed_count(result: BenchmarkResult) -> int | None:
    counts = [
        sample.details.get("package_changed_count")
        for sample in result.samples
        if isinstance(sample.details.get("package_changed_count"), int)
    ]
    return max(counts) if counts else None


def _sdk_versions(result: BenchmarkResult) -> dict[str, str] | None:
    for sample in result.samples:
        sdk_versions = sample.details.get("sdk_versions")
        if not isinstance(sdk_versions, dict):
            continue
        cleaned = {
            str(name): str(version)
            for name, version in sdk_versions.items()
            if name and version
        }
        if cleaned:
            return cleaned
    return None


def _sdk_versions_label(sdk_versions: dict[str, str] | None) -> str:
    if not sdk_versions:
        return "n/a"
    return ", ".join(
        f"{name} {version}" for name, version in sorted(sdk_versions.items())
    )


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


def _fmt(value: float | int | None) -> str:
    return "n/a" if value is None else f"{float(value):.3f}"


def _fmt_count(value: int | None) -> str:
    return "n/a" if value is None else str(value)


def _markdown_cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


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
