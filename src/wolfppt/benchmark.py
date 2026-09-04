"""Repeatable benchmark suite for PPTX adapters."""

from __future__ import annotations

import gc
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from tempfile import TemporaryDirectory
from typing import Any, Callable

from . import benchmark_core_operations as _benchmark_core_operations
from . import (
    benchmark_dropin_chart_data_operations as _benchmark_dropin_chart_data_operations,
)
from . import benchmark_dropin_chart_operations as _benchmark_dropin_chart_operations
from . import benchmark_dropin_common_operations as _benchmark_dropin_common_operations
from . import benchmark_dropin_media_operations as _benchmark_dropin_media_operations
from . import (
    benchmark_dropin_nested_group_operations as _benchmark_dropin_nested_group_operations,
)
from . import benchmark_dropin_shape_operations as _benchmark_dropin_shape_operations
from . import benchmark_dropin_table_operations as _benchmark_dropin_table_operations
from . import benchmark_dropin_text_operations as _benchmark_dropin_text_operations
from .adapters import available_tools
from .adapters import apache_poi as _apache_poi_adapter
from .adapters import aspose_docker as _aspose_docker_adapter
from .adapters import aspose_slides as _aspose_slides_adapter
from .adapters import external_command as _external_command_adapter
from .adapters import openxml_sdk as _openxml_sdk_adapter
from .adapters import pptxgenjs as _pptxgenjs_adapter
from .adapters import rust_core as _rust_core_adapter
from .adapters import spire_presentation as _spire_presentation_adapter
from .adapters import syncfusion as _syncfusion_adapter
from .benchmark_fit_text_fonts import find_fit_text_font
from .benchmark_models import (
    BenchmarkAdapter,
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkSample,
)
from .benchmark_registry import build_benchmark_adapters, default_benchmark_adapter_names
from .benchmark_runtime import (
    always_available as _always_available,
    max_rss_mb as _max_rss_mb,
    python_pptx_available as _python_pptx_available,
)
from .corpus import EXPECTED_ROOT, FIXTURE_ROOT, MANIFEST_PATH, fixture_manifest
from .native import native_available
from .native import native_build_info
from .private_decks import (
    PRIVATE_DECKS_SENTINEL,
    discover_private_decks,
    has_private_fixture_ids,
    write_private_report_redaction_check,
)
from .results import HarnessResult, append_result

BenchmarkProgress = Callable[[dict[str, Any]], None]


def run_benchmarks(
    *,
    iterations: int = 5,
    warmup: int = 1,
    adapter_names: list[str] | None = None,
    fixture_ids: list[str] | None = None,
    validate_openxml: bool = False,
    write_results: bool = False,
    required_adapters: list[str] | None = None,
    run_id: str | None = None,
    progress_callback: BenchmarkProgress | None = None,
) -> BenchmarkRun:
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if warmup < 0:
        raise ValueError("warmup must be non-negative")

    adapters = _resolve_adapters(adapter_names)
    required = _resolve_required_adapters(required_adapters, adapters)
    fixture_items = _resolve_fixtures(fixture_ids)
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    start = perf_counter()
    results: list[BenchmarkResult] = []
    total_results = len(fixture_items) * len(adapters)

    for item in fixture_items:
        fixture_id = str(item["id"])
        fixture_path = _fixture_runtime_path(item)
        report_path = _fixture_report_path(item, fixture_path)
        expected_path = EXPECTED_ROOT / f"{fixture_id}.json"
        for adapter in adapters:
            result = _run_adapter_benchmark(
                adapter,
                fixture_id,
                fixture_path,
                expected_path,
                report_path=report_path,
                iterations=iterations,
                warmup=warmup,
                validate_openxml=validate_openxml,
                required=adapter.name in required,
            )
            results.append(result)
            if write_results:
                _append_benchmark_results(run_id, result)
            if progress_callback is not None:
                progress_callback(
                    {
                        "event": "result_finish",
                        "run_id": run_id,
                        "fixture_id": fixture_id,
                        "adapter": adapter.name,
                        "operation": adapter.operation,
                        "status": result.status,
                        "completed_results": len(results),
                        "total_results": total_results,
                        "elapsed_wall_ms": (perf_counter() - start) * 1000.0,
                    }
                )

    return BenchmarkRun(
        run_id=run_id,
        iterations=iterations,
        warmup=warmup,
        validate_openxml=validate_openxml,
        adapters=[adapter.name for adapter in adapters],
        required_adapters=sorted(required),
        environment=_benchmark_environment(),
        fixture_ids=[str(item["id"]) for item in fixture_items],
        tool_availability=[tool.to_dict() for tool in available_tools()],
        results=results,
        elapsed_wall_ms=(perf_counter() - start) * 1000.0,
    )


