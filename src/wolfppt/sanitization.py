"""Source-bound native inventory and removal of confidential package content.

``inspect_pptx_sanitization`` reads one admitted presentation and reports every
part, its classification, its reachability, and the exact removal targets this
surface can remove.  ``sanitize_pptx`` applies one strict source-bound request
naming those targets and publishes exactly one verified output through the same
private sibling staging file plus ``os.link`` no-replace publication the
encryption surface uses, so a destination that already exists, is a dangling
symbolic link, or appears while the operation runs is preserved and reported
instead of overwritten.

The supported surface is exactly this, and nothing beyond it:

* What is removable is a closed, recognized list: the package's core, extended,
  and custom property parts, its thumbnail part, its legacy comments and comment
  author directory, and its speaker-notes parts.  A removal is the part itself,
  its own relationships part, the relationship each preserved owner declares for
  it, and its ``[Content_Types].xml`` override - the complete scope the receipt
  declares, never an arbitrary path, and never a part a preserved part still
  reaches through markup.
* Everything else is preserved byte for byte and reported.  Embedded payloads
  (OLE objects, macros, and active content), media, external links, modern
  threaded comments, slides and structural parts, digital-signature parts, and
  any part whose declared type this engine does not recognize are all marked
  not-removable with a precise reason and refused when a request selects them.
* Active XML is inventoried by expanded element and attribute names only.
  Malformed XML and prohibited DTDs receive named diagnoses. Attribute values,
  text, embedded payload and media bytes, and external relationship targets
  are never echoed. This surface removes a part it recognizes and can prove
  absent, and it never claims
  a package is free of confidential content.
* A signed package is refused for mutation.  Signature markers are read from
  signature part names, declared content types, and relationship types, and
  removing any part of such a package would invalidate a signature this surface
  can neither verify nor repair.
* Package identity is the engine's own.  Admission, planning, and writing consume
  one bounded immutable snapshot: the bytes are preflighted against the package
  envelope the security surface declares, parsed through
  :func:`wolfppt.render_package.read_package_bytes`, required to digest to the
  SHA-256 the request states, and required to be PresentationML - the ``ppt/
  presentation.xml`` part must exist, carry the PresentationML root element and a
  recognized presentation content type, and be the part the package's single
  internal ``officeDocument`` relationship reaches.  The writer is handed those
  same bytes, never a second read of the mutable path.
* Writing is the engine's raw-preservation writer: every unselected member is
  copied through its original ZIP span, so an unselected part's bytes are
  preserved by construction rather than by re-serialization.
* Verification happens on the staged file before the link.  The staged package is
  re-read through the same bounded admission, its part set must be exactly the
  source's minus the planned removals, every rewritten part must equal the bytes
  the plan produced, every preserved part must equal its source bytes, no
  surviving relationship or content-type override may name a removed part, and
  reachability may shrink only by the removed parts.  The source digest is
  re-checked after that verification, immediately before the no-replace link.
* Reachability, and therefore orphan reporting, is resolved through the native
  package graph with :func:`wolfppt.render_package.resolve_target`.  The
  reporting-scoped ``reachable_parts`` helper resolves relationship targets by
  plain path join, so it cannot see the package root part or a package-absolute
  target, and it is therefore not the authority this inventory is built on.

Reports carry ids, part names, sizes, and classification, and never a comment
body, an author name, an embedded payload, or an external target.

CustomUI 2006/2009, Office web-extension/taskpane and ActiveX XML inventories
are available on each part as ``xml_elements``, ``xml_attributes`` and
``xml_diagnosis``. These are structural inventories, not schema validation.
Deletion remains an atomic refusal under the census's refused disposition.
"""

from __future__ import annotations

import hashlib
import io
import json
import posixpath
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from xml.etree import ElementTree as ET

from .comments_facade import (
    CONTENT_TYPES_NS,
    LEGACY_COMMENT_AUTHORS_CONTENT_TYPE,
    LEGACY_COMMENTS_CONTENT_TYPE,
    MODERN_COMMENTS_CONTENT_TYPE,
    MODERN_PERSON_CONTENT_TYPE,
    PKG_REL_NS,
    R_NS,
    CommentRefusal,
    content_type_overrides,
    modern_comment_markers,
    relationships_xml,
)
from .core_properties import CORE_PROPERTIES_PARTNAME
from .package_parts import copy_open_package_with_replacements
from .render_package import (
    Package,
    PackageRefusal,
    normalize_part,
    read_package_bytes,
    rels_part_name,
    resolve_target,
)
from .security import (
    _PUBLICATION_RECOVERIES as _SECURITY_PUBLICATION_RECOVERIES,
)
from .security import (
    PPTX_SECURITY_LIMITS,
    PRESENTATION_PART,
    PptxPackageLimits,
    _admitted_package,
    _presentation_refusal,
    _publish_staged,
    _require_sha256,
    _zip_envelope_refusal,
    sha256_file,
)
from .xml_helpers import content_types_xml

INSPECT = "inspect"
"""The read-only operation: one bounded inventory of one source package."""

SANITIZE = "sanitize"
"""The mutating operation: one verified removal into one new package."""

OPERATIONS = (INSPECT, SANITIZE)
"""The two operations this surface exposes."""

CORE_PROPERTIES_PART = CORE_PROPERTIES_PARTNAME
"""The recognized core-properties part, the engine's own metadata authority."""

EXTENDED_PROPERTIES_PART = "docProps/app.xml"
"""The recognized extended-properties part of an OPC presentation package."""

CUSTOM_PROPERTIES_PART = "docProps/custom.xml"
"""The recognized custom-properties part of an OPC presentation package."""

THUMBNAIL_PREFIX = "docProps/thumbnail."
"""The part-name prefix of the package thumbnail part."""

THUMBNAIL_RELATIONSHIP_KIND = "thumbnail"
"""The root relationship kind that names the package thumbnail part."""

COMMENT_AUTHORS_PART = "ppt/commentAuthors.xml"
"""The presentation-scoped legacy comment author directory."""

COMMENTS_DIRECTORY = "ppt/comments"
"""The directory holding legacy and modern comment parts."""

NOTES_SLIDES_DIRECTORY = "ppt/notesSlides"
"""The directory holding speaker-notes parts."""

SLIDES_DIRECTORY = "ppt/slides"
"""The directory holding slide parts."""

MEDIA_PREFIX = "ppt/media/"
"""The part-name prefix of package media parts."""

EMBEDDED_PREFIXES = ("ppt/embeddings/", "ppt/activeX/")
"""The part-name prefixes of embedded payload parts."""

MACRO_PART = "ppt/vbaProject.bin"
"""The part name of a presentation's VBA macro project."""

EXTERNAL_LINKS_PREFIX = "ppt/externalLinks/"
"""The part-name prefix of external-link parts."""

SIGNATURE_PREFIX = "_xmlsignatures/"
"""The part-name prefix of digital-signature parts."""

SIGNATURE_ORIGIN_PART = "origin.xml"
"""The file name of the digital-signature origin part."""

CONTENT_TYPES_PART = "[Content_Types].xml"
"""The OPC content-type part name."""

CORE_PROPERTIES_CONTENT_TYPE = "application/vnd.openxmlformats-package.core-properties+xml"
EXTENDED_PROPERTIES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.extended-properties+xml"
)
CUSTOM_PROPERTIES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.custom-properties+xml"
)
NOTES_SLIDE_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
)
"""The declared content types a recognized channel is classified against."""

