"""Shared benchmark adapter registry metadata types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkAdapterSpec:
    name: str
    operation: str
    role: str
    available: str
    run: str
    unavailable_reason: str | None = None
