"""OPC relationship-closure copying shared by editing and deck assembly.

Importing a slide master from another deck and assembling decks both copy a
part together with every part it reaches through relationships, so the copier
and the relationship, content-type, and part-name helpers it needs live here.
"""

from __future__ import annotations

import posixpath
from collections import deque
from collections.abc import Mapping
from typing import Any
from xml.etree import ElementTree as ET

from .xml_helpers import content_types_xml as _content_types_xml

_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


class AssemblyRefusal(ValueError):
    """Raised when a package closure or source-bound assembly cannot be published safely."""


def copy_rooted_relationship_closure(
    destination: dict[str, bytes],
    source: Mapping[str, bytes],
    roots: Mapping[str, str],
) -> dict[str, str]:
    """Copy an OPC closure from explicit roots, preserving external relationships."""

    if "[Content_Types].xml" not in source:
        raise AssemblyRefusal("source package is missing [Content_Types].xml")
    mapping = dict(roots)
    reserved = set(destination)
    for source_part, destination_part in mapping.items():
        if source_part not in source:
            raise AssemblyRefusal(f"source part {source_part!r} is missing")
        if destination_part in reserved:
            raise AssemblyRefusal(
                f"destination part {destination_part!r} already exists"
            )
        reserved.add(destination_part)
        reserved.add(_rels_part(destination_part))
    queue: deque[str] = deque(mapping)
    while queue:
        source_part = queue.popleft()
        rels_name = _rels_part(source_part)
        if rels_name not in source:
            continue
        for relationship in _relationships(source[rels_name], source_part):
            if relationship.get("TargetMode") == "External":
                continue
            target = _relationship_target(source_part, relationship)
            if target not in source:
                raise AssemblyRefusal(
                    f"source relationship targets missing part {target!r}"
                )
            if target not in mapping:
                destination_part = _allocate_part_name(target, reserved)
                mapping[target] = destination_part
                reserved.add(destination_part)
                reserved.add(_rels_part(destination_part))
                queue.append(target)
    source_types = _content_types(source["[Content_Types].xml"], "source")
    destination_types = _content_types(
        destination["[Content_Types].xml"], "destination"
    )
    for source_part, destination_part in mapping.items():
        destination[destination_part] = source[source_part]
        _copy_content_type(
            source_types, destination_types, source_part, destination_part
        )
    for source_part, destination_part in mapping.items():
        source_rels = _rels_part(source_part)
        if source_rels in source:
            destination[_rels_part(destination_part)] = _rewritten_relationships(
                source[source_rels], source_part, destination_part, mapping
            )
    destination["[Content_Types].xml"] = _content_types_xml(destination_types["root"])
    return mapping


def _relationships(payload: bytes, owner: str) -> list[ET.Element]:
    root = ET.fromstring(payload)
    if root.tag != f"{{{_PKG_REL_NS}}}Relationships":
        raise AssemblyRefusal(f"relationships for {owner!r} have an invalid root")
    relationships = list(root.findall(f"{{{_PKG_REL_NS}}}Relationship"))
    ids = [relationship.get("Id") for relationship in relationships]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise AssemblyRefusal(f"relationships for {owner!r} have invalid identities")
    return relationships


