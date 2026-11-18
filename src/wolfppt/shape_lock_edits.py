"""Package-level applicator for DrawingML / PresentationML shape lock edits."""

from __future__ import annotations

import shutil
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .shape_edit_refs import ShapeEditRef
from .shape_locks import (
    LOCK_PROPERTY_TO_XML_ATTR,
    LOCK_TAG_BY_KIND,
    NON_VISUAL_TAG_BY_KIND,
    VALID_LOCK_PROPERTIES_BY_KIND,
    ShapeLockUnsupportedError,
    ShapeLockValueError,
)
from .shape_xml import _shape_xml_element
from .slide_payloads import load_slide_payloads as _load_slide_payloads
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _shape_payload(
    slide_payload: dict[str, Any],
    shape_ref: ShapeEditRef,
) -> dict[str, Any]:
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
            raise TypeError("group child shape payload must be a mapping")
        return child_payload
    try:
        return slide_payload["shapes"][shape_ref]
    except IndexError as exc:
        raise IndexError("shape index out of range") from exc


def _set_shape_locks(
    shape_element: ET.Element,
    shape_payload: dict[str, Any],
    flags: dict[str, bool],
) -> None:
    local_tag = _xml_local_name(shape_element.tag)
    tag_to_kind = {
        "sp": "shape",
        "pic": "picture",
        "cxnSp": "connector",
        "grpSp": "group",
        "graphicFrame": "graphic_frame",
    }
    kind = tag_to_kind.get(local_tag)
    if kind is None:
        raise ShapeLockUnsupportedError(
            "shape lock editing requires a shape, picture, connector, group, or graphic frame; "
            f"received <p:{local_tag}>"
        )
    if kind == "graphic_frame" and shape_payload.get("kind") != kind:
        raise ShapeLockUnsupportedError(
            f"shape kind {shape_payload.get('kind')!r} does not support shape locks"
        )

    valid_props = VALID_LOCK_PROPERTIES_BY_KIND[kind]
    for prop, val in flags.items():
        if prop not in valid_props:
            raise ShapeLockUnsupportedError(
                f"lock property {prop!r} is not supported for {kind} shapes"
            )
        if type(val) is not bool:
            raise ShapeLockValueError(
                f"lock property {prop!r} must be a bool, got {type(val).__name__}"
            )

    nv_tag = {
        "sp": f"{{{P_NS}}}nvSpPr",
        "pic": f"{{{P_NS}}}nvPicPr",
        "cxnSp": f"{{{P_NS}}}nvCxnSpPr",
        "grpSp": f"{{{P_NS}}}nvGrpSpPr",
        "graphicFrame": f"{{{P_NS}}}nvGraphicFramePr",
    }[local_tag]

    nv = shape_element.find(f"./{nv_tag}")
    if nv is None:
        nv = ET.Element(nv_tag)
        shape_element.insert(0, nv)

    cnv_tag = NON_VISUAL_TAG_BY_KIND[kind]
    cnv = nv.find(f"./{cnv_tag}")
    if cnv is None:
        cnv = ET.Element(cnv_tag)
        insert_idx = len(nv)
        cnv_pr = nv.find(f"./{{{P_NS}}}cNvPr")
        if cnv_pr is not None:
            insert_idx = list(nv).index(cnv_pr) + 1
        nv.insert(insert_idx, cnv)

    lock_tag = LOCK_TAG_BY_KIND[kind]
    lock_element = cnv.find(f"./{lock_tag}")
    if lock_element is None and not any(flags.values()):
        return
    created = False
    if lock_element is None:
        created = True
        lock_element = ET.Element(lock_tag)
        if kind == "connector":
            # CT_NonVisualConnectorProperties sequence: cxnSpLocks?, stCxn?, endCxn?, extLst?
            insert_idx = len(cnv)
            for follower in (
                f"{{{A_NS}}}stCxn",
                f"{{{A_NS}}}endCxn",
                f"{{{A_NS}}}extLst",
            ):
                elem = cnv.find(follower)
                if elem is not None:
                    idx = list(cnv).index(elem)
                    insert_idx = min(insert_idx, idx)
            cnv.insert(insert_idx, lock_element)
        else:
            # Non-visual drawing properties: locks?, extLst?
            ext_lst = cnv.find(f"{{{A_NS}}}extLst")
            insert_idx = list(cnv).index(ext_lst) if ext_lst is not None else len(cnv)
            cnv.insert(insert_idx, lock_element)

    # Apply flag updates, preserving unknown attributes and existing authored attributes
    for prop_name, value in flags.items():
        attr_name = LOCK_PROPERTY_TO_XML_ATTR[prop_name]
        if value:
            lock_element.set(attr_name, "1")
        else:
            lock_element.attrib.pop(attr_name, None)

    # If newly created and has no attributes and no children, clean up
    if created and len(lock_element.attrib) == 0 and len(lock_element) == 0:
        cnv.remove(lock_element)


def apply_shape_lock_edits(
    input_path: str | Path,
    output_path: str | Path,
    lock_edits: Sequence[tuple[tuple[int, ShapeEditRef], dict[str, bool]]]
    | dict[tuple[int, ShapeEditRef], dict[str, bool]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    """Apply queued shape lock metadata edits to a PPTX package.

    Invalid flag mappings and non-bool values raise ``ShapeLockValueError``.
    Unsupported properties raise ``ShapeLockUnsupportedError``. Validate the
    whole batch before writing, preserving existing destinations on refusal.
    These metadata updates do not enforce locks on other editing APIs.
    """
    input_path = Path(input_path)
    edits_list = list(lock_edits.items()) if isinstance(lock_edits, Mapping) else list(lock_edits)

    for _target, flags in edits_list:
        if not isinstance(flags, Mapping):
            raise ShapeLockValueError(f"expected lock flags dict, got {type(flags).__name__}")
        for prop, val in flags.items():
            if type(val) is not bool:
                raise ShapeLockValueError(
                    f"lock property {prop!r} must be a bool, got {type(val).__name__}"
                )

    output_path = Path(output_path)

    if not edits_list:
        shutil.copy2(input_path, output_path)
        return

    slides = slide_payloads if slide_payloads is not None else _load_slide_payloads(input_path)

    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[ShapeEditRef, dict[str, bool]]]] = {}
    for (slide_index, shape_ref), flags in edits_list:
        edits_by_slide.setdefault(slide_index, []).append((shape_ref, flags))

    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            if slide_index < 0 or slide_index >= len(slides):
                raise IndexError(f"slide index {slide_index} out of range")
            slide_payload = slides[slide_index]
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_ref, flags in slide_edits:
                shape_payload_item = _shape_payload(slide_payload, shape_ref)
                shape_element = _shape_xml_element(root, shape_payload_item)
                _set_shape_locks(shape_element, shape_payload_item, flags)

            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    _copy_package_with_replacements(input_path, output_path, replacements)


__all__ = [
    "apply_shape_lock_edits",
]
