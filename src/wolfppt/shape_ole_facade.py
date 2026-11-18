"""OLE-object facade helpers for slide shapes."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    PackagePart,
    XmlElementProxy,
    open_package_source,
    package_part_content_type,
    rels_part_for_package_part,
)
from .package_parts import (
    package_xml_element as _package_xml_element,
)
from .package_parts import (
    resolve_package_target as _resolve_package_target,
)
from .shape_xml import _shape_xml_element
from .slide_relationships import slide_relationship_info as _slide_relationship_info
from .xml_helpers import find_ooxml

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class OleObjectRefusal(ValueError):
    """An OLE payload or icon cannot be extracted from an internal package part."""


class _OlePart(PackagePart):
    @property
    def blob(self) -> bytes:
        with open_package_source(self._presentation._source_path) as package:
            return package.read(self._partname.lstrip("/"))

    @property
    def content_type(self) -> str:
        return package_part_content_type(self._presentation._source_path, self._partname)


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
        ole = self._ole_element()
        if ole is None or ole.find(f"{{{P_NS}}}link") is not None:
            raise OleObjectRefusal("embedded_ole_required")
        return self._related_part(ole.get(f"{{{R_NS}}}id"), {"/oleObject", "/package"}).blob

    @property
    def icon(self) -> PackagePart:
        """Return the exact stored icon/preview part, without decoding or re-encoding it."""
        ole = self._ole_element()
        blip = None if ole is None else ole.find(f"{{{P_NS}}}pic/{{{P_NS}}}blipFill/{{{A_NS}}}blip")
        if blip is None or blip.get(f"{{{R_NS}}}link") is not None:
            raise OleObjectRefusal("embedded_ole_icon_required")
        return self._related_part(blip.get(f"{{{R_NS}}}embed"), {"/image"})

    def _related_part(self, relationship_id: str | None, suffixes: set[str]) -> PackagePart:
        slide = self._shape._slide
        with open_package_source(slide._presentation._source_path) as package:
            try:
                root = ET.fromstring(
                    package.read(rels_part_for_package_part(slide.partname.lstrip("/")))
                )
            except (KeyError, ET.ParseError) as exc:
                raise OleObjectRefusal("ole_relationships_unavailable") from exc
            matches = [
                rel
                for rel in root.findall(f"{{{REL_NS}}}Relationship")
                if rel.get("Id") == relationship_id
            ]
            if relationship_id is None or len(matches) != 1:
                raise OleObjectRefusal("ole_relationship_unavailable")
            rel = matches[0]
            if rel.get("TargetMode", "Internal") != "Internal" or not any(
                rel.get("Type", "").endswith(suffix) for suffix in suffixes
            ):
                raise OleObjectRefusal("internal_ole_relationship_required")
            partname = _resolve_package_target(slide.partname.lstrip("/"), rel.get("Target", ""))
            if partname not in package.namelist():
                raise OleObjectRefusal("ole_part_unavailable")
        return _OlePart(slide._presentation, partname)

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
        return find_ooxml(_shape_xml_element_for_shape(self._shape), f".//{{{P_NS}}}oleObj")


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
        shape._slide._presentation._source_path,
        shape._slide.partname,
    )
    return _shape_xml_element(root._element, shape._payload)
