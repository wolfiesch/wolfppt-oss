"""PPTX/PPTM package complexity counters used by benchmark gates."""

from __future__ import annotations

import zipfile
from collections import Counter
from pathlib import Path
from typing import Final
from xml.etree import ElementTree as ET


DECK_COMPLEXITY_FEATURES: Final = (
    "slides",
    "shapes",
    "tables",
    "charts",
    "media",
    "embedded_objects",
)
DECK_COMPLEXITY_TOTAL_FIELDS: Final = {
    "slides": "total_slide_count",
    "shapes": "total_shape_count",
    "tables": "total_table_count",
    "charts": "total_chart_count",
    "media": "total_media_count",
    "embedded_objects": "total_embedded_object_count",
}
_PML_NS: Final = "http://schemas.openxmlformats.org/presentationml/2006/main"
_DML_NS: Final = "http://schemas.openxmlformats.org/drawingml/2006/main"


def deck_complexity_counts(path: Path) -> dict[str, int]:
    """Return coarse content counts for one PowerPoint package."""

    try:
        with zipfile.ZipFile(path) as package:
            names = package.namelist()
            slide_parts = _slide_parts(names)
            counts: Counter[str] = Counter(
                {
                    "slides": _slide_count(package, slide_parts),
                    "charts": _package_part_count(names, "ppt/charts/chart", ".xml"),
                    "media": _package_part_count(names, "ppt/media/", ""),
                    "embedded_objects": _package_part_count(names, "ppt/embeddings/", ""),
                }
            )
            for slide_part in slide_parts:
                _update_slide_complexity_counts(counts, package.read(slide_part))
    except zipfile.BadZipFile as exc:
        raise ValueError("deck package could not be inspected") from exc

    return {feature: int(counts[feature]) for feature in DECK_COMPLEXITY_FEATURES}


def _slide_parts(names: list[str]) -> list[str]:
    return sorted(
        name
        for name in names
        if name.startswith("ppt/slides/slide") and name.endswith(".xml")
    )


def _slide_count(package: zipfile.ZipFile, slide_parts: list[str]) -> int:
    try:
        presentation = package.read("ppt/presentation.xml")
    except KeyError:
        return len(slide_parts)
    try:
        root = ET.fromstring(presentation)
    except ET.ParseError as exc:
        raise ValueError("deck presentation metadata could not be inspected") from exc

    namespace = {"p": _PML_NS}
    slide_id_list = root.find("p:sldIdLst", namespace)
    if slide_id_list is None:
        return 0
    return len(slide_id_list.findall("p:sldId", namespace))


def _package_part_count(names: list[str], prefix: str, suffix: str) -> int:
    return sum(
        1
        for name in names
        if name.startswith(prefix)
        and (not suffix or name.endswith(suffix))
        and not name.endswith("/")
    )


def _update_slide_complexity_counts(counts: Counter[str], slide_xml: bytes) -> None:
    try:
        root = ET.fromstring(slide_xml)
    except ET.ParseError as exc:
        raise ValueError("deck slide metadata could not be inspected") from exc
    namespaces = {"p": _PML_NS, "a": _DML_NS}
    counts["shapes"] += sum(
        len(root.findall(f".//p:{tag}", namespaces))
        for tag in ("sp", "pic", "graphicFrame", "cxnSp", "grpSp")
    )
    counts["tables"] += len(root.findall(".//a:tbl", namespaces))
