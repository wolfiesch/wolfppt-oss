"""Slide payload helpers used while saving presentations."""

from __future__ import annotations

from typing import Any


def full_slide_payloads_for_save(
    owner: Any,
    edits: Any,
) -> list[dict[str, Any]] | None:
    payloads = slide_part_payloads_for_save(owner, edits)
    if payloads is None:
        return None
    if any("shapes" not in payload for payload in payloads):
        return None
    return payloads


def slide_part_payloads_for_save(
    owner: Any,
    edits: Any,
) -> list[dict[str, Any]] | None:
    if edits.slide_creations or edits.shape_adds:
        return None
    payloads = [slide._payload for slide in owner._slides]
    if any("part" not in payload for payload in payloads):
        return None
    return payloads
