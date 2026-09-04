"""Tier-A capability queue and focused-check execution."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from typing import Any

from .spec import ROOT, load_spec_module

ACTIONABLE_STATUSES = frozenset({"planned", "implemented"})
WORKFLOW_STATUSES = ACTIONABLE_STATUSES | {"verified"}
ENTRY_STATUS_BY_WORKFLOW_STATUS = {
    "planned": "not_yet",
    "implemented": "supported",
    "verified": "supported",
}
REQUIRED_FIELDS = frozenset(
    {
        "id",
        "tier",
        "domain",
        "rank",
        "status",
        "capability_id",
        "capability",
        "python_pptx_probe",
        "fixture",
        "pytest_nodes",
        "rust_nodes",
        "expected_changed_parts",
        "mutation_route",
    }
)


class CapabilityPlanError(ValueError):
    """Raised when a capability queue request cannot be fulfilled."""


def load_capability_workflows() -> list[dict[str, Any]]:
    """Load and validate the workflow queue kept in the compatibility spec."""
    module = load_spec_module()
    workflows = getattr(module, "TIER_A_WORKFLOWS", None)
    if not isinstance(workflows, list):
        raise CapabilityPlanError("compatibility spec has no TIER_A_WORKFLOWS list")
    entries = getattr(module, "ENTRIES", None)
    if not isinstance(entries, list):
        raise CapabilityPlanError("compatibility spec has no ENTRIES list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in workflows:
        if not isinstance(raw, Mapping):
            raise CapabilityPlanError("capability workflow must be a mapping")
        missing = sorted(REQUIRED_FIELDS - raw.keys())
        if missing:
            workflow_id = raw.get("id", "<unknown>")
            raise CapabilityPlanError(
                f"capability workflow {workflow_id!r} is missing: {', '.join(missing)}"
            )
        workflow = dict(raw)
        workflow_id = workflow["id"]
        if not isinstance(workflow_id, str) or not workflow_id:
            raise CapabilityPlanError("capability workflow id must be a non-empty string")
        if workflow_id in seen_ids:
            raise CapabilityPlanError(f"duplicate capability workflow id: {workflow_id}")
        seen_ids.add(workflow_id)
        if workflow["tier"] != "A":
            raise CapabilityPlanError(
                f"capability workflow {workflow_id!r} has unsupported tier "
                f"{workflow['tier']!r}"
            )
        if workflow["status"] not in WORKFLOW_STATUSES:
            raise CapabilityPlanError(
                f"capability workflow {workflow_id!r} has invalid status "
                f"{workflow['status']!r}"
            )
        capability_id = workflow["capability_id"]
        if not isinstance(capability_id, str) or not capability_id:
            raise CapabilityPlanError(
                f"capability workflow {workflow_id!r} capability_id must be a non-empty string"
            )
        matches = [
            entry
            for entry in entries
            if isinstance(entry, Mapping) and entry.get("id") == capability_id
        ]
        if len(matches) != 1:
            raise CapabilityPlanError(
                f"capability workflow {workflow_id!r} references {capability_id!r}, "
                f"which resolves to {len(matches)} compatibility entries"
            )
        expected_entry_status = ENTRY_STATUS_BY_WORKFLOW_STATUS[workflow["status"]]
        actual_entry_status = matches[0].get("status")
        if actual_entry_status != expected_entry_status:
            raise CapabilityPlanError(
                f"capability workflow {workflow_id!r} status {workflow['status']!r} "
                f"requires compatibility status {expected_entry_status!r}, got "
                f"{actual_entry_status!r}"
            )

        if not isinstance(workflow["rank"], int) or isinstance(workflow["rank"], bool):
            raise CapabilityPlanError(
                f"capability workflow {workflow_id!r} rank must be an integer"
            )
        for field in (
            "pytest_nodes",
            "rust_nodes",
            "expected_changed_parts",
        ):
            value = workflow[field]
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item for item in value
            ):
                raise CapabilityPlanError(
                    f"capability workflow {workflow_id!r} {field} must be strings"
                )
        normalized.append(workflow)
    return normalized


def capability_plan(tier: str, *, include_completed: bool = False) -> dict[str, Any]:
    """Return deterministic agent-ready packets for one capability tier."""
    workflows = load_capability_workflows()
    selected = [
        workflow
        for workflow in workflows
        if workflow["tier"] == tier
        and (include_completed or workflow["status"] in ACTIONABLE_STATUSES)
    ]
    selected.sort(key=lambda workflow: (workflow["rank"], workflow["id"]))
    return {
        "kind": "capability-plan",
        "schema_version": 1,
        "tier": tier,
        "include_completed": include_completed,
        "workflows": selected,
        "total": len(selected),
    }


def find_capability_workflow(workflow_id: str) -> dict[str, Any]:
    """Return one workflow or raise a user-facing unknown-id error."""
    for workflow in load_capability_workflows():
        if workflow["id"] == workflow_id:
            return workflow
    raise CapabilityPlanError(f"unknown capability id: {workflow_id}")


def capability_check(workflow_id: str) -> dict[str, Any]:
    """Execute only the focused Python and Rust checks named by a workflow."""
    workflow = find_capability_workflow(workflow_id)
    commands = _focused_commands(workflow)
    results: list[dict[str, Any]] = []
    for kind, command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        result = {
            "kind": kind,
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        results.append(result)
        if completed.returncode:
            return {
                "kind": "capability-check",
                "schema_version": 1,
                "id": workflow_id,
                "status": "failed",
                "checks": results,
            }
    return {
        "kind": "capability-check",
        "schema_version": 1,
        "id": workflow_id,
        "status": "passed",
        "checks": results,
    }


def render_capability_plan_markdown(plan: Mapping[str, Any]) -> str:
    """Render an actionable queue without hiding its evidence gaps."""
    lines = [
        f"# Capability Plan: Tier {plan['tier']}",
        "",
        f"Workflows: {plan['total']}",
    ]
    for workflow in plan["workflows"]:
        lines.extend(
            (
                "",
                f"## {workflow['rank']}: {workflow['capability']}",
                f"- ID: `{workflow['id']}`",
                f"- Status: `{workflow['status']}`",
                f"- Domain: {workflow['domain']}",
                f"- python-pptx probe: {workflow['python_pptx_probe']}",
                f"- Fixture: `{workflow['fixture']}`",
                "- Pytest: " + _render_values(workflow["pytest_nodes"]),
                "- Rust: " + _render_values(workflow["rust_nodes"]),
                "- Expected parts: "
                + _render_values(workflow["expected_changed_parts"]),
                f"- Mutation route: {workflow['mutation_route']}",
            )
        )
        notes = workflow.get("notes")
        if notes:
            lines.append(f"- Notes: {notes}")
    return "\n".join(lines) + "\n"


def render_capability_check_markdown(report: Mapping[str, Any]) -> str:
    """Render a focused-check receipt."""
    lines = [
        f"# Capability Check: {report['id']}",
        "",
        f"Status: {report['status']}",
    ]
    for check in report["checks"]:
        lines.append(
            "- "
            + check["kind"]
            + " (exit "
            + str(check["returncode"])
            + "): `"
            + " ".join(check["command"])
            + "`"
        )
        for output_name in ("stdout", "stderr"):
            output = check.get(output_name)
            if output:
                lines.extend((f"  {output_name}:", output.rstrip()))
    return "\n".join(lines) + "\n"


def _focused_commands(workflow: Mapping[str, Any]) -> list[tuple[str, list[str]]]:
    pytest_nodes = _string_list(workflow["pytest_nodes"], "pytest_nodes", workflow["id"])
    rust_nodes = _string_list(workflow["rust_nodes"], "rust_nodes", workflow["id"])
    commands: list[tuple[str, list[str]]] = []
    if pytest_nodes:
        commands.append(("pytest", ["uv", "run", "pytest", *pytest_nodes, "-q"]))
    commands.extend(
        ("rust", ["cargo", "test", "-p", "wolfppt-core", rust_node])
        for rust_node in rust_nodes
    )
    if not commands:
        raise CapabilityPlanError(
            f"capability {workflow['id']} has no focused checks defined"
        )
    return commands


def _string_list(value: object, field: str, workflow_id: object) -> Sequence[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise CapabilityPlanError(
            f"capability {workflow_id!r} {field} must be strings"
        )
    return value


def _render_values(values: Sequence[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"
