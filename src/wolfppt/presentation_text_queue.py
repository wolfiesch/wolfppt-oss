"""Apply grouped text operations through the shared shape-reference save path.

Queue keys retain the parent ShapeEditRef plus the immediate child index. Save
lowers those paths on its snapshot; this module only invokes the existing
DrawingML mutation helpers, never serializes a replacement rich-text payload.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .shape_xml import (
    _clear_paragraph_content,
    _insert_paragraph_line_break,
    _paragraph_default_run_properties_element,
    _paragraph_properties_element,
    _paragraph_xml_element,
    _run_properties_element,
    _set_hyperlink_address,
    _set_paragraph_alignment,
    _set_paragraph_bullet,
    _set_paragraph_font_properties,
    _set_paragraph_level,
    _set_paragraph_spacing,
    _set_text_frame_fit,
    _text_body_properties_element,
    _text_run_xml_element,
)
from .slide_text_frame_edits import _apply_text_frame_advanced_to_body
from .slide_text_shape_edits import _append_paragraph_text
from .text_xml import (
    _add_paragraph_tab_stop,
    _apply_text_body_auto_size,
    _set_font_baseline,
    _set_font_caps,
    _set_font_highlight,
    _set_font_spacing,
    _set_portion_format,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"

GROUP_TEXT_XML_FIELDS = (
    "group_child_paragraph_text_edits",
    "group_child_run_text_edits",
    "group_child_run_font_edits",
    "group_child_run_hyperlink_edits",
    "group_child_paragraph_alignment_edits",
    "group_child_paragraph_level_edits",
    "group_child_paragraph_spacing_edits",
    "group_child_paragraph_font_edits",
    "group_child_paragraph_bullet_edits",
    "group_child_paragraph_tab_stop_edits",
    "group_child_text_frame_margin_edits",
    "group_child_text_frame_word_wrap_edits",
    "group_child_text_frame_vertical_anchor_edits",
    "group_child_text_frame_auto_size_edits",
    "group_child_text_frame_fit_edits",
    "group_child_text_frame_advanced_edits",
)


def clear_group_text_edits(
    presentation: Any,
    slide_index: int,
    group_index: int,
    child_path: tuple[int, ...],
) -> None:
    """Discard rich-text edits superseded by a whole-shape replacement."""
    if len(child_path) == 1:
        slide = next(
            slide for slide in presentation.slides if slide._index == slide_index
        )
        groups = [
            shape for shape in slide.shapes if shape._payload.get("kind") == "group"
        ]
        parent = (groups[group_index]._index,)
    else:
        parent = (group_index, *child_path[:-1])
    prefix = (slide_index, parent, child_path[-1])
    for field in GROUP_TEXT_XML_FIELDS:
        if not field.startswith(("group_child_paragraph_", "group_child_run_")):
            continue
        pending = getattr(presentation, f"_{field}")
        for key in list(pending):
            if key[:3] == prefix:
                del pending[key]
    for field in (
        "_group_child_paragraph_clear_edits",
        "_group_child_paragraph_line_break_edits",
    ):
        pending = getattr(presentation, field)
        pending.difference_update(key for key in tuple(pending) if key[:3] == prefix)


def apply_group_text_operation(
    shape_element: ET.Element,
    operation: str,
    indices: tuple[int, ...],
    value: Any,
    rels_root: ET.Element | None,
) -> None:
    if operation in {"paragraph_text", "paragraph_replace"}:
        body = shape_element.find(f"{{{P_NS}}}txBody")
        if body is None:
            raise AttributeError("shape text body is unavailable")
        paragraphs = body.findall(f"{{{A_NS}}}p")
        index = indices[0]
        if index == len(paragraphs):
            paragraph = ET.Element(f"{{{A_NS}}}p")
            insert_at = (
                list(body).index(paragraphs[-1]) + 1 if paragraphs else len(body)
            )
            body.insert(insert_at, paragraph)
            _append_paragraph_text(paragraph, value)
        else:
            paragraph = _paragraph_xml_element(shape_element, index)
            if operation == "paragraph_replace":
                _clear_paragraph_content(paragraph)
                _append_paragraph_text(paragraph, value)
                return
            texts = list(paragraph.iter(f"{{{A_NS}}}t"))
            if texts:
                # Match grouped replacement semantics without rebuilding rPr/pPr.
                texts[0].text = value
                for text in texts[1:]:
                    text.text = ""
            else:
                _append_paragraph_text(paragraph, value)
        return
    if operation == "run_text":
        paragraph_index, run_index = indices
        paragraph = _paragraph_xml_element(shape_element, paragraph_index)
        runs = paragraph.findall(f"{{{A_NS}}}r")
        if run_index == len(runs):
            run = ET.Element(f"{{{A_NS}}}r")
            trailing = paragraph.find(f"{{{A_NS}}}endParaRPr")
            paragraph.insert(
                len(paragraph) if trailing is None else list(paragraph).index(trailing),
                run,
            )
        else:
            run = _text_run_xml_element(shape_element, paragraph_index, run_index)
        text = run.find(f"{{{A_NS}}}t")
        if text is None:
            text = ET.SubElement(run, f"{{{A_NS}}}t")
        text.text = value
        return
    if operation.startswith("run_"):
        run = _text_run_xml_element(shape_element, *indices)
        properties = _run_properties_element(run)
        if operation == "run_hyperlink":
            assert rels_root is not None
            _set_hyperlink_address(properties, rels_root, value)
            return
        if operation != "run_font":
            raise ValueError(f"unknown grouped text operation: {operation}")
        _set_paragraph_font_properties(properties, value)
        if "baseline" in value:
            _set_font_baseline(properties, value["baseline"])
        if "spacing" in value:
            _set_font_spacing(properties, value["spacing"])
        if "small_caps" in value:
            _set_font_caps(properties, "small" if value["small_caps"] else None)
        if "highlight_color" in value:
            _set_font_highlight(properties, value["highlight_color"])
        if "portion" in value:
            _set_portion_format(properties, value["portion"])
        return
    if operation.startswith("paragraph_"):
        paragraph = _paragraph_xml_element(shape_element, indices[0])
        if operation == "paragraph_clear":
            _clear_paragraph_content(paragraph)
        elif operation == "paragraph_line_break":
            _insert_paragraph_line_break(paragraph, indices[1])
        elif operation == "paragraph_font":
            _set_paragraph_font_properties(
                _paragraph_default_run_properties_element(paragraph), value
            )
        else:
            properties = _paragraph_properties_element(paragraph)
            if operation == "paragraph_alignment":
                _set_paragraph_alignment(properties, value)
            elif operation == "paragraph_level":
                _set_paragraph_level(properties, value)
            elif operation == "paragraph_spacing":
                _set_paragraph_spacing(properties, value)
            elif operation == "paragraph_bullet":
                _set_paragraph_bullet(properties, value)
            elif operation == "paragraph_tab_stop":
                tabs = properties.find(f"{{{A_NS}}}tabLst")
                if tabs is not None:
                    properties.remove(tabs)
                for stop in value:
                    _add_paragraph_tab_stop(
                        properties, stop["pos"], stop.get("align", "l")
                    )
            else:
                raise ValueError(f"unknown grouped text operation: {operation}")
        return
    body = _text_body_properties_element(shape_element)
    if operation == "text_frame_margin":
        for attribute, margin in value.items():
            if margin is None:
                body.attrib.pop(attribute, None)
            else:
                body.set(attribute, str(margin))
    elif operation == "text_frame_word_wrap":
        if value is None:
            body.attrib.pop("wrap", None)
        else:
            body.set("wrap", "square" if value else "none")
    elif operation == "text_frame_vertical_anchor":
        if value is None:
            body.attrib.pop("anchor", None)
        else:
            body.set("anchor", value)
    elif operation == "text_frame_auto_size":
        mode, scale = value if isinstance(value, tuple) else (value, None)
        _apply_text_body_auto_size(body, mode, scale)
    elif operation == "text_frame_fit":
        _set_text_frame_fit(shape_element, value)
    elif operation == "text_frame_advanced":
        _apply_text_frame_advanced_to_body(body, value)
    else:
        raise ValueError(f"unknown grouped text operation: {operation}")
