"""Shared typed dictionaries for compatibility spec data."""

from __future__ import annotations

from typing import Literal, TypedDict


class Category(TypedDict):
    id: str
    title: str


class Entry(TypedDict, total=False):
    id: str
    category: str
    capability: str
    priority: str
    status: str
    oracle: str
    notes: str
    gap_id: str


class CapabilityWorkflow(TypedDict):
    id: str
    tier: Literal["A"]
    domain: str
    rank: int
    status: Literal["planned", "implemented", "verified"]
    capability_id: str
    capability: str
    python_pptx_probe: str
    fixture: str
    pytest_nodes: list[str]
    rust_nodes: list[str]
    expected_changed_parts: list[str]
    mutation_route: str
    notes: str
