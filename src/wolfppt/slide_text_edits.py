"""Compatibility exports for slide text XML edit applicators."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_open_package_with_replacements as _copy_open_package_with_replacements,
)
from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .shape_xml import (
    _clear_paragraph_content,
    _paragraph_default_run_properties_element,
    _paragraph_properties_element,
    _paragraph_xml_element,
    _part_paragraph_xml_element,
    _part_text_run_slots,
    _part_text_run_xml_element,
    _run_properties_element,
    _set_hyperlink_address,
    _set_paragraph_alignment,
    _set_paragraph_font_properties,
    _set_paragraph_level,
    _set_paragraph_spacing,
    _set_run_font_color,
    _set_run_font_fill_type,
    _set_run_font_language,
    _shape_xml_element,
)
from .slide_paragraph_edits import (
    _apply_group_child_paragraph_alignment_edits,
    _apply_group_child_paragraph_clear_edits,
    _apply_group_child_paragraph_font_edits,
    _apply_group_child_paragraph_level_edits,
    _apply_group_child_paragraph_line_break_edits,
    _apply_group_child_paragraph_spacing_edits,
    _apply_group_child_paragraph_tab_stop_edits,
    _apply_paragraph_alignment_edits,
    _apply_paragraph_clear_edits,
    _apply_paragraph_font_edits,
    _apply_paragraph_level_edits,
    _apply_paragraph_line_break_edits,
    _apply_paragraph_property_edits,
    _apply_paragraph_spacing_edits,
    _apply_paragraph_tab_stop_edits,
    _apply_part_paragraph_font_edits,
    _apply_part_paragraph_property_edits,
    _apply_part_paragraph_tab_stop_edits,
)
from .slide_payloads import load_shape_payloads as _load_shape_payloads
from .slide_text_frame_edits import (
    _apply_group_child_text_frame_advanced_edits,
    _apply_group_child_text_frame_auto_size_edits,
    _apply_group_child_text_frame_fit_edits,
    _apply_group_child_text_frame_margin_edits,
    _apply_group_child_text_frame_vertical_anchor_edits,
    _apply_group_child_text_frame_word_wrap_edits,
    _apply_part_text_frame_advanced_edits,
    _apply_part_text_frame_auto_size_edits,
    _apply_part_text_frame_edits,
    _apply_part_text_frame_margin_edits,
    _apply_part_text_frame_vertical_anchor_edits,
    _apply_part_text_frame_word_wrap_edits,
    _apply_text_frame_advanced_edits,
    _apply_text_frame_auto_size_edits,
    _apply_text_frame_fit_edits,
    _apply_text_frame_margin_edits,
    _apply_text_frame_vertical_anchor_edits,
    _apply_text_frame_word_wrap_edits,
)
from .slide_text_run_edits import (
    _apply_group_child_text_run_font_edits,
    _apply_group_child_text_run_hyperlink_edits,
    _apply_part_text_run_font_edits,
    _apply_part_text_run_hyperlink_edits,
    _apply_text_run_advanced_edits,
    _apply_text_run_font_color_edits,
    _apply_text_run_font_fill_type_edits,
    _apply_text_run_font_language_edits,
    _apply_text_run_hyperlink_edits,
)
from .slide_text_shape_edits import (
    _append_paragraph_text,
    _apply_nested_group_child_shape_text_edits,
    _apply_part_shape_text_edits,
    _part_shape_text_replacements,
    _part_shape_text_replacements_from_package,
    _set_shape_text,
)
from .text_xml import (
    _set_font_bool_attribute,
    _set_font_name,
    _set_font_size,
    _set_font_underline,
)
from .xml_helpers import A_NS, R_NS, find_ooxml, ooxml_namespace
from .xml_helpers import xml_local_name as _xml_local_name

PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _set_part_run_text(
    shape_element: ET.Element, paragraph_index: int, run_index: int, value: str
) -> None:
    """Address the part reader's ordered, empty-inclusive r/fld slots."""
    paragraph = _part_paragraph_xml_element(shape_element, paragraph_index)
    runs = _part_text_run_slots(paragraph)
    if run_index < 0 or run_index > len(runs):
        raise IndexError("run index out of range")
    if run_index == len(runs):
        run = ET.Element(f"{{{ooxml_namespace(paragraph, A_NS)}}}r")
        trailing = find_ooxml(paragraph, f"{{{A_NS}}}endParaRPr")
        paragraph.insert(
            len(paragraph) if trailing is None else list(paragraph).index(trailing),
            run,
        )
    else:
        run = runs[run_index]
    text = find_ooxml(run, f"{{{A_NS}}}t")
    if text is None:
        text = ET.SubElement(run, f"{{{ooxml_namespace(run, A_NS)}}}t")
    text.text = value


