"""Read-only access to the parts of a PPTX package.

The renderer reads a deck's package directly instead of going through an
editing model, because scene resolution needs raw OOXML (inheritance chains,
transforms, relationship targets) and must never mutate the source.  Nothing in
this module writes: it exposes part bytes, content types, and relationships.
"""

from __future__ import annotations

import hashlib
import io
import posixpath
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .extractor import (
    SemanticExtractionRefusal,
    _select_effective_mc_children,
    _selected_mc_branch,
)
from .package_limits import (
    PPTX_PACKAGE_LIMITS,
    PptxPackageLimits,
    _zip_envelope_refusal,
)
from .render_refusals import RenderRefusal
from .xml_helpers import find_ooxml, ooxml_namespace

_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P166_NS = "http://schemas.microsoft.com/office/powerpoint/2016/6/main"
_ZOOM_NAMESPACES = {
    "http://schemas.microsoft.com/office/powerpoint/2016/slidezoom": ("sldZm", "sldZmObj", "sldId"),
    "http://schemas.microsoft.com/office/powerpoint/2016/sectionzoom": (
        "sectionZm",
        "sectionZmObj",
        "sectionId",
    ),
    "http://schemas.microsoft.com/office/powerpoint/2016/summaryzoom": (
        "summaryZm",
        "summaryZmObj",
        "sectionId",
    ),
}
# Renderer-local attributes are attached only after MC selection, never saved.
_ZOOM_RENDER_NS = "urn:wolfppt:render:zoom"


class PackageRefusal(RenderRefusal):
    """Raised when a package cannot be read as a PPTX package."""


def _parse_xml_with_namespace_scopes(
    payload: bytes, part: str
) -> tuple[ET.Element, dict[int, dict[str, str]]]:
    """Parse XML while retaining each element's lexical prefix bindings."""
    scopes: dict[int, dict[str, str]] = {}
    pending: dict[str, str] = {}
    stack: list[dict[str, str]] = []
    root: ET.Element | None = None
    try:
        for event, value in ET.iterparse(io.BytesIO(payload), events=("start", "end", "start-ns")):
            if event == "start-ns":
                prefix, uri = value
                pending[prefix or ""] = uri
                continue
            if event == "start":
                element = value
                if root is None:
                    root = element
                scope = (
                    dict(stack[-1]) if stack else {"xml": "http://www.w3.org/XML/1998/namespace"}
                )
                scope.update(pending)
                pending.clear()
                scopes[id(element)] = scope
                stack.append(scope)
                continue
            stack.pop()
    except ET.ParseError as exc:
        raise PackageRefusal(f"part {part!r} is not well-formed XML") from exc
    if root is None:
        raise PackageRefusal(f"part {part!r} is not well-formed XML")
    return (root, scopes)


def _zoom_fallback_images(
    root: ET.Element,
    namespace_scopes: dict[int, dict[str, str]],
    supported_namespaces: frozenset[str],
) -> list[tuple[ET.Element, ET.Element, str, str]]:
    """Capture zoom image sources without changing which MC branch is selected."""
    overlays: list[tuple[ET.Element, ET.Element, str, str]] = []
    for alternate in root.iter(f"{{{_MC_NS}}}AlternateContent"):
        fallback = alternate.find(f"{{{_MC_NS}}}Fallback")
        if (
            fallback is None
            or _selected_mc_branch(alternate, namespace_scopes, supported_namespaces)
            is not fallback
        ):
            continue
        for choice in alternate.findall(f"{{{_MC_NS}}}Choice"):
            requires = choice.get("Requires", "").split()
            bindings = namespace_scopes.get(id(choice), {})
            if not requires or not all(
                bindings.get(prefix) in supported_namespaces
                or bindings.get(prefix) in _ZOOM_NAMESPACES
                for prefix in requires
            ):
                continue
            frame = find_ooxml(choice, f"{{{_P_NS}}}graphicFrame")
            data = (
                None
                if frame is None
                else find_ooxml(frame, f"{{{_A_NS}}}graphic/{{{_A_NS}}}graphicData")
            )
            if data is None:
                continue
            namespace = data.get("uri", "")
            specification = _ZOOM_NAMESPACES.get(namespace)
            if specification is None:
                continue
            container_name, object_name, target_name = specification
            container = data.find(f"{{{namespace}}}{container_name}")
            if container is None:
                continue
            objects = container.findall(f"{{{namespace}}}{object_name}")
            pictures = [
                element
                for element in fallback.iter()
                if element.tag == f"{{{ooxml_namespace(element, _P_NS)}}}pic"
            ]
            # An imported summary may have one composite cached picture rather
            # than an object-by-object group. Do not misattribute its objects.
            if not objects or len(objects) != len(pictures):
                continue
            for picture, zoom_object in zip(pictures, objects, strict=True):
                properties = zoom_object.find(f"{{{namespace}}}zmPr")
                if properties is None:
                    properties = zoom_object.find(f"{{{_P166_NS}}}zmPr")
                if properties is not None:
                    overlays.append(
                        (picture, properties, target_name, zoom_object.get(target_name, ""))
                    )
            break
    return overlays


