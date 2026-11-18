"""Shape stacking (z-order) edits and XML reordering for PresentationML."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any, Literal
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements
from .shape_edit_refs import ShapeEditRef, shape_edit_ref
from .slide_payloads import load_slide_payloads
from .xml_helpers import xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

ZOrderAction = Literal[
    "bring_to_front", "send_to_back", "bring_forward", "send_backward"
]
VALID_Z_ORDER_ACTIONS: frozenset[str] = frozenset(
    {"bring_to_front", "send_to_back", "bring_forward", "send_backward"}
)

SHAPE_TAGS: frozenset[str] = frozenset(
    {"sp", "pic", "graphicFrame", "grpSp", "cxnSp", "contentPart"}
)
HEADER_TAGS: frozenset[str] = frozenset({"nvGrpSpPr", "grpSpPr"})
TRAILER_TAGS: frozenset[str] = frozenset({"extLst"})


def _is_pending_shape(shape: Any) -> bool:
    payload = getattr(shape, "_payload", {})
    return bool(payload.get("_pending_shape") or payload.get("_pending_group_child"))


def validate_shape_z_order_target(shape: Any) -> None:
    """Validate that a shape can participate in z-order operations.

    Refuses deleted shapes and shapes on deleted slides before any mutation
    occurs. Top-level shapes added in the current session are accepted.
    Unsaved shapes inside a group are refused: group child removal reindexes
    children by collection position, which a mirrored reorder would corrupt.
    """
    payload = getattr(shape, "_payload", {})
    if payload.get("_deleted"):
        raise ValueError("cannot change z-order of a deleted shape")
    slide = getattr(shape, "_slide", None)
    if slide is not None and getattr(slide, "_deleted", False):
        raise ValueError("cannot change z-order of a deleted shape")
    if payload.get("_group_child"):
        group_shape = getattr(shape, "_parent_group", None)
        if group_shape is not None and group_shape._payload.get("_deleted"):
            raise ValueError("cannot change z-order of a deleted shape")
        if _is_pending_shape(shape) or _is_pending_shape(group_shape):
            raise NotImplementedError(
                "changing z-order of an unsaved shape inside a group is not "
                "supported yet"
            )


def queue_shape_z_order_action(shape: Any, action: str) -> None:
    """Validate and enqueue a shape stacking order operation."""
    if action not in VALID_Z_ORDER_ACTIONS:
        raise ValueError(
            f"invalid z-order action: {action!r}; expected one of {sorted(VALID_Z_ORDER_ACTIONS)}"
        )
    validate_shape_z_order_target(shape)
    slide = shape._slide
    presentation = slide._presentation
    ref = shape_edit_ref(shape)
    if isinstance(ref, int) and any(_is_pending_shape(s) for s in slide.shapes):
        _queue_mirrored_z_order(presentation, slide, shape, action)
        return
    presentation._queue_shape_z_order(slide._index, ref, action)


def _move_shape(
    order: list[Any], target: Any, action: str
) -> tuple[str, int, list[Any]]:
    """Apply one action to an in-memory order as bounded single steps.

    Returns the step action, its repeat count, and the resulting order.
    """
    position = next(i for i, shape in enumerate(order) if shape is target)
    last = len(order) - 1
    if action == "bring_to_front":
        step, count, new_position = "bring_forward", last - position, last
    elif action == "send_to_back":
        step, count, new_position = "send_backward", position, 0
    elif action == "bring_forward":
        count = int(position < last)
        step, new_position = "bring_forward", position + count
    else:
        count = int(position > 0)
        step, new_position = "send_backward", position - count
    moved = [shape for shape in order if shape is not target]
    moved.insert(new_position, target)
    return step, count, moved


def _queue_mirrored_z_order(
    presentation: Any, slide: Any, shape: Any, action: str
) -> None:
    """Queue a z-order edit on a slide holding unsaved shapes, mirrored in memory.

    After save, held unsaved shapes bind to inserted XML elements by relative
    position, so the collection must already hold the saved stacking order.
    Shape additions are written before z-order edits replay, so every queued
    edit for this shape tree is rewritten as bounded single steps: replaying
    them then never moves a shape past shapes added after the call. The
    current order is rebuilt by replaying those edits over the
    materialization order (``_index``), which also absorbs removals.
    """
    collection = slide.shapes
    by_ref = {member._index: member for member in collection}
    if len(by_ref) != len(collection):
        raise NotImplementedError(
            "changing z-order on a slide with unsaved shapes after removing a "
            "shape is not supported yet; save the presentation first"
        )
    slide_index = slide._index
    order = sorted(by_ref.values(), key=lambda member: member._index)
    rewritten: list[tuple[int, Any, str]] = []
    for edit in presentation._shape_z_order_edits:
        edit_slide, edit_ref, edit_action = edit
        target = by_ref.get(edit_ref) if edit_slide == slide_index else None
        if target is None:
            rewritten.append(edit)
            continue
        step, count, order = _move_shape(order, target, edit_action)
        rewritten.extend([(slide_index, edit_ref, step)] * count)
    step, count, order = _move_shape(order, shape, action)
    rewritten.extend([(slide_index, shape._index, step)] * count)
    presentation._shape_z_order_edits[:] = rewritten
    collection._shapes[:] = order


def bring_to_front(shape: Any) -> None:
    """Move shape to the front of its container's stacking order."""
    queue_shape_z_order_action(shape, "bring_to_front")


