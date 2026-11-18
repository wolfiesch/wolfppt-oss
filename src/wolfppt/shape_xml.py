"""Shape and text XML mutation helpers for presentation saves."""

from __future__ import annotations

import posixpath
from typing import Any, Self
from xml.etree import ElementTree as ET

from .dml_fill import (
    existing_pattern_fill_element as _existing_pattern_fill_element,
)
from .dml_fill import (
    no_fill_element as _no_fill_element,
)
from .dml_fill import (
    pattern_color_element as _pattern_color_element,
)
from .dml_fill import (
    pattern_fill_element as _pattern_fill_element,
)
from .dml_fill import (
    run_gradient_fill_element as _run_gradient_fill_element,
)
from .dml_fill import (
    run_no_fill_element as _run_no_fill_element,
)
from .dml_fill import (
    run_solid_fill_element as _run_solid_fill_element,
)
from .dml_fill import (
    set_color_choice_rgb as _set_color_choice_rgb,
)
from .dml_fill import (
    set_run_gradient_fill as _set_run_gradient_fill,
)
from .dml_fill import (
    set_run_pattern_fill as _set_run_pattern_fill,
)
from .dml_fill import (
    set_run_pattern_fill_color as _set_run_pattern_fill_color,
)
from .dml_fill import (
    set_solid_fill_color as _set_solid_fill_color,
)
from .dml_fill import (
    solid_fill_element as _solid_fill_element,
)
from .dml_fill import validate_text_color_element as _validate_text_color_element
from .enum.action import PP_HYPERLINK_COLOR_SOURCE
from .facade_values import (
    emu_to_centipoints as _emu_to_centipoints,
)
from .facade_values import (
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
)
from .facade_values import (
    rotation_openxml_units as _rotation_openxml_units,
)
from .shape_preset_guides import PRESET_ADJUST_GUIDE_NAMES
from .text_xml import (
    _clear_text_frame_auto_size_children,
    _end_paragraph_run_properties_element,
    _set_fit_font_properties,
    _set_font_bool_attribute,
    _set_font_name,
    _set_font_size,
    _set_font_strike,
    _set_font_underline,
    _text_character_properties_element,
    _text_frame_auto_size_insert_index,
)
from .xml_helpers import find_ooxml, findall_ooxml, ooxml_namespace
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_HYPERLINK_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
)
_SLIDE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
_NAMED_SLIDE_ACTION = "ppaction://hlinksldjump"
_PARAGRAPH_SPACING_TAGS = ("lnSpc", "spcBef", "spcAft")
#: ``a:hlinkClick`` extension that chooses where hyperlink text takes its color.
HYPERLINK_COLOR_EXT_URI = "{A12FA001-AC4F-418D-AE19-62706E023703}"
HYPERLINK_COLOR_NS = "http://schemas.microsoft.com/office/drawing/2018/hyperlinkcolor"
ET.register_namespace("ahyp", HYPERLINK_COLOR_NS)


class HyperlinkColorSourceRefusal(ValueError):
    """A hyperlink color source request or saved value WolfPPT will not model."""


class RunHyperlinkAddress(str):
    """Queued hyperlink address that also carries ``a:hlinkClick`` metadata.

    ``screen_tip`` is the full tooltip state (``None``: no tooltip).
    ``color_source_edit`` is ``None`` when the color source is untouched (saved
    extension entries are kept), or a one-tuple holding the new ``hlinkClr``
    value, where ``(None,)`` clears it. It is a plain ``str`` everywhere an
    address is expected, so queue bookkeeping keeps working unchanged.
    """

    screen_tip: str | None
    color_source_edit: tuple[str | None] | None

    def __new__(
        cls,
        address: str,
        screen_tip: str | None = None,
        color_source_edit: tuple[str | None] | None = None,
    ) -> Self:
        value = super().__new__(cls, address)
        value.screen_tip = screen_tip
        value.color_source_edit = color_source_edit
        return value

    def __reduce__(self) -> tuple[Any, ...]:
        return (RunHyperlinkAddress, (str(self), self.screen_tip, self.color_source_edit))


def queued_hyperlink_address(
    address: str | None,
    screen_tip: str | None,
    color_source_edit: tuple[str | None] | None = None,
) -> str | None:
    """The queue value for a hyperlink: a plain address unless metadata rides along."""
    if address is None or (screen_tip is None and color_source_edit is None):
        return address
    return RunHyperlinkAddress(address, screen_tip, color_source_edit)


def hyperlink_color_source_xml(value: Any) -> str | None:
    """``hlinkClr/@val`` for a requested color source; refuse anything else."""
    if value is None:
        return None
    if isinstance(value, PP_HYPERLINK_COLOR_SOURCE):
        return value.xml_value
    if isinstance(value, str) and value in {"hlink", "tx"}:
        return value
    raise HyperlinkColorSourceRefusal(
        f"hyperlink color_source must be a PP_HYPERLINK_COLOR_SOURCE member, 'hlink', "
        f"'tx' or None, got {value!r}"
    )


