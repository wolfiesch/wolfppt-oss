"""XML readers for text paragraph and run facade state."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    fill_rgb_from_xml_children as _fill_rgb_from_xml_children,
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)
from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
    coerce_paragraph_level as _coerce_paragraph_level,
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
)
from .shape_xml import (
    _paragraph_xml_element,
    _shape_xml_element,
    _text_run_xml_element,
)
from .slide_relationships import slide_relationship_target as _slide_relationship_target

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



def _shape_text_run_hyperlink_address(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    if shape._payload.get("kind") != "shape":
        return None
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
        run_element = _text_run_xml_element(
            shape_element,
            paragraph_index,
            run_index,
        )
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return None
    run_properties = run_element.find(f"{{{A_NS}}}rPr")
    if run_properties is None:
        return None
    hyperlink = run_properties.find(f"{{{A_NS}}}hlinkClick")
    if hyperlink is None:
        return None
    relationship_id = hyperlink.attrib.get(f"{{{R_NS}}}id")
    if not relationship_id:
        return None
    return _slide_relationship_target(
        shape._slide._presentation.path,
        shape._slide.partname,
        relationship_id,
        "/hyperlink",
    )


def _shape_text_paragraph_alignment(shape: Shape, paragraph_index: int) -> str | None:
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
    paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return None
    return paragraph_properties.attrib.get("algn")


def _shape_text_paragraph_level(shape: Shape, paragraph_index: int) -> int:
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
    paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
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
) -> int | float | None:
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
    paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return None
    spacing = paragraph_properties.find(f"{{{A_NS}}}{_paragraph_spacing_xml_tag(attr)}")
    if spacing is None:
        return None
    spacing_points = spacing.find(f"{{{A_NS}}}spcPts")
    if spacing_points is not None:
        try:
            return _centipoints_to_emu(int(spacing_points.attrib["val"]))
        except (KeyError, ValueError):
            return None
    if attr == "line_spacing":
        spacing_percent = spacing.find(f"{{{A_NS}}}spcPct")
        if spacing_percent is not None:
            try:
                return int(spacing_percent.attrib["val"]) / 100000
            except (KeyError, ValueError):
                return None
    return None


def _shape_text_run_rgb(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
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
    run_properties = run_element.find(f"{{{A_NS}}}rPr")
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


def _shape_text_run_fill_type(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
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
    run_properties = run_element.find(f"{{{A_NS}}}rPr")
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
) -> ET.Element | None:
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
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
    return run_element.find(f"{{{A_NS}}}rPr")


def _shape_text_run_language_id(
    shape: Shape,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    if shape._payload.get("kind") != "shape" or not shape._slide.partname:
        return None
    try:
        root = _shape_text_part_root(shape)
        shape_element = _shape_xml_element(root, shape._payload)
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
    run_properties = run_element.find(f"{{{A_NS}}}rPr")
    if run_properties is None:
        return None
    value = run_properties.attrib.get("lang")
    return value if value else None


def _shape_text_paragraph_default_run_properties(
    shape: Shape,
    paragraph_index: int,
) -> ET.Element | None:
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
    paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return None
    return paragraph_properties.find(f"{{{A_NS}}}defRPr")


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
    latin = default_run_properties.find(f"{{{A_NS}}}latin")
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
    color = default_run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
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
    pattern_fill = default_run_properties.find(f"{{{A_NS}}}pattFill")
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
    color = default_run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}schemeClr")
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
    for child in parent:
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


def _shape_run_count_payload(payload: dict[str, Any]) -> int:
    raw_runs = payload.get("paragraph_runs")
    if raw_runs is None:
        return len(payload.get("paragraphs", []))
    return sum(len(paragraph) for paragraph in raw_runs)
