"""Click-action and hyperlink inspection helpers for shape facades."""

from __future__ import annotations

import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import resolve_package_target as _resolve_package_target
from .shape_xml import _shape_xml_element
from .slide_relationships import slide_relationship_info as _slide_relationship_info

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_NAMED_SLIDE_ACTION = "ppaction://hlinksldjump"


def _shape_click_action_value(shape: Any) -> Any:
    action = _shape_click_action_name(shape)
    try:
        from pptx.enum.action import PP_ACTION
    except ImportError:  # pragma: no cover - lean runtime fallback
        return action
    if action == "NAMED_SLIDE":
        return PP_ACTION.NAMED_SLIDE
    return PP_ACTION.HYPERLINK if action == "HYPERLINK" else PP_ACTION.NONE


def _shape_click_action_name(shape: Any) -> str:
    if "target_slide_index" in shape._payload and shape._payload.get(
        "target_slide_index"
    ) is not None:
        return "NAMED_SLIDE"
    if "hyperlink_address" in shape._payload:
        return "HYPERLINK" if shape._payload.get("hyperlink_address") else "NONE"
    hyperlink = _shape_hyperlink_click(shape)
    if hyperlink is None:
        return "NONE"
    action = hyperlink.attrib.get("action")
    if action == _NAMED_SLIDE_ACTION:
        return "NAMED_SLIDE"
    if action in (None, "") and hyperlink.attrib.get(f"{{{R_NS}}}id"):
        return "HYPERLINK"
    return "NONE"


def _shape_hyperlink_address(shape: Any) -> str | None:
    if "hyperlink_address" in shape._payload:
        address = shape._payload.get("hyperlink_address")
        return str(address) if address else None
    hyperlink = _shape_hyperlink_click(shape)
    if hyperlink is None:
        shape._payload["hyperlink_address"] = None
        return None
    relationship_id = hyperlink.attrib.get(f"{{{R_NS}}}id")
    if not relationship_id:
        shape._payload["hyperlink_address"] = None
        return None
    relationship = _slide_relationship_info(
        shape._slide._presentation.path,
        shape._slide.partname,
        relationship_id,
    )
    if relationship is None:
        address = None
    else:
        relationship_type, address = relationship
        if not relationship_type.endswith(("/hyperlink", "/slide")):
            address = None
    shape._payload["hyperlink_address"] = address
    return address


def _shape_target_slide(shape: Any) -> "Slide | None":
    if "target_slide_index" in shape._payload:
        target_index = shape._payload.get("target_slide_index")
        if target_index is None:
            return None
        return shape._slide._presentation.slides[int(target_index)]
    hyperlink = _shape_hyperlink_click(shape)
    if hyperlink is None or hyperlink.attrib.get("action") != _NAMED_SLIDE_ACTION:
        shape._payload["target_slide_index"] = None
        return None
    relationship_id = hyperlink.attrib.get(f"{{{R_NS}}}id")
    if not relationship_id:
        shape._payload["target_slide_index"] = None
        return None
    relationship = _slide_relationship_info(
        shape._slide._presentation.path,
        shape._slide.partname,
        relationship_id,
    )
    if relationship is None:
        shape._payload["target_slide_index"] = None
        return None
    relationship_type, target = relationship
    if not relationship_type.endswith("/slide"):
        shape._payload["target_slide_index"] = None
        return None
    target_part = _resolve_package_target(shape._slide.partname, target)
    for slide in shape._slide._presentation.slides:
        if slide.partname == target_part:
            shape._payload["target_slide_index"] = slide._index
            shape._payload["hyperlink_address"] = target
            return slide
    shape._payload["target_slide_index"] = None
    return None


def _shape_hyperlink_click(shape: Any) -> ET.Element | None:
    if shape._payload.get("kind") not in {"shape", "connector", "picture"}:
        return None
    try:
        with zipfile.ZipFile(shape._slide._presentation.path) as package:
            root = ET.fromstring(package.read(shape._slide.partname))
        shape_element = _shape_xml_element(root, shape._payload)
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return None
    non_visual_properties = shape_element.find(f".//{{{P_NS}}}cNvPr")
    if non_visual_properties is None:
        return None
    return non_visual_properties.find(f"{{{A_NS}}}hlinkClick")
