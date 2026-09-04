"""XML inspection helpers for shape formatting facades."""

from __future__ import annotations

import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    fill_type_from_xml_children as _fill_type_from_xml_children,
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)
from .shape_xml import _shape_xml_element
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _is_pending_shape(shape: Shape) -> bool:
    payload = getattr(shape, "_payload", {})
    return bool(payload.get("_pending_shape") or payload.get("_pending_group_child"))


def _shape_style_rgb(shape: Shape, target: str) -> str | None:
    payload = _shape_style_color_payload(shape, target)
    if payload is None or payload.get("type") != "rgb":
        return None
    value = payload.get("value")
    return value if isinstance(value, str) else None


def _shape_style_color_payload(shape: Shape, target: str) -> dict[str, Any] | None:
    fill_parent = _detached_fill_parent(shape)
    if fill_parent is not None:
        if target != "fill":
            return None
        return _color_payload_from_fill_parent(fill_parent)
    if _is_pending_shape(shape):
        return None
    if target == "fill" and shape._payload.get("kind") != "shape":
        return None
    if target == "line" and not _supports_shape_line_style(shape):
        return None
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    fill_parent = (
        shape_properties
        if target == "fill"
        else shape_properties.find(f"{{{A_NS}}}ln")
    )
    if fill_parent is None:
        return None
    return _color_payload_from_fill_parent(fill_parent)


def _color_payload_from_fill_parent(parent: ET.Element) -> dict[str, Any] | None:
    color = parent.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    if color is not None:
        value = color.attrib.get("val")
        return (
            {
                "type": "rgb",
                "value": value.upper(),
                "brightness": _brightness_from_color_element(color),
            }
            if value
            else None
        )
    color = parent.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}schemeClr")
    if color is None:
        return None
    value = color.attrib.get("val")
    return (
        {
            "type": "scheme",
            "value": value,
            "brightness": _brightness_from_color_element(color),
        }
        if value
        else None
    )


def _brightness_from_color_element(color: ET.Element) -> float:
    lum_off = color.find(f"{{{A_NS}}}lumOff")
    if lum_off is not None:
        value = lum_off.attrib.get("val")
        return 0.0 if value is None else int(value) / 100000
    lum_mod = color.find(f"{{{A_NS}}}lumMod")
    if lum_mod is not None:
        value = lum_mod.attrib.get("val")
        return 0.0 if value is None else (int(value) / 100000) - 1.0
    return 0.0


def _shape_pattern_rgb(shape: Shape, target: str, role: str) -> str | None:
    fill_parent = _detached_fill_parent(shape)
    if fill_parent is not None:
        if target != "fill":
            return None
        color_tag = "fgClr" if role == "fore" else "bgClr"
        color = fill_parent.find(
            f"{{{A_NS}}}pattFill/{{{A_NS}}}{color_tag}/{{{A_NS}}}srgbClr"
        )
        if color is None:
            return None
        value = color.attrib.get("val")
        return value.upper() if value else None
    if _is_pending_shape(shape):
        return None
    if target == "fill" and shape._payload.get("kind") != "shape":
        return None
    if target == "line" and not _supports_shape_line_style(shape):
        return None
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    if target == "fill":
        pattern_fill = shape_properties.find(f"{{{A_NS}}}pattFill")
    else:
        pattern_fill = shape_properties.find(f"{{{A_NS}}}ln/{{{A_NS}}}pattFill")
    if pattern_fill is None:
        return None
    color_tag = "fgClr" if role == "fore" else "bgClr"
    color = pattern_fill.find(f"{{{A_NS}}}{color_tag}/{{{A_NS}}}srgbClr")
    if color is None:
        return None
    value = color.attrib.get("val")
    return value.upper() if value else None