def send_to_back(shape: Any) -> None:
    """Move shape to the back of its container's stacking order."""
    queue_shape_z_order_action(shape, "send_to_back")


def bring_forward(shape: Any) -> None:
    """Move shape one step forward in its container's stacking order."""
    queue_shape_z_order_action(shape, "bring_forward")


def send_backward(shape: Any) -> None:
    """Move shape one step backward in its container's stacking order."""
    queue_shape_z_order_action(shape, "send_backward")


class PresentationZOrderQueueMixin:
    """Queue mixin for presentation shape z-order edits."""

    def _queue_shape_z_order(
        self,
        slide_index: int,
        shape_ref: ShapeEditRef,
        action: str,
    ) -> None:
        if not hasattr(self, "_shape_z_order_edits"):
            self._shape_z_order_edits = []
        self._shape_z_order_edits.append((slide_index, shape_ref, action))


def _shape_cNvPr(element: ET.Element) -> ET.Element | None:
    """Find the exact non-visual drawing properties element for a shape."""
    tag = xml_local_name(element.tag)
    if tag == "sp":
        return element.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
    if tag == "pic":
        return element.find(f"{{{P_NS}}}nvPicPr/{{{P_NS}}}cNvPr")
    if tag == "graphicFrame":
        return element.find(f"{{{P_NS}}}nvGraphicFramePr/{{{P_NS}}}cNvPr")
    if tag == "grpSp":
        return element.find(f"{{{P_NS}}}nvGrpSpPr/{{{P_NS}}}cNvPr")
    if tag == "cxnSp":
        return element.find(f"{{{P_NS}}}nvCxnSpPr/{{{P_NS}}}cNvPr")
    if tag == "contentPart":
        return element.find(f"{{{P_NS}}}nvContentPartPr/{{{P_NS}}}cNvPr")
    return element.find(f".//{{{P_NS}}}cNvPr")


def _resolve_shape_payload(
    slide_payload: dict[str, Any],
    shape_ref: ShapeEditRef,
) -> dict[str, Any]:
    """Resolve a ShapeEditRef against a slide payload snapshot."""
    if isinstance(shape_ref, tuple):
        try:
            child_payload = slide_payload["shapes"][shape_ref[0]]
            for child_index in shape_ref[1:]:
                child_payload = child_payload["children"][child_index]
        except IndexError as exc:
            raise IndexError("group child shape index out of range") from exc
        except KeyError as exc:
            raise AttributeError("group child shape payload is unavailable") from exc
        if not isinstance(child_payload, dict):
            raise TypeError("group child shape payload is unavailable")
        return child_payload
    try:
        return slide_payload["shapes"][shape_ref]
    except IndexError as exc:
        raise IndexError("shape index out of range") from exc


