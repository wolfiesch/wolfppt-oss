"""Presentation slide-size read and write helpers."""

from __future__ import annotations

import zipfile
from numbers import Integral
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements
from .slide_metadata import presentation_partname


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
MIN_SLIDE_SIZE_EMU = 914400
MAX_SLIDE_SIZE_EMU = 51206400
DEFAULT_SLIDE_SIZE = {"cx": 9144000, "cy": 6858000}


def presentation_slide_size(presentation: Any) -> dict[str, int]:
    if presentation._slide_size is not None:
        return dict(presentation._slide_size)
    size = read_presentation_slide_size(presentation.path)
    presentation._slide_size = size
    return dict(size)


def read_presentation_slide_size(path: Path) -> dict[str, int]:
    try:
        with zipfile.ZipFile(path) as package:
            root = ET.fromstring(package.read(presentation_partname(path)))
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return dict(DEFAULT_SLIDE_SIZE)
    slide_size = root.find(f"{{{P_NS}}}sldSz")
    if slide_size is None:
        return dict(DEFAULT_SLIDE_SIZE)
    return {
        "cx": int(slide_size.attrib.get("cx", str(DEFAULT_SLIDE_SIZE["cx"]))),
        "cy": int(slide_size.attrib.get("cy", str(DEFAULT_SLIDE_SIZE["cy"]))),
    }


def coerce_slide_size_emu(value: Any, name: str) -> int:
    if not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integral EMU value")
    emu = int(value)
    if not MIN_SLIDE_SIZE_EMU <= emu <= MAX_SLIDE_SIZE_EMU:
        raise ValueError(
            f"{name} must be in range({MIN_SLIDE_SIZE_EMU}, "
            f"{MAX_SLIDE_SIZE_EMU}), got {emu}"
        )
    return emu


def apply_presentation_size_edits(
    input_path: Path,
    output_path: Path,
    size_edits: dict[str, int],
) -> None:
    presentation_part = presentation_partname(input_path)
    with zipfile.ZipFile(input_path) as package:
        root = ET.fromstring(package.read(presentation_part))
    slide_size = presentation_slide_size_element(root)
    for attr in ("cx", "cy"):
        if attr in size_edits:
            slide_size.set(attr, str(size_edits[attr]))
    copy_package_with_replacements(
        input_path,
        output_path,
        {
            presentation_part: ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
        },
    )


def presentation_slide_size_element(root: ET.Element) -> ET.Element:
    slide_size = root.find(f"{{{P_NS}}}sldSz")
    if slide_size is not None:
        return slide_size
    slide_size = ET.Element(
        f"{{{P_NS}}}sldSz",
        {"cx": "9144000", "cy": "6858000", "type": "screen4x3"},
    )
    children = list(root)
    insert_at = len(children)
    for index, child in enumerate(children):
        local_name = _xml_local_name(child.tag)
        if local_name in {"notesSz", "smartTags", "embeddedFontLst", "custShowLst"}:
            insert_at = index
            break
    root.insert(insert_at, slide_size)
    return slide_size


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
