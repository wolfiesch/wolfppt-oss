"""Package-level custom document property inspection and modification operations."""

from __future__ import annotations

import contextlib
import os
import posixpath
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .custom_properties import (
    CONTENT_TYPES_NS,
    CUSTOM_PROPERTIES_CONTENT_TYPE,
    CUSTOM_PROPERTIES_PARTNAME,
    CUSTOM_PROPERTIES_REL_TYPE,
    CUSTOM_PROPERTIES_REL_TYPES,
    CUSTOM_PROPERTY_FMTID,
    STRICT_CUSTOM_PROPERTIES_REL_TYPE,
    CustomProperties,
    CustomPropertiesRefusal,
    CustomPropertyRecord,
    _validate_and_normalize_value,
    _validate_property_name,
    read_custom_properties_profile,
    serialize_custom_properties,
)
from .extended_property_edits import package_is_strict
from .package_parts import (
    copy_open_package_with_replacements,
    resolve_package_target,
)
from .xml_helpers import content_types_xml

PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _serialize_relationships(root: ET.Element) -> bytes:
    """Serialize package relationships using the OPC required default namespace."""
    if root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise CustomPropertiesRefusal(f"root relationships element has invalid tag: {root.tag!r}")
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    match = re.search(rb"<(?P<prefix>[A-Za-z_][A-Za-z0-9_.-]*):Relationships(?=[\s>/])", payload)
    if match is None:
        return payload
    prefix = match.group("prefix").decode("ascii")
    qualified = re.compile(
        rb"(</?)" + re.escape(prefix.encode("ascii")) + rb":([A-Za-z_][\w.-]*)(?=[\s>/])"
    )
    normalized = qualified.sub(rb"\1\2", payload)
    return normalized.replace(
        f' xmlns:{prefix}="{PKG_REL_NS}"'.encode("ascii"),
        f' xmlns="{PKG_REL_NS}"'.encode("ascii"),
        1,
    )


def _next_free_relationship_id(root: ET.Element) -> str:
    """Return the next monotonic rIdN relationship identifier not currently in use."""
    existing_ids: set[int] = set()
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        rel_id = rel.attrib.get("Id", "")
        if rel_id.startswith("rId"):
            with contextlib.suppress(ValueError):
                existing_ids.add(int(rel_id[3:]))
    next_num = max(existing_ids, default=0) + 1
    return f"rId{next_num}"


def resolve_custom_properties_part(
    package: zipfile.ZipFile,
) -> tuple[str | None, str | None]:
    """Resolve the custom properties relationship ID and target part path from an open package.

    Returns ``(relationship_id, part_name)`` if present, or ``(None, None)`` if the package
    has no custom properties relationship. Raises ``CustomPropertiesRefusal`` on malformed,
    ambiguous, or unsafe packages.
    """
    if "_rels/.rels" not in package.namelist():
        return None, None

    try:
        rels_root = ET.fromstring(package.read("_rels/.rels"))
    except ET.ParseError as exc:
        raise CustomPropertiesRefusal("package root relationships are malformed XML") from exc

    if rels_root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise CustomPropertiesRefusal(
            f"package root relationships has invalid root tag: {rels_root.tag!r}"
        )

    matching_rels: list[ET.Element] = []
    for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Type") in CUSTOM_PROPERTIES_REL_TYPES:
            matching_rels.append(rel)

    if not matching_rels:
        return None, None

    if len(matching_rels) > 1:
        raise CustomPropertiesRefusal(
            "package declares multiple custom-properties relationships in _rels/.rels: "
            f"{len(matching_rels)}"
        )

    rel = matching_rels[0]
    rel_id = rel.attrib.get("Id")
    if not rel_id:
        raise CustomPropertiesRefusal(
            "custom-properties relationship has missing or empty Id attribute"
        )

    if rel.attrib.get("TargetMode") == "External":
        raise CustomPropertiesRefusal("custom-properties relationship has external target mode")

    raw_target = rel.attrib.get("Target", "").strip()
    if not raw_target:
        raise CustomPropertiesRefusal("custom-properties relationship target is empty")

    norm_target = resolve_package_target("", raw_target)
    if not norm_target or norm_target.startswith(("../", "/")):
        raise CustomPropertiesRefusal(
            f"custom-properties relationship target escapes package root: {raw_target!r}"
        )

    clean_target = posixpath.normpath(norm_target).lstrip("/")
    if clean_target.startswith("../") or ".." in clean_target.split("/"):
        raise CustomPropertiesRefusal(
            f"custom-properties relationship target uses illegal traversal: {raw_target!r}"
        )

    if clean_target not in package.namelist():
        raise CustomPropertiesRefusal(
            f"custom-properties part {clean_target!r} declared in _rels/.rels "
            "does not exist in package"
        )

    if "[Content_Types].xml" in package.namelist():
        try:
            ct_root = ET.fromstring(package.read("[Content_Types].xml"))
        except ET.ParseError as exc:
            raise CustomPropertiesRefusal("package [Content_Types].xml is malformed XML") from exc

        override_path = f"/{clean_target}"
        for override in ct_root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
            if override.attrib.get("PartName") == override_path:
                declared_ct = override.attrib.get("ContentType")
                if declared_ct != CUSTOM_PROPERTIES_CONTENT_TYPE:
                    raise CustomPropertiesRefusal(
                        f"custom-properties part {clean_target!r} declared with invalid "
                        f"content type {declared_ct!r}"
                    )
                break

    return rel_id, clean_target


