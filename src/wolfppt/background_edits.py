"""Part-scoped background fill edits for slide-like XML parts."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import set_solid_fill_color as _set_solid_fill_color
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
    normalize_package_partname as _normalize_package_partname,
)


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def apply_background_fill_edits(
    input_path: Path,
    output_path: Path,
    solid_edits: list[str],
    background_edits: list[str],
    color_edits: list[tuple[str, str | dict[str, Any]]],
) -> None:
    edits: dict[str, dict[str, Any]] = {}
    for partname in solid_edits:
        edits[_normalize_package_partname(partname).lstrip("/")] = {"type": "solid"}
    for partname in background_edits:
        edits[_normalize_package_partname(partname).lstrip("/")] = {
            "type": "background"
        }
    for partname, rgb in color_edits:
        payload = edits.setdefault(
            _normalize_package_partname(partname).lstrip("/"),
            {"type": "solid"},
        )
        payload["type"] = "solid"
        payload["rgb"] = rgb

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        for partname, edit in edits.items():
            root = ET.fromstring(package.read(partname))
            common_slide_data = root.find(f"{{{P_NS}}}cSld")
            if common_slide_data is None:
                raise ValueError(
                    f"slide part {partname} has no <p:cSld> common slide data; "
                    "cannot apply background edits"
                )
            background_properties = _background_properties(common_slide_data)
            _replace_fill(background_properties, str(edit["type"]), edit.get("rgb"))
            _register_namespaces()
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _background_properties(common_slide_data: ET.Element) -> ET.Element:
    background = common_slide_data.find(f"{{{P_NS}}}bg")
    if background is None:
        background = ET.Element(f"{{{P_NS}}}bg")
        common_slide_data.insert(_background_insert_index(common_slide_data), background)
    background_properties = background.find(f"{{{P_NS}}}bgPr")
    if background_properties is None:
        background.clear()
        background_properties = ET.SubElement(background, f"{{{P_NS}}}bgPr")
    if background_properties.find(f"{{{A_NS}}}effectLst") is None:
        ET.SubElement(background_properties, f"{{{A_NS}}}effectLst")
    return background_properties


def _background_insert_index(common_slide_data: ET.Element) -> int:
    for index, child in enumerate(list(common_slide_data)):
        if _local_name(child.tag) == "spTree":
            return index
    return 0


def _replace_fill(
    background_properties: ET.Element,
    fill_type: str,
    color: str | dict[str, Any] | None,
) -> None:
    for child in list(background_properties):
        if _local_name(child.tag).endswith("Fill"):
            background_properties.remove(child)
    if fill_type == "background":
        fill = ET.Element(f"{{{A_NS}}}noFill")
    elif fill_type == "solid":
        fill = ET.Element(f"{{{A_NS}}}solidFill")
        if color is not None:
            _set_solid_fill_color(fill, color)
    else:
        raise ValueError(f"unsupported background fill type: {fill_type}")
    background_properties.insert(0, fill)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _register_namespaces() -> None:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)
