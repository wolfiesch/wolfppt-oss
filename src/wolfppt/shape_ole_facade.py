"""OLE-object facade helpers for slide shapes."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    PackagePart,
    XmlElementProxy,
    package_xml_element as _package_xml_element,
    resolve_package_target as _resolve_package_target,
)
from .shape_xml import _shape_xml_element
from .slide_relationships import slide_relationship_info as _slide_relationship_info

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


class OleFormat:
    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def parent(self) -> Any:
        return self._shape

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @property
    def prog_id(self) -> str:
        ole = self._ole_element()
        if ole is None:
            return ""
        return ole.attrib.get("progId", "")

    @property
    def blob(self) -> bytes:
        partname = _shape_related_partname(self._shape, "/oleObject")
        if partname is None:
            raise AttributeError("OLE object package part is unavailable")
        return PackagePart(self._shape._slide._presentation, partname).blob

    @property
    def element(self) -> XmlElementProxy:
        graphic_data = _shape_xml_element_for_shape(self._shape).find(
            ".//{http://schemas.openxmlformats.org/drawingml/2006/main}graphicData"
        )
        if graphic_data is None:
            raise AttributeError("OLE object XML element is unavailable")
        return XmlElementProxy(graphic_data)

    @property
    def show_as_icon(self) -> bool:
        ole = self._ole_element()
        if ole is None:
            return False
        return ole.attrib.get("showAsIcon") in {"1", "true", "True"}

    def _ole_element(self) -> ET.Element | None:
        return _shape_xml_element_for_shape(self._shape).find(f".//{{{P_NS}}}oleObj")


def _shape_related_partname(shape: Any, relationship_type_suffix: str) -> str | None:
    if relationship_type_suffix == "/chart" and shape._payload.get("_chart_part"):
        return str(shape._payload["_chart_part"])
    for relationship_id in shape._payload.get("relationship_ids") or []:
        relationship = _slide_relationship_info(
            shape._slide._presentation.path,
            shape._slide.partname,
            str(relationship_id),
        )
        if relationship is None:
            continue
        relationship_type, target = relationship
        if relationship_type.endswith(relationship_type_suffix):
            return _resolve_package_target(shape._slide.partname, target)
    return None


def _shape_xml_element_for_shape(shape: Any) -> ET.Element:
    root = _package_xml_element(
        shape._slide._presentation.path,
        shape._slide.partname,
    )
    return _shape_xml_element(root._element, shape._payload)