def apply_custom_properties_edits(
    input_path: Path | str,
    output_path: Path | str,
    edits: Any,
) -> None:
    """Apply custom properties modifications from an input package to an output path."""
    source_path = Path(input_path)
    dest_path = Path(output_path)

    with zipfile.ZipFile(source_path) as source:
        existing_rel_id, existing_part_name = resolve_custom_properties_part(source)

        if existing_part_name is not None:
            existing_records, strict = read_custom_properties_profile(
                source.read(existing_part_name)
            )
        else:
            existing_records = {}
            strict = package_is_strict(source)

        target_records: dict[str, CustomPropertyRecord] = {}

        if isinstance(edits, CustomProperties):
            target_records = {k: v.copy() for k, v in edits._records.items()}
        elif hasattr(edits, "records") and isinstance(edits.records, dict):
            target_records = {k: v.copy() for k, v in edits.records.items()}
        elif isinstance(edits, dict):
            existing_pids = {r.pid for r in existing_records.values()}
            next_pid = max(existing_pids, default=1)

            for key, val in edits.items():
                name = _validate_property_name(key)
                if name in existing_records:
                    existing = existing_records[name]
                    if existing.val_type == "variant":
                        if val is not existing.value and val != existing.value:
                            raise CustomPropertiesRefusal(
                                "cannot destructively rewrite unsupported property variant "
                                f"{name!r}"
                            )
                        target_records[name] = existing.copy()
                    else:
                        norm_val, val_type = _validate_and_normalize_value(
                            val, existing_type=existing.val_type
                        )
                        target_records[name] = CustomPropertyRecord(
                            name=name,
                            value=norm_val,
                            pid=existing.pid,
                            fmtid=existing.fmtid,
                            val_type=val_type,
                        )
                else:
                    norm_val, val_type = _validate_and_normalize_value(val)
                    next_pid += 1
                    target_records[name] = CustomPropertyRecord(
                        name=name,
                        value=norm_val,
                        pid=next_pid,
                        fmtid=CUSTOM_PROPERTY_FMTID,
                        val_type=val_type,
                    )
        elif edits is None:
            target_records = {}
        else:
            raise TypeError(f"unsupported custom property edits type: {type(edits).__name__!r}")

        replacements: dict[str, bytes] = {}
        removals: set[str] = set()

        if not target_records:
            if existing_part_name is not None:
                removals.add(existing_part_name)

                if "_rels/.rels" in source.namelist():
                    rels_root = ET.fromstring(source.read("_rels/.rels"))
                    removed_rel = False
                    for rel in list(rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")):
                        if rel.attrib.get("Type") in CUSTOM_PROPERTIES_REL_TYPES:
                            rels_root.remove(rel)
                            removed_rel = True
                    if removed_rel:
                        replacements["_rels/.rels"] = _serialize_relationships(rels_root)

                if "[Content_Types].xml" in source.namelist():
                    ct_root = ET.fromstring(source.read("[Content_Types].xml"))
                    target_override = f"/{existing_part_name.lstrip('/')}"
                    removed_override = False
                    for override in list(ct_root.findall(f"{{{CONTENT_TYPES_NS}}}Override")):
                        if override.attrib.get("PartName") == target_override:
                            ct_root.remove(override)
                            removed_override = True
                    if removed_override:
                        replacements["[Content_Types].xml"] = content_types_xml(ct_root)
        else:
            target_part = existing_part_name or CUSTOM_PROPERTIES_PARTNAME
            serialized_xml = serialize_custom_properties(
                list(target_records.values()), strict=strict
            )
            replacements[target_part] = serialized_xml

            if existing_rel_id is None:
                if "_rels/.rels" in source.namelist():
                    rels_root = ET.fromstring(source.read("_rels/.rels"))
                else:
                    rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
                free_id = _next_free_relationship_id(rels_root)
                ET.SubElement(
                    rels_root,
                    f"{{{PKG_REL_NS}}}Relationship",
                    {
                        "Id": free_id,
                        "Type": (
                            STRICT_CUSTOM_PROPERTIES_REL_TYPE
                            if strict
                            else CUSTOM_PROPERTIES_REL_TYPE
                        ),
                        "Target": target_part,
                    },
                )
                replacements["_rels/.rels"] = _serialize_relationships(rels_root)

            if "[Content_Types].xml" in source.namelist():
                ct_root = ET.fromstring(source.read("[Content_Types].xml"))
            else:
                ct_root = ET.Element(f"{{{CONTENT_TYPES_NS}}}Types")
            target_override = f"/{target_part.lstrip('/')}"
            override_elem = None
            for override in ct_root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
                if override.attrib.get("PartName") == target_override:
                    override_elem = override
                    break
            if override_elem is None:
                ET.SubElement(
                    ct_root,
                    f"{{{CONTENT_TYPES_NS}}}Override",
                    {
                        "PartName": target_override,
                        "ContentType": CUSTOM_PROPERTIES_CONTENT_TYPE,
                    },
                )
                replacements["[Content_Types].xml"] = content_types_xml(ct_root)
            elif override_elem.attrib.get("ContentType") != CUSTOM_PROPERTIES_CONTENT_TYPE:
                override_elem.attrib["ContentType"] = CUSTOM_PROPERTIES_CONTENT_TYPE
                replacements["[Content_Types].xml"] = content_types_xml(ct_root)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() == dest_path.resolve():
            staged = dest_path.with_name(f".{dest_path.name}.stage-{uuid.uuid4().hex[:8]}")
            try:
                copy_open_package_with_replacements(source, staged, replacements, removals)
                os.replace(staged, dest_path)
            finally:
                if staged.exists():
                    with contextlib.suppress(OSError):
                        staged.unlink()
        else:
            copy_open_package_with_replacements(source, dest_path, replacements, removals)


__all__ = [
    "apply_custom_properties_edits",
    "resolve_custom_properties_part",
]
