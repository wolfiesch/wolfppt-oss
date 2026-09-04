"""Private deck CLI registration and gate handling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .private_decks import (
    private_complexity_gate_message,
    private_complexity_total,
    private_deck_inventory,
    private_distinct_feature_deck_count,
    private_distinct_feature_deck_gate_message,
    private_feature_deck_count,
    private_feature_deck_gate_message,
    private_min_complexity,
    private_min_complexity_gate_message,
    verify_private_report_redaction,
)


def register_private_deck_commands(sub: argparse._SubParsersAction[Any]) -> None:
    """Register private-deck inventory and redaction commands."""
    private_decks_parser = sub.add_parser(
        "private-decks",
        help="list redacted private deck inventory from WOLFPPT_PRIVATE_DECKS_DIR",
    )
    private_decks_parser.add_argument(
        "--json",
        action="store_true",
        help="emit the redacted inventory as JSON; currently the default output format",
    )
    private_decks_parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="fail unless at least this many private decks are discovered",
    )
    private_decks_parser.add_argument(
        "--min-distinct-count",
        type=int,
        help=(
            "fail unless at least this many distinct private deck contents are "
            "discovered"
        ),
    )
    private_decks_parser.add_argument(
        "--min-total-slides",
        type=int,
        help="fail unless discovered private decks contain at least this many total slides",
    )
    private_decks_parser.add_argument(
        "--min-total-shapes",
        type=int,
        help="fail unless discovered private decks contain at least this many shapes",
    )
    private_decks_parser.add_argument(
        "--min-total-tables",
        type=int,
        help="fail unless discovered private decks contain at least this many tables",
    )
    private_decks_parser.add_argument(
        "--min-total-charts",
        type=int,
        help="fail unless discovered private decks contain at least this many charts",
    )
    private_decks_parser.add_argument(
        "--min-total-media",
        type=int,
        help="fail unless discovered private decks contain at least this many media parts",
    )
    private_decks_parser.add_argument(
        "--min-total-embedded-objects",
        type=int,
        help=(
            "fail unless discovered private decks contain at least this many "
            "embedded object parts"
        ),
    )
    private_decks_parser.add_argument(
        "--min-decks-with-tables",
        type=int,
        help="fail unless at least this many private decks contain tables",
    )
    private_decks_parser.add_argument(
        "--min-decks-with-charts",
        type=int,
        help="fail unless at least this many private decks contain charts",
    )
    private_decks_parser.add_argument(
        "--min-decks-with-media",
        type=int,
        help="fail unless at least this many private decks contain media parts",
    )
    private_decks_parser.add_argument(
        "--min-decks-with-embedded-objects",
        type=int,
        help="fail unless at least this many private decks contain embedded object parts",
    )
    private_decks_parser.add_argument(
        "--min-distinct-decks-with-tables",
        type=int,
        help="fail unless at least this many distinct private deck contents contain tables",
    )
    private_decks_parser.add_argument(
        "--min-distinct-decks-with-charts",
        type=int,
        help="fail unless at least this many distinct private deck contents contain charts",
    )
    private_decks_parser.add_argument(
        "--min-distinct-decks-with-media",
        type=int,
        help="fail unless at least this many distinct private deck contents contain media parts",
    )
    private_decks_parser.add_argument(
        "--min-distinct-decks-with-embedded-objects",
        type=int,
        help=(
            "fail unless at least this many distinct private deck contents contain "
            "embedded object parts"
        ),
    )
    private_decks_parser.add_argument(
        "--min-slides-per-deck",
        type=int,
        help="fail unless every private deck has at least this many slides",
    )
    private_decks_parser.add_argument(
        "--min-shapes-per-deck",
        type=int,
        help="fail unless every private deck has at least this many shapes",
    )

    private_report_check_parser = sub.add_parser(
        "private-report-check",
        help="check generated benchmark reports for raw private deck names and paths",
    )
    private_report_check_parser.add_argument("path", type=Path)


def handle_private_decks_command(args: argparse.Namespace) -> int:
    """Run the redacted private deck inventory command."""
    private_complexity_gates = {
        "slides": ("--min-total-slides", args.min_total_slides),
        "shapes": ("--min-total-shapes", args.min_total_shapes),
        "tables": ("--min-total-tables", args.min_total_tables),
        "charts": ("--min-total-charts", args.min_total_charts),
        "media": ("--min-total-media", args.min_total_media),
        "embedded_objects": (
            "--min-total-embedded-objects",
            args.min_total_embedded_objects,
        ),
    }
    private_min_complexity_gates = {
        "slides": ("--min-slides-per-deck", args.min_slides_per_deck),
        "shapes": ("--min-shapes-per-deck", args.min_shapes_per_deck),
    }
    private_feature_deck_gates = {
        "tables": ("--min-decks-with-tables", args.min_decks_with_tables),
        "charts": ("--min-decks-with-charts", args.min_decks_with_charts),
        "media": ("--min-decks-with-media", args.min_decks_with_media),
        "embedded_objects": (
            "--min-decks-with-embedded-objects",
            args.min_decks_with_embedded_objects,
        ),
    }
    private_distinct_feature_deck_gates = {
        "tables": (
            "--min-distinct-decks-with-tables",
            args.min_distinct_decks_with_tables,
        ),
        "charts": (
            "--min-distinct-decks-with-charts",
            args.min_distinct_decks_with_charts,
        ),
        "media": (
            "--min-distinct-decks-with-media",
            args.min_distinct_decks_with_media,
        ),
        "embedded_objects": (
            "--min-distinct-decks-with-embedded-objects",
            args.min_distinct_decks_with_embedded_objects,
        ),
    }
    if args.min_count < 1:
        print("--min-count must be at least 1", file=sys.stderr)
        return 2
    if args.min_distinct_count is not None and args.min_distinct_count < 1:
        print("--min-distinct-count must be at least 1", file=sys.stderr)
        return 2
    for option_name, minimum in private_complexity_gates.values():
        if minimum is not None and minimum < 1:
            print(f"{option_name} must be at least 1", file=sys.stderr)
            return 2
    for option_name, minimum in private_min_complexity_gates.values():
        if minimum is not None and minimum < 1:
            print(f"{option_name} must be at least 1", file=sys.stderr)
            return 2
    for option_name, minimum in private_feature_deck_gates.values():
        if minimum is not None and minimum < 1:
            print(f"{option_name} must be at least 1", file=sys.stderr)
            return 2
    for option_name, minimum in private_distinct_feature_deck_gates.values():
        if minimum is not None and minimum < 1:
            print(f"{option_name} must be at least 1", file=sys.stderr)
            return 2
    try:
        inventory = private_deck_inventory()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if inventory["deck_count"] < args.min_count:
        print(json.dumps(inventory, indent=2, sort_keys=True))
        print(
            (
                f"{inventory['env']} contains {inventory['deck_count']} private "
                f"deck(s); at least {args.min_count} required"
            ),
            file=sys.stderr,
        )
        return 2
    if (
        args.min_distinct_count is not None
        and inventory["distinct_content_count"] < args.min_distinct_count
    ):
        print(json.dumps(inventory, indent=2, sort_keys=True))
        print(
            (
                f"{inventory['env']} contains "
                f"{inventory['distinct_content_count']} distinct private deck "
                f"content item(s); at least {args.min_distinct_count} required"
            ),
            file=sys.stderr,
        )
        return 2
    for feature, (_, minimum) in private_complexity_gates.items():
        if minimum is not None and private_complexity_total(inventory, feature) < minimum:
            print(json.dumps(inventory, indent=2, sort_keys=True))
            print(
                private_complexity_gate_message(inventory, feature, minimum),
                file=sys.stderr,
            )
            return 2
    for feature, (_, minimum) in private_min_complexity_gates.items():
        if minimum is not None and private_min_complexity(inventory, feature) < minimum:
            print(json.dumps(inventory, indent=2, sort_keys=True))
            print(
                private_min_complexity_gate_message(inventory, feature, minimum),
                file=sys.stderr,
            )
            return 2
    for feature, (_, minimum) in private_feature_deck_gates.items():
        if minimum is not None and private_feature_deck_count(inventory, feature) < minimum:
            print(json.dumps(inventory, indent=2, sort_keys=True))
            print(
                private_feature_deck_gate_message(inventory, feature, minimum),
                file=sys.stderr,
            )
            return 2
    for feature, (_, minimum) in private_distinct_feature_deck_gates.items():
        if (
            minimum is not None
            and private_distinct_feature_deck_count(inventory, feature) < minimum
        ):
            print(json.dumps(inventory, indent=2, sort_keys=True))
            print(
                private_distinct_feature_deck_gate_message(
                    inventory,
                    feature,
                    minimum,
                ),
                file=sys.stderr,
            )
            return 2
    print(json.dumps(inventory, indent=2, sort_keys=True))
    return 0


def handle_private_report_check_command(args: argparse.Namespace) -> int:
    """Run the generated private report redaction checker."""
    try:
        result = verify_private_report_redaction(args.path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1
