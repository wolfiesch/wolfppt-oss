"""PPTX semantic extraction.

This module intentionally uses only the Python standard library. The harness
needs to inspect fixtures and candidate outputs before any third-party PPTX
library is installed.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

NS = {
    "p": P_NS,
    "a": A_NS,
    "r": R_NS,
    "rel": REL_NS,
}


@dataclass(frozen=True)
class Relationship:
    source: str
    id: str
    type: str
    target: str
    target_mode: str | None = None


@dataclass(frozen=True)
class Table:
    rows: list[list[str]]
    row_count: int
    col_count: int


@dataclass(frozen=True)
class Transform:
    x: int
    y: int
    cx: int
    cy: int


@dataclass(frozen=True)
class _CoordinateFrame:
    x: int
    y: int
    cx: int
    cy: int
    ch_x: int
    ch_y: int
    ch_cx: int
    ch_cy: int


@dataclass(frozen=True)
class Shape:
    id: str | None
    name: str | None
    kind: str
    text: str
    paragraphs: list[str] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    relationship_ids: list[str] = field(default_factory=list)
    has_chart: bool = False
    has_picture: bool = False
    has_group: bool = False
    transform: Transform | None = None
    effective_transform: Transform | None = None
    children: list["Shape"] = field(default_factory=list)


@dataclass(frozen=True)
class Slide:
    part: str
    shape_count: int
    texts: list[str]
    shapes: list[Shape]
    notes: list[str] = field(default_factory=list)
    has_transition: bool = False
    has_timing: bool = False


@dataclass(frozen=True)
class PresentationSemantics:
    format: str
    path: str
    part_count: int
    parts: list[str]
    has_vba: bool
    relationships: list[Relationship]
    slides: list[Slide]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def extract_semantics(path: str | Path) -> PresentationSemantics:
    """Extract a stable semantic summary from a PPTX/PPTM package."""

    deck_path = Path(path)
    with zipfile.ZipFile(deck_path) as zf:
        parts = sorted(zf.namelist())
        relationships = _extract_relationships(zf, parts)
        slide_parts = _ordered_slide_parts(zf, parts)
        notes_by_slide = _notes_by_slide(zf, relationships)
        slides = [
            _extract_slide(zf, slide_part, notes_by_slide.get(slide_part, []))
            for slide_part in slide_parts
        ]

    return PresentationSemantics(
        format="wolfppt.semantic.v1",
        path=str(deck_path),
        part_count=len(parts),
        parts=parts,
        has_vba=any(part.endswith("vbaProject.bin") for part in parts),
        relationships=relationships,
        slides=slides,
    )


def _extract_relationships(
    zf: zipfile.ZipFile, parts: list[str]
) -> list[Relationship]:
    rels: list[Relationship] = []
    for part in parts:
        if not part.endswith(".rels"):
            continue
        source = _rels_source(part)
        try:
            root = ET.fromstring(zf.read(part))
        except ET.ParseError:
            continue
        for rel in root.findall("rel:Relationship", NS):
            rels.append(
                Relationship(
                    source=source,
                    id=rel.attrib.get("Id", ""),
                    type=rel.attrib.get("Type", ""),
                    target=rel.attrib.get("Target", ""),
                    target_mode=rel.attrib.get("TargetMode"),
                )
            )
    return sorted(rels, key=lambda item: (item.source, _natural_key(item.id), item.target))


def _rels_source(rels_part: str) -> str:
    if rels_part == "_rels/.rels":
        return "/"
    prefix, name = rels_part.rsplit("/_rels/", 1)
    return f"{prefix}/{name.removesuffix('.rels')}"


def _ordered_slide_parts(zf: zipfile.ZipFile, parts: list[str]) -> list[str]:
    presentation_rels = {
        rel.id: rel
        for rel in _extract_relationships(zf, ["ppt/_rels/presentation.xml.rels"])
        if rel.type.endswith("/slide")
    }
    if "ppt/presentation.xml" in parts and presentation_rels:
        try:
            root = ET.fromstring(zf.read("ppt/presentation.xml"))
            ordered: list[str] = []
            for slide_id in root.findall(".//p:sldId", NS):
                rel_id = slide_id.attrib.get(f"{{{R_NS}}}id")
                rel = presentation_rels.get(rel_id or "")
                if rel:
                    ordered.append(_resolve_target("ppt/presentation.xml", rel.target))
            if ordered:
                return ordered
        except ET.ParseError:
            pass
    return sorted(
        [part for part in parts if re.fullmatch(r"ppt/slides/slide\d+\.xml", part)],
        key=_natural_key,
    )


def _notes_by_slide(
    zf: zipfile.ZipFile, relationships: list[Relationship]
) -> dict[str, list[str]]:
    notes: dict[str, list[str]] = {}
    for rel in relationships:
        if rel.source.startswith("ppt/slides/slide") and rel.type.endswith("/notesSlide"):
            notes_part = _resolve_target(rel.source, rel.target)
            try:
                notes[rel.source] = _extract_texts(ET.fromstring(zf.read(notes_part)))
            except (KeyError, ET.ParseError):
                notes[rel.source] = []
    return notes


def _extract_slide(zf: zipfile.ZipFile, part: str, notes: list[str]) -> Slide:
    try:
        root = ET.fromstring(zf.read(part))
    except ET.ParseError:
        return Slide(part=part, shape_count=0, texts=[], shapes=[], notes=notes)

    shapes = [_extract_shape(el) for el in _shape_elements(root)]
    texts = [shape.text for shape in shapes if shape.text]
    return Slide(
        part=part,
        shape_count=len(shapes),
        texts=texts,
        shapes=shapes,
        notes=notes,
        has_transition=root.find(".//p:transition", NS) is not None,
        has_timing=root.find(".//p:timing", NS) is not None,
    )


def _shape_elements(root: ET.Element) -> list[ET.Element]:
    elements: list[ET.Element] = []
    for child in root.findall(".//p:cSld/p:spTree/*", NS):
        tag = _local_name(child.tag)
        if tag in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}:
            elements.append(child)
    return elements


def _extract_shape(el: ET.Element, parent_frame: _CoordinateFrame | None = None) -> Shape:
    nv = el.find(".//p:cNvPr", NS)
    shape_id = nv.attrib.get("id") if nv is not None else None
    name = nv.attrib.get("name") if nv is not None else None
    paragraphs = _extract_texts(el)
    tables = [_extract_table(tbl) for tbl in el.findall(".//a:tbl", NS)]
    rel_ids = sorted(
        {
            value
            for key, value in _walk_attribs(el)
            if key == f"{{{R_NS}}}embed" or key == f"{{{R_NS}}}link" or key == f"{{{R_NS}}}id"
        }
    )
    kind = {
        "sp": "shape",
        "pic": "picture",
        "graphicFrame": "graphic_frame",
        "grpSp": "group",
        "cxnSp": "connector",
    }.get(_local_name(el.tag), "unknown")
    if kind == "graphic_frame" and el.find(".//p:oleObj", NS) is not None:
        kind = "ole_object"
    local_transform = _extract_transform(el)
    effective_transform = _apply_parent_transform(local_transform, parent_frame)
    child_frame = _group_frame(el, parent_frame)
    children = [_extract_shape(child, child_frame) for child in _shape_child_elements(el)]
    return Shape(
        id=shape_id,
        name=name,
        kind=kind,
        text="\n".join(paragraphs),
        paragraphs=paragraphs,
        tables=tables,
        relationship_ids=rel_ids,
        has_chart=el.find(".//c:chart", {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}) is not None,
        has_picture=_local_name(el.tag) == "pic",
        has_group=_local_name(el.tag) == "grpSp",
        transform=local_transform,
        effective_transform=effective_transform,
        children=children,
    )


def _shape_child_elements(root: ET.Element) -> list[ET.Element]:
    elements: list[ET.Element] = []
    for child in root:
        tag = _local_name(child.tag)
        if tag in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}:
            elements.append(child)
    return elements


def _extract_transform(el: ET.Element) -> Transform | None:
    xfrm = el.find("./p:spPr/a:xfrm", NS)
    if xfrm is None:
        xfrm = el.find("./p:grpSpPr/a:xfrm", NS)
    if xfrm is None:
        xfrm = el.find("./p:xfrm", NS)
    if xfrm is None:
        return None
    off = xfrm.find("./a:off", NS)
    ext = xfrm.find("./a:ext", NS)
    if off is None or ext is None:
        return None
    return Transform(
        x=int(off.attrib.get("x", "0")),
        y=int(off.attrib.get("y", "0")),
        cx=int(ext.attrib.get("cx", "0")),
        cy=int(ext.attrib.get("cy", "0")),
    )


def _group_frame(el: ET.Element, parent_frame: _CoordinateFrame | None) -> _CoordinateFrame | None:
    xfrm = el.find("./p:grpSpPr/a:xfrm", NS)
    if xfrm is None:
        return None
    local = _extract_transform(el)
    effective = _apply_parent_transform(local, parent_frame)
    if effective is None:
        return None
    ch_off = xfrm.find("./a:chOff", NS)
    ch_ext = xfrm.find("./a:chExt", NS)
    return _CoordinateFrame(
        x=effective.x,
        y=effective.y,
        cx=effective.cx,
        cy=effective.cy,
        ch_x=int(ch_off.attrib.get("x", "0")) if ch_off is not None else 0,
        ch_y=int(ch_off.attrib.get("y", "0")) if ch_off is not None else 0,
        ch_cx=int(ch_ext.attrib.get("cx", str(effective.cx))) if ch_ext is not None else effective.cx,
        ch_cy=int(ch_ext.attrib.get("cy", str(effective.cy))) if ch_ext is not None else effective.cy,
    )


def _apply_parent_transform(
    transform: Transform | None,
    parent_frame: _CoordinateFrame | None,
) -> Transform | None:
    if transform is None:
        return None
    if parent_frame is None:
        return transform
    return Transform(
        x=parent_frame.x
        + _scale_child_coordinate(
            transform.x - parent_frame.ch_x,
            parent_frame.cx,
            parent_frame.ch_cx,
        ),
        y=parent_frame.y
        + _scale_child_coordinate(
            transform.y - parent_frame.ch_y,
            parent_frame.cy,
            parent_frame.ch_cy,
        ),
        cx=_scale_child_coordinate(transform.cx, parent_frame.cx, parent_frame.ch_cx),
        cy=_scale_child_coordinate(transform.cy, parent_frame.cy, parent_frame.ch_cy),
    )


def _scale_child_coordinate(value: int, parent_extent: int, child_extent: int) -> int:
    if child_extent == 0:
        return value
    return round(value * parent_extent / child_extent)


def _extract_texts(root: ET.Element) -> list[str]:
    paragraphs: list[str] = []
    for paragraph in root.findall(".//a:p", NS):
        parts: list[str] = []
        for child in list(paragraph):
            if _local_name(child.tag) == "br":
                parts.append("\v")
            else:
                parts.append("".join(node.text or "" for node in child.findall(".//a:t", NS)))
        paragraphs.append("".join(parts))
    return paragraphs


def _extract_table(tbl: ET.Element) -> Table:
    rows: list[list[str]] = []
    for row in tbl.findall("./a:tr", NS):
        cells: list[str] = []
        for cell in row.findall("./a:tc", NS):
            cells.append("\n".join(_extract_texts(cell)))
        rows.append(cells)
    return Table(
        rows=rows,
        row_count=len(rows),
        col_count=max((len(row) for row in rows), default=0),
    )


def _walk_attribs(root: ET.Element) -> list[tuple[str, str]]:
    attrs: list[tuple[str, str]] = []
    for el in root.iter():
        attrs.extend(el.attrib.items())
    return attrs


def _resolve_target(source: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base = Path(source).parent
    normalized = (base / target).as_posix()
    parts: list[str] = []
    for part in normalized.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part and part != ".":
            parts.append(part)
    return "/".join(parts)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _natural_key(value: str) -> list[int | str]:
    return [int(chunk) if chunk.isdigit() else chunk for chunk in re.split(r"(\d+)", value)]
