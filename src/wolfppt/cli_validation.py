"""CLI helpers for validation ladder commands."""

from __future__ import annotations

import json
from typing import Any

from .validation_ladder import (
    impacted_validation_plan,
    render_impacted_validation_markdown,
    render_validation_ladder_markdown,
    validation_ladder,
    validation_tiers,
)


def register_validation_commands(subparsers: Any) -> None:
    validate_ladder_parser = subparsers.add_parser(
        "validate",
        aliases=("validation-plan",),
        help="print the recommended validation tier for local or VPS checks",
    )
    validate_ladder_parser.add_argument(
        "tier",
        choices=validation_tiers(),
        help="validation tier to print",
    )
    validate_ladder_parser.add_argument(
        "--json", action="store_true", help="print JSON instead of Markdown"
    )
    validate_ladder_parser.add_argument(
        "--vps-host",
        default="validation-host",
        help="SSH host alias for VPS validation tiers",
    )
    validate_ladder_parser.add_argument(
        "--vps-path",
        default="~/Projects/wolfppt-validation",
        help="remote repo mirror path for VPS validation tiers",
    )

    validate_impacted_parser = subparsers.add_parser(
        "validate-impacted",
        help="print focused validation commands for changed or supplied paths",
    )
    validate_impacted_parser.add_argument(
        "paths",
        nargs="*",
        help="changed paths to plan for; defaults to git changed and untracked files",
    )
    validate_impacted_parser.add_argument(
        "--json", action="store_true", help="print JSON instead of Markdown"
    )


def handle_validate_command(args: Any) -> int:
    plan = validation_ladder(
        args.tier,
        vps_host=args.vps_host,
        vps_path=args.vps_path,
    )
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(render_validation_ladder_markdown(plan), end="")
    return 0


def handle_validate_impacted_command(args: Any) -> int:
    plan = impacted_validation_plan(list(args.paths) if args.paths else None)
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(render_impacted_validation_markdown(plan), end="")
    return 0
