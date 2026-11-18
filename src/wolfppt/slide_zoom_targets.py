"""Slide, section and summary zoom target integrity ([MS-PPTX] Zoom Extensions).

A slide zoom names its target by presentation slide id
(``pslz:sldZmObj/@sldId``); section and summary zoom destinations name section
GUIDs (``sectionZmObj/@sectionId`` and ``summaryZmObj/@sectionId``).
Unambiguous fallback picture hyperlinks must open the target slide or the first
slide of the target section. Imported summary composite pictures do not imply
one hyperlink per destination. Structural edits must keep every target live.
"""

from __future__ import annotations

import posixpath
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .package_parts import rels_part_for_package_part, resolve_package_target
from .shape_xml import MC_NS, PSEZ_NS, PSLZ_NS

_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_PSUZ_NS = "http://schemas.microsoft.com/office/powerpoint/2016/summaryzoom"
_PRESENTATION_PART = "ppt/presentation.xml"


class ZoomTargetError(ValueError):
    """Raised when an edit would leave a zoom pointing at a missing target."""


@dataclass(frozen=True)
class ZoomReference:
    """One slide, section or summary destination on a presentation slide."""

    slide_part: str
    name: str
    kind: str
    target: str
    link_relationship_id: str | None


def presentation_slide_parts(package: zipfile.ZipFile, root: ET.Element) -> dict[int, str]:
    """Map presentation slide id to slide part, in ``p:sldIdLst`` order."""
    targets = _relationship_targets(package, _PRESENTATION_PART)
    parts: dict[int, str] = {}
    for entry in root.findall(f"{{{_P_NS}}}sldIdLst/{{{_P_NS}}}sldId"):
        part = targets.get(entry.get(f"{{{_R_NS}}}id") or "")
        if part is not None and (entry.get("id") or "").isdigit():
            parts[int(entry.get("id"))] = part
    return parts


def zoom_references(package: zipfile.ZipFile, slide_parts: Iterable[str]) -> list[ZoomReference]:
    """Return every zoom destination, including summary objects and grouped zooms."""
    references: list[ZoomReference] = []
    for part in slide_parts:
        payload = package.read(part)
        if not any(ns.encode() in payload for ns in (PSLZ_NS, PSEZ_NS, _PSUZ_NS)):
            continue
        for alternate in ET.fromstring(payload).iter(f"{{{MC_NS}}}AlternateContent"):
            references.extend(_zoom_references(part, alternate))
    return references


def section_zoom_hosts(
    package: zipfile.ZipFile, slide_parts: Iterable[str]
) -> dict[str, list[str]]:
    """Map section GUIDs to hosts of section zooms and summary destinations."""
    hosts: dict[str, list[str]] = {}
    for reference in zoom_references(package, slide_parts):
        if reference.kind in {"section", "summary"}:
            hosts.setdefault(reference.target.strip().upper(), []).append(reference.slide_part)
    return hosts


def reconcile_section_zoom_targets(
    package: zipfile.ZipFile,
    slide_parts_by_id: dict[int, str],
    sections: Iterable[tuple[str, list[int]]],
) -> dict[str, bytes]:
    """Retarget section and per-object summary fallbacks to section first slides.

    ``sections`` holds the settled ``(section id, slide ids)`` layout. Returns
    replacement relationship parts; raises :class:`ZoomTargetError` when a
    zoom's section no longer exists or has no slides left to open.
    """
    layout = {section_id.strip().upper(): slide_ids for section_id, slide_ids in sections}
    replacements: dict[str, bytes] = {}
    for reference in zoom_references(package, slide_parts_by_id.values()):
        if reference.kind not in {"section", "summary"}:
            continue
        slide_ids = layout.get(reference.target.strip().upper())
        if slide_ids is None:
            raise ZoomTargetError(
                f"{reference.kind} zoom {reference.name!r} on {reference.slide_part} targets "
                f"section {reference.target} that the edit removes"
            )
        first = next((slide_parts_by_id[i] for i in slide_ids if i in slide_parts_by_id), None)
        if first is None:
            raise ZoomTargetError(
                f"{reference.kind} zoom {reference.name!r} on {reference.slide_part} targets "
                f"section {reference.target} that the edit leaves without slides"
            )
        _retarget_link(package, reference, first, replacements)
    return replacements


