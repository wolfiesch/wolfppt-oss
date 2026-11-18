"""Package-level extended document property inspection and modification operations."""

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

from .extended_properties import (
    _SNAKE_TO_CANONICAL,
    CONTENT_TYPES_NS,
    EXTENDED_PROPERTIES_CONTENT_TYPE,
    EXTENDED_PROPERTIES_PARTNAME,
    EXTENDED_PROPERTIES_REL_TYPE,
    EXTENDED_PROPERTIES_REL_TYPES,
    STRICT_EXTENDED_PROPERTIES_REL_TYPE,
    ExtendedProperties,
    ExtendedPropertiesRefusal,
    ExtendedPropertiesSnapshot,
    _validate_bool,
    _validate_total_time,
    _validate_xml_text,
    read_extended_properties,
    serialize_extended_properties,
)
from .package_parts import (
    copy_open_package_with_replacements,
    resolve_package_target,
)
from .xml_helpers import content_types_xml

PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_STRICT_OOXML = "http://purl.oclc.org/ooxml/"


def package_is_strict(package: zipfile.ZipFile) -> bool:
    """True when the package's officeDocument root relationship uses a strict type.

    A package without readable root relationships, or without an officeDocument
    relationship, is not strict.
    """
    if "_rels/.rels" not in package.namelist():
        return False
    try:
        rels_root = ET.fromstring(package.read("_rels/.rels"))
    except ET.ParseError:
        return False
    return any(
        rel.attrib.get("Type", "").startswith(_STRICT_OOXML)
        and rel.attrib.get("Type", "").endswith("/officeDocument")
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
    )


def _serialize_relationships(root: ET.Element) -> bytes:
    """Serialize package relationships using the OPC required default namespace."""
    if root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise ExtendedPropertiesRefusal(f"root relationships element has invalid tag: {root.tag!r}")
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


def resolve_extended_properties_part(
    package: zipfile.ZipFile,
) -> tuple[str | None, str | None]:
    """Resolve the extended properties relationship ID and target part path from an open package.

    Returns ``(relationship_id, part_name)`` if present, or ``(None, None)`` if the package
    has no extended properties relationship. Raises ``ExtendedPropertiesRefusal`` on malformed,
    ambiguous, or unsafe packages.
    """
    if "_rels/.rels" not in package.namelist():
        return None, None

    try:
        rels_root = ET.fromstring(package.read("_rels/.rels"))
    except ET.ParseError as exc:
        raise ExtendedPropertiesRefusal("package root relationships are malformed XML") from exc

    if rels_root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise ExtendedPropertiesRefusal(
            f"package root relationships has invalid root tag: {rels_root.tag!r}"
        )

    matching_rels: list[ET.Element] = []
    for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Type") in EXTENDED_PROPERTIES_REL_TYPES:
            matching_rels.append(rel)

    if not matching_rels:
        return None, None

    if len(matching_rels) > 1:
        raise ExtendedPropertiesRefusal(
            "package declares multiple extended-properties relationships in _rels/.rels: "
            f"{len(matching_rels)}"
        )

    rel = matching_rels[0]
    rel_id = rel.attrib.get("Id")
    if not rel_id:
        raise ExtendedPropertiesRefusal(
            "extended-properties relationship has missing or empty Id attribute"
        )

    if rel.attrib.get("TargetMode") == "External":
        raise ExtendedPropertiesRefusal("extended-properties relationship has external target mode")

    raw_target = rel.attrib.get("Target", "").strip()
    if not raw_target:
        raise ExtendedPropertiesRefusal("extended-properties relationship target is empty")

    norm_target = resolve_package_target("", raw_target)
    if not norm_target or norm_target.startswith(("../", "/")):
        raise ExtendedPropertiesRefusal(
            f"extended-properties relationship target escapes package root: {raw_target!r}"
        )

    clean_target = posixpath.normpath(norm_target).lstrip("/")
    if clean_target.startswith("../") or ".." in clean_target.split("/"):
        raise ExtendedPropertiesRefusal(
            f"extended-properties relationship target uses illegal traversal: {raw_target!r}"
        )

    if clean_target not in package.namelist():
        raise ExtendedPropertiesRefusal(
            f"extended-properties part {clean_target!r} declared in _rels/.rels "
            "does not exist in package"
        )

    if "[Content_Types].xml" in package.namelist():
        try:
            ct_root = ET.fromstring(package.read("[Content_Types].xml"))
        except ET.ParseError as exc:
            raise ExtendedPropertiesRefusal("package [Content_Types].xml is malformed XML") from exc

        override_path = f"/{clean_target}"
        for override in ct_root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
            if override.attrib.get("PartName") == override_path:
                declared_ct = override.attrib.get("ContentType")
                if declared_ct != EXTENDED_PROPERTIES_CONTENT_TYPE:
                    raise ExtendedPropertiesRefusal(
                        f"extended-properties part {clean_target!r} declared with invalid "
                        f"content type {declared_ct!r}"
                    )
                break

    return rel_id, clean_target


