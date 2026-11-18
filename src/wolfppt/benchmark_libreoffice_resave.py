"""python-pptx edit plus LibreOffice re-save benchmark adapters.

These adapters model the common free pipeline "edit with python-pptx, then
normalize the saved deck with headless LibreOffice". Each one runs the exact
workload of an existing ``python-pptx-*`` adapter while every python-pptx save
is followed by a LibreOffice re-save of the saved bytes. The measured time
therefore covers both steps, and the preservation, effect, and Open XML checks
of the wrapped adapter inspect the LibreOffice output.
"""

from __future__ import annotations

import importlib.metadata
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

from .adapters.libreoffice import LibreOfficeResaveResult, resave
from .benchmark_adapter_spec import BenchmarkAdapterSpec

BenchmarkFn = Callable[[str, Path, Path, Path, bool], tuple[float, dict[str, Any]]]

LIBREOFFICE_RESAVE_PREFIX = "libreoffice-resave-"
# python-pptx adapter suffixes that get a LibreOffice re-save twin: the
# open/save round-trip plus the representative release-smoke edit workloads.
LIBREOFFICE_RESAVE_WORKLOADS: tuple[str, ...] = (
    "roundtrip",
    "dropin-edit",
    "dropin-table-cell-text-frame-edit",
    "dropin-mixed-workload-edit",
    "dropin-chart-data-edit",
    "dropin-add-picture",
    "dropin-add-table",
    "dropin-add-slide",
)


def libreoffice_resave_adapter_name(workload: str) -> str:
    return f"{LIBREOFFICE_RESAVE_PREFIX}{workload}"


def libreoffice_resave_adapter_specs(
    specs: tuple[BenchmarkAdapterSpec, ...],
) -> tuple[BenchmarkAdapterSpec, ...]:
    """Derive one re-save twin spec per python-pptx workload in ``specs``."""

    by_name = {spec.name: spec for spec in specs}
    return tuple(
        BenchmarkAdapterSpec(
            libreoffice_resave_adapter_name(workload),
            by_name[f"python-pptx-{workload}"].operation,
            f"python-pptx {workload} then headless LibreOffice re-save baseline",
            "libreoffice_resave_available",
            _run_name(by_name[f"python-pptx-{workload}"].run),
            "libreoffice_resave_unavailable_reason",
        )
        for workload in LIBREOFFICE_RESAVE_WORKLOADS
    )


def libreoffice_resave_runs(
    specs: tuple[BenchmarkAdapterSpec, ...],
    namespace: Mapping[str, Any],
) -> dict[str, BenchmarkFn]:
    """Build the re-save run functions keyed by their spec ``run`` name."""

    runs: dict[str, BenchmarkFn] = {}
    for workload in LIBREOFFICE_RESAVE_WORKLOADS:
        base_run = next(
            spec.run for spec in specs if spec.name == f"python-pptx-{workload}"
        )
        runs[_run_name(base_run)] = libreoffice_resave_benchmark(namespace[base_run])
    return runs


def libreoffice_resave_benchmark(python_pptx_run: BenchmarkFn) -> BenchmarkFn:
    """Wrap a python-pptx benchmark so each save is re-saved by LibreOffice."""

    def run(
        fixture_id: str,
        fixture_path: Path,
        expected_path: Path,
        tmp_path: Path,
        validate_openxml: bool,
    ) -> tuple[float, dict[str, Any]]:
        with _resave_python_pptx_saves() as resaves:
            elapsed_ms, details = python_pptx_run(
                fixture_id, fixture_path, expected_path, tmp_path, validate_openxml
            )
        if not resaves:
            raise RuntimeError(
                "libreoffice-resave workload did not save through python-pptx"
            )
        details = dict(details)
        details.update(_resave_details(resaves))
        return elapsed_ms, details

    return run


@contextmanager
def _resave_python_pptx_saves() -> Iterator[list[LibreOfficeResaveResult]]:
    from pptx.presentation import Presentation

    original_save = Presentation.save
    resaves: list[LibreOfficeResaveResult] = []

    def save_then_resave(self: Any, file: str | Path | BinaryIO) -> None:
        original_save(self, file)
        if isinstance(file, (str, Path)):
            resaves.append(resave(file, file))
            return
        resaves.append(_resave_stream(file))

    Presentation.save = save_then_resave  # type: ignore[method-assign]
    try:
        yield resaves
    finally:
        Presentation.save = original_save  # type: ignore[method-assign]


def _resave_stream(stream: BinaryIO) -> LibreOfficeResaveResult:
    with tempfile.TemporaryDirectory(prefix="wolfppt-lo-stream-") as work:
        staged = Path(work) / "deck.pptx"
        stream.seek(0)
        staged.write_bytes(stream.read())
        result = resave(staged, staged)
        stream.seek(0)
        stream.truncate()
        stream.write(staged.read_bytes())
    return result


def _resave_details(resaves: list[LibreOfficeResaveResult]) -> dict[str, Any]:
    last = resaves[-1]
    sdk_versions = {"python-pptx": _python_pptx_version()}
    if last.libreoffice_version is not None:
        sdk_versions["LibreOffice"] = last.libreoffice_version
    return {
        "sdk_versions": sdk_versions,
        "libreoffice_resave_count": len(resaves),
        "libreoffice_resave_ms": round(sum(item.elapsed_ms for item in resaves), 3),
        "libreoffice_resave_timeout_seconds": last.timeout_seconds,
        "libreoffice_resave_argv": _redacted_argv(last.argv),
    }


def _redacted_argv(argv: list[str]) -> list[str]:
    # Keep the reproducible command shape; temporary paths vary per call.
    redacted = list(argv)
    redacted[1] = "-env:UserInstallation=<isolated-profile>"
    redacted[-3:] = ["--outdir", "<outdir>", "<input>"]
    return redacted


def _python_pptx_version() -> str:
    try:
        return importlib.metadata.version("python-pptx")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _run_name(python_pptx_run: str) -> str:
    return python_pptx_run.replace(
        "_bench_python_pptx_", "_bench_libreoffice_resave_", 1
    )
