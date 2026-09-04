"""Placeholder clone edits for master and layout shape trees."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)


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