def _validate_and_normalize_edit(key: str, val: Any) -> tuple[str, Any]:
    """Validate and normalize one extended property key/value pair."""
    canonical_key = _SNAKE_TO_CANONICAL.get(key, key)
    if canonical_key in (
        "Company",
        "Manager",
        "Application",
        "AppVersion",
        "Template",
        "HyperlinkBase",
    ):
        norm_val = _validate_xml_text(val, canonical_key)
        return canonical_key, norm_val
    if canonical_key in (
        "SharedDoc",
        "ScaleCrop",
        "LinksUpToDate",
        "HyperlinksChanged",
    ):
        norm_val = _validate_bool(val, canonical_key)
        return canonical_key, norm_val
    if canonical_key == "TotalTime":
        norm_val = _validate_total_time(val, canonical_key)
        return canonical_key, norm_val
    if isinstance(val, str):
        norm_val = _validate_xml_text(val, canonical_key)
        return canonical_key, norm_val
    if isinstance(val, bool):
        return canonical_key, val
    if isinstance(val, int):
        return canonical_key, val
    raise TypeError(
        f"unsupported extended property value type for {canonical_key!r}: {type(val).__name__!r}"
    )


def apply_extended_properties_edits(
    input_path: Path | str,
    output_path: Path | str,
    edits: Any,
) -> None:
    """Apply extended properties modifications from an input package to an output path."""
    source_path = Path(input_path)
    dest_path = Path(output_path)

    if edits is None:
        if source_path.resolve() != dest_path.resolve():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(source_path) as source:
                copy_open_package_with_replacements(source, dest_path, {})
        return

    with zipfile.ZipFile(source_path) as source:
        _existing_rel_id, existing_part_name = resolve_extended_properties_part(source)
        values: dict[str, Any] = {}
        modified_keys: set[str] = set()
        raw_root: ET.Element | None = None
        raw_elements: dict[str, ET.Element] = {}

        if isinstance(edits, ExtendedProperties):
            snapshot = edits._snapshot()
            values = dict(snapshot)
            modified_keys = set(snapshot.modified_keys)
            raw_root = snapshot.raw_root
            raw_elements = snapshot.raw_elements
        elif isinstance(edits, ExtendedPropertiesSnapshot):
            values = dict(edits)
            modified_keys = set(edits.modified_keys)
            raw_root = edits.raw_root
            raw_elements = edits.raw_elements
        elif isinstance(edits, dict):
            for k, v in edits.items():
                norm_k, norm_v = _validate_and_normalize_edit(k, v)
                values[norm_k] = norm_v
                modified_keys.add(norm_k)
        else:
            raise TypeError(f"unsupported extended property edits type: {type(edits).__name__!r}")

        # If existing part is present, load its XML if we don't already have a raw_root
        if existing_part_name is not None and raw_root is None:
            parsed = read_extended_properties(source.read(existing_part_name))
            raw_root = parsed["raw_root"]
            raw_elements = parsed["raw_elements"]
            # For non-modified keys, existing values stay preserved
            for k, v in parsed["values"].items():
                if k not in values:
                    values[k] = v

        # Validate each modified property
        for k in list(modified_keys):
            if k in values:
                norm_k, norm_v = _validate_and_normalize_edit(k, values[k])
                values[norm_k] = norm_v
                if norm_k != k:
                    modified_keys.remove(k)
                    modified_keys.add(norm_k)

        replacements: dict[str, bytes] = {}
        removals: set[str] = set()

        if existing_part_name is not None:
            if modified_keys:
                target_part = existing_part_name
                serialized_xml = serialize_extended_properties(
                    values=values,
                    modified_keys=modified_keys,
                    raw_elements=raw_elements,
                    raw_root=raw_root,
                )
                replacements[target_part] = serialized_xml
        else:
            # Extended properties part is absent
            if modified_keys:
                target_part = EXTENDED_PROPERTIES_PARTNAME
                strict = package_is_strict(source)
                serialized_xml = serialize_extended_properties(
                    values=values,
                    modified_keys=modified_keys,
                    strict=strict,
                )
                replacements[target_part] = serialized_xml

                # Add relationship in _rels/.rels if not present
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
                            STRICT_EXTENDED_PROPERTIES_REL_TYPE
                            if strict
                            else EXTENDED_PROPERTIES_REL_TYPE
                        ),
                        "Target": target_part,
                    },
                )
                replacements["_rels/.rels"] = _serialize_relationships(rels_root)

                # Add Override in [Content_Types].xml
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
                            "ContentType": EXTENDED_PROPERTIES_CONTENT_TYPE,
                        },
                    )
                    replacements["[Content_Types].xml"] = content_types_xml(ct_root)
                elif override_elem.attrib.get("ContentType") != EXTENDED_PROPERTIES_CONTENT_TYPE:
                    override_elem.attrib["ContentType"] = EXTENDED_PROPERTIES_CONTENT_TYPE
                    replacements["[Content_Types].xml"] = content_types_xml(ct_root)

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() == dest_path.resolve():
            if not replacements and not removals:
                return
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
    "apply_extended_properties_edits",
    "package_is_strict",
    "resolve_extended_properties_part",
]
