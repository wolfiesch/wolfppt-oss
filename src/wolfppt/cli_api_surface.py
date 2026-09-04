"""CLI helpers for the python-pptx public surface ratchet."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .python_api_surface import (
    compare_public_surface,
    render_public_surface_markdown,
    write_public_surface_report,
)


def register_python_api_surface_command(subparsers: Any) -> None:
    api_surface_parser = subparsers.add_parser(
        "python-api-surface",
        help="compare WolfPPT facade public names against python-pptx",
    )
    api_surface_parser.add_argument(
        "--json", action="store_true", help="print JSON instead of Markdown"
    )
    api_surface_parser.add_argument(
        "--fixture-root", type=Path, default=Path("fixtures/pptx")
    )
    api_surface_parser.add_argument(
        "--max-real-slides",
        type=int,
        default=3,
        help="maximum slides sampled per checked-in fixture",
    )
    api_surface_parser.add_argument(
        "--max-real-shapes",
        type=int,
        default=5,
        help="maximum shapes sampled per sampled slide",
    )
    api_surface_parser.add_argument(
        "--min-fixtures",
        type=int,
        help="fail unless at least this many fixture decks are checked",
    )
    api_surface_parser.add_argument(
        "--min-representative-pairs",
        type=int,
        help="fail unless at least this many representative object pairs are checked",
    )
    api_surface_parser.add_argument(
        "--min-real-pairs",
        type=int,
        help="fail unless at least this many real-fixture object pairs are checked",
    )
    api_surface_parser.add_argument(
        "--write-report",
        action="store_true",
        help="write results/api-surface/latest and an archived report copy",
    )
    api_surface_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/api-surface/latest"),
        help="directory for --write-report output",
    )


def handle_python_api_surface_command(args: Any) -> int:
    try:
        report = compare_public_surface(
            args.fixture_root,
            max_real_slides=args.max_real_slides,
            max_real_shapes=args.max_real_shapes,
            min_fixtures=args.min_fixtures,
            min_representative_pairs=args.min_representative_pairs,
            min_real_pairs=args.min_real_pairs,
        )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write_report:
        write_public_surface_report(report, args.output_dir)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_public_surface_markdown(report), end="")
    return 0 if report["status"] == "pass" else 1
