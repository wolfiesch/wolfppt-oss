"""Shared helpers for drop-in benchmark edit operations."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .benchmark_runtime import elapsed_ms as _elapsed_ms, stamp as _stamp
from .presentation import Presentation as WolfPresentation

BenchmarkDetails = Callable[[str, Path, Path, bool], dict[str, Any]]
EditAction = Callable[[str, Any], None]


def make_python_pptx_dropin_bench(
    *,
    slug: str,
    action: EditAction,
    details: BenchmarkDetails,
    name: str,
) -> Callable[[str, Path, Path, Path, bool], tuple[float, dict[str, Any]]]:
    def bench(
        fixture_id: str,
        fixture_path: Path,
        expected_path: Path,
        tmp_path: Path,
        validate_openxml: bool,
    ) -> tuple[float, dict[str, Any]]:
        from pptx import Presentation as PythonPptxPresentation

        out = tmp_path / (
            f"python-pptx-dropin-{slug}-{fixture_path.stem}-{_stamp()}{fixture_path.suffix}"
        )
        start = perf_counter()
        prs = PythonPptxPresentation(str(fixture_path))
        action(fixture_id, prs)
        prs.save(str(out))
        elapsed_ms = _elapsed_ms(start)
        return elapsed_ms, details(fixture_id, fixture_path, out, validate_openxml)

    bench.__name__ = name
    return bench


def make_wolfppt_dropin_bench(
    *,
    slug: str,
    action: EditAction,
    details: BenchmarkDetails,
    name: str,
) -> Callable[[str, Path, Path, Path, bool], tuple[float, dict[str, Any]]]:
    def bench(
        fixture_id: str,
        fixture_path: Path,
        expected_path: Path,
        tmp_path: Path,
        validate_openxml: bool,
    ) -> tuple[float, dict[str, Any]]:
        out = tmp_path / (
            f"wolfppt-dropin-{slug}-{fixture_path.stem}-{_stamp()}{fixture_path.suffix}"
        )
        start = perf_counter()
        prs = WolfPresentation(fixture_path)
        action(fixture_id, prs)
        prs.save(out)
        elapsed_ms = _elapsed_ms(start)
        return elapsed_ms, details(fixture_id, fixture_path, out, validate_openxml)

    bench.__name__ = name
    return bench