def _insert_part_paragraph_line_break(paragraph: ET.Element, run_slot: int) -> None:
    runs = _part_text_run_slots(paragraph)
    if run_slot < 0 or run_slot > len(runs):
        raise IndexError("run slot out of range")
    following = (
        runs[run_slot]
        if run_slot < len(runs)
        else find_ooxml(paragraph, f"{{{A_NS}}}endParaRPr")
    )
    insert_at = len(paragraph) if following is None else list(paragraph).index(following)
    paragraph.insert(
        insert_at, ET.Element(f"{{{ooxml_namespace(paragraph, A_NS)}}}br")
    )


def _apply_part_text_edits(
    input_path: Path,
    output_path: Path,
    shape_text_edits: list[tuple[tuple[str, int], str]],
    paragraph_text_edits: list[tuple[tuple[str, int, int], str]],
    paragraph_clear_edits: list[tuple[str, int, int]],
    paragraph_line_break_edits: list[tuple[str, int, int, int]],
    run_text_edits: list[tuple[tuple[str, int, int, int], str]],
    run_font_edits: list[tuple[tuple[str, int, int, int], dict[str, Any]]],
    run_hyperlink_edits: list[tuple[tuple[str, int, int, int], str | None]],
    paragraph_font_edits: list[tuple[tuple[str, int, int], dict[str, Any]]],
    paragraph_alignment_edits: list[tuple[tuple[str, int, int], str | None]],
    paragraph_level_edits: list[tuple[tuple[str, int, int], int]],
    paragraph_spacing_edits: list[
        tuple[tuple[str, int, int], dict[str, int | float | None]]
    ],
) -> None:
    edits_by_part: dict[str, dict[int, dict[str, Any]]] = {}
    for (partname, shape_index), text in shape_text_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})["text"] = (
            text
        )
    for (partname, shape_index, paragraph_index), text in paragraph_text_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "paragraph_texts", []
        ).append((paragraph_index, text))
    for partname, shape_index, paragraph_index in paragraph_clear_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "paragraph_clears", []
        ).append(paragraph_index)
    for partname, shape_index, paragraph_index, run_slot in paragraph_line_break_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "paragraph_line_breaks", []
        ).append((paragraph_index, run_slot))
    for (partname, shape_index, paragraph_index, run_index), text in run_text_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "run_texts",
            [],
        ).append((paragraph_index, run_index, text))
    for (partname, shape_index, paragraph_index, run_index), edits in run_font_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "run_fonts",
            [],
        ).append((paragraph_index, run_index, edits))
    for (
        partname,
        shape_index,
        paragraph_index,
        run_index,
    ), address in run_hyperlink_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "run_hyperlinks",
            [],
        ).append((paragraph_index, run_index, address))
    for (partname, shape_index, paragraph_index), edits in paragraph_font_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "paragraph_fonts",
            [],
        ).append((paragraph_index, edits))
    for (
        partname,
        shape_index,
        paragraph_index,
    ), alignment in paragraph_alignment_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "paragraph_properties",
            {},
        ).setdefault(paragraph_index, {})["alignment"] = alignment
    for (partname, shape_index, paragraph_index), level in paragraph_level_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "paragraph_properties",
            {},
        ).setdefault(paragraph_index, {})["level"] = level
    for (partname, shape_index, paragraph_index), spacing in paragraph_spacing_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {}).setdefault(
            "paragraph_properties",
            {},
        ).setdefault(paragraph_index, {})["spacing"] = spacing

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            rels_part: str | None = None
            rels_root: ET.Element | None = None
            if any(
                shape_edits.get("run_hyperlinks") for shape_edits in part_edits.values()
            ):
                rels_part = _rels_part_for_package_part(partname)
                try:
                    rels_root = ET.fromstring(package.read(rels_part))
                except KeyError:
                    rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            for shape_index, shape_edits in part_edits.items():
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if "text" in shape_edits:
                    if _xml_local_name(shape_element.tag) != "sp":
                        raise AttributeError(
                            "shape text editing is only supported for shape elements"
                        )
                    _set_shape_text(shape_element, shape_edits["text"])
                for paragraph_index, text in shape_edits.get("paragraph_texts", []):
                    paragraph = _part_paragraph_xml_element(
                        shape_element, paragraph_index, allow_append=True
                    )
                    _clear_paragraph_content(paragraph)
                    _append_paragraph_text(paragraph, text)
                for paragraph_index in shape_edits.get("paragraph_clears", []):
                    _clear_paragraph_content(
                        _part_paragraph_xml_element(shape_element, paragraph_index)
                    )
                for paragraph_index, run_index, text in shape_edits.get(
                    "run_texts", []
                ):
                    if _xml_local_name(shape_element.tag) != "sp":
                        raise AttributeError(
                            "part text run editing is only supported for shape elements"
                        )
                    _set_part_run_text(
                        shape_element, paragraph_index, run_index, text
                    )
                for paragraph_index, run_index, edits in shape_edits.get(
                    "run_fonts",
                    [],
                ):
                    if _xml_local_name(shape_element.tag) != "sp":
                        raise AttributeError(
                            "part text run font editing is only supported for shape elements"
                        )
                    run_element = _part_text_run_xml_element(
                        shape_element,
                        paragraph_index,
                        run_index,
                    )
                    run_properties = _run_properties_element(run_element, part_scoped=True)
                    if "bold" in edits:
                        _set_font_bool_attribute(run_properties, "b", edits["bold"])
                    if "italic" in edits:
                        _set_font_bool_attribute(run_properties, "i", edits["italic"])
                    if "underline" in edits:
                        _set_font_underline(run_properties, edits["underline"])
                    if "size" in edits:
                        _set_font_size(run_properties, edits["size"])
                    if "name" in edits:
                        _set_font_name(run_properties, edits["name"])
                    if "color" in edits:
                        _set_run_font_color(run_properties, edits["color"])
                    if "fill_type" in edits:
                        _set_run_font_fill_type(run_properties, edits["fill_type"])
                    if "language_id" in edits:
                        _set_run_font_language(run_properties, edits["language_id"])
                for paragraph_index, run_index, address in shape_edits.get(
                    "run_hyperlinks",
                    [],
                ):
                    if _xml_local_name(shape_element.tag) != "sp":
                        raise AttributeError(
                            "part text run hyperlink editing is only supported for shape elements"
                        )
                    assert rels_root is not None
                    run_element = _part_text_run_xml_element(
                        shape_element,
                        paragraph_index,
                        run_index,
                    )
                    _set_hyperlink_address(
                        _run_properties_element(run_element, part_scoped=True),
                        rels_root,
                        address,
                        relationship_type=f"{ooxml_namespace(run_element, R_NS)}/hyperlink",
                        part_root=root,
                    )
                for paragraph_index, run_slot in shape_edits.get(
                    "paragraph_line_breaks", []
                ):
                    _insert_part_paragraph_line_break(
                        _part_paragraph_xml_element(shape_element, paragraph_index),
                        run_slot,
                    )
                for paragraph_index, edits in shape_edits.get("paragraph_fonts", []):
                    if _xml_local_name(shape_element.tag) != "sp":
                        raise AttributeError(
                            "part paragraph font editing is only supported for shape elements"
                        )
                    paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                    default_run_properties = _paragraph_default_run_properties_element(
                        paragraph
                    )
                    _set_paragraph_font_properties(default_run_properties, edits)
                for paragraph_index, edits in shape_edits.get(
                    "paragraph_properties",
                    {},
                ).items():
                    if _xml_local_name(shape_element.tag) != "sp":
                        raise AttributeError(
                            "paragraph property editing is only supported for shape elements"
                        )
                    paragraph = _paragraph_xml_element(shape_element, paragraph_index)
                    paragraph_properties = _paragraph_properties_element(paragraph)
                    if "alignment" in edits:
                        _set_paragraph_alignment(
                            paragraph_properties,
                            edits["alignment"],
                        )
                    if "level" in edits:
                        _set_paragraph_level(paragraph_properties, edits["level"])
                    if "spacing" in edits:
                        _set_paragraph_spacing(paragraph_properties, edits["spacing"])
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
            if rels_root is not None:
                assert rels_part is not None
                replacements[rels_part] = ET.tostring(
                    rels_root,
                    encoding="utf-8",
                    xml_declaration=True,
                )
        _copy_open_package_with_replacements(package, output_path, replacements)


