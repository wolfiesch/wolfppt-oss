"""XML readers for text paragraph and run facade state."""

from __future__ import annotations

import zipfile
from copy import deepcopy
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
)
from .dml_fill import (
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)
from .dml_fill import validate_text_color_element as _validate_text_color_element
from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
)
from .facade_values import (
    coerce_paragraph_level as _coerce_paragraph_level,
)
from .facade_values import (
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
)
from .shape_edit_refs import shape_edit_ref
from .shape_xml import (
    _paragraph_xml_element,
    _part_text_run_xml_element,
    _shape_xml_element,
    _text_run_xml_element,
)
from .slide_relationships import slide_relationship_target as _slide_relationship_target
from .xml_helpers import find_ooxml, findall_ooxml, ooxml_namespace, percentage_value

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

if TYPE_CHECKING:
    from .shape_core_facade import Shape


def _shape_text_part_root(shape: Shape) -> ET.Element:
    """Return the current source XML root for a text facade's package part."""
    presentation = shape._slide._presentation
    partname = shape._slide.partname
    cache = presentation._facade_xml_root_cache
    root = cache.get(partname)
    if root is not None:
        return root
    with zipfile.ZipFile(presentation.path) as package:
        root = ET.fromstring(package.read(partname))
    cache[partname] = root
    return root


def _paragraph_edit_source(shape: Shape, paragraph_index: int) -> tuple[bool, str, tuple[Any, ...]]:
    """Resolve whole-text and property queues using their native target keys."""
    slide = shape._slide
    presentation = slide._presentation
    payload = shape._payload
    if getattr(slide, "_is_notes_slide", False):
        key = (str(slide.partname), shape._index)
        replacements = presentation._part_shape_text_edits
        prefix = "_part"
        paragraph_key = (*key, paragraph_index)
        if key not in replacements and paragraph_key in presentation._part_paragraph_text_edits:
            root = _shape_text_part_root(shape)
            element = _shape_xml_element(root, payload)
            body = element.find(
                "{http://schemas.openxmlformats.org/presentationml/2006/main}txBody"
            )
            if body is not None and paragraph_index >= len(body.findall(f"{{{A_NS}}}p")):
                return True, prefix, paragraph_key
    elif payload.get("_group_child"):
        key = (slide._index, int(payload["_group_index"]))
        if payload.get("_deep_nested_group_child"):
            key += (
                int(payload["_nested_group_child_index"]),
                int(payload["_deeper_group_child_index"]),
            )
            replacements = presentation._deeper_group_child_text_edits
        elif payload.get("_nested_group_child"):
            key += (int(payload["_nested_group_child_index"]),)
            replacements = presentation._nested_group_child_text_edits
        else:
            replacements = presentation._group_child_text_edits
        key += (int(payload["_group_child_index"]),)
        replaced = key in replacements
        key = (slide._index, shape_edit_ref(shape)[:-1], key[-1])
        return replaced, "_group_child", (*key, paragraph_index)
    else:
        key = (slide._index, shape._index)
        replacements = presentation._shape_text_edits
        prefix = ""
    return key in replacements, prefix, (*key, paragraph_index)


def _pending_paragraph_property(
    shape: Shape, paragraph_index: int, property_name: str, default: Any = None
) -> tuple[bool, Any]:
    """Prefer explicit pending properties, then blank replacement defaults."""
    replaced, prefix, key = _paragraph_edit_source(shape, paragraph_index)
    edits = getattr(shape._slide._presentation, f"{prefix}_paragraph_{property_name}_edits")
    return replaced or key in edits, edits.get(key, default)


