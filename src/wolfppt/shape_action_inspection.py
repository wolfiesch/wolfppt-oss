"""Click-action and hyperlink inspection helpers for shape facades."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .enum.action import PP_ACTION
from .package_parts import resolve_package_target as _resolve_package_target
from .shape_xml import _shape_xml_element, saved_hyperlink_color_source
from .slide_relationships import slide_relationship_info as _slide_relationship_info
from .xml_helpers import find_ooxml, ooxml_namespace

if TYPE_CHECKING:
    from .presentation import Slide

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

_NAMED_SLIDE_ACTION = "ppaction://hlinksldjump"
_SHOW_JUMP_ACTION = "ppaction://hlinkshowjump"
# ``jump`` values of ``ppaction://hlinkshowjump`` keyed to ``PP_ACTION`` names.
SHOW_JUMP_ACTIONS = {
    "firstslide": "FIRST_SLIDE",
    "lastslide": "LAST_SLIDE",
    "lastslideviewed": "LAST_SLIDE_VIEWED",
    "nextslide": "NEXT_SLIDE",
    "previousslide": "PREVIOUS_SLIDE",
    "endshow": "END_SHOW",
}


def _shape_click_action_value(shape: Any) -> Any:
    action = _shape_click_action_name(shape)
    return PP_ACTION[action]


def _shape_click_action_name(shape: Any) -> str:
    if (
        "target_slide_index" in shape._payload
        and shape._payload.get("target_slide_index") is not None
    ):
        return "NAMED_SLIDE"
    show_jump = _shape_show_jump_name(shape)
    if show_jump is not None:
        return show_jump
    if "hyperlink_address" in shape._payload:
        return "HYPERLINK" if shape._payload.get("hyperlink_address") else "NONE"
    hyperlink = _shape_hyperlink_click(shape)
    if hyperlink is None:
        return "NONE"
    action = hyperlink.attrib.get("action")
    if action == _NAMED_SLIDE_ACTION:
        return "NAMED_SLIDE"
    if action in (None, "") and hyperlink.attrib.get(f"{{{ooxml_namespace(hyperlink, R_NS)}}}id"):
        return "HYPERLINK"
    return "NONE"


def _shape_show_jump_name(shape: Any) -> str | None:
    """``PP_ACTION`` name of the shape's slide-show jump, such as ``NEXT_SLIDE``.

    Pending edits record the jump in the payload (``None`` once another click
    action replaces it); otherwise the saved ``a:hlinkClick`` is parsed.
    """
    if "show_jump_action" in shape._payload:
        return shape._payload.get("show_jump_action")
    hyperlink = _shape_hyperlink_click(shape)
    name = None if hyperlink is None else _show_jump_name(hyperlink.get("action"))
    shape._payload["show_jump_action"] = name
    return name


def _show_jump_name(action: str | None) -> str | None:
    verb, _, query = (action or "").partition("?")
    if verb != _SHOW_JUMP_ACTION:
        return None
    fields = dict(field.partition("=")[::2] for field in query.split("&"))
    return SHOW_JUMP_ACTIONS.get(fields.get("jump", ""))


def _shape_has_click_action(shape: Any) -> bool:
    """Whether the shape carries a click action that clearing must remove.

    Pending edits live in the payload; otherwise any saved ``a:hlinkClick``
    counts, including actions that the read side reports as ``NONE``. A clear
    that is already queued still counts because the saved element remains
    until save; re-queueing that clear is idempotent.
    """
    payload = shape._payload
    if (
        payload.get("target_slide_index") is not None
        or payload.get("hyperlink_address")
        or payload.get("show_jump_action")
    ):
        return True
    return _shape_hyperlink_click(shape) is not None


def _shape_hyperlink_address(shape: Any) -> str | None:
    if "hyperlink_address" in shape._payload:
        address = shape._payload.get("hyperlink_address")
        return str(address) if address else None
    hyperlink = _shape_hyperlink_click(shape)
    if hyperlink is None:
        shape._payload["hyperlink_address"] = None
        return None
    relationship_id = hyperlink.attrib.get(f"{{{ooxml_namespace(hyperlink, R_NS)}}}id")
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


def _shape_hyperlink_screentip(shape: Any) -> str | None:
    """Tooltip text of the shape's click hyperlink (``a:hlinkClick/@tooltip``)."""
    if "hyperlink_screentip" in shape._payload:
        return shape._payload.get("hyperlink_screentip")
    hyperlink = _shape_hyperlink_click(shape)
    screentip = None if hyperlink is None else hyperlink.get("tooltip")
    shape._payload["hyperlink_screentip"] = screentip
    return screentip


def _shape_hyperlink_color_source(shape: Any) -> str | None:
    """Pending or saved ``hlinkClr/@val`` of the shape's click hyperlink.

    A pending color edit (``None`` once the link is removed) wins; otherwise
    the saved extension is read, refusing malformed values.
    """
    if "hyperlink_color_source_edit" in shape._payload:
        return shape._payload["hyperlink_color_source_edit"]
    return saved_hyperlink_color_source(_shape_hyperlink_click(shape))


def _shape_hyperlink_sub_address(shape: Any) -> str | None:
    """Location inside the click target.

    For a jump to a slide in this presentation it is the slide target relative
    to the source slide (``slide2.xml``); for an external address it is the
    ``#`` fragment of the relationship target.
    """
    address = _shape_hyperlink_address(shape)
    if address is None:
        return None
    if _shape_target_slide(shape) is not None:
        return address
    _, separator, fragment = address.partition("#")
    return fragment if separator and fragment else None


def _shape_target_slide(shape: Any) -> Slide | None:
    if "target_slide_index" in shape._payload:
        target_index = shape._payload.get("target_slide_index")
        if target_index is None:
            return None
        return shape._slide._presentation.slides[int(target_index)]
    hyperlink = _shape_hyperlink_click(shape)
    if hyperlink is None or hyperlink.attrib.get("action") != _NAMED_SLIDE_ACTION:
        shape._payload["target_slide_index"] = None
        return None
    relationship_id = hyperlink.attrib.get(f"{{{ooxml_namespace(hyperlink, R_NS)}}}id")
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
    non_visual_properties = find_ooxml(shape_element, f".//{{{P_NS}}}cNvPr")
    if non_visual_properties is None:
        return None
    return find_ooxml(non_visual_properties, f"{{{A_NS}}}hlinkClick")