__all__ = [
    "_apply_group_child_paragraph_alignment_edits",
    "_apply_group_child_paragraph_clear_edits",
    "_apply_group_child_paragraph_font_edits",
    "_apply_group_child_paragraph_level_edits",
    "_apply_group_child_paragraph_line_break_edits",
    "_apply_group_child_paragraph_spacing_edits",
    "_apply_group_child_paragraph_tab_stop_edits",
    "_apply_group_child_text_frame_advanced_edits",
    "_apply_group_child_text_frame_auto_size_edits",
    "_apply_group_child_text_frame_fit_edits",
    "_apply_group_child_text_frame_margin_edits",
    "_apply_group_child_text_frame_vertical_anchor_edits",
    "_apply_group_child_text_frame_word_wrap_edits",
    "_apply_group_child_text_run_font_edits",
    "_apply_group_child_text_run_hyperlink_edits",
    "_apply_nested_group_child_shape_text_edits",
    "_apply_paragraph_alignment_edits",
    "_apply_paragraph_clear_edits",
    "_apply_paragraph_font_edits",
    "_apply_paragraph_level_edits",
    "_apply_paragraph_line_break_edits",
    "_apply_paragraph_property_edits",
    "_apply_paragraph_spacing_edits",
    "_apply_paragraph_tab_stop_edits",
    "_apply_part_paragraph_font_edits",
    "_apply_part_paragraph_property_edits",
    "_apply_part_paragraph_tab_stop_edits",
    "_apply_part_shape_text_edits",
    "_apply_part_text_edits",
    "_apply_part_text_frame_advanced_edits",
    "_apply_part_text_frame_auto_size_edits",
    "_apply_part_text_frame_edits",
    "_apply_part_text_frame_margin_edits",
    "_apply_part_text_frame_vertical_anchor_edits",
    "_apply_part_text_frame_word_wrap_edits",
    "_apply_part_text_run_font_edits",
    "_apply_part_text_run_hyperlink_edits",
    "_apply_text_frame_advanced_edits",
    "_apply_text_frame_auto_size_edits",
    "_apply_text_frame_fit_edits",
    "_apply_text_frame_margin_edits",
    "_apply_text_frame_vertical_anchor_edits",
    "_apply_text_frame_word_wrap_edits",
    "_apply_text_run_advanced_edits",
    "_apply_text_run_font_color_edits",
    "_apply_text_run_font_fill_type_edits",
    "_apply_text_run_font_language_edits",
    "_apply_text_run_hyperlink_edits",
    "_part_shape_text_replacements",
    "_part_shape_text_replacements_from_package",
    "_set_shape_text",
]
