"""Slide layout package removal helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
    normalize_package_partname as _normalize_package_partname,
    rels_part_for_package_part as _rels_part_for_package_part,
    resolve_package_target as _resolve_package_target,
)


CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def apply_slide_layout_removals(
    input_path: Path,
    output_path: Path,
    partnames: list[str],
) -> None:
    removals = {
        _normalize_package_partname(partname).lstrip("/")
        for partname in partnames
    }
    if not removals:
        _copy_package_with_replacements(input_path, output_path, {})
        return

    with zipfile.ZipFile(input_path) as package:
        replacements: dict[str, bytes] = {}
        removed_parts = set(removals)
        for partname in removals:
            removed_parts.add(_rels_part_for_package_part(partname))
            master_part, rel_id = _master_relationship_for_layout(package, partname)
            if master_part and rel_id:
                _remove_master_layout_reference(
                    package,
                    replacements,
                    master_part,
                    rel_id,
                    partname,
                )
        replacements["[Content_Types].xml"] = _content_types_without_layouts(
            package,
            removals,
        )

    _copy_package_with_replacements(
        input_path,
        output_path,
        replacements,
        removals=removed_parts,
    )


def _master_relationship_for_layout(
    package: zipfile.ZipFile,
    layout_part: str,
) -> tuple[str | None, str | None]:
    for name in package.namelist():
        if not (
            name.startswith("ppt/slideMasters/_rels/slideMaster")
            and name.endswith(".xml.rels")
        ):
            continue
        master_part = f"ppt/slideMasters/{Path(name).name.removesuffix('.rels')}"
        try:
            root = ET.fromstring(package.read(name))
        except (KeyError, ET.ParseError):
            continue
        for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
            target = relationship.attrib.get("Target")
            rel_id = relationship.attrib.get("Id")
            if not target or not rel_id:
                continue
            if _resolve_package_target(master_part, target) == layout_part:
                return master_part, rel_id
    return None, None


def _remove_master_layout_reference(
    package: zipfile.ZipFile,
    replacements: dict[str, bytes],
    master_part: str,
    rel_id: str,
    layout_part: str,
) -> None:
    rels_part = _rels_part_for_package_part(master_part)
    rels_root = ET.fromstring(replacements.get(rels_part, package.read(rels_part)))
    for relationship in list(rels_root):
        target = relationship.attrib.get("Target")
        if relationship.attrib.get("Id") == rel_id or (
            target and _resolve_package_target(master_part, target) == layout_part
        ):
            rels_root.remove(relationship)
    ET.register_namespace("", PKG_REL_NS)
    replacements[rels_part] = ET.tostring(rels_root, encoding="utf-8")

    master_root = ET.fromstring(replacements.get(master_part, package.read(master_part)))
    layout_ids = master_root.find(f"{{{P_NS}}}sldLayoutIdLst")
    if layout_ids is not None:
        for layout_id in list(layout_ids):
            if layout_id.attrib.get(f"{{{R_NS}}}id") == rel_id:
                layout_ids.remove(layout_id)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)
    replacements[master_part] = ET.tostring(master_root, encoding="utf-8")


def _content_types_without_layouts(
    package: zipfile.ZipFile,
    removals: set[str],
) -> bytes:
    root = ET.fromstring(package.read("[Content_Types].xml"))
    partnames = {f"/{partname}" for partname in removals}
    for override in list(root.findall(f"{{{CONTENT_TYPES_NS}}}Override")):
        if override.attrib.get("PartName") in partnames:
            root.remove(override)
    ET.register_namespace("", CONTENT_TYPES_NS)
    return ET.tostring(root, encoding="utf-8")
