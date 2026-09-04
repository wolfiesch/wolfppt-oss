"""Media child additions for group-shape collections."""

from __future__ import annotations

from typing import Any

from .facade_values import coerce_emu as _coerce_emu
from .image_dimensions import picture_dimensions as _picture_dimensions
from .image_inputs import (
    binary_source_for_queue as _binary_source_for_queue,
    image_source_for_queue as _image_source_for_queue,
)
from .shape_core_facade import Shape
from .shape_group_payloads import _pending_group_child_payload


def add_group_ole_object(
    collection: Any,
    object_file: Any,
    prog_id: Any,
    left: int,
    top: int,
    width: int | None = None,
    height: int | None = None,
    icon_file: Any = None,
    icon_width: int | None = None,
    icon_height: int | None = None,
) -> Shape:
    object_source = _binary_source_for_queue(object_file, "object.bin")
    icon_source = None if icon_file is None else _image_source_for_queue(icon_file)
    prog_id_value = str(getattr(prog_id, "progId", prog_id))
    default_width = int(getattr(prog_id, "width", 965200))
    default_height = int(getattr(prog_id, "height", 609600))
    x_emu = _coerce_emu(left, "left")
    y_emu = _coerce_emu(top, "top")
    cx_emu = default_width if width is None else _coerce_emu(width, "width")
    cy_emu = default_height if height is None else _coerce_emu(height, "height")
    icon_cx_emu = (
        965200 if icon_width is None else _coerce_emu(icon_width, "icon_width")
    )
    icon_cy_emu = (
        609600 if icon_height is None else _coerce_emu(icon_height, "icon_height")
    )
    child_index = len(collection._shapes)
    group_index = collection._group_ordinal()
    nested_group_child_index: int | None = None
    deeper_group_child_index: int | None = None
    if collection._is_deeper_nested_group_target():
        group_index = int(collection._group_shape._payload["_group_index"])
        nested_group_child_index = int(
            collection._group_shape._payload["_nested_group_child_index"]
        )
        deeper_group_child_index = int(
            collection._group_shape._payload["_group_child_index"]
        )
        collection._group_shape._slide._presentation._queue_deeper_nested_group_ole_object_add(
            collection._group_shape._slide._index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            child_index,
            object_source,
            prog_id_value,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_source,
            icon_cx_emu,
            icon_cy_emu,
        )
    elif collection._is_nested_group_target():
        group_index = int(collection._group_shape._payload["_group_index"])
        nested_group_child_index = int(
            collection._group_shape._payload["_group_child_index"]
        )
        collection._group_shape._slide._presentation._queue_nested_group_ole_object_add(
            collection._group_shape._slide._index,
            group_index,
            nested_group_child_index,
            child_index,
            object_source,
            prog_id_value,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_source,
            icon_cx_emu,
            icon_cy_emu,
        )
    else:
        collection._group_shape._slide._presentation._queue_group_ole_object_add(
            collection._group_shape._slide._index,
            group_index,
            child_index,
            object_source,
            prog_id_value,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_source,
            icon_cx_emu,
            icon_cy_emu,
        )
    group_payload = _pending_group_child_payload(
        "ole_object",
        collection._group_shape._index,
        group_index,
        child_index,
        nested_group_child_index,
        deeper_group_child_index,
    )
    shape = Shape(
        collection._group_shape._slide,
        child_index,
        {
            **collection._pending_group_child_identity(),
            "name": collection._next_pending_shape_name("Object"),
            "kind": "ole_object",
            "text": "",
            "paragraphs": [],
            "paragraph_runs": [],
            "transform": {
                "x": x_emu,
                "y": y_emu,
                "cx": cx_emu,
                "cy": cy_emu,
            },
            **group_payload,
        },
    )
    collection._append_pending_shape(shape)
    return shape


def add_group_picture(
    collection: Any,
    image_file: Any,
    left: int,
    top: int,
    width: int | None = None,
    height: int | None = None,
) -> Shape:
    x_emu = _coerce_emu(left, "left")
    y_emu = _coerce_emu(top, "top")
    image_source = _image_source_for_queue(image_file)
    cx_emu, cy_emu = _picture_dimensions(image_source, width, height)
    child_index = len(collection._shapes)
    group_index = collection._group_ordinal()
    nested_group_child_index: int | None = None
    deeper_group_child_index: int | None = None
    if collection._is_deeper_nested_group_target():
        group_index = int(collection._group_shape._payload["_group_index"])
        nested_group_child_index = int(
            collection._group_shape._payload["_nested_group_child_index"]
        )
        deeper_group_child_index = int(
            collection._group_shape._payload["_group_child_index"]
        )
        collection._group_shape._slide._presentation._queue_deeper_nested_group_picture_add(
            collection._group_shape._slide._index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            child_index,
            image_source,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    elif collection._is_nested_group_target():
        group_index = int(collection._group_shape._payload["_group_index"])
        nested_group_child_index = int(
            collection._group_shape._payload["_group_child_index"]
        )
        collection._group_shape._slide._presentation._queue_nested_group_picture_add(
            collection._group_shape._slide._index,
            group_index,
            nested_group_child_index,
            child_index,
            image_source,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    else:
        collection._group_shape._slide._presentation._queue_group_picture_add(
            collection._group_shape._slide._index,
            group_index,
            child_index,
            image_source,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    group_payload = _pending_group_child_payload(
        "picture",
        collection._group_shape._index,
        group_index,
        child_index,
        nested_group_child_index,
        deeper_group_child_index,
    )
    shape = Shape(
        collection._group_shape._slide,
        child_index,
        {
            **collection._pending_group_child_identity(),
            "name": collection._next_pending_shape_name("Picture"),
            "kind": "picture",
            "text": "",
            "paragraphs": [],
            "paragraph_runs": [],
            "transform": {
                "x": x_emu,
                "y": y_emu,
                "cx": cx_emu,
                "cy": cy_emu,
            },
            "has_picture": True,
            "_image_file": image_source,
            **group_payload,
        },
    )
    collection._append_pending_shape(shape)
    return shape
