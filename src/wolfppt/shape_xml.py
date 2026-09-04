"""Shape and text XML mutation helpers for presentation saves."""

from __future__ import annotations

import posixpath
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    existing_pattern_fill_element as _existing_pattern_fill_element,
    no_fill_element as _no_fill_element,
    pattern_color_element as _pattern_color_element,
    pattern_fill_element as _pattern_fill_element,
    run_gradient_fill_element as _run_gradient_fill_element,
    run_no_fill_element as _run_no_fill_element,
    run_solid_fill_element as _run_solid_fill_element,
    set_run_gradient_fill as _set_run_gradient_fill,
    set_run_pattern_fill as _set_run_pattern_fill,
    set_run_pattern_fill_color as _set_run_pattern_fill_color,
    set_color_choice_rgb as _set_color_choice_rgb,
    set_solid_fill_color as _set_solid_fill_color,
    set_solid_fill_rgb as _set_solid_fill_rgb,
    solid_fill_element as _solid_fill_element,
)
from .facade_values import (
    emu_to_centipoints as _emu_to_centipoints,
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
    rotation_openxml_units as _rotation_openxml_units,
)
from .text_xml import (
    _clear_text_frame_auto_size_children,
    _end_paragraph_run_properties_element,
    _set_fit_font_properties,
    _set_font_bool_attribute,
    _set_font_name,
    _set_font_size,
    _set_font_underline,
    _text_character_properties_element,
    _text_frame_auto_size_insert_index,
)
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_HYPERLINK_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
)
_SLIDE_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
)
_NAMED_SLIDE_ACTION = "ppaction://hlinksldjump"
_PARAGRAPH_SPACING_TAGS = ("lnSpc", "spcBef", "spcAft")


def _shape_xml_element(root: ET.Element, shape_payload: dict[str, Any]) -> ET.Element:
    shape_id = shape_payload.get("id")
    shape_tree = root.find(f".//{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if shape_tree is None:
        raise AttributeError("shape XML element is unavailable")
    for element in _iter_shape_elements(shape_tree):
        nv = element.find(f".//{{{P_NS}}}cNvPr")
        if nv is not None and nv.attrib.get("id") == str(shape_id):
            return element
    raise AttributeError("shape XML element is unavailable")


def _iter_shape_elements(container: ET.Element):
    for element in list(container):
        tag = _xml_local_name(element.tag)
        if tag not in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}:
            continue
        yield element
        if tag == "grpSp":
            yield from _iter_shape_elements(element)


def _paragraph_xml_element(shape_element: ET.Element, paragraph_index: int) -> ET.Element:
    text_body = shape_element.find(f"{{{P_NS}}}txBody")
    if text_body is None:
        raise AttributeError("shape text body is unavailable")
    paragraphs = text_body.findall(f"{{{A_NS}}}p")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        raise IndexError("paragraph index out of range")
    return paragraphs[paragraph_index]


def _find_text_body_properties_element(shape_element: ET.Element) -> ET.Element | None:
    text_body = shape_element.find(f"{{{P_NS}}}txBody")
    if text_body is None:
        return None
    return text_body.find(f"{{{A_NS}}}bodyPr")


def _text_body_properties_element(shape_element: ET.Element) -> ET.Element:
    text_body = shape_element.find(f"{{{P_NS}}}txBody")
    if text_body is None:
        text_body = ET.Element(f"{{{P_NS}}}txBody")
        shape_element.append(text_body)
    body_properties = text_body.find(f"{{{A_NS}}}bodyPr")
    if body_properties is not None:
        return body_properties
    body_properties = ET.Element(f"{{{A_NS}}}bodyPr")
    text_body.insert(0, body_properties)
    return body_properties