CHANNELS = (
    "content_types",
    "relationships",
    "core_properties",
    "extended_properties",
    "custom_properties",
    "thumbnail",
    "comment_authors",
    "comments",
    "modern_comments",
    "notes_slides",
    "slides",
    "structure",
    "external_links",
    "embedded_payloads",
    "media",
    "signatures",
    "unrecognized",
)
"""Every classification this inventory assigns, one per part."""

REMOVABLE_CHANNELS = frozenset(
    {
        "core_properties",
        "extended_properties",
        "custom_properties",
        "thumbnail",
        "comment_authors",
        "comments",
        "notes_slides",
    }
)
"""The one closed list of channels this surface can remove and verify."""

SENSITIVE_CHANNELS = frozenset(
    {
        "core_properties",
        "extended_properties",
        "custom_properties",
        "thumbnail",
        "comment_authors",
        "comments",
        "modern_comments",
        "notes_slides",
        "external_links",
        "embedded_payloads",
        "media",
        "signatures",
    }
)
"""Channels that can carry content beyond the visible slide bodies."""

_REASON_BY_CHANNEL = {
    "content_types": "part_is_content_types",
    "relationships": "part_is_relationships",
    "modern_comments": "part_modern_comments_unsupported",
    "slides": "part_is_slide_content",
    "structure": "part_is_presentation_structure",
    "external_links": "part_external_target_not_inspected",
    "embedded_payloads": "part_payload_not_inspected",
    "media": "part_payload_not_inspected",
    "signatures": "part_signature_not_verifiable",
    "unrecognized": "part_not_recognized",
}
"""Why each non-removable channel refuses a selection."""

_PUBLISHED = "published"
_INSPECTED = "inspected"
_REFUSED = "refused"
_DIGEST_CHUNK_BYTES = 1 << 20

_INSPECT_REQUEST_FIELDS = frozenset({"source", "source_sha256"})
_REQUEST_FIELDS = frozenset({"source", "destination", "source_sha256", "removals"})

_STRUCTURAL_PREFIXES = (
    "ppt/slideLayouts/",
    "ppt/slideMasters/",
    "ppt/notesMasters/",
    "ppt/handoutMasters/",
    "ppt/theme/",
    "ppt/printerSettings/",
    "ppt/tags/",
    "ppt/charts/",
)
"""PresentationML structure this engine models but never removes."""

_NEUTRAL_CONTENT_TYPES = frozenset({"application/xml", "text/xml", "application/octet-stream"})
"""Declared types that never contradict a recognized part name."""

_SIGNATURE_CONTENT_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-package.digital-signature-origin",
        "application/vnd.openxmlformats-package.digital-signature-xmlsignature+xml",
    }
)
"""The declared content types that mark digital-signature parts."""

_SIGNATURE_RELATIONSHIP_PREFIX = (
    "http://schemas.openxmlformats.org/package/2006/relationships/digital-signature/"
)
"""The relationship-type prefix that marks digital-signature relationships."""

_SLIDES_PREFIX = f"{SLIDES_DIRECTORY}/"
_MODERN_PERSON_PART = "ppt/person.xml"
"""The part name a modern threaded-comment person part uses."""

_COMMENT_PART = re.compile(r"ppt/comments/comment\d+\.xml\Z")
_MODERN_COMMENT_PART = re.compile(r"ppt/comments/modernComment\d+\.xml\Z")
_NOTES_SLIDE_PART = re.compile(r"ppt/notesSlides/notesSlide\d+\.xml\Z")


_OFFICE_NS = "http://schemas.microsoft.com/office"
_ACTIVE_XML_ROOTS = {
    "customUI/customUI.xml": f"{{{_OFFICE_NS}/2006/01/customui}}customUI",
    "customUI/customUI14.xml": f"{{{_OFFICE_NS}/2009/07/customui}}customUI",
}
_ACTIVE_XML_TYPES = {
    "application/vnd.ms-office.webextension+xml": (
        f"{{{_OFFICE_NS}/webextensions/webextension/2010/11}}webextension"
    ),
    "application/vnd.ms-office.webextensiontaskpanes+xml": (
        f"{{{_OFFICE_NS}/webextensions/taskpanes/2010/11}}taskpanes"
    ),
    "application/vnd.ms-office.activeX+xml": f"{{{_OFFICE_NS}/2006/activeX}}ocx",
}