def hyperlink_color_source_member(xml_value: str | None) -> PP_HYPERLINK_COLOR_SOURCE | None:
    return None if xml_value is None else PP_HYPERLINK_COLOR_SOURCE.from_xml(xml_value)


def _hyperlink_color_extensions(hyperlink: ET.Element) -> list[ET.Element]:
    a_ns = ooxml_namespace(hyperlink, A_NS)
    return [
        extension
        for extension in hyperlink.findall(f"{{{a_ns}}}extLst/{{{a_ns}}}ext")
        if extension.get("uri") == HYPERLINK_COLOR_EXT_URI
    ]


def saved_hyperlink_color_source(hyperlink: ET.Element | None) -> str | None:
    """Saved ``hlinkClr/@val`` of an ``a:hlinkClick``; refuse malformed entries."""
    if hyperlink is None:
        return None
    extensions = _hyperlink_color_extensions(hyperlink)
    if not extensions:
        return None
    if len(extensions) > 1:
        raise HyperlinkColorSourceRefusal("hyperlink carries more than one hlinkClr extension")
    color = extensions[0].find(f"{{{HYPERLINK_COLOR_NS}}}hlinkClr")
    value = None if color is None else color.get("val")
    if value not in {"hlink", "tx"}:
        raise HyperlinkColorSourceRefusal(
            f"hyperlink hlinkClr extension has unsupported value {value!r}; "
            "expected 'hlink' or 'tx'"
        )
    return value


def _set_hyperlink_color_source(hyperlink: ET.Element, value: str | None) -> None:
    """Write or clear ``hlinkClr`` in place, keeping every other extension entry."""
    a_ns = ooxml_namespace(hyperlink, A_NS)
    extensions = _hyperlink_color_extensions(hyperlink)
    extension_list = hyperlink.find(f"{{{a_ns}}}extLst")
    kept = extensions[0] if extensions and value is not None else None
    for extension in extensions:
        if extension is not kept and extension_list is not None:
            extension_list.remove(extension)
    if value is None:
        if extension_list is not None and len(extension_list) == 0:
            hyperlink.remove(extension_list)
        return
    if kept is None:
        if extension_list is None:
            # ``extLst`` is the last child of CT_Hyperlink.
            extension_list = ET.SubElement(hyperlink, f"{{{a_ns}}}extLst")
        kept = ET.SubElement(extension_list, f"{{{a_ns}}}ext", {"uri": HYPERLINK_COLOR_EXT_URI})
    for child in list(kept):
        kept.remove(child)
    ET.SubElement(kept, f"{{{HYPERLINK_COLOR_NS}}}hlinkClr", {"val": value})


def _apply_hyperlink_metadata(hyperlink: ET.Element, address: Any) -> None:
    """Apply the tooltip and color source a queued address carries."""
    if not isinstance(address, RunHyperlinkAddress):
        return
    if address.screen_tip is None:
        hyperlink.attrib.pop("tooltip", None)
    else:
        hyperlink.set("tooltip", address.screen_tip)
    if address.color_source_edit is not None:
        _set_hyperlink_color_source(hyperlink, address.color_source_edit[0])


def _shape_xml_element(root: ET.Element, shape_payload: dict[str, Any]) -> ET.Element:
    shape_id = shape_payload.get("id")
    shape_tree = find_ooxml(root, f".//{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if shape_tree is None:
        raise AttributeError("shape XML element is unavailable")
    for element in _iter_shape_elements(shape_tree):
        nv = find_ooxml(element, f".//{{{P_NS}}}cNvPr")
        if nv is not None and nv.attrib.get("id") == str(shape_id):
            return element
    raise AttributeError("shape XML element is unavailable")


def _iter_shape_elements(container: ET.Element):
    for element in list(container):
        tag = _xml_local_name(element.tag)
        if tag not in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}:
            continue
        if element.tag != f"{{{ooxml_namespace(container, P_NS)}}}{tag}":
            continue
        yield element
        if tag == "grpSp":
            yield from _iter_shape_elements(element)


def _paragraph_xml_element(shape_element: ET.Element, paragraph_index: int) -> ET.Element:
    text_body = find_ooxml(shape_element, f"{{{P_NS}}}txBody")
    if text_body is None:
        raise AttributeError("shape text body is unavailable")
    paragraphs = findall_ooxml(text_body, f"{{{A_NS}}}p")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        raise IndexError("paragraph index out of range")
    return paragraphs[paragraph_index]


def _part_paragraph_xml_element(
    shape_element: ET.Element, paragraph_index: int, *, allow_append: bool = False
) -> ET.Element:
    """Resolve a part paragraph in its source profile, optionally appending one."""
    body = find_ooxml(shape_element, f"{{{P_NS}}}txBody")
    if body is None:
        raise AttributeError("shape text body is unavailable")
    paragraphs = findall_ooxml(body, f"{{{A_NS}}}p")
    if allow_append and paragraph_index == len(paragraphs):
        paragraph = ET.Element(f"{{{ooxml_namespace(body, A_NS)}}}p")
        insert_at = list(body).index(paragraphs[-1]) + 1 if paragraphs else len(body)
        body.insert(insert_at, paragraph)
        return paragraph
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        raise IndexError("paragraph index out of range")
    return paragraphs[paragraph_index]