def write_benchmark_report(
    run: BenchmarkRun,
    output_dir: Path = Path("results/benchmarks/latest"),
) -> None:
    for target_dir in _benchmark_report_dirs(run.run_id, output_dir):
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "run.json").write_text(
            json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (target_dir / "report.md").write_text(run.to_markdown(), encoding="utf-8")
        if has_private_fixture_ids(run.fixture_ids):
            write_private_report_redaction_check(target_dir)


def _benchmark_report_dirs(run_id: str, output_dir: Path) -> tuple[Path, ...]:
    if output_dir.name != "latest":
        return (output_dir,)
    archive_dir = output_dir.parent / "runs" / run_id
    return (output_dir, archive_dir)


def available_benchmark_adapters() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for adapter in BENCHMARK_ADAPTERS:
        available = adapter.available()
        rows.append(
            {
                "name": adapter.name,
                "operation": adapter.operation,
                "role": adapter.role,
                "available": available,
                "unavailable_reason": None
                if available
                else _adapter_unavailable_reason(adapter),
                "default": adapter.name in DEFAULT_BENCHMARK_ADAPTERS,
            }
        )
    return rows


def _run_adapter_benchmark(
    adapter: BenchmarkAdapter,
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    *,
    report_path: str | None = None,
    iterations: int,
    warmup: int,
    validate_openxml: bool,
    required: bool = False,
) -> BenchmarkResult:
    result_path = report_path or str(fixture_path)
    if not adapter.available():
        reason = _adapter_unavailable_reason(adapter)
        if required:
            reason = f"required adapter unavailable: {reason}"
        return BenchmarkResult(
            fixture_id=fixture_id,
            path=result_path,
            adapter=adapter.name,
            operation=adapter.operation,
            status="fail" if required else "skip",
            skip_reason=reason,
        )

    samples: list[BenchmarkSample] = []
    try:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for _ in range(warmup):
                adapter.run(fixture_id, fixture_path, expected_path, tmp_path, validate_openxml)
                gc.collect()
            for iteration in range(1, iterations + 1):
                elapsed_ms, details = adapter.run(
                    fixture_id,
                    fixture_path,
                    expected_path,
                    tmp_path,
                    validate_openxml,
                )
                gc.collect()
                samples.append(
                    BenchmarkSample(
                        iteration=iteration,
                        elapsed_ms=elapsed_ms,
                        rss_mb=_max_rss_mb(),
                        status="pass" if bool(details.get("ok")) else "fail",
                        details=details,
                    )
                )
    except RuntimeError as exc:
        return BenchmarkResult(
            fixture_id=fixture_id,
            path=result_path,
            adapter=adapter.name,
            operation=adapter.operation,
            status="fail",
            skip_reason=str(exc),
            samples=samples,
        )

    status = "pass" if all(sample.status == "pass" for sample in samples) else "fail"
    return BenchmarkResult(
        fixture_id=fixture_id,
        path=result_path,
        adapter=adapter.name,
        operation=adapter.operation,
        status=status,
        samples=samples,
    )


def _adapter_unavailable_reason(adapter: BenchmarkAdapter) -> str:
    if adapter.unavailable_reason is None:
        return "adapter unavailable"
    return adapter.unavailable_reason() or "adapter unavailable"


def _resolve_adapters(adapter_names: list[str] | None) -> list[BenchmarkAdapter]:
    names = adapter_names or list(DEFAULT_BENCHMARK_ADAPTERS)
    by_name = {adapter.name: adapter for adapter in BENCHMARK_ADAPTERS}
    missing = [name for name in names if name not in by_name]
    if missing:
        known = ", ".join(sorted(by_name))
        raise ValueError(f"unknown benchmark adapter(s): {', '.join(missing)}; known adapters: {known}")
    return [by_name[name] for name in names]


def _resolve_required_adapters(
    required_adapters: list[str] | None,
    adapters: list[BenchmarkAdapter],
) -> set[str]:
    if not required_adapters:
        return set()
    selected = {adapter.name for adapter in adapters}
    required = set(required_adapters)
    missing = sorted(required - selected)
    if missing:
        selected_names = ", ".join(sorted(selected))
        raise ValueError(
            "required adapter(s) are not selected: "
            f"{', '.join(missing)}; selected adapters: {selected_names}"
        )
    return required


def _resolve_fixtures(fixture_ids: list[str] | None) -> list[dict[str, object]]:
    items = fixture_manifest(MANIFEST_PATH)
    if fixture_ids is None:
        return items
    needs_private = (
        PRIVATE_DECKS_SENTINEL in fixture_ids
        or any(fixture_id.startswith("private/") for fixture_id in fixture_ids)
    )
    private_items = discover_private_decks() if needs_private else []
    wanted = set(fixture_ids)
    selected = [item for item in items if str(item["id"]) in wanted]
    if PRIVATE_DECKS_SENTINEL in wanted:
        selected.extend(private_items)
        wanted.remove(PRIVATE_DECKS_SENTINEL)
    else:
        selected.extend(item for item in private_items if str(item["id"]) in wanted)
    found = {str(item["id"]) for item in selected}
    missing = sorted(wanted - found)
    if missing:
        known_items = [*items, *private_items]
        known = ", ".join(str(item["id"]) for item in known_items)
        raise ValueError(f"unknown fixture id(s): {', '.join(missing)}; known fixtures: {known}")
    return selected


def _fixture_runtime_path(item: dict[str, object]) -> Path:
    actual_path = item.get("actual_path")
    if actual_path is not None:
        return Path(str(actual_path))
    return FIXTURE_ROOT / str(item["path"])


def _fixture_report_path(item: dict[str, object], fixture_path: Path) -> str:
    report_path = item.get("report_path")
    return str(report_path) if report_path is not None else str(fixture_path)


def _append_benchmark_results(run_id: str, result: BenchmarkResult) -> None:
    if result.status == "skip":
        append_result(
            HarnessResult(
                run_id=run_id,
                fixture=result.fixture_id,
                adapter=result.adapter,
                operation=f"benchmark:{result.operation}",
                status="skip",
                metadata={"reason": result.skip_reason, "latency_ms": result.latency_stats()},
            )
        )
        return
    for sample in result.samples:
        append_result(
            HarnessResult(
                run_id=run_id,
                fixture=result.fixture_id,
                adapter=result.adapter,
                operation=f"benchmark:{result.operation}",
                status=sample.status,
                elapsed_ms=sample.elapsed_ms,
                rss_mb=sample.rss_mb,
                metadata=sample.details,
            )
        )


def _benchmark_environment() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git": _git_environment(),
        "native_binding": native_build_info(),
    }


