"""Placeholder cloning and saved-part size-class edits.

``shape.placeholder_format.size = PlaceholderSize.HALF`` edits only ``p:ph/@sz``.
``None`` clears the attribute; an absent attribute reads as FULL. Size classes
are metadata, not shape dimensions. Save queued edits first and reacquire shape
handles after package-backed edits. Other placeholder attributes are preserved.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .chart_workbook import serialize_xml_preserving_namespaces
from .enum.shapes import PlaceholderSize
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .shape_xml import _shape_xml_element
from .xml_helpers import findall_ooxml

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def apply_part_placeholder_adds(
    input_path: Path,
    output_path: Path,
    adds: list[tuple[str, dict[str, str | bool | None]]],
) -> None:
    if not adds:
        _copy_package_with_replacements(input_path, output_path, {})
        return

    adds_by_part: dict[str, list[dict[str, str | bool | None]]] = {}
    for partname, spec in adds:
        adds_by_part.setdefault(partname.lstrip("/"), []).append(dict(spec))

    with zipfile.ZipFile(input_path) as package:
        replacements: dict[str, bytes] = {}
        for partname, specs in adds_by_part.items():
            root = ET.fromstring(package.read(partname))
            shape_tree = _shape_tree(root)
            for spec in specs:
                _insert_shape_tree_child(shape_tree, _placeholder_shape(spec))
            _register_namespaces()
            replacements[partname] = ET.tostring(root, encoding="utf-8")

    _copy_package_with_replacements(input_path, output_path, replacements)


def _shape_tree(root: ET.Element) -> ET.Element:
    shape_tree = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if shape_tree is None:
        raise AttributeError("shape tree is unavailable")
    return shape_tree


def _placeholder_shape(spec: dict[str, str | bool | None]) -> ET.Element:
    shape = ET.Element(f"{{{P_NS}}}sp")
    non_visual = ET.SubElement(shape, f"{{{P_NS}}}nvSpPr")
    common = ET.SubElement(non_visual, f"{{{P_NS}}}cNvPr")
    common.set("id", str(spec["id"]))
    common.set("name", str(spec["name"]))
    non_visual_shape = ET.SubElement(non_visual, f"{{{P_NS}}}cNvSpPr")
    ET.SubElement(non_visual_shape, f"{{{A_NS}}}spLocks", {"noGrp": "1"})
    non_visual_properties = ET.SubElement(non_visual, f"{{{P_NS}}}nvPr")
    placeholder = ET.SubElement(non_visual_properties, f"{{{P_NS}}}ph")
    _set_optional_attr(placeholder, "type", spec.get("placeholder_type"))
    _set_optional_attr(placeholder, "orient", spec.get("placeholder_orient"))
    _set_optional_attr(placeholder, "sz", spec.get("placeholder_size"))
    placeholder_idx = spec.get("placeholder_idx")
    if placeholder_idx not in {None, "", "0"}:
        placeholder.set("idx", str(placeholder_idx))
    ET.SubElement(shape, f"{{{P_NS}}}spPr")
    if spec.get("has_text_body"):
        text_body = ET.SubElement(shape, f"{{{P_NS}}}txBody")
        ET.SubElement(text_body, f"{{{A_NS}}}bodyPr")
        ET.SubElement(text_body, f"{{{A_NS}}}lstStyle")
        ET.SubElement(text_body, f"{{{A_NS}}}p")
    return shape


def _set_optional_attr(element: ET.Element, name: str, value: str | bool | None) -> None:
    if value not in {None, ""}:
        element.set(name, str(value))


def _insert_shape_tree_child(shape_tree: ET.Element, child: ET.Element) -> None:
    insert_at = len(shape_tree)
    for index, existing in enumerate(list(shape_tree)):
        if _local_name(existing.tag) == "extLst":
            insert_at = index
            break
    shape_tree.insert(insert_at, child)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _register_namespaces() -> None:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)


class PlaceholderSizeRefusal(ValueError):
    """Placeholder size metadata cannot be read or edited safely."""


def _placeholder_element(element: ET.Element) -> ET.Element:
    placeholders = findall_ooxml(element, f".//{{{P_NS}}}ph")
    if len(placeholders) != 1:
        raise PlaceholderSizeRefusal("shape must have exactly one placeholder declaration")
    placeholder = placeholders[0]
    declarations = [
        node
        for name in ("nvSpPr", "nvPicPr", "nvGraphicFramePr", "nvCxnSpPr")
        for node in findall_ooxml(element, f"{{{P_NS}}}{name}/{{{P_NS}}}nvPr/{{{P_NS}}}ph")
    ]
    if declarations != [placeholder]:
        raise PlaceholderSizeRefusal("nested placeholder declarations are unsupported")
    if any(
        node.tag == "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
        for node in element.iter()
    ):
        raise PlaceholderSizeRefusal("alternate placeholder XML is unsupported")
    return placeholder


def _read_placeholder_size(element: ET.Element) -> PlaceholderSize:
    raw = _placeholder_element(element).get("sz", "full")
    try:
        return PlaceholderSize(raw)
    except ValueError as exc:
        raise PlaceholderSizeRefusal(f"unsupported saved placeholder size {raw!r}") from exc


def placeholder_size(shape: Any) -> PlaceholderSize:
    """Read the local placeholder class; absent ``sz`` has schema default FULL."""
    try:
        return _read_placeholder_size(shape.element._element)
    except (AttributeError, KeyError, OSError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise PlaceholderSizeRefusal("saved placeholder XML is unavailable") from exc


def set_placeholder_size(shape: Any, value: PlaceholderSize | str | None) -> None:
    """Set or clear only ``p:ph/@sz`` on a saved slide, layout, master or notes shape.

    This metadata does not resize the shape. Save queued edits first; package
    rewrites rebase the presentation, so reacquire shape handles afterwards.
    Other placeholder attributes and untouched package payloads are preserved.
    """
    if value is not None:
        if not isinstance(value, str):
            raise PlaceholderSizeRefusal("placeholder size must be full, half, quarter or None")
        try:
            value = PlaceholderSize(value)
        except ValueError as exc:
            raise PlaceholderSizeRefusal(
                "placeholder size must be full, half, quarter or None"
            ) from exc
    owner = getattr(shape, "_master", None) or getattr(shape, "_slide", None)
    if owner is None or not owner.partname:
        raise PlaceholderSizeRefusal("placeholder must belong to a saved presentation part")
    presentation = owner._presentation
    part = owner.partname

    def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
        source = package.read(part)
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        root = ET.fromstring(source, parser=parser)
        element = _shape_xml_element(root, shape._payload)
        _read_placeholder_size(element)
        placeholder = _placeholder_element(element)
        if value is None:
            if "sz" not in placeholder.attrib:
                return {}, set(), None
            del placeholder.attrib["sz"]
        else:
            if placeholder.get("sz") == value.value:
                return {}, set(), None
            placeholder.set("sz", value.value)
        return {part: serialize_xml_preserving_namespaces(root, source)}, set(), None

    try:
        presentation._rewrite_package("setting placeholder size", plan)
    except (
        ValueError,
        RuntimeError,
        AttributeError,
        KeyError,
        OSError,
        ET.ParseError,
        zipfile.BadZipFile,
    ) as exc:
        if isinstance(exc, PlaceholderSizeRefusal):
            raise
        raise PlaceholderSizeRefusal(f"cannot set placeholder size: {exc}") from exc
