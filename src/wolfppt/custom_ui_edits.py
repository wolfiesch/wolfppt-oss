"""Plan Ribbon CustomUI part creation and edits. No callback, macro or image is evaluated.

``custom_ui_parts`` stages one package rewrite: the customUI XML part, its root
relationship, its content type and its image relationships. Every refusal is
raised before any output is written, so a refused edit leaves the package
untouched.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from .active_parts import CustomUI, RibbonImage, _XmlBuilder
from .package_parts import rels_part_for_package_part, resolve_package_target

_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
_MS = "http://schemas.microsoft.com/office/"
_XML_CONTENT_TYPE = "application/xml"

# namespace -> (relationship type, default part name)
_UI_2006 = (_MS + "2006/01/customui", _MS + "2006/relationships/ui/extensibility")
_UI_2009 = (_MS + "2009/07/customui", _MS + "2007/relationships/ui/extensibility")
_KINDS = {
    _UI_2006[0]: (_UI_2006[1], "customUI/customUI.xml"),
    _UI_2009[0]: (_UI_2009[1], "customUI/customUI14.xml"),
}
# leading bytes -> (extension, content type)
_IMAGE_FORMATS = (
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"GIF87a", "gif", "image/gif"),
    (b"GIF89a", "gif", "image/gif"),
    (b"BM", "bmp", "image/bmp"),
    (b"\x00\x00\x01\x00", "ico", "image/x-icon"),
)
_IMAGE_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
_RELS_TEMPLATE = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<Relationships xmlns="' + _PKG_REL_NS.encode() + b'"></Relationships>'
)


class CustomUIAuthoringError(ValueError):
    """Named refusal for invalid customUI XML, images or package state; nothing is written."""

    def __init__(self, reason: str, partname: str) -> None:
        self.reason = reason
        self.partname = partname
        super().__init__(f"{reason}: {partname}")


def _payload(xml: Any) -> bytes:
    if isinstance(xml, str):
        return xml.encode("utf-8")
    if isinstance(xml, (bytes, bytearray)):
        return bytes(xml)
    raise TypeError("customUI xml must be str or bytes")


def _root(payload: bytes) -> ET.Element:
    try:
        return ET.fromstring(payload, parser=ET.XMLParser(target=_XmlBuilder()))
    except (ET.ParseError, ValueError) as exc:
        raise CustomUIAuthoringError("custom_ui_xml_invalid", "<xml>") from exc


def _images(images: Mapping[str, Any] | None) -> dict[str, tuple[bytes, str, str]]:
    if images is None:
        return {}
    if not isinstance(images, Mapping):
        raise TypeError("images must map relationship ids to image bytes")
    result = {}
    for rid, blob in images.items():
        if not isinstance(rid, str):
            raise TypeError("image relationship ids must be str")
        if not isinstance(blob, (bytes, bytearray)):
            raise TypeError("image payloads must be bytes")
        data = bytes(blob)
        if not _IMAGE_ID.fullmatch(rid):
            raise CustomUIAuthoringError("ribbon_image_id_invalid", rid)
        if not data:
            raise CustomUIAuthoringError("ribbon_image_empty", rid)
        found = next((f for f in _IMAGE_FORMATS if data.startswith(f[0])), None)
        if found is None:
            raise CustomUIAuthoringError("ribbon_image_format_unsupported", rid)
        result[rid] = (data, found[1], found[2])
    return result


def _parse(package: Any, name: str) -> ET.Element:
    from .presentation_tags import parse_xml

    try:
        return parse_xml(package.read(name))
    except Exception as exc:  # parse_xml also refuses prefix rebinding
        raise CustomUIAuthoringError("package_xml_invalid", name) from exc


def _relationships(package: Any, name: str, *, create: bool) -> ET.Element:
    from .presentation_tags import parse_xml

    if name not in package.namelist():
        if not create:
            raise CustomUIAuthoringError("relationships_missing", name)
        return parse_xml(_RELS_TEMPLATE)
    root = _parse(package, name)
    if root.tag != f"{{{_PKG_REL_NS}}}Relationships":
        raise CustomUIAuthoringError("relationships_root_invalid", name)
    seen = set()
    for rel in root.findall(f"{{{_PKG_REL_NS}}}Relationship"):
        rid = rel.get("Id")
        if not rid or rid in seen:
            raise CustomUIAuthoringError("relationship_id_invalid", name)
        seen.add(rid)
    return root


def _internal_target(package_names: set[str], owner: str, rel: ET.Element) -> str:
    target = rel.get("Target", "")
    try:
        parsed = urlsplit(target)
    except ValueError as exc:
        raise CustomUIAuthoringError("active_relationship_target_invalid", owner) from exc
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
        raise CustomUIAuthoringError("active_relationship_target_invalid", owner)
    if part not in package_names:
        raise CustomUIAuthoringError("active_part_missing", part)
    return part


def _next_rid(root: ET.Element) -> str:
    used = {rel.get("Id") for rel in root.findall(f"{{{_PKG_REL_NS}}}Relationship")}
    index = 1
    while f"rId{index}" in used:
        index += 1
    return f"rId{index}"


def _references(package: Any, names: set[str]) -> dict[str, list[tuple[str, str]]]:
    """Internal relationship targets: part -> [(rels part, relationship id)]."""
    found: dict[str, list[tuple[str, str]]] = {}
    for rels_name in sorted(n for n in names if n.endswith(".rels")):
        owner = posixpath.join(
            posixpath.dirname(posixpath.dirname(rels_name)),
            posixpath.basename(rels_name)[: -len(".rels")],
        )
        try:
            root = ET.fromstring(package.read(rels_name))
        except ET.ParseError:
            continue
        for rel in root.findall(f"{{{_PKG_REL_NS}}}Relationship"):
            if rel.get("TargetMode", "Internal") != "Internal":
                continue
            target = resolve_package_target(owner, rel.get("Target", ""))
            found.setdefault(target, []).append((rels_name, rel.get("Id", "")))
    return found


def _ensure_content_type(
    types: ET.Element, partname: str, extension: str, content_type: str
) -> bool:
    """Make ``partname`` resolve to ``content_type``; returns whether ``types`` changed."""
    defaults = {
        node.get("Extension", "").lower(): node.get("ContentType", "")
        for node in types.findall(f"{{{_CT_NS}}}Default")
    }
    overrides = [
        node
        for node in types.findall(f"{{{_CT_NS}}}Override")
        if node.get("PartName", "").lstrip("/") == partname
    ]
    if overrides:
        if len(overrides) == 1 and overrides[0].get("ContentType") == content_type:
            return False
        for node in overrides:
            types.remove(node)
        changed = True
    else:
        changed = False
    if extension not in defaults:
        ET.SubElement(
            types,
            f"{{{_CT_NS}}}Default",
            {"Extension": extension, "ContentType": content_type},
        )
        return True
    if defaults[extension] != content_type:
        ET.SubElement(
            types,
            f"{{{_CT_NS}}}Override",
            {"PartName": "/" + partname, "ContentType": content_type},
        )
        return True
    return changed


def _drop_overrides(types: ET.Element, partname: str) -> bool:
    stale = [
        node
        for node in types.findall(f"{{{_CT_NS}}}Override")
        if node.get("PartName", "").lstrip("/") == partname
    ]
    for node in stale:
        types.remove(node)
    return bool(stale)


def custom_ui_parts(
    package: Any, xml: Any, images: Mapping[str, Any] | None = None
) -> tuple[dict[str, bytes], set[str], CustomUI]:
    """Plan the package rewrite that creates or replaces one customUI part.

    Returns ``(replacements, removals, snapshot)``. ``xml`` is stored byte for
    byte; its namespace selects customUI.xml (2006) or customUI14.xml (2009). An
    existing part of that namespace is edited in place at its current name. Each
    ``images`` entry writes the ribbon image relationship of that id.
    """
    from .native_media import ordered_content_types_xml
    from .presentation_tags import serialize_xml

    payload = _payload(xml)
    root = _root(payload)
    namespace = root.tag[1:].partition("}")[0] if root.tag.startswith("{") else ""
    if namespace not in _KINDS or root.tag != f"{{{namespace}}}customUI":
        raise CustomUIAuthoringError("custom_ui_root_invalid", "<xml>")
    rel_type, default_part = _KINDS[namespace]
    wanted = _images(images)

    names = set(package.namelist())
    folded = {name.casefold() for name in names}
    replacements: dict[str, bytes] = {}
    removals: set[str] = set()

    root_rels = _relationships(package, "_rels/.rels", create=False)
    current = [
        r for r in root_rels.findall(f"{{{_PKG_REL_NS}}}Relationship") if r.get("Type") == rel_type
    ]
    if len(current) > 1:
        raise CustomUIAuthoringError("duplicate_custom_ui", "_rels/.rels")
    types = _parse(package, "[Content_Types].xml")
    types_changed = False
    if current:
        partname = _internal_target(names, "", current[0])
    else:
        partname = default_part
        if partname.casefold() in folded:
            raise CustomUIAuthoringError("custom_ui_partname_conflict", partname)
        ET.SubElement(
            root_rels,
            f"{{{_PKG_REL_NS}}}Relationship",
            {"Id": _next_rid(root_rels), "Type": rel_type, "Target": partname},
        )
        replacements["_rels/.rels"] = serialize_xml(root_rels)
        types_changed |= _ensure_content_type(types, partname, "xml", _XML_CONTENT_TYPE)
    replacements[partname] = payload

    rels_name = rels_part_for_package_part(partname)
    rels = _relationships(package, rels_name, create=True)
    references = _references(package, names) if wanted else {}
    owner_dir = posixpath.dirname(partname)
    taken = set(folded)
    rels_changed = False
    for rid, (blob, extension, content_type) in wanted.items():
        existing = [r for r in rels.findall(f"{{{_PKG_REL_NS}}}Relationship") if r.get("Id") == rid]
        target = None
        if existing:
            rel = existing[0]
            if rel.get("Type") != _IMAGE_REL:
                raise CustomUIAuthoringError("ribbon_image_relationship_conflict", rid)
            target = _internal_target(names, partname, rel)
        shared = target is not None and any(
            ref != (rels_name, rid) for ref in references.get(target, ())
        )
        if target is not None and not shared and target.rsplit(".", 1)[-1].lower() == extension:
            replacements[target] = blob
            types_changed |= _ensure_content_type(types, target, extension, content_type)
            continue
        candidate = posixpath.join(owner_dir, "images", f"{rid}.{extension}")
        stem, counter = candidate.rsplit(".", 1)[0], 1
        while candidate.casefold() in taken:
            candidate = f"{stem}_{counter}.{extension}"
            counter += 1
        taken.add(candidate.casefold())
        replacements[candidate] = blob
        relative = posixpath.relpath(candidate, owner_dir or ".")
        if existing:
            existing[0].set("Target", relative)
            if not shared:
                removals.add(target)
                types_changed |= _drop_overrides(types, target)
        else:
            ET.SubElement(
                rels,
                f"{{{_PKG_REL_NS}}}Relationship",
                {"Id": rid, "Type": _IMAGE_REL, "Target": relative},
            )
        rels_changed = True
        types_changed |= _ensure_content_type(types, candidate, extension, content_type)
    if rels_changed:
        replacements[rels_name] = serialize_xml(rels)

    available = names | set(replacements)
    ribbon_images = []
    for rel in rels.findall(f"{{{_PKG_REL_NS}}}Relationship"):
        if rel.get("Type") != _IMAGE_REL:
            continue
        target = _internal_target(available, partname, rel)
        blob = replacements[target] if target in replacements else package.read(target)
        ribbon_images.append(RibbonImage(rel.get("Id", ""), target, blob))
    image_ids = {image.relationship_id for image in ribbon_images}
    if any(node.get("image") not in image_ids for node in root.iter() if "image" in node.attrib):
        raise CustomUIAuthoringError("ribbon_image_relationship_missing", partname)
    if types_changed:
        replacements["[Content_Types].xml"] = ordered_content_types_xml(types)
    return replacements, removals, CustomUI(partname, namespace, payload, tuple(ribbon_images))
