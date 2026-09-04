"""Group-shape XML edits for python-pptx-compatible facade saves."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements
from .slide_payloads import load_slide_payloads
from .xml_helpers import xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

SHAPE_TAGS = {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}


def apply_existing_shape_grouping(
    input_path: Path,
    output_path: Path,
    slide_index: int,
    shape_indices: tuple[int, ...],
) -> None:
    slides = load_slide_payloads(input_path)
    try:
        slide_part = str(slides[slide_index]["part"])
    except IndexError as exc:
        raise IndexError("slide index out of range") from exc

    with zipfile.ZipFile(input_path) as package:
        root = ET.fromstring(package.read(slide_part))

    shape_tree = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if shape_tree is None:
        raise ValueError("slide shape tree is missing")

    shapes = _shape_tree_children(shape_tree)
    selected = _selected_shape_elements(shapes, shape_indices)
    left, top, width, height = _group_bounds(selected)
    shape_id = _next_cnvpr_id(root)
    group = _group_shape_element(shape_id, left, top, width, height)

    selected_ids = {id(element) for element in selected}
    for element in list(shape_tree):
        if id(element) in selected_ids:
            shape_tree.remove(element)

    for element in selected:
        group.append(element)

    shape_tree.insert(_append_shape_index(shape_tree), group)
    copy_package_with_replacements(
        input_path,
        output_path,
        {
            slide_part: ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
        },
    )


def apply_existing_group_child_grouping(
    input_path: Path,
    output_path: Path,
    slide_index: int,
    group_index: int,
    child_indices: tuple[int, ...],
) -> None:
    from . import native

    native.group_existing_group_children(
        input_path,
        output_path,
        slide_index,
        group_index,
        tuple(child_indices),
    )


def apply_existing_nested_group_child_grouping(
    input_path: Path,
    output_path: Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    child_indices: tuple[int, ...],
) -> None:
    from . import native

    native.group_existing_nested_group_children(
        input_path,
        output_path,
        slide_index,
        group_index,
        nested_group_child_index,
        tuple(child_indices),
    )


def apply_existing_deeper_nested_group_child_grouping(
    input_path: Path,
    output_path: Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
    child_indices: tuple[int, ...],
) -> None:
    from . import native

    native.group_existing_deeper_nested_group_children(
        input_path,
        output_path,
        slide_index,
        group_index,
        nested_group_child_index,
        deeper_group_child_index,
        tuple(child_indices),
    )


def _shape_tree_children(shape_tree: ET.Element) -> list[ET.Element]:
    return [
        child
        for child in list(shape_tree)
        if xml_local_name(child.tag) in SHAPE_TAGS
    ]


def _selected_shape_elements(
    shapes: list[ET.Element],
    shape_indices: tuple[int, ...],
) -> list[ET.Element]:
    if not shape_indices:
        raise ValueError("at least one shape is required")
    selected: list[ET.Element] = []
    for index in shape_indices:
        try:
            selected.append(shapes[index])
        except IndexError as exc:
            raise IndexError("shape index out of range") from exc
    return selected


def _top_level_group(shape_tree: ET.Element, group_index: int) -> ET.Element:
    groups = [
        child
        for child in _shape_tree_children(shape_tree)
        if xml_local_name(child.tag) == "grpSp"
    ]
    try:
        return groups[group_index]
    except IndexError as exc:
        raise IndexError("group shape index out of range") from exc


def _group_bounds(shapes: list[ET.Element]) -> tuple[int, int, int, int]:
    boxes = [_shape_bounds(shape) for shape in shapes]
    left = min(x for x, _y, _cx, _cy in boxes)
    top = min(y for _x, y, _cx, _cy in boxes)
    right = max(x + cx for x, _y, cx, _cy in boxes)
    bottom = max(y + cy for _x, y, _cx, cy in boxes)
    return left, top, right - left, bottom - top


def _shape_bounds(shape: ET.Element) -> tuple[int, int, int, int]:
    xfrm = _shape_transform(shape)
    off = xfrm.find(f"{{{A_NS}}}off")
    ext = xfrm.find(f"{{{A_NS}}}ext")
    if off is None or ext is None:
        raise ValueError("selected shape is missing transform bounds")
    return (
        int(off.attrib.get("x", "0")),
        int(off.attrib.get("y", "0")),
        int(ext.attrib.get("cx", "0")),
        int(ext.attrib.get("cy", "0")),
    )


def _shape_transform(shape: ET.Element) -> ET.Element:
    tag = xml_local_name(shape.tag)
    if tag == "grpSp":
        path = f"{{{P_NS}}}grpSpPr/{{{A_NS}}}xfrm"
    elif tag == "graphicFrame":
        path = f"{{{P_NS}}}xfrm"
    else:
        path = f"{{{P_NS}}}spPr/{{{A_NS}}}xfrm"
    xfrm = shape.find(path)
    if xfrm is None:
        raise ValueError("selected shape is missing transform")
    return xfrm


def _next_cnvpr_id(root: ET.Element) -> int:
    ids = [1]
    for element in root.iter(f"{{{P_NS}}}cNvPr"):
        try:
            ids.append(int(element.attrib.get("id", "0")))
        except ValueError:
            pass
    return max(ids) + 1


def _group_shape_element(
    shape_id: int,
    left: int,
    top: int,
    width: int,
    height: int,
) -> ET.Element:
    group = ET.Element(f"{{{P_NS}}}grpSp")
    nv_group = ET.SubElement(group, f"{{{P_NS}}}nvGrpSpPr")
    ET.SubElement(
        nv_group,
        f"{{{P_NS}}}cNvPr",
        {"id": str(shape_id), "name": f"Group {shape_id - 1}"},
    )
    ET.SubElement(nv_group, f"{{{P_NS}}}cNvGrpSpPr")
    ET.SubElement(nv_group, f"{{{P_NS}}}nvPr")
    group_properties = ET.SubElement(group, f"{{{P_NS}}}grpSpPr")
    xfrm = ET.SubElement(group_properties, f"{{{A_NS}}}xfrm")
    ET.SubElement(xfrm, f"{{{A_NS}}}off", {"x": str(left), "y": str(top)})
    ET.SubElement(xfrm, f"{{{A_NS}}}ext", {"cx": str(width), "cy": str(height)})
    ET.SubElement(xfrm, f"{{{A_NS}}}chOff", {"x": str(left), "y": str(top)})
    ET.SubElement(xfrm, f"{{{A_NS}}}chExt", {"cx": str(width), "cy": str(height)})
    return group


def _append_shape_index(shape_tree: ET.Element) -> int:
    children = list(shape_tree)
    for index, child in enumerate(children):
        if xml_local_name(child.tag) == "extLst":
            return index
    return len(children)
