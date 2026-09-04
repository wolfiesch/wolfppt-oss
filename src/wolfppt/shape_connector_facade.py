"""Connector endpoint helpers for shape facade objects."""

from __future__ import annotations

from typing import Any

from .package_parts import package_xml_element as _package_xml_element
from .shape_edit_refs import shape_edit_ref as _shape_edit_ref
from .shape_payloads import (
    _shape_transform,
    _shape_transform_value,
)
from .shape_xml import _shape_xml_element

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def connector_endpoint_value(shape: Any, end: str, axis: str) -> int:
    if shape._payload.get("kind") != "connector":
        raise AttributeError(f"'Shape' object has no attribute '{end}_{axis}'")
    payload_key = f"{end}_{axis}"
    if payload_key in shape._payload:
        return int(shape._payload[payload_key])
    origin = _shape_transform_value(shape, axis)
    extent_key = "cx" if axis == "x" else "cy"
    extent = _shape_transform_value(shape, extent_key)
    flipped = _connector_transform_flipped(shape, "h" if axis == "x" else "v")
    if end == "begin":
        return origin + extent if flipped else origin
    return origin if flipped else origin + extent


def connect_connector_endpoint(
    connector: Any,
    endpoint: str,
    shape: Any,
    cxn_pt_idx: int,
) -> None:
    if connector._payload.get("kind") != "connector":
        raise AttributeError("'Shape' object has no connector connection API")
    if not isinstance(cxn_pt_idx, int):
        raise TypeError("connection point index must be an integer")
    if not hasattr(shape, "shape_id"):
        raise TypeError("shape must be a shape-like object with a shape_id")
    target_shape_id = shape.shape_id
    payload = getattr(shape, "_payload", {})
    if target_shape_id is None and (
        payload.get("_pending_shape") or payload.get("_pending_group_child")
    ):
        raise NotImplementedError("connecting to unsaved shapes is not supported yet")
    if not isinstance(target_shape_id, int):
        raise TypeError(
            f"value must be an integral type, got {type(target_shape_id)}"
        )
    x_emu, y_emu = _shape_connection_point(shape, cxn_pt_idx)
    if endpoint == "begin":
        begin_x, begin_y = x_emu, y_emu
        end_x = connector_endpoint_value(connector, "end", "x")
        end_y = connector_endpoint_value(connector, "end", "y")
    else:
        begin_x = connector_endpoint_value(connector, "begin", "x")
        begin_y = connector_endpoint_value(connector, "begin", "y")
        end_x, end_y = x_emu, y_emu
    transform = {
        "x": min(begin_x, end_x),
        "y": min(begin_y, end_y),
        "cx": abs(end_x - begin_x),
        "cy": abs(end_y - begin_y),
    }
    flip_h = begin_x > end_x
    flip_v = begin_y > end_y
    connector._payload.update(
        {
            "begin_x": begin_x,
            "begin_y": begin_y,
            "end_x": end_x,
            "end_y": end_y,
            "flip_h": flip_h,
            "flip_v": flip_v,
            "transform": transform,
            "effective_transform": transform,
            f"{endpoint}_connection": {
                "shape_id": target_shape_id,
                "cxn_pt_idx": cxn_pt_idx,
            },
        }
    )
    connector._slide._presentation._queue_connector_connection(
        connector._slide._index,
        _shape_edit_ref(connector),
        endpoint,
        {"shape_id": target_shape_id, "cxn_pt_idx": cxn_pt_idx},
        begin_x,
        begin_y,
        end_x,
        end_y,
        transform,
        flip_h,
        flip_v,
    )


def _connector_transform_flipped(shape: Any, axis: str) -> bool:
    payload_key = "flip_h" if axis == "h" else "flip_v"
    if payload_key in shape._payload:
        return bool(shape._payload[payload_key])
    if shape._payload.get("_pending_group_child") or shape.shape_id is None:
        return False
    root = _package_xml_element(
        shape._slide._presentation.path,
        shape._slide.partname,
    )
    element = _shape_xml_element(root._element, shape._payload)
    xfrm = element.find(f"./{{{P_NS}}}spPr/{{{A_NS}}}xfrm")
    if xfrm is None:
        xfrm = element.find(f"./{{{P_NS}}}xfrm")
    if xfrm is None:
        return False
    attr = "flipH" if axis == "h" else "flipV"
    return xfrm.attrib.get(attr) in {"1", "true", "True"}


def _shape_connection_point(shape: Any, cxn_pt_idx: int) -> tuple[int, int]:
    transform = _shape_transform(shape)
    left = transform["x"]
    top = transform["y"]
    width = transform["cx"]
    height = transform["cy"]
    connection_points = {
        0: (left + width // 2, top),
        1: (left, top + height // 2),
        2: (left + width // 2, top + height),
        3: (left + width, top + height // 2),
    }
    return connection_points[cxn_pt_idx]
