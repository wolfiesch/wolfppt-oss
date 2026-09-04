"""Corpus runner lane implementations."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from .adapters.libreoffice import find_soffice, render_pdf
from .adapters.openxml import validate as validate_openxml
from .adapters.powerpoint import export_png as powerpoint_export_png
from .adapters.powerpoint import powerpoint_available
from .adapters.python_pptx import roundtrip as python_pptx_roundtrip
from .adapters.rust_core import add_image as rust_add_image
from .adapters.rust_core import add_slide as rust_add_slide
from .adapters.rust_core import add_table as rust_add_table
from .adapters.rust_core import inspect as rust_inspect
from .adapters.rust_core import replace_text_run as rust_replace_text_run
from .adapters.rust_core import roundtrip as rust_roundtrip
from .adapters.rust_core import rust_cli_available
from .adapters.rust_core import set_paragraph_text as rust_set_paragraph_text
from .adapters.rust_core import set_shape_text as rust_set_shape_text
from .compare import DEFAULT_ROUNDTRIP_IGNORES, compare_semantics
from .extractor import extract_semantics
from .native import add_image as native_add_image
from .native import add_slide as native_add_slide
from .native import add_table as native_add_table
from .native import inspect as native_inspect
from .native import native_available
from .native import replace_text_run as native_replace_text_run
from .native import roundtrip as native_roundtrip
from .native import set_paragraph_text as native_set_paragraph_text
from .native import set_shape_text as native_set_shape_text
from .package_diff import diff_packages
from .results import HarnessResult, append_result
from .runner_details import (
    PARAGRAPH_TEXT_REPLACEMENT,
    SHAPE_TEXT_REPLACEMENT,
    _first_text_paragraph_target,
    _first_text_shape_target,
    _image_add_details,
    _paragraph_text_set_details,
    _shape_text_set_details,
    _slide_add_details,
    _table_add_details,
    _text_run_replace_details,
    _write_sample_png,
)
from .runner_models import FixtureRun, LaneResult
from .rust_parity import compare_native_summary


def semantic_lane(fixture_id: str, fixture_path: Path, expected_path: Path) -> LaneResult:
    start = perf_counter()
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual = extract_semantics(fixture_path).to_dict()
    comparison = compare_semantics(fixture_id, expected, actual)
    return LaneResult(
        name="semantic-oracle",
        status="pass" if comparison.passed else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=comparison.to_dict(),
    )


def openxml_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    try:
        result = validate_openxml(fixture_path)
    except RuntimeError as exc:
        return LaneResult("openxml-validation", "skip", _elapsed_ms(start), {"reason": str(exc)})
    return LaneResult(
        name="openxml-validation",
        status="pass" if result.valid else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=result.to_dict(),
    )


def python_pptx_roundtrip_lane(fixture_id: str, fixture_path: Path) -> LaneResult:
    start = perf_counter()
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            python_pptx_roundtrip(fixture_path, out)
            original_semantics = extract_semantics(fixture_path).to_dict()
            roundtrip_semantics = extract_semantics(out).to_dict()
            comparison = compare_semantics(
                fixture_id,
                original_semantics,
                roundtrip_semantics,
                ignore_paths=DEFAULT_ROUNDTRIP_IGNORES,
            )
            package_diff = diff_packages(fixture_path, out)
    except RuntimeError as exc:
        return LaneResult("python-pptx-roundtrip", "skip", _elapsed_ms(start), {"reason": str(exc)})
    return LaneResult(
        name="python-pptx-roundtrip",
        status="pass" if comparison.passed else "fail",
        elapsed_ms=_elapsed_ms(start),
        details={
            "semantic": comparison.to_dict(),
            "package_diff": package_diff.to_dict(),
        },
    )


def libreoffice_lane(fixture_path: Path, out_dir: Path) -> LaneResult:
    start = perf_counter()
    if find_soffice() is None:
        return LaneResult("libreoffice-render", "skip", _elapsed_ms(start), {"reason": "soffice not found"})
    try:
        result = render_pdf(fixture_path, out_dir)
    except RuntimeError as exc:
        return LaneResult("libreoffice-render", "skip", _elapsed_ms(start), {"reason": str(exc)})
    return LaneResult(
        name="libreoffice-render",
        status="pass" if result.ok else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=result.to_dict(),
    )


def rust_core_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not rust_cli_available():
        return LaneResult("rust-core-inspect", "skip", _elapsed_ms(start), {"reason": "cargo/Cargo.toml not found"})
    try:
        result = rust_inspect(fixture_path)
    except RuntimeError as exc:
        return LaneResult("rust-core-inspect", "fail", _elapsed_ms(start), {"reason": str(exc)})
    expected = extract_semantics(fixture_path)
    ok = result.part_count == expected.part_count and result.has_vba == expected.has_vba
    return LaneResult(
        name="rust-core-inspect",
        status="pass" if ok else "fail",
        elapsed_ms=_elapsed_ms(start),
        details={
            "part_count": result.part_count,
            "expected_part_count": expected.part_count,
            "has_vba": result.has_vba,
            "expected_has_vba": expected.has_vba,
        },
    )


def rust_core_roundtrip_lane(fixture_id: str, fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not rust_cli_available():
        return LaneResult("rust-core-roundtrip", "skip", _elapsed_ms(start), {"reason": "cargo/Cargo.toml not found"})
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = rust_roundtrip(fixture_path, out)
            original_semantics = extract_semantics(fixture_path).to_dict()
            roundtrip_semantics = extract_semantics(out).to_dict()
            comparison = compare_semantics(
                fixture_id,
                original_semantics,
                roundtrip_semantics,
                ignore_paths=DEFAULT_ROUNDTRIP_IGNORES,
            )
            package_diff = diff_packages(fixture_path, out)
    except RuntimeError as exc:
        return LaneResult("rust-core-roundtrip", "fail", _elapsed_ms(start), {"reason": str(exc)})
    return LaneResult(
        name="rust-core-roundtrip",
        status="pass" if comparison.passed and package_diff.clean else "fail",
        elapsed_ms=_elapsed_ms(start),
        details={
            "part_count": result.part_count,
            "has_vba": result.has_vba,
            "semantic": comparison.to_dict(),
            "package_diff": package_diff.to_dict(),
        },
    )


def rust_core_replace_text_run_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not rust_cli_available():
        return LaneResult(
            "rust-core-replace-text-run",
            "skip",
            _elapsed_ms(start),
            {"reason": "cargo/Cargo.toml not found"},
        )
    original = extract_semantics(fixture_path)
    if not original.slides or not original.slides[0].texts:
        return LaneResult(
            "rust-core-replace-text-run",
            "skip",
            _elapsed_ms(start),
            {"reason": "fixture has no slide text runs"},
        )
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = rust_replace_text_run(fixture_path, out, 0, 0, "WolfPPT Run")
            details = _text_run_replace_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "rust-core-replace-text-run",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="rust-core-replace-text-run",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def rust_core_set_shape_text_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not rust_cli_available():
        return LaneResult(
            "rust-core-set-shape-text",
            "skip",
            _elapsed_ms(start),
            {"reason": "cargo/Cargo.toml not found"},
        )
    target = _first_text_shape_target(fixture_path)
    if target is None:
        return LaneResult(
            "rust-core-set-shape-text",
            "skip",
            _elapsed_ms(start),
            {"reason": "fixture has no editable text shape"},
        )
    slide_index, shape_index = target
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = rust_set_shape_text(
                fixture_path,
                out,
                slide_index,
                shape_index,
                SHAPE_TEXT_REPLACEMENT,
            )
            details = _shape_text_set_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "rust-core-set-shape-text",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="rust-core-set-shape-text",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def rust_core_set_paragraph_text_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not rust_cli_available():
        return LaneResult(
            "rust-core-set-paragraph-text",
            "skip",
            _elapsed_ms(start),
            {"reason": "cargo/Cargo.toml not found"},
        )
    target = _first_text_paragraph_target(fixture_path)
    if target is None:
        return LaneResult(
            "rust-core-set-paragraph-text",
            "skip",
            _elapsed_ms(start),
            {"reason": "fixture has no editable text paragraph"},
        )
    slide_index, shape_index, paragraph_index = target
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = rust_set_paragraph_text(
                fixture_path,
                out,
                slide_index,
                shape_index,
                paragraph_index,
                PARAGRAPH_TEXT_REPLACEMENT,
            )
            details = _paragraph_text_set_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "rust-core-set-paragraph-text",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="rust-core-set-paragraph-text",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def rust_core_add_slide_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not rust_cli_available():
        return LaneResult(
            "rust-core-add-slide",
            "skip",
            _elapsed_ms(start),
            {"reason": "cargo/Cargo.toml not found"},
        )
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = rust_add_slide(fixture_path, out)
            details = _slide_add_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "rust-core-add-slide",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="rust-core-add-slide",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def rust_core_add_image_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not rust_cli_available():
        return LaneResult(
            "rust-core-add-image",
            "skip",
            _elapsed_ms(start),
            {"reason": "cargo/Cargo.toml not found"},
        )
    try:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / fixture_path.name
            image = _write_sample_png(tmp_path)
            result = rust_add_image(fixture_path, out, 0, image, 0, 0, 914400, 914400)
            details = _image_add_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "rust-core-add-image",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="rust-core-add-image",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def rust_core_add_table_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not rust_cli_available():
        return LaneResult(
            "rust-core-add-table",
            "skip",
            _elapsed_ms(start),
            {"reason": "cargo/Cargo.toml not found"},
        )
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = rust_add_table(fixture_path, out, 0, 2, 2, 0, 0, 2743200, 914400)
            details = _table_add_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "rust-core-add-table",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="rust-core-add-table",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def native_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-package",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    try:
        result = native_inspect(fixture_path)
    except RuntimeError as exc:
        return LaneResult("native-rust-package", "fail", _elapsed_ms(start), {"reason": str(exc)})
    expected = extract_semantics(fixture_path)
    ok = result.part_count == expected.part_count and result.has_vba == expected.has_vba
    return LaneResult(
        name="native-rust-package",
        status="pass" if ok else "fail",
        elapsed_ms=_elapsed_ms(start),
        details={
            "part_count": result.part_count,
            "expected_part_count": expected.part_count,
            "has_vba": result.has_vba,
            "expected_has_vba": expected.has_vba,
        },
    )


def native_summary_lane(fixture_id: str, fixture_path: Path, expected_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-summary",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    try:
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        comparison = compare_native_summary(fixture_id, fixture_path, expected)
    except RuntimeError as exc:
        return LaneResult("native-rust-summary", "fail", _elapsed_ms(start), {"reason": str(exc)})
    return LaneResult(
        name="native-rust-summary",
        status="pass" if comparison.passed else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=comparison.to_dict(),
    )


def native_roundtrip_lane(fixture_id: str, fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-roundtrip",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = native_roundtrip(fixture_path, out)
            original_semantics = extract_semantics(fixture_path).to_dict()
            roundtrip_semantics = extract_semantics(out).to_dict()
            comparison = compare_semantics(
                fixture_id,
                original_semantics,
                roundtrip_semantics,
                ignore_paths=DEFAULT_ROUNDTRIP_IGNORES,
            )
            package_diff = diff_packages(fixture_path, out)
    except RuntimeError as exc:
        return LaneResult("native-rust-roundtrip", "fail", _elapsed_ms(start), {"reason": str(exc)})
    return LaneResult(
        name="native-rust-roundtrip",
        status="pass" if comparison.passed and package_diff.clean else "fail",
        elapsed_ms=_elapsed_ms(start),
        details={
            "part_count": result.part_count,
            "has_vba": result.has_vba,
            "semantic": comparison.to_dict(),
            "package_diff": package_diff.to_dict(),
        },
    )


def powerpoint_lane(fixture_path: Path, out_dir: Path) -> LaneResult:
    start = perf_counter()
    if not powerpoint_available():
        return LaneResult(
            "powerpoint-render",
            "skip",
            _elapsed_ms(start),
            {"reason": "Microsoft PowerPoint.app was not found"},
        )
    result = powerpoint_export_png(fixture_path, out_dir)
    return LaneResult(
        name="powerpoint-render",
        status="pass" if result.ok else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=result.to_dict(),
    )


def native_replace_text_run_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-replace-text-run",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    original = extract_semantics(fixture_path)
    if not original.slides or not original.slides[0].texts:
        return LaneResult(
            "native-rust-replace-text-run",
            "skip",
            _elapsed_ms(start),
            {"reason": "fixture has no slide text runs"},
        )
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = native_replace_text_run(fixture_path, out, 0, 0, "WolfPPT Run")
            details = _text_run_replace_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "native-rust-replace-text-run",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="native-rust-replace-text-run",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def native_set_shape_text_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-set-shape-text",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    target = _first_text_shape_target(fixture_path)
    if target is None:
        return LaneResult(
            "native-rust-set-shape-text",
            "skip",
            _elapsed_ms(start),
            {"reason": "fixture has no editable text shape"},
        )
    slide_index, shape_index = target
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = native_set_shape_text(
                fixture_path,
                out,
                slide_index,
                shape_index,
                SHAPE_TEXT_REPLACEMENT,
            )
            details = _shape_text_set_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "native-rust-set-shape-text",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="native-rust-set-shape-text",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def native_set_paragraph_text_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-set-paragraph-text",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    target = _first_text_paragraph_target(fixture_path)
    if target is None:
        return LaneResult(
            "native-rust-set-paragraph-text",
            "skip",
            _elapsed_ms(start),
            {"reason": "fixture has no editable text paragraph"},
        )
    slide_index, shape_index, paragraph_index = target
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = native_set_paragraph_text(
                fixture_path,
                out,
                slide_index,
                shape_index,
                paragraph_index,
                PARAGRAPH_TEXT_REPLACEMENT,
            )
            details = _paragraph_text_set_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "native-rust-set-paragraph-text",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="native-rust-set-paragraph-text",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def native_add_slide_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-add-slide",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = native_add_slide(fixture_path, out)
            details = _slide_add_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "native-rust-add-slide",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="native-rust-add-slide",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def native_add_image_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-add-image",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    try:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / fixture_path.name
            image = _write_sample_png(tmp_path)
            result = native_add_image(fixture_path, out, 0, image, 0, 0, 914400, 914400)
            details = _image_add_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "native-rust-add-image",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="native-rust-add-image",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def native_add_table_lane(fixture_path: Path) -> LaneResult:
    start = perf_counter()
    if not native_available():
        return LaneResult(
            "native-rust-add-table",
            "skip",
            _elapsed_ms(start),
            {"reason": "wolfppt_native is not installed"},
        )
    try:
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / fixture_path.name
            result = native_add_table(fixture_path, out, 0, 2, 2, 0, 0, 2743200, 914400)
            details = _table_add_details(fixture_path, out, result.to_dict())
    except RuntimeError as exc:
        return LaneResult(
            "native-rust-add-table",
            "fail",
            _elapsed_ms(start),
            {"reason": str(exc)},
        )
    return LaneResult(
        name="native-rust-add-table",
        status="pass" if details["ok"] else "fail",
        elapsed_ms=_elapsed_ms(start),
        details=details,
    )


def append_fixture_results(run_id: str, fixture: FixtureRun) -> None:
    for lane in fixture.lanes:
        append_result(
            HarnessResult(
                run_id=run_id,
                fixture=fixture.fixture_id,
                adapter=lane.name,
                operation="corpus-run",
                status=lane.status,
                elapsed_ms=lane.elapsed_ms,
                metadata=lane.details,
            )
        )


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)