def _shape_fill_type(shape: Shape) -> str | None:
    fill_parent = _detached_fill_parent(shape)
    if fill_parent is not None:
        return _fill_type_from_xml_children(fill_parent)
    if _is_pending_shape(shape):
        return None
    if shape._payload.get("kind") != "shape":
        return None
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    for child in shape_properties:
        if child.tag == f"{{{A_NS}}}solidFill":
            return "solid"
        if child.tag == f"{{{A_NS}}}noFill":
            return "background"
        if child.tag == f"{{{A_NS}}}pattFill":
            return "patterned"
        if child.tag == f"{{{A_NS}}}gradFill":
            return "gradient"
        if child.tag == f"{{{A_NS}}}blipFill":
            return "picture"
        if child.tag == f"{{{A_NS}}}grpFill":
            return "group"
    return None


def _shape_fill_pattern(shape: Shape) -> str | None:
    fill_parent = _detached_fill_parent(shape)
    if fill_parent is not None:
        pattern_fill = fill_parent.find(f"{{{A_NS}}}pattFill")
        if pattern_fill is None:
            return None
        value = pattern_fill.attrib.get("prst")
        return value if value else None
    if _is_pending_shape(shape):
        return None
    if shape._payload.get("kind") != "shape":
        return None
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    pattern_fill = shape_element.find(f"{{{P_NS}}}spPr/{{{A_NS}}}pattFill")
    if pattern_fill is None:
        return None
    value = pattern_fill.attrib.get("prst")
    return value if value else None


def _shape_gradient_fill_payload(shape: Shape) -> dict[str, Any] | None:
    fill_parent = _detached_fill_parent(shape)
    if fill_parent is not None:
        return _gradient_payload_from_fill_parent(fill_parent)
    if _is_pending_shape(shape):
        return None
    if shape._payload.get("kind") != "shape":
        return None
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    return _gradient_payload_from_fill_parent(shape_properties)


def _shape_line_fill_type(shape: Shape) -> str | None:
    if not _supports_shape_line_style(shape):
        return None
    if _is_pending_shape(shape):
        return None
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        return None
    for child in line:
        if child.tag == f"{{{A_NS}}}solidFill":
            return "solid"
        if child.tag == f"{{{A_NS}}}noFill":
            return "background"
        if child.tag == f"{{{A_NS}}}pattFill":
            return "patterned"
        if child.tag == f"{{{A_NS}}}gradFill":
            return "gradient"
    return None


def _shape_line_fill_pattern(shape: Shape) -> str | None:
    if not _supports_shape_line_style(shape):
        return None
    if _is_pending_shape(shape):
        return None
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    pattern_fill = shape_element.find(
        f"{{{P_NS}}}spPr/{{{A_NS}}}ln/{{{A_NS}}}pattFill"
    )
    if pattern_fill is None:
        return None
    value = pattern_fill.attrib.get("prst")
    return value if value else None


def _shape_line_width(shape: Shape) -> int:
    if not _supports_shape_line_style(shape):
        return 0
    if _is_pending_shape(shape):
        return 0
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return 0
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        return 0
    return int(line.attrib.get("w", "0"))


def _shape_line_dash_style(shape: Shape) -> str | None:
    if not _supports_shape_line_style(shape):
        return None
    if _is_pending_shape(shape):
        return None
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(shape._slide.partname))
    shape_element = _shape_xml_element(root, shape._payload)
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    preset_dash = shape_properties.find(f"{{{A_NS}}}ln/{{{A_NS}}}prstDash")
    if preset_dash is None:
        return None
    value = preset_dash.attrib.get("val")
    return value if value else None


def _supports_shape_line_style(shape: Shape) -> bool:
    return shape._payload.get("kind") in {"shape", "connector"}


def _shape_shadow_inherit(shape: Shape) -> bool:
    if shape._payload.get("kind") not in {"shape", "connector", "picture"}:
        return True
    if _is_pending_shape(shape):
        return True
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
        return True
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return True
    has_effect_override = any(
        _xml_local_name(child.tag) in {"effectLst", "effectDag"}
        for child in shape_properties
    )
    return not has_effect_override


def _detached_fill_parent(shape: Any) -> ET.Element | None:
    fill_parent = getattr(shape, "_payload", {}).get("fill_parent")
    return fill_parent if fill_parent is not None else None