def _zoom_references(part: str, alternate: ET.Element) -> list[ZoomReference]:
    choice = alternate.find(f"{{{MC_NS}}}Choice")
    if choice is None:
        return []
    identity = choice.find(f".//{{{_P_NS}}}cNvPr")
    name = identity.get("name", "") if identity is not None else ""
    slide_zoom = choice.find(f".//{{{PSLZ_NS}}}sldZmObj")
    section_zoom = choice.find(f".//{{{PSEZ_NS}}}sectionZmObj")
    if slide_zoom is not None:
        kind, target = "slide", slide_zoom.get("sldId", "")
    elif section_zoom is not None:
        kind, target = "section", section_zoom.get("sectionId", "")
    else:
        objects = choice.findall(f".//{{{_PSUZ_NS}}}summaryZmObj")
        return [
            ZoomReference(part, name, "summary", node.get("sectionId", ""), link_id)
            for node, link_id in zip(objects, _summary_links(alternate, objects), strict=True)
        ]
    link = alternate.find(f"{{{MC_NS}}}Fallback//{{{_A_NS}}}hlinkClick")
    return [
        ZoomReference(
            slide_part=part,
            name=name,
            kind=kind,
            target=target,
            link_relationship_id=None if link is None else link.get(f"{{{_R_NS}}}id"),
        )
    ]


def _summary_links(alternate: ET.Element, objects: list[ET.Element]) -> list[str | None]:
    """Associate ordered fallback pictures only when each destination has one.

    A composite picture cannot identify individual destination hyperlinks.
    Likewise a shared relationship cannot open distinct section destinations.
    Preserve those ambiguous links rather than repeatedly retargeting them.
    """
    pictures = alternate.findall(f"{{{MC_NS}}}Fallback//{{{_P_NS}}}pic")
    if len(pictures) != len(objects):
        return [None] * len(objects)
    links: list[str | None] = []
    destinations: dict[str, str] = {}
    ambiguous: set[str] = set()
    for picture, node in zip(pictures, objects, strict=True):
        link = picture.find(f"{{{_P_NS}}}nvPicPr/{{{_P_NS}}}cNvPr/{{{_A_NS}}}hlinkClick")
        link_id = None if link is None else link.get(f"{{{_R_NS}}}id")
        links.append(link_id)
        if link_id is not None:
            target = node.get("sectionId", "").strip().upper()
            if link_id in destinations and destinations[link_id] != target:
                ambiguous.add(link_id)
            destinations[link_id] = target
    return [None if link_id in ambiguous else link_id for link_id in links]


def _retarget_link(
    package: zipfile.ZipFile,
    reference: ZoomReference,
    target_part: str,
    replacements: dict[str, bytes],
) -> None:
    if reference.link_relationship_id is None:
        return
    rels_part = rels_part_for_package_part(reference.slide_part)
    payload = replacements.get(rels_part)
    if payload is None:
        payload = package.read(rels_part)
    root = ET.fromstring(payload)
    relationship = next(
        (
            item
            for item in root.findall(f"{{{_PKG_REL_NS}}}Relationship")
            if item.get("Id") == reference.link_relationship_id
        ),
        None,
    )
    if relationship is None:
        raise ZoomTargetError(
            f"zoom {reference.name!r} on {reference.slide_part} links through missing "
            f"relationship {reference.link_relationship_id}"
        )
    target, _, fragment = relationship.get("Target", "").partition("#")
    if resolve_package_target(reference.slide_part, target) == target_part:
        return
    relative = posixpath.relpath(target_part, posixpath.dirname(reference.slide_part))
    relationship.set("Target", f"{relative}#{fragment}" if fragment else relative)
    ET.register_namespace("", _PKG_REL_NS)
    replacements[rels_part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _relationship_targets(package: zipfile.ZipFile, part: str) -> dict[str, str]:
    rels_part = rels_part_for_package_part(part)
    if rels_part not in package.namelist():
        return {}
    return {
        item.get("Id", ""): resolve_package_target(part, item.get("Target", ""))
        for item in ET.fromstring(package.read(rels_part)).findall(f"{{{_PKG_REL_NS}}}Relationship")
        if item.get("TargetMode") != "External"
    }


__all__ = [
    "ZoomReference",
    "ZoomTargetError",
    "presentation_slide_parts",
    "reconcile_section_zoom_targets",
    "section_zoom_hosts",
    "zoom_references",
]