def _find_shape_element_by_id(
    root: ET.Element,
    shape_id: str | int,
) -> ET.Element | None:
    """Find a shape element in the slide shape tree by its cNvPr id."""
    str_id = str(shape_id)
    shape_tree = root.find(f".//{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if shape_tree is None:
        return None
    for element in shape_tree.iter():
        tag = xml_local_name(element.tag)
        if tag in SHAPE_TAGS:
            nv = _shape_cNvPr(element)
            if nv is not None and nv.attrib.get("id") == str_id:
                return element
    return None


def _build_parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    """Map each child element in root to its direct parent element."""
    return {child: parent for parent in root.iter() for child in parent}


def reorder_shape_elements(
    container: ET.Element,
    target_element: ET.Element,
    action: str,
) -> None:
    """Reorder a target shape within its parent container element.

    Preserves nvGrpSpPr/grpSpPr header elements at the front and extLst at the end,
    satisfying the PresentationML schema for p:spTree and p:grpSp.
    """
    if action not in VALID_Z_ORDER_ACTIONS:
        raise ValueError(
            f"invalid z-order action: {action!r}; expected one of {sorted(VALID_Z_ORDER_ACTIONS)}"
        )

    headers: list[ET.Element] = []
    shapes: list[ET.Element] = []
    trailers: list[ET.Element] = []

    for child in list(container):
        tag = xml_local_name(child.tag)
        if tag in HEADER_TAGS:
            headers.append(child)
        elif tag in TRAILER_TAGS:
            trailers.append(child)
        elif tag in SHAPE_TAGS:
            shapes.append(child)
        else:
            if not shapes:
                headers.append(child)
            else:
                trailers.append(child)

    target_index = -1
    for i, shape in enumerate(shapes):
        if shape is target_element:
            target_index = i
            break

    if target_index == -1:
        target_nv = _shape_cNvPr(target_element)
        target_id = target_nv.attrib.get("id") if target_nv is not None else None
        if target_id is not None:
            for i, shape in enumerate(shapes):
                nv = _shape_cNvPr(shape)
                if nv is not None and nv.attrib.get("id") == target_id:
                    target_index = i
                    break

    if target_index == -1:
        raise ValueError("target shape element is not a direct child of the container")

    if action == "bring_to_front":
        if target_index < len(shapes) - 1:
            shapes.append(shapes.pop(target_index))
    elif action == "send_to_back":
        if target_index > 0:
            shapes.insert(0, shapes.pop(target_index))
    elif action == "bring_forward":
        if target_index < len(shapes) - 1:
            shapes.insert(target_index + 1, shapes.pop(target_index))
    elif action == "send_backward" and target_index > 0:
        shapes.insert(target_index - 1, shapes.pop(target_index))

    new_children = headers + shapes + trailers
    for child in list(container):
        container.remove(child)
    for child in new_children:
        container.append(child)


def apply_shape_z_order_edits(
    input_path: str | Path,
    output_path: str | Path,
    z_order_edits: list[tuple[int, Any, str]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    """Apply queued shape z-order edits to a PPTX package.

    Must run AFTER all index-targeted edits (geometry, text, fill, etc.) so that
    those edits resolve existing positional references correctly.
    """
    in_path = Path(input_path)
    out_path = Path(output_path)
    if not z_order_edits and in_path != out_path:
        shutil.copy2(in_path, out_path)
        return

    slides = (
        slide_payloads if slide_payloads is not None else load_slide_payloads(in_path)
    )
    edits_by_slide: dict[int, list[tuple[Any, str]]] = {}
    for edit in z_order_edits:
        slide_index = edit[0]
        shape_ref = edit[1]
        action = edit[2]
        if slide_index < 0 or slide_index >= len(slides):
            raise IndexError("slide index out of range")
        slide_payload = slides[slide_index]
        shape_payload = _resolve_shape_payload(slide_payload, shape_ref)
        if shape_payload.get("_deleted"):
            raise ValueError("cannot change z-order of a deleted shape")
        if shape_payload.get("_pending_shape") or shape_payload.get(
            "_pending_group_child"
        ):
            raise NotImplementedError(
                "changing z-order of an unsaved shape is not supported yet"
            )
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, action))
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(in_path) as package:
        for slide_index, edits in edits_by_slide.items():
            slide_payload = slides[slide_index]
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            parent_map = _build_parent_map(root)

            for shape_ref, action in edits:
                shape_payload = _resolve_shape_payload(slide_payload, shape_ref)
                shape_id = shape_payload.get("id")
                if shape_id is None:
                    raise ValueError(f"shape payload missing id: {shape_payload}")
                shape_element = _find_shape_element_by_id(root, shape_id)
                if shape_element is None:
                    raise AttributeError(
                        f"shape XML element for id {shape_id} is unavailable"
                    )
                container = parent_map.get(shape_element)
                if container is None:
                    container = root.find(f".//{{{P_NS}}}cSld/{{{P_NS}}}spTree")
                    if container is None:
                        raise AttributeError("shape tree XML element is unavailable")
                reorder_shape_elements(container, shape_element, action)
                parent_map = _build_parent_map(root)

            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    copy_package_with_replacements(in_path, out_path, replacements)


_apply_shape_z_order_edits = apply_shape_z_order_edits


__all__ = [
    "HEADER_TAGS",
    "SHAPE_TAGS",
    "TRAILER_TAGS",
    "VALID_Z_ORDER_ACTIONS",
    "PresentationZOrderQueueMixin",
    "ZOrderAction",
    "_apply_shape_z_order_edits",
    "_build_parent_map",
    "_find_shape_element_by_id",
    "_resolve_shape_payload",
    "_shape_cNvPr",
    "apply_shape_z_order_edits",
    "bring_forward",
    "bring_to_front",
    "queue_shape_z_order_action",
    "reorder_shape_elements",
    "send_backward",
    "send_to_back",
    "validate_shape_z_order_target",
]
