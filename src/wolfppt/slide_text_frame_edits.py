"""Text, paragraph, and text-frame slide XML edit applicators."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .math_text import apply_shape_equations
from .package_parts import (
    copy_open_package_with_replacements as _copy_open_package_with_replacements,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .shape_3d_format import _rotation_attributes, _scaled
from .shape_xml import (
    _set_text_frame_fit,
    _shape_xml_element,
    _text_body_properties_element,
)
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
)
from .slide_payloads import (
    load_slide_payloads as _load_slide_payloads,
)
from .text_xml import (
    _apply_text_body_auto_size,
    _set_text_body_columns,
    _set_text_body_overflow,
    _set_text_body_vertical,
)
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _register_namespaces() -> None:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)


def _apply_text_frame_advanced_to_body(body_properties: ET.Element, edits: dict[str, Any]) -> None:
    if "vertical" in edits:
        _set_text_body_vertical(body_properties, edits["vertical"])
    if "column_count" in edits or "column_spacing" in edits:
        _set_text_body_columns(
            body_properties,
            edits.get("column_count"),
            edits.get("column_spacing"),
        )
    if "text_3d" in edits:
        set_text_body_3d(body_properties, edits["text_3d"])
    if "overflow" in edits:
        _set_text_body_overflow(body_properties, edits["overflow"])


# CT_TextBodyProperties child order (ECMA-376 Part 1, 21.1.2.1.1).
_BODY_PROPERTY_ORDER = (
    "prstTxWarp",
    "noAutofit",
    "normAutofit",
    "spAutoFit",
    "scene3d",
    "sp3d",
    "flatTx",
    "extLst",
)


def set_text_body_3d(body_properties: ET.Element, value: dict[str, Any] | None) -> None:
    """Write or remove the 3-D text format of a text body.

    DrawingML keeps 3-D text on ``a:bodyPr`` (``a:scene3d`` camera and light
    rig, ``a:sp3d`` bevel, depth and material), so it applies to the whole
    body; ``None`` removes both, together with any ``a:flatTx``.
    """
    if value is None:
        for name in ("scene3d", "sp3d", "flatTx"):
            for existing in body_properties.findall(f"{{{A_NS}}}{name}"):
                body_properties.remove(existing)
        return
    scene = ET.Element(f"{{{A_NS}}}scene3d")
    camera = ET.SubElement(scene, f"{{{A_NS}}}camera", {"prst": value["camera"]})
    fov = _scaled("camera_field_of_view", 60000, 180)(value.get("camera_field_of_view"))
    if fov is not None:
        camera.set("fov", fov)
    light = ET.SubElement(
        scene,
        f"{{{A_NS}}}lightRig",
        {"rig": value["lighting"], "dir": value.get("lighting_direction", "t")},
    )
    for node, key in ((camera, "camera_rotation"), (light, "lighting_rotation")):
        attributes = _rotation_attributes(value.get(key))
        if attributes is not None:
            ET.SubElement(node, f"{{{A_NS}}}rot", attributes)
    shape_3d = ET.Element(f"{{{A_NS}}}sp3d")
    if value["extrusion_height"]:
        shape_3d.set("extrusionH", str(value["extrusion_height"]))
    shape_3d.set("prstMaterial", value["material"])
    if value["bevel"] is not None:
        ET.SubElement(
            shape_3d,
            f"{{{A_NS}}}bevelT",
            {
                "w": str(value["bevel_width"]),
                "h": str(value["bevel_height"]),
                "prst": value["bevel"],
            },
        )
    if value.get("bottom_bevel") is not None:
        ET.SubElement(
            shape_3d,
            f"{{{A_NS}}}bevelB",
            {
                "w": str(value.get("bottom_bevel_width", 76200)),
                "h": str(value.get("bottom_bevel_height", 76200)),
                "prst": value["bottom_bevel"],
            },
        )
    if value["extrusion_color"] is not None:
        color = ET.SubElement(shape_3d, f"{{{A_NS}}}extrusionClr")
        ET.SubElement(color, f"{{{A_NS}}}srgbClr", {"val": value["extrusion_color"]})
    for name in ("scene3d", "sp3d", "flatTx"):
        for existing in body_properties.findall(f"{{{A_NS}}}{name}"):
            body_properties.remove(existing)
    for element in (scene, shape_3d):
        rank = _BODY_PROPERTY_ORDER.index(_xml_local_name(element.tag))
        for index, sibling in enumerate(list(body_properties)):
            name = _xml_local_name(sibling.tag)
            if name in _BODY_PROPERTY_ORDER and _BODY_PROPERTY_ORDER.index(name) > rank:
                body_properties.insert(index, element)
                break
        else:
            body_properties.append(element)


def _set_text_frame_margins(body_properties: ET.Element, margins: dict[str, int | None]) -> None:
    for attr, value in margins.items():
        if value is None:
            body_properties.attrib.pop(attr, None)
        else:
            body_properties.set(attr, str(value))


def _apply_text_frame_advanced_edits(
    input_path: Path,
    output_path: Path,
    frame_edits: list[tuple[tuple[int, int], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index), edits in frame_edits:
            try:
                slide_payload = slides[slide_index]
                shape_payload = slide_payload["shapes"][shape_index]
            except IndexError as exc:
                raise IndexError("slide or shape index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = (
                ET.fromstring(replacements[slide_part])
                if slide_part in replacements
                else ET.fromstring(package.read(slide_part))
            )
            shape_element = _shape_xml_element(root, shape_payload)
            if _xml_local_name(shape_element.tag) != "sp":
                raise AttributeError(
                    "advanced text frame editing is only supported for shape elements"
                )
            _apply_text_frame_advanced_to_body(_text_body_properties_element(shape_element), edits)
            if "equations" in edits:
                apply_shape_equations(root, shape_element, edits["equations"])
            _register_namespaces()
            replacements[slide_part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_advanced_edits(
    input_path: Path,
    output_path: Path,
    frame_edits: list[tuple[tuple[str, int], dict[str, Any]]],
) -> None:
    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=frame_edits,
        apply_edit=_apply_text_frame_advanced_to_body,
        feature="advanced text frame editing",
    )


def _apply_group_child_text_frame_advanced_edits(
    input_path: Path,
    output_path: Path,
    frame_edits: list[tuple[tuple[int, int, int], dict[str, Any]]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, dict[str, Any]]]] = {}
    for (slide_index, group_index, child_index), edits in frame_edits:
        edits_by_slide.setdefault(slide_index, []).append((group_index, child_index, edits))
    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=_apply_text_frame_advanced_to_body,
        feature="advanced text frame editing",
    )


def _apply_text_frame_margin_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[int, int], dict[str, int | None]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, dict[str, int | None]]]] = {}
    for (slide_index, shape_index), margins in margin_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, margins))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, margins in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text frame margin editing is only supported for shape elements"
                    )
                _set_text_frame_margins(_text_body_properties_element(shape_element), margins)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_margin_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[str, int], dict[str, int | None]]],
) -> None:
    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=margin_edits,
        apply_edit=_set_text_frame_margins,
        feature="text frame margin editing",
    )


def _apply_group_child_text_frame_margin_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[int, int, int], dict[str, int | None]]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, dict[str, int | None]]]] = {}
    for (slide_index, group_index, child_index), margins in margin_edits:
        edits_by_slide.setdefault(slide_index, []).append((group_index, child_index, margins))
    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=_set_text_frame_margins,
        feature="text frame margin editing",
    )


def _apply_text_frame_word_wrap_edits(
    input_path: Path,
    output_path: Path,
    word_wrap_edits: list[tuple[tuple[int, int], bool | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, bool | None]]] = {}
    for (slide_index, shape_index), word_wrap in word_wrap_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, word_wrap))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, word_wrap in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text frame word-wrap editing is only supported for shape elements"
                    )
                body_properties = _text_body_properties_element(shape_element)
                if word_wrap is None:
                    body_properties.attrib.pop("wrap", None)
                else:
                    body_properties.set("wrap", "square" if word_wrap else "none")
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_word_wrap_edits(
    input_path: Path,
    output_path: Path,
    word_wrap_edits: list[tuple[tuple[str, int], bool | None]],
) -> None:
    def apply_edit(body_properties: ET.Element, word_wrap: bool | None) -> None:
        if word_wrap is None:
            body_properties.attrib.pop("wrap", None)
        else:
            body_properties.set("wrap", "square" if word_wrap else "none")

    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=word_wrap_edits,
        apply_edit=apply_edit,
        feature="text frame word-wrap editing",
    )


def _apply_group_child_text_frame_word_wrap_edits(
    input_path: Path,
    output_path: Path,
    word_wrap_edits: list[tuple[tuple[int, int, int], bool | None]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, bool | None]]] = {}
    for (slide_index, group_index, child_index), word_wrap in word_wrap_edits:
        edits_by_slide.setdefault(slide_index, []).append((group_index, child_index, word_wrap))

    def apply_edit(body_properties: ET.Element, word_wrap: bool | None) -> None:
        if word_wrap is None:
            body_properties.attrib.pop("wrap", None)
        else:
            body_properties.set("wrap", "square" if word_wrap else "none")

    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=apply_edit,
        feature="text frame word-wrap editing",
    )


def _apply_text_frame_vertical_anchor_edits(
    input_path: Path,
    output_path: Path,
    vertical_anchor_edits: list[tuple[tuple[int, int], str | None]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, str | None]]] = {}
    for (slide_index, shape_index), anchor in vertical_anchor_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, anchor))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, anchor in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text frame vertical-anchor editing is only supported for shape elements"
                    )
                body_properties = _text_body_properties_element(shape_element)
                if anchor is None:
                    body_properties.attrib.pop("anchor", None)
                else:
                    body_properties.set("anchor", anchor)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_vertical_anchor_edits(
    input_path: Path,
    output_path: Path,
    vertical_anchor_edits: list[tuple[tuple[str, int], str | None]],
) -> None:
    def apply_edit(body_properties: ET.Element, anchor: str | None) -> None:
        if anchor is None:
            body_properties.attrib.pop("anchor", None)
        else:
            body_properties.set("anchor", anchor)

    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=vertical_anchor_edits,
        apply_edit=apply_edit,
        feature="text frame vertical-anchor editing",
    )


def _apply_group_child_text_frame_vertical_anchor_edits(
    input_path: Path,
    output_path: Path,
    vertical_anchor_edits: list[tuple[tuple[int, int, int], str | None]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, str | None]]] = {}
    for (slide_index, group_index, child_index), anchor in vertical_anchor_edits:
        edits_by_slide.setdefault(slide_index, []).append((group_index, child_index, anchor))

    def apply_edit(body_properties: ET.Element, anchor: str | None) -> None:
        if anchor is None:
            body_properties.attrib.pop("anchor", None)
        else:
            body_properties.set("anchor", anchor)

    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=apply_edit,
        feature="text frame vertical-anchor editing",
    )


def _apply_text_frame_auto_size_edits(
    input_path: Path,
    output_path: Path,
    auto_size_edits: list[tuple[tuple[int, int], Any]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, Any]]] = {}
    for (slide_index, shape_index), payload in auto_size_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, payload))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, payload in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(
                        "text frame auto-size editing is only supported for shape elements"
                    )
                body_properties = _text_body_properties_element(shape_element)
                if isinstance(payload, tuple) and len(payload) == 2:
                    auto_size, autofit_scale = payload
                else:
                    auto_size, autofit_scale = payload, None
                _apply_text_body_auto_size(body_properties, auto_size, autofit_scale)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_auto_size_edits(
    input_path: Path,
    output_path: Path,
    auto_size_edits: list[tuple[tuple[str, int], Any]],
) -> None:
    def apply_edit(body_properties: ET.Element, payload: Any) -> None:
        if isinstance(payload, tuple) and len(payload) == 2:
            auto_size, autofit_scale = payload
        else:
            auto_size, autofit_scale = payload, None
        _apply_text_body_auto_size(body_properties, auto_size, autofit_scale)

    _apply_part_text_frame_property_edits(
        input_path,
        output_path,
        edits=auto_size_edits,
        apply_edit=apply_edit,
        feature="text frame auto-size editing",
    )


def _apply_part_text_frame_edits(
    input_path: Path,
    output_path: Path,
    margin_edits: list[tuple[tuple[str, int], dict[str, int | None]]],
    word_wrap_edits: list[tuple[tuple[str, int], bool | None]],
    vertical_anchor_edits: list[tuple[tuple[str, int], str | None]],
    auto_size_edits: list[tuple[tuple[str, int], str | None]],
) -> None:
    edits_by_part: dict[str, dict[int, dict[str, Any]]] = {}
    for (partname, shape_index), margins in margin_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})["margins"] = margins
    for (partname, shape_index), word_wrap in word_wrap_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})["word_wrap"] = (
            word_wrap
        )
    for (partname, shape_index), anchor in vertical_anchor_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})["vertical_anchor"] = (
            anchor
        )
    for (partname, shape_index), auto_size in auto_size_edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, {}).setdefault(shape_index, {})["auto_size"] = (
            auto_size
        )

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            for shape_index, properties in part_edits.items():
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    for property_name, feature in (
                        ("margins", "text frame margin editing"),
                        ("word_wrap", "text frame word-wrap editing"),
                        ("vertical_anchor", "text frame vertical-anchor editing"),
                        ("auto_size", "text frame auto-size editing"),
                    ):
                        if property_name in properties:
                            raise AttributeError(f"{feature} is only supported for shape elements")
                body_properties = _text_body_properties_element(shape_element)
                margins = properties.get("margins")
                if margins is not None:
                    _set_text_frame_margins(body_properties, margins)
                if "word_wrap" in properties:
                    word_wrap = properties["word_wrap"]
                    if word_wrap is None:
                        body_properties.attrib.pop("wrap", None)
                    else:
                        body_properties.set(
                            "wrap",
                            "square" if word_wrap else "none",
                        )
                if "vertical_anchor" in properties:
                    anchor = properties["vertical_anchor"]
                    if anchor is None:
                        body_properties.attrib.pop("anchor", None)
                    else:
                        body_properties.set("anchor", anchor)
                if "auto_size" in properties:
                    payload = properties["auto_size"]
                    if isinstance(payload, tuple) and len(payload) == 2:
                        auto_size, autofit_scale = payload
                    else:
                        auto_size, autofit_scale = payload, None
                    _apply_text_body_auto_size(body_properties, auto_size, autofit_scale)
            _register_namespaces()
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
        _copy_open_package_with_replacements(package, output_path, replacements)


def _apply_group_child_text_frame_auto_size_edits(
    input_path: Path,
    output_path: Path,
    auto_size_edits: list[tuple[tuple[int, int, int], Any]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, Any]]] = {}
    for (slide_index, group_index, child_index), payload in auto_size_edits:
        edits_by_slide.setdefault(slide_index, []).append((group_index, child_index, payload))

    def apply_edit(body_properties: ET.Element, payload: Any) -> None:
        if isinstance(payload, tuple) and len(payload) == 2:
            auto_size, autofit_scale = payload
        else:
            auto_size, autofit_scale = payload, None
        _apply_text_body_auto_size(body_properties, auto_size, autofit_scale)

    _apply_group_child_text_frame_property_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=apply_edit,
        feature="text frame auto-size editing",
    )


def _apply_group_child_text_frame_fit_edits(
    input_path: Path,
    output_path: Path,
    fit_edits: list[tuple[tuple[int, int, int], dict[str, Any]]],
) -> None:
    edits_by_slide: dict[int, list[tuple[int, int, dict[str, Any]]]] = {}
    for (slide_index, group_index, child_index), fit in fit_edits:
        edits_by_slide.setdefault(slide_index, []).append((group_index, child_index, fit))

    def apply_edit(shape_element: ET.Element, fit: dict[str, Any]) -> None:
        _set_text_frame_fit(shape_element, fit)

    _apply_group_child_text_frame_shape_edits(
        input_path,
        output_path,
        edits_by_slide=edits_by_slide,
        apply_edit=apply_edit,
        feature="text fitting",
    )


def _apply_text_frame_fit_edits(
    input_path: Path,
    output_path: Path,
    fit_edits: list[tuple[tuple[int, int], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    edits_by_slide: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for (slide_index, shape_index), fit in fit_edits:
        edits_by_slide.setdefault(slide_index, []).append((shape_index, fit))
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for shape_index, fit in slide_edits:
                try:
                    shape_payload = slide_payload["shapes"][shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError("text fitting is only supported for shape elements")
                _set_text_frame_fit(shape_element, fit)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_text_frame_shape_edits(
    input_path: Path,
    output_path: Path,
    *,
    edits_by_slide: dict[int, list[tuple[int, int, Any]]],
    apply_edit: Any,
    feature: str,
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for group_index, child_index, value in slide_edits:
                shape_element = _group_child_shape_element(
                    root,
                    slide_payload,
                    group_index,
                    child_index,
                )
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(f"{feature} is only supported for shape elements")
                apply_edit(shape_element, value)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_part_text_frame_property_edits(
    input_path: Path,
    output_path: Path,
    *,
    edits: list[tuple[tuple[str, int], Any]],
    apply_edit: Any,
    feature: str,
) -> None:
    replacements: dict[str, bytes] = {}
    edits_by_part: dict[str, list[tuple[int, Any]]] = {}
    for (partname, shape_index), value in edits:
        normalized = _normalize_package_partname(partname).lstrip("/")
        edits_by_part.setdefault(normalized, []).append((shape_index, value))
    with zipfile.ZipFile(input_path) as package:
        for partname, part_edits in edits_by_part.items():
            shape_payloads = _load_shape_payloads(input_path, partname)
            root = ET.fromstring(package.read(partname))
            for shape_index, value in part_edits:
                try:
                    shape_payload = shape_payloads[shape_index]
                except IndexError as exc:
                    raise IndexError("shape index out of range") from exc
                shape_element = _shape_xml_element(root, shape_payload)
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(f"{feature} is only supported for shape elements")
                body_properties = _text_body_properties_element(shape_element)
                apply_edit(body_properties, value)
            _register_namespaces()
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_group_child_text_frame_property_edits(
    input_path: Path,
    output_path: Path,
    *,
    edits_by_slide: dict[int, list[tuple[int, int, Any]]],
    apply_edit: Any,
    feature: str,
) -> None:
    slides = _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for slide_index, slide_edits in edits_by_slide.items():
            try:
                slide_payload = slides[slide_index]
            except IndexError as exc:
                raise IndexError("slide index out of range") from exc
            slide_part = str(slide_payload["part"])
            root = ET.fromstring(package.read(slide_part))
            for group_index, child_index, value in slide_edits:
                shape_element = _group_child_shape_element(
                    root,
                    slide_payload,
                    group_index,
                    child_index,
                )
                if _xml_local_name(shape_element.tag) != "sp":
                    raise AttributeError(f"{feature} is only supported for shape elements")
                body_properties = _text_body_properties_element(shape_element)
                apply_edit(body_properties, value)
            replacements[slide_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _group_child_shape_element(
    root: ET.Element,
    slide_payload: dict[str, Any],
    group_index: int,
    child_index: int,
) -> ET.Element:
    try:
        group_payload = slide_payload["shapes"][group_index]
        child_payload = group_payload["children"][child_index]
    except IndexError as exc:
        raise IndexError("group child shape index out of range") from exc
    if not isinstance(child_payload, dict):
        raise TypeError("group child shape payload is unavailable")
    return _shape_xml_element(root, child_payload)