def _part_text_run_slots(paragraph: ET.Element) -> list[ET.Element]:
    """Match the part reader's document-ordered, empty-inclusive r/fld slots."""
    return [child for child in paragraph if _xml_local_name(child.tag) in {"r", "fld"}]


def _part_text_run_xml_element(
    shape_element: ET.Element, paragraph_index: int, run_index: int
) -> ET.Element:
    runs = _part_text_run_slots(_part_paragraph_xml_element(shape_element, paragraph_index))
    if run_index < 0 or run_index >= len(runs):
        raise IndexError("run index out of range")
    return runs[run_index]


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
                "".join(text_node.text or "" for text_node in child.findall(f".//{{{A_NS}}}t"))
            )
    if parts:
        return "".join(parts)
    return "".join(text_node.text or "" for text_node in paragraph.findall(f".//{{{A_NS}}}t"))


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
    p_ns = ooxml_namespace(shape_element, P_NS)
    shape_properties = shape_element.find(f"{{{p_ns}}}spPr")
    if shape_properties is not None:
        return shape_properties
    shape_properties = ET.Element(f"{{{p_ns}}}spPr")
    insert_at = 0
    if (
        shape_element.find(f"{{{p_ns}}}nvSpPr") is not None
        or shape_element.find(f"{{{p_ns}}}nvCxnSpPr") is not None
    ):
        insert_at = 1
    elif shape_element.find(f"{{{p_ns}}}nvPicPr") is not None:
        insert_at = 1
        if shape_element.find(f"{{{p_ns}}}blipFill") is not None:
            insert_at = 2
    shape_element.insert(insert_at, shape_properties)
    return shape_properties


def _find_shape_transform_xml_element(shape_element: ET.Element) -> ET.Element | None:
    tag = _xml_local_name(shape_element.tag)
    if tag == "graphicFrame":
        return find_ooxml(shape_element, f"{{{P_NS}}}xfrm")
    if tag == "grpSp":
        return find_ooxml(shape_element, f"{{{P_NS}}}grpSpPr/{{{A_NS}}}xfrm")
    shape_properties = find_ooxml(shape_element, f"{{{P_NS}}}spPr")
    if shape_properties is None:
        return None
    return find_ooxml(shape_properties, f"{{{A_NS}}}xfrm")


def _shape_transform_xml_element(shape_element: ET.Element) -> ET.Element:
    existing = _find_shape_transform_xml_element(shape_element)
    if existing is not None:
        return existing
    p_ns = ooxml_namespace(shape_element, P_NS)
    a_ns = ooxml_namespace(shape_element, A_NS)
    tag = _xml_local_name(shape_element.tag)
    if tag == "graphicFrame":
        transform = ET.Element(f"{{{p_ns}}}xfrm")
        insert_at = 1 if shape_element.find(f"{{{p_ns}}}nvGraphicFramePr") is not None else 0
        shape_element.insert(insert_at, transform)
        return transform
    if tag == "grpSp":
        group_properties = shape_element.find(f"{{{p_ns}}}grpSpPr")
        if group_properties is None:
            group_properties = ET.Element(f"{{{p_ns}}}grpSpPr")
            insert_at = 1 if shape_element.find(f"{{{p_ns}}}nvGrpSpPr") is not None else 0
            shape_element.insert(insert_at, group_properties)
        transform = ET.Element(f"{{{a_ns}}}xfrm")
        group_properties.insert(0, transform)
        return transform
    shape_properties = _shape_properties_element(shape_element)
    transform = ET.Element(f"{{{a_ns}}}xfrm")
    shape_properties.insert(0, transform)
    return transform


def _set_connector_connection(
    connector_element: ET.Element,
    endpoint: str,
    target_shape_id: int | str,
    cxn_pt_idx: int,
) -> None:
    connection_properties = _connector_connection_properties_element(connector_element)
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
    paragraph_properties = find_ooxml(paragraph, f"{{{A_NS}}}pPr")
    if paragraph_properties is not None:
        return paragraph_properties
    paragraph_properties = ET.Element(f"{{{ooxml_namespace(paragraph, A_NS)}}}pPr")
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


