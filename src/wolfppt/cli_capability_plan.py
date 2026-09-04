"""CLI commands for the Tier-A capability queue."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .capability_plan import (
    CapabilityPlanError,
    capability_check,
    capability_plan,
    render_capability_check_markdown,
    render_capability_plan_markdown,
)


def register_capability_plan_commands(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Register the agent-oriented capability queue commands."""
    plan_parser = subparsers.add_parser(
        "capability-plan",
        help="emit ranked capability work packets",
    )
    plan_parser.add_argument("--tier", choices=("A",), default="A")
    plan_parser.add_argument(
        "--include-completed",
        action="store_true",
        help="include verified workflows alongside actionable gaps",
    )
    plan_parser.add_argument("--json", action="store_true", help="emit JSON")

    check_parser = subparsers.add_parser(
        "capability-check",
        help="run only the focused checks declared for one capability packet",
    )
    check_parser.add_argument("capability_id")
    check_parser.add_argument("--json", action="store_true", help="emit JSON")


def handle_capability_plan_command(args: Any) -> int:
    """Render the actionable Tier-A queue."""
    try:
        plan = capability_plan(args.tier, include_completed=args.include_completed)
    except CapabilityPlanError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(render_capability_plan_markdown(plan), end="")
    return 0


def handle_capability_check_command(args: Any) -> int:
    """Run the exact checks selected by one stable capability ID."""
    try:
        report = capability_check(args.capability_id)
    except CapabilityPlanError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_capability_check_markdown(report), end="")
    return 0 if report["status"] == "passed" else 1