def _git_environment() -> dict[str, Any]:
    env_head = os.environ.get("WOLFPPT_BENCHMARK_GIT_HEAD")
    if env_head:
        env_short_head = os.environ.get("WOLFPPT_BENCHMARK_GIT_SHORT_HEAD") or env_head[:7]
        env_dirty = os.environ.get("WOLFPPT_BENCHMARK_GIT_DIRTY", "false").lower()
        env_sync_status = os.environ.get("WOLFPPT_BENCHMARK_GIT_SYNC_STATUS")
        git_info: dict[str, Any] = {
            "available": True,
            "head": env_head,
            "short_head": env_short_head,
            "dirty": env_dirty in {"1", "true", "yes"},
            "source": "environment",
        }
        if env_sync_status:
            git_info["sync_status"] = env_sync_status
        return git_info

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        short_head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"available": False}
    return {
        "available": True,
        "head": head,
        "short_head": short_head,
        "dirty": dirty,
        "source": "git",
    }


def _fit_text_available() -> bool:
    try:
        _fit_text_font_file()
    except Exception:
        return False
    return True


def _python_pptx_fit_text_available() -> bool:
    return _python_pptx_available() and _fit_text_available()


def _wolfppt_fit_text_available() -> bool:
    return native_available() and _fit_text_available()


