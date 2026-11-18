"""Connector endpoint helpers for shape facade objects."""

from __future__ import annotations

import math
from typing import Any

from .facade_values import coerce_emu as _coerce_emu
from .package_parts import package_xml_element as _package_xml_element
from .render_model import Affine, Rect
from .shape_edit_refs import shape_edit_ref as _shape_edit_ref
from .shape_locks import check_shape_geometry_locks
from .shape_payloads import (
    _group_insertion_frame,
    _shape_transform,
    _shape_transform_value,
)
from .shape_xml import (
    _find_shape_transform_xml_element,
    _shape_xml_element,
    parse_ooxml_bool,
)

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


def set_connector_endpoint_value(shape: Any, end: str, axis: str, value: Any) -> None:
    """Move one endpoint coordinate, keeping the other endpoint fixed.

    Mirrors python-pptx: the offset, extent and flip on that axis are rewritten
    and existing connections are left in place.
    """
    if shape._payload.get("kind") != "connector":
        raise AttributeError(f"'Shape' object has no attribute '{end}_{axis}'")
    new = _coerce_emu(value, f"{end}_{axis}")
    transform = _shape_transform(shape)
    flips = {
        "h": _connector_transform_flipped(shape, "h"),
        "v": _connector_transform_flipped(shape, "v"),
    }
    flip_axis = "h" if axis == "x" else "v"
    extent_key = "cx" if axis == "x" else "cy"
    origin, extent = transform[axis], transform[extent_key]
    far = origin + extent
    # The begin point sits at the origin unless flipped; the end point opposite.
    if (end == "begin") != flips[flip_axis]:
        if new <= far:
            origin, extent = new, far - new
        else:
            origin, extent = far, new - far
            flips[flip_axis] = not flips[flip_axis]
    elif new >= origin:
        extent = new - origin
    else:
        origin, extent = new, origin - new
        flips[flip_axis] = not flips[flip_axis]
    transform[axis], transform[extent_key] = origin, extent
    check_shape_geometry_locks(shape, transform)
    flip_h, flip_v = flips["h"], flips["v"]
    shape._payload.update(
        {
            "begin_x": transform["x"] + transform["cx"] if flip_h else transform["x"],
            "begin_y": transform["y"] + transform["cy"] if flip_v else transform["y"],
            "end_x": transform["x"] if flip_h else transform["x"] + transform["cx"],
            "end_y": transform["y"] if flip_v else transform["y"] + transform["cy"],
            "flip_h": flip_h,
            "flip_v": flip_v,
            "flip_horizontal": flip_h,
            "flip_vertical": flip_v,
            "transform": transform,
            "effective_transform": dict(transform),
        }
    )
    presentation = shape._slide._presentation
    key = (shape._slide._index, _shape_edit_ref(shape))
    edits = presentation._connector_connection_edits.setdefault(key, {})
    edits["transform"] = dict(transform)
    edits["flip_h"] = flip_h
    edits["flip_v"] = flip_v
    # Flip edits apply after connector edits; keep an earlier one consistent.
    flip_record = presentation._shape_flip_edits.get(key)
    if flip_record is not None:
        flip_record.update(flip_h=flip_h, flip_v=flip_v)


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
        raise TypeError(f"value must be an integral type, got {type(target_shape_id)}")
    if getattr(shape, "_slide", None) is not connector._slide:
        raise ValueError("connector target must belong to the same slide")
    x_emu, y_emu = _shape_connection_point(shape, cxn_pt_idx)
    x_emu, y_emu = _connection_point_in_parent(connector, shape, x_emu, y_emu)
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
    check_shape_geometry_locks(connector, transform)
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
    reference = _shape_edit_ref(connector)
    if connector._payload.get("_pending_shape") or connector._payload.get("_pending_group_child"):
        # Keep authored insertion geometry stable, then apply the attachment
        # transform through the signed-coordinate edit path. Rewriting an
        # insertion would also change a group's child coordinate frame.
        edits = connector._slide._presentation._connector_connection_edits.setdefault(
            (connector._slide._index, reference), {}
        )
        edits[endpoint] = {"shape_id": target_shape_id, "cxn_pt_idx": cxn_pt_idx}
        edits["transform"] = dict(transform)
        edits["flip_h"] = flip_h
        edits["flip_v"] = flip_v
    else:
        presentation = connector._slide._presentation
        presentation._queue_connector_connection(
            connector._slide._index,
            reference,
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
        # A queued insertion absorbs the attachment, but an earlier endpoint
        # move may still hold a transform edit that would override it.
        queued = presentation._connector_connection_edits.get((connector._slide._index, reference))
        if queued is not None:
            queued.update(transform=dict(transform), flip_h=flip_h, flip_v=flip_v)


def disconnect_connector_endpoint(connector: Any, endpoint: str) -> None:
    """Detach one connector endpoint, keeping its current geometry.

    The removal is queued as an explicit ``None`` edit so it also clears a
    connection baked into a queued connector insertion or read from the file.
    """
    if connector._payload.get("kind") != "connector":
        raise AttributeError("'Shape' object has no connector connection API")
    connector._payload.pop(f"{endpoint}_connection", None)
    key = (connector._slide._index, _shape_edit_ref(connector))
    edits = connector._slide._presentation._connector_connection_edits
    edits.setdefault(key, {})[endpoint] = None


def _connector_transform_flipped(shape: Any, axis: str) -> bool:
    payload_key = "flip_h" if axis == "h" else "flip_v"
    if payload_key in shape._payload:
        return bool(shape._payload[payload_key])
    begin_key, end_key = ("begin_x", "end_x") if axis == "h" else ("begin_y", "end_y")
    if begin_key in shape._payload and end_key in shape._payload:
        return int(shape._payload[begin_key]) > int(shape._payload[end_key])
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


def _shape_connection_point(shape: Any, cxn_pt_idx: int) -> tuple[float, float]:
    transform = _shape_transform(shape)
    left = transform["x"]
    top = transform["y"]
    width = transform["cx"]
    height = transform["cy"]
    connection_points = {
        0: (left + width / 2, top),
        1: (left, top + height / 2),
        2: (left + width / 2, top + height),
        3: (left + width, top + height / 2),
    }
    x, y = connection_points[cxn_pt_idx]
    payload = shape._payload
    xfrm = None
    if not (payload.get("_pending_shape") or payload.get("_pending_group_child")):
        root = _package_xml_element(shape._slide._presentation.path, shape._slide.partname)
        element = _shape_xml_element(root._element, payload)
        xfrm = _find_shape_transform_xml_element(element)
    rotation = payload.get("rotation")
    if rotation is None:
        try:
            rotation = int(xfrm.get("rot", "0")) / 60000.0 if xfrm is not None else 0
        except ValueError as exc:
            raise ValueError("target coordinate rotation is malformed") from exc
    if not math.isfinite(rotation):
        raise ValueError("target coordinate rotation must be finite")

    def flipped(axis: str, long_axis: str) -> bool:
        return parse_ooxml_bool(
            payload.get(
                f"flip_{long_axis}",
                payload.get(
                    f"flip_{axis}",
                    xfrm.get(f"flip{axis.upper()}") if xfrm is not None else None,
                ),
            )
        )

    # Reflect in the target's own box before rotating in its parent frame.
    # Keep fractional coordinates through the ancestor maps; round only once.
    if flipped("h", "horizontal"):
        x = 2 * left + width - x
    if flipped("v", "vertical"):
        y = 2 * top + height - y
    if rotation % 360:
        return Affine.rotation_about(left + width / 2, top + height / 2, rotation).apply(x, y)
    return x, y


def _connection_parent_groups(shape: Any) -> tuple[Any, ...]:
    """Find the live parent chain, including queued group children."""

    def visit(shapes: Any, parents: tuple[Any, ...]) -> tuple[Any, ...] | None:
        for candidate in shapes:
            if candidate is shape:
                return parents
            if candidate._payload.get("kind") == "group":
                found = visit(candidate.shapes, (*parents, candidate))
                if found is not None:
                    return found
        return None

    parents = visit(shape._slide.shapes, ())
    if parents is None or shape._payload.get("_deleted"):
        raise ValueError("connector and target must be live shapes on the same slide")
    return parents


def _group_coordinate_map(group: Any) -> Affine:
    """Use the scene's DrawingML box-map, flips, then clockwise rotation."""
    xfrm = None
    if group._payload.get("_pending_shape"):
        # Only authored groups own inferred frames. Loaded malformed/zero
        # transforms must still fail validation rather than becoming identity.
        frame = _group_insertion_frame(group)
    else:
        root = _package_xml_element(group._slide._presentation.path, group._slide.partname)
        element = _shape_xml_element(root._element, group._payload)
        xfrm = element.find(f"./{{{P_NS}}}grpSpPr/{{{A_NS}}}xfrm")
        if xfrm is None:
            raise ValueError("group coordinate transform is missing")
        # Validate the source even when insertion has cached a derived frame.
        for tag, axes in (
            ("off", ("x", "y")),
            ("ext", ("cx", "cy")),
            ("chOff", ("x", "y")),
            ("chExt", ("cx", "cy")),
        ):
            field = xfrm.find(f"{{{A_NS}}}{tag}")
            if field is None:
                raise ValueError("group coordinate transform is incomplete")
            try:
                values = [int(field.attrib[axis]) for axis in axes]
            except (KeyError, ValueError) as exc:
                raise ValueError("group coordinate transform is malformed") from exc
            if tag in {"ext", "chExt"} and min(values) <= 0:
                raise ValueError("group coordinate transform must have positive extents")
        frame = _group_insertion_frame(group)
    child_x, child_y, child_width, child_height = frame[4:]
    transform = _shape_transform(group)
    box = Rect(transform["x"], transform["y"], transform["cx"], transform["cy"])
    child_box = Rect(child_x, child_y, child_width, child_height)
    if min(box.width, box.height, child_box.width, child_box.height) <= 0:
        raise ValueError("group coordinate transform must have positive extents")
    rotation = group._payload.get("rotation")
    if rotation is None:
        try:
            rotation = int(xfrm.get("rot", "0")) / 60000.0 if xfrm is not None else 0
        except ValueError as exc:
            raise ValueError("group coordinate rotation is malformed") from exc
    if not math.isfinite(rotation):
        raise ValueError("group coordinate rotation must be finite")

    def flipped(axis: str, long_axis: str) -> bool:
        payload = group._payload
        return parse_ooxml_bool(
            payload.get(
                f"flip_{long_axis}",
                payload.get(
                    f"flip_{axis}",
                    xfrm.get(f"flip{axis.upper()}") if xfrm is not None else None,
                ),
            )
        )

    mapping = Affine.box_map(
        child_box,
        box,
        flip_h=flipped("h", "horizontal"),
        flip_v=flipped("v", "vertical"),
    )
    if rotation % 360:
        mapping = mapping.then(
            Affine.rotation_about(box.x + box.width / 2, box.y + box.height / 2, rotation)
        )
    return mapping


def _connection_point_in_parent(connector: Any, target: Any, x: float, y: float) -> tuple[int, int]:
    target_groups = _connection_parent_groups(target)
    connector_groups = _connection_parent_groups(connector)
    shared = 0
    for target_group, connector_group in zip(target_groups, connector_groups, strict=False):
        if target_group is not connector_group:
            break
        shared += 1
    # Shared ancestors cancel. Same-group connections avoid a floating-point
    # ancestor round trip, retaining only the target's own orientation.
    for group in reversed(target_groups[shared:]):
        x, y = _group_coordinate_map(group).apply(x, y)
    for group in connector_groups[shared:]:
        mapping = _group_coordinate_map(group)
        determinant = mapping.a * mapping.d - mapping.b * mapping.c
        if not math.isfinite(determinant) or determinant == 0:
            raise ValueError("group coordinate transform is not invertible")
        translated_x, translated_y = x - mapping.e, y - mapping.f
        x = (mapping.d * translated_x - mapping.c * translated_y) / determinant
        y = (mapping.a * translated_y - mapping.b * translated_x) / determinant
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("connector coordinates must be finite")
    return round(x), round(y)
