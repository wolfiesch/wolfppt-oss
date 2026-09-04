"""Command line interface for the WolfPPT harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters.libreoffice import render_pdf
from .adapters.openxml import validate as validate_openxml
from .adapters.powerpoint import export_png as powerpoint_export_png
from .adapters.python_pptx import roundtrip as python_pptx_roundtrip
from .adapters.python_pptx import summarize as python_pptx_summarize
from .adapters.rust_core import add_image as rust_add_image
from .adapters.rust_core import add_slide as rust_add_slide
from .adapters.rust_core import add_table as rust_add_table
from .adapters.rust_core import inspect as rust_inspect
from .adapters.rust_core import replace_image as rust_replace_image
from .adapters.rust_core import replace_table_cell as rust_replace_table_cell
from .adapters.rust_core import replace_text as rust_replace_text
from .adapters.rust_core import replace_text_run as rust_replace_text_run
from .adapters.rust_core import roundtrip as rust_roundtrip
from .adapters.rust_core import set_paragraph_text as rust_set_paragraph_text
from .adapters.rust_core import set_shape_text as rust_set_shape_text
from .benchmark import run_benchmarks, write_benchmark_report
from .cli_benchmark_profiles import (
    handle_benchmark_adapters_command,
    handle_benchmark_profile_command,
    handle_benchmark_profiles_command,
    register_benchmark_profile_commands,
)
from .cli_api_surface import (
    handle_python_api_surface_command,
    register_python_api_surface_command,
)
from .cli_capability_plan import (
    handle_capability_check_command,
    handle_capability_plan_command,
    register_capability_plan_commands,
)
from .cli_helpers import parse_key_value_int_args as _parse_key_value_int_args
from .cli_helpers import split_csv_args as _split_csv_args
from .cli_private_decks import (
    handle_private_decks_command,
    handle_private_report_check_command,
    register_private_deck_commands,
)
from .cli_tools import handle_tools_command, register_tools_command
from .cli_validation import (
    handle_validate_command,
    handle_validate_impacted_command,
    register_validation_commands,
)
from .corpus import generate_corpus
from .dropin_coverage import (
    DEFAULT_REQUIRED_DOMAINS,
    dropin_behavior_coverage,
    render_dropin_behavior_coverage_markdown,
)
from .extractor import extract_semantics
from .matrix import write_matrix
from .native import add_image as native_add_image
from .native import add_slide as native_add_slide
from .native import add_table as native_add_table
from .native import inspect as native_inspect
from .native import replace_image as native_replace_image
from .native import replace_table_cell as native_replace_table_cell
from .native import replace_text as native_replace_text
from .native import replace_text_run as native_replace_text_run
from .native import roundtrip as native_roundtrip
from .native import set_paragraph_text as native_set_paragraph_text
from .native import set_shape_text as native_set_shape_text
from .native import summarize as native_summarize
from .package_diff import diff_packages, package_manifest
from .results import HarnessResult, append_result
from .runner import run_corpus, write_corpus_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wolfppt-harness")
    sub = parser.add_subparsers(dest="command", required=True)

    extract_parser = sub.add_parser(
        "extract", help="extract semantic JSON from a PPTX/PPTM"
    )
    extract_parser.add_argument("path", type=Path)

    manifest_parser = sub.add_parser(
        "manifest", help="emit normalized package manifest JSON"
    )
    manifest_parser.add_argument("path", type=Path)

    diff_parser = sub.add_parser("diff", help="compare two PPTX/PPTM packages")
    diff_parser.add_argument("left", type=Path)
    diff_parser.add_argument("right", type=Path)

    pptx_summary_parser = sub.add_parser(
        "python-pptx-summary", help="summarize a deck via python-pptx"
    )
    pptx_summary_parser.add_argument("path", type=Path)

    pptx_roundtrip_parser = sub.add_parser(
        "python-pptx-roundtrip", help="round-trip a deck via python-pptx"
    )
    pptx_roundtrip_parser.add_argument("input", type=Path)
    pptx_roundtrip_parser.add_argument("output", type=Path)

    validate_parser = sub.add_parser(
        "validate-openxml", help="validate a deck with Open XML SDK"
    )
    validate_parser.add_argument("path", type=Path)

    rust_parser = sub.add_parser(
        "rust-inspect", help="inspect a deck using the Rust core CLI"
    )
    rust_parser.add_argument("path", type=Path)

    rust_roundtrip_parser = sub.add_parser(
        "rust-roundtrip", help="round-trip a deck using the Rust core CLI"
    )
    rust_roundtrip_parser.add_argument("input", type=Path)
    rust_roundtrip_parser.add_argument("output", type=Path)

    rust_add_slide_parser = sub.add_parser(
        "rust-add-slide", help="append a blank slide using an existing layout"
    )
    rust_add_slide_parser.add_argument("input", type=Path)
    rust_add_slide_parser.add_argument("output", type=Path)
    rust_add_slide_parser.add_argument("layout_index", nargs="?", type=int)

    rust_replace_parser = sub.add_parser(
        "rust-replace-text", help="replace slide text using the Rust core CLI"
    )
    rust_replace_parser.add_argument("input", type=Path)
    rust_replace_parser.add_argument("output", type=Path)
    rust_replace_parser.add_argument("search")
    rust_replace_parser.add_argument("replacement")
    rust_replace_parser.add_argument("--slide-index", type=int)

    rust_replace_run_parser = sub.add_parser(
        "rust-replace-text-run", help="replace one slide text run via Rust core CLI"
    )
    rust_replace_run_parser.add_argument("input", type=Path)
    rust_replace_run_parser.add_argument("output", type=Path)
    rust_replace_run_parser.add_argument("slide_index", type=int)
    rust_replace_run_parser.add_argument("run_index", type=int)
    rust_replace_run_parser.add_argument("replacement")

    rust_shape_text_parser = sub.add_parser(
        "rust-set-shape-text", help="set one shape's text via Rust core CLI"
    )
    rust_shape_text_parser.add_argument("input", type=Path)
    rust_shape_text_parser.add_argument("output", type=Path)
    rust_shape_text_parser.add_argument("slide_index", type=int)
    rust_shape_text_parser.add_argument("shape_index", type=int)
    rust_shape_text_parser.add_argument("replacement")

    rust_paragraph_text_parser = sub.add_parser(
        "rust-set-paragraph-text", help="set one shape paragraph via Rust core CLI"
    )
    rust_paragraph_text_parser.add_argument("input", type=Path)
    rust_paragraph_text_parser.add_argument("output", type=Path)
    rust_paragraph_text_parser.add_argument("slide_index", type=int)
    rust_paragraph_text_parser.add_argument("shape_index", type=int)
    rust_paragraph_text_parser.add_argument("paragraph_index", type=int)
    rust_paragraph_text_parser.add_argument("replacement")

    rust_image_parser = sub.add_parser(
        "rust-replace-image", help="replace an existing slide image via Rust core CLI"
    )
    rust_image_parser.add_argument("input", type=Path)
    rust_image_parser.add_argument("output", type=Path)
    rust_image_parser.add_argument("relationship_id")
    rust_image_parser.add_argument("image", type=Path)
    rust_image_parser.add_argument("--slide-index", type=int)

    rust_add_image_parser = sub.add_parser(
        "rust-add-image", help="add a picture shape via Rust core CLI"
    )
    rust_add_image_parser.add_argument("input", type=Path)
    rust_add_image_parser.add_argument("output", type=Path)
    rust_add_image_parser.add_argument("slide_index", type=int)
    rust_add_image_parser.add_argument("image", type=Path)
    rust_add_image_parser.add_argument("x_emu", type=int)
    rust_add_image_parser.add_argument("y_emu", type=int)
    rust_add_image_parser.add_argument("cx_emu", type=int)
    rust_add_image_parser.add_argument("cy_emu", type=int)

    rust_table_parser = sub.add_parser(
        "rust-replace-table-cell", help="replace table cell text via Rust core CLI"
    )
    rust_table_parser.add_argument("input", type=Path)
    rust_table_parser.add_argument("output", type=Path)
    rust_table_parser.add_argument("slide_index", type=int)
    rust_table_parser.add_argument("table_index", type=int)
    rust_table_parser.add_argument("row_index", type=int)
    rust_table_parser.add_argument("col_index", type=int)
    rust_table_parser.add_argument("replacement")

    rust_add_table_parser = sub.add_parser(
        "rust-add-table", help="add a basic table shape via Rust core CLI"
    )
    rust_add_table_parser.add_argument("input", type=Path)
    rust_add_table_parser.add_argument("output", type=Path)
    rust_add_table_parser.add_argument("slide_index", type=int)
    rust_add_table_parser.add_argument("rows", type=int)
    rust_add_table_parser.add_argument("cols", type=int)
    rust_add_table_parser.add_argument("x_emu", type=int)
    rust_add_table_parser.add_argument("y_emu", type=int)
    rust_add_table_parser.add_argument("cx_emu", type=int)
    rust_add_table_parser.add_argument("cy_emu", type=int)

    native_parser = sub.add_parser(
        "native-inspect", help="inspect a deck using the native Rust Python module"
    )
    native_parser.add_argument("path", type=Path)

    native_summary_parser = sub.add_parser(
        "native-summary", help="summarize a deck using the native Rust Python module"
    )
    native_summary_parser.add_argument("path", type=Path)

    native_roundtrip_parser = sub.add_parser(
        "native-roundtrip", help="round-trip a deck using the native Rust module"
    )
    native_roundtrip_parser.add_argument("input", type=Path)
    native_roundtrip_parser.add_argument("output", type=Path)

    native_add_slide_parser = sub.add_parser(
        "native-add-slide", help="append a blank slide using native Rust"
    )
    native_add_slide_parser.add_argument("input", type=Path)
    native_add_slide_parser.add_argument("output", type=Path)
    native_add_slide_parser.add_argument("layout_index", nargs="?", type=int)

    native_replace_parser = sub.add_parser(
        "native-replace-text", help="replace slide text using the native Rust module"
    )
    native_replace_parser.add_argument("input", type=Path)
    native_replace_parser.add_argument("output", type=Path)
    native_replace_parser.add_argument("search")
    native_replace_parser.add_argument("replacement")
    native_replace_parser.add_argument("--slide-index", type=int)

    native_replace_run_parser = sub.add_parser(
        "native-replace-text-run", help="replace one slide text run via native Rust"
    )
    native_replace_run_parser.add_argument("input", type=Path)
    native_replace_run_parser.add_argument("output", type=Path)
    native_replace_run_parser.add_argument("slide_index", type=int)
    native_replace_run_parser.add_argument("run_index", type=int)
    native_replace_run_parser.add_argument("replacement")

    native_shape_text_parser = sub.add_parser(
        "native-set-shape-text", help="set one shape's text via native Rust"
    )
    native_shape_text_parser.add_argument("input", type=Path)
    native_shape_text_parser.add_argument("output", type=Path)
    native_shape_text_parser.add_argument("slide_index", type=int)
    native_shape_text_parser.add_argument("shape_index", type=int)
    native_shape_text_parser.add_argument("replacement")

    native_paragraph_text_parser = sub.add_parser(
        "native-set-paragraph-text", help="set one shape paragraph via native Rust"
    )
    native_paragraph_text_parser.add_argument("input", type=Path)
    native_paragraph_text_parser.add_argument("output", type=Path)
    native_paragraph_text_parser.add_argument("slide_index", type=int)
    native_paragraph_text_parser.add_argument("shape_index", type=int)
    native_paragraph_text_parser.add_argument("paragraph_index", type=int)
    native_paragraph_text_parser.add_argument("replacement")

    native_image_parser = sub.add_parser(
        "native-replace-image", help="replace an existing slide image via native Rust"
    )
    native_image_parser.add_argument("input", type=Path)
    native_image_parser.add_argument("output", type=Path)
    native_image_parser.add_argument("relationship_id")
    native_image_parser.add_argument("image", type=Path)
    native_image_parser.add_argument("--slide-index", type=int)

    native_add_image_parser = sub.add_parser(
        "native-add-image", help="add a picture shape via native Rust"
    )
    native_add_image_parser.add_argument("input", type=Path)
    native_add_image_parser.add_argument("output", type=Path)
    native_add_image_parser.add_argument("slide_index", type=int)
    native_add_image_parser.add_argument("image", type=Path)
    native_add_image_parser.add_argument("x_emu", type=int)
    native_add_image_parser.add_argument("y_emu", type=int)
    native_add_image_parser.add_argument("cx_emu", type=int)
    native_add_image_parser.add_argument("cy_emu", type=int)

    native_table_parser = sub.add_parser(
        "native-replace-table-cell", help="replace table cell text via native Rust"
    )
    native_table_parser.add_argument("input", type=Path)
    native_table_parser.add_argument("output", type=Path)
    native_table_parser.add_argument("slide_index", type=int)
    native_table_parser.add_argument("table_index", type=int)
    native_table_parser.add_argument("row_index", type=int)
    native_table_parser.add_argument("col_index", type=int)
    native_table_parser.add_argument("replacement")

    native_add_table_parser = sub.add_parser(
        "native-add-table", help="add a basic table shape via native Rust"
    )
    native_add_table_parser.add_argument("input", type=Path)
    native_add_table_parser.add_argument("output", type=Path)
    native_add_table_parser.add_argument("slide_index", type=int)
    native_add_table_parser.add_argument("rows", type=int)
    native_add_table_parser.add_argument("cols", type=int)
    native_add_table_parser.add_argument("x_emu", type=int)
    native_add_table_parser.add_argument("y_emu", type=int)
    native_add_table_parser.add_argument("cx_emu", type=int)
    native_add_table_parser.add_argument("cy_emu", type=int)

    render_parser = sub.add_parser(
        "render-libreoffice", help="render a deck to PDF using LibreOffice"
    )
    render_parser.add_argument("path", type=Path)
    render_parser.add_argument(
        "--out-dir", type=Path, default=Path("results/rendered/libreoffice")
    )

    powerpoint_parser = sub.add_parser(
        "render-powerpoint", help="export slide PNGs using Microsoft PowerPoint"
    )
    powerpoint_parser.add_argument("path", type=Path)
    powerpoint_parser.add_argument(
        "--out-dir", type=Path, default=Path("results/rendered/powerpoint")
    )

    matrix_parser = sub.add_parser("matrix", help="regenerate compatibility matrix")
    matrix_parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the checked-in matrix differs from generated output",
    )

    register_python_api_surface_command(sub)

    record_parser = sub.add_parser(
        "record", help="append one benchmark/parity result row"
    )
    record_parser.add_argument("--fixture", required=True)
    record_parser.add_argument("--adapter", required=True)
    record_parser.add_argument("--operation", required=True)
    record_parser.add_argument("--status", required=True)
    record_parser.add_argument("--known-gap")

    sub.add_parser("corpus", help="generate deterministic Phase 1 fixtures and oracles")

    run_parser = sub.add_parser(
        "run-corpus", help="run corpus through configured oracle lanes"
    )
    run_parser.add_argument(
        "--json", action="store_true", help="print JSON instead of Markdown"
    )
    run_parser.add_argument(
        "--write-results",
        action="store_true",
        help="append lane rows to results/runs.jsonl",
    )
    run_parser.add_argument(
        "--write-report",
        action="store_true",
        help="write results/corpus/latest report files",
    )
    run_parser.add_argument(
        "--include-libreoffice",
        action="store_true",
        help="include LibreOffice PDF render smoke",
    )
    run_parser.add_argument(
        "--include-powerpoint",
        action="store_true",
        help="include Microsoft PowerPoint PNG export",
    )
    run_parser.add_argument(
        "--require-lane",
        action="append",
        dest="required_lanes",
        help=(
            "fail unless this corpus lane is present and passes for every fixture; "
            "repeat or pass comma-separated names"
        ),
    )
    run_parser.add_argument(
        "--min-powerpoint-exported-slides",
        type=int,
        help="fail unless PowerPoint render lanes export at least this many slide PNGs",
    )
    run_parser.add_argument(
        "--skip-python-pptx",
        action="store_true",
        help="skip python-pptx round-trip lane",
    )
    run_parser.add_argument(
        "--skip-rust-core", action="store_true", help="skip Rust core inspect lane"
    )
    run_parser.add_argument(
        "--skip-native",
        action="store_true",
        help="skip native Rust Python binding lane",
    )

    benchmark_parser = sub.add_parser(
        "benchmark", help="run repeatable adapter performance/correctness benchmarks"
    )
    benchmark_parser.add_argument(
        "--json", action="store_true", help="print JSON instead of Markdown"
    )
    benchmark_parser.add_argument(
        "--write-results",
        action="store_true",
        help="append sample rows to results/runs.jsonl",
    )
    benchmark_parser.add_argument(
        "--write-report",
        action="store_true",
        help="write results/benchmarks/latest and archived report files",
    )
    benchmark_parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="measured iterations per adapter/fixture",
    )
    benchmark_parser.add_argument(
        "--warmup", type=int, default=1, help="warmup iterations per adapter/fixture"
    )
    benchmark_parser.add_argument(
        "--adapter",
        action="append",
        dest="adapters",
        help="adapter to benchmark; repeat or pass comma-separated names",
    )
    benchmark_parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        help="fixture id to benchmark; repeat or pass comma-separated ids",
    )
    benchmark_parser.add_argument(
        "--validate-openxml",
        action="store_true",
        help="validate output decks after timing write/round-trip operations",
    )
    benchmark_parser.add_argument(
        "--require-adapter",
        action="append",
        dest="required_adapters",
        help="fail if this selected adapter is unavailable; repeat or pass comma-separated names",
    )

    register_benchmark_profile_commands(sub)

    dropin_coverage_parser = sub.add_parser(
        "dropin-coverage",
        help="summarize behavioral coverage from a python-pptx drop-in profile",
    )
    dropin_coverage_parser.add_argument(
        "--profile",
        default="dropin-full",
        help="drop-in benchmark profile to summarize",
    )
    dropin_coverage_parser.add_argument(
        "--json", action="store_true", help="print JSON instead of Markdown"
    )
    dropin_coverage_parser.add_argument(
        "--require-domain",
        action="append",
        dest="required_domains",
        default=list(DEFAULT_REQUIRED_DOMAINS),
        help=(
            "domain that must be represented; repeat or pass comma-separated names"
        ),
    )
    dropin_coverage_parser.add_argument(
        "--min-behaviors",
        type=int,
        help="fail unless the profile covers at least this many behavior batches",
    )
    dropin_coverage_parser.add_argument(
        "--min-domains",
        type=int,
        help="fail unless the profile covers at least this many behavior domains",
    )
    dropin_coverage_parser.add_argument(
        "--min-domain-behaviors",
        action="append",
        dest="min_domain_behaviors",
        help=(
            "domain=count floor for behavior batches in one domain; repeat or "
            "pass comma-separated values"
        ),
    )
    dropin_coverage_parser.add_argument(
        "--min-fixture-scenarios",
        type=int,
        help="fail unless the profile covers at least this many fixture scenarios",
    )
    dropin_coverage_parser.add_argument(
        "--min-adapter-fixture-rows",
        type=int,
        help="fail unless the profile covers at least this many adapter/fixture rows",
    )

    register_validation_commands(sub)
    register_capability_plan_commands(sub)


    register_private_deck_commands(sub)

    register_tools_command(sub)

    demo_parser = sub.add_parser(
        "demo",
        help="run the surgical-edit demo and print its verification receipt",
    )
    demo_parser.add_argument("--output-dir", type=Path, default=None)
    demo_parser.add_argument(
        "--fail-injection", action="store_true", help="also demo a refused commit"
    )

    release_candidate_parser = sub.add_parser(
        "release-candidate",
        help="run the release-candidate evidence card",
    )
    release_candidate_parser.add_argument(
        "--fast", action="store_true", help="limit the unit/regression row"
    )
    release_candidate_parser.add_argument(
        "--json", action="store_true", help="print a machine-readable card"
    )
    release_candidate_parser.add_argument(
        "--strict", action="store_true", help="treat skipped rows as failures"
    )
    release_candidate_parser.add_argument(
        "--confirm-readme-audit",
        action="store_true",
        help="confirm README claims match current evidence",
    )
    release_candidate_parser.add_argument(
        "--skip",
        action="append",
        default=[],
        dest="rc_skip_rows",
        help="row id to skip; repeatable",
    )
    release_candidate_parser.add_argument(
        "--python", default=None, help="python executable for subprocess rows"
    )
    release_candidate_parser.add_argument(
        "--corpus-timeout", type=int, default=None, help="real-deck corpus timeout"
    )
    release_candidate_parser.add_argument(
        "--pytest-args",
        nargs="+",
        default=None,
        help="extra pytest arguments for the unit/regression row",
    )

    args = parser.parse_args(argv)

    if args.command == "extract":
        print(extract_semantics(args.path).to_json())
        return 0

    if args.command == "manifest":
        print(package_manifest(args.path).to_json())
        return 0

    if args.command == "diff":
        package_diff = diff_packages(args.left, args.right)
        print(json.dumps(package_diff.to_dict(), indent=2, sort_keys=True))
        return 0 if package_diff.clean else 1

    if args.command == "python-pptx-summary":
        print(
            json.dumps(
                python_pptx_summarize(args.path).to_dict(), indent=2, sort_keys=True
            )
        )
        return 0

    if args.command == "python-pptx-roundtrip":
        out = python_pptx_roundtrip(args.input, args.output)
        print(out)
        return 0

    if args.command == "validate-openxml":
        result = validate_openxml(args.path)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.valid else 1

    if args.command == "rust-inspect":
        result = rust_inspect(args.path)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-roundtrip":
        result = rust_roundtrip(args.input, args.output)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-add-slide":
        result = rust_add_slide(args.input, args.output, args.layout_index)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-replace-text":
        result = rust_replace_text(
            args.input,
            args.output,
            args.search,
            args.replacement,
            slide_index=args.slide_index,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-replace-text-run":
        result = rust_replace_text_run(
            args.input,
            args.output,
            args.slide_index,
            args.run_index,
            args.replacement,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-set-shape-text":
        result = rust_set_shape_text(
            args.input,
            args.output,
            args.slide_index,
            args.shape_index,
            args.replacement,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-set-paragraph-text":
        result = rust_set_paragraph_text(
            args.input,
            args.output,
            args.slide_index,
            args.shape_index,
            args.paragraph_index,
            args.replacement,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-replace-image":
        result = rust_replace_image(
            args.input,
            args.output,
            args.relationship_id,
            args.image,
            slide_index=args.slide_index,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-add-image":
        result = rust_add_image(
            args.input,
            args.output,
            args.slide_index,
            args.image,
            args.x_emu,
            args.y_emu,
            args.cx_emu,
            args.cy_emu,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-replace-table-cell":
        result = rust_replace_table_cell(
            args.input,
            args.output,
            args.slide_index,
            args.table_index,
            args.row_index,
            args.col_index,
            args.replacement,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "rust-add-table":
        result = rust_add_table(
            args.input,
            args.output,
            args.slide_index,
            args.rows,
            args.cols,
            args.x_emu,
            args.y_emu,
            args.cx_emu,
            args.cy_emu,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-inspect":
        result = native_inspect(args.path)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-summary":
        result = native_summarize(args.path)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-roundtrip":
        result = native_roundtrip(args.input, args.output)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-add-slide":
        result = native_add_slide(args.input, args.output, args.layout_index)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-replace-text":
        result = native_replace_text(
            args.input,
            args.output,
            args.search,
            args.replacement,
            slide_index=args.slide_index,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-replace-text-run":
        result = native_replace_text_run(
            args.input,
            args.output,
            args.slide_index,
            args.run_index,
            args.replacement,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-set-shape-text":
        result = native_set_shape_text(
            args.input,
            args.output,
            args.slide_index,
            args.shape_index,
            args.replacement,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-set-paragraph-text":
        result = native_set_paragraph_text(
            args.input,
            args.output,
            args.slide_index,
            args.shape_index,
            args.paragraph_index,
            args.replacement,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-replace-image":
        result = native_replace_image(
            args.input,
            args.output,
            args.relationship_id,
            args.image,
            slide_index=args.slide_index,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-add-image":
        result = native_add_image(
            args.input,
            args.output,
            args.slide_index,
            args.image,
            args.x_emu,
            args.y_emu,
            args.cx_emu,
            args.cy_emu,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-replace-table-cell":
        result = native_replace_table_cell(
            args.input,
            args.output,
            args.slide_index,
            args.table_index,
            args.row_index,
            args.col_index,
            args.replacement,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "native-add-table":
        result = native_add_table(
            args.input,
            args.output,
            args.slide_index,
            args.rows,
            args.cols,
            args.x_emu,
            args.y_emu,
            args.cx_emu,
            args.cy_emu,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "render-libreoffice":
        result = render_pdf(args.path, args.out_dir)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.ok else 1

    if args.command == "render-powerpoint":
        result = powerpoint_export_png(args.path, args.out_dir)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.ok else 1

    if args.command == "matrix":
        if args.check:
            from .matrix import OUT_PATH, render_matrix

            current = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
            generated = render_matrix()
            if current != generated:
                print(
                    f"{OUT_PATH} is stale; run wolfppt-harness matrix", file=sys.stderr
                )
                return 1
            return 0
        out = write_matrix()
        print(out)
        return 0

    if args.command == "python-api-surface":
        return handle_python_api_surface_command(args)

    if args.command == "record":
        append_result(
            HarnessResult(
                fixture=args.fixture,
                adapter=args.adapter,
                operation=args.operation,
                status=args.status,
                known_gap=args.known_gap,
            )
        )
        return 0

    if args.command == "corpus":
        fixtures = generate_corpus()
        print(f"generated {len(fixtures)} fixtures")
        return 0

    if args.command == "run-corpus":
        try:
            run = run_corpus(
                include_python_pptx=not args.skip_python_pptx,
                include_rust_core=not args.skip_rust_core,
                include_native=not args.skip_native,
                include_libreoffice=args.include_libreoffice,
                include_powerpoint=args.include_powerpoint,
                required_lanes=_split_csv_args(args.required_lanes),
                min_powerpoint_exported_slides=args.min_powerpoint_exported_slides,
                write_results=args.write_results,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if args.write_report:
            write_corpus_report(run)
        if args.json:
            print(json.dumps(run.to_dict(), indent=2, sort_keys=True))
        else:
            print(run.to_markdown(), end="")
        return 0 if run.status == "pass" else 1

    if args.command == "benchmark":
        try:
            run = run_benchmarks(
                iterations=args.iterations,
                warmup=args.warmup,
                adapter_names=_split_csv_args(args.adapters),
                fixture_ids=_split_csv_args(args.fixtures),
                validate_openxml=args.validate_openxml,
                write_results=args.write_results,
                required_adapters=_split_csv_args(args.required_adapters),
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if args.write_report:
            write_benchmark_report(run)
        if args.json:
            print(json.dumps(run.to_dict(), indent=2, sort_keys=True))
        else:
            print(run.to_markdown(), end="")
        return 0 if run.status == "pass" else 1

    if args.command == "benchmark-adapters":
        return handle_benchmark_adapters_command(args)

    if args.command == "benchmark-profile":
        return handle_benchmark_profile_command(args)

    if args.command == "dropin-coverage":
        for option_name in (
            "min_behaviors",
            "min_domains",
            "min_fixture_scenarios",
            "min_adapter_fixture_rows",
        ):
            value = getattr(args, option_name)
            if value is not None and value < 1:
                print(
                    f"--{option_name.replace('_', '-')} must be at least 1",
                    file=sys.stderr,
                )
                return 2
        try:
            min_domain_behaviors = _parse_key_value_int_args(
                args.min_domain_behaviors,
                "--min-domain-behaviors",
            )
            report = dropin_behavior_coverage(
                args.profile,
                required_domains=tuple(_split_csv_args(args.required_domains) or ()),
                min_behaviors=args.min_behaviors,
                min_domains=args.min_domains,
                min_domain_behaviors=min_domain_behaviors,
                min_fixture_scenarios=args.min_fixture_scenarios,
                min_adapter_fixture_rows=args.min_adapter_fixture_rows,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(render_dropin_behavior_coverage_markdown(report), end="")
        return 0 if report["status"] == "pass" else 1

    if args.command in {"validate", "validation-plan"}:
        return handle_validate_command(args)

    if args.command == "validate-impacted":
        return handle_validate_impacted_command(args)

    if args.command == "capability-plan":
        return handle_capability_plan_command(args)

    if args.command == "capability-check":
        return handle_capability_check_command(args)

    if args.command == "benchmark-profiles":
        return handle_benchmark_profiles_command(args)

    if args.command == "private-decks":
        return handle_private_decks_command(args)

    if args.command == "private-report-check":
        return handle_private_report_check_command(args)

    if args.command == "demo":
        from .demo import main as demo_main

        demo_argv: list[str] = []
        if args.output_dir is not None:
            demo_argv.extend(["--output-dir", str(args.output_dir)])
        if args.fail_injection:
            demo_argv.append("--fail-injection")
        return demo_main(demo_argv)

    if args.command == "release-candidate":
        from .release_candidate import run_release_candidate

        rc_argv: list[str] = []
        if args.fast:
            rc_argv.append("--fast")
        if args.json:
            rc_argv.append("--json")
        if args.strict:
            rc_argv.append("--strict")
        if args.confirm_readme_audit:
            rc_argv.append("--confirm-readme-audit")
        for row_id in args.rc_skip_rows:
            rc_argv.extend(["--skip", row_id])
        if args.python is not None:
            rc_argv.extend(["--python", args.python])
        if args.corpus_timeout is not None:
            rc_argv.extend(["--corpus-timeout", str(args.corpus_timeout)])
        if args.pytest_args:
            rc_argv.append("--pytest-args")
            rc_argv.extend(args.pytest_args)
        return run_release_candidate(rc_argv)


    if args.command == "tools":
        return handle_tools_command(args)

    return 2

if __name__ == "__main__":
    raise SystemExit(main())