def _rewritten_relationships(
    payload: bytes,
    source_owner: str,
    destination_owner: str,
    mapping: Mapping[str, str],
) -> bytes:
    root = ET.fromstring(payload)
    destination_by_id = {
        relationship.get("Id"): relationship
        for relationship in root.findall(f"{{{_PKG_REL_NS}}}Relationship")
    }
    for relationship in _relationships(payload, source_owner):
        target = destination_by_id.get(relationship.get("Id"))
        if target is None:
            raise AssemblyRefusal("relationship rewrite could not locate an identity")
        if relationship.get("TargetMode") == "External":
            continue
        source_target = _relationship_target(source_owner, relationship)
        destination_target = mapping.get(source_target)
        if destination_target is None:
            raise AssemblyRefusal("relationship closure omitted an internal dependency")
        fragment = relationship.get("Target", "").partition("#")[2]
        rewritten = _relative_target(destination_owner, destination_target)
        target.set("Target", f"{rewritten}#{fragment}" if fragment else rewritten)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _content_types(payload: bytes, label: str) -> dict[str, Any]:
    root = ET.fromstring(payload)
    if root.tag != f"{{{_CONTENT_NS}}}Types":
        raise AssemblyRefusal(f"{label} content types have an invalid root")
    overrides: dict[str, str] = {}
    defaults: dict[str, str] = {}
    for child in root:
        if child.tag == f"{{{_CONTENT_NS}}}Override":
            name = child.get("PartName")
            content_type = child.get("ContentType")
            if not name or not content_type or name in overrides:
                raise AssemblyRefusal(
                    f"{label} content types contain an invalid override"
                )
            overrides[name.lstrip("/")] = content_type
        elif child.tag == f"{{{_CONTENT_NS}}}Default":
            extension = child.get("Extension")
            content_type = child.get("ContentType")
            if not extension or not content_type or extension in defaults:
                raise AssemblyRefusal(
                    f"{label} content types contain an invalid default"
                )
            defaults[extension] = content_type
    return {"root": root, "overrides": overrides, "defaults": defaults}


def _copy_content_type(
    source: Mapping[str, Any],
    destination: Mapping[str, Any],
    source_part: str,
    destination_part: str,
) -> None:
    content_type = _part_content_type(source, source_part)
    extension = _extension(destination_part)
    existing = destination["overrides"].get(destination_part)
    if existing == content_type or (
        existing is None and destination["defaults"].get(extension) == content_type
    ):
        return
    destination["root"].append(
        ET.Element(
            f"{{{_CONTENT_NS}}}Override",
            {"PartName": f"/{destination_part}", "ContentType": content_type},
        )
    )
    destination["overrides"][destination_part] = content_type


def _part_content_type(content_types: Mapping[str, Any], part: str) -> str:
    value = content_types["overrides"].get(part)
    if value is not None:
        return value
    value = content_types["defaults"].get(_extension(part))
    if value is None:
        raise AssemblyRefusal(f"source part {part!r} has no content type")
    return value


def _relationship_target(owner: str, relationship: ET.Element) -> str:
    raw_target = relationship.get("Target")
    if not raw_target:
        raise AssemblyRefusal("relationship is missing a target")
    target, separator, fragment = raw_target.partition("#")
    if not target or separator and not fragment:
        raise AssemblyRefusal("relationship target is invalid")
    if target.startswith("/"):
        resolved = posixpath.normpath(target.lstrip("/"))
    else:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(owner), target))
    if resolved in {".", ""} or resolved == ".." or resolved.startswith(("../", "/")):
        raise AssemblyRefusal("relationship target escapes the package")
    return resolved


def _relative_target(owner: str, target: str) -> str:
    return posixpath.relpath(target, posixpath.dirname(owner) or ".")


def _rels_part(part: str) -> str:
    parent, filename = posixpath.split(part)
    return f"{parent}/_rels/{filename}.rels"


def _allocate_part_name(source_part: str, reserved: set[str]) -> str:
    if _is_slide_part(source_part):
        number = 1
        while True:
            candidate = f"ppt/slides/slide{number}.xml"
            if candidate not in reserved and _rels_part(candidate) not in reserved:
                return candidate
            number += 1
    parent, filename = posixpath.split(source_part)
    stem, suffix = posixpath.splitext(filename)
    candidate = source_part
    number = 2
    while candidate in reserved or _rels_part(candidate) in reserved:
        candidate = f"{parent}/{stem}-wolfppt-{number}{suffix}"
        number += 1
    return candidate


def _is_slide_part(part: str) -> bool:
    parent, filename = posixpath.split(part)
    return parent == "ppt/slides" and filename.endswith(".xml")


def _extension(part: str) -> str:
    suffix = posixpath.splitext(part)[1]
    if not suffix:
        raise AssemblyRefusal(f"part {part!r} has no extension for content type lookup")
    return suffix[1:]
