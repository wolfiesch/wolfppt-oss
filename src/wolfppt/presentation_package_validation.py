"""Validate PresentationML package roots before constructing a presentation."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .package_parts import (
    CONTENT_TYPES_NS,
    P_NS,
    PKG_REL_NS,
    R_NS,
    InMemoryPackageSource,
    open_package_source,
    resolve_package_target,
)
from .package_read_scope import package_xml
from .xml_helpers import findall_ooxml, ooxml_namespace

_OFFICE_DOCUMENT_TYPES = frozenset(
    {
        f"{R_NS}/officeDocument",
        "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument",
    }
)
_PRESENTATION_ROOTS = frozenset(
    {
        f"{{{P_NS}}}presentation",
        "{http://purl.oclc.org/ooxml/presentationml/main}presentation",
    }
)
_PRESENTATION_CONTENT_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        "application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml",
        "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml",
        "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml",
        "application/vnd.ms-powerpoint.slideshow.macroEnabled.main+xml",
        "application/vnd.ms-powerpoint.template.macroEnabled.main+xml",
        "application/vnd.ms-powerpoint.addin.macroEnabled.main+xml",
    }
)


class PresentationPackageError(ValueError):
    """Raised when ZIP input lacks the required PresentationML package roots."""


def validate_presentation_package(source: Path | InMemoryPackageSource) -> None:
    """Check package identity, without imposing slide counts or rewriting parts."""
    with open_package_source(source) as package:
        content_types = _required_xml(package, "[Content_Types].xml")
        if content_types.tag != f"{{{CONTENT_TYPES_NS}}}Types":
            raise PresentationPackageError("invalid OPC content-types root")
        relationships = _required_xml(package, "_rels/.rels")
        if relationships.tag != f"{{{PKG_REL_NS}}}Relationships":
            raise PresentationPackageError("invalid OPC package relationships root")
        _validate_relationship_identities(package)
        document_relationships = [
            relationship
            for relationship in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
            if relationship.get("Type") in _OFFICE_DOCUMENT_TYPES
        ]
        if len(document_relationships) != 1:
            raise PresentationPackageError(
                "presentation package requires exactly one officeDocument relationship"
            )
        relationship = document_relationships[0]
        target = relationship.get("Target", "")
        if (
            not relationship.get("Id")
            or not target
            or relationship.get("TargetMode", "Internal") != "Internal"
        ):
            raise PresentationPackageError(
                "presentation package requires an internal officeDocument target and identity"
            )
        partname = resolve_package_target("", target)
        content_type = _content_type(content_types, partname)
        if content_type not in _PRESENTATION_CONTENT_TYPES:
            raise PresentationPackageError(
                "officeDocument target has no supported PresentationML content type"
            )
        presentation = _required_xml(package, partname)
        if presentation.tag not in _PRESENTATION_ROOTS:
            raise PresentationPackageError(
                "officeDocument target is not a PresentationML presentation root"
            )
        # Select the same MCE branches as the slide reader without mutating the
        # shared raw XML root used by preservation/editing callers.
        if any(
            node.tag
            == "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
            for node in presentation.iter()
        ):
            from .native_read import _parse_native_effective_xml

            presentation = _parse_native_effective_xml(package.read(partname))
        _validate_slide_parts(package, partname, presentation)


def _validate_relationship_identities(package: ZipFile) -> None:
    """Relationship identities are unique within each owning relationship part."""
    for name in package.namelist():
        if _relationship_owner(name) is None:
            continue
        seen: set[str] = set()
        for relationship in _required_xml(package, name).findall(f"{{{PKG_REL_NS}}}Relationship"):
            identity = relationship.get("Id")
            if not identity:
                continue
            if identity in seen:
                raise PresentationPackageError(
                    f"duplicate relationship identity in {name}: {identity}"
                )
            seen.add(identity)


def orphan_parts(source: Path | InMemoryPackageSource) -> tuple[str, ...]:
    """Sorted data-part names unreachable from package-root internal relationships.

    Inspect the saved package baseline, including opaque parts. External targets
    are never followed; relationship parts and the content-types stream are
    structural metadata, not orphan candidates. Cycles cannot create reachability.
    """
    with open_package_source(source) as package:
        names = set(package.namelist())
        candidates = {
            name
            for name in names
            if name != "[Content_Types].xml"
            and not name.endswith("/")
            and _relationship_owner(name) is None
        }
        reachable: set[str] = set()
        pending = [""]
        while pending:
            owner = pending.pop()
            relname = "_rels/.rels" if not owner else _rels_part_for_package_part(owner)
            if relname not in names:
                continue
            root = _required_xml(package, relname)
            for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
                if relationship.get("TargetMode", "Internal") != "Internal":
                    continue
                target = relationship.get("Target", "")
                if not target:
                    continue
                part = resolve_package_target(owner, target)
                if part in candidates and part not in reachable:
                    reachable.add(part)
                    pending.append(part)
        return tuple(sorted(candidates - reachable))


def _relationship_owner(name: str) -> str | None:
    if name == "_rels/.rels":
        return ""
    parent, _, filename = name.rpartition("/")
    if not filename.endswith(".rels") or parent.rsplit("/", 1)[-1] != "_rels":
        return None
    directory = parent.removesuffix("_rels")
    return f"{directory}{filename[:-5]}"


def _required_xml(package: ZipFile, partname: str) -> ET.Element:
    try:
        return package_xml(package, partname)
    except KeyError as exc:
        raise PresentationPackageError(
            f"presentation package is missing required part: {partname}"
        ) from exc
    except ET.ParseError as exc:
        raise PresentationPackageError(
            f"presentation package contains malformed XML: {partname}"
        ) from exc


def _content_type(root: ET.Element, partname: str) -> str:
    for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.get("PartName") == f"/{partname}":
            return override.get("ContentType", "")
    extension = partname.rsplit(".", 1)[-1].lower()
    for default in root.findall(f"{{{CONTENT_TYPES_NS}}}Default"):
        if default.get("Extension", "").lower() == extension:
            return default.get("ContentType", "")
    return ""


def _validate_slide_parts(
    package: ZipFile,
    presentation_partname: str,
    presentation_root: ET.Element,
) -> None:
    """Validate that all slide relationships target existing, well-formed parts."""
    rels_partname = _rels_part_for_package_part(presentation_partname)
    try:
        rels_root = package_xml(package, rels_partname)
    except KeyError:
        rels_root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    except ET.ParseError as exc:
        raise PresentationPackageError(
            f"presentation package contains malformed XML: {rels_partname}"
        ) from exc

    relationships = {
        rel.get("Id"): rel
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
        if rel.get("Id")
    }

    for slide_id in findall_ooxml(presentation_root, f".//{{{P_NS}}}sldId"):
        relationship_id = slide_id.get(f"{{{ooxml_namespace(slide_id, R_NS)}}}id")
        if relationship_id is None:
            continue

        relationship = relationships.get(relationship_id)
        if relationship is None:
            raise PresentationPackageError(
                f"presentation slide references missing relationship: {relationship_id}"
            )

        target = relationship.get("Target", "")
        if not target:
            raise PresentationPackageError(
                f"presentation slide relationship has no target: {relationship_id}"
            )

        slide_part = resolve_package_target(presentation_partname, target)

        try:
            package_xml(package, slide_part)
        except KeyError as exc:
            raise PresentationPackageError(
                f"presentation slide references missing part: {slide_part}"
            ) from exc
        except ET.ParseError as exc:
            raise PresentationPackageError(
                f"presentation package contains malformed slide XML: {slide_part}"
            ) from exc


def _rels_part_for_package_part(part: str) -> str:
    """Return the relationships part name for a given package part."""
    if "/" in part:
        parent = part.rsplit("/", 1)[0]
        name = part.rsplit("/", 1)[1]
        return f"{parent}/_rels/{name}.rels"
    return f"_rels/{part}.rels"
