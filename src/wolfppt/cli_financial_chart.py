"""Public CLI for authoring and refreshing editable financial charts.

The command authors real, editable OOXML charts (combination charts with
secondary-axis line ownership, and signed stacked-bar bridge charts standing in
for financial waterfalls) into a deck.  It never renders a picture and
never emulates a chart with generic shapes: every output stays a chart part with
an embedded workbook that PowerPoint and Excel reopen for editing.

Publication contract: ``--input`` is read-only and is opened from a private
snapshot, ``--output`` must be a new regular file (an existing path, a symbolic
link, or the input path itself is refused), and the deck is re-checked before
the staged package is published atomically.  Publication uses a hard link only,
so a destination filesystem that cannot hard-link is refused instead of
exposing a partially written deck.  A refusal or failure leaves the input deck
unchanged and the output path absent.  The receipt's
``source_sha256``/``output_sha256`` are the raw file digests of the input deck
and the published output.

Representation boundary: the bridge is an editable OOXML stacked-bar
construction, not Microsoft's chartEx ``waterfall`` part type, and no Office
layout parity is claimed.  ``--list-kinds`` prints the exact authored surface and
the refused chart families.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .chart_financial import (
    FINANCIAL_CHART_KINDS,
    FINANCIAL_CHART_REPRESENTATIONS,
    UNSUPPORTED_FINANCIAL_CHART_TYPES,
    FinancialChartRefusal,
    author_financial_chart,
    financial_chart_frame,
    financial_spec_from_request,
    refresh_financial_chart,
)


def register_financial_chart_commands(
    sub: argparse._SubParsersAction[Any],
) -> None:
    """Register the ``financial-chart`` authoring/refresh command."""
    parser = sub.add_parser(
        "financial-chart",
        help=(
            "author or refresh an editable combination/waterfall chart in a "
            "deck (OOXML chart parts, not images)"
        ),
    )
    parser.add_argument(
        "--operation",
        choices=("author", "refresh"),
        default="author",
        help=(
            "author adds a new chart shape; refresh replaces the data of an "
            "existing authored financial chart in place"
        ),
    )
    parser.add_argument(
        "--request",
        type=Path,
        help="JSON request file holding the chart kind, data, and optional layout",
    )
    parser.add_argument("--input", type=Path, help="source PPTX/PPTM to read")
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "destination PPTX/PPTM to publish atomically; must not already "
            "exist and must differ from --input"
        ),
    )
    parser.add_argument(
        "--slide-index",
        type=int,
        help="zero-based slide index the chart is authored into or refreshed on",
    )
    parser.add_argument(
        "--shape-name",
        help="chart shape name to refresh when the slide holds several charts",
    )
    for axis in ("x", "y", "cx", "cy"):
        parser.add_argument(
            f"--{axis}",
            type=int,
            help=f"chart frame {axis} in EMU (overrides the request layout)",
        )
    parser.add_argument(
        "--list-kinds",
        action="store_true",
        help="print the authored financial chart kinds and refused types, then exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the receipt as JSON; currently the default output format",
    )


def financial_chart_surface() -> dict[str, Any]:
    """Describe the authored kinds, their representation, and the refusals."""
    return {
        "kinds": list(FINANCIAL_CHART_KINDS),
        "representations": dict(FINANCIAL_CHART_REPRESENTATIONS),
        "unsupported": dict(UNSUPPORTED_FINANCIAL_CHART_TYPES),
        "editable": True,
        "office_parity": False,
        "note": (
            "authored charts are editable OOXML chart parts with embedded "
            "workbooks; WATERFALL is an editable stacked-bar bridge, not a "
            "chartEx waterfall part"
        ),
    }


def handle_financial_chart_command(args: argparse.Namespace) -> int:
    """Run one ``financial-chart`` request and print its receipt."""
    if args.list_kinds:
        print(json.dumps(financial_chart_surface(), indent=2, sort_keys=True))
        return 0
    missing = [
        name for name in ("request", "input", "output") if getattr(args, name) is None
    ]
    if missing:
        print(
            "financial-chart requires "
            + ", ".join(f"--{name}" for name in missing)
            + " (or --list-kinds)",
            file=sys.stderr,
        )
        return 2
    try:
        document = _load_request(args.request)
        spec = financial_spec_from_request(document)
        frame = financial_chart_frame(
            document,
            override={
                "x": args.x,
                "y": args.y,
                "cx": args.cx,
                "cy": args.cy,
            },
        )
        slide_index = (
            args.slide_index
            if args.slide_index is not None
            else int(document.get("slide_index") or 0)
        )
        shape_name = args.shape_name or document.get("shape_name")
        if args.operation == "refresh":
            receipt = refresh_financial_chart(
                args.input,
                args.output,
                spec=spec,
                slide_index=slide_index,
                shape_name=None if shape_name is None else str(shape_name),
            )
        else:
            receipt = author_financial_chart(
                args.input,
                args.output,
                spec=spec,
                slide_index=slide_index,
                **frame,
            )
    except FinancialChartRefusal as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(receipt.to_dict(), indent=2, sort_keys=True))
    return 0


def _load_request(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FinancialChartRefusal(
            f"request file {path} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise FinancialChartRefusal("financial chart request must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    """Standalone entry point so the command runs without the harness parser."""
    parser = argparse.ArgumentParser(
        prog="python -m wolfppt.cli_financial_chart",
        description=__doc__,
    )
    register_financial_chart_commands(
        parser.add_subparsers(dest="command", required=True)
    )
    args = parser.parse_args(["financial-chart", *(argv or [])])
    return handle_financial_chart_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