def _project_zoom_image(
    picture: ET.Element, properties: ET.Element, target_name: str, target: str
) -> None:
    """Keep fallback placement and identity, but render the zoom's image source."""
    picture.set(
        f"{{{_ZOOM_RENDER_NS}}}sourceHash",
        hashlib.sha256(ET.tostring(picture)).hexdigest(),
    )
    picture.set(f"{{{_ZOOM_RENDER_NS}}}imageType", properties.get("imageType", "preview"))
    picture.set(f"{{{_ZOOM_RENDER_NS}}}{target_name}", target)
    picture.set(f"{{{_ZOOM_RENDER_NS}}}showBg", properties.get("showBg", "true"))
    image_fill = properties.find(f"{{{_P166_NS}}}blipFill")
    if image_fill is None:
        return
    fallback_fill = find_ooxml(picture, f"{{{_P_NS}}}blipFill")
    if fallback_fill is None:
        return
    replacement = deepcopy(image_fill)
    replacement.tag = fallback_fill.tag
    picture[list(picture).index(fallback_fill)] = replacement


def refuse_unsupported_must_understand(
    part: str,
    root: ET.Element,
    namespace_scopes: dict[int, dict[str, str]],
    supported_namespaces: frozenset[str],
) -> None:
    """Select effective MC content in place and refuse unmet requirements.

    Every consumer must inspect this selected tree, not reparse the raw part.
    Keep XML parse failures separate from MC refusals so callers can retain
    their existing malformed-part handling.
    """
    zoom_images = _zoom_fallback_images(root, namespace_scopes, supported_namespaces)
    try:
        _select_effective_mc_children(
            root,
            namespace_scopes,
            part,
            supported_namespaces=supported_namespaces,
        )
    except SemanticExtractionRefusal as exc:
        raise PackageRefusal(str(exc)) from exc
    retained = {id(element) for element in root.iter()}
    for picture, properties, target_name, target in zoom_images:
        if id(picture) in retained:
            _project_zoom_image(picture, properties, target_name, target)


@dataclass(frozen=True)
class Relationship:
    """One OPC relationship from a part."""

    identifier: str
    type: str
    target: str
    external: bool

    @property
    def kind(self) -> str:
        """Return the relationship type's final segment."""
        return self.type.rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Package:
    """One read-only PPTX package."""

    source: Path
    digest: str
    parts: dict[str, bytes]
    content_types: dict[str, str]
    relationships: dict[str, tuple[Relationship, ...]]

    def read(self, part: str) -> bytes:
        """Return one part's bytes, refusing a missing part."""
        normalized = normalize_part(part)
        payload = self.parts.get(normalized)
        if payload is None:
            raise PackageRefusal(f"package has no part {normalized!r}")
        return payload

    def read_optional(self, part: str) -> bytes | None:
        return self.parts.get(normalize_part(part))

    def xml(self, part: str) -> ET.Element:
        """Parse one part, refusing malformed XML."""
        payload = self.read(part)
        try:
            return ET.fromstring(payload)
        except ET.ParseError as exc:
            raise PackageRefusal(f"part {part!r} is not well-formed XML") from exc

    def xml_with_namespace_scopes(self, part: str) -> tuple[ET.Element, dict[int, dict[str, str]]]:
        """Parse one part with lexical namespace bindings for MC processing."""
        return _parse_xml_with_namespace_scopes(self.read(part), part)

    def content_type(self, part: str) -> str | None:
        """Return the declared content type of one part."""
        normalized = normalize_part(part)
        override = self.content_types.get(normalized)
        if override is not None:
            return override
        filename = posixpath.basename(normalized)
        separator = filename.rfind(".")
        extension = filename[separator + 1 :].casefold() if separator >= 0 else ""
        return self.content_types.get(f"*.{extension}")

    def part_rels(self, part: str) -> tuple[Relationship, ...]:
        """Return the relationships declared by one part."""
        return self.relationships.get(normalize_part(part), ())

    def related_parts(self, part: str, kind: str) -> list[str]:
        """Return internal targets of one relationship kind, in document order."""
        targets: list[str] = []
        for relationship in self.part_rels(part):
            if relationship.kind != kind or relationship.external:
                continue
            targets.append(resolve_target(part, relationship.target))
        return targets

    def related_part(self, part: str, kind: str) -> str | None:
        targets = self.related_parts(part, kind)
        return targets[0] if targets else None


