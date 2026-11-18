"""Public CLI for source-bound PPTX package sanitization.

``wolfppt-harness sanitize-inspect --request FILE`` prints one read-only
inventory of a presentation's package, and ``wolfppt-harness sanitize --request
FILE`` removes one selection of that inventory's targets into one new package.
The inspection request file holds exactly ``source`` and ``source_sha256``; the
sanitization request file holds exactly ``source``, ``destination``,
``source_sha256``, and ``removals``, where ``removals`` are exact target ids from
the inspection receipt of the very bytes ``source_sha256`` names.

Exactly one JSON report is printed to stdout, and the exit status carries the
outcome: ``0`` when the inventory was read or the verified output was published,
``2`` when the operation refused and the destination was left alone.  A request
that cannot be named, read, or parsed is the same refusal - one content-safe
report on stdout with ``{operation}_request_invalid`` and the same ``2`` - while
the parser's own help and usage behavior is untouched.

The report is content-safe by construction: it names parts, sizes, channels,
reachability, removal targets, and every category this surface will not call
clean, and never carries a comment body, an author name, an embedded payload, or
an external target.  A removal rewrites only the relationship and content-type
parts that name what it removes, preserves every other part byte for byte, and is
re-verified against both the plan and the source before publication.  Publication
is a private sibling staging file plus an atomic ``os.link`` no-replace commit, so
an existing destination, a dangling symbolic link, the source itself, and a
destination created while the operation runs are all refused instead of
overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .sanitization import (
    INSPECT,
    OPERATIONS,
    SANITIZE,
    PptxSanitizationReport,
    inspect_pptx_sanitization,
    load_pptx_sanitization_inspect_request,
    load_pptx_sanitization_request,
    sanitize_pptx,
)

_COMMAND_BY_OPERATION = {INSPECT: "sanitize-inspect", SANITIZE: "sanitize"}
"""The one CLI command name each operation is exposed under."""

_OPERATION_BY_COMMAND = {
    command: operation for operation, command in _COMMAND_BY_OPERATION.items()
}
"""The operation each CLI command name runs."""

_COMMAND_HELP = {
    INSPECT: (
        "print one read-only, source-bound inventory of a presentation's package "
        "(exit 0 inspected, 2 refused)"
    ),
    SANITIZE: (
        "remove one verified selection of recognized sensitive channels into a new "
        "package (exit 0 published, 2 refused)"
    ),
}
"""The one-line help of each operation's command."""


def register_sanitization_commands(sub: argparse._SubParsersAction[Any]) -> None:
    """Register the ``sanitize-inspect`` and ``sanitize`` package-content commands."""

    for operation in OPERATIONS:
        parser = sub.add_parser(
            _COMMAND_BY_OPERATION[operation],
            help=_COMMAND_HELP[operation],
            description=(
                f"Run one source-bound {operation} request and print exactly one "
                "JSON sanitization report. The request file holds exactly source "
                "and source_sha256 to inspect, or exactly source, destination, "
                "source_sha256, and removals to sanitize."
            ),
        )
        parser.add_argument(
            "--request",
            type=Path,
            help=(
                "JSON request file with exactly source and source_sha256, or exactly "
                "source, destination, source_sha256, and removals"
            ),
        )


def _run(operation: str, request_path: Path) -> PptxSanitizationReport:
    """Load one request file and run the operation it names."""

    if operation == INSPECT:
        request = load_pptx_sanitization_inspect_request(request_path)
        return inspect_pptx_sanitization(
            request.source, source_sha256=request.source_sha256
        )
    return sanitize_pptx(load_pptx_sanitization_request(request_path))


def _request_refusal(operation: str, recovery: str) -> dict[str, Any]:
    """Return the report shape for a request that could not be read.

    The report has the same keys in the same order as a real one; the values only
    a request can supply are ``None``, because none of them could be established.
    """

    return {
        "schema_version": 1,
        "operation": operation,
        "passed": False,
        "status": "refused",
        "code": f"{operation}_request_invalid",
        "source_sha256": None,
        "removals": [],
        "removed_parts": [],
        "rewritten_parts": [],
        "preserved_part_count": 0,
        "destination_sha256": None,
        "inventory": None,
        "recovery": recovery,
    }


def _print_report(payload: Mapping[str, Any]) -> None:
    """Print exactly one JSON sanitization report on stdout."""

    print(json.dumps(payload, indent=2, sort_keys=True))


def handle_sanitization_command(args: argparse.Namespace) -> int:
    """Run one ``sanitize``/``sanitize-inspect`` request and print its JSON report."""

    operation = _OPERATION_BY_COMMAND.get(getattr(args, "command", ""))
    if operation is None:
        print(
            f"sanitization commands are {', '.join(_COMMAND_BY_OPERATION.values())}",
            file=sys.stderr,
        )
        return 2
    request_path = getattr(args, "request", None)
    if request_path is None:
        _print_report(
            _request_refusal(
                operation,
                (
                    "Name the JSON request file with --request; it holds exactly "
                    "source and source_sha256, or exactly source, destination, "
                    "source_sha256, and removals."
                ),
            )
        )
        return 2
    try:
        report = _run(operation, request_path)
    except (OSError, TypeError, ValueError):
        # A request file that cannot be read or parsed is a refusal like any
        # other, and the unreadable content is never echoed into the report.
        _print_report(
            _request_refusal(
                operation,
                (
                    "Supply a readable UTF-8 JSON request file holding exactly "
                    "source and source_sha256, or exactly source, destination, "
                    "source_sha256, and removals in the documented shapes."
                ),
            )
        )
        return 2
    _print_report(report.to_dict())
    return 0 if report.passed else 2


def main(argv: list[str] | None = None) -> int:
    """Standalone entry point so the commands run without the harness parser."""

    parser = argparse.ArgumentParser(
        prog="python -m wolfppt.cli_sanitization",
        description=__doc__,
    )
    register_sanitization_commands(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(argv)
    return handle_sanitization_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
