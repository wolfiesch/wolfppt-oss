"""Text, paragraph, and text-frame slide XML edit applicators."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .shape_xml import (
    RunHyperlinkAddress as RunHyperlinkAddress,  # re-exported for existing importers
)
from .shape_xml import (
    _run_properties_element,
    _set_hyperlink_address,
    _set_run_font_color,
    _set_run_font_fill_type,
    _set_run_font_language,
    _shape_xml_element,
    _text_run_xml_element,
)
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
)
from .slide_payloads import (
    load_slide_payloads as _load_slide_payloads,
)
from .text_xml import (
    _set_font_baseline,
    _set_font_bool_attribute,
    _set_font_caps,
    _set_font_highlight,
    _set_font_name,
    _set_font_size,
    _set_font_spacing,
    _set_font_strike,
    _set_font_underline,
    _set_portion_format,
)
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


#: Advanced run-edit keys that author DrawingML text effects on ``a:rPr``.
TEXT_EFFECT_RUN_ATTRS = ("text_outer_shadow", "text_glow", "text_fill_alpha")

# CT_TextCharacterProperties child order (ECMA-376 Part 1, 21.1.2.3.9).
_RUN_PROPERTY_ORDER = (
    "ln",
    "noFill",
    "solidFill",
    "gradFill",
    "blipFill",
    "pattFill",
    "grpFill",
    "effectLst",
    "effectDag",
    "highlight",
    "uLnTx",
    "uLn",
    "uFillTx",
    "uFill",
    "latin",
    "ea",
    "cs",
    "sym",
    "hlinkClick",
    "hlinkMouseOver",
    "rtl",
    "extLst",
)
# CT_EffectList child order (ECMA-376 Part 1, 20.1.8.26).
_EFFECT_LIST_ORDER = (
    "blur",
    "fillOverlay",
    "glow",
    "innerShdw",
    "outerShdw",
    "prstShdw",
    "reflection",
    "softEdge",
)


def insert_in_schema_order(parent: ET.Element, child: ET.Element, order: tuple[str, ...]) -> None:
    """Insert ``child`` before the first sibling the schema orders after it."""
    rank = order.index(_xml_local_name(child.tag))
    for index, sibling in enumerate(list(parent)):
        name = _xml_local_name(sibling.tag)
        if name in order and order.index(name) > rank:
            parent.insert(index, child)
            return
    parent.append(child)


def _effect_color(color: str, alpha: int) -> ET.Element:
    """Return ``srgbClr`` for six-digit RGB hex, ``schemeClr`` for a theme name."""
    is_rgb = len(color) == 6 and all(char in "0123456789ABCDEF" for char in color)
    element = ET.Element(f"{{{A_NS}}}{'srgbClr' if is_rgb else 'schemeClr'}", {"val": color})
    if alpha < 100000:
        ET.SubElement(element, f"{{{A_NS}}}alpha", {"val": str(alpha)})
    return element


def set_run_text_effect(properties: ET.Element, attr: str, value: Any) -> None:
    """Write one queued text effect onto a run's ``a:rPr``.

    ``text_outer_shadow`` and ``text_glow`` replace or remove one child of the
    run's ``a:effectLst`` and keep its other effects; a list emptied this way
    stays, so the run keeps drawing no inherited effect.  ``text_fill_alpha``
    sets the opacity (``a:alpha``, 0-100000) of the run's solid text colour;
    ``None`` makes it opaque again.
    """
    if attr == "text_fill_alpha":
        fill = properties.find(f"{{{A_NS}}}solidFill")
        color = None if fill is None or len(fill) == 0 else fill[0]
        if color is None:
            raise ValueError(
                "text transparency needs a solid text colour on the run; set font.color first"
            )
        for alpha in color.findall(f"{{{A_NS}}}alpha"):
            color.remove(alpha)
        if value is not None and value < 100000:
            ET.SubElement(color, f"{{{A_NS}}}alpha", {"val": str(value)})
        return
    if properties.find(f"{{{A_NS}}}effectDag") is not None:
        raise ValueError(
            "the run uses a text effect graph (a:effectDag), which text effect "
            "editing does not rewrite"
        )
    tag = "glow" if attr == "text_glow" else "outerShdw"
    effect_list = properties.find(f"{{{A_NS}}}effectLst")
    if effect_list is None:
        if value is None:
            return
        effect_list = ET.Element(f"{{{A_NS}}}effectLst")
        insert_in_schema_order(properties, effect_list, _RUN_PROPERTY_ORDER)
    for existing in effect_list.findall(f"{{{A_NS}}}{tag}"):
        effect_list.remove(existing)
    if value is None:
        return
    if tag == "glow":
        effect = ET.Element(f"{{{A_NS}}}glow", {"rad": str(value["radius"])})
    else:
        effect = ET.Element(
            f"{{{A_NS}}}outerShdw",
            {
                "blurRad": str(value["blur_radius"]),
                "dist": str(value["distance"]),
                "dir": str(value["direction"]),
                "algn": "tl",
                "rotWithShape": "0",
            },
        )
    effect.append(_effect_color(value["color"], value["alpha"]))
    insert_in_schema_order(effect_list, effect, _EFFECT_LIST_ORDER)


def _apply_text_run_font_color_edits(
    input_path: Path,
    output_path: Path,
    color_edits: list[tuple[tuple[int, int, int, int], Any]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, Any]]] = {}
    for (slide_index, shape_index, paragraph_index, run_index), color in color_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, run_index, color)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, run_index, color in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text run font color editing is only supported for shape elements"
                    )
                run_element = _text_run_xml_element(
                    shape_element,
                    paragraph_index,
                    run_index,
                )
                run_properties = _run_properties_element(run_element)
                _set_run_font_color(run_properties, color)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_text_run_font_fill_type_edits(
    input_path: Path,
    output_path: Path,
    fill_type_edits: list[tuple[tuple[int, int, int, int], Any]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, Any]]] = {}
    for (
        slide_index,
        shape_index,
        paragraph_index,
        run_index,
    ), fill_type in fill_type_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, run_index, fill_type)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, run_index, fill_type in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text run font fill editing is only supported for shape elements"
                    )
                run_element = _text_run_xml_element(
                    shape_element,
                    paragraph_index,
                    run_index,
                )
                run_properties = _run_properties_element(run_element)
                _set_run_font_fill_type(run_properties, fill_type)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_text_run_font_language_edits(
    input_path: Path,
    output_path: Path,
    language_edits: list[tuple[tuple[int, int, int, int], str | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, str | None]]] = {}
    for (slide_index, shape_index, paragraph_index, run_index), value in language_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, run_index, value)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, run_index, value in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text run font language editing is only supported for shape elements"
                    )
                run_element = _text_run_xml_element(
                    shape_element,
                    paragraph_index,
                    run_index,
                )
                run_properties = _run_properties_element(run_element)
                _set_run_font_language(run_properties, value)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_text_run_advanced_edits(
    input_path: Path,
    output_path: Path,
    font_edits: list[tuple[tuple[int, int, int, int], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, dict[str, Any]]]] = {}
    for (slide_index, shape_index, paragraph_index, run_index), edits in font_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, run_index, edits)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, paragraph_index, run_index, edits in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "advanced text run editing is only supported for shape elements"
                    )
                run_element = _text_run_xml_element(shape_element, paragraph_index, run_index)
                run_properties = _run_properties_element(run_element)
                if "baseline" in edits:
                    _set_font_baseline(run_properties, edits["baseline"])
                if "spacing" in edits:
                    _set_font_spacing(run_properties, edits["spacing"])
                if "small_caps" in edits:
                    _set_font_caps(
                        run_properties,
                        "small" if edits["small_caps"] else None,
                    )
                if "highlight_color" in edits:
                    _set_font_highlight(run_properties, edits["highlight_color"])
                if "portion" in edits:
                    _set_portion_format(run_properties, edits["portion"])
                for attr in TEXT_EFFECT_RUN_ATTRS:
                    if attr in edits:
                        set_run_text_effect(run_properties, attr, edits[attr])
            replacements[slide_part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_text_run_font_edits(
    input_path: Path,
    output_path: Path,
    font_edits: list[tuple[tuple[int, int, int, int, int], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, int, dict[str, Any]]]] = {}
    for key, edits in font_edits:
        slide_index, group_index, child_index, paragraph_index, run_index = key
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, paragraph_index, run_index, edits)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for (
                group_index,
                child_index,
                paragraph_index,
                run_index,
                edits,
            ) in slide_edits:
                try:
                    group_payload = slide_payload["shapes"][group_index]
                    child_payload = group_payload["children"][child_index]
                except IndexError as exc:
                    raise IndexError("group child index out of range") from exc
                shape_element = _shape_xml_element(root, child_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "group child text run font editing is only supported for shape elements"
                    )
                run_element = _text_run_xml_element(
                    shape_element,
                    paragraph_index,
                    run_index,
                )
                run_properties = _run_properties_element(run_element)
                if "bold" in edits:
                    _set_font_bool_attribute(run_properties, "b", edits["bold"])
                if "italic" in edits:
                    _set_font_bool_attribute(run_properties, "i", edits["italic"])
                if "underline" in edits:
                    _set_font_underline(run_properties, edits["underline"])
                if "strike" in edits:
                    _set_font_strike(run_properties, edits["strike"])
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
                if "baseline" in edits:
                    _set_font_baseline(run_properties, edits["baseline"])
                if "spacing" in edits:
                    _set_font_spacing(run_properties, edits["spacing"])
                if "small_caps" in edits:
                    _set_font_caps(run_properties, "small" if edits["small_caps"] else None)
                if "highlight_color" in edits:
                    _set_font_highlight(run_properties, edits["highlight_color"])
                if "portion" in edits:
                    _set_portion_format(run_properties, edits["portion"])
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_run_font_edits(
    input_path: Path,
    output_path: Path,
    font_edits: list[tuple[tuple[str, int, int, int], dict[str, Any]]],
) -> None:
    replacements: dict[str, bytes] = {}
    edits_by_part: dict[str, list[tuple[int, int, int, dict[str, Any]]]] = {}
    for key, edits in font_edits:
        partname, shape_index, paragraph_index, run_index = key
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, []).append(
            (shape_index, paragraph_index, run_index, edits)
        )
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            for shape_index, paragraph_index, run_index, edits in part_edits:
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "part text run font editing is only supported for shape elements"
                    )
                run_element = _text_run_xml_element(
                    shape_element,
                    paragraph_index,
                    run_index,
                )
                run_properties = _run_properties_element(run_element)
                if "bold" in edits:
                    _set_font_bool_attribute(run_properties, "b", edits["bold"])
                if "italic" in edits:
                    _set_font_bool_attribute(run_properties, "i", edits["italic"])
                if "underline" in edits:
                    _set_font_underline(run_properties, edits["underline"])
                if "strike" in edits:
                    _set_font_strike(run_properties, edits["strike"])
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
                if "baseline" in edits:
                    _set_font_baseline(run_properties, edits["baseline"])
                if "spacing" in edits:
                    _set_font_spacing(run_properties, edits["spacing"])
                if "small_caps" in edits:
                    _set_font_caps(run_properties, "small" if edits["small_caps"] else None)
                if "highlight_color" in edits:
                    _set_font_highlight(run_properties, edits["highlight_color"])
                if "portion" in edits:
                    _set_portion_format(run_properties, edits["portion"])
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_run_hyperlink_edits(
    input_path: Path,
    output_path: Path,
    hyperlink_edits: list[tuple[tuple[str, int, int, int], str | None]],
) -> None:
    replacements: dict[str, bytes] = {}
    edits_by_part: dict[str, list[tuple[int, int, int, str | None]]] = {}
    for key, address in hyperlink_edits:
        partname, shape_index, paragraph_index, run_index = key
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, []).append(
            (shape_index, paragraph_index, run_index, address)
        )
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            rels_part = _rels_part_for_package_part(partname)
            try:
                rels_root = ET.fromstring(package.read(rels_part))
            except KeyError:
                rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            for shape_index, paragraph_index, run_index, address in part_edits:
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "part text run hyperlink editing is only supported for shape elements"
                    )
                run_element = _text_run_xml_element(
                    shape_element,
                    paragraph_index,
                    run_index,
                )
                run_properties = _run_properties_element(run_element)
                _set_hyperlink_address(run_properties, rels_root, address)
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[rels_part] = ET.tostring(
                rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_text_run_hyperlink_edits(
    input_path: Path,
    output_path: Path,
    hyperlink_edits: list[tuple[tuple[int, int, int, int], str | None]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    slides = slide_payloads if slide_payloads is not None else _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, str | None]]] = {}
    for (
        slide_index,
        shape_index,
        paragraph_index,
        run_index,
    ), address in hyperlink_edits:
        edits_by_slide.setdefault(slide_index, []).append(
            (shape_index, paragraph_index, run_index, address)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            slide_root = ET.fromstring(package.read(slide_part))
            rels_part = _rels_part_for_package_part(slide_part)
            try:
                rels_root = ET.fromstring(package.read(rels_part))
            except KeyError:
                rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            for shape_index, paragraph_index, run_index, address in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(slide_root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text run hyperlink editing is only supported for shape elements"
                    )
                run_element = _text_run_xml_element(
                    shape_element,
                    paragraph_index,
                    run_index,
                )
                run_properties = _run_properties_element(run_element)
                # The shared writer applies a queued tooltip and color source.
                _set_hyperlink_address(run_properties, rels_root, address)
            replacements[slide_part] = ET.tostring(
                slide_root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[rels_part] = ET.tostring(
                rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_text_run_hyperlink_edits(
    input_path: Path,
    output_path: Path,
    hyperlink_edits: list[tuple[tuple[int, int, int, int, int], str | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, int, int, int, str | None]]] = {}
    for key, address in hyperlink_edits:
        slide_index, group_index, child_index, paragraph_index, run_index = key
        edits_by_slide.setdefault(slide_index, []).append(
            (group_index, child_index, paragraph_index, run_index, address)
        )
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            slide_root = ET.fromstring(package.read(slide_part))
            rels_part = _rels_part_for_package_part(slide_part)
            try:
                rels_root = ET.fromstring(package.read(rels_part))
            except KeyError:
                rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            for (
                group_index,
                child_index,
                paragraph_index,
                run_index,
                address,
            ) in slide_edits:
                try:
                    group_payload = slide_payload["shapes"][group_index]
                    child_payload = group_payload["children"][child_index]
                except IndexError as exc:
                    raise IndexError("group child index out of range") from exc
                shape_element = _shape_xml_element(slide_root, child_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "group child text run hyperlink editing is only supported for "
                        "shape elements"
                    )
                run_element = _text_run_xml_element(
                    shape_element,
                    paragraph_index,
                    run_index,
                )
                run_properties = _run_properties_element(run_element)
                _set_hyperlink_address(run_properties, rels_root, address)
            replacements[slide_part] = ET.tostring(
                slide_root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[rels_part] = ET.tostring(
                rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)
