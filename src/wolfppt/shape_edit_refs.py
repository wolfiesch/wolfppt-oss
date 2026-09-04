"""Shared shape edit reference helpers."""

from __future__ import annotations

from typing import Any

ShapeEditRef = int | tuple[int, ...]


def queued_shape_add_weight(add_kind: str) -> int:
    if add_kind.startswith("nested_group_") and add_kind.endswith("_in_new_group"):
        return 2
    if add_kind in {
        "connected_connector_with_auto_shapes",
        "connected_group_connector_with_auto_shapes",
    }:
        return 3
    return 1


def shape_edit_ref(shape: Any) -> ShapeEditRef:
    payload = shape._payload
    if not payload.get("_group_child"):
        return shape._index
    if payload.get("_deep_nested_group_child"):
        return (
            int(payload["_group_index"]),
            int(payload["_nested_group_child_index"]),
            int(payload["_deeper_group_child_index"]),
            int(payload["_group_child_index"]),
        )
    if payload.get("_nested_group_child"):
        return (
            int(payload["_group_index"]),
            int(payload["_nested_group_child_index"]),
            int(payload["_group_child_index"]),
        )
    return (
        int(payload.get("_group_shape_index", payload["_group_index"])),
        int(payload["_group_child_index"]),
    )