def _shape_text_paragraph_tab_stops(shape: Shape, paragraph_index: int) -> list[dict[str, Any]]:
    pending, stops = _pending_paragraph_property(shape, paragraph_index, "tab_stop")
    if pending:
        return [] if stops is None else stops
    if not str(getattr(shape._slide, "partname", "")):
        return []
    root = _shape_text_part_root(shape)
    shape_element = _shape_xml_element(root, shape._payload)
    paragraph = _paragraph_xml_element(shape_element, paragraph_index)
    tab_list = find_ooxml(paragraph, f"{{{A_NS}}}pPr/{{{A_NS}}}tabLst")
    if tab_list is None:
        return []
    return [
        {"pos": int(tab.get("pos", "0")), "align": tab.get("algn", "l")}
        for tab in findall_ooxml(tab_list, f"{{{A_NS}}}tab")
        if tab.get("pos") is not None
    ]


def _shape_text_run_hyperlink_address(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = _shape_text_run_properties(
        shape, paragraph_index, run_index, profile_aware=True
    )
    if run_properties is None:
        return None
    r_ns = ooxml_namespace(run_properties, R_NS)
    hyperlink = find_ooxml(run_properties, f"{{{A_NS}}}hlinkClick")
    if hyperlink is None:
        return None
    relationship_id = hyperlink.attrib.get(f"{{{r_ns}}}id")
    if not relationship_id:
        return None
    return _slide_relationship_target(
        shape._slide._presentation.path,
        shape._slide.partname,
        relationship_id,
        "/hyperlink",
    )


def _shape_text_paragraph_alignment(shape: Shape, paragraph_index: int) -> str | None:
    pending, alignment = _pending_paragraph_property(shape, paragraph_index, "alignment")
    if pending:
        return alignment
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
        paragraph = _paragraph_xml_element(shape_element, paragraph_index)
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return None
    paragraph_properties = find_ooxml(paragraph, f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return None
    return paragraph_properties.attrib.get("algn")


def _shape_text_paragraph_level(shape: Shape, paragraph_index: int) -> int:
    pending, level = _pending_paragraph_property(shape, paragraph_index, "level", 0)
    if pending:
        return level
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return 0
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
        paragraph = _paragraph_xml_element(shape_element, paragraph_index)
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return 0
    paragraph_properties = find_ooxml(paragraph, f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return 0
    raw = paragraph_properties.attrib.get("lvl")
    if raw in (None, ""):
        return 0
    try:
        return _coerce_paragraph_level(int(raw))
    except (TypeError, ValueError):
        return 0


def _shape_text_paragraph_spacing(
    shape: Shape,
    paragraph_index: int,
    attr: str,
) -> int | float | str | None:
    replaced, prefix, key = _paragraph_edit_source(shape, paragraph_index)
    spacing = getattr(shape._slide._presentation, f"{prefix}_paragraph_spacing_edits").get(key, {})
    if attr in spacing:
        return spacing[attr]
    if replaced:
        return None
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
        paragraph = _paragraph_xml_element(shape_element, paragraph_index)
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return None
    paragraph_properties = find_ooxml(paragraph, f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return None
    if attr == "font_alignment":
        return paragraph_properties.get("fontAlgn")
    paragraph_attribute = {
        "margin_left": "marL",
        "margin_right": "marR",
        "indent": "indent",
    }.get(attr)
    if paragraph_attribute is not None:
        raw = paragraph_properties.attrib.get(paragraph_attribute)
        try:
            return None if raw is None else int(raw)
        except ValueError:
            return None
    spacing = find_ooxml(paragraph_properties, f"{{{A_NS}}}{_paragraph_spacing_xml_tag(attr)}")
    if spacing is None:
        return None
    spacing_points = find_ooxml(spacing, f"{{{A_NS}}}spcPts")
    if spacing_points is not None:
        try:
            return _centipoints_to_emu(int(spacing_points.attrib["val"]))
        except (KeyError, ValueError):
            return None
    if attr == "line_spacing":
        spacing_percent = find_ooxml(spacing, f"{{{A_NS}}}spcPct")
        if spacing_percent is not None:
            try:
                return percentage_value(spacing_percent, spacing_percent.attrib["val"])
            except (KeyError, ValueError):
                return None
    return None


def _shape_text_run_rgb(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
    if run_properties is None:
        return None
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    if color is None:
        return None
    value = color.attrib.get("val")
    return value.upper() if value else None


def _shape_text_run_theme_color(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
    if run_properties is None:
        return None
    color = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}schemeClr")
    if color is None:
        return None
    return color.attrib.get("val") or None


def _shape_text_run_color(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> ET.Element | None:
    run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
    if run_properties is None:
        return None
    fills = [
        child
        for child in run_properties
        if child.tag
        in {
            f"{{{A_NS}}}{tag}"
            for tag in (
                "solidFill",
                "noFill",
                "gradFill",
                "pattFill",
                "blipFill",
                "grpFill",
            )
        }
    ]
    if not fills:
        return None
    if len(fills) != 1:
        raise ValueError("text color requires one unambiguous fill")
    fill = fills[0]
    if fill.tag != f"{{{A_NS}}}solidFill" or len(fill) == 0:
        return None
    if len(fill) != 1:
        raise ValueError("solid text fill requires exactly one color")
    color = fill[0]
    _validate_text_color_element(color)
    return color


def _shape_text_run_fill_type(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
    if run_properties is None:
        return None
    return _fill_type_from_xml_children(run_properties)


def _shape_text_run_pattern(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
    if run_properties is None:
        return None
    pattern_fill = run_properties.find(f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def _shape_text_run_pattern_rgb(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
    color_tag: str,
) -> str | None:
    run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
    if run_properties is None:
        return None
    return _fill_rgb_from_xml_children(run_properties, color_tag)


def _shape_text_run_gradient_payload(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> dict[str, Any] | None:
    run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
    if run_properties is None:
        return None
    return _gradient_payload_from_fill_parent(run_properties)


def _shape_text_run_properties(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
    *,
    profile_aware: bool = False,
) -> ET.Element | None:
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    if getattr(shape._slide, "_is_notes_slide", False):
        presentation = shape._slide._presentation
        key = (str(shape._slide.partname), shape._index, paragraph_index)
        if (
            key[:2] in presentation._part_shape_text_edits
            or key in presentation._part_paragraph_text_edits
            or key in presentation._part_paragraph_clear_edits
        ):
            return None
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
        if getattr(shape._slide, "_is_notes_slide", False):
            run_element = _part_text_run_xml_element(shape_element, paragraph_index, run_index)
        elif profile_aware:
            paragraph = _paragraph_xml_element(shape_element, paragraph_index)
            runs = findall_ooxml(paragraph, f"{{{A_NS}}}r")
            if run_index < 0 or run_index >= len(runs):
                return None
            run_element = runs[run_index]
        else:
            run_element = _text_run_xml_element(shape_element, paragraph_index, run_index)
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return None
    if profile_aware or getattr(shape._slide, "_is_notes_slide", False):
        return find_ooxml(run_element, f"{{{A_NS}}}rPr")
    return run_element.find(f"{{{A_NS}}}rPr")


def _shape_text_run_language_id(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    run_properties = _shape_text_run_properties(shape, paragraph_index, run_index)
    if run_properties is None:
        return None
    value = run_properties.attrib.get("lang")
    return value if value else None


def _shape_text_paragraph_default_run_properties(
    shape: Shape,
    paragraph_index: int,
) -> ET.Element | None:
    from .shape_xml import _set_paragraph_font_properties

    replaced, prefix, key = _paragraph_edit_source(shape, paragraph_index)
    font = getattr(shape._slide._presentation, f"{prefix}_paragraph_font_edits").get(key)
    properties = None
    if not replaced and shape._payload.get("kind") == "shape" and shape._slide.partname:
        try:
            root = _shape_text_part_root(shape)
            shape_element = _shape_xml_element(root, shape._payload)
            paragraph = _paragraph_xml_element(shape_element, paragraph_index)
            properties = find_ooxml(paragraph, f"{{{A_NS}}}pPr/{{{A_NS}}}defRPr")
        except (
            AttributeError,
            FileNotFoundError,
            IndexError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            pass
    if not font:
        return properties
    properties = ET.Element(f"{{{A_NS}}}defRPr") if properties is None else deepcopy(properties)
    _set_paragraph_font_properties(properties, font)
    return properties


def _shape_text_paragraph_font_bool(
    shape: Shape,
    paragraph_index: int,
    attr: str,
) -> bool | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    value = default_run_properties.attrib.get(attr)
    if value is None:
        return None
    return value not in {"0", "false", "False"}


def _shape_text_paragraph_font_underline(
    shape: Shape,
    paragraph_index: int,
) -> bool | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    value = default_run_properties.attrib.get("u")
    if value is None:
        return None
    return value != "none"


def _shape_text_paragraph_font_strike(
    shape: Shape,
    paragraph_index: int,
) -> bool | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    value = default_run_properties.attrib.get("strike")
    if value is None:
        return None
    return value != "noStrike"


def _shape_text_paragraph_font_size(
    shape: Shape,
    paragraph_index: int,
) -> int | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    value = default_run_properties.attrib.get("sz")
    if value is None:
        return None
    try:
        return _centipoints_to_emu(int(value))
    except ValueError:
        return None


def _shape_text_paragraph_font_name(
    shape: Shape,
    paragraph_index: int,
) -> str | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    latin = find_ooxml(default_run_properties, f"{{{A_NS}}}latin")
    if latin is None:
        return None
    return latin.attrib.get("typeface") or None


def _shape_text_paragraph_font_rgb(
    shape: Shape,
    paragraph_index: int,
) -> str | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    color = find_ooxml(default_run_properties, f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    if color is None:
        return None
    value = color.attrib.get("val")
    return value.upper() if value else None


def _shape_text_paragraph_font_pattern(
    shape: Shape,
    paragraph_index: int,
) -> str | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    pattern_fill = find_ooxml(default_run_properties, f"{{{A_NS}}}pattFill")
    return None if pattern_fill is None else pattern_fill.attrib.get("prst")


def _shape_text_paragraph_font_pattern_rgb(
    shape: Shape,
    paragraph_index: int,
    color_tag: str,
) -> str | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    return _fill_rgb_from_xml_children(default_run_properties, color_tag)


def _shape_text_paragraph_font_gradient_payload(
    shape: Shape,
    paragraph_index: int,
) -> dict[str, Any] | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    return _gradient_payload_from_fill_parent(default_run_properties)


def _shape_text_paragraph_font_theme_color(
    shape: Shape,
    paragraph_index: int,
) -> str | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    color = find_ooxml(default_run_properties, f"{{{A_NS}}}solidFill/{{{A_NS}}}schemeClr")
    if color is None:
        return None
    return color.attrib.get("val") or None


def _shape_text_paragraph_font_fill_type(
    shape: Shape,
    paragraph_index: int,
) -> str | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    return _fill_type_from_xml_children(default_run_properties)


def _shape_text_paragraph_font_language(
    shape: Shape,
    paragraph_index: int,
) -> str | None:
    default_run_properties = _shape_text_paragraph_default_run_properties(
        shape,
        paragraph_index,
    )
    if default_run_properties is None:
        return None
    value = default_run_properties.attrib.get("lang")
    return value if value else None


def _fill_type_from_xml_children(parent: ET.Element) -> str | None:
    a_ns = ooxml_namespace(parent, A_NS)
    for child in parent:
        if child.tag == f"{{{a_ns}}}solidFill":
            return "solid"
        if child.tag == f"{{{a_ns}}}noFill":
            return "background"
        if child.tag == f"{{{a_ns}}}pattFill":
            return "patterned"
        if child.tag == f"{{{a_ns}}}gradFill":
            return "gradient"
        if child.tag == f"{{{a_ns}}}blipFill":
            return "picture"
        if child.tag == f"{{{a_ns}}}grpFill":
            return "group"
    return None


def _shape_run_count_payload(payload: dict[str, Any]) -> int:
    raw_runs = payload.get("paragraph_runs")
    if raw_runs is None:
        return len(payload.get("paragraphs", []))
    return sum(len(paragraph) for paragraph in raw_runs)
