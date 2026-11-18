"""Low-level output helpers for presentation saves."""

from __future__ import annotations

import os
import zipfile
from os import PathLike
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .core_properties import (
    _CORE_PROPERTIES_CONTENT_TYPE,
)
from .core_properties import (
    CORE_PROPERTIES_PARTNAME as _CORE_PROPERTIES_PARTNAME,
)
from .core_properties import (
    serialize_core_properties as _serialize_core_properties,
)
from .extended_property_edits import (
    PKG_REL_NS,
    _next_free_relationship_id,
    _serialize_relationships,
)
from .package_parts import CONTENT_TYPES_NS, copy_open_package_with_replacements
from .xml_helpers import content_types_xml


def is_file_like_output(value: Any) -> bool:
    return not isinstance(value, (str, bytes, PathLike)) and hasattr(value, "write")


def write_path_to_file_like(source_path: Path, output: Any) -> None:
    output.write(source_path.read_bytes())


def publish_staged_output(candidate_path: Path, destination: Path) -> None:
    """Atomically replace a destination with a complete staged candidate."""
    os.replace(candidate_path, destination)


def apply_core_properties_edits(
    input_path: Path,
    output_path: Path,
    values: dict[str, Any],
) -> None:
    replacements = {_CORE_PROPERTIES_PARTNAME: _serialize_core_properties(values)}
    with zipfile.ZipFile(input_path) as source:
        if _CORE_PROPERTIES_PARTNAME not in source.namelist():
            # Create the part and its OPC registrations as one staged package.
            rels_root = ET.fromstring(source.read("_rels/.rels"))
            rel_type = f"{PKG_REL_NS}/metadata/core-properties"
            if not any(
                rel.get("Type") == rel_type
                for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
            ):
                ET.SubElement(
                    rels_root,
                    f"{{{PKG_REL_NS}}}Relationship",
                    {
                        "Id": _next_free_relationship_id(rels_root),
                        "Type": rel_type,
                        "Target": _CORE_PROPERTIES_PARTNAME,
                    },
                )
                replacements["_rels/.rels"] = _serialize_relationships(rels_root)

            ct_root = ET.fromstring(source.read("[Content_Types].xml"))
            partname = f"/{_CORE_PROPERTIES_PARTNAME}"
            override = next(
                (
                    element
                    for element in ct_root.findall(f"{{{CONTENT_TYPES_NS}}}Override")
                    if element.get("PartName") == partname
                ),
                None,
            )
            if override is None:
                ET.SubElement(
                    ct_root,
                    f"{{{CONTENT_TYPES_NS}}}Override",
                    {
                        "PartName": partname,
                        "ContentType": _CORE_PROPERTIES_CONTENT_TYPE,
                    },
                )
                replacements["[Content_Types].xml"] = content_types_xml(ct_root)
            elif override.get("ContentType") != _CORE_PROPERTIES_CONTENT_TYPE:
                override.set("ContentType", _CORE_PROPERTIES_CONTENT_TYPE)
                replacements["[Content_Types].xml"] = content_types_xml(ct_root)
        copy_open_package_with_replacements(source, output_path, replacements)
