"""Read-only active-content snapshots. No callbacks, controls or macros are executed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID
from xml.etree import ElementTree as ET

from .activex_controls import ActiveXControlRefusal, _inspect
from .package_parts import open_package_source, rels_part_for_package_part, resolve_package_target

_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
_MS = "http://schemas.microsoft.com/office/"
_UI = {
    _MS + "2006/relationships/ui/extensibility": _MS + "2006/01/customui",
    _MS + "2007/relationships/ui/extensibility": _MS + "2009/07/customui",
}
_SIGNATURES = {
    _MS + "2006/relationships/vbaProjectSignature": "legacy",
    _MS + "2014/relationships/vbaProjectSignatureAgile": "agile",
    _MS + "2020/07/relationships/vbaProjectSignatureV3": "v3",
}


class ActivePartReadError(ValueError):
    """Named refusal for malformed active XML, relationships or missing payloads."""

    def __init__(self, reason: str, partname: str) -> None:
        self.reason = reason
        self.partname = partname
        super().__init__(f"{reason}: {partname}")


@dataclass(frozen=True)
class RibbonImage:
    relationship_id: str
    partname: str
    blob: bytes


@dataclass(frozen=True)
class CustomUI:
    """Saved Ribbon XML and related image bytes, without interpreting callbacks."""

    partname: str
    namespace: str
    xml: bytes
    images: tuple[RibbonImage, ...]


@dataclass(frozen=True)
class VbaSignature:
    """Opaque saved signature bytes. Presence is not cryptographic verification."""

    relationship_id: str
    relationship_type: str
    kind: str
    partname: str
    blob: bytes


@dataclass(frozen=True)
class ActiveXControlSnapshot:
    slide_partname: str
    relationship_id: str
    name: str
    partname: str
    class_id: str
    persistence: str
    properties: tuple[tuple[str, str], ...]
    xml: bytes
    binary_partname: str | None
    binary_blob: bytes | None


class _XmlBuilder(ET.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise ValueError("DTD declarations are unsupported")


def _payload(package: Any, part: str) -> bytes:
    try:
        return package.read(part)
    except KeyError as exc:
        raise ActivePartReadError("active_part_missing", part) from exc


def _xml(payload: bytes, part: str) -> ET.Element:
    try:
        return ET.fromstring(payload, parser=ET.XMLParser(target=_XmlBuilder()))
    except (ET.ParseError, ValueError) as exc:
        raise ActivePartReadError("active_part_xml_invalid", part) from exc


def _relationships(package: Any, owner: str) -> tuple[ET.Element, ...]:
    part = rels_part_for_package_part(owner) if owner else "_rels/.rels"
    if part not in package.namelist():
        return ()
    root = _xml(_payload(package, part), part)
    if root.tag != f"{{{_REL}}}Relationships":
        raise ActivePartReadError("relationships_root_invalid", part)
    seen = set()
    for rel in root:
        rid = rel.get("Id")
        if rel.tag != f"{{{_REL}}}Relationship" or not rid or rid in seen:
            raise ActivePartReadError("relationship_id_invalid", part)
        if not rel.get("Type") or not rel.get("Target"):
            raise ActivePartReadError("relationship_invalid", part)
        seen.add(rid)
    return tuple(root)


def _target(package: Any, owner: str, rel: ET.Element) -> str:
    target = rel.get("Target", "")
    try:
        parsed = urlsplit(target)
    except ValueError as exc:
        raise ActivePartReadError("active_relationship_target_invalid", owner) from exc
    part = resolve_package_target(owner, target)
    if (
        rel.get("TargetMode", "Internal") != "Internal"
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or "\\" in target
        or part in ("", ".", "..")
        or part.startswith("../")
    ):
        raise ActivePartReadError("active_relationship_target_invalid", owner)
    if part not in package.namelist():
        raise ActivePartReadError("active_part_missing", part)
    return part


def read_custom_ui(source: Any) -> tuple[CustomUI, ...]:
    result = []
    with open_package_source(source) as package:
        seen = set()
        for rel in _relationships(package, ""):
            namespace = _UI.get(rel.get("Type"))
            if namespace is None:
                continue
            if namespace in seen:
                raise ActivePartReadError("duplicate_custom_ui", "_rels/.rels")
            seen.add(namespace)
            part = _target(package, "", rel)
            payload = _payload(package, part)
            root = _xml(payload, part)
            if root.tag != f"{{{namespace}}}customUI":
                raise ActivePartReadError("custom_ui_root_invalid", part)
            images = tuple(
                RibbonImage(image.get("Id"), target, _payload(package, target))
                for image in _relationships(package, part)
                if image.get("Type") == _R + "image"
                for target in (_target(package, part, image),)
            )
            image_ids = {image.relationship_id for image in images}
            if any(
                node.get("image") not in image_ids for node in root.iter() if "image" in node.attrib
            ):
                raise ActivePartReadError("ribbon_image_relationship_missing", part)
            result.append(CustomUI(part, namespace, payload, images))
    return tuple(result)


def read_vba_signatures(source: Any) -> tuple[VbaSignature, ...]:
    result = []
    with open_package_source(source) as package:
        for main in _relationships(package, ""):
            if main.get("Type") not in (
                _R + "officeDocument",
                "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument",
            ):
                continue
            main_part = _target(package, "", main)
            for project in _relationships(package, main_part):
                if project.get("Type") != _MS + "2006/relationships/vbaProject":
                    continue
                project_part = _target(package, main_part, project)
                seen = set()
                for rel in _relationships(package, project_part):
                    kind = _SIGNATURES.get(rel.get("Type"))
                    if kind is None:
                        continue
                    if kind in seen:
                        raise ActivePartReadError("duplicate_vba_signature", project_part)
                    seen.add(kind)
                    part = _target(package, project_part, rel)
                    blob = _payload(package, part)
                    if not blob:
                        raise ActivePartReadError("vba_signature_empty", part)
                    result.append(VbaSignature(rel.get("Id"), rel.get("Type"), kind, part, blob))
    return tuple(result)


def read_activex_controls(
    source: Any, slides: tuple[str, ...]
) -> tuple[ActiveXControlSnapshot, ...]:
    result = []
    with open_package_source(source) as package:
        for slide in slides:
            try:
                for control in _inspect(package, slide):
                    try:
                        UUID(control.class_id.strip("{}"))
                    except ValueError as exc:
                        raise ActivePartReadError(
                            "invalid_control_class_id", control.partname
                        ) from exc
                    binary = control.binary_partname
                    result.append(
                        ActiveXControlSnapshot(
                            slide,
                            control.rid,
                            control.name,
                            control.partname,
                            control.class_id,
                            control.persistence,
                            tuple(control.properties.items()),
                            control.xml,
                            binary,
                            None if binary is None else _payload(package, binary),
                        )
                    )
            except ActiveXControlRefusal as exc:
                raise ActivePartReadError(exc.reason, slide) from exc
    return tuple(result)
