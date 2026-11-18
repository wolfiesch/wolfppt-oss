"""Read-only slide part metadata helpers."""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    InMemoryPackageSource,
    natural_key,
    open_package_source,
    rels_part_for_package_part,
    resolve_package_target,
)
from .package_read_scope import package_xml
from .xml_helpers import find_ooxml, findall_ooxml, ooxml_path

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CX_NS = "http://schemas.microsoft.com/office/drawing/2014/chartex"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def presentation_partname(path: Path | InMemoryPackageSource) -> str:
    try:
        with open_package_source(path) as package:
            root = package_xml(package, "_rels/.rels")
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return "ppt/presentation.xml"
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Type", "").endswith("/officeDocument"):
            return resolve_package_target("", rel.attrib.get("Target", ""))
    return "ppt/presentation.xml"


def presentation_slide_master_partnames(
    package: zipfile.ZipFile,
    path: Path,
) -> list[str]:
    try:
        presentation_part = presentation_partname(path)
        relationships = package_relationships(package, presentation_part)
        parts = [
            resolve_package_target(
                presentation_part,
                relationship.attrib.get("Target", ""),
            )
            for relationship in relationships.values()
            if relationship.attrib.get("Type", "").endswith("/slideMaster")
        ]
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        parts = []
    if parts:
        return parts
    return sorted(
        [
            name
            for name in package.namelist()
            if name.startswith("ppt/slideMasters/slideMaster") and name.endswith(".xml")
        ],
        key=natural_key,
    )


def related_package_partnames(
    package: zipfile.ZipFile,
    partname: str,
    rel_suffix: str,
) -> list[str]:
    return [
        resolve_package_target(partname, relationship.attrib.get("Target", ""))
        for relationship in package_relationships(package, partname).values()
        if relationship.attrib.get("Type", "").endswith(rel_suffix)
    ]


def part_common_slide_name(package: zipfile.ZipFile, partname: str) -> str:
    try:
        root = ET.fromstring(package.read(partname))
    except (KeyError, ET.ParseError):
        return ""
    common_slide_data = find_ooxml(root, f"{{{P_NS}}}cSld")
    if common_slide_data is None:
        return ""
    return common_slide_data.attrib.get("name", "")


def part_common_slide_name_from_path(path: Path | InMemoryPackageSource, partname: str) -> str:
    try:
        with open_package_source(path) as package:
            return part_common_slide_name(package, partname)
    except (FileNotFoundError, zipfile.BadZipFile):
        return ""


def first_slide_master_partname(path: Path) -> str:
    presentation_part = presentation_partname(path)
    try:
        with zipfile.ZipFile(path) as package:
            root = ET.fromstring(package.read(rels_part_for_package_part(presentation_part)))
            for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
                if rel.attrib.get("Type", "").endswith("/slideMaster"):
                    return resolve_package_target(
                        presentation_part,
                        rel.attrib.get("Target", ""),
                    )
            slide_masters = sorted(
                [
                    name
                    for name in package.namelist()
                    if name.startswith("ppt/slideMasters/slideMaster") and name.endswith(".xml")
                ],
                key=natural_key,
            )
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        slide_masters = []
    if slide_masters:
        return slide_masters[0]
    raise AttributeError("slide master part is unavailable")


def presentation_notes_master_partname(path: Path) -> str:
    presentation_part = presentation_partname(path)
    try:
        with zipfile.ZipFile(path) as package:
            for rel in package_relationships(package, presentation_part).values():
                if rel.attrib.get("Type", "").endswith("/notesMaster"):
                    return resolve_package_target(
                        presentation_part,
                        rel.attrib.get("Target", ""),
                    )
            notes_masters = sorted(
                [
                    name
                    for name in package.namelist()
                    if name.startswith("ppt/notesMasters/notesMaster") and name.endswith(".xml")
                ],
                key=natural_key,
            )
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        notes_masters = []
    if notes_masters:
        return notes_masters[0]
    raise AttributeError("notes master part is unavailable")


