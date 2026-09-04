"""Benchmark profile data models and report helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .benchmark_profile_inventory_report import (
    fixture_gate_observed as _fixture_gate_observed,
    fixture_inventory_markdown as _fixture_inventory_markdown,
    private_inventory_markdown as _private_inventory_markdown,
)
from .benchmark_models import (
    BenchmarkResult,
    BenchmarkRun,
    format_failure_preview,
    validation_cache_stats,
)
from .benchmark_profile_rows import (
    SPEEDUP_GATE_IMMATERIAL_SLOWDOWN_MS,
    _adapter_summary,
    _failed_result_rows,
    _fmt,
    _fmt_count,
    _git_summary,
    _markdown_cell,
    _native_summary,
    _sdk_failed_preservation_rows,
    _sdk_preservation_rows,
    _sdk_versions_label,
    _sdk_speedup_rows,
    _skipped_result_rows,
    _speedup_row_fails_gate,
    _speedup_row_is_near_miss,
    _speedup_rows,
    _status_counts,
)


@dataclass(frozen=True)
class BenchmarkProfileBatch:
    name: str
    description: str
    adapter_names: tuple[str, ...]
    fixture_ids: tuple[str, ...] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "adapter_names": list(self.adapter_names),
            "fixture_ids": list(self.fixture_ids) if self.fixture_ids is not None else "all",
        }


@dataclass(frozen=True)
class BenchmarkProfile:
    name: str
    description: str
    batches: tuple[BenchmarkProfileBatch, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "batches": [batch.to_dict() for batch in self.batches],
        }


@dataclass(frozen=True)
class BenchmarkProfileBatchRun:
    batch: BenchmarkProfileBatch
    run: BenchmarkRun

    @property
    def status(self) -> str:
        return self.run.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch": self.batch.to_dict(),
            "status": self.status,
            "run": self.run.to_dict(),
        }


@dataclass(frozen=True)
class BenchmarkProfileRun:
    run_id: str
    profile: BenchmarkProfile
    iterations: int
    warmup: int
    validate_openxml: bool
    batch_runs: tuple[BenchmarkProfileBatchRun, ...]
    min_wolfppt_speedup: float | None = None
    min_native_roundtrip_speedup: float | None = None
    min_openxml_samples: int | None = None
    min_source_invalid_preserved_samples: int | None = None
    min_distinct_fixtures: int | None = None
    min_sdk_preservation_rows: int | None = None
    fixture_inventory: dict[str, Any] | None = None
    fixture_gates: dict[str, int] | None = None
    private_inventory: dict[str, Any] | None = None
    private_gates: dict[str, int] | None = None
    fail_fast: bool = False
    stopped_early: bool = False
    elapsed_wall_ms: float | None = None

    @property
    def status(self) -> str:
        if any(batch_run.status == "fail" for batch_run in self.batch_runs):
            return "fail"
        if self.speedup_failures:
            return "fail"
        if self.native_roundtrip_speedup_failures:
            return "fail"
        if self.validation_sample_failures:
            return "fail"
        if self.source_invalid_preservation_failures:
            return "fail"
        if self.fixture_coverage_failures:
            return "fail"
        if self.fixture_complexity_failures:
            return "fail"
        if self.sdk_preservation_row_failures:
            return "fail"
        return "pass"

    @property
    def results(self) -> list[BenchmarkResult]:
        return [result for batch_run in self.batch_runs for result in batch_run.run.results]

    @property
    def status_counts(self) -> dict[str, int]:
        return _status_counts(self.results)

    @property
    def validation_cache_stats(self) -> dict[str, int]:
        return validation_cache_stats(self.results)

    @property
    def distinct_fixture_count(self) -> int:
        return len({result.fixture_id for result in self.results})

    @property
    def speedups(self) -> list[dict[str, Any]]:
        return _speedup_rows(self.batch_runs)

    @property
    def sdk_speedups(self) -> list[dict[str, Any]]:
        return _sdk_speedup_rows(self.batch_runs)

    @property
    def sdk_preservation(self) -> list[dict[str, Any]]:
        return _sdk_preservation_rows(self.sdk_speedups)

    @property
    def sdk_failed_preservation(self) -> list[dict[str, Any]]:
        return _sdk_failed_preservation_rows(self.batch_runs)

    @property
    def skipped_results(self) -> list[dict[str, Any]]:
        return _skipped_result_rows(self.results)

    @property
    def failed_results(self) -> list[dict[str, Any]]:
        return _failed_result_rows(self.batch_runs)

    @property
    def environment(self) -> dict[str, Any]:
        if not self.batch_runs:
            return {}
        return self.batch_runs[0].run.environment

    @property
    def speedup_failures(self) -> list[dict[str, Any]]:
        if self.min_wolfppt_speedup is None:
            return []
        return [
            {
                **row,
                "required_min_speedup": self.min_wolfppt_speedup,
            }
            for row in self.speedups
            if _speedup_row_fails_gate(row, self.min_wolfppt_speedup)
        ]

    @property
    def speedup_near_misses(self) -> list[dict[str, Any]]:
        if self.min_wolfppt_speedup is None:
            return []
        return [
            {
                **row,
                "required_min_speedup": self.min_wolfppt_speedup,
                "tolerance_ms": SPEEDUP_GATE_IMMATERIAL_SLOWDOWN_MS,
            }
            for row in self.speedups
            if _speedup_row_is_near_miss(row, self.min_wolfppt_speedup)
        ]

    @property
    def native_roundtrip_speedup_failures(self) -> list[dict[str, Any]]:
        if self.min_native_roundtrip_speedup is None:
            return []
        rows = self.sdk_speedups
        if not rows:
            return [
                {
                    "reason": "no measured native round-trip speedup rows",
                    "required_min_speedup": self.min_native_roundtrip_speedup,
                }
            ]
        return [
            {
                **row,
                "required_min_speedup": self.min_native_roundtrip_speedup,
            }
            for row in rows
            if float(row["wolfppt_speedup"]) < self.min_native_roundtrip_speedup
        ]

    @property
    def validation_sample_failures(self) -> list[dict[str, int]]:
        if self.min_openxml_samples is None:
            return []
        observed = self.validation_cache_stats["samples"]
        if observed >= self.min_openxml_samples:
            return []
        return [
            {
                "observed_openxml_samples": observed,
                "required_min_openxml_samples": self.min_openxml_samples,
            }
        ]

    @property
    def source_invalid_preserved_sample_count(self) -> int:
        return sum(
            1
            for result in self.results
            for sample in result.samples
            if sample.details.get("openxml_source_invalid_preserved") is True
        )

    @property
    def source_invalid_preservation_failures(self) -> list[dict[str, int]]:
        if self.min_source_invalid_preserved_samples is None:
            return []
        observed = self.source_invalid_preserved_sample_count
        if observed >= self.min_source_invalid_preserved_samples:
            return []
        return [
            {
                "observed_source_invalid_preserved_samples": observed,
                "required_min_source_invalid_preserved_samples": (
                    self.min_source_invalid_preserved_samples
                ),
            }
        ]

    @property
    def sdk_preservation_row_failures(self) -> list[dict[str, int]]:
        if self.min_sdk_preservation_rows is None:
            return []
        observed = len(self.sdk_preservation)
        if observed >= self.min_sdk_preservation_rows:
            return []
        return [
            {
                "observed_sdk_preservation_rows": observed,
                "required_min_sdk_preservation_rows": self.min_sdk_preservation_rows,
            }
        ]

    @property
    def fixture_coverage_failures(self) -> list[dict[str, int]]:
        if self.min_distinct_fixtures is None:
            return []
        observed = self.distinct_fixture_count
        if observed >= self.min_distinct_fixtures:
            return []
        return [
            {
                "observed_distinct_fixtures": observed,
                "required_min_distinct_fixtures": self.min_distinct_fixtures,
            }
        ]

    @property
    def fixture_complexity_failures(self) -> list[dict[str, Any]]:
        inventory = self.fixture_inventory
        gates = self.fixture_gates or {}
        if inventory is None or not gates:
            return []
        failures: list[dict[str, Any]] = []
        for feature, minimum in sorted(gates.items()):
            observed = _fixture_gate_observed(inventory, feature)
            if observed < minimum:
                failures.append(
                    {
                        "feature": feature,
                        "observed": observed,
                        "required_minimum": minimum,
                    }
                )
        return failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "benchmark-profile",
            "run_id": self.run_id,
            "status": self.status,
            "profile": self.profile.to_dict(),
            "iterations": self.iterations,
            "warmup": self.warmup,
            "validate_openxml": self.validate_openxml,
            "min_wolfppt_speedup": self.min_wolfppt_speedup,
            "min_native_roundtrip_speedup": self.min_native_roundtrip_speedup,
            "min_openxml_samples": self.min_openxml_samples,
            "min_source_invalid_preserved_samples": (
                self.min_source_invalid_preserved_samples
            ),
            "min_distinct_fixtures": self.min_distinct_fixtures,
            "min_sdk_preservation_rows": self.min_sdk_preservation_rows,
            "fixture_inventory": self.fixture_inventory,
            "fixture_gates": self.fixture_gates or {},
            "private_inventory": self.private_inventory,
            "private_gates": self.private_gates or {},
            "fail_fast": self.fail_fast,
            "stopped_early": self.stopped_early,
            "environment": self.environment,
            "status_counts": self.status_counts,
            "distinct_fixture_count": self.distinct_fixture_count,
            "elapsed_wall_ms": None
            if self.elapsed_wall_ms is None
            else round(self.elapsed_wall_ms, 3),
            "validation_cache": self.validation_cache_stats,
            "source_invalid_preserved_sample_count": (
                self.source_invalid_preserved_sample_count
            ),
            "skipped_results": self.skipped_results,
            "failed_results": self.failed_results,
            "speedups": self.speedups,
            "sdk_speedups": self.sdk_speedups,
            "sdk_preservation": self.sdk_preservation,
            "sdk_failed_preservation": self.sdk_failed_preservation,
            "speedup_failures": self.speedup_failures,
            "speedup_near_misses": self.speedup_near_misses,
            "native_roundtrip_speedup_failures": self.native_roundtrip_speedup_failures,
            "validation_sample_failures": self.validation_sample_failures,
            "source_invalid_preservation_failures": (
                self.source_invalid_preservation_failures
            ),
            "fixture_coverage_failures": self.fixture_coverage_failures,
            "fixture_complexity_failures": self.fixture_complexity_failures,
            "sdk_preservation_row_failures": self.sdk_preservation_row_failures,
            "batches": [batch_run.to_dict() for batch_run in self.batch_runs],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# WolfPPT Benchmark Profile {self.run_id}",
            "",
            f"Profile: `{self.profile.name}`",
            "",
            self.profile.description,
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
            f"| fail fast | {self.fail_fast} |",
            f"| stopped early | {self.stopped_early} |",
            f"| minimum WolfPPT speedup | {_fmt(self.min_wolfppt_speedup)} |",
            f"| minimum native round-trip speedup | {_fmt(self.min_native_roundtrip_speedup)} |",
            f"| minimum Open XML validation samples | {_fmt_count(self.min_openxml_samples)} |",
            (
                "| minimum source-invalid preserved samples | "
                f"{_fmt_count(self.min_source_invalid_preserved_samples)} |"
            ),
            f"| minimum distinct fixtures | {_fmt_count(self.min_distinct_fixtures)} |",
            f"| minimum SDK preservation rows | {_fmt_count(self.min_sdk_preservation_rows)} |",
            f"| git HEAD | {_git_summary(self.environment)} |",
            f"| native binding | {_native_summary(self.environment)} |",
            f"| elapsed wall time | {_fmt(self.elapsed_wall_ms)} ms |",
            f"| batches | {len(self.batch_runs)} |",
            f"| results | {len(self.results)} |",
            f"| distinct fixtures | {self.distinct_fixture_count} |",
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
        if self.private_inventory is not None:
            lines.extend(_private_inventory_markdown(self.private_inventory, self.private_gates or {}))
        if self.fixture_inventory is not None:
            lines.extend(
                _fixture_inventory_markdown(
                    self.fixture_inventory,
                    self.fixture_gates or {},
                )
            )
        lines.extend(
            [
                "",
                "## Batches",
                "",
                "| batch | fixtures | adapters | status | results | pass | skip | fail |",
                "|---|---:|---:|---|---:|---:|---:|---:|",
            ]
        )
        for batch_run in self.batch_runs:
            batch = batch_run.batch
            fixture_count = "all" if batch.fixture_ids is None else str(len(batch.fixture_ids))
            batch_counts = _status_counts(batch_run.run.results)
            lines.append(
                f"| `{batch.name}` | {fixture_count} | {len(batch.adapter_names)} | "
                f"{batch_run.status} | {len(batch_run.run.results)} | "
                f"{batch_counts['pass']} | {batch_counts['skip']} | {batch_counts['fail']} |"
            )

        lines.extend(
            [
                "",
                "## Adapter Summary",
                "",
                "| adapter | operation | results | median ms | p95 ms | pass | skip | fail | Open XML accepted | source-invalid preserved |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in _adapter_summary(self.results):
            lines.append(
                "| {adapter} | {operation} | {results} | {median_ms} | {p95_ms} | "
                "{pass_count} | {skip_count} | {fail_count} | "
                "{openxml_accepted} | {source_invalid_preserved} |".format(**row)
            )

        skipped = self.skipped_results
        if skipped:
            lines.extend(
                [
                    "",
                    "## Skipped Adapters",
                    "",
                    "| adapter | operation | skipped results | reason |",
                    "|---|---|---:|---|",
                ]
            )
            for row in skipped:
                lines.append(
                    f"| {row['adapter']} | {row['operation']} | "
                    f"{row['count']} | {row['reason']} |"
                )
        failed = self.failed_results
        if failed:
            lines.extend(
                [
                    "",
                    "## Failed Results",
                    "",
                    "| batch | fixture | adapter | operation | failed samples | reason | details |",
                    "|---|---|---|---|---:|---|---|",
                ]
            )
            for row in failed:
                lines.append(
                    f"| `{row['batch']}` | `{row['fixture_id']}` | "
                    f"{row['adapter']} | {row['operation']} | "
                    f"{row['failed_samples']} | {_markdown_cell(row['reason'])} | "
                    f"{_markdown_cell(format_failure_preview(row['detail_preview']))} |"
                )

        speedups = self.speedups
        if speedups:
            lines.extend(
                [
                    "",
                    "## Python-Compatible Speedups",
                    "",
                    "| batch | fixture | operation | python-pptx median ms | WolfPPT median ms | WolfPPT speedup |",
                    "|---|---|---|---:|---:|---:|",
                ]
            )
            for row in speedups:
                lines.append(
                    f"| `{row['batch']}` | `{row['fixture_id']}` | {row['operation']} | "
                    f"{_fmt(row['python_pptx_median_ms'])} | {_fmt(row['wolfppt_median_ms'])} | "
                    f"{_fmt(row['wolfppt_speedup'])}x |"
                )

        sdk_speedups = self.sdk_speedups
        if sdk_speedups:
            lines.extend(
                [
                    "",
                    "## Third-Party Round-Trip Speedups",
                    "",
                    "| batch | fixture | baseline adapter | baseline SDK | baseline median ms | WolfPPT native median ms | WolfPPT speedup | baseline changed parts | WolfPPT changed parts |",
                    "|---|---|---|---|---:|---:|---:|---:|---:|",
                ]
            )
            for row in sdk_speedups:
                lines.append(
                    f"| `{row['batch']}` | `{row['fixture_id']}` | "
                    f"{row['baseline_adapter']} | "
                    f"{_markdown_cell(_sdk_versions_label(row['baseline_sdk_versions']))} | "
                    f"{_fmt(row['baseline_median_ms'])} | "
                    f"{_fmt(row['wolfppt_median_ms'])} | "
                    f"{_fmt(row['wolfppt_speedup'])}x | "
                    f"{_fmt_count(row['baseline_package_changed_count'])} | "
                    f"{_fmt_count(row['wolfppt_package_changed_count'])} |"
                )

        sdk_preservation = self.sdk_preservation
        if sdk_preservation:
            lines.extend(
                [
                    "",
                    "## Third-Party Preservation Comparison",
                    "",
                    "| batch | fixture | baseline adapter | baseline changed parts | WolfPPT changed parts | WolfPPT changed fewer parts |",
                    "|---|---|---|---:|---:|---:|",
                ]
            )
            for row in sdk_preservation:
                lines.append(
                    f"| `{row['batch']}` | `{row['fixture_id']}` | "
                    f"{row['baseline_adapter']} | "
                    f"{_fmt_count(row['baseline_package_changed_count'])} | "
                    f"{_fmt_count(row['wolfppt_package_changed_count'])} | "
                    f"{_fmt_count(row['wolfppt_fewer_changed_parts'])} |"
                )

        sdk_failed_preservation = self.sdk_failed_preservation
        if sdk_failed_preservation:
            lines.extend(
                [
                    "",
                    "## Failed Third-Party Preservation Comparison",
                    "",
                    "| batch | fixture | baseline adapter | reason | baseline mismatches | baseline changed parts | baseline Open XML accepted | WolfPPT changed parts |",
                    "|---|---|---|---|---:|---:|---:|---:|",
                ]
            )
            for row in sdk_failed_preservation:
                lines.append(
                    f"| `{row['batch']}` | `{row['fixture_id']}` | "
                    f"{row['baseline_adapter']} | {_markdown_cell(row['reason'])} | "
                    f"{_fmt_count(row['baseline_mismatch_count'])} | "
                    f"{_fmt_count(row['baseline_package_changed_count'])} | "
                    f"{row['baseline_openxml_accepted']} | "
                    f"{_fmt_count(row['wolfppt_package_changed_count'])} |"
                )

        if self.min_native_roundtrip_speedup is not None:
            lines.extend(
                [
                    "",
                    "## Native Round-Trip Speedup Gate",
                    "",
                    (
                        "Minimum native round-trip speedup: "
                        f"`{_fmt(self.min_native_roundtrip_speedup)}x`"
                    ),
                    "",
                ]
            )
            failures = self.native_roundtrip_speedup_failures
            if failures:
                if "reason" in failures[0]:
                    lines.append(failures[0]["reason"])
                else:
                    lines.extend(
                        [
                            "| batch | fixture | baseline adapter | baseline median ms | WolfPPT native median ms | WolfPPT speedup | required |",
                            "|---|---|---|---:|---:|---:|---:|",
                        ]
                    )
                    for row in failures:
                        lines.append(
                            f"| `{row['batch']}` | `{row['fixture_id']}` | "
                            f"{row['baseline_adapter']} | "
                            f"{_fmt(row['baseline_median_ms'])} | "
                            f"{_fmt(row['wolfppt_median_ms'])} | "
                            f"{_fmt(row['wolfppt_speedup'])}x | "
                            f"{_fmt(row['required_min_speedup'])}x |"
                        )
            else:
                lines.append(
                    "All measured native round-trip rows met the speedup threshold."
                )

        if self.min_wolfppt_speedup is not None:
            lines.extend(
                [
                    "",
                    "## Speedup Gate",
                    "",
                    f"Minimum WolfPPT speedup: `{_fmt(self.min_wolfppt_speedup)}x`",
                    "",
                ]
            )
            if self.speedup_failures:
                lines.extend(
                    [
                        "| batch | fixture | operation | python-pptx median ms | WolfPPT median ms | WolfPPT slower by ms | WolfPPT speedup | required |",
                        "|---|---|---|---:|---:|---:|---:|---:|",
                    ]
                )
                for row in self.speedup_failures:
                    lines.append(
                        f"| `{row['batch']}` | `{row['fixture_id']}` | "
                        f"{row['operation']} | {_fmt(row['python_pptx_median_ms'])} | "
                        f"{_fmt(row['wolfppt_median_ms'])} | "
                        f"{_fmt(row['wolfppt_slower_by_ms'])} | "
                        f"{_fmt(row['wolfppt_speedup'])}x | "
                        f"{_fmt(row['required_min_speedup'])}x |"
                    )
            else:
                if self.speedup_near_misses:
                    lines.append(
                        "No measured python-pptx/WolfPPT pair missed the speedup "
                        "threshold by a material absolute delta."
                    )
                else:
                    lines.append(
                        "All measured python-pptx/WolfPPT pairs met the speedup threshold."
                    )
            if self.speedup_near_misses:
                lines.extend(
                    [
                        "",
                        (
                            "Rows below the ratio threshold but within the "
                            f"{_fmt(SPEEDUP_GATE_IMMATERIAL_SLOWDOWN_MS)} ms "
                            "absolute slowdown tolerance:"
                        ),
                        "",
                        "| batch | fixture | operation | python-pptx median ms | WolfPPT median ms | WolfPPT slower by ms | WolfPPT speedup | required |",
                        "|---|---|---|---:|---:|---:|---:|---:|",
                    ]
                )
                for row in self.speedup_near_misses:
                    lines.append(
                        f"| `{row['batch']}` | `{row['fixture_id']}` | "
                        f"{row['operation']} | {_fmt(row['python_pptx_median_ms'])} | "
                        f"{_fmt(row['wolfppt_median_ms'])} | "
                        f"{_fmt(row['wolfppt_slower_by_ms'])} | "
                        f"{_fmt(row['wolfppt_speedup'])}x | "
                        f"{_fmt(row['required_min_speedup'])}x |"
                    )

        if self.min_openxml_samples is not None:
            lines.extend(
                [
                    "",
                    "## Open XML Validation Gate",
                    "",
                    (
                        "Required Open XML validation samples: "
                        f"`{self.min_openxml_samples}`"
                    ),
                    "",
                ]
            )
            if self.validation_sample_failures:
                lines.extend(
                    [
                        "| observed samples | required samples |",
                        "|---:|---:|",
                    ]
                )
                for row in self.validation_sample_failures:
                    lines.append(
                        "| {observed_openxml_samples} | "
                        "{required_min_openxml_samples} |".format(**row)
                    )
            else:
                lines.append("Open XML validation sample count met the threshold.")

        if self.min_source_invalid_preserved_samples is not None:
            lines.extend(
                [
                    "",
                    "## Source-Invalid Preservation Gate",
                    "",
                    (
                        "Required source-invalid preserved samples: "
                        f"`{self.min_source_invalid_preserved_samples}`"
                    ),
                    "",
                ]
            )
            if self.source_invalid_preservation_failures:
                lines.extend(
                    [
                        "| observed preserved samples | required preserved samples |",
                        "|---:|---:|",
                    ]
                )
                for row in self.source_invalid_preservation_failures:
                    lines.append(
                        "| {observed_source_invalid_preserved_samples} | "
                        "{required_min_source_invalid_preserved_samples} |".format(
                            **row
                        )
                    )
            else:
                lines.append(
                    "Source-invalid Open XML preservation sample count met the threshold."
                )

        if self.min_distinct_fixtures is not None:
            lines.extend(
                [
                    "",
                    "## Fixture Coverage Gate",
                    "",
                    (
                        "Required distinct fixtures: "
                        f"`{self.min_distinct_fixtures}`"
                    ),
                    "",
                ]
            )
            if self.fixture_coverage_failures:
                lines.extend(
                    [
                        "| observed fixtures | required fixtures |",
                        "|---:|---:|",
                    ]
                )
                for row in self.fixture_coverage_failures:
                    lines.append(
                        "| {observed_distinct_fixtures} | "
                        "{required_min_distinct_fixtures} |".format(**row)
                    )
            else:
                lines.append("Distinct fixture count met the threshold.")

        if self.fixture_gates:
            lines.extend(
                [
                    "",
                    "## Fixture Complexity Gate",
                    "",
                    "| feature | observed | required |",
                    "|---|---:|---:|",
                ]
            )
            for feature, required in sorted(self.fixture_gates.items()):
                lines.append(
                    f"| {feature.replace('_', ' ')} | "
                    f"{_fmt_count(_fixture_gate_observed(self.fixture_inventory or {}, feature))} | {required} |"
                )
            if self.fixture_complexity_failures:
                lines.append("")
                lines.append("Fixture complexity coverage missed the threshold.")
            else:
                lines.append("")
                lines.append("Fixture complexity coverage met the threshold.")

        if self.min_sdk_preservation_rows is not None:
            lines.extend(
                [
                    "",
                    "## SDK Preservation Row Gate",
                    "",
                    (
                        "Required SDK preservation rows: "
                        f"`{self.min_sdk_preservation_rows}`"
                    ),
                    "",
                ]
            )
            if self.sdk_preservation_row_failures:
                lines.extend(
                    [
                        "| observed rows | required rows |",
                        "|---:|---:|",
                    ]
                )
                for row in self.sdk_preservation_row_failures:
                    lines.append(
                        "| {observed_sdk_preservation_rows} | "
                        "{required_min_sdk_preservation_rows} |".format(**row)
                    )
            else:
                lines.append("SDK preservation row count met the threshold.")

        lines.extend(
            [
                "",
                "## Fixture Results",
                "",
                "| batch | fixture | adapter | status | samples | median ms | p95 ms |",
                "|---|---|---|---|---:|---:|---:|",
            ]
        )
        for batch_run in self.batch_runs:
            for result in batch_run.run.results:
                stats = result.latency_stats()
                lines.append(
                    f"| `{batch_run.batch.name}` | `{result.fixture_id}` | {result.adapter} | "
                    f"{result.status} | {stats['count']} | {_fmt(stats['median'])} | {_fmt(stats['p95'])} |"
                )

        tools = self.batch_runs[0].run.tool_availability if self.batch_runs else []
        lines.extend(["", "## Tools", "", "| tool | available | role |", "|---|---:|---|"])
        for tool in tools:
            lines.append(f"| {tool['name']} | {tool['available']} | {tool['role']} |")
        lines.extend(
            [
                "",
                (
                    "Note: profile batches avoid known invalid drop-in adapter/fixture "
                    "combinations. Timings measure adapter calls only; semantic diffs, "
                    "package diffs, and optional Open XML validation run after timing."
                ),
            ]
        )
        return "\n".join(lines) + "\n"
