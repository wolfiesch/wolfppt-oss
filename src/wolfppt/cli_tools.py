"""CLI helpers for optional tool availability commands."""

from __future__ import annotations

import json
import sys
from typing import Any

from .adapters import available_tools
from .cli_helpers import split_csv_args as _split_csv_args


def register_tools_command(subparsers: Any) -> None:
    tools_parser = subparsers.add_parser(
        "tools", help="report optional tool availability"
    )
    tools_parser.add_argument(
        "--json",
        action="store_true",
        help="print JSON output; kept for consistency with other status commands",
    )
    tools_parser.add_argument(
        "--unavailable-only",
        action="store_true",
        help="only report unavailable optional tools and their setup reasons",
    )
    tools_parser.add_argument(
        "--require-tool",
        action="append",
        dest="required_tools",
        help=(
            "fail unless the named tool is available; repeat or pass "
            "comma-separated names"
        ),
    )


def handle_tools_command(args: Any) -> int:
    tools = [tool.to_dict() for tool in available_tools()]
    required_tools = _split_csv_args(args.required_tools) or []
    tools_by_name = {tool["name"]: tool for tool in tools}
    unknown_required = [
        tool_name for tool_name in required_tools if tool_name not in tools_by_name
    ]
    if unknown_required:
        print(
            "unknown required tool(s): " + ", ".join(sorted(unknown_required)),
            file=sys.stderr,
        )
        return 2
    missing_required = [
        tools_by_name[tool_name]
        for tool_name in required_tools
        if not tools_by_name[tool_name]["available"]
    ]
    if args.unavailable_only:
        tools = [tool for tool in tools if not tool["available"]]
    print(json.dumps(tools, indent=2, sort_keys=True))
    return 1 if missing_required else 0