class _ActiveXMLBuilder(ET.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise ValueError("active_xml_declaration_unsupported")


def _active_xml_root(name: str, content_type: str | None) -> str | None:
    expected = _ACTIVE_XML_ROOTS.get(name) or _ACTIVE_XML_TYPES.get(content_type)
    if expected:
        return expected
    if re.fullmatch(r"ppt/webextensions/webextension\d+\.xml", name):
        return _ACTIVE_XML_TYPES["application/vnd.ms-office.webextension+xml"]
    if name == "ppt/webextensions/taskpanes.xml":
        return _ACTIVE_XML_TYPES["application/vnd.ms-office.webextensiontaskpanes+xml"]
    if re.fullmatch(r"ppt/activeX/activeX\d+\.xml", name):
        return _ACTIVE_XML_TYPES["application/vnd.ms-office.activeX+xml"]
    return None


def _active_xml_members(
    payload: bytes, expected: str
) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    try:
        root = ET.fromstring(payload, parser=ET.XMLParser(target=_ActiveXMLBuilder()))
    except ValueError:
        return (), (), "active_xml_declaration_unsupported"
    except ET.ParseError:
        return (), (), "active_xml_malformed"
    if root.tag != expected:
        return (), (), "active_xml_root_invalid"
    elements = tuple(sorted({node.tag for node in root.iter()}))
    attributes = tuple(sorted({name for node in root.iter() for name in node.attrib}))
    return elements, attributes, None


SANITIZATION_NOTES = (
    (
        "a removal target is the exact part name this receipt lists, and the plan "
        "it produces is the target's own declared scope: the part, its "
        "relationships part, the relationship a preserved owner declares for it, "
        "and its content-type override"
    ),
    (
        "a request is applied only while the source still digests to the SHA-256 "
        "it states, so a target read from an older receipt is refused rather than "
        "guessed at"
    ),
    (
        "an unselected part is preserved byte for byte, and a part the package "
        "already fails to reach is reported rather than deleted"
    ),
    (
        "reachability is resolved through the package graph: a part is reachable "
        "when the package root reaches it, and a relationships part is in use "
        "while the part that owns it is reachable"
    ),
    (
        "opaque payload bytes, media bytes, and external relationship targets are "
        "never inspected, so this receipt never says a package is free of "
        "confidential content"
    ),
    (
        "a signed package is reported and refused for mutation: removing any part "
        "of it would invalidate a signature this surface can neither verify nor "
        "repair"
    ),
)

_SIGNATURE_DETAIL = (
    "Digital-signature markers are present; a signed package cannot be mutated, "
    "verified, or repaired by this surface."
)
_EMBEDDED_DETAIL = (
    "Embedded payload bytes (OLE objects, macros, and active content) are never "
    "parsed by this engine, so this report makes no statement about what they "
    "hold; each payload is referenced through markup, so removing one is a "
    "structural mutation this surface does not perform."
)
_MEDIA_DETAIL = (
    "Media bytes are never parsed by this engine, and a media part is referenced "
    "through markup relationship ids, so this surface neither inspects nor "
    "removes one."
)
_MODERN_DETAIL = (
    "Modern threaded comments and their person data are reported and preserved "
    "verbatim; this surface does not edit threaded comment parts."
)
_EXTERNAL_DETAIL = (
    "External relationship targets are not echoed because they can name "
    "confidential locations; only the declaring part, the relationship id, and "
    "its kind are reported."
)
_UNRECOGNIZED_DETAIL = (
    "These parts carry no content type this engine models, so it cannot classify "
    "their content or verify a removal of them."
)
_HIDDEN_DETAIL = (
    "These slides are marked hidden and their content is still in the package; "
    "this surface never removes a slide."
)
_DANGLING_DETAIL = (
    "These relationships already pointed at no part of the source package before "
    "this operation ran; they are reported and left exactly as they were."
)
_ORPHAN_DETAIL = (
    "No relationship of the package reaches these parts; they are reported and "
    "preserved, and only a request that selects one removes it."
)

_HASH_MISMATCH_RECOVERY = (
    "The source no longer digests to the SHA-256 this request states; read the "
    "presentation again and issue the operation against its current digest."
)
_SIGNED_RECOVERY = (
    "The source carries digital-signature markers, and removing any part of a "
    "signed package would invalidate a signature this surface cannot verify or "
    "repair.  Work from an unsigned copy of the presentation."
)
_EMPTY_REMOVALS_RECOVERY = (
    "A sanitization request must name at least one of the removal targets the "
    "inspection receipt lists; run the inspection operation first and select "
    "exactly the targets to remove."
)
_UNKNOWN_REMOVAL_RECOVERY = (
    "Every removal is an exact target id from the inspection receipt of this same "
    "source digest: a part name this package does not carry cannot be removed.  "
    "Run the inspection operation against this source and use the ids it reports."
)
_UNSUPPORTED_REMOVAL_RECOVERY = (
    "This surface removes only the recognized metadata, thumbnail, legacy "
    "comment, comment author, and speaker-notes channels, and only where a "
    "preserved part does not still reach the target through markup.  The "
    "receipt's reason for this target states why it is not removable."
)
_DUPLICATE_REMOVAL_RECOVERY = (
    "Each removal target is listed once; remove the repeated ids from the request."
)
_AUTHORS_REFERENCED_RECOVERY = (
    "ppt/commentAuthors.xml owns the author every surviving legacy comment "
    "references by id, so it is removed together with those comments or not at "
    "all: select every legacy comment part in the same request, or leave the "
    "author directory in place."
)
_SOURCE_CHANGED_RECOVERY = (
    "The source changed while the operation ran, so nothing was published; retry "
    "against a source that stays unchanged until the operation finishes."
)
_STAGED_VERIFICATION_RECOVERY = (
    "The staged output failed this surface's independent verification against the "
    "plan, so nothing was published and the destination was left untouched; retry "
    "against a destination the process can read and write."
)
_RECOVERIES = {
    "sanitize_source_hash_mismatch": _HASH_MISMATCH_RECOVERY,
    "inspect_source_hash_mismatch": _HASH_MISMATCH_RECOVERY,
    "sanitize_source_changed": _SOURCE_CHANGED_RECOVERY,
    "sanitize_source_signed": _SIGNED_RECOVERY,
    "sanitize_removals_empty": _EMPTY_REMOVALS_RECOVERY,
    "sanitize_removal_unknown": _UNKNOWN_REMOVAL_RECOVERY,
    "sanitize_removal_unsupported": _UNSUPPORTED_REMOVAL_RECOVERY,
    "sanitize_removal_duplicate": _DUPLICATE_REMOVAL_RECOVERY,
    "sanitize_removal_authors_referenced": _AUTHORS_REFERENCED_RECOVERY,
    "sanitize_staging_unavailable": _SECURITY_PUBLICATION_RECOVERIES["staging_unavailable"],
    "sanitize_staged_verification_failed": _SECURITY_PUBLICATION_RECOVERIES["verification"],
    "sanitize_publication_unavailable": _SECURITY_PUBLICATION_RECOVERIES["publication_unavailable"],
}
"""The recovery a refusal offers, keyed by refusal code."""


@dataclass(frozen=True)
class PptxSanitizationInspectRequest:
    """One read-only inventory request, bound to one source digest."""

    source: Path
    source_sha256: str


@dataclass(frozen=True)
class PptxSanitizationRequest:
    """One source-bound removal request.

    ``removals`` are exact removal target ids from the inspection receipt of the
    very bytes ``source_sha256`` names, never patterns, paths, or inferred ids.
    """

    source: Path
    destination: Path
    source_sha256: str
    removals: tuple[str, ...]


@dataclass(frozen=True)
class PptxSanitizationPart:
    """One package part as the inventory describes it."""

    name: str
    size: int
    channel: str
    content_type: str | None
    reachable: bool
    referenced_by: tuple[str, ...]
    external_relationships: tuple[str, ...]
    removable: bool
    reason: str | None
    xml_elements: tuple[str, ...] = ()
    xml_attributes: tuple[str, ...] = ()
    xml_diagnosis: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return this part's inventory record in one stable key order."""
        return {
            "name": self.name,
            "size": self.size,
            "channel": self.channel,
            "content_type": self.content_type,
            "reachable": self.reachable,
            "referenced_by": list(self.referenced_by),
            "external_relationships": list(self.external_relationships),
            "removable": self.removable,
            "reason": self.reason,
            "xml_elements": list(self.xml_elements),
            "xml_attributes": list(self.xml_attributes),
            "xml_diagnosis": self.xml_diagnosis,
        }


@dataclass(frozen=True)
class PptxSanitizationTarget:
    """One selectable removal target and the complete scope removing it covers."""

    target: str
    channel: str
    parts: tuple[str, ...]
    relationships: tuple[str, ...]
    content_types: tuple[str, ...]
    size: int

    def to_dict(self) -> dict[str, Any]:
        """Return this target's declared removal scope in one stable key order."""
        return {
            "target": self.target,
            "channel": self.channel,
            "parts": list(self.parts),
            "relationships": list(self.relationships),
            "content_types": list(self.content_types),
            "size": self.size,
        }


@dataclass(frozen=True)
class PptxSanitizationChannel:
    """One channel's parts, size, and removal standing."""

    channel: str
    parts: tuple[str, ...]
    size: int
    sensitive: bool
    removable: bool
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return this channel's summary in one stable key order."""
        return {
            "channel": self.channel,
            "parts": list(self.parts),
            "size": self.size,
            "sensitive": self.sensitive,
            "removable": self.removable,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PptxSanitizationExternal:
    """One external relationship, reported without its target."""

    owner: str
    identifier: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        """Return this external relationship in one stable key order."""
        return {"owner": self.owner, "identifier": self.identifier, "kind": self.kind}


@dataclass(frozen=True)
class PptxSanitizationResidual:
    """One category of content this surface cannot remove or cannot inspect."""

    code: str
    detail: str
    targets: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return this residual in one stable key order."""
        return {"code": self.code, "detail": self.detail, "targets": list(self.targets)}


@dataclass(frozen=True)
class PptxSanitizationInventory:
    """The complete, content-safe inventory of one package.

    ``package_sha256`` is the digest of the package this inventory describes: the
    inspected source for an inspection report, and the verified output for a
    published sanitization report.
    """

    package_sha256: str
    parts: tuple[PptxSanitizationPart, ...]
    channels: tuple[PptxSanitizationChannel, ...]
    targets: tuple[PptxSanitizationTarget, ...]
    orphans: tuple[str, ...]
    external_relationships: tuple[PptxSanitizationExternal, ...]
    signed: bool
    unsupported: tuple[PptxSanitizationResidual, ...]
    notes: tuple[str, ...]

    @property
    def part_count(self) -> int:
        """Return how many parts the inventory describes."""
        return len(self.parts)

    def to_dict(self) -> dict[str, Any]:
        """Return the machine-readable inventory in one stable key order."""
        return {
            "package_sha256": self.package_sha256,
            "part_count": self.part_count,
            "parts": [part.to_dict() for part in self.parts],
            "channels": [channel.to_dict() for channel in self.channels],
            "targets": [target.to_dict() for target in self.targets],
            "orphans": list(self.orphans),
            "external_relationships": [
                relationship.to_dict() for relationship in self.external_relationships
            ],
            "signed": self.signed,
            "unsupported": [residual.to_dict() for residual in self.unsupported],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class PptxSanitizationPlan:
    """One resolved removal: exactly what is removed, rewritten, and preserved."""

    targets: tuple[PptxSanitizationTarget, ...]
    remove_parts: frozenset[str]
    rewrite_parts: dict[str, bytes]
    preserved_parts: frozenset[str]


@dataclass(frozen=True)
class PptxSanitizationReport:
    """The content-safe result of one inspection or one sanitization.

    ``inventory`` describes the package the operation ends on: the inspected
    source for an inspection, and the verified output - with every retained
    opaque and unsupported channel - for a published sanitization.
    """

    operation: str
    status: str
    code: str | None
    source_sha256: str
    removals: tuple[str, ...] = ()
    removed_parts: tuple[str, ...] = ()
    rewritten_parts: tuple[str, ...] = ()
    preserved_part_count: int = 0
    destination_sha256: str | None = None
    inventory: PptxSanitizationInventory | None = None
    recovery: str | None = None

    @property
    def passed(self) -> bool:
        """Return whether the operation completed without refusing."""
        return self.status != _REFUSED

    def to_dict(self) -> dict[str, Any]:
        """Return the machine-readable report in one stable key order."""
        return {
            "schema_version": 1,
            "operation": self.operation,
            "passed": self.passed,
            "status": self.status,
            "code": self.code,
            "source_sha256": self.source_sha256,
            "removals": list(self.removals),
            "removed_parts": list(self.removed_parts),
            "rewritten_parts": list(self.rewritten_parts),
            "preserved_part_count": self.preserved_part_count,
            "destination_sha256": self.destination_sha256,
            "inventory": None if self.inventory is None else self.inventory.to_dict(),
            "recovery": self.recovery,
        }


def parse_pptx_sanitization_inspect_request(
    value: Any,
) -> PptxSanitizationInspectRequest:
    """Parse the two-field inspection request without coercion."""

    if not isinstance(value, Mapping):
        raise TypeError("pptx_sanitization_inspect_request_invalid")
    if set(value) != _INSPECT_REQUEST_FIELDS:
        raise ValueError("pptx_sanitization_inspect_request_fields_invalid")
    source = value["source"]
    if not isinstance(source, str) or not source:
        raise ValueError("pptx_sanitization_source_invalid")
    return PptxSanitizationInspectRequest(
        source=Path(source),
        source_sha256=_require_sha256(value["source_sha256"], "pptx_sanitization_source_sha256"),
    )


def load_pptx_sanitization_inspect_request(
    path: str | Path,
) -> PptxSanitizationInspectRequest:
    """Load one UTF-8 JSON inspection request through the same strict parser."""

    with Path(path).open(encoding="utf-8") as stream:
        return parse_pptx_sanitization_inspect_request(json.load(stream))


def _parse_removals(value: Any) -> tuple[str, ...]:
    """Return one request's unique removal target ids, refusing anything else."""

    if not isinstance(value, list) or not all(
        isinstance(removal, str) and removal for removal in value
    ):
        raise ValueError("pptx_sanitization_removals_invalid")
    removals: tuple[str, ...] = tuple(value)
    if len(set(removals)) != len(removals):
        raise ValueError("pptx_sanitization_removals_duplicate")
    return removals


def parse_pptx_sanitization_request(value: Any) -> PptxSanitizationRequest:
    """Parse the intentionally small public request schema without coercion."""

    if not isinstance(value, Mapping):
        raise TypeError("pptx_sanitization_request_invalid")
    if set(value) != _REQUEST_FIELDS:
        raise ValueError("pptx_sanitization_request_fields_invalid")
    source = value["source"]
    destination = value["destination"]
    if not isinstance(source, str) or not source:
        raise ValueError("pptx_sanitization_source_invalid")
    if not isinstance(destination, str) or not destination:
        raise ValueError("pptx_sanitization_destination_invalid")
    return PptxSanitizationRequest(
        source=Path(source),
        destination=Path(destination),
        source_sha256=_require_sha256(value["source_sha256"], "pptx_sanitization_source_sha256"),
        removals=_parse_removals(value["removals"]),
    )


def load_pptx_sanitization_request(path: str | Path) -> PptxSanitizationRequest:
    """Load one UTF-8 JSON sanitization request through the same strict parser."""

    with Path(path).open(encoding="utf-8") as stream:
        return parse_pptx_sanitization_request(json.load(stream))


def _refusal(
    operation: str,
    source_sha256: str | None,
    code: str,
    *,
    recovery: str | None = None,
    removals: tuple[str, ...] = (),
) -> PptxSanitizationReport:
    """Return one refusal report, carrying nothing a request did not state."""

    return PptxSanitizationReport(
        operation=operation,
        status=_REFUSED,
        code=code,
        source_sha256=source_sha256,
        removals=removals,
        recovery=recovery,
    )


def _owner_label(owner: str) -> str:
    """Return one relationship owner's report label; the root part is ``/``."""

    return owner or "/"


def _rels_part_for(owner: str) -> str:
    """Return the relationships part name of one owner, root included."""

    return rels_part_name(owner) if owner else "_rels/.rels"


def _declared_as(content_type: str | None, expected: str) -> bool:
    """Return whether one part's declared type agrees with a recognized channel."""

    if content_type is None or content_type == expected:
        return True
    return content_type.casefold() in _NEUTRAL_CONTENT_TYPES


def _channel_for_part(name: str, content_type: str | None, thumbnails: frozenset[str]) -> str:
    """Classify one part into exactly one channel of this inventory."""

    if name == CONTENT_TYPES_PART:
        return "content_types"
    if name.endswith(".rels"):
        return "relationships"
    if name in thumbnails:
        return "thumbnail"
    if name == CORE_PROPERTIES_PART and _declared_as(content_type, CORE_PROPERTIES_CONTENT_TYPE):
        return "core_properties"
    if name == EXTENDED_PROPERTIES_PART and _declared_as(
        content_type, EXTENDED_PROPERTIES_CONTENT_TYPE
    ):
        return "extended_properties"
    if name == CUSTOM_PROPERTIES_PART and _declared_as(
        content_type, CUSTOM_PROPERTIES_CONTENT_TYPE
    ):
        return "custom_properties"
    if name == COMMENT_AUTHORS_PART and _declared_as(
        content_type, LEGACY_COMMENT_AUTHORS_CONTENT_TYPE
    ):
        return "comment_authors"
    if _COMMENT_PART.match(name) and _declared_as(content_type, LEGACY_COMMENTS_CONTENT_TYPE):
        return "comments"
    if _NOTES_SLIDE_PART.match(name) and _declared_as(content_type, NOTES_SLIDE_CONTENT_TYPE):
        return "notes_slides"
    if _MODERN_COMMENT_PART.match(name) or name == _MODERN_PERSON_PART:
        return "modern_comments"
    if content_type in (MODERN_COMMENTS_CONTENT_TYPE, MODERN_PERSON_CONTENT_TYPE):
        return "modern_comments"
    if (
        name.startswith(SIGNATURE_PREFIX)
        or posixpath.basename(name) == SIGNATURE_ORIGIN_PART
        or (content_type is not None and content_type.casefold() in _SIGNATURE_CONTENT_TYPES)
    ):
        return "signatures"
    if name.startswith(EXTERNAL_LINKS_PREFIX):
        return "external_links"
    if name.startswith(MEDIA_PREFIX):
        return "media"
    if name.startswith(EMBEDDED_PREFIXES) or name == MACRO_PART:
        return "embedded_payloads"
    if name.startswith(_SLIDES_PREFIX):
        return "slides"
    if name == PRESENTATION_PART or name.startswith(_STRUCTURAL_PREFIXES):
        return "structure"
    return "unrecognized"


def _thumbnail_parts(package: Package) -> frozenset[str]:
    """Return the parts the package declares or names as its thumbnail."""

    names = {name for name in package.parts if name.startswith(THUMBNAIL_PREFIX)}
    for relationship in package.part_rels(""):
        if relationship.external or relationship.kind != THUMBNAIL_RELATIONSHIP_KIND:
            continue
        names.add(resolve_target("", relationship.target))
    return frozenset(names)


def _signature_markers(package: Package) -> tuple[str, ...]:
    """Return every package fact that marks a digital signature.

    Signature parts, declared signature content types, and signature
    relationships are each checked, so detection never depends on one producer's
    naming.  A marker names a part or a relationship, never a value.
    """

    markers: list[str] = []
    overrides = content_type_overrides(package.parts)
    for name in sorted(package.parts):
        if name.startswith(SIGNATURE_PREFIX) or (posixpath.basename(name) == SIGNATURE_ORIGIN_PART):
            markers.append(f"part {name}")
        content_type = overrides.get(name)
        if content_type is not None and content_type.casefold() in (_SIGNATURE_CONTENT_TYPES):
            markers.append(f"content type of {name}: {content_type}")
    for owner in sorted(package.relationships):
        for relationship in package.part_rels(owner):
            if relationship.type.startswith(_SIGNATURE_RELATIONSHIP_PREFIX):
                markers.append(f"relationship {relationship.identifier} in {_owner_label(owner)}")
    return tuple(dict.fromkeys(markers))


def _internal_references(package: Package) -> dict[str, tuple[tuple[str, str], ...]]:
    """Return target part name -> (owner, relationship id) for every internal rel."""

    references: dict[str, list[tuple[str, str]]] = {}
    for owner in package.relationships:
        for relationship in package.part_rels(owner):
            if relationship.external:
                continue
            target = resolve_target(owner, relationship.target)
            references.setdefault(target, []).append((owner, relationship.identifier))
    return {target: tuple(owners) for target, owners in references.items()}


def _reachable_targets(package: Package) -> frozenset[str]:
    """Return every part the package root reaches through internal relationships.

    The walk starts at the package root part, which has no part name of its own,
    and resolves each target against the part that declares it, so a
    package-absolute target is reached exactly like a relative one.

    The graph walked is the engine's own parsed package, through the
    relationships and target resolution of :mod:`wolfppt.render_package`, not a
    second parse.  ``reporting_continuations.reachable_parts`` is not reused for
    it: that walk is rooted at named parts (its ``slide_rels_part`` cannot name
    the root-owned ``_rels/.rels``), so a root walk through it would report no
    reachability at all for an ordinary package.
    """

    parts = package.parts
    reached: set[str] = set()
    pending = [""]
    seen = {""}
    while pending:
        owner = pending.pop()
        for relationship in package.part_rels(owner):
            if relationship.external:
                continue
            target = resolve_target(owner, relationship.target)
            if target not in parts or target in seen:
                continue
            seen.add(target)
            reached.add(target)
            pending.append(target)
    return frozenset(reached)


def _is_reachable(name: str, reached: frozenset[str]) -> bool:
    """Return whether one part is in use: reached, content types, or an owner's rels."""

    if name == CONTENT_TYPES_PART:
        return True
    if name.endswith(".rels"):
        owner = _rels_owner(name)
        return owner == "" or owner in reached
    return name in reached


def _rels_owner(name: str) -> str:
    """Return the part one relationships part describes; the root part is ``""``."""

    parent, filename = posixpath.split(name)
    return posixpath.join(posixpath.dirname(parent), filename[: -len(".rels")])


def _markup_relationship_ids(package: Package, owner: str) -> frozenset[str] | None:
    """Return the relationship ids one part's markup references, or ``None``.

    ``None`` means the part's markup could not be read, which is never treated as
    "references nothing": a removal whose safety cannot be shown is refused.
    """

    if not owner.endswith(".xml"):
        return frozenset()
    payload = package.parts.get(owner)
    if payload is None:
        return frozenset()
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return None
    return frozenset(
        value
        for element in root.iter()
        for name, value in element.attrib.items()
        if name.startswith(f"{{{R_NS}}}")
    )


def _markup_ids(
    package: Package, owner: str, cache: dict[str, frozenset[str] | None]
) -> frozenset[str] | None:
    """Return one owner's markup relationship ids, parsed at most once."""

    if owner not in cache:
        cache[owner] = _markup_relationship_ids(package, owner)
    return cache[owner]


def _removability(
    package: Package,
    name: str,
    channel: str,
    references: Mapping[str, tuple[tuple[str, str], ...]],
    cache: dict[str, frozenset[str] | None],
) -> tuple[bool, str | None]:
    """Return whether one part can be removed, and why not when it cannot."""

    if channel not in REMOVABLE_CHANNELS:
        if _active_xml_root(name, package.content_type(name)):
            return False, "part_active_xml_removal_unsupported"
        return False, _REASON_BY_CHANNEL[channel]
    for owner, identifier in references.get(name, ()):
        identifiers = _markup_ids(package, owner, cache)
        if identifiers is None:
            return False, "part_owner_markup_unreadable"
        if identifier in identifiers:
            return False, "part_referenced_by_markup"
    return True, None


def _hidden_slides(package: Package) -> tuple[str, ...]:
    """Return every slide part the package marks hidden."""

    hidden: list[str] = []
    for name in sorted(package.parts):
        if not name.startswith(_SLIDES_PREFIX):
            continue
        try:
            root = ET.fromstring(package.parts[name])
        except ET.ParseError:
            continue
        if root.get("show", "").casefold() in {"0", "false"}:
            hidden.append(name)
    return tuple(hidden)


def _channel_summary(
    records: tuple[PptxSanitizationPart, ...],
) -> tuple[PptxSanitizationChannel, ...]:
    """Group the part records into their channels, in one fixed channel order."""

    summary: list[PptxSanitizationChannel] = []
    for channel in CHANNELS:
        members = tuple(record for record in records if record.channel == channel)
        if not members:
            continue
        summary.append(
            PptxSanitizationChannel(
                channel=channel,
                parts=tuple(record.name for record in members),
                size=sum(record.size for record in members),
                sensitive=channel in SENSITIVE_CHANNELS,
                removable=channel in REMOVABLE_CHANNELS,
                reason=None if channel in REMOVABLE_CHANNELS else _REASON_BY_CHANNEL[channel],
            )
        )
    return tuple(summary)


def _residuals(
    package: Package,
    records: tuple[PptxSanitizationPart, ...],
    orphans: tuple[str, ...],
    dangling: tuple[str, ...],
    signatures: tuple[str, ...],
    external: tuple[PptxSanitizationExternal, ...],
) -> tuple[PptxSanitizationResidual, ...]:
    """Return every category this report will not call clean, in a fixed order."""

    def channel_parts(channel: str) -> tuple[str, ...]:
        return tuple(record.name for record in records if record.channel == channel)

    residuals: list[PptxSanitizationResidual] = []
    if signatures:
        residuals.append(
            PptxSanitizationResidual("signature_parts_present", _SIGNATURE_DETAIL, signatures)
        )
    if embedded := channel_parts("embedded_payloads"):
        residuals.append(
            PptxSanitizationResidual(
                "embedded_payload_bytes_not_inspected", _EMBEDDED_DETAIL, embedded
            )
        )
    if media := channel_parts("media"):
        residuals.append(
            PptxSanitizationResidual("media_bytes_not_inspected", _MEDIA_DETAIL, media)
        )
    try:
        modern = modern_comment_markers(package.parts)
    except CommentRefusal as exc:
        raise PackageRefusal(
            "the package's comment markers cannot be read as relationships"
        ) from exc
    if modern:
        residuals.append(
            PptxSanitizationResidual(
                "modern_threaded_comments_unsupported", _MODERN_DETAIL, tuple(modern)
            )
        )
    if external:
        residuals.append(
            PptxSanitizationResidual(
                "external_relationship_targets_not_reported",
                _EXTERNAL_DETAIL,
                tuple(
                    f"{relationship.owner}#{relationship.identifier}" for relationship in external
                ),
            )
        )
    if unrecognized := channel_parts("unrecognized"):
        residuals.append(
            PptxSanitizationResidual("part_not_recognized", _UNRECOGNIZED_DETAIL, unrecognized)
        )
    for code in (
        "active_xml_malformed",
        "active_xml_declaration_unsupported",
        "active_xml_root_invalid",
    ):
        targets = tuple(record.name for record in records if record.xml_diagnosis == code)
        if targets:
            residuals.append(
                PptxSanitizationResidual(
                    code, "Active XML could not be inventoried safely.", targets
                )
            )
    if hidden := _hidden_slides(package):
        residuals.append(PptxSanitizationResidual("hidden_slides_present", _HIDDEN_DETAIL, hidden))
    if dangling:
        residuals.append(
            PptxSanitizationResidual(
                "preexisting_dangling_relationships", _DANGLING_DETAIL, dangling
            )
        )
    if orphans:
        residuals.append(
            PptxSanitizationResidual("preexisting_orphan_parts", _ORPHAN_DETAIL, orphans)
        )
    return tuple(residuals)


def _target_for(
    package: Package,
    record: PptxSanitizationPart,
    references: Mapping[str, tuple[tuple[str, str], ...]],
    overrides: frozenset[str],
) -> PptxSanitizationTarget:
    """Return one part's removal target and the complete scope removing it covers."""

    rels_part = rels_part_name(record.name)
    parts = (record.name, rels_part) if rels_part in package.parts else (record.name,)
    return PptxSanitizationTarget(
        target=record.name,
        channel=record.channel,
        parts=parts,
        relationships=tuple(
            f"{_owner_label(owner)}#{identifier}"
            for owner, identifier in references.get(record.name, ())
        ),
        content_types=tuple(part for part in parts if part in overrides),
        size=sum(len(package.parts[part]) for part in parts),
    )


def inventory_package(package: Package) -> PptxSanitizationInventory:
    """Return the complete inventory of one admitted package.

    The inventory is read-only and content-safe: it names parts, sizes, channels,
    reachability, external relationships, orphans, removal targets with their
    declared scope, and every category this surface will not call clean.  It
    raises :class:`wolfppt.render_package.PackageRefusal` when the package's own
    relationship parts cannot be read as OPC relationships, because no
    reachability or removal claim can be made about such a package.
    """

    parts = package.parts
    references = _internal_references(package)
    reached = _reachable_targets(package)
    overrides = frozenset(content_type_overrides(parts))
    thumbnails = _thumbnail_parts(package)
    signatures = _signature_markers(package)
    markup: dict[str, frozenset[str] | None] = {}
    records: list[PptxSanitizationPart] = []
    for name in sorted(parts):
        channel = _channel_for_part(name, package.content_type(name), thumbnails)
        removable, reason = _removability(package, name, channel, references, markup)
        xml = ((), (), None)
        if expected := _active_xml_root(name, package.content_type(name)):
            xml = _active_xml_members(parts[name], expected)
        records.append(
            PptxSanitizationPart(
                name=name,
                size=len(parts[name]),
                channel=channel,
                content_type=package.content_type(name),
                reachable=_is_reachable(name, reached),
                referenced_by=tuple(
                    sorted({_owner_label(owner) for owner, _identifier in references.get(name, ())})
                ),
                external_relationships=tuple(
                    relationship.identifier
                    for relationship in package.part_rels(name)
                    if relationship.external
                ),
                removable=removable,
                reason=reason,
                xml_elements=xml[0],
                xml_attributes=xml[1],
                xml_diagnosis=xml[2],
            )
        )
    inventory_records = tuple(records)
    targets = tuple(
        _target_for(package, record, references, overrides)
        for record in inventory_records
        if record.removable
    )
    external = tuple(
        sorted(
            (
                PptxSanitizationExternal(
                    owner=_owner_label(owner),
                    identifier=relationship.identifier,
                    kind=relationship.kind,
                )
                for owner in package.relationships
                for relationship in package.part_rels(owner)
                if relationship.external
            ),
            key=lambda entry: (entry.owner, entry.identifier),
        )
    )
    orphans = tuple(sorted(name for name in parts if not _is_reachable(name, reached)))
    dangling = tuple(
        sorted(
            f"{_owner_label(owner)}#{identifier}"
            for target, owners in references.items()
            if target not in parts
            for owner, identifier in owners
        )
    )
    return PptxSanitizationInventory(
        package_sha256=package.digest,
        parts=inventory_records,
        channels=_channel_summary(inventory_records),
        targets=targets,
        orphans=orphans,
        external_relationships=external,
        signed=bool(signatures),
        unsupported=_residuals(package, inventory_records, orphans, dangling, signatures, external),
        notes=SANITIZATION_NOTES,
    )


def _drop_relationships(payload: bytes, removed: frozenset[str]) -> bytes | None:
    """Return one relationships part without the named relationships."""

    root = ET.fromstring(payload)
    if root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise PackageRefusal("a relationship part has an invalid root element")
    dropped = False
    for element in list(root):
        if element.tag != f"{{{PKG_REL_NS}}}Relationship":
            continue
        if element.get("Id") in removed:
            root.remove(element)
            dropped = True
    return relationships_xml(root) if dropped else None


def _drop_content_type_overrides(package: Package, removed: frozenset[str]) -> bytes | None:
    """Return ``[Content_Types].xml`` without the overrides of removed parts."""

    if not removed:
        return None
    root = ET.fromstring(package.parts[CONTENT_TYPES_PART])
    if root.tag != f"{{{CONTENT_TYPES_NS}}}Types":
        return None
    dropped = False
    for element in list(root):
        if element.tag != f"{{{CONTENT_TYPES_NS}}}Override":
            continue
        part_name = element.get("PartName")
        if part_name and normalize_part(part_name) in removed:
            root.remove(element)
            dropped = True
    return content_types_xml(root) if dropped else None


def plan_package_sanitization(
    package: Package,
    removals: tuple[str, ...],
    *,
    inventory: PptxSanitizationInventory | None = None,
) -> PptxSanitizationPlan | str:
    """Resolve one selection into exactly what is removed, rewritten, and preserved.

    The plan is pure: it reads the package and the inventory it is derived from
    and returns either a plan or the refusal code that stops the request.  A
    removal that is not a target of this package's inventory, a removal this
    surface cannot verify, a repeated removal, and an empty selection are all
    refused here, before any byte is written.
    """

    if inventory is None:
        inventory = inventory_package(package)
    if len(set(removals)) != len(removals):
        return "sanitize_removal_duplicate"
    if not removals:
        return "sanitize_removals_empty"
    by_target = {target.target: target for target in inventory.targets}
    by_part = {record.name: record for record in inventory.parts}
    selected: list[PptxSanitizationTarget] = []
    for removal in removals:
        target = by_target.get(removal)
        if target is None:
            return (
                "sanitize_removal_unsupported" if removal in by_part else "sanitize_removal_unknown"
            )
        selected.append(target)
    remove_parts = frozenset(part for target in selected for part in target.parts)
    legacy_comments = frozenset(
        record.name for record in inventory.parts if record.channel == "comments"
    )
    if COMMENT_AUTHORS_PART in remove_parts and legacy_comments - remove_parts:
        return "sanitize_removal_authors_referenced"
    references = _internal_references(package)
    dropped: dict[str, set[str]] = {}
    for part in remove_parts:
        for owner, identifier in references.get(part, ()):
            if owner in remove_parts:
                continue
            dropped.setdefault(owner, set()).add(identifier)
    rewrite_parts: dict[str, bytes] = {}
    for owner, identifiers in dropped.items():
        rels_part = _rels_part_for(owner)
        rewritten = _drop_relationships(package.parts[rels_part], frozenset(identifiers))
        if rewritten is not None:
            rewrite_parts[rels_part] = rewritten
    if (content_types := _drop_content_type_overrides(package, remove_parts)) is not None:
        rewrite_parts[CONTENT_TYPES_PART] = content_types
    return PptxSanitizationPlan(
        targets=tuple(selected),
        remove_parts=remove_parts,
        rewrite_parts=rewrite_parts,
        preserved_parts=frozenset(package.parts) - remove_parts - set(rewrite_parts),
    )


def _source_guard(
    request: PptxSanitizationRequest,
) -> tuple[Path, Path] | PptxSanitizationReport:
    """Resolve both paths and refuse an aliased, missing, or unplaceable pair."""

    source = request.source.resolve()
    # The destination stays exactly as the request wrote it.  Resolving it would
    # follow a symbolic link, so a dangling destination link would silently
    # become a different output path instead of being refused and preserved.
    destination = request.destination
    if source == destination.resolve():
        return _refusal(
            SANITIZE,
            request.source_sha256,
            "sanitize_source_destination_same",
            removals=request.removals,
        )
    if not source.is_file():
        return _refusal(
            SANITIZE,
            request.source_sha256,
            "sanitize_source_missing",
            removals=request.removals,
        )
    if not destination.parent.is_dir():
        return _refusal(
            SANITIZE,
            request.source_sha256,
            "sanitize_destination_parent_missing",
            removals=request.removals,
        )
    return source, destination


def _snapshot(
    operation: str,
    source_sha256: str,
    source: Path,
    limits: PptxPackageLimits,
    removals: tuple[str, ...] = (),
) -> bytes | PptxSanitizationReport:
    """Read one private exact-byte snapshot, bounded before it is allocated."""

    limit = limits.max_archive_size
    try:
        with source.open("rb") as stream:
            snapshot = stream.read(limit + 1)
    except OSError:
        return _refusal(
            operation,
            source_sha256,
            f"{operation}_source_unreadable",
            removals=removals,
        )
    if len(snapshot) > limit:
        return _refusal(
            operation,
            source_sha256,
            f"{operation}_source_size_limit",
            removals=removals,
            recovery=(
                f"The source holds more than the {limit} byte package archive limit "
                f"this surface admits; the bound stopped the snapshot after "
                f"{len(snapshot)} bytes.  Use a smaller source package."
            ),
        )
    return snapshot


def _admit(
    operation: str,
    source: Path,
    source_sha256: str,
    limits: PptxPackageLimits,
    removals: tuple[str, ...] = (),
) -> tuple[Package, bytes] | PptxSanitizationReport:
    """Admit one source, returning the admitted package and the snapshot it came from.

    The snapshot is returned with the package so the writer copies from the very
    bytes that were bounded, preflighted, digested against the request, and
    parsed, rather than from a second read of the mutable source path.
    """

    snapshot = _snapshot(operation, source_sha256, source, limits, removals)
    if not isinstance(snapshot, bytes):
        return snapshot
    digest = hashlib.sha256(snapshot).hexdigest()
    if digest != source_sha256:
        return _refusal(
            operation,
            source_sha256,
            f"{operation}_source_hash_mismatch",
            removals=removals,
            recovery=_HASH_MISMATCH_RECOVERY,
        )
    envelope = _zip_envelope_refusal(snapshot, limits)
    if envelope is not None:
        return _refusal(
            operation,
            source_sha256,
            f"{operation}_source_{envelope.code}",
            removals=removals,
            recovery=envelope.recovery,
        )
    admission = _admitted_package(operation, source, snapshot, digest)
    if isinstance(admission, str):
        return _refusal(operation, source_sha256, admission, removals=removals)
    return admission, snapshot


def _inventory_or_refusal(
    operation: str,
    package: Package,
    source_sha256: str,
    removals: tuple[str, ...] = (),
) -> PptxSanitizationInventory | PptxSanitizationReport:
    """Return one package's inventory, or the refusal an unreadable graph earns."""

    try:
        return inventory_package(package)
    except PackageRefusal:
        return _refusal(
            operation,
            source_sha256,
            f"{operation}_source_package_invalid",
            removals=removals,
        )


def _reachable_names(inventory: PptxSanitizationInventory) -> set[str]:
    """Return the parts one inventory reports as in use."""

    return {record.name for record in inventory.parts if record.reachable}


def _recovery_for(code: str) -> str | None:
    """Return the recovery this surface offers for one staged-publication code."""

    if code.startswith("sanitize_staged_"):
        return _STAGED_VERIFICATION_RECOVERY
    return _RECOVERIES.get(code)


def inspect_pptx_sanitization(source: str | Path, *, source_sha256: str) -> PptxSanitizationReport:
    """Return one source-bound, read-only inventory of a presentation's package.

    The source is admitted through the same bounded envelope, package, and
    PresentationML authorities every operation of this surface uses, and only
    when it digests to ``source_sha256``, so the receipt a caller selects
    removals from always describes the bytes it named.
    """

    digest = _require_sha256(source_sha256, "pptx_sanitization_source_sha256")
    path = Path(source).resolve()
    if not path.is_file():
        return _refusal(INSPECT, digest, "inspect_source_missing")
    limits = PPTX_SECURITY_LIMITS
    admission = _admit(INSPECT, path, digest, limits)
    if not isinstance(admission, tuple):
        return admission
    package, _ = admission
    inventory = _inventory_or_refusal(INSPECT, package, digest)
    if not isinstance(inventory, PptxSanitizationInventory):
        return inventory
    return PptxSanitizationReport(
        operation=INSPECT,
        status=_INSPECTED,
        code=None,
        source_sha256=digest,
        preserved_part_count=inventory.part_count,
        inventory=inventory,
    )


def sanitize_pptx(request: PptxSanitizationRequest) -> PptxSanitizationReport:
    """Remove one selection of recognized channels and publish the verified result.

    Admission, planning, and writing consume one bounded immutable snapshot, so
    the package that was inspected, the package the plan was derived from, and
    the package the writer copies from are the same bytes.  The staged package is
    reopened and verified against both the plan and the source before the link,
    the source digest is re-checked immediately before the no-replace link, and a
    source that changed at any point is refused with nothing published.
    """

    guarded = _source_guard(request)
    if not isinstance(guarded, tuple):
        return guarded
    source, destination = guarded
    limits = PPTX_SECURITY_LIMITS
    admission = _admit(SANITIZE, source, request.source_sha256, limits, request.removals)
    if not isinstance(admission, tuple):
        return admission
    package, snapshot = admission
    inventory = _inventory_or_refusal(SANITIZE, package, request.source_sha256, request.removals)
    if not isinstance(inventory, PptxSanitizationInventory):
        return inventory
    if inventory.signed:
        return _refusal(
            SANITIZE,
            request.source_sha256,
            "sanitize_source_signed",
            removals=request.removals,
            recovery=_SIGNED_RECOVERY,
        )
    plan = plan_package_sanitization(package, request.removals, inventory=inventory)
    if isinstance(plan, str):
        return _refusal(
            SANITIZE,
            request.source_sha256,
            plan,
            removals=request.removals,
            recovery=_RECOVERIES.get(plan),
        )
    staged_size: int | None = None
    residual: PptxSanitizationInventory | None = None

    def write(stream: BinaryIO) -> str | None:
        try:
            with zipfile.ZipFile(io.BytesIO(snapshot)) as archive:
                copy_open_package_with_replacements(
                    archive,
                    stream,
                    plan.rewrite_parts,
                    set(plan.remove_parts),
                )
        except OSError:
            # A destination directory that refuses the sibling staging file, a
            # full disk, or a stream that fails mid-write is a refusal, not a
            # traceback.
            return "sanitize_staging_unavailable"
        return None

    def verify(staged: Path) -> str | None:
        nonlocal staged_size, residual
        staged_size = staged.stat().st_size
        if staged_size > limits.max_archive_size:
            return "sanitize_staged_size_limit"
        output_payload = staged.read_bytes()
        if _zip_envelope_refusal(output_payload, limits) is not None:
            return "sanitize_staged_package_invalid"
        try:
            output = read_package_bytes(staged, output_payload)
        except PackageRefusal:
            return "sanitize_staged_package_invalid"
        if _presentation_refusal(output) is not None:
            return "sanitize_staged_presentation_invalid"
        removed = plan.remove_parts
        if set(output.parts) != set(package.parts) - removed:
            return "sanitize_staged_part_set_mismatch"
        for name, payload in output.parts.items():
            planned = plan.rewrite_parts.get(name)
            if planned is not None:
                if payload != planned:
                    return "sanitize_staged_rewrite_mismatch"
            elif payload != package.parts[name]:
                return "sanitize_staged_preserved_bytes_changed"
        for owner in output.relationships:
            for relationship in output.part_rels(owner):
                if relationship.external:
                    continue
                if resolve_target(owner, relationship.target) in removed:
                    return "sanitize_staged_relationship_dangling"
        if removed & set(_internal_references(output)):
            return "sanitize_staged_relationship_dangling"
        if removed & set(content_type_overrides(output.parts)):
            return "sanitize_staged_content_type_dangling"
        residual = inventory_package(output)
        if _reachable_names(residual) != _reachable_names(inventory) - removed:
            return "sanitize_staged_reachability_changed"
        # Re-checked last, so the originality guard sits as close to the
        # no-replace publication as the staging protocol allows.
        try:
            current = sha256_file(source)
        except OSError:
            return "sanitize_source_missing"
        if current != request.source_sha256:
            return "sanitize_source_changed"
        return None

    code, output_digest = _publish_staged(
        destination,
        write,
        verify,
        staging_code="sanitize_staging_unavailable",
        verification_code="sanitize_staged_verification_failed",
        exists_code="sanitize_destination_invalid",
        unavailable_code="sanitize_publication_unavailable",
    )
    if code is not None:
        recovery = _recovery_for(code)
        if code == "sanitize_staged_size_limit":
            assert staged_size is not None
            recovery = (
                f"The staged output measures {staged_size} bytes, above the "
                f"{limits.max_archive_size} byte package archive limit that bounds "
                "every package this surface admits.  Sanitize a smaller source "
                "presentation."
            )
        return _refusal(
            SANITIZE,
            request.source_sha256,
            code,
            removals=request.removals,
            recovery=recovery,
        )
    assert output_digest is not None
    assert residual is not None
    return PptxSanitizationReport(
        operation=SANITIZE,
        status=_PUBLISHED,
        code=None,
        source_sha256=request.source_sha256,
        removals=request.removals,
        removed_parts=tuple(sorted(plan.remove_parts)),
        rewritten_parts=tuple(sorted(plan.rewrite_parts)),
        preserved_part_count=len(plan.preserved_parts),
        destination_sha256=output_digest,
        inventory=residual,
    )


__all__ = [
    "CHANNELS",
    "COMMENTS_DIRECTORY",
    "COMMENT_AUTHORS_PART",
    "CONTENT_TYPES_PART",
    "CORE_PROPERTIES_PART",
    "CUSTOM_PROPERTIES_PART",
    "EMBEDDED_PREFIXES",
    "EXTENDED_PROPERTIES_PART",
    "EXTERNAL_LINKS_PREFIX",
    "INSPECT",
    "MACRO_PART",
    "MEDIA_PREFIX",
    "NOTES_SLIDES_DIRECTORY",
    "OPERATIONS",
    "REMOVABLE_CHANNELS",
    "SANITIZATION_NOTES",
    "SANITIZE",
    "SENSITIVE_CHANNELS",
    "SIGNATURE_PREFIX",
    "SLIDES_DIRECTORY",
    "THUMBNAIL_PREFIX",
    "PptxSanitizationChannel",
    "PptxSanitizationExternal",
    "PptxSanitizationInspectRequest",
    "PptxSanitizationInventory",
    "PptxSanitizationPart",
    "PptxSanitizationPlan",
    "PptxSanitizationReport",
    "PptxSanitizationRequest",
    "PptxSanitizationResidual",
    "PptxSanitizationTarget",
    "inspect_pptx_sanitization",
    "inventory_package",
    "load_pptx_sanitization_inspect_request",
    "load_pptx_sanitization_request",
    "parse_pptx_sanitization_inspect_request",
    "parse_pptx_sanitization_request",
    "plan_package_sanitization",
    "sanitize_pptx",
]