def _run_properties_element(run_element: ET.Element, *, part_scoped: bool = False) -> ET.Element:
    a_ns = ooxml_namespace(run_element, A_NS) if part_scoped else A_NS
    run_properties = run_element.find(f"{{{a_ns}}}rPr")
    if run_properties is not None:
        return run_properties
    run_properties = ET.Element(f"{{{a_ns}}}rPr")
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
    # A queued slide-show jump is an ``action`` with no relationship target.
    show_jump_action = getattr(address, "show_jump_action", None)
    if show_jump_action is not None:
        _set_hyperlink_address(non_visual_properties, rels_root, None, action=show_jump_action)
        return
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
    *,
    part_root: ET.Element | None = None,
) -> None:
    a_ns = ooxml_namespace(owner, A_NS) if part_root is not None else A_NS
    r_ns = ooxml_namespace(owner, R_NS) if part_root is not None else R_NS
    existing = owner.find(f"{{{a_ns}}}hlinkClick")
    if existing is not None and _targets_same_hyperlink(
        existing, rels_root, address, relationship_type, target_mode, r_ns
    ):
        # A targeted color edit on an unchanged link rewrites nothing else.
        _apply_hyperlink_metadata(existing, address)
        return
    # Retargeting keeps the link's extension entries (color source and others).
    extensions = None if existing is None else existing.find(f"{{{a_ns}}}extLst")
    if existing is not None:
        relationship_id = existing.attrib.get(f"{{{r_ns}}}id")
        owner.remove(existing)
        if relationship_id and (
            part_root is None
            or not any(
                value == relationship_id
                for element in part_root.iter()
                for attribute, value in element.attrib.items()
                if attribute.startswith(f"{{{R_NS}}}") or attribute.startswith(f"{{{r_ns}}}")
            )
        ):
            _remove_relationship(rels_root, relationship_id)
    if not address and action is None:
        return
    relationship_id = ""
    if address:
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
    hyperlink = ET.Element(f"{{{a_ns}}}hlinkClick")
    hyperlink.set(f"{{{r_ns}}}id", relationship_id)
    if action is not None:
        hyperlink.set("action", action)
    if extensions is not None:
        hyperlink.append(extensions)
    _apply_hyperlink_metadata(hyperlink, address)
    insert_at = len(owner)
    for index, child in enumerate(list(owner)):
        if _xml_local_name(child.tag) == "extLst" or (
            part_root is not None and _xml_local_name(child.tag) in {"hlinkMouseOver", "rtl"}
        ):
            insert_at = index
            break
    owner.insert(insert_at, hyperlink)


def _targets_same_hyperlink(
    existing: ET.Element,
    rels_root: ET.Element,
    address: Any,
    relationship_type: str,
    target_mode: str | None,
    r_ns: str,
) -> bool:
    """Whether a queued color edit leaves the saved link target untouched."""
    if getattr(address, "color_source_edit", None) is None:
        return False
    if existing.get("action") is not None:
        return False
    relationship_id = existing.get(f"{{{r_ns}}}id")
    return any(
        _xml_local_name(relationship.tag) == "Relationship"
        and relationship.get("Id") == relationship_id
        and relationship.get("Type") == relationship_type
        and relationship.get("Target") == str(address)
        and relationship.get("TargetMode") == target_mode
        for relationship in rels_root
    )


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


def parse_ooxml_bool(raw: Any) -> bool:
    if raw is None:
        return False
    if type(raw) is bool:
        return raw
    s = str(raw).strip()
    lower = s.lower()
    if lower in {"1", "true", "on"}:
        return True
    if lower in {"0", "false", "off"}:
        return False
    raise ValueError(f"malformed OOXML boolean: {raw!r}")


def _set_shape_flip(
    transform: ET.Element,
    flip_h: bool | None = None,
    flip_v: bool | None = None,
) -> None:
    if flip_h is not None:
        if flip_h:
            transform.set("flipH", "1")
        else:
            transform.attrib.pop("flipH", None)
    if flip_v is not None:
        if flip_v:
            transform.set("flipV", "1")
        else:
            transform.attrib.pop("flipV", None)


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


def _set_shape_preset_geometry(shape_properties: ET.Element, preset: str) -> None:
    """Set ``a:prstGeom/@prst`` and keep only the adjust guides ``preset`` declares."""
    a_ns = ooxml_namespace(shape_properties, A_NS)
    preset_geometry = shape_properties.find(f"{{{a_ns}}}prstGeom")
    if preset_geometry is None:
        raise AttributeError("shape preset geometry is unavailable")
    preset_geometry.set("prst", preset)
    adjust_value_list = preset_geometry.find(f"{{{a_ns}}}avLst")
    if adjust_value_list is None:
        return
    declared = set(PRESET_ADJUST_GUIDE_NAMES[preset])
    for guide in list(adjust_value_list):
        if guide.get("name") not in declared:
            adjust_value_list.remove(guide)


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
        units = round(float(crop.get(key, 0.0)) * 100000)
        if units:
            src_rect.set(key, str(units))
        else:
            src_rect.attrib.pop(key, None)


