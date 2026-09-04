"""Payload helpers for group-shape child facade objects."""

from __future__ import annotations

from typing import Any


def _group_child_payload(
    child: dict[str, Any],
    group_shape_index: int,
    group_index: int,
    child_index: int,
    nested_group_child_index: int | None = None,
    deeper_group_child_index: int | None = None,
    *,
    group_shape_id: int | None = None,
) -> dict[str, Any]:
    payload = dict(child)
    payload["_group_child"] = True
    payload["_group_shape_index"] = group_shape_index
    payload["_group_index"] = group_index
    payload["_group_child_index"] = child_index
    if group_shape_id is not None:
        payload["_group_shape_id"] = group_shape_id
    if nested_group_child_index is not None:
        payload["_nested_group_child"] = True
        payload["_nested_group_child_index"] = nested_group_child_index
        if child.get("kind") == "group":
            payload["_deep_nested_group_target"] = True
    if deeper_group_child_index is not None:
        payload["_deep_nested_group_child"] = True
        payload["_deeper_group_child_index"] = deeper_group_child_index
    return payload


def _pending_group_child_payload(
    kind: str,
    group_shape_index: int,
    group_index: int,
    child_index: int,
    nested_group_child_index: int | None = None,
    deeper_group_child_index: int | None = None,
    *,
    mark_deep_nested_target: bool = False,
) -> dict[str, Any]:
    payload = {
        "_group_child": True,
        "_pending_group_child": True,
        "_pending_group_child_kind": kind,
        "_group_shape_index": group_shape_index,
        "_group_index": group_index,
        "_group_child_index": child_index,
    }
    if nested_group_child_index is not None:
        payload.update(
            {
                "_nested_group_child": True,
                "_nested_group_child_index": nested_group_child_index,
            }
        )
        if mark_deep_nested_target:
            payload["_deep_nested_group_target"] = True
    if deeper_group_child_index is not None:
        payload.update(
            {
                "_deep_nested_group_child": True,
                "_deeper_group_child_index": deeper_group_child_index,
            }
        )
    return payload
