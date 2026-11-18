"""CLI entry points for source-bound slide background picture authoring.

This module provides the ``background-picture`` subcommand for authoring slide
background pictures into presentations from validated, source-bound requests.
No claim of Office layout or render equivalence is made.

Publication contract:
- ``--input`` is read-only and opened from a private snapshot.
- ``--output`` must be a new regular file (an existing path, a symbolic link,
  or the input path itself is strictly refused).
- The presentation digest is verified before and after staging.
- Output publication is atomic via hard link (os.link).
- A refusal or error leaves the input presentation and existing destination
  untouched, outputs an error message to stderr, and exits with code 2.
- A success prints a JSON receipt to stdout with real SHA-256 hashes and
  exits with code 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .background_picture_requests import (
    BackgroundPictureRefusal,
    _apply_background_picture_request,
    load_background_picture_request,
    parse_background_picture_request,
)


def _add_background_picture_arguments(parser: argparse.ArgumentParser) -> None:
    """Add standard arguments for background picture authoring."""
    parser.add_argument(
        "--request",
        type=Path,
        help="JSON request file containing source_sha256, slide_index, image_path, and optional crop",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="source PPTX/PPTM presentation to read",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "destination PPTX/PPTM presentation to publish atomically; "
            "must not already exist and must differ from --input"
        ),
    )


def register_background_picture_commands(
    sub: argparse._SubParsersAction[Any],
) -> None:
    """Register the ``background-picture`` subcommand on a harness parser."""
    parser = sub.add_parser(
        "background-picture",
        help="author or update a slide background picture from a validated request",
        description=(
            "Author a slide background picture from a source-bound JSON request. "
            "The request must specify source_sha256, slide_index, image_path, and optional crop."
        ),
    )
    _add_background_picture_arguments(parser)
    parser.set_defaults(handler=handle_background_picture_command)


def handle_background_picture_command(args: argparse.Namespace) -> int:
    """Run one ``background-picture`` request and print its receipt."""
    missing = [
        f"--{name}"
        for name in ("request", "input", "output")
        if getattr(args, name) is None
    ]
    if missing:
        print(
            f"background-picture requires {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    req_path = Path(args.request)
    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        doc = load_background_picture_request(req_path)
        request = parse_background_picture_request(doc, base_dir=req_path.parent)
        publication = _apply_background_picture_request(
            input_path, request, output_path
        )

        receipt: dict[str, Any] = {
            "crop": {
                "bottom": publication["crop"][3],
                "left": publication["crop"][0],
                "right": publication["crop"][2],
                "top": publication["crop"][1],
            },
            "image_path": str(publication["image_path"]),
            "image_sha256": publication["image_sha256"],
            "operation": "background-picture",
            "output": str(output_path),
            "output_sha256": publication["output_sha256"],
            "slide_index": publication["slide_index"],
            "source": str(input_path),
            "source_sha256": publication["source_sha256"],
        }
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    except BackgroundPictureRefusal as exc:
        print(f"background-picture refusal: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"background-picture error: {exc}", file=sys.stderr)
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Standalone entry point so the command runs without the harness parser."""
    if argv is None:
        raw_args = list(sys.argv[1:])
    else:
        raw_args = list(argv)

    if raw_args and raw_args[0] == "background-picture":
        raw_args = raw_args[1:]

    parser = argparse.ArgumentParser(
        prog="wolfppt-background-picture",
        description="Source-bound slide background picture authoring.",
    )
    _add_background_picture_arguments(parser)
    args = parser.parse_args(raw_args)
    return handle_background_picture_command(args)


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = [
    "handle_background_picture_command",
    "main",
    "register_background_picture_commands",
]