def _set_run_font_color(run_properties: ET.Element, color: str | dict[str, Any]) -> None:
    if isinstance(color, dict) and color.get("type") == "xml":
        element = ET.fromstring(color["value"])
        _validate_text_color_element(element)
        fill = _run_solid_fill_element(run_properties)
        fill.append(element)
        return
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
        colors = {
            role: payload[f"pattern_{role}_color"]
            for role in ("fore", "back")
            if f"pattern_{role}_color" in payload
        }
        for color in colors.values():
            _validate_text_color_element(color)
        pattern = run_properties.find(f"{{{A_NS}}}pattFill")
        if pattern is None:
            _set_run_pattern_fill(run_properties, payload.get("pattern"))
        elif payload.get("pattern") is None:
            pattern.attrib.pop("prst", None)
        else:
            pattern.set("prst", payload["pattern"])
        for role in ("fore", "back"):
            rgb = payload.get(f"pattern_{role}_rgb")
            if rgb is None:
                continue
            tag = "bgClr" if role == "back" else "fgClr"
            existing = run_properties.find(f"{{{A_NS}}}pattFill/{{{A_NS}}}{tag}/{{{A_NS}}}srgbClr")
            if existing is None or existing.get("val") != str(rgb):
                _set_run_pattern_fill_color(run_properties, tag, str(rgb))
        for role, color in colors.items():
            _set_run_pattern_fill_color(
                run_properties,
                "bgClr" if role == "back" else "fgClr",
                {"type": "xml", "value": ET.tostring(color, encoding="unicode")},
            )
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
    if "strike" in edits:
        _set_font_strike(default_run_properties, edits["strike"])
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
    spacing: dict[str, int | float | str | None],
) -> None:
    for attr in ("line_spacing", "space_before", "space_after"):
        if attr not in spacing:
            continue
        _set_paragraph_spacing_value(
            paragraph_properties,
            _paragraph_spacing_xml_tag(attr),
            spacing[attr],
        )
    for attr, xml_attribute in {
        "margin_left": "marL",
        "margin_right": "marR",
        "indent": "indent",
    }.items():
        if attr not in spacing:
            continue
        value = spacing[attr]
        if value is None:
            paragraph_properties.attrib.pop(xml_attribute, None)
        else:
            paragraph_properties.set(xml_attribute, str(int(value)))
    if "rtl" in spacing:
        rtl = spacing["rtl"]
        if rtl is None:
            paragraph_properties.attrib.pop("rtl", None)
        else:
            paragraph_properties.set("rtl", "1" if rtl else "0")
    if "font_alignment" in spacing:
        from .enum.text import ParagraphFontAlignment

        alignment = spacing["font_alignment"]
        if alignment is None:
            paragraph_properties.attrib.pop("fontAlgn", None)
        else:
            paragraph_properties.set("fontAlgn", ParagraphFontAlignment.from_xml(alignment).value)


