"""CLI helpers for benchmark availability and profile commands."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .benchmark import available_benchmark_adapters
from .benchmark_profiles import (
    available_benchmark_profiles,
    run_benchmark_profile,
    write_benchmark_profile_report,
)
from .cli_helpers import (
    emit_benchmark_profile_progress,
    split_csv_args,
)


def register_benchmark_profile_commands(
    subparsers: argparse._SubParsersAction[Any],
) -> None:
    """Register benchmark adapter/profile subcommands."""
    benchmark_adapters_parser = subparsers.add_parser(
        "benchmark-adapters",
        help="list benchmark adapter availability",
    )
    benchmark_adapters_parser.add_argument(
        "--unavailable-only",
        action="store_true",
        help="only print adapters that need setup before they can run",
    )

    benchmark_profile_parser = subparsers.add_parser(
        "benchmark-profile",
        help="run a curated benchmark profile with valid adapter/fixture batches",
    )
    benchmark_profile_parser.add_argument(
        "profile", help="profile name; see benchmark-profiles"
    )
    benchmark_profile_parser.add_argument(
        "--batch",
        action="append",
        dest="batch_names",
        help=(
            "run only this named profile batch; repeat or pass comma-separated names "
            "from benchmark-profiles"
        ),
    )
    benchmark_profile_parser.add_argument(
        "--json", action="store_true", help="print JSON instead of Markdown"
    )
    benchmark_profile_parser.add_argument(
        "--progress",
        action="store_true",
        help="emit compact benchmark-profile batch progress to stderr",
    )
    benchmark_profile_parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="stop after the first failed profile batch",
    )
    benchmark_profile_parser.add_argument(
        "--write-results",
        action="store_true",
        help="append sample rows to results/runs.jsonl",
    )
    benchmark_profile_parser.add_argument(
        "--write-report",
        action="store_true",
        help="write results/benchmarks/latest and archived report files",
    )
    benchmark_profile_parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="measured iterations per adapter/fixture",
    )
    benchmark_profile_parser.add_argument(
        "--warmup", type=int, default=1, help="warmup iterations per adapter/fixture"
    )
    benchmark_profile_parser.add_argument(
        "--validate-openxml",
        action="store_true",
        help="validate output decks after timing write/round-trip operations",
    )
    benchmark_profile_parser.add_argument(
        "--require-adapter",
        action="append",
        dest="required_adapters",
        help="fail if this profile adapter is unavailable; repeat or pass comma-separated names",
    )
    _add_speedup_gates(benchmark_profile_parser)
    _add_private_deck_gates(benchmark_profile_parser)
    _add_fixture_gates(benchmark_profile_parser)
    _add_validation_gates(benchmark_profile_parser)

    subparsers.add_parser("benchmark-profiles", help="list curated benchmark profiles")


def _add_speedup_gates(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--min-wolfppt-speedup",
        type=float,
        help=(
            "fail the profile if any passing python-pptx/WolfPPT pair is below "
            "this WolfPPT speedup"
        ),
    )
    parser.add_argument(
        "--min-native-roundtrip-speedup",
        type=float,
        help=(
            "fail the profile if any passing round-trip baseline/native WolfPPT "
            "pair is below this native speedup"
        ),
    )


def _add_private_deck_gates(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--min-private-decks",
        type=int,
        help=(
            "fail a private-deck benchmark profile unless at least this many "
            "private decks are discovered"
        ),
    )
    parser.add_argument(
        "--min-distinct-private-decks",
        type=int,
        help=(
            "fail a private-deck benchmark profile unless at least this many "
            "distinct private deck contents are discovered"
        ),
    )
    parser.add_argument(
        "--min-private-total-slides",
        type=int,
        help=(
            "fail a private-deck benchmark profile unless discovered private "
            "decks contain at least this many total slides"
        ),
    )
    for suffix, content_type in (
        ("shapes", "shapes"),
        ("tables", "tables"),
        ("charts", "charts"),
        ("media", "media parts"),
        ("embedded-objects", "embedded object parts"),
    ):
        parser.add_argument(
            f"--min-private-total-{suffix}",
            type=int,
            help=(
                "fail a private-deck benchmark profile unless private decks "
                f"contain this many {content_type}"
            ),
        )
    for suffix, content_type in (
        ("tables", "tables"),
        ("charts", "charts"),
        ("media", "media parts"),
        ("embedded-objects", "embedded object parts"),
    ):
        parser.add_argument(
            f"--min-private-decks-with-{suffix}",
            type=int,
            help=(
                "fail a private-deck benchmark profile unless this many private "
                f"decks contain {content_type}"
            ),
        )
        parser.add_argument(
            f"--min-private-distinct-decks-with-{suffix}",
            type=int,
            help=(
                "fail a private-deck benchmark profile unless this many distinct "
                f"private deck contents contain {content_type}"
            ),
        )
    parser.add_argument(
        "--min-private-slides-per-deck",
        type=int,
        help=(
            "fail a private-deck benchmark profile unless every private deck "
            "has at least this many slides"
        ),
    )
    parser.add_argument(
        "--min-private-shapes-per-deck",
        type=int,
        help=(
            "fail a private-deck benchmark profile unless every private deck "
            "has at least this many shapes"
        ),
    )


def _add_fixture_gates(parser: argparse.ArgumentParser) -> None:
    for suffix, content_type in (
        ("slides", "slides"),
        ("shapes", "shapes"),
        ("tables", "tables"),
        ("charts", "charts"),
        ("media", "media parts"),
        ("embedded-objects", "embedded object parts"),
    ):
        parser.add_argument(
            f"--min-fixture-total-{suffix}",
            type=int,
            help=(
                "fail unless covered checked-in fixtures contain at least this "
                f"many {content_type}"
            ),
        )
    for suffix, content_type in (
        ("tables", "tables"),
        ("charts", "charts"),
        ("media", "media parts"),
        ("embedded-objects", "embedded object parts"),
    ):
        parser.add_argument(
            f"--min-fixtures-with-{suffix}",
            type=int,
            help=(
                "fail unless at least this many checked-in fixtures contain "
                f"{content_type}"
            ),
        )


def _add_validation_gates(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--min-openxml-samples",
        type=int,
        help=(
            "fail the profile unless at least this many Open XML validation "
            "samples are recorded; requires --validate-openxml"
        ),
    )
    parser.add_argument(
        "--min-source-invalid-preserved-samples",
        type=int,
        help=(
            "fail the profile unless at least this many source-invalid Open XML "
            "samples are preserved; requires --validate-openxml"
        ),
    )
    parser.add_argument(
        "--min-distinct-fixtures",
        type=int,
        help=(
            "fail the profile unless results cover at least this many distinct "
            "fixture ids"
        ),
    )
    parser.add_argument(
        "--min-sdk-preservation-rows",
        type=int,
        help=(
            "fail the profile unless at least this many third-party/native "
            "preservation comparison rows are recorded"
        ),
    )


def handle_benchmark_adapters_command(args: argparse.Namespace) -> int:
    adapters = available_benchmark_adapters()
    if args.unavailable_only:
        adapters = [adapter for adapter in adapters if not adapter["available"]]
    print(json.dumps(adapters, indent=2, sort_keys=True))
    return 0


def handle_benchmark_profile_command(args: argparse.Namespace) -> int:
    try:
        run = run_benchmark_profile(
            args.profile,
            batch_names=split_csv_args(args.batch_names),
            iterations=args.iterations,
            warmup=args.warmup,
            validate_openxml=args.validate_openxml,
            write_results=args.write_results,
            min_wolfppt_speedup=args.min_wolfppt_speedup,
            min_native_roundtrip_speedup=args.min_native_roundtrip_speedup,
            min_private_decks=args.min_private_decks,
            min_distinct_private_decks=args.min_distinct_private_decks,
            min_private_total_slides=args.min_private_total_slides,
            min_private_total_shapes=args.min_private_total_shapes,
            min_private_total_tables=args.min_private_total_tables,
            min_private_total_charts=args.min_private_total_charts,
            min_private_total_media=args.min_private_total_media,
            min_private_total_embedded_objects=args.min_private_total_embedded_objects,
            min_private_decks_with_tables=args.min_private_decks_with_tables,
            min_private_decks_with_charts=args.min_private_decks_with_charts,
            min_private_decks_with_media=args.min_private_decks_with_media,
            min_private_decks_with_embedded_objects=(
                args.min_private_decks_with_embedded_objects
            ),
            min_private_distinct_decks_with_tables=(
                args.min_private_distinct_decks_with_tables
            ),
            min_private_distinct_decks_with_charts=(
                args.min_private_distinct_decks_with_charts
            ),
            min_private_distinct_decks_with_media=(
                args.min_private_distinct_decks_with_media
            ),
            min_private_distinct_decks_with_embedded_objects=(
                args.min_private_distinct_decks_with_embedded_objects
            ),
            min_private_slides_per_deck=args.min_private_slides_per_deck,
            min_private_shapes_per_deck=args.min_private_shapes_per_deck,
            min_fixture_total_slides=args.min_fixture_total_slides,
            min_fixture_total_shapes=args.min_fixture_total_shapes,
            min_fixture_total_tables=args.min_fixture_total_tables,
            min_fixture_total_charts=args.min_fixture_total_charts,
            min_fixture_total_media=args.min_fixture_total_media,
            min_fixture_total_embedded_objects=args.min_fixture_total_embedded_objects,
            min_fixtures_with_tables=args.min_fixtures_with_tables,
            min_fixtures_with_charts=args.min_fixtures_with_charts,
            min_fixtures_with_media=args.min_fixtures_with_media,
            min_fixtures_with_embedded_objects=(
                args.min_fixtures_with_embedded_objects
            ),
            min_openxml_samples=args.min_openxml_samples,
            min_source_invalid_preserved_samples=(
                args.min_source_invalid_preserved_samples
            ),
            min_distinct_fixtures=args.min_distinct_fixtures,
            min_sdk_preservation_rows=args.min_sdk_preservation_rows,
            required_adapters=split_csv_args(args.required_adapters),
            progress_callback=emit_benchmark_profile_progress
            if args.progress
            else None,
            fail_fast=args.fail_fast,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write_report:
        write_benchmark_profile_report(run)
    if args.json:
        print(json.dumps(run.to_dict(), indent=2, sort_keys=True))
    else:
        print(run.to_markdown(), end="")
    return 0 if run.status == "pass" else 1


def handle_benchmark_profiles_command(_: argparse.Namespace) -> int:
    print(json.dumps(available_benchmark_profiles(), indent=2, sort_keys=True))
    return 0
