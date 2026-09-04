"""Coverage summary for python-pptx-compatible drop-in benchmark profiles."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .benchmark_profiles import resolve_benchmark_profile

DEFAULT_REQUIRED_DOMAINS = (
    "charts",
    "groups",
    "media",
    "notes",
    "presentation",
    "shapes",
    "slides_layouts",
    "tables",
    "text",
)

DOMAIN_RULES = {
    "charts": ("chart",),
    "groups": ("group", "nested group", "nested-group"),
    "media": ("picture", "movie", "ole", "media"),
    "notes": ("notes", "speaker-notes"),
    "presentation": ("presentation", "core-properties", "slide-size"),
    "shapes": (
        "connector",
        "freeform",
        "line",
        "shape",
        "shadow",
        "fill",
        "rotation",
        "hyperlink",
    ),
    "slides_layouts": ("slide", "layout", "placeholder"),
    "tables": ("table", "cell", "row-height", "column-width"),
    "text": (
        "font",
        "formatting",
        "paragraph",
        "run",
        "text",
        "word-wrap",
        "fit-text",
    ),
}


def dropin_behavior_coverage(
    profile_name: str = "dropin-full",
    *,
    required_domains: tuple[str, ...] = DEFAULT_REQUIRED_DOMAINS,
    min_behaviors: int | None = None,
    min_domains: int | None = None,
    min_domain_behaviors: dict[str, int] | None = None,
    min_fixture_scenarios: int | None = None,
    min_adapter_fixture_rows: int | None = None,
) -> dict[str, Any]:
    """Summarize behavioral benchmark coverage for a drop-in profile."""

    profile = resolve_benchmark_profile(profile_name)
    domain_batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    batches: list[dict[str, Any]] = []
    malformed_batches: list[dict[str, Any]] = []

    for batch in profile.batches:
        fixture_ids = batch.fixture_ids or ()
        domains = _classify_batch(batch.name, batch.description)
        expected_adapters = (
            _expected_python_adapter(batch.adapter_names),
            _expected_wolfppt_adapter(batch.adapter_names),
        )
        batch_row = {
            "name": batch.name,
            "description": batch.description,
            "domains": domains,
            "fixture_ids": list(fixture_ids),
            "fixture_scenarios": len(fixture_ids),
            "adapter_fixture_rows": len(batch.adapter_names) * len(fixture_ids),
            "adapter_names": list(batch.adapter_names),
        }
        batches.append(batch_row)
        if None in expected_adapters:
            malformed_batches.append(
                {
                    "name": batch.name,
                    "adapter_names": list(batch.adapter_names),
                    "reason": "expected one python-pptx adapter and one WolfPPT facade adapter",
                }
            )
        for domain in domains:
            domain_batches[domain].append(batch_row)

    domain_summary = {
        domain: _domain_summary(domain, rows)
        for domain, rows in sorted(domain_batches.items())
    }
    missing_required_domains = [
        domain for domain in required_domains if domain not in domain_summary
    ]
    totals = {
        "behaviors": len(batches),
        "domains": len(domain_summary),
        "fixture_scenarios": sum(row["fixture_scenarios"] for row in batches),
        "adapter_fixture_rows": sum(row["adapter_fixture_rows"] for row in batches),
    }
    gate_failures = _gate_failures(
        totals,
        domain_summary,
        missing_required_domains,
        malformed_batches,
        min_behaviors=min_behaviors,
        min_domains=min_domains,
        min_domain_behaviors=min_domain_behaviors or {},
        min_fixture_scenarios=min_fixture_scenarios,
        min_adapter_fixture_rows=min_adapter_fixture_rows,
    )
    return {
        "profile": profile.name,
        "description": profile.description,
        "status": "fail" if gate_failures else "pass",
        "totals": totals,
        "required_domains": list(required_domains),
        "missing_required_domains": missing_required_domains,
        "domains": domain_summary,
        "domain_behavior_minimums": min_domain_behaviors or {},
        "malformed_batches": malformed_batches,
        "gate_failures": gate_failures,
        "batches": batches,
    }


def render_dropin_behavior_coverage_markdown(report: dict[str, Any]) -> str:
    """Render a compact Markdown report for drop-in behavioral coverage."""

    totals = report["totals"]
    lines = [
        "# Drop-In Behavioral Coverage",
        "",
        f"Profile: `{report['profile']}`",
        "",
        f"Status: **{report['status']}**",
        "",
        "## Totals",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| behaviors | {totals['behaviors']} |",
        f"| domains | {totals['domains']} |",
        f"| fixture scenarios | {totals['fixture_scenarios']} |",
        f"| adapter/fixture rows | {totals['adapter_fixture_rows']} |",
        "",
        "## Domain Coverage",
        "",
        "| domain | behaviors | fixture scenarios | adapter/fixture rows |",
        "|---|---:|---:|---:|",
    ]
    for domain, summary in report["domains"].items():
        lines.append(
            f"| `{domain}` | {summary['behaviors']} | "
            f"{summary['fixture_scenarios']} | {summary['adapter_fixture_rows']} |"
        )
    if report["gate_failures"]:
        lines.extend(["", "## Gate Failures", ""])
        lines.extend(f"- {failure}" for failure in report["gate_failures"])
    return "\n".join(lines) + "\n"


def _classify_batch(name: str, description: str) -> list[str]:
    haystack = f"{name} {description}".lower().replace("_", "-")
    domains = [
        domain
        for domain, tokens in DOMAIN_RULES.items()
        if any(_has_token(haystack, token) for token in tokens)
    ]
    return sorted(set(domains)) or ["other"]


def _has_token(haystack: str, token: str) -> bool:
    if not token.replace("-", "").isalnum():
        return token in haystack
    pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def _expected_python_adapter(adapter_names: tuple[str, ...]) -> str | None:
    return next(
        (
            adapter
            for adapter in adapter_names
            if adapter.startswith("python-pptx-dropin-")
        ),
        None,
    )


def _expected_wolfppt_adapter(adapter_names: tuple[str, ...]) -> str | None:
    return next(
        (
            adapter
            for adapter in adapter_names
            if adapter.startswith("wolfppt-facade-dropin-")
        ),
        None,
    )


def _domain_summary(domain: str, batches: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "domain": domain,
        "behaviors": len(batches),
        "fixture_scenarios": sum(batch["fixture_scenarios"] for batch in batches),
        "adapter_fixture_rows": sum(
            batch["adapter_fixture_rows"] for batch in batches
        ),
        "batch_names": [batch["name"] for batch in batches],
    }


def _gate_failures(
    totals: dict[str, int],
    domain_summary: dict[str, dict[str, Any]],
    missing_required_domains: list[str],
    malformed_batches: list[dict[str, Any]],
    *,
    min_behaviors: int | None,
    min_domains: int | None,
    min_domain_behaviors: dict[str, int],
    min_fixture_scenarios: int | None,
    min_adapter_fixture_rows: int | None,
) -> list[str]:
    failures: list[str] = []
    if missing_required_domains:
        failures.append(
            "missing required domain(s): " + ", ".join(missing_required_domains)
        )
    if malformed_batches:
        failures.append(
            "malformed adapter pair(s): "
            + ", ".join(batch["name"] for batch in malformed_batches)
        )
    for key, minimum in (
        ("behaviors", min_behaviors),
        ("domains", min_domains),
        ("fixture_scenarios", min_fixture_scenarios),
        ("adapter_fixture_rows", min_adapter_fixture_rows),
    ):
        if minimum is not None and totals[key] < minimum:
            failures.append(f"{key}: observed {totals[key]}, required {minimum}")
    for domain, minimum in sorted(min_domain_behaviors.items()):
        observed = domain_summary.get(domain, {}).get("behaviors", 0)
        if observed < minimum:
            failures.append(
                f"{domain} behaviors: observed {observed}, required {minimum}"
            )
    return failures
