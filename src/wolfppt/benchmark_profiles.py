"""Curated benchmark profiles for valid adapter/fixture suites."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .benchmark import run_benchmarks
from .benchmark_models import format_failure_preview
from .benchmark_profile_catalog import BENCHMARK_PROFILES
from .benchmark_profile_models import (
    BenchmarkProfile,
    BenchmarkProfileBatch,
    BenchmarkProfileBatchRun,
    BenchmarkProfileRun,
)
from .corpus import FIXTURE_ROOT, MANIFEST_PATH, fixture_manifest
from .deck_complexity import DECK_COMPLEXITY_FEATURES
from .deck_complexity import DECK_COMPLEXITY_TOTAL_FIELDS
from .deck_complexity import deck_complexity_counts
from .private_decks import (
    PRIVATE_DECKS_SENTINEL,
    has_private_fixture_ids,
    private_complexity_gate_message,
    private_complexity_total,
    private_deck_inventory,
    private_feature_deck_count,
    private_feature_deck_gate_message,
    private_distinct_feature_deck_count,
    private_distinct_feature_deck_gate_message,
    private_min_complexity,
    private_min_complexity_gate_message,
    write_private_report_redaction_check,
)

MIN_SPEEDUP_GATE_ITERATIONS = 15
BenchmarkProfileProgress = Callable[[dict[str, Any]], None]


def available_benchmark_profiles() -> list[dict[str, Any]]:
    return [
        {
            "name": profile.name,
            "description": profile.description,
            "batches": len(profile.batches),
            "batch_names": [batch.name for batch in profile.batches],
            "adapter_fixture_pairs": _profile_pair_count(profile),
        }
        for profile in BENCHMARK_PROFILES
    ]


def resolve_benchmark_profile(name: str) -> BenchmarkProfile:
    profiles = {profile.name: profile for profile in BENCHMARK_PROFILES}
    try:
        return profiles[name]
    except KeyError as exc:
        known = ", ".join(sorted(profiles))
        raise ValueError(f"unknown benchmark profile {name!r}; known profiles: {known}") from exc


def run_benchmark_profile(
    name: str,
    *,
    batch_names: list[str] | None = None,
    iterations: int = 5,
    warmup: int = 1,
    validate_openxml: bool = False,
    write_results: bool = False,
    min_wolfppt_speedup: float | None = None,
    min_native_roundtrip_speedup: float | None = None,
    min_private_decks: int | None = None,
    min_distinct_private_decks: int | None = None,
    min_private_total_slides: int | None = None,
    min_private_total_shapes: int | None = None,
    min_private_total_tables: int | None = None,
    min_private_total_charts: int | None = None,
    min_private_total_media: int | None = None,
    min_private_total_embedded_objects: int | None = None,
    min_private_decks_with_tables: int | None = None,
    min_private_decks_with_charts: int | None = None,
    min_private_decks_with_media: int | None = None,
    min_private_decks_with_embedded_objects: int | None = None,
    min_private_distinct_decks_with_tables: int | None = None,
    min_private_distinct_decks_with_charts: int | None = None,
    min_private_distinct_decks_with_media: int | None = None,
    min_private_distinct_decks_with_embedded_objects: int | None = None,
    min_private_slides_per_deck: int | None = None,
    min_private_shapes_per_deck: int | None = None,
    min_fixture_total_slides: int | None = None,
    min_fixture_total_shapes: int | None = None,
    min_fixture_total_tables: int | None = None,
    min_fixture_total_charts: int | None = None,
    min_fixture_total_media: int | None = None,
    min_fixture_total_embedded_objects: int | None = None,
    min_fixtures_with_tables: int | None = None,
    min_fixtures_with_charts: int | None = None,
    min_fixtures_with_media: int | None = None,
    min_fixtures_with_embedded_objects: int | None = None,
    min_openxml_samples: int | None = None,
    min_source_invalid_preserved_samples: int | None = None,
    min_distinct_fixtures: int | None = None,
    min_sdk_preservation_rows: int | None = None,
    required_adapters: list[str] | None = None,
    progress_callback: BenchmarkProfileProgress | None = None,
    fail_fast: bool = False,
) -> BenchmarkProfileRun:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if warmup < 0:
        raise ValueError("warmup must be non-negative")
    if min_wolfppt_speedup is not None and min_wolfppt_speedup <= 0:
        raise ValueError("min_wolfppt_speedup must be greater than 0")
    if min_native_roundtrip_speedup is not None and min_native_roundtrip_speedup <= 0:
        raise ValueError("min_native_roundtrip_speedup must be greater than 0")
    if min_wolfppt_speedup is not None and iterations < MIN_SPEEDUP_GATE_ITERATIONS:
        raise ValueError(
            "min_wolfppt_speedup requires at least "
            f"{MIN_SPEEDUP_GATE_ITERATIONS} measured iterations"
        )
    if (
        min_native_roundtrip_speedup is not None
        and iterations < MIN_SPEEDUP_GATE_ITERATIONS
    ):
        raise ValueError(
            "min_native_roundtrip_speedup requires at least "
            f"{MIN_SPEEDUP_GATE_ITERATIONS} measured iterations"
        )
    if min_private_decks is not None and min_private_decks < 1:
        raise ValueError("min_private_decks must be at least 1")
    if min_distinct_private_decks is not None and min_distinct_private_decks < 1:
        raise ValueError("min_distinct_private_decks must be at least 1")
    private_complexity_gates = {
        "slides": ("min_private_total_slides", min_private_total_slides),
        "shapes": ("min_private_total_shapes", min_private_total_shapes),
        "tables": ("min_private_total_tables", min_private_total_tables),
        "charts": ("min_private_total_charts", min_private_total_charts),
        "media": ("min_private_total_media", min_private_total_media),
        "embedded_objects": (
            "min_private_total_embedded_objects",
            min_private_total_embedded_objects,
        ),
    }
    for parameter_name, minimum in private_complexity_gates.values():
        if minimum is not None and minimum < 1:
            raise ValueError(f"{parameter_name} must be at least 1")
    private_feature_deck_gates = {
        "tables": ("min_private_decks_with_tables", min_private_decks_with_tables),
        "charts": ("min_private_decks_with_charts", min_private_decks_with_charts),
        "media": ("min_private_decks_with_media", min_private_decks_with_media),
        "embedded_objects": (
            "min_private_decks_with_embedded_objects",
            min_private_decks_with_embedded_objects,
        ),
    }
    for parameter_name, minimum in private_feature_deck_gates.values():
        if minimum is not None and minimum < 1:
            raise ValueError(f"{parameter_name} must be at least 1")
    private_distinct_feature_deck_gates = {
        "tables": (
            "min_private_distinct_decks_with_tables",
            min_private_distinct_decks_with_tables,
        ),
        "charts": (
            "min_private_distinct_decks_with_charts",
            min_private_distinct_decks_with_charts,
        ),
        "media": (
            "min_private_distinct_decks_with_media",
            min_private_distinct_decks_with_media,
        ),
        "embedded_objects": (
            "min_private_distinct_decks_with_embedded_objects",
            min_private_distinct_decks_with_embedded_objects,
        ),
    }
    for parameter_name, minimum in private_distinct_feature_deck_gates.values():
        if minimum is not None and minimum < 1:
            raise ValueError(f"{parameter_name} must be at least 1")
    private_min_complexity_gates = {
        "slides": ("min_private_slides_per_deck", min_private_slides_per_deck),
        "shapes": ("min_private_shapes_per_deck", min_private_shapes_per_deck),
    }
    for parameter_name, minimum in private_min_complexity_gates.values():
        if minimum is not None and minimum < 1:
            raise ValueError(f"{parameter_name} must be at least 1")
    fixture_complexity_gates = {
        "slides": ("min_fixture_total_slides", min_fixture_total_slides),
        "shapes": ("min_fixture_total_shapes", min_fixture_total_shapes),
        "tables": ("min_fixture_total_tables", min_fixture_total_tables),
        "charts": ("min_fixture_total_charts", min_fixture_total_charts),
        "media": ("min_fixture_total_media", min_fixture_total_media),
        "embedded_objects": (
            "min_fixture_total_embedded_objects",
            min_fixture_total_embedded_objects,
        ),
    }
    for parameter_name, minimum in fixture_complexity_gates.values():
        if minimum is not None and minimum < 1:
            raise ValueError(f"{parameter_name} must be at least 1")
    fixture_feature_gates = {
        "tables": ("min_fixtures_with_tables", min_fixtures_with_tables),
        "charts": ("min_fixtures_with_charts", min_fixtures_with_charts),
        "media": ("min_fixtures_with_media", min_fixtures_with_media),
        "embedded_objects": (
            "min_fixtures_with_embedded_objects",
            min_fixtures_with_embedded_objects,
        ),
    }
    for parameter_name, minimum in fixture_feature_gates.values():
        if minimum is not None and minimum < 1:
            raise ValueError(f"{parameter_name} must be at least 1")
    if min_openxml_samples is not None and min_openxml_samples < 1:
        raise ValueError("min_openxml_samples must be at least 1")
    if min_openxml_samples is not None and not validate_openxml:
        raise ValueError("min_openxml_samples requires validate_openxml=True")
    if (
        min_source_invalid_preserved_samples is not None
        and min_source_invalid_preserved_samples < 1
    ):
        raise ValueError("min_source_invalid_preserved_samples must be at least 1")
    if min_source_invalid_preserved_samples is not None and not validate_openxml:
        raise ValueError(
            "min_source_invalid_preserved_samples requires validate_openxml=True"
        )
    if min_distinct_fixtures is not None and min_distinct_fixtures < 1:
        raise ValueError("min_distinct_fixtures must be at least 1")
    if min_sdk_preservation_rows is not None and min_sdk_preservation_rows < 1:
        raise ValueError("min_sdk_preservation_rows must be at least 1")

    profile = _select_profile_batches(resolve_benchmark_profile(name), batch_names)
    uses_private_decks = any(
        batch.fixture_ids is not None and PRIVATE_DECKS_SENTINEL in batch.fixture_ids
        for batch in profile.batches
    )
    if min_private_decks is not None and not uses_private_decks:
        raise ValueError("min_private_decks only applies to private-deck profiles")
    if min_distinct_private_decks is not None and not uses_private_decks:
        raise ValueError(
            "min_distinct_private_decks only applies to private-deck profiles"
        )
    active_complexity_gates = {
        feature: minimum
        for feature, (_, minimum) in private_complexity_gates.items()
        if minimum is not None
    }
    active_fixture_complexity_gates = {
        feature: minimum
        for feature, (_, minimum) in fixture_complexity_gates.items()
        if minimum is not None
    }
    active_fixture_feature_gates = {
        feature: minimum
        for feature, (_, minimum) in fixture_feature_gates.items()
        if minimum is not None
    }
    if active_fixture_feature_gates and uses_private_decks:
        raise ValueError(
            "checked-in fixture feature gates do not apply to private-deck profiles"
        )
    if active_complexity_gates and not uses_private_decks:
        raise ValueError(
            "private complexity gates only apply to private-deck profiles"
        )
    active_feature_deck_gates = {
        feature: minimum
        for feature, (_, minimum) in private_feature_deck_gates.items()
        if minimum is not None
    }
    if active_feature_deck_gates and not uses_private_decks:
        raise ValueError(
            "private feature-deck gates only apply to private-deck profiles"
        )
    active_distinct_feature_deck_gates = {
        feature: minimum
        for feature, (_, minimum) in private_distinct_feature_deck_gates.items()
        if minimum is not None
    }
    if active_distinct_feature_deck_gates and not uses_private_decks:
        raise ValueError(
            "private distinct feature-deck gates only apply to private-deck profiles"
        )
    active_min_complexity_gates = {
        feature: minimum
        for feature, (_, minimum) in private_min_complexity_gates.items()
        if minimum is not None
    }
    if active_min_complexity_gates and not uses_private_decks:
        raise ValueError(
            "private per-deck complexity gates only apply to private-deck profiles"
        )
    inventory: dict[str, Any] | None = None
    private_gates: dict[str, int] = {}
    if uses_private_decks:
        inventory = private_deck_inventory()
        if min_private_decks is not None:
            private_gates["deck_count"] = min_private_decks
        if min_distinct_private_decks is not None:
            private_gates["distinct_content_count"] = min_distinct_private_decks
        private_gates.update(active_complexity_gates)
        private_gates.update(
            {
                f"decks_with_{feature}": minimum
                for feature, minimum in active_feature_deck_gates.items()
            }
        )
        private_gates.update(
            {
                f"distinct_decks_with_{feature}": minimum
                for feature, minimum in active_distinct_feature_deck_gates.items()
            }
        )
        private_gates.update(
            {
                f"min_{feature}_per_deck": minimum
                for feature, minimum in active_min_complexity_gates.items()
            }
        )
        if (
            min_private_decks is not None
            and inventory["deck_count"] < min_private_decks
        ):
            raise ValueError(
                (
                    f"{inventory['env']} contains {inventory['deck_count']} private "
                    f"deck(s); at least {min_private_decks} required"
                )
            )
        if (
            min_distinct_private_decks is not None
            and inventory["distinct_content_count"] < min_distinct_private_decks
        ):
            raise ValueError(
                (
                    f"{inventory['env']} contains {inventory['distinct_content_count']} "
                    "distinct private deck content item(s); at least "
                    f"{min_distinct_private_decks} required"
                )
            )
        for feature, minimum in active_complexity_gates.items():
            if private_complexity_total(inventory, feature) < minimum:
                raise ValueError(
                    private_complexity_gate_message(inventory, feature, minimum)
                )
        for feature, minimum in active_feature_deck_gates.items():
            if private_feature_deck_count(inventory, feature) < minimum:
                raise ValueError(
                    private_feature_deck_gate_message(inventory, feature, minimum)
                )
        for feature, minimum in active_distinct_feature_deck_gates.items():
            if private_distinct_feature_deck_count(inventory, feature) < minimum:
                raise ValueError(
                    private_distinct_feature_deck_gate_message(
                        inventory,
                        feature,
                        minimum,
                    )
                )
        for feature, minimum in active_min_complexity_gates.items():
            if private_min_complexity(inventory, feature) < minimum:
                raise ValueError(
                    private_min_complexity_gate_message(inventory, feature, minimum)
                )

    required = set(required_adapters or [])
    if required:
        profile_adapters = {
            adapter
            for batch in profile.batches
            for adapter in batch.adapter_names
        }
        missing = sorted(required - profile_adapters)
        if missing:
            raise ValueError(
                "required adapter(s) are not present in benchmark profile "
                f"{profile.name}: {', '.join(missing)}"
            )
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    start = perf_counter()
    batch_runs: list[BenchmarkProfileBatchRun] = []
    for batch_index, batch in enumerate(profile.batches, start=1):
        batch_start = perf_counter()
        result_progress_callback = (
            _batch_result_progress_callback(
                progress_callback,
                profile=profile,
                batch=batch,
                batch_index=batch_index,
                batch_count=len(profile.batches),
                run_id=run_id,
                iterations=iterations,
                warmup=warmup,
                validate_openxml=validate_openxml,
                private_inventory=inventory,
            )
            if progress_callback is not None
            else None
        )
        if progress_callback is not None:
            progress_callback(
                _benchmark_profile_progress_event(
                    "batch_start",
                    profile=profile,
                    batch=batch,
                    batch_index=batch_index,
                    batch_count=len(profile.batches),
                    run_id=run_id,
                    iterations=iterations,
                    warmup=warmup,
                    validate_openxml=validate_openxml,
                    private_inventory=inventory,
                )
            )
        try:
            benchmark_kwargs: dict[str, Any] = {}
            if result_progress_callback is not None:
                benchmark_kwargs["progress_callback"] = result_progress_callback
            run = run_benchmarks(
                iterations=iterations,
                warmup=warmup,
                adapter_names=list(batch.adapter_names),
                fixture_ids=list(batch.fixture_ids)
                if batch.fixture_ids is not None
                else None,
                validate_openxml=validate_openxml,
                write_results=write_results,
                required_adapters=[
                    adapter for adapter in batch.adapter_names if adapter in required
                ],
                run_id=run_id,
                **benchmark_kwargs,
            )
        except Exception as exc:
            if progress_callback is not None:
                progress_callback(
                    {
                        **_benchmark_profile_progress_event(
                            "batch_error",
                            profile=profile,
                            batch=batch,
                            batch_index=batch_index,
                            batch_count=len(profile.batches),
                            run_id=run_id,
                            iterations=iterations,
                            warmup=warmup,
                            validate_openxml=validate_openxml,
                            private_inventory=inventory,
                        ),
                        "elapsed_wall_ms": (perf_counter() - batch_start) * 1000.0,
                        "error_type": type(exc).__name__,
                    }
                )
            raise
        if progress_callback is not None:
            progress_callback(
                {
                    **_benchmark_profile_progress_event(
                        "batch_finish",
                        profile=profile,
                        batch=batch,
                        batch_index=batch_index,
                        batch_count=len(profile.batches),
                        run_id=run_id,
                        iterations=iterations,
                        warmup=warmup,
                        validate_openxml=validate_openxml,
                        private_inventory=inventory,
                    ),
                    "status": run.status,
                    "status_counts": run.status_counts,
                    "failure_preview": _batch_failure_preview(run),
                    "elapsed_wall_ms": (perf_counter() - batch_start) * 1000.0,
                }
            )
        batch_runs.append(BenchmarkProfileBatchRun(batch=batch, run=run))
        if fail_fast and run.status == "fail":
            break

    return BenchmarkProfileRun(
        run_id=run_id,
        profile=profile,
        iterations=iterations,
        warmup=warmup,
        validate_openxml=validate_openxml,
        batch_runs=tuple(batch_runs),
        min_wolfppt_speedup=min_wolfppt_speedup,
        min_native_roundtrip_speedup=min_native_roundtrip_speedup,
        min_openxml_samples=min_openxml_samples,
        min_source_invalid_preserved_samples=min_source_invalid_preserved_samples,
        min_distinct_fixtures=min_distinct_fixtures,
        min_sdk_preservation_rows=min_sdk_preservation_rows,
        fixture_inventory=_fixture_complexity_inventory(
            {result.fixture_id for batch_run in batch_runs for result in batch_run.run.results}
        )
        if active_fixture_complexity_gates or active_fixture_feature_gates
        else None,
        fixture_gates={
            **active_fixture_complexity_gates,
            **{
                f"fixtures_with_{feature}": minimum
                for feature, minimum in active_fixture_feature_gates.items()
            },
        }
        or None,
        private_inventory=inventory,
        private_gates=private_gates or None,
        fail_fast=fail_fast,
        stopped_early=fail_fast and len(batch_runs) < len(profile.batches),
        elapsed_wall_ms=(perf_counter() - start) * 1000.0,
    )


def _batch_failure_preview(run: Any, *, limit: int = 3) -> list[str]:
    return [
        (
            f"{row['adapter']} {row['fixture_id']}: {row['reason']} "
            f"details={format_failure_preview(row['detail_preview'])}"
        )
        for row in run.failed_results[:limit]
    ]


def write_benchmark_profile_report(
    run: BenchmarkProfileRun,
    output_dir: Path = Path("results/benchmarks/latest"),
) -> None:
    for target_dir in _benchmark_profile_report_dirs(run.run_id, output_dir):
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "run.json").write_text(
            json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (target_dir / "report.md").write_text(run.to_markdown(), encoding="utf-8")
        if has_private_fixture_ids([result.fixture_id for result in run.results]):
            write_private_report_redaction_check(target_dir)


def _benchmark_profile_report_dirs(run_id: str, output_dir: Path) -> tuple[Path, ...]:
    if output_dir.name != "latest":
        return (output_dir,)
    archive_dir = output_dir.parent / "runs" / run_id
    return (output_dir, archive_dir)


def _select_profile_batches(
    profile: BenchmarkProfile,
    batch_names: list[str] | None,
) -> BenchmarkProfile:
    if not batch_names:
        return profile
    selected_names = set(batch_names)
    known_names = {batch.name for batch in profile.batches}
    unknown = sorted(selected_names - known_names)
    if unknown:
        known = ", ".join(sorted(known_names))
        raise ValueError(
            "unknown benchmark batch(es) for profile "
            f"{profile.name!r}: {', '.join(unknown)}; known batches: {known}"
        )
    return BenchmarkProfile(
        name=profile.name,
        description=profile.description,
        batches=tuple(batch for batch in profile.batches if batch.name in selected_names),
    )


def _profile_pair_count(profile: BenchmarkProfile) -> int | None:
    total = 0
    for batch in profile.batches:
        if batch.fixture_ids is None or PRIVATE_DECKS_SENTINEL in batch.fixture_ids:
            return None
        total += len(batch.adapter_names) * len(batch.fixture_ids)
    return total


def _benchmark_profile_progress_event(
    event: str,
    *,
    profile: BenchmarkProfile,
    batch: BenchmarkProfileBatch,
    batch_index: int,
    batch_count: int,
    run_id: str,
    iterations: int,
    warmup: int,
    validate_openxml: bool,
    private_inventory: dict[str, Any] | None,
) -> dict[str, Any]:
    fixture_scope, fixture_count = _batch_fixture_scope(batch, private_inventory)
    profile_result_count = _profile_pair_count(profile)
    return {
        "event": event,
        "run_id": run_id,
        "profile": profile.name,
        "batch": batch.name,
        "batch_index": batch_index,
        "batch_count": batch_count,
        "adapter_count": len(batch.adapter_names),
        "fixture_scope": fixture_scope,
        "fixture_count": fixture_count,
        "profile_result_count": profile_result_count,
        "iterations": iterations,
        "warmup": warmup,
        "validate_openxml": validate_openxml,
    }


def _batch_result_progress_callback(
    progress_callback: BenchmarkProfileProgress,
    *,
    profile: BenchmarkProfile,
    batch: BenchmarkProfileBatch,
    batch_index: int,
    batch_count: int,
    run_id: str,
    iterations: int,
    warmup: int,
    validate_openxml: bool,
    private_inventory: dict[str, Any] | None,
) -> BenchmarkProfileProgress:
    profile_completed_before_batch = _completed_profile_results_before_batch(
        profile,
        batch_index,
    )
    profile_result_count = _profile_pair_count(profile)

    def callback(event: dict[str, Any]) -> None:
        if event.get("event") != "result_finish":
            return
        profile_completed_results = None
        if profile_completed_before_batch is not None:
            profile_completed_results = (
                profile_completed_before_batch + event["completed_results"]
            )
        progress_callback(
            {
                **_benchmark_profile_progress_event(
                    "batch_result",
                    profile=profile,
                    batch=batch,
                    batch_index=batch_index,
                    batch_count=batch_count,
                    run_id=run_id,
                    iterations=iterations,
                    warmup=warmup,
                    validate_openxml=validate_openxml,
                    private_inventory=private_inventory,
                ),
                "fixture_id": event["fixture_id"],
                "adapter": event["adapter"],
                "operation": event["operation"],
                "status": event["status"],
                "completed_results": event["completed_results"],
                "total_results": event["total_results"],
                "profile_completed_results": profile_completed_results,
                "profile_result_count": profile_result_count,
                "elapsed_wall_ms": event["elapsed_wall_ms"],
            }
        )

    return callback


def _completed_profile_results_before_batch(
    profile: BenchmarkProfile,
    batch_index: int,
) -> int | None:
    total = 0
    for batch in profile.batches[: batch_index - 1]:
        if batch.fixture_ids is None or PRIVATE_DECKS_SENTINEL in batch.fixture_ids:
            return None
        total += len(batch.adapter_names) * len(batch.fixture_ids)
    return total


def _batch_fixture_scope(
    batch: BenchmarkProfileBatch,
    private_inventory: dict[str, Any] | None,
) -> tuple[str, int | None]:
    if batch.fixture_ids is None:
        return ("all", None)
    if PRIVATE_DECKS_SENTINEL in batch.fixture_ids:
        count = (
            None
            if private_inventory is None
            else int(private_inventory["deck_count"])
        )
        return ("private", count)
    return ("selected", len(batch.fixture_ids))


def _fixture_complexity_inventory(fixture_ids: set[str]) -> dict[str, object]:
    manifest_by_id = {str(item["id"]): item for item in fixture_manifest(MANIFEST_PATH)}
    counts: Counter[str] = Counter()
    fixtures: list[dict[str, object]] = []
    for fixture_id in sorted(fixture_ids):
        if fixture_id.startswith("private/") or fixture_id not in manifest_by_id:
            continue
        item = manifest_by_id[fixture_id]
        path = FIXTURE_ROOT / str(item["path"])
        try:
            fixture_counts = deck_complexity_counts(path)
        except ValueError as exc:
            raise ValueError(f"fixture {fixture_id!r} could not be inspected: {exc}") from exc
        counts.update(fixture_counts)
        fixtures.append(
            {
                "id": fixture_id,
                "complexity_counts": fixture_counts,
            }
        )
    complexity_payload = {
        feature: int(counts[feature])
        for feature in DECK_COMPLEXITY_FEATURES
    }
    feature_fixture_counts = {
        feature: sum(
            1
            for fixture in fixtures
            if int(dict(fixture["complexity_counts"])[feature]) > 0
        )
        for feature in ("tables", "charts", "media", "embedded_objects")
    }
    total_fields = {
        total_field: complexity_payload[feature]
        for feature, total_field in DECK_COMPLEXITY_TOTAL_FIELDS.items()
    }
    return {
        "fixture_count": len(fixtures),
        **total_fields,
        "complexity_counts": complexity_payload,
        "feature_fixture_counts": feature_fixture_counts,
        "fixtures": fixtures,
    }