def normalize_part(part: str) -> str:
    """Normalize a part name to its package form (no leading slash)."""
    return part.lstrip("/")


def resolve_target(source_part: str, target: str) -> str:
    """Resolve a relationship target against the part that declares it."""
    if target.startswith("/"):
        return normalize_part(target)
    base = posixpath.dirname(normalize_part(source_part))
    return posixpath.normpath(posixpath.join(base, target))


def _rels_part(part: str) -> str:
    parent, filename = posixpath.split(normalize_part(part))
    return f"{parent}/_rels/{filename}.rels" if parent else f"_rels/{filename}.rels"


def _parse_content_types(payload: bytes) -> dict[str, str]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise PackageRefusal("[Content_Types].xml is not well-formed XML") from exc
    content_types: dict[str, str] = {}
    for element in root:
        name = element.tag.rsplit("}", 1)[-1]
        value = element.get("ContentType")
        if value is None:
            continue
        if name == "Default":
            extension = element.get("Extension")
            if extension:
                content_types[f"*.{extension.casefold()}"] = value
        elif name == "Override":
            part_name = element.get("PartName")
            if part_name:
                content_types[normalize_part(part_name)] = value
    return content_types


def _parse_relationships(payload: bytes) -> tuple[Relationship, ...]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise PackageRefusal("a relationship part is not well-formed XML") from exc
    relationships: list[Relationship] = []
    for element in root:
        if element.tag.rsplit("}", 1)[-1] != "Relationship":
            continue
        identifier = element.get("Id")
        kind = element.get("Type")
        target = element.get("Target")
        if not identifier or not kind or not target:
            raise PackageRefusal("a relationship is missing Id, Type, or Target")
        relationships.append(
            Relationship(
                identifier=identifier,
                type=kind,
                target=target,
                external=element.get("TargetMode", "").casefold() == "external",
            )
        )
    return tuple(relationships)


def read_package(source: Path, *, limits: PptxPackageLimits | None = None) -> Package:
    """Open one bounded PPTX package from one exact snapshot of ``source``.

    The digest is the raw snapshot's SHA-256, and the archive is parsed from
    those very bytes.  The ZIP envelope is admitted before any member expands,
    so a package can never retain decompressed bytes beyond the shared bounds.
    """
    limits = PPTX_PACKAGE_LIMITS if limits is None else limits
    if not source.exists():
        raise PackageRefusal(f"deck {source} does not exist")
    if not source.is_file():
        raise PackageRefusal(f"deck {source} is not a file")
    try:
        with source.open("rb") as stream:
            payload = stream.read(limits.max_archive_size + 1)
    except OSError as exc:
        raise PackageRefusal(f"deck {source} cannot be read") from exc
    return read_package_bytes(source, payload, limits=limits)


def read_package_bytes(
    source: Path, payload: bytes, *, limits: PptxPackageLimits | None = None
) -> Package:
    """Parse bounded package bytes without expanding an unadmitted ZIP member.

    The identity of the package is derived from the exact bytes parsed here, so
    the digest is never supplied by a caller and cannot describe other bytes.
    """
    limits = PPTX_PACKAGE_LIMITS if limits is None else limits
    if len(payload) > limits.max_archive_size:
        raise PackageRefusal(
            f"deck {source} size_limit: the package holds more than the "
            f"{limits.max_archive_size} byte archive limit"
        )
    envelope = _zip_envelope_refusal(payload, limits)
    if envelope is not None:
        raise PackageRefusal(f"deck {source} {envelope.code}: {envelope.recovery}")
    digest = hashlib.sha256(payload).hexdigest()
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise PackageRefusal("package contains duplicate part names")
            parts: dict[str, bytes] = {}
            for name in names:
                if name.endswith("/"):
                    continue
                parts[normalize_part(name)] = archive.read(name)
    except zipfile.BadZipFile as exc:
        raise PackageRefusal(f"deck {source} is not a readable package") from exc
    if "[Content_Types].xml" not in parts:
        raise PackageRefusal("package has no [Content_Types].xml part")
    content_types = _parse_content_types(parts["[Content_Types].xml"])
    relationships: dict[str, tuple[Relationship, ...]] = {}
    for name, payload_part in parts.items():
        if not name.endswith(".rels"):
            continue
        parent, filename = posixpath.split(name)
        if posixpath.basename(parent) != "_rels":
            continue
        owner = posixpath.join(posixpath.dirname(parent), filename[: -len(".rels")])
        relationships[owner] = _parse_relationships(payload_part)
    return Package(
        source=source,
        digest=digest,
        parts=parts,
        content_types=content_types,
        relationships=relationships,
    )


def rels_part_name(part: str) -> str:
    """Return the relationship part name of one part."""
    return _rels_part(part)
