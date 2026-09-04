"""Non-drop-in benchmark operation implementations."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .adapters.apache_poi import roundtrip as apache_poi_roundtrip
from .adapters.aspose_docker import roundtrip as aspose_docker_roundtrip
from .adapters.aspose_slides import roundtrip as aspose_slides_roundtrip
from .adapters.external_command import roundtrip as external_command_roundtrip
from .adapters.openxml_sdk import roundtrip as openxml_sdk_roundtrip
from .adapters.pptxgenjs import generate as pptxgenjs_generate
from .adapters.python_pptx import roundtrip as python_pptx_roundtrip
from .adapters.python_pptx import summarize as python_pptx_summarize
from .adapters.rust_core import inspect as rust_inspect
from .adapters.rust_core import roundtrip as rust_roundtrip
from .adapters.spire_presentation import roundtrip as spire_presentation_roundtrip
from .adapters.syncfusion import roundtrip as syncfusion_roundtrip
from .benchmark_runtime import elapsed_ms as _elapsed_ms, stamp as _stamp
from .benchmark_validation import _roundtrip_details, _validate_output
from .compare import compare_semantics, semantic_mismatch_preview
from .extractor import extract_semantics
from .native import inspect as native_inspect
from .native import roundtrip as native_roundtrip
from .native import summarize as native_summarize
from .rust_parity import normalize_python_oracle, normalize_rust_summary


def _bench_semantic_extract(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    start = perf_counter()
    actual = extract_semantics(fixture_path).to_dict()
    elapsed_ms = _elapsed_ms(start)
    if not expected_path.exists():
        ok = len(actual["slides"]) >= 1
        return elapsed_ms, {
            "ok": ok,
            "semantic_pass": ok,
            "semantic_score": 1.0 if ok else 0.0,
            "mismatch_count": 0 if ok else 1,
            "comparison_scope": "extractability-only; no checked-in semantic oracle",
            "slide_count": len(actual["slides"]),
            "part_count": actual["part_count"],
        }
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    comparison = compare_semantics(fixture_id, expected, actual)
    return elapsed_ms, {
        "ok": comparison.passed,
        "semantic_pass": comparison.passed,
        "semantic_score": comparison.score,
        "mismatch_count": len(comparison.mismatches),
        "semantic_mismatches": semantic_mismatch_preview(comparison),
        "semantic_mismatch_preview_truncated": len(comparison.mismatches) > 3,
    }


def _bench_python_pptx_summary(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    start = perf_counter()
    summary = python_pptx_summarize(fixture_path)
    elapsed_ms = _elapsed_ms(start)
    if expected_path.exists():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        expected_slide_count = len(expected["slides"])
        comparison_scope = "checked-in semantic oracle slide count"
    else:
        expected_slide_count = len(extract_semantics(fixture_path).slides)
        comparison_scope = "extractor-derived slide count; no checked-in semantic oracle"
    return elapsed_ms, {
        "ok": summary.slide_count == expected_slide_count,
        "semantic_pass": summary.slide_count == expected_slide_count,
        "comparison_scope": comparison_scope,
        "slide_count": summary.slide_count,
        "expected_slide_count": expected_slide_count,
        "shape_count": summary.shape_count,
        "text_count": len(summary.texts),
    }


def _bench_python_pptx_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"python-pptx-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    python_pptx_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    return elapsed_ms, _roundtrip_details(fixture_id, fixture_path, out, validate_openxml)


def _bench_openxml_sdk_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"openxml-sdk-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    result = openxml_sdk_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    details = _roundtrip_details(fixture_id, fixture_path, out, validate_openxml)
    details.update(
        {
            "part_count": result.part_count,
            "has_vba": result.has_vba,
            "sdk_versions": result.sdk_versions,
        }
    )
    return elapsed_ms, details


def _bench_pptxgenjs_generate(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"pptxgenjs-{_output_stem(fixture_id, fixture_path)}-{_stamp()}.pptx"
    start = perf_counter()
    result = pptxgenjs_generate(fixture_id, fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    generated = extract_semantics(out)
    validation = _validate_output(out) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    ok = Path(result.path).exists() and result.bytes > 0 and len(generated.slides) >= 1 and openxml_ok
    return elapsed_ms, {
        "ok": ok,
        "semantic_pass": len(generated.slides) >= 1,
        "semantic_score": 1.0 if len(generated.slides) >= 1 else 0.0,
        "comparison_scope": "generated output extractable; not fixture parity or round-trip preservation",
        "generated_slide_count": len(generated.slides),
        "generated_part_count": generated.part_count,
        "bytes": result.bytes,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _bench_apache_poi_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"apache-poi-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    result = apache_poi_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    details = _roundtrip_details(fixture_id, fixture_path, out, validate_openxml)
    details.update(
        {
            "part_count": result.part_count,
            "has_vba": result.has_vba,
            "sdk_versions": result.sdk_versions,
        }
    )
    return elapsed_ms, details


def _bench_aspose_slides_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"aspose-slides-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    result = aspose_slides_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    details = _roundtrip_details(fixture_id, fixture_path, out, validate_openxml)
    details.update(
        {
            "part_count": result.part_count,
            "has_vba": result.has_vba,
        }
    )
    return elapsed_ms, details


def _bench_aspose_docker_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"aspose-docker-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    result = aspose_docker_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    details = _roundtrip_details(fixture_id, fixture_path, out, validate_openxml)
    details.update(
        {
            "part_count": result.part_count,
            "has_vba": result.has_vba,
            "command": result.command,
            "image": result.image,
            "sdk_versions": result.sdk_versions,
        }
    )
    return elapsed_ms, details


def _bench_spire_presentation_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"spire-presentation-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    result = spire_presentation_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    details = _roundtrip_details(fixture_id, fixture_path, out, validate_openxml)
    details.update(
        {
            "part_count": result.part_count,
            "has_vba": result.has_vba,
            "sdk_versions": result.sdk_versions,
        }
    )
    return elapsed_ms, details


def _bench_syncfusion_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = (
        tmp_path
        / f"syncfusion-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    )
    start = perf_counter()
    result = syncfusion_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    details = _roundtrip_details(fixture_id, fixture_path, out, validate_openxml)
    details.update(
        {
            "part_count": result.part_count,
            "has_vba": result.has_vba,
            "command": result.command,
            "trial_allowed": result.trial_allowed,
            "sdk_versions": result.sdk_versions,
        }
    )
    return elapsed_ms, details


def _bench_external_command_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"external-command-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    result = external_command_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    details = _roundtrip_details(fixture_id, fixture_path, out, validate_openxml)
    details.update(
        {
            "part_count": result.part_count,
            "has_vba": result.has_vba,
            "command": result.command,
            "command_executable": result.command_executable,
            "command_template_sha256": result.command_template_sha256,
            "command_arg_count": result.command_arg_count,
            "command_uses_absolute_executable": result.command_uses_absolute_executable,
            "external_sdk_name": result.external_sdk_name,
            "external_sdk_version": result.external_sdk_version,
            "sdk_versions": result.sdk_versions,
            "timeout_seconds": result.timeout_seconds,
        }
    )
    return elapsed_ms, details


def _bench_rust_core_inspect(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    expected = extract_semantics(fixture_path)
    start = perf_counter()
    result = rust_inspect(fixture_path)
    elapsed_ms = _elapsed_ms(start)
    ok = result.part_count == expected.part_count and result.has_vba == expected.has_vba
    return elapsed_ms, {
        "ok": ok,
        "semantic_pass": ok,
        "part_count": result.part_count,
        "expected_part_count": expected.part_count,
        "has_vba": result.has_vba,
        "expected_has_vba": expected.has_vba,
    }


def _bench_rust_core_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"rust-core-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    rust_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    return elapsed_ms, _roundtrip_details(fixture_id, fixture_path, out, validate_openxml, require_package_clean=True)


def _bench_native_package(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    expected = extract_semantics(fixture_path)
    start = perf_counter()
    result = native_inspect(fixture_path)
    elapsed_ms = _elapsed_ms(start)
    ok = result.part_count == expected.part_count and result.has_vba == expected.has_vba
    return elapsed_ms, {
        "ok": ok,
        "semantic_pass": ok,
        "part_count": result.part_count,
        "expected_part_count": expected.part_count,
        "has_vba": result.has_vba,
        "expected_has_vba": expected.has_vba,
    }


def _bench_native_summary(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    start = perf_counter()
    summary = native_summarize(fixture_path)
    elapsed_ms = _elapsed_ms(start)
    if expected_path.exists():
        expected = normalize_python_oracle(json.loads(expected_path.read_text(encoding="utf-8")))
        comparison_scope = "checked-in semantic oracle"
    else:
        expected = normalize_python_oracle(extract_semantics(fixture_path).to_dict())
        comparison_scope = "python extractor parity; no checked-in semantic oracle"
    comparison = compare_semantics(
        fixture_id,
        expected,
        normalize_rust_summary(summary.to_dict()),
    )
    return elapsed_ms, {
        "ok": comparison.passed,
        "semantic_pass": comparison.passed,
        "semantic_score": comparison.score,
        "mismatch_count": len(comparison.mismatches),
        "semantic_mismatches": semantic_mismatch_preview(comparison),
        "semantic_mismatch_preview_truncated": len(comparison.mismatches) > 3,
        "comparison_scope": comparison_scope,
    }


def _bench_native_roundtrip(
    fixture_id: str,
    fixture_path: Path,
    expected_path: Path,
    tmp_path: Path,
    validate_openxml: bool,
) -> tuple[float, dict[str, Any]]:
    out = tmp_path / f"native-rust-{_output_stem(fixture_id, fixture_path)}-{_stamp()}{fixture_path.suffix}"
    start = perf_counter()
    native_roundtrip(fixture_path, out)
    elapsed_ms = _elapsed_ms(start)
    return elapsed_ms, _roundtrip_details(fixture_id, fixture_path, out, validate_openxml, require_package_clean=True)


def _output_stem(fixture_id: str, fixture_path: Path) -> str:
    if fixture_id.startswith("private/"):
        return fixture_id.replace("/", "-")
    return fixture_path.stem