def _fit_text_font_file() -> str:
    return find_fit_text_font()[1]


_BENCHMARK_OPERATION_MODULES = (
    _benchmark_core_operations,
    _benchmark_dropin_common_operations,
    _benchmark_dropin_table_operations,
    _benchmark_dropin_text_operations,
    _benchmark_dropin_media_operations,
    _benchmark_dropin_nested_group_operations,
    _benchmark_dropin_shape_operations,
    _benchmark_dropin_chart_operations,
    _benchmark_dropin_chart_data_operations,
)


def _benchmark_adapter_namespace() -> dict[str, Any]:
    namespace = globals().copy()
    namespace.update(
        {
            "_always_available": _always_available,
            "apache_poi_roundtrip_available": (
                _apache_poi_adapter.apache_poi_roundtrip_available
            ),
            "apache_poi_roundtrip_unavailable_reason": (
                _apache_poi_adapter.apache_poi_roundtrip_unavailable_reason
            ),
            "aspose_docker_roundtrip_available": (
                _aspose_docker_adapter.aspose_docker_roundtrip_available
            ),
            "aspose_docker_roundtrip_unavailable_reason": (
                _aspose_docker_adapter.aspose_docker_roundtrip_unavailable_reason
            ),
            "aspose_slides_roundtrip_available": (
                _aspose_slides_adapter.aspose_slides_roundtrip_available
            ),
            "aspose_slides_roundtrip_unavailable_reason": (
                _aspose_slides_adapter.aspose_slides_roundtrip_unavailable_reason
            ),
            "external_command_roundtrip_available": (
                _external_command_adapter.external_command_roundtrip_available
            ),
            "external_command_roundtrip_unavailable_reason": (
                _external_command_adapter.external_command_roundtrip_unavailable_reason
            ),
            "openxml_sdk_roundtrip_available": (
                _openxml_sdk_adapter.openxml_sdk_roundtrip_available
            ),
            "pptxgenjs_available": _pptxgenjs_adapter.pptxgenjs_available,
            "rust_cli_available": _rust_core_adapter.rust_cli_available,
            "spire_presentation_roundtrip_available": (
                _spire_presentation_adapter.spire_presentation_roundtrip_available
            ),
            "spire_presentation_roundtrip_unavailable_reason": (
                _spire_presentation_adapter.spire_presentation_roundtrip_unavailable_reason
            ),
            "syncfusion_roundtrip_available": (
                _syncfusion_adapter.syncfusion_roundtrip_available
            ),
            "syncfusion_roundtrip_unavailable_reason": (
                _syncfusion_adapter.syncfusion_roundtrip_unavailable_reason
            ),
        }
    )
    for module in _BENCHMARK_OPERATION_MODULES:
        namespace.update(
            (name, value)
            for name, value in vars(module).items()
            if name.startswith("_bench_")
        )
    return namespace


BENCHMARK_ADAPTERS: tuple[BenchmarkAdapter, ...] = build_benchmark_adapters(
    _benchmark_adapter_namespace()
)
DEFAULT_BENCHMARK_ADAPTERS: tuple[str, ...] = default_benchmark_adapter_names(
    BENCHMARK_ADAPTERS
)