def presentation_handout_master_partname(path: Path) -> str:
    presentation_part = presentation_partname(path)
    try:
        with zipfile.ZipFile(path) as package:
            for rel in package_relationships(package, presentation_part).values():
                if rel.attrib.get("Type", "").endswith("/handoutMaster"):
                    return resolve_package_target(
                        presentation_part,
                        rel.attrib.get("Target", ""),
                    )
            handout_masters = sorted(
                [
                    name
                    for name in package.namelist()
                    if name.startswith("ppt/handoutMasters/handoutMaster") and name.endswith(".xml")
                ],
                key=natural_key,
            )
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        handout_masters = []
    if handout_masters:
        return handout_masters[0]
    raise AttributeError("handout master part is unavailable")


def next_handout_master_partname(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as package:
            handout_masters = [
                name
                for name in package.namelist()
                if name.startswith("ppt/handoutMasters/handoutMaster") and name.endswith(".xml")
            ]
    except (FileNotFoundError, zipfile.BadZipFile):
        handout_masters = []
    highest = 0
    for partname in handout_masters:
        suffix = partname.removeprefix("ppt/handoutMasters/handoutMaster").removesuffix(".xml")
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"ppt/handoutMasters/handoutMaster{highest + 1}.xml"


def slide_metadata(slide: Any) -> dict[str, Any]:
    partname = slide.partname
    if not partname:
        return {}
    metadata = presentation_slide_metadata(slide._presentation)
    return dict(metadata.get(partname, {}))


def presentation_slide_metadata(presentation: Any) -> dict[str, dict[str, Any]]:
    if getattr(presentation, "_disposed", False):
        raise RuntimeError("presentation is disposed")
    if presentation._slide_metadata is not None:
        return presentation._slide_metadata
    metadata = read_presentation_slide_metadata(presentation._source_path)
    presentation._slide_metadata = metadata
    return metadata


def read_presentation_slide_metadata(
    path: Path | InMemoryPackageSource,
    *,
    include_shape_hints: bool = True,
) -> dict[str, dict[str, Any]]:
    try:
        with open_package_source(path) as package:
            presentation_part = presentation_partname(path)
            presentation = package_xml(package, presentation_part)
            presentation_rels = package_relationships(package, presentation_part)
            metadata: dict[str, dict[str, Any]] = {}
            for slide_id in findall_ooxml(presentation, f".//{{{P_NS}}}sldId"):
                relationship_id = slide_id.attrib.get(ooxml_path(slide_id, f"{{{R_NS}}}id"))
                if relationship_id is None:
                    continue
                relationship = presentation_rels.get(relationship_id)
                if relationship is None:
                    continue
                slide_part = resolve_package_target(
                    presentation_part,
                    relationship.attrib.get("Target", ""),
                )
                payload = metadata.setdefault(slide_part, {})
                payload["relationship_id"] = relationship_id
                raw_slide_id = slide_id.attrib.get("id")
                if raw_slide_id:
                    payload["slide_id"] = int(raw_slide_id)
            for slide_part, payload in metadata.items():
                payload.update(
                    read_slide_part_metadata(
                        package,
                        slide_part,
                        include_shape_hints=include_shape_hints,
                    )
                )
            return metadata
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return {}


def read_slide_part_metadata(
    package: zipfile.ZipFile,
    slide_part: str,
    *,
    include_shape_hints: bool = True,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    try:
        root = package_xml(package, slide_part)
    except (KeyError, ET.ParseError):
        root = None
    if root is not None:
        common_slide_data = find_ooxml(root, f"{{{P_NS}}}cSld")
        metadata["name"] = (
            "" if common_slide_data is None else common_slide_data.attrib.get("name", "")
        )
        metadata["follow_master_background"] = (
            True
            if common_slide_data is None
            else find_ooxml(common_slide_data, f"{{{P_NS}}}bg") is None
        )
        raw_show = root.attrib.get("show")
        if raw_show is not None:
            if raw_show in ("1", "true"):
                metadata["hidden"] = False
            elif raw_show in ("0", "false"):
                metadata["hidden"] = True
            else:
                raise ValueError(f"malformed OOXML boolean attribute show={raw_show!r}")
        else:
            metadata["hidden"] = False
    else:
        metadata["hidden"] = False
    relationships = package_relationships(package, slide_part)
    metadata["has_notes_slide"] = False
    chart_relationship_ids: list[str] = []
    chart_relationship_parts: list[str] = []
    chart_parts_by_relationship_id: dict[str, str] = {}
    image_relationship_ids: list[str] = []
    image_relationship_parts: list[str] = []
    image_parts_by_relationship_id: dict[str, str] = {}
    for relationship in relationships.values():
        relationship_type = relationship.attrib.get("Type", "")
        if relationship_type.endswith("/slideLayout"):
            metadata["layout_part"] = resolve_package_target(
                slide_part,
                relationship.attrib.get("Target", ""),
            )
        elif relationship_type.endswith("/notesSlide"):
            metadata["has_notes_slide"] = True
            metadata["notes_part"] = resolve_package_target(
                slide_part,
                relationship.attrib.get("Target", ""),
            )
        elif relationship_type.endswith(("/chart", "/chartEx")):
            relationship_id = str(relationship.attrib.get("Id", ""))
            chart_part = resolve_package_target(
                slide_part,
                relationship.attrib.get("Target", ""),
            )
            chart_relationship_ids.append(relationship_id)
            chart_relationship_parts.append(chart_part)
            chart_parts_by_relationship_id[relationship_id] = chart_part
        elif relationship_type.endswith("/image"):
            relationship_id = str(relationship.attrib.get("Id", ""))
            image_part = resolve_package_target(
                slide_part,
                relationship.attrib.get("Target", ""),
            )
            image_relationship_ids.append(relationship_id)
            image_relationship_parts.append(image_part)
            image_parts_by_relationship_id[relationship_id] = image_part
    if include_shape_hints and root is not None:
        chart_shape_hints = _top_level_chart_shape_hints(
            root,
            chart_parts_by_relationship_id,
        )
        picture_shape_hints = _top_level_picture_shape_hints(
            root,
            image_parts_by_relationship_id,
        )
        connector_shape_hints = _top_level_connector_shape_hints(root)
        table_shape_hints = _top_level_table_shape_hints(root)
        group_shape_hints = _top_level_group_shape_hints(root)
        metadata["chart_shape_hints"] = chart_shape_hints
        metadata["picture_shape_hints"] = picture_shape_hints
        metadata["connector_shape_hints"] = connector_shape_hints
        metadata["table_shape_hints"] = table_shape_hints
        metadata["group_shape_hints"] = group_shape_hints
        metadata["shape_shell_hints"] = sorted(
            [
                *_top_level_text_shape_hints(root),
                *chart_shape_hints,
                *picture_shape_hints,
                *connector_shape_hints,
                *table_shape_hints,
                *group_shape_hints,
            ],
            key=lambda hint: int(hint.get("_shape_index", 0)),
        )
    metadata["has_chart_relationship"] = bool(chart_relationship_ids)
    metadata["chart_relationship_ids"] = chart_relationship_ids
    metadata["chart_parts"] = chart_relationship_parts
    metadata["has_image_relationship"] = bool(image_relationship_ids)
    metadata["image_relationship_ids"] = image_relationship_ids
    metadata["image_parts"] = image_relationship_parts
    return metadata


def _top_level_chart_shape_hints(
    root: ET.Element,
    chart_parts_by_relationship_id: dict[str, str],
) -> list[dict[str, Any]]:
    shape_tree = _shape_tree(root)
    if shape_tree is None:
        return []
    hints: list[dict[str, Any]] = []
    shape_index = 0
    for child in list(shape_tree):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        if local_name != "graphicFrame":
            shape_index += 1
            continue
        chart = _first_descendant(child, f"{{{C_NS}}}chart")
        if chart is None:
            chart = _first_descendant(child, f"{{{CX_NS}}}chart")
        relationship_id = None if chart is None else chart.attrib.get(f"{{{R_NS}}}id")
        if relationship_id:
            non_visual_properties = _first_descendant(child, f"{{{P_NS}}}cNvPr")
            transform = _shape_transform_payload(child)
            hints.append(
                {
                    "id": None
                    if non_visual_properties is None
                    else non_visual_properties.attrib.get("id"),
                    "name": ""
                    if non_visual_properties is None
                    else non_visual_properties.attrib.get("name", ""),
                    "kind": "graphic_frame",
                    "text": "",
                    "paragraphs": [],
                    "paragraph_runs": [],
                    "relationship_ids": [relationship_id],
                    "_chart_part": chart_parts_by_relationship_id.get(
                        relationship_id,
                        "",
                    ),
                    "has_chart": True,
                    "has_picture": False,
                    "tables": [],
                    "transform": transform,
                    "effective_transform": transform,
                    "_shape_index": shape_index,
                    "_shell_shape_hint": True,
                }
            )
        shape_index += 1
    return hints


def _top_level_picture_shape_hints(
    root: ET.Element,
    image_parts_by_relationship_id: dict[str, str],
) -> list[dict[str, Any]]:
    shape_tree = _shape_tree(root)
    if shape_tree is None:
        return []
    hints: list[dict[str, Any]] = []
    shape_index = 0
    for child in list(shape_tree):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        if local_name != "pic":
            shape_index += 1
            continue
        blip = _first_descendant(child, f"{{{A_NS}}}blip")
        relationship_id = None if blip is None else blip.attrib.get(f"{{{R_NS}}}embed")
        if relationship_id:
            non_visual_properties = _first_descendant(child, f"{{{P_NS}}}cNvPr")
            transform = _shape_transform_payload(child)
            hints.append(
                {
                    "id": None
                    if non_visual_properties is None
                    else non_visual_properties.attrib.get("id"),
                    "name": ""
                    if non_visual_properties is None
                    else non_visual_properties.attrib.get("name", ""),
                    "kind": "picture",
                    "text": "",
                    "paragraphs": [],
                    "paragraph_runs": [],
                    "relationship_ids": [relationship_id],
                    "_image_relationship_id": relationship_id,
                    "_image_part": image_parts_by_relationship_id.get(
                        relationship_id,
                        "",
                    ),
                    "has_chart": False,
                    "has_picture": True,
                    "tables": [],
                    "transform": transform,
                    "effective_transform": transform,
                    "_shape_index": shape_index,
                    "_shell_shape_hint": True,
                }
            )
        shape_index += 1
    return hints


def _top_level_connector_shape_hints(root: ET.Element) -> list[dict[str, Any]]:
    shape_tree = _shape_tree(root)
    if shape_tree is None:
        return []
    hints: list[dict[str, Any]] = []
    shape_index = 0
    for child in list(shape_tree):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        if local_name != "cxnSp":
            shape_index += 1
            continue
        non_visual_properties = _first_descendant(child, f"{{{P_NS}}}cNvPr")
        transform = _shape_transform_payload(child)
        hints.append(
            {
                "id": None
                if non_visual_properties is None
                else non_visual_properties.attrib.get("id"),
                "name": ""
                if non_visual_properties is None
                else non_visual_properties.attrib.get("name", ""),
                "kind": "connector",
                "text": "",
                "paragraphs": [],
                "paragraph_runs": [],
                "relationship_ids": [],
                "has_chart": False,
                "has_picture": False,
                "tables": [],
                "transform": transform,
                "effective_transform": transform,
                "_shape_index": shape_index,
                "_shell_shape_hint": True,
            }
        )
        shape_index += 1
    return hints


def _top_level_table_shape_hints(root: ET.Element) -> list[dict[str, Any]]:
    shape_tree = _shape_tree(root)
    if shape_tree is None:
        return []
    hints: list[dict[str, Any]] = []
    shape_index = 0
    table_index = 0
    for child in list(shape_tree):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        if local_name != "graphicFrame":
            shape_index += 1
            continue
        table = _first_descendant(child, f"{{{A_NS}}}tbl")
        if table is not None:
            non_visual_properties = _first_descendant(child, f"{{{P_NS}}}cNvPr")
            transform = _shape_transform_payload(child)
            table_payload = _table_payload(table)
            hints.append(
                {
                    "id": None
                    if non_visual_properties is None
                    else non_visual_properties.attrib.get("id"),
                    "name": ""
                    if non_visual_properties is None
                    else non_visual_properties.attrib.get("name", ""),
                    "kind": "graphic_frame",
                    "text": "",
                    "paragraphs": [],
                    "paragraph_runs": [],
                    "relationship_ids": [],
                    "has_chart": False,
                    "has_picture": False,
                    "tables": [table_payload],
                    "transform": transform,
                    "effective_transform": transform,
                    "_shape_index": shape_index,
                    "_table_index": table_index,
                    "_shell_shape_hint": True,
                }
            )
            table_index += 1
        shape_index += 1
    return hints


def _top_level_text_shape_hints(root: ET.Element) -> list[dict[str, Any]]:
    shape_tree = _shape_tree(root)
    if shape_tree is None:
        return []
    hints: list[dict[str, Any]] = []
    shape_index = 0
    for child in list(shape_tree):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        if local_name != "sp":
            shape_index += 1
            continue
        non_visual_properties = _first_descendant(child, f"{{{P_NS}}}cNvPr")
        blocks, runs = _text_blocks_and_runs(child)
        paragraphs = blocks or [""]
        paragraph_runs = runs or [[] for _ in paragraphs]
        transform = _shape_transform_payload(child)
        hint = {
            "id": None if non_visual_properties is None else non_visual_properties.attrib.get("id"),
            "name": ""
            if non_visual_properties is None
            else non_visual_properties.attrib.get("name", ""),
            "kind": "shape",
            "text": "\n".join(paragraphs),
            "paragraphs": paragraphs,
            "paragraph_runs": _fit_text_run_blocks(paragraph_runs, paragraphs),
            "paragraph_line_breaks": [[] for _ in paragraphs],
            "relationship_ids": [],
            "has_chart": False,
            "has_picture": False,
            "tables": [],
            "transform": transform,
            "effective_transform": transform,
            "_shape_index": shape_index,
            "_shell_shape_hint": True,
        }
        placeholder = _first_descendant(child, f"{{{P_NS}}}ph")
        if placeholder is not None:
            hint.update(
                {
                    "is_placeholder": True,
                    "placeholder_type": placeholder.attrib.get("type"),
                    "placeholder_idx": placeholder.attrib.get("idx"),
                    "placeholder_orient": placeholder.attrib.get("orient"),
                    "placeholder_size": placeholder.attrib.get("sz"),
                }
            )
        hints.append(hint)
        shape_index += 1
    return hints


def _top_level_group_shape_hints(root: ET.Element) -> list[dict[str, Any]]:
    shape_tree = _shape_tree(root)
    if shape_tree is None:
        return []
    max_shape_id = _max_shape_id(shape_tree)
    hints: list[dict[str, Any]] = []
    shape_index = 0
    group_index = 0
    for child in list(shape_tree):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        if local_name == "grpSp":
            hint = _group_shape_hint(child, shape_index, group_index, max_shape_id)
            hints.append(hint)
            group_index += 1
        shape_index += 1
    return hints


def _group_shape_hint(
    element: ET.Element,
    shape_index: int,
    group_index: int,
    max_shape_id: int,
) -> dict[str, Any]:
    non_visual_properties = _first_descendant(element, f"{{{P_NS}}}cNvPr")
    children = [
        _child_shape_hint(child, child_index)
        for child_index, child in enumerate(_shape_children(element))
    ]
    transform = _shape_transform_payload(element)
    return {
        "id": None if non_visual_properties is None else non_visual_properties.attrib.get("id"),
        "name": ""
        if non_visual_properties is None
        else non_visual_properties.attrib.get("name", ""),
        "kind": "group",
        "text": "",
        "paragraphs": [],
        "paragraph_runs": [],
        "relationship_ids": [],
        "has_chart": False,
        "has_picture": False,
        "tables": [],
        "children": children,
        "transform": transform,
        "effective_transform": transform,
        "_shape_index": shape_index,
        "_group_index": group_index,
        "_max_shape_id": max_shape_id,
        "_shell_shape_hint": True,
    }


def _child_shape_hint(element: ET.Element, shape_index: int) -> dict[str, Any]:
    local_name = _xml_local_name(element.tag)
    non_visual_properties = _first_descendant(element, f"{{{P_NS}}}cNvPr")
    relationship_ids = _shape_relationship_ids(element)
    blocks, runs = _text_blocks_and_runs(element)
    paragraphs = blocks or [""]
    paragraph_runs = runs or [[] for _ in paragraphs]
    kind = {
        "grpSp": "group",
        "pic": "picture",
        "cxnSp": "connector",
        "graphicFrame": "graphic_frame",
    }.get(local_name, "shape")
    transform = _shape_transform_payload(element)
    hint: dict[str, Any] = {
        "id": None if non_visual_properties is None else non_visual_properties.attrib.get("id"),
        "name": ""
        if non_visual_properties is None
        else non_visual_properties.attrib.get("name", ""),
        "kind": kind,
        "text": "\n".join(paragraphs) if local_name == "sp" else "",
        "paragraphs": paragraphs if local_name == "sp" else [],
        "paragraph_runs": _fit_text_run_blocks(paragraph_runs, paragraphs)
        if local_name == "sp"
        else [],
        "relationship_ids": relationship_ids,
        "has_chart": any(rel_id for rel_id in relationship_ids if rel_id),
        "has_picture": local_name == "pic",
        "tables": [],
        "transform": transform,
        "effective_transform": transform,
        "_shape_index": shape_index,
        "_shell_shape_hint": True,
    }
    if local_name == "grpSp":
        hint["children"] = [
            _child_shape_hint(child, child_index)
            for child_index, child in enumerate(_shape_children(element))
        ]
    return hint


def _shape_children(element: ET.Element) -> list[ET.Element]:
    children: list[ET.Element] = []
    for child in list(element):
        local_name = _xml_local_name(child.tag)
        if local_name in {"nvGrpSpPr", "grpSpPr", "extLst"}:
            continue
        children.append(child)
    return children


def _shape_relationship_ids(element: ET.Element) -> list[str]:
    ids: list[str] = []
    for node in element.iter():
        for key, value in node.attrib.items():
            if key.startswith(f"{{{R_NS}}}") and value:
                ids.append(value)
    return ids


def _max_shape_id(element: ET.Element) -> int:
    ids: list[int] = [1]
    for non_visual_properties in _descendants(element, f"{{{P_NS}}}cNvPr"):
        try:
            ids.append(int(non_visual_properties.attrib.get("id", "1")))
        except ValueError:
            continue
    return max(ids)


def _table_payload(table: ET.Element) -> dict[str, Any]:
    rows: list[list[str]] = []
    for row in table.findall(f"{{{A_NS}}}tr"):
        cells: list[str] = []
        for cell in row.findall(f"{{{A_NS}}}tc"):
            cells.append("\n".join(_text_blocks_and_runs(cell)[0]))
        rows.append(cells)
    return {
        "rows": rows,
        "row_count": len(rows),
        "col_count": max((len(row) for row in rows), default=0),
    }


def _text_blocks_and_runs(root: ET.Element) -> tuple[list[str], list[list[str]]]:
    """Return paragraph texts and run texts from one walk over ``.//a:p``."""
    paragraphs: list[str] = []
    paragraph_runs: list[list[str]] = []
    for paragraph in _descendants(root, f"{{{A_NS}}}p"):
        parts: list[str] = []
        runs: list[str] = []
        for child in list(paragraph):
            local_name = _xml_local_name(child.tag)
            if local_name == "br":
                parts.append("\v")
            else:
                parts.append(
                    "".join(node.text or "" for node in _descendants(child, f"{{{A_NS}}}t"))
                )
            if local_name in {"r", "fld"}:
                text = child.find(f"{{{A_NS}}}t")
                runs.append("" if text is None else text.text or "")
        paragraphs.append("".join(parts))
        paragraph_runs.append(runs)
    return paragraphs, paragraph_runs


def _fit_text_run_blocks(
    paragraph_runs: list[list[str]],
    paragraphs: list[str],
) -> list[list[str]]:
    fitted = [list(runs) for runs in paragraph_runs[: len(paragraphs)]]
    while len(fitted) < len(paragraphs):
        paragraph = paragraphs[len(fitted)]
        fitted.append([paragraph] if paragraph else [])
    return fitted


def _shape_transform_payload(element: ET.Element) -> dict[str, int]:
    transform = element.find(f"{{{P_NS}}}xfrm")
    if transform is None:
        transform = _grandchild(element, f"{{{P_NS}}}spPr", f"{{{A_NS}}}xfrm")
    if transform is None:
        transform = _grandchild(element, f"{{{P_NS}}}grpSpPr", f"{{{A_NS}}}xfrm")
    offset = None if transform is None else transform.find(f"{{{A_NS}}}off")
    extents = None if transform is None else transform.find(f"{{{A_NS}}}ext")
    return {
        "x": 0 if offset is None else int(offset.attrib.get("x", "0")),
        "y": 0 if offset is None else int(offset.attrib.get("y", "0")),
        "cx": 0 if extents is None else int(extents.attrib.get("cx", "0")),
        "cy": 0 if extents is None else int(extents.attrib.get("cy", "0")),
    }


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _descendants(element: ET.Element, tag: str) -> Iterator[ET.Element]:
    """Yield ``element.findall(".//" + tag)`` matches without ElementPath dispatch."""
    for node in element.iter(tag):
        if node is not element:
            yield node


def _first_descendant(element: ET.Element, tag: str) -> ET.Element | None:
    return next(_descendants(element, tag), None)


def _grandchild(element: ET.Element, child_tag: str, tag: str) -> ET.Element | None:
    """Return ``element.find(child_tag + "/" + tag)`` without ElementPath dispatch."""
    for child in element.findall(child_tag):
        match = child.find(tag)
        if match is not None:
            return match
    return None


def _shape_tree(root: ET.Element) -> ET.Element | None:
    return _grandchild(root, f"{{{P_NS}}}cSld", f"{{{P_NS}}}spTree")


def package_relationships(
    package: zipfile.ZipFile,
    partname: str,
) -> dict[str, ET.Element]:
    try:
        root = package_xml(package, rels_part_for_package_part(partname))
    except (KeyError, ET.ParseError):
        return {}
    return {
        relationship.attrib["Id"]: relationship
        for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship")
        if relationship.attrib.get("Id")
    }


def slide_name(slide: Any) -> str:
    return str(slide_metadata(slide).get("name") or "")


def slide_hidden(slide: Any) -> bool:
    return bool(slide_metadata(slide).get("hidden", False))


def slide_notes_partname(slide: Any) -> str:
    partname = slide_metadata(slide).get("notes_part")
    if partname:
        return str(partname)
    raise AttributeError("notes slide part is unavailable")


def slide_notes_partname_for_part(path: Path, slide_part: str) -> str:
    try:
        with zipfile.ZipFile(path) as package:
            relationships = package_relationships(package, slide_part)
            for relationship in relationships.values():
                if relationship.attrib.get("Type", "").endswith("/notesSlide"):
                    return resolve_package_target(
                        slide_part,
                        relationship.attrib.get("Target", ""),
                    )
    except (FileNotFoundError, zipfile.BadZipFile):
        pass
    raise AttributeError("notes slide part is unavailable")