def _text_paragraph_content(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for child in paragraph:
        local_name = _xml_local_name(child.tag)
        if local_name == "br":
            parts.append("\v")
        elif local_name in {"r", "fld"}:
            parts.append(
                "".join(
                    text_node.text or ""
                    for text_node in child.findall(f".//{{{A_NS}}}t")
                )
            )
    if parts:
        return "".join(parts)
    return "".join(
        text_node.text or "" for text_node in paragraph.findall(f".//{{{A_NS}}}t")
    )


def _set_text_frame_fit(shape_element: ET.Element, fit: dict[str, Any]) -> None:
    body_properties = _text_body_properties_element(shape_element)
    body_properties.set("wrap", "square")
    _clear_text_frame_auto_size_children(body_properties)
    body_properties.insert(
        _text_frame_auto_size_insert_index(body_properties),
        ET.Element(f"{{{A_NS}}}noAutofit"),
    )
    text_body = shape_element.find(f"{{{P_NS}}}txBody")
    if text_body is None:
        return
    for paragraph in text_body.findall(f"{{{A_NS}}}p"):
        for child in list(paragraph):
            if _xml_local_name(child.tag) not in {"r", "br", "fld"}:
                continue
            _set_fit_font_properties(_text_character_properties_element(child), fit)
        _set_fit_font_properties(_end_paragraph_run_properties_element(paragraph), fit)


def _clear_paragraph_content(paragraph: ET.Element) -> None:
    for child in list(paragraph):
        if _xml_local_name(child.tag) != "pPr":
            paragraph.remove(child)


def _insert_paragraph_line_break(paragraph: ET.Element, run_slot: int) -> None:
    if run_slot < 0:
        raise IndexError("run slot out of range")
    run_count = 0
    insert_index = len(paragraph)
    for index, child in enumerate(list(paragraph)):
        if _xml_local_name(child.tag) != "r":
            continue
        if run_count == run_slot:
            insert_index = index
            break
        run_count += 1
    else:
        if run_slot > run_count:
            raise IndexError("run slot out of range")
    paragraph.insert(insert_index, ET.Element(f"{{{A_NS}}}br"))


def _text_run_xml_element(
    shape_element: ET.Element,
    paragraph_index: int,
    run_index: int,
) -> ET.Element:
    runs = _paragraph_xml_element(shape_element, paragraph_index).findall(f"{{{A_NS}}}r")
    if run_index < 0 or run_index >= len(runs):
        raise IndexError("run index out of range")
    return runs[run_index]


def _shape_properties_element(shape_element: ET.Element) -> ET.Element:
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is not None:
        return shape_properties
    shape_properties = ET.Element(f"{{{P_NS}}}spPr")
    insert_at = 0
    if shape_element.find(f"{{{P_NS}}}nvSpPr") is not None:
        insert_at = 1
    elif shape_element.find(f"{{{P_NS}}}nvCxnSpPr") is not None:
        insert_at = 1
    elif shape_element.find(f"{{{P_NS}}}nvPicPr") is not None:
        insert_at = 1
        if shape_element.find(f"{{{P_NS}}}blipFill") is not None:
            insert_at = 2
    shape_element.insert(insert_at, shape_properties)
    return shape_properties


def _find_shape_transform_xml_element(shape_element: ET.Element) -> ET.Element | None:
    tag = _xml_local_name(shape_element.tag)
    if tag == "graphicFrame":
        return shape_element.find(f"{{{P_NS}}}xfrm")
    if tag == "grpSp":
        return shape_element.find(f"{{{P_NS}}}grpSpPr/{{{A_NS}}}xfrm")
    shape_properties = shape_element.find(f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    return shape_properties.find(f"{{{A_NS}}}xfrm")


def _shape_transform_xml_element(shape_element: ET.Element) -> ET.Element:
    existing = _find_shape_transform_xml_element(shape_element)
    if existing is not None:
        return existing
    tag = _xml_local_name(shape_element.tag)
    if tag == "graphicFrame":
        transform = ET.Element(f"{{{P_NS}}}xfrm")
        insert_at = (
            1
            if shape_element.find(f"{{{P_NS}}}nvGraphicFramePr") is not None
            else 0
        )
        shape_element.insert(insert_at, transform)
        return transform
    if tag == "grpSp":
        group_properties = shape_element.find(f"{{{P_NS}}}grpSpPr")
        if group_properties is None:
            group_properties = ET.Element(f"{{{P_NS}}}grpSpPr")
            insert_at = (
                1
                if shape_element.find(f"{{{P_NS}}}nvGrpSpPr") is not None
                else 0
            )
            shape_element.insert(insert_at, group_properties)
        transform = ET.Element(f"{{{A_NS}}}xfrm")
        group_properties.insert(0, transform)
        return transform
    shape_properties = _shape_properties_element(shape_element)
    transform = ET.Element(f"{{{A_NS}}}xfrm")
    shape_properties.insert(0, transform)
    return transform


def _set_connector_connection(
    connector_element: ET.Element,
    endpoint: str,
    target_shape_id: int | str,
    cxn_pt_idx: int,
) -> None:
    connection_properties = _connector_connection_properties_element(
        connector_element
    )
    tag = f"{{{A_NS}}}{'stCxn' if endpoint == 'begin' else 'endCxn'}"
    connection = connection_properties.find(tag)
    if connection is None:
        connection = ET.Element(tag)
        if endpoint == "begin":
            connection_properties.insert(0, connection)
        else:
            insert_at = len(connection_properties)
            ext_list = connection_properties.find(f"{{{A_NS}}}extLst")
            if ext_list is not None:
                insert_at = list(connection_properties).index(ext_list)
            connection_properties.insert(insert_at, connection)
    connection.set("id", str(target_shape_id))
    connection.set("idx", str(cxn_pt_idx))


def _connector_connection_properties_element(
    connector_element: ET.Element,
) -> ET.Element:
    non_visual = connector_element.find(f"{{{P_NS}}}nvCxnSpPr")
    if non_visual is None:
        non_visual = ET.Element(f"{{{P_NS}}}nvCxnSpPr")
        connector_element.insert(0, non_visual)
    properties = non_visual.find(f"{{{P_NS}}}cNvCxnSpPr")
    if properties is not None:
        return properties
    properties = ET.Element(f"{{{P_NS}}}cNvCxnSpPr")
    insert_at = len(non_visual)
    non_visual_properties = non_visual.find(f"{{{P_NS}}}cNvPr")
    if non_visual_properties is not None:
        insert_at = list(non_visual).index(non_visual_properties) + 1
    non_visual.insert(insert_at, properties)
    return properties


def _set_connector_transform(
    connector_element: ET.Element,
    transform: dict[str, int],
    flip_h: bool,
    flip_v: bool,
) -> None:
    xfrm = _shape_transform_xml_element(connector_element)
    if flip_h:
        xfrm.set("flipH", "1")
    else:
        xfrm.attrib.pop("flipH", None)
    if flip_v:
        xfrm.set("flipV", "1")
    else:
        xfrm.attrib.pop("flipV", None)
    offset = xfrm.find(f"{{{A_NS}}}off")
    if offset is None:
        offset = ET.Element(f"{{{A_NS}}}off")
        xfrm.insert(0, offset)
    extent = xfrm.find(f"{{{A_NS}}}ext")
    if extent is None:
        extent = ET.Element(f"{{{A_NS}}}ext")
        insert_at = list(xfrm).index(offset) + 1
        xfrm.insert(insert_at, extent)
    offset.set("x", str(transform["x"]))
    offset.set("y", str(transform["y"]))
    extent.set("cx", str(transform["cx"]))
    extent.set("cy", str(transform["cy"]))


def _picture_blip_fill_element(picture_element: ET.Element) -> ET.Element:
    blip_fill = picture_element.find(f"{{{P_NS}}}blipFill")
    if blip_fill is None:
        raise AttributeError("picture blip fill is unavailable")
    return blip_fill


def _paragraph_properties_element(paragraph: ET.Element) -> ET.Element:
    paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
    if paragraph_properties is not None:
        return paragraph_properties
    paragraph_properties = ET.Element(f"{{{A_NS}}}pPr")
    paragraph.insert(0, paragraph_properties)
    return paragraph_properties


def _paragraph_default_run_properties_element(paragraph: ET.Element) -> ET.Element:
    paragraph_properties = _paragraph_properties_element(paragraph)
    default_run_properties = paragraph_properties.find(f"{{{A_NS}}}defRPr")
    if default_run_properties is not None:
        return default_run_properties
    default_run_properties = ET.Element(f"{{{A_NS}}}defRPr")
    insert_at = len(paragraph_properties)
    for index, child in enumerate(list(paragraph_properties)):
        if _xml_local_name(child.tag) == "extLst":
            insert_at = index
            break
    paragraph_properties.insert(insert_at, default_run_properties)
    return default_run_properties


def _run_properties_element(run_element: ET.Element) -> ET.Element:
    run_properties = run_element.find(f"{{{A_NS}}}rPr")
    if run_properties is not None:
        return run_properties
    run_properties = ET.Element(f"{{{A_NS}}}rPr")
    run_element.insert(0, run_properties)
    return run_properties


def _get_or_add_shape_line_element(shape_properties: ET.Element) -> ET.Element:
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is not None:
        return line
    line = ET.Element(f"{{{A_NS}}}ln")
    insert_at = len(shape_properties)
    for index, child in enumerate(list(shape_properties)):
        if _xml_local_name(child.tag) in {
            "effectLst",
            "effectDag",
            "scene3d",
            "sp3d",
            "extLst",
        }:
            insert_at = index
            break
    shape_properties.insert(insert_at, line)
    return line


def _set_shape_line_color(
    shape_properties: ET.Element,
    color: str | dict[str, Any],
) -> None:
    line = _get_or_add_shape_line_element(shape_properties)
    fill = _solid_fill_element(line)
    _set_solid_fill_color(fill, color)


def _set_shape_line_solid_fill(shape_properties: ET.Element) -> None:
    line = _get_or_add_shape_line_element(shape_properties)
    _solid_fill_element(line)


def _set_shape_line_no_fill(shape_properties: ET.Element) -> None:
    line = _get_or_add_shape_line_element(shape_properties)
    fill = _no_fill_element(line)
    fill.clear()


def _set_shape_line_pattern_fill(
    shape_properties: ET.Element,
    pattern: str | None,
) -> None:
    line = _get_or_add_shape_line_element(shape_properties)
    fill = _pattern_fill_element(line)
    if pattern is None:
        fill.attrib.pop("prst", None)
        return
    fill.set("prst", pattern)


def _set_shape_line_pattern_fill_color(
    shape_properties: ET.Element,
    color_tag: str,
    rgb: str,
) -> None:
    line = _get_or_add_shape_line_element(shape_properties)
    fill = _existing_pattern_fill_element(line)
    color = _pattern_color_element(fill, color_tag)
    _set_color_choice_rgb(color, rgb)


def _set_shape_line_width(shape_properties: ET.Element, width: int) -> None:
    line = _get_or_add_shape_line_element(shape_properties)
    line.set("w", str(width))


def _set_shape_line_dash_style(
    shape_properties: ET.Element,
    dash_style: str | None,
) -> None:
    line = _get_or_add_shape_line_element(shape_properties)
    for child in list(line):
        if child.tag == f"{{{A_NS}}}prstDash":
            line.remove(child)
    if dash_style is None:
        return
    preset_dash = ET.Element(f"{{{A_NS}}}prstDash")
    preset_dash.set("val", dash_style)
    insert_at = len(line)
    for index, child in enumerate(list(line)):
        if child.tag in {
            f"{{{A_NS}}}round",
            f"{{{A_NS}}}bevel",
            f"{{{A_NS}}}miter",
            f"{{{A_NS}}}headEnd",
            f"{{{A_NS}}}tailEnd",
            f"{{{A_NS}}}extLst",
        }:
            insert_at = index
            break
    line.insert(insert_at, preset_dash)


def _set_shape_shadow_inherit(shape_properties: ET.Element, inherit: bool) -> None:
    for child in list(shape_properties):
        if _xml_local_name(child.tag) in {"effectLst", "effectDag"}:
            shape_properties.remove(child)
    if inherit:
        return
    effect_list = ET.Element(f"{{{A_NS}}}effectLst")
    insert_at = len(shape_properties)
    for index, child in enumerate(list(shape_properties)):
        if _xml_local_name(child.tag) in {"scene3d", "sp3d", "extLst"}:
            insert_at = index
            break
    shape_properties.insert(insert_at, effect_list)


def _set_shape_hyperlink_address(
    non_visual_properties: ET.Element,
    rels_root: ET.Element,
    address: str | None,
) -> None:
    _set_hyperlink_address(non_visual_properties, rels_root, address)


def _set_shape_target_slide(
    non_visual_properties: ET.Element,
    rels_root: ET.Element,
    source_slide_part: str,
    target_slide_part: str | None,
) -> None:
    if target_slide_part is None:
        _set_hyperlink_address(non_visual_properties, rels_root, None)
        return
    target = posixpath.relpath(
        target_slide_part,
        posixpath.dirname(source_slide_part),
    )
    _set_hyperlink_address(
        non_visual_properties,
        rels_root,
        target,
        relationship_type=_SLIDE_REL_TYPE,
        action=_NAMED_SLIDE_ACTION,
        target_mode=None,
    )


def _set_hyperlink_address(
    owner: ET.Element,
    rels_root: ET.Element,
    address: str | None,
    relationship_type: str = _HYPERLINK_REL_TYPE,
    action: str | None = None,
    target_mode: str | None = "External",
) -> None:
    existing = owner.find(f"{{{A_NS}}}hlinkClick")
    if existing is not None:
        relationship_id = existing.attrib.get(f"{{{R_NS}}}id")
        if relationship_id:
            _remove_relationship(rels_root, relationship_id)
        owner.remove(existing)
    if not address:
        return
    relationship_id = _next_relationship_id(rels_root)
    relationship_attrs = {
        "Id": relationship_id,
        "Type": relationship_type,
        "Target": address,
    }
    if target_mode is not None:
        relationship_attrs["TargetMode"] = target_mode
    relationship = ET.Element(f"{{{PKG_REL_NS}}}Relationship", relationship_attrs)
    rels_root.append(relationship)
    hyperlink = ET.Element(f"{{{A_NS}}}hlinkClick")
    hyperlink.set(f"{{{R_NS}}}id", relationship_id)
    if action is not None:
        hyperlink.set("action", action)
    insert_at = len(owner)
    for index, child in enumerate(list(owner)):
        if _xml_local_name(child.tag) == "extLst":
            insert_at = index
            break
    owner.insert(insert_at, hyperlink)


def _remove_relationship(rels_root: ET.Element, relationship_id: str) -> None:
    for relationship in list(rels_root):
        if (
            _xml_local_name(relationship.tag) == "Relationship"
            and relationship.attrib.get("Id") == relationship_id
        ):
            rels_root.remove(relationship)


def _next_relationship_id(rels_root: ET.Element) -> str:
    max_id = 0
    for relationship in rels_root:
        if _xml_local_name(relationship.tag) != "Relationship":
            continue
        raw = relationship.attrib.get("Id", "")
        if not raw.startswith("rId"):
            continue
        try:
            max_id = max(max_id, int(raw.removeprefix("rId")))
        except ValueError:
            continue
    return f"rId{max_id + 1}"


def _set_shape_rotation(transform: ET.Element, rotation: float) -> None:
    transform.set("rot", str(_rotation_openxml_units(rotation)))


def _set_shape_adjustment_guides(
    shape_properties: ET.Element,
    guides: list[tuple[str, int]],
) -> None:
    preset_geometry = shape_properties.find(f"{{{A_NS}}}prstGeom")
    if preset_geometry is None:
        raise AttributeError("shape preset geometry is unavailable")
    adjust_value_list = preset_geometry.find(f"{{{A_NS}}}avLst")
    if adjust_value_list is None:
        adjust_value_list = ET.Element(f"{{{A_NS}}}avLst")
        preset_geometry.insert(0, adjust_value_list)
    for child in list(adjust_value_list):
        adjust_value_list.remove(child)
    for name, value in guides:
        guide = ET.Element(f"{{{A_NS}}}gd")
        guide.set("name", name)
        guide.set("fmla", f"val {value}")
        adjust_value_list.append(guide)


def _set_picture_crop(blip_fill: ET.Element, crop: dict[str, float]) -> None:
    src_rect = blip_fill.find(f"{{{A_NS}}}srcRect")
    if src_rect is None:
        src_rect = ET.Element(f"{{{A_NS}}}srcRect")
        insert_at = 0
        for index, child in enumerate(list(blip_fill)):
            if child.tag == f"{{{A_NS}}}blip":
                insert_at = index + 1
        blip_fill.insert(insert_at, src_rect)
    for key in ("l", "r", "t", "b"):
        units = int(round(float(crop.get(key, 0.0)) * 100000))
        if units:
            src_rect.set(key, str(units))
        else:
            src_rect.attrib.pop(key, None)


def _set_run_font_color(run_properties: ET.Element, color: str | dict[str, Any]) -> None:
    fill = _run_solid_fill_element(run_properties)
    _set_solid_fill_color(fill, color)


def _set_run_font_fill_type(run_properties: ET.Element, fill_type: Any) -> None:
    payload = fill_type if isinstance(fill_type, dict) else {"type": fill_type}
    fill_type = payload.get("type")
    if fill_type == "solid":
        _run_solid_fill_element(run_properties)
        return
    if fill_type == "background":
        _run_no_fill_element(run_properties)
        return
    if fill_type == "patterned":
        _set_run_pattern_fill(run_properties, payload.get("pattern"))
        fore_rgb = payload.get("pattern_fore_rgb")
        if fore_rgb is not None:
            _set_run_pattern_fill_color(run_properties, "fgClr", str(fore_rgb))
        back_rgb = payload.get("pattern_back_rgb")
        if back_rgb is not None:
            _set_run_pattern_fill_color(run_properties, "bgClr", str(back_rgb))
        return
    if fill_type == "gradient":
        gradient = payload.get("gradient")
        if isinstance(gradient, dict):
            _set_run_gradient_fill(run_properties, gradient)
        else:
            _run_gradient_fill_element(run_properties)
        return
    raise ValueError(f"unsupported run font fill type: {fill_type!r}")


def _set_run_font_language(run_properties: ET.Element, value: str | None) -> None:
    if value is None:
        run_properties.attrib.pop("lang", None)
        return
    run_properties.set("lang", value)


def _set_paragraph_font_properties(
    default_run_properties: ET.Element,
    edits: dict[str, Any],
) -> None:
    if "bold" in edits:
        _set_font_bool_attribute(default_run_properties, "b", edits["bold"])
    if "italic" in edits:
        _set_font_bool_attribute(default_run_properties, "i", edits["italic"])
    if "underline" in edits:
        _set_font_underline(default_run_properties, edits["underline"])
    if "size" in edits:
        _set_font_size(default_run_properties, edits["size"])
    if "name" in edits:
        _set_font_name(default_run_properties, edits["name"])
    if "fill_type" in edits:
        _set_run_font_fill_type(default_run_properties, edits["fill_type"])
    if "color" in edits:
        _set_run_font_color(default_run_properties, edits["color"])
    if "language_id" in edits:
        _set_run_font_language(default_run_properties, edits["language_id"])


def _set_paragraph_alignment(
    paragraph_properties: ET.Element,
    alignment: str | None,
) -> None:
    if alignment is None:
        paragraph_properties.attrib.pop("algn", None)
        return
    paragraph_properties.set("algn", alignment)


def _set_paragraph_level(paragraph_properties: ET.Element, level: int) -> None:
    if level == 0:
        paragraph_properties.attrib.pop("lvl", None)
        return
    paragraph_properties.set("lvl", str(level))


def _set_paragraph_spacing(
    paragraph_properties: ET.Element,
    spacing: dict[str, int | float | None],
) -> None:
    for attr in ("line_spacing", "space_before", "space_after"):
        if attr not in spacing:
            continue
        _set_paragraph_spacing_value(
            paragraph_properties,
            _paragraph_spacing_xml_tag(attr),
            spacing[attr],
        )


def _set_paragraph_spacing_value(
    paragraph_properties: ET.Element,
    tag: str,
    value: int | float | None,
) -> None:
    _remove_paragraph_spacing_child(paragraph_properties, tag)
    if value is None:
        return
    spacing = ET.Element(f"{{{A_NS}}}{tag}")
    if tag == "lnSpc" and isinstance(value, float):
        ET.SubElement(spacing, f"{{{A_NS}}}spcPct").set(
            "val",
            str(int(round(value * 100000))),
        )
    else:
        ET.SubElement(spacing, f"{{{A_NS}}}spcPts").set(
            "val",
            str(_emu_to_centipoints(int(value))),
        )
    paragraph_properties.insert(
        _paragraph_spacing_insert_index(paragraph_properties, tag),
        spacing,
    )


def _remove_paragraph_spacing_child(paragraph_properties: ET.Element, tag: str) -> None:
    for child in list(paragraph_properties):
        if _xml_local_name(child.tag) == tag:
            paragraph_properties.remove(child)


def _paragraph_spacing_insert_index(paragraph_properties: ET.Element, tag: str) -> int:
    target_index = _PARAGRAPH_SPACING_TAGS.index(tag)
    insert_index = 0
    for index, child in enumerate(list(paragraph_properties)):
        local_name = _xml_local_name(child.tag)
        if local_name not in _PARAGRAPH_SPACING_TAGS:
            continue
        if _PARAGRAPH_SPACING_TAGS.index(local_name) > target_index:
            return index
        insert_index = index + 1
    return insert_index
