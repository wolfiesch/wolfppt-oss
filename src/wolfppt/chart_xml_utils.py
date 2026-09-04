"""Shared Chart XML namespace and scalar helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def chart_title_element_text(title: ET.Element | None) -> str:
    if title is None:
        return ""
    rich = title.find(f"{{{C_NS}}}tx/{{{C_NS}}}rich")
    if rich is None:
        return ""
    paragraphs: list[str] = []
    for paragraph in rich.findall(f"{{{A_NS}}}p"):
        paragraphs.append(
            "".join(
                text_node.text or ""
                for text_node in paragraph.findall(f".//{{{A_NS}}}t")
            )
        )
    return "\n".join(paragraphs)


def child_val(element: ET.Element, child_name: str) -> str | None:
    child = element.find(f"{{{C_NS}}}{child_name}")
    if child is None:
        return None
    return child.attrib.get("val")


def xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def xml_bool_value(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value not in {"0", "false", "False"}


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def optional_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
