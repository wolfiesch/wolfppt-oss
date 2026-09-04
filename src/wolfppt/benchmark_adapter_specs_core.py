"""Core benchmark adapter specifications."""

from __future__ import annotations

from .benchmark_adapter_spec import BenchmarkAdapterSpec


CORE_BENCHMARK_ADAPTER_SPECS: tuple[BenchmarkAdapterSpec, ...] = (
    BenchmarkAdapterSpec(
        "semantic-oracle",
        "extract",
        "stdlib semantic extractor baseline",
        "_always_available",
        "_bench_semantic_extract",
    ),
    BenchmarkAdapterSpec(
        "python-pptx-summary",
        "read-summary",
        "popular Python API baseline",
        "_python_pptx_available",
        "_bench_python_pptx_summary",
    ),
    BenchmarkAdapterSpec(
        "python-pptx-roundtrip",
        "roundtrip",
        "popular Python round-trip baseline",
        "_python_pptx_available",
        "_bench_python_pptx_roundtrip",
    ),
    BenchmarkAdapterSpec(
        "python-pptx-dropin-edit",
        "dropin-edit",
        "popular Python API edit baseline",
        "_python_pptx_available",
        "_bench_python_pptx_dropin_edit",
    ),
    BenchmarkAdapterSpec(
        "wolfppt-facade-dropin-edit",
        "dropin-edit",
        "WolfPPT public Python-compatible facade",
        "native_available",
        "_bench_wolfppt_facade_dropin_edit",
    ),
    BenchmarkAdapterSpec(
        "python-pptx-dropin-file-like-edit",
        "dropin-file-like-edit",
        "popular Python API file-like open/save edit baseline",
        "_python_pptx_available",
        "_bench_python_pptx_dropin_file_like_edit",
    ),
    BenchmarkAdapterSpec(
        "wolfppt-facade-dropin-file-like-edit",
        "dropin-file-like-edit",
        "WolfPPT public Python-compatible file-like open/save edit facade",
        "native_available",
        "_bench_wolfppt_facade_dropin_file_like_edit",
    ),
)
