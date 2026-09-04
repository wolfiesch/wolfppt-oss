"""Queued text edits for pending group child shapes."""

from __future__ import annotations

from typing import Any


def queue_pending_group_child_text(shape: Any, text: str) -> bool:
    if not shape._payload.get("_pending_group_child"):
        return False
    if shape._payload.get("_deep_nested_group_child"):
        if shape._payload.get("_pending_group_child_kind") == "auto_shape":
            queue_method = (
                shape._slide._presentation._queue_deeper_nested_group_auto_shape_text
            )
        elif shape._payload.get("_pending_group_child_kind") == "freeform":
            queue_method = (
                shape._slide._presentation._queue_deeper_nested_group_freeform_shape_text
            )
        else:
            queue_method = shape._slide._presentation._queue_deeper_nested_group_text_box_text
        queue_method(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_nested_group_child_index"]),
            int(shape._payload["_deeper_group_child_index"]),
            int(shape._payload["_group_child_index"]),
            text,
        )
        return True
    if shape._payload.get("_nested_group_child"):
        if shape._payload.get("_pending_group_child_kind") == "auto_shape":
            queue_method = shape._slide._presentation._queue_nested_group_auto_shape_text
        elif shape._payload.get("_pending_group_child_kind") == "freeform":
            queue_method = shape._slide._presentation._queue_nested_group_freeform_shape_text
        else:
            queue_method = shape._slide._presentation._queue_nested_group_text_box_text
        queue_method(
            shape._slide._index,
            int(shape._payload["_group_index"]),
            int(shape._payload["_nested_group_child_index"]),
            int(shape._payload["_group_child_index"]),
            text,
        )
        return True
    pending_kind = shape._payload.get("_pending_group_child_kind")
    if pending_kind == "auto_shape":
        queue_method = shape._slide._presentation._queue_group_auto_shape_text
    elif pending_kind == "freeform":
        queue_method = shape._slide._presentation._queue_group_freeform_shape_text
    else:
        queue_method = shape._slide._presentation._queue_group_text_box_text
    queue_method(
        shape._slide._index,
        int(shape._payload["_group_index"]),
        int(shape._payload["_group_child_index"]),
        text,
    )
    return True
