"""Corpus runner for adapter/oracle evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .adapters import available_tools
from .corpus import FIXTURE_ROOT, EXPECTED_ROOT, MANIFEST_PATH, fixture_manifest
from .runner_details import _first_text_paragraph_target, _first_text_shape_target
from .runner_lanes import (
    append_fixture_results,
    libreoffice_lane,
    native_add_image_lane,
    native_add_slide_lane,
    native_add_table_lane,
    native_lane,
    native_replace_text_run_lane,
    native_roundtrip_lane,
    native_set_paragraph_text_lane,
    native_set_shape_text_lane,
    native_summary_lane,
    openxml_lane,
    powerpoint_lane,
    python_pptx_roundtrip_lane,
    rust_core_add_image_lane,
    rust_core_add_slide_lane,
    rust_core_add_table_lane,
    rust_core_lane,
    rust_core_replace_text_run_lane,
    rust_core_roundtrip_lane,
    rust_core_set_paragraph_text_lane,
    rust_core_set_shape_text_lane,
    semantic_lane,
)
from .runner_models import CorpusRun, FixtureRun, LaneResult

__all__ = [
    "CorpusRun",
    "FixtureRun",
    "LaneResult",
    "_first_text_paragraph_target",
    "_first_text_shape_target",
    "run_corpus",
    "write_corpus_report",
]


def run_corpus(
    *,
    include_python_pptx: bool = True,
    include_rust_core: bool = True,
    include_native: bool = True,
    include_libreoffice: bool = False,
    include_powerpoint: bool = False,
    required_lanes: list[str] | tuple[str, ...] | None = None,
    min_powerpoint_exported_slides: int | None = None,
    write_results: bool = False,
    output_dir: Path = Path("results/corpus/latest"),
) -> CorpusRun:
    if (
        min_powerpoint_exported_slides is not None
        and min_powerpoint_exported_slides < 1
    ):
        raise ValueError("min_powerpoint_exported_slides must be at least 1")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    tool_availability = [tool.to_dict() for tool in available_tools()]
    fixtures: list[FixtureRun] = []

    for item in fixture_manifest(MANIFEST_PATH):
        fixture_id = str(item["id"])
        rel_path = str(item["path"])
        fixture_path = FIXTURE_ROOT / rel_path
        expected_path = EXPECTED_ROOT / f"{fixture_id}.json"
        lanes = [
            semantic_lane(fixture_id, fixture_path, expected_path),
            openxml_lane(fixture_path),
        ]
        if include_python_pptx:
            lanes.append(python_pptx_roundtrip_lane(fixture_id, fixture_path))
        if include_rust_core:
            lanes.append(rust_core_lane(fixture_path))
            lanes.append(rust_core_roundtrip_lane(fixture_id, fixture_path))
            lanes.append(rust_core_replace_text_run_lane(fixture_path))
            lanes.append(rust_core_set_shape_text_lane(fixture_path))
            lanes.append(rust_core_set_paragraph_text_lane(fixture_path))
            lanes.append(rust_core_add_slide_lane(fixture_path))
            lanes.append(rust_core_add_image_lane(fixture_path))
            lanes.append(rust_core_add_table_lane(fixture_path))
        if include_native:
            lanes.append(native_lane(fixture_path))
            lanes.append(native_summary_lane(fixture_id, fixture_path, expected_path))
            lanes.append(native_roundtrip_lane(fixture_id, fixture_path))
            lanes.append(native_replace_text_run_lane(fixture_path))
            lanes.append(native_set_shape_text_lane(fixture_path))
            lanes.append(native_set_paragraph_text_lane(fixture_path))
            lanes.append(native_add_slide_lane(fixture_path))
            lanes.append(native_add_image_lane(fixture_path))
            lanes.append(native_add_table_lane(fixture_path))
        if include_libreoffice:
            lanes.append(libreoffice_lane(fixture_path, output_dir / "libreoffice"))
        if include_powerpoint:
            lanes.append(powerpoint_lane(fixture_path, output_dir / "powerpoint" / fixture_path.stem))
        fixture_run = FixtureRun(fixture_id=fixture_id, path=str(fixture_path), lanes=lanes)
        fixtures.append(fixture_run)
        if write_results:
            append_fixture_results(run_id, fixture_run)

    return CorpusRun(
        run_id=run_id,
        fixtures=fixtures,
        tool_availability=tool_availability,
        required_lanes=tuple(required_lanes or ()),
        min_powerpoint_exported_slides=min_powerpoint_exported_slides,
    )


def write_corpus_report(run: CorpusRun, output_dir: Path = Path("results/corpus/latest")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run.json").write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(run.to_markdown(), encoding="utf-8")
