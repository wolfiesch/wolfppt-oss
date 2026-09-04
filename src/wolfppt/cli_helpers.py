"""Small CLI formatting and parsing helpers."""

from __future__ import annotations

import sys


def emit_benchmark_profile_progress(event: dict[str, object]) -> None:
    prefix = (
        "[benchmark-profile] "
        f"{event['run_id']} {event['profile']} "
        f"batch {event['batch_index']}/{event['batch_count']} "
        f"{event['batch']}"
    )
    scope = (
        f"adapters={event['adapter_count']} "
        f"fixtures={_format_progress_fixture_count(event)} "
        f"iterations={event['iterations']} warmup={event['warmup']} "
        f"validate_openxml={event['validate_openxml']}"
    )
    if event["event"] == "batch_start":
        print(f"{prefix} start {scope}", file=sys.stderr, flush=True)
        return
    if event["event"] == "batch_result":
        profile_result = _format_profile_result_progress(event)
        print(
            (
                f"{prefix} result "
                f"{event['completed_results']}/{event['total_results']} "
                f"adapter={event['adapter']} fixture={event['fixture_id']} "
                f"status={event['status']} "
                f"elapsed_ms={float(event['elapsed_wall_ms']):.1f}"
                f"{profile_result}"
            ),
            file=sys.stderr,
            flush=True,
        )
        return
    if event["event"] == "batch_finish":
        counts = dict(event["status_counts"])  # type: ignore[arg-type]
        failure_preview = list(event.get("failure_preview", []))  # type: ignore[arg-type]
        print(
            (
                f"{prefix} finish status={event['status']} "
                f"pass={counts.get('pass', 0)} skip={counts.get('skip', 0)} "
                f"fail={counts.get('fail', 0)} "
                f"elapsed_ms={float(event['elapsed_wall_ms']):.1f}"
            ),
            file=sys.stderr,
            flush=True,
        )
        for index, preview in enumerate(failure_preview, start=1):
            print(
                f"{prefix} failure {index}/{len(failure_preview)} {preview}",
                file=sys.stderr,
                flush=True,
            )
        return
    if event["event"] == "batch_error":
        print(
            (
                f"{prefix} error type={event['error_type']} "
                f"elapsed_ms={float(event['elapsed_wall_ms']):.1f}"
            ),
            file=sys.stderr,
            flush=True,
        )


def split_csv_args(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    items: list[str] = []
    for value in values:
        items.extend(item.strip() for item in value.split(",") if item.strip())
    return items


def _format_profile_result_progress(event: dict[str, object]) -> str:
    completed = event.get("profile_completed_results")
    total = event.get("profile_result_count")
    if completed is None or total is None:
        return ""
    return f" profile_result={completed}/{total}"


def parse_key_value_int_args(
    values: list[str] | None,
    option_name: str,
) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for item in split_csv_args(values) or []:
        if "=" not in item:
            raise ValueError(f"{option_name} entries must use name=count")
        name, raw_value = (part.strip() for part in item.split("=", 1))
        if not name:
            raise ValueError(f"{option_name} entries must include a name")
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise ValueError(
                f"{option_name} count for {name!r} must be an integer"
            ) from exc
        if value < 1:
            raise ValueError(f"{option_name} count for {name!r} must be at least 1")
        parsed[name] = value
    return parsed


def _format_progress_fixture_count(event: dict[str, object]) -> str:
    fixture_count = event["fixture_count"]
    fixture_scope = event["fixture_scope"]
    if fixture_count is None:
        return str(fixture_scope)
    return f"{fixture_count}({fixture_scope})"