def _set_paragraph_spacing_value(
    paragraph_properties: ET.Element,
    tag: str,
    value: float | None,
) -> None:
    _remove_paragraph_spacing_child(paragraph_properties, tag)
    if value is None:
        return
    spacing = ET.Element(f"{{{A_NS}}}{tag}")
    if tag == "lnSpc" and isinstance(value, float):
        ET.SubElement(spacing, f"{{{A_NS}}}spcPct").set(
            "val",
            str(round(value * 100000)),
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


_BULLET_TYPE_TAGS = ("buNone", "buChar", "buAutoNum", "buBlip")
_BULLET_FORMAT_TAGS = (
    "buClr",
    "buClrTx",
    "buFont",
    "buFontTx",
    "buSzTx",
    "buSzPct",
    "buSzPts",
)
_PPR_CHILD_ORDER = {
    "lnSpc": 10,
    "spcBef": 20,
    "spcAft": 30,
    "buClrTx": 40,
    "buClr": 40,
    "buSzTx": 50,
    "buSzPct": 50,
    "buSzPts": 50,
    "buFontTx": 60,
    "buFont": 60,
    "buNone": 70,
    "buAutoNum": 70,
    "buChar": 70,
    "buBlip": 70,
    "tabLst": 80,
    "defRPr": 90,
    "extLst": 100,
}


def _ppr_child_insert_index(paragraph_properties: ET.Element, tag: str) -> int:
    target_rank = _PPR_CHILD_ORDER.get(tag, 70)
    for index, child in enumerate(list(paragraph_properties)):
        child_name = _xml_local_name(child.tag)
        child_rank = _PPR_CHILD_ORDER.get(child_name, 70)
        if child_rank > target_rank:
            return index
    return len(paragraph_properties)


def _remove_bullet_type_elements(paragraph_properties: ET.Element) -> None:
    for child in list(paragraph_properties):
        if _xml_local_name(child.tag) in _BULLET_TYPE_TAGS:
            paragraph_properties.remove(child)


def _remove_all_bullet_elements(paragraph_properties: ET.Element) -> None:
    bullet_all = set(_BULLET_TYPE_TAGS) | set(_BULLET_FORMAT_TAGS)
    for child in list(paragraph_properties):
        if _xml_local_name(child.tag) in bullet_all:
            paragraph_properties.remove(child)


def _set_paragraph_bullet_font(
    paragraph_properties: ET.Element,
    font: str | None,
) -> None:
    for child in list(paragraph_properties):
        if _xml_local_name(child.tag) in {"buFont", "buFontTx"}:
            paragraph_properties.remove(child)
    if not font:
        return
    bu_font = ET.Element(f"{{{A_NS}}}buFont", {"typeface": str(font)})
    idx = _ppr_child_insert_index(paragraph_properties, "buFont")
    paragraph_properties.insert(idx, bu_font)


def _remove_paragraph_bullet_font(paragraph_properties: ET.Element) -> None:
    for child in list(paragraph_properties):
        if _xml_local_name(child.tag) in {"buFont", "buFontTx"}:
            paragraph_properties.remove(child)


def _set_paragraph_bullet_color(
    paragraph_properties: ET.Element,
    color: str | None,
) -> None:
    for child in list(paragraph_properties):
        if _xml_local_name(child.tag) in {"buClr", "buClrTx"}:
            paragraph_properties.remove(child)
    if not color:
        return
    clean = str(color).strip().lstrip("#").upper()
    bu_clr = ET.Element(f"{{{A_NS}}}buClr")
    ET.SubElement(bu_clr, f"{{{A_NS}}}srgbClr", {"val": clean})
    idx = _ppr_child_insert_index(paragraph_properties, "buClr")
    paragraph_properties.insert(idx, bu_clr)


def _remove_paragraph_bullet_color(paragraph_properties: ET.Element) -> None:
    for child in list(paragraph_properties):
        if _xml_local_name(child.tag) in {"buClr", "buClrTx"}:
            paragraph_properties.remove(child)


def _set_paragraph_bullet_char(
    paragraph_properties: ET.Element,
    char: str,
    font: str | None = None,
    color: str | None = None,
) -> None:
    _remove_bullet_type_elements(paragraph_properties)
    if font is not None:
        _set_paragraph_bullet_font(paragraph_properties, font)
    if color is not None:
        _set_paragraph_bullet_color(paragraph_properties, color)
    bu_char = ET.Element(f"{{{A_NS}}}buChar", {"char": str(char)})
    idx = _ppr_child_insert_index(paragraph_properties, "buChar")
    paragraph_properties.insert(idx, bu_char)


def _set_paragraph_auto_number(
    paragraph_properties: ET.Element,
    style: str = "arabicPeriod",
    start_at: int = 1,
    font: str | None = None,
    color: str | None = None,
) -> None:
    _remove_bullet_type_elements(paragraph_properties)
    if font is not None:
        _set_paragraph_bullet_font(paragraph_properties, font)
    if color is not None:
        _set_paragraph_bullet_color(paragraph_properties, color)
    attribs = {"type": str(style)}
    if int(start_at) > 1:
        attribs["startAt"] = str(int(start_at))
    elif int(start_at) == 1:
        attribs["startAt"] = "1"
    bu_autonum = ET.Element(f"{{{A_NS}}}buAutoNum", attribs)
    idx = _ppr_child_insert_index(paragraph_properties, "buAutoNum")
    paragraph_properties.insert(idx, bu_autonum)


def _set_paragraph_picture_bullet(paragraph_properties: ET.Element, relationship_id: str) -> None:
    _remove_bullet_type_elements(paragraph_properties)
    bullet = ET.Element(f"{{{A_NS}}}buBlip")
    blip = ET.SubElement(bullet, f"{{{A_NS}}}blip")
    blip.set(f"{{{R_NS}}}embed", relationship_id)
    paragraph_properties.insert(_ppr_child_insert_index(paragraph_properties, "buBlip"), bullet)


def _set_paragraph_no_bullet(paragraph_properties: ET.Element) -> None:
    _remove_all_bullet_elements(paragraph_properties)
    bu_none = ET.Element(f"{{{A_NS}}}buNone")
    idx = _ppr_child_insert_index(paragraph_properties, "buNone")
    paragraph_properties.insert(idx, bu_none)


def _clear_paragraph_bullet(paragraph_properties: ET.Element) -> None:
    _remove_all_bullet_elements(paragraph_properties)


def _set_paragraph_bullet(
    paragraph_properties: ET.Element,
    bullet: dict[str, Any] | None,
) -> None:
    if bullet is None:
        _clear_paragraph_bullet(paragraph_properties)
        return
    btype = bullet.get("type") or bullet.get("kind")
    if btype in (None, "clear"):
        _clear_paragraph_bullet(paragraph_properties)
    elif btype == "none":
        _set_paragraph_no_bullet(paragraph_properties)
    elif btype == "char":
        _set_paragraph_bullet_char(
            paragraph_properties,
            char=str(bullet.get("char", "•")),
            font=bullet.get("font"),
            color=bullet.get("color"),
        )
    elif btype == "auto_number":
        _set_paragraph_auto_number(
            paragraph_properties,
            style=str(bullet.get("style", "arabicPeriod")),
            start_at=int(bullet.get("start_at", 1)),
            font=bullet.get("font"),
            color=bullet.get("color"),
        )
    elif btype == "blip":
        relationship_id = bullet.get("embed")
        if not isinstance(relationship_id, str) or not relationship_id:
            raise ValueError("picture bullet requires an image relationship")
        _set_paragraph_picture_bullet(paragraph_properties, relationship_id)
    else:
        raise ValueError(f"unsupported bullet type: {btype}")


def _read_paragraph_bullet(paragraph_properties: ET.Element) -> dict[str, Any] | None:
    bullet_type = None
    bullet_dict: dict[str, Any] = {}

    for child in list(paragraph_properties):
        local_name = _xml_local_name(child.tag)
        if local_name == "buNone":
            bullet_type = "none"
        elif local_name == "buChar":
            bullet_type = "char"
            bullet_dict["char"] = child.attrib.get("char", "")
        elif local_name == "buAutoNum":
            bullet_type = "auto_number"
            bullet_dict["style"] = child.attrib.get("type", "arabicPeriod")
            start_at_raw = child.attrib.get("startAt")
            if start_at_raw is not None:
                try:
                    bullet_dict["start_at"] = int(start_at_raw)
                except ValueError:
                    bullet_dict["start_at"] = 1
            else:
                bullet_dict["start_at"] = 1
        elif local_name == "buBlip":
            bullet_type = "blip"
        elif local_name == "buFont":
            typeface = child.attrib.get("typeface")
            if typeface:
                bullet_dict["font"] = typeface
        elif local_name == "buClr":
            srgb = find_ooxml(child, f"{{{A_NS}}}srgbClr")
            if srgb is not None and srgb.attrib.get("val"):
                bullet_dict["color"] = srgb.attrib.get("val").upper()

    if bullet_type is None:
        return None

    bullet_dict["type"] = bullet_type
    return bullet_dict


# Office 2016+ zoom namespaces, per [MS-PPTX] 5.7-5.9 and PowerPoint's own
# namespace table (prefixes pslz, psez, p166).
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
PSLZ_NS = "http://schemas.microsoft.com/office/powerpoint/2016/slidezoom"
PSEZ_NS = "http://schemas.microsoft.com/office/powerpoint/2016/sectionzoom"
P166_NS = "http://schemas.microsoft.com/office/powerpoint/2016/6/main"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"
_SLIDE_CREATION_ID_EXT_URI = "{BB962C8B-B14F-4D97-AF65-F5344CB8AC3E}"
_MAX_UNSIGNED_INT = 0xFFFFFFFF
ZOOM_IMAGE_TYPES = frozenset({"preview", "cover"})
_ZOOM_KINDS = {
    # kind: (namespace, Requires prefix, container, object, target attribute)
    "slide": (PSLZ_NS, "pslz", "sldZm", "sldZmObj", "sldId"),
    "section": (PSEZ_NS, "psez", "sectionZm", "sectionZmObj", "sectionId"),
}


def register_zoom_namespaces() -> None:
    """Pin prefixes so the mc:Choice ``Requires`` token resolves when serialized."""
    ET.register_namespace("p", P_NS)
    ET.register_namespace("a", A_NS)
    ET.register_namespace("r", R_NS)
    ET.register_namespace("mc", MC_NS)
    ET.register_namespace("pslz", PSLZ_NS)
    ET.register_namespace("psez", PSEZ_NS)
    ET.register_namespace("p166", P166_NS)
    ET.register_namespace("p14", P14_NS)


def slide_creation_id(slide_root: ET.Element) -> str | None:
    """Return the slide's ``p14:creationId`` (an xsd:unsignedInt), if it has one."""
    for extension in slide_root.findall(f"{{{P_NS}}}extLst/{{{P_NS}}}ext"):
        if extension.get("uri", "").upper() != _SLIDE_CREATION_ID_EXT_URI:
            continue
        creation = extension.find(f"{{{P14_NS}}}creationId")
        value = "" if creation is None else (creation.get("val") or "").strip()
        if value.isdigit() and int(value) <= _MAX_UNSIGNED_INT:
            return str(int(value))
    return None


def zoom_alternate_content(
    kind: str,
    *,
    shape_id: int,
    name: str,
    offset: tuple[int, int],
    extent: tuple[int, int],
    target: str,
    zoom_id: str,
    image_relationship_id: str,
    link_relationship_id: str,
    return_to_parent: bool,
    image_type: str,
    creation_id: str | None = None,
    transition_duration: str | None = None,
    show_background: bool | None = None,
) -> ET.Element:
    """Build a slide or section zoom as PowerPoint writes it.

    The mc:Choice holds a graphicFrame whose graphicData carries the zoom
    object; the mc:Fallback is a picture with a slide-jump hyperlink so older
    consumers keep an equivalent navigable thumbnail ([MS-PPTX] Zoom Extensions).
    ``creation_id`` is the target slide's ``p14:creationId``; PowerPoint pairs a
    slide zoom with its target through ``cId`` and renders it broken when the
    target carries a creation id the zoom does not repeat.
    """
    namespace, prefix, container, zoom_object, target_attribute = _ZOOM_KINDS[kind]
    if image_type not in ZOOM_IMAGE_TYPES:
        raise ValueError(f"zoom image_type must be one of {sorted(ZOOM_IMAGE_TYPES)}")
    alternate = ET.Element(f"{{{MC_NS}}}AlternateContent")
    choice = ET.SubElement(alternate, f"{{{MC_NS}}}Choice", {"Requires": prefix})
    frame = ET.SubElement(choice, f"{{{P_NS}}}graphicFrame")
    frame_non_visual = ET.SubElement(frame, f"{{{P_NS}}}nvGraphicFramePr")
    ET.SubElement(frame_non_visual, f"{{{P_NS}}}cNvPr", {"id": str(shape_id), "name": name})
    frame_locks = ET.SubElement(frame_non_visual, f"{{{P_NS}}}cNvGraphicFramePr")
    ET.SubElement(frame_locks, f"{{{A_NS}}}graphicFrameLocks", {"noChangeAspect": "1"})
    ET.SubElement(frame_non_visual, f"{{{P_NS}}}nvPr")
    _append_zoom_transform(frame, f"{{{P_NS}}}xfrm", offset, extent)
    graphic = ET.SubElement(frame, f"{{{A_NS}}}graphic")
    graphic_data = ET.SubElement(graphic, f"{{{A_NS}}}graphicData", {"uri": namespace})
    zoom_container = ET.SubElement(graphic_data, f"{{{namespace}}}{container}")
    zoom_target = ET.SubElement(
        zoom_container, f"{{{namespace}}}{zoom_object}", {target_attribute: target}
    )
    if creation_id is not None:
        zoom_target.set("cId", creation_id)
    properties = ET.SubElement(
        zoom_target,
        f"{{{namespace}}}zmPr",
        {"id": zoom_id, "returnToParent": "1" if return_to_parent else "0"},
    )
    if image_type != "preview":
        properties.set("imageType", image_type)
    if show_background is not None:
        properties.set("showBg", "1" if show_background else "0")
    if transition_duration is not None:
        properties.set("transitionDur", transition_duration)
    _append_zoom_blip_fill(properties, f"{{{P166_NS}}}blipFill", image_relationship_id)
    _append_zoom_shape_properties(properties, f"{{{P166_NS}}}spPr", (0, 0), extent)

    fallback = ET.SubElement(alternate, f"{{{MC_NS}}}Fallback")
    picture = ET.SubElement(fallback, f"{{{P_NS}}}pic")
    picture_non_visual = ET.SubElement(picture, f"{{{P_NS}}}nvPicPr")
    identity = ET.SubElement(
        picture_non_visual, f"{{{P_NS}}}cNvPr", {"id": str(shape_id), "name": name}
    )
    ET.SubElement(
        identity,
        f"{{{A_NS}}}hlinkClick",
        {f"{{{R_NS}}}id": link_relationship_id, "action": _NAMED_SLIDE_ACTION},
    )
    picture_locks = ET.SubElement(picture_non_visual, f"{{{P_NS}}}cNvPicPr")
    ET.SubElement(
        picture_locks,
        f"{{{A_NS}}}picLocks",
        {"noGrp": "1", "noRot": "1", "noChangeAspect": "1"},
    )
    ET.SubElement(picture_non_visual, f"{{{P_NS}}}nvPr")
    _append_zoom_blip_fill(picture, f"{{{P_NS}}}blipFill", image_relationship_id)
    _append_zoom_shape_properties(picture, f"{{{P_NS}}}spPr", offset, extent)
    return alternate


def _append_zoom_transform(
    parent: ET.Element,
    tag: str,
    offset: tuple[int, int],
    extent: tuple[int, int],
) -> None:
    transform = ET.SubElement(parent, tag)
    ET.SubElement(transform, f"{{{A_NS}}}off", {"x": str(offset[0]), "y": str(offset[1])})
    ET.SubElement(transform, f"{{{A_NS}}}ext", {"cx": str(extent[0]), "cy": str(extent[1])})


def _append_zoom_blip_fill(parent: ET.Element, tag: str, relationship_id: str) -> None:
    blip_fill = ET.SubElement(parent, tag)
    ET.SubElement(blip_fill, f"{{{A_NS}}}blip", {f"{{{R_NS}}}embed": relationship_id})
    stretch = ET.SubElement(blip_fill, f"{{{A_NS}}}stretch")
    ET.SubElement(stretch, f"{{{A_NS}}}fillRect")


def _append_zoom_shape_properties(
    parent: ET.Element,
    tag: str,
    offset: tuple[int, int],
    extent: tuple[int, int],
) -> None:
    shape_properties = ET.SubElement(parent, tag)
    _append_zoom_transform(shape_properties, f"{{{A_NS}}}xfrm", offset, extent)
    geometry = ET.SubElement(shape_properties, f"{{{A_NS}}}prstGeom", {"prst": "rect"})
    ET.SubElement(geometry, f"{{{A_NS}}}avLst")
    line = ET.SubElement(shape_properties, f"{{{A_NS}}}ln", {"w": "3175"})
    line_fill = ET.SubElement(line, f"{{{A_NS}}}solidFill")
    ET.SubElement(line_fill, f"{{{A_NS}}}prstClr", {"val": "ltGray"})
