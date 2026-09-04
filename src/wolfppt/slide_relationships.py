"""Slide relationship lookup helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .package_parts import rels_part_for_package_part as _rels_part_for_package_part

PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def slide_relationship_target(
    path: Path,
    slide_part: str,
    relationship_id: str,
    type_suffix: str,
) -> str | None:
    relationship = slide_relationship_info(path, slide_part, relationship_id)
    if relationship is None:
        return None
    relationship_type, target = relationship
    if not relationship_type.endswith(type_suffix):
        return None
    return target


def slide_relationship_info(
    path: Path,
    slide_part: str,
    relationship_id: str,
) -> tuple[str, str] | None:
    rels_part = _rels_part_for_package_part(slide_part)
    try:
        with zipfile.ZipFile(path) as package:
            root = ET.fromstring(package.read(rels_part))
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return None
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Id") != relationship_id:
            continue
        relationship_type = rel.attrib.get("Type", "")
        target = rel.attrib.get("Target")
        if not relationship_type or not target:
            return None
        return relationship_type, target
    return None
