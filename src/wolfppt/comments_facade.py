"""Source-bound discovery of PowerPoint comment parts.

A PowerPoint package can carry two different comment representations, and this
module reads both so it can tell them apart:

``legacy`` (Office 2007-2019)
    ``ppt/commentAuthors.xml`` holds one presentation-scoped ``p:cmAuthorLst``
    author directory, and every slide owns one ``p:cmLst`` comments part
    (``ppt/comments/commentN.xml``) reached through a ``.../comments``
    relationship in that slide's own ``.rels`` part.
    Both Transitional and Strict namespace profiles are read without rewriting
    the source elements or changing comment identity.

``modern`` (Office 2021 and later threaded comments)
    a different content type, a different relationship type, and a
    ``ppt/person.xml`` author directory.

Only the legacy representation is authored by this package.  Every modern
marker found in a package is reported by :func:`discover_comment_targets` and
refuses mutation, so a threaded package is preserved verbatim instead of being
rewritten into a shape the legacy writer cannot verify.

Identity rules this module fixes for every reader and writer:

* an author is presentation-scoped and is addressed by its ``p:cmAuthor`` ID;
* a comment is slide-owned and is addressed by its ``p:cm/@idx`` within that
  slide's own comments part;
* a comment's ``content_sha256`` digests that comment's own element subtree, so
  a caller holding a discovered comment can tell whether the comment it
  addressed is still the comment it inspected.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any
from xml.etree import ElementTree as ET
from xml.parsers import expat

from .package_parts import (
    rels_part_for_package_part,
    resolve_package_target,
)
from .xml_helpers import (
    STRICT_A_NS,
    STRICT_R_NS,
    find_ooxml,
    findall_ooxml,
    ooxml_namespace,
)

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

LEGACY_COMMENTS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
LEGACY_COMMENT_AUTHORS_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors"
)
MODERN_COMMENT_REL = "http://schemas.microsoft.com/office/2018/10/relationships/comments"
MODERN_AUTHORS_REL = "http://schemas.microsoft.com/office/2018/10/relationships/authors"
MODERN_PERSON_REL = "http://schemas.microsoft.com/office/2018/10/relationships/person"
MODERN_POWERPOINT_NS = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"
MODERN_POWERPOINT_NS_ALT = "http://schemas.microsoft.com/office/powerpoint/2018/04/main"
MODERN_POWERPOINT_NAMESPACES = frozenset({MODERN_POWERPOINT_NS, MODERN_POWERPOINT_NS_ALT})
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
COMMENT_COMMAND_NS = "http://schemas.microsoft.com/office/powerpoint/2013/main/command"

LEGACY_COMMENTS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.comments+xml"
)
LEGACY_COMMENT_AUTHORS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml"
)
MODERN_COMMENTS_CONTENT_TYPE = "application/vnd.ms-powerpoint.comments+xml"
MODERN_AUTHORS_CONTENT_TYPE = "application/vnd.ms-powerpoint.authors+xml"
MODERN_PERSON_CONTENT_TYPE = "application/vnd.ms-powerpoint.person+xml"

PACKAGE_RELATIONSHIPS_PART = "_rels/.rels"
COMMENT_AUTHORS_PART = "ppt/commentAuthors.xml"
AUTHORS_PART = "ppt/authors.xml"
COMMENTS_DIRECTORY = "ppt/comments"

OPERATIONS = ("add", "update", "delete")

COMMENT_DATE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")
SHA256_DIGEST = re.compile(r"[0-9a-f]{64}\Z")

_COMMENT_LOCAL_NAMES = frozenset({"comment", "comments"})
_MODERN_PART_NAMES = frozenset({"ppt/person.xml", "ppt/authors.xml"})

ET.register_namespace("p", P_NS)
ET.register_namespace("p188", MODERN_POWERPOINT_NS)
ET.register_namespace("a", A_NS)

DISCOVERY_NOTES = (
    (
        "an author is presentation-scoped: ppt/commentAuthors.xml owns every "
        "author ID, and an existing author is reused instead of duplicated"
    ),
    (
        "a comment is slide-owned: ppt/comments/commentN.xml is reached only "
        "through its own slide's relationship part"
    ),
    (
        "a comment's content_sha256 digests that comment's own subtree, so an "
        "update or delete can require the exact comment it discovered"
    ),
    (
        "modern/threaded comments are reported and refused for mutation; their "
        "parts, relationships, and content types are preserved verbatim"
    ),
    (
        "discovery never mutates the source package: the reported "
        "source_sha256 is the raw digest of the file that was read"
    ),
)


class CommentRefusal(ValueError):
    """Raised when a comment package cannot be read or safely rewritten."""


@dataclass(frozen=True)
class CommentAuthor:
    """One presentation-scoped legacy comment author."""

    author_id: int
    name: str
    initials: str
    last_index: int
    color_index: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "author_id": self.author_id,
            "name": self.name,
            "initials": self.initials,
            "last_index": self.last_index,
            "color_index": self.color_index,
        }


@dataclass(frozen=True)
class ModernCommentAuthor:
    """One presentation-scoped modern comment author from ppt/authors.xml."""

    id: str
    name: str
    initials: str
    user_id: str = ""
    provider_id: str = "AD"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "initials": self.initials,
            "user_id": self.user_id,
            "provider_id": self.provider_id,
        }


@dataclass(frozen=True)
class DiscoveredReaction:
    """One reaction on a modern comment or reply (read-preserve only)."""

    reaction_id: str
    author_id: str
    author: str
    initials: str
    reaction_type: str  # emoji or like indicator
    date: str = ""
    content_sha256: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "reaction_id": self.reaction_id,
            "author_id": self.author_id,
            "author": self.author,
            "initials": self.initials,
            "reaction_type": self.reaction_type,
            "date": self.date,
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True)
class DiscoveredReply:
    """One modern threaded comment reply."""

    reply_id: str
    author_id: str
    author: str
    initials: str
    date: str
    text: str
    status: str = "active"
    content_sha256: str = ""
    reactions: tuple[DiscoveredReaction, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "reply_id": self.reply_id,
            "author_id": self.author_id,
            "author": self.author,
            "initials": self.initials,
            "date": self.date,
            "text": self.text,
            "status": self.status,
            "content_sha256": self.content_sha256,
            "reactions": [r.as_dict() for r in self.reactions],
        }


@dataclass(frozen=True)
class CommentAnchorMoniker:
    """Declared slide anchor identifiers, without resolving or inventing them."""

    document_attributes: Mapping[str, str] | None
    slide_attributes: Mapping[str, str] | None

    @property
    def slide_id(self) -> int | None:
        raw = None if self.slide_attributes is None else self.slide_attributes.get("sldId")
        return None if raw is None else int(raw)


@dataclass(frozen=True)
class OpaqueCommentExtension:
    """One uninterpreted extension, with exact source XML and namespace context."""

    attributes: Mapping[str, str]
    xml: bytes
    namespaces: Mapping[str, str]

    @property
    def uri(self) -> str | None:
        return self.attributes.get("uri")


def _comment_xml_spans(
    payload: bytes, root: ET.Element
) -> dict[int, tuple[int, int, Mapping[str, str]]]:
    """Associate the existing parsed tree with lexical spans, not a second model."""
    parser = expat.ParserCreate()
    spans = []
    stack = []

    def start(_name: str, attributes: dict[str, str]) -> None:
        namespaces = dict(stack[-1][2]) if stack else {}
        for name, value in attributes.items():
            if name == "xmlns":
                namespaces[""] = value
            elif name.startswith("xmlns:"):
                namespaces[name[6:]] = value
        record = [parser.CurrentByteIndex, None, namespaces]
        spans.append(record)
        stack.append(record)

    def end(_name: str) -> None:
        record = stack.pop()
        offset = parser.CurrentByteIndex
        record[1] = (
            payload.index(b">", offset) + 1 if payload[offset : offset + 2] == b"</" else offset
        )

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(payload, True)
    return {
        id(node): (start, end, MappingProxyType(namespaces))
        for node, (start, end, namespaces) in zip(root.iter(), spans, strict=True)
    }


def _preserve_modern_extensions(payload: bytes, root: ET.Element) -> bytes:
    """Keep extension payload bytes on the existing modern edit/save path."""
    from xml.sax.saxutils import quoteattr

    original = ET.fromstring(payload)
    spans = _comment_xml_spans(payload, original)
    originals = {}
    for comment in original:
        for child in comment:
            if child.tag in {f"{{{ns}}}extLst" for ns in MODERN_POWERPOINT_NAMESPACES}:
                start, end, namespaces = spans[id(child)]
                raw = payload[start:end]
                # Make the wrapper self-contained; extension children stay byte-identical.
                opening = re.match(rb"""<(?:[^>"']|"[^"]*"|'[^']*')*>""", raw)
                assert opening is not None
                tag = opening.group()
                declarations = b"".join(
                    f" xmlns{':' + prefix if prefix else ''}={quoteattr(uri)}".encode()
                    for prefix, uri in namespaces.items()
                    if not re.search(
                        rb"\sxmlns"
                        + (b":" + re.escape(prefix.encode()) if prefix else b"")
                        + rb"\s*=",
                        tag,
                    )
                )
                offset = len(tag) - (2 if tag.endswith(b"/>") else 1)
                originals[str(comment.get("id"))] = raw[:offset] + declarations + raw[offset:]
    serialized = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if not originals:
        return serialized
    saved = ET.fromstring(serialized)
    saved_spans = _comment_xml_spans(serialized, saved)
    replacements = []
    for comment in saved:
        raw = originals.get(str(comment.get("id")))
        if raw is None:
            continue
        for child in comment:
            if child.tag in {f"{{{ns}}}extLst" for ns in MODERN_POWERPOINT_NAMESPACES}:
                start, end, _ = saved_spans[id(child)]
                replacements.append((start, end, raw))
    for start, end, raw in reversed(replacements):
        serialized = serialized[:start] + raw + serialized[end:]
    return serialized


@dataclass(frozen=True)
class DiscoveredComment:
    """One legacy or modern comment exactly as one slide declares it."""

    comment_id: int | str
    ordinal: int
    author_id: int | str
    author: str
    initials: str
    date: str
    text: str
    position: tuple[int, int]
    content_sha256: str
    kind: str = "legacy"
    replies: tuple[DiscoveredReply, ...] = ()
    status: str = "active"
    reactions: tuple[DiscoveredReaction, ...] = ()
    anchor_moniker: CommentAnchorMoniker | None = None
    attributes: Mapping[str, str] | None = None
    opaque_extensions: tuple[OpaqueCommentExtension, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "comment_id": self.comment_id,
            "ordinal": self.ordinal,
            "author_id": self.author_id,
            "author": self.author,
            "initials": self.initials,
            "date": self.date,
            "text": self.text,
            "position": {"x": self.position[0], "y": self.position[1]},
            "content_sha256": self.content_sha256,
            "reactions": [r.as_dict() for r in self.reactions],
        }
        if self.kind == "modern":
            result["kind"] = "modern"
            result["status"] = self.status
            result["reactions"] = [r.as_dict() for r in self.reactions]
            result["replies"] = [reply.as_dict() for reply in self.replies]
        return result


@dataclass(frozen=True)
class CommentRelationship:
    """The comment relationship one slide declares, and how it is classified."""

    relationship_id: str
    relationship_type: str
    kind: str
    part: str


@dataclass(frozen=True)
class SlideCommentTarget:
    """One slide's comment state under one source version."""

    slide_index: int
    slide_id: int
    slide_part: str
    comments_part: str | None
    relationship_id: str | None
    relationship_kind: str
    comments: tuple[DiscoveredComment, ...]

    @property
    def modern(self) -> bool:
        return self.relationship_kind not in {"", "legacy"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "slide_id": self.slide_id,
            "slide_part": self.slide_part,
            "comments_part": self.comments_part,
            "relationship_id": self.relationship_id,
            "relationship_kind": self.relationship_kind,
            "comment_count": len(self.comments),
            "comments": [comment.as_dict() for comment in self.comments],
        }


def part_name(value: str) -> str:
    """Return a package part name without its leading slash."""
    return str(value).strip().lstrip("/")


def sha256_file(path: Path) -> str:
    """Return the raw file digest of one package."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_package(path: str | Path) -> dict[str, bytes]:
    """Read every member of one package into memory."""
    try:
        with zipfile.ZipFile(path) as package:
            return {name: package.read(name) for name in package.namelist()}
    except (FileNotFoundError, zipfile.BadZipFile) as exc:
        raise CommentRefusal(f"{path} is not a readable OPC package") from exc


def comment_timestamp() -> str:
    """Return the current UTC instant in the ``p:cm/@dt`` lexical form."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def derived_initials(name: str) -> str:
    """Return the initials an author name implies when none are supplied."""
    initials = "".join(word[0] for word in str(name).split() if word).upper()
    return initials[:3] or "?"


def relationship_elements(payload: bytes, label: str) -> list[ET.Element]:
    """Parse one relationship part into its ``Relationship`` elements."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CommentRefusal(f"{label} relationships are malformed") from exc
    if root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise CommentRefusal(f"{label} relationships have an invalid root element")
    return list(root.findall(f"{{{PKG_REL_NS}}}Relationship"))


def relationships_xml(root: ET.Element) -> bytes:
    """Serialize an OPC relationships root under its required default namespace.

    ``xml.etree`` only emits a default namespace for the prefix the running
    process registered for that URI, so the root is normalized here instead of
    depending on which module happened to import first.
    """
    if root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise CommentRefusal("relationships root is not an OPC Relationships element")
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    match = re.search(rb"<(?P<prefix>[A-Za-z_][A-Za-z0-9_.-]*):Relationships(?=[\s>/])", payload)
    if match is None:
        return payload
    prefix = match.group("prefix").decode("ascii")
    qualified = re.compile(
        rb"(</?)" + re.escape(prefix.encode("ascii")) + rb":([A-Za-z_][\w.-]*)(?=[\s>/])"
    )
    normalized = qualified.sub(rb"\1\2", payload)
    return normalized.replace(
        f' xmlns:{prefix}="{PKG_REL_NS}"'.encode("ascii"),
        f' xmlns="{PKG_REL_NS}"'.encode("ascii"),
        1,
    )


def element_content_sha256(element: ET.Element) -> str:
    """Digest one element's own subtree, independent of prefix and write order."""
    return hashlib.sha256(_canonical_element(element).encode("utf-8")).hexdigest()


def _canonical_element(element: ET.Element) -> str:
    attributes = "?".join(f"{name}={value}" for name, value in sorted(element.attrib.items()))
    children = "|".join(_canonical_element(child) for child in element)
    return f"{element.tag}[{attributes}]{{{element.text or ''}}}({children})"


def int_attribute(element: ET.Element, name: str, label: str) -> int:
    """Return one required integer attribute of one package element."""
    value = element.get(name)
    if value is None:
        raise CommentRefusal(f"{label} has no {name} attribute")
    try:
        return int(value)
    except ValueError as exc:
        raise CommentRefusal(f"{label} {name} is not an integer") from exc


def comment_relationship_kind(relationship_type: str) -> str:
    """Classify one relationship type as legacy, modern, unsupported, or unrelated."""
    if relationship_type in (LEGACY_COMMENTS_REL, f"{STRICT_R_NS}/comments"):
        return "legacy"
    if relationship_type == MODERN_COMMENT_REL:
        return "modern"
    if relationship_type.rsplit("/", 1)[-1] in _COMMENT_LOCAL_NAMES:
        return "unsupported"
    return ""


def presentation_partname(parts: Mapping[str, bytes]) -> str:
    """Return the presentation part the package root relationship reaches."""
    payload = parts.get(PACKAGE_RELATIONSHIPS_PART)
    if payload is not None:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            root = None
        if root is not None:
            for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
                if relationship.get("Type", "").endswith("/officeDocument"):
                    return resolve_package_target("", relationship.get("Target", ""))
    return "ppt/presentation.xml"


def presentation_slide_parts(
    parts: Mapping[str, bytes],
) -> tuple[tuple[int, int, str], ...]:
    """Return ``(slide_index, slide_id, slide_part)`` in presentation order."""
    presentation_part = presentation_partname(parts)
    payload = parts.get(presentation_part)
    if payload is None:
        raise CommentRefusal("the package has no presentation part")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CommentRefusal("the presentation part is malformed") from exc
    relationships = {}
    rels_payload = parts.get(rels_part_for_package_part(presentation_part))
    if rels_payload is not None:
        relationships = {
            relationship.get("Id"): relationship
            for relationship in relationship_elements(rels_payload, presentation_part)
        }
    slides: list[tuple[int, int, str]] = []
    for slide_id in findall_ooxml(root, f".//{{{P_NS}}}sldId"):
        relationship = relationships.get(slide_id.get(f"{{{ooxml_namespace(slide_id, R_NS)}}}id"))
        if relationship is None:
            continue
        target = relationship.get("Target", "")
        if not target or relationship.get("TargetMode") == "External":
            continue
        slides.append(
            (
                len(slides),
                int(slide_id.get("id") or 0),
                resolve_package_target(presentation_part, target),
            )
        )
    return tuple(slides)


def slide_comment_relationship(
    parts: Mapping[str, bytes], slide_part: str
) -> CommentRelationship | None:
    """Return the comment relationship one slide declares, if it declares one.

    A slide that declares more than one comment relationship is ambiguous and
    refuses, because neither comments part can be edited as *the* slide's.
    """
    payload = parts.get(rels_part_for_package_part(slide_part))
    if payload is None:
        return None
    found = [
        relationship
        for relationship in relationship_elements(payload, slide_part)
        if comment_relationship_kind(relationship.get("Type", ""))
    ]
    if not found:
        return None
    if len(found) > 1:
        raise CommentRefusal(f"{slide_part} declares more than one comment relationship")
    relationship = found[0]
    relationship_type = relationship.get("Type", "")
    kind = comment_relationship_kind(relationship_type)
    target = relationship.get("Target", "")
    if kind in ("legacy", "modern") and relationship.get("TargetMode") != "External" and target:
        return CommentRelationship(
            relationship_id=str(relationship.get("Id") or ""),
            relationship_type=relationship_type,
            kind=kind,
            part=resolve_package_target(slide_part, target),
        )
    return CommentRelationship(
        relationship_id=str(relationship.get("Id") or ""),
        relationship_type=relationship_type,
        kind="unsupported",
        part=part_name(target),
    )


def content_type_overrides(parts: Mapping[str, bytes]) -> dict[str, str]:
    """Return ``part name -> content type`` for every declared part override."""
    payload = parts.get("[Content_Types].xml")
    if payload is None:
        return {}
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CommentRefusal("the package content types are malformed") from exc
    return {
        part_name(override.get("PartName", "")): override.get("ContentType", "")
        for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override")
        if override.get("PartName")
    }


def legacy_comment_authors(parts: Mapping[str, bytes]) -> tuple[CommentAuthor, ...]:
    """Return the presentation-scoped author directory, ordered by author ID."""
    payload = parts.get(COMMENT_AUTHORS_PART)
    if payload is None:
        return ()
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CommentRefusal("ppt/commentAuthors.xml is malformed") from exc
    if root.tag != f"{{{ooxml_namespace(root, P_NS)}}}cmAuthorLst":
        raise CommentRefusal("ppt/commentAuthors.xml root is not a cmAuthorLst")
    authors: dict[int, CommentAuthor] = {}
    for element in findall_ooxml(root, f"{{{P_NS}}}cmAuthor"):
        author_id = int_attribute(element, "id", "ppt/commentAuthors.xml author")
        if author_id in authors:
            raise CommentRefusal(f"ppt/commentAuthors.xml declares author id {author_id} twice")
        authors[author_id] = CommentAuthor(
            author_id=author_id,
            name=element.get("name", ""),
            initials=element.get("initials", ""),
            last_index=int(element.get("lastIdx") or 0),
            color_index=int(element.get("clrIdx") or 0),
        )
    return tuple(authors[key] for key in sorted(authors))


def comment_elements(payload: bytes, part: str) -> tuple[ET.Element, ...]:
    """Return one comments part's ``p:cm`` elements in document order."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CommentRefusal(f"{part} is malformed") from exc
    if root.tag != f"{{{ooxml_namespace(root, P_NS)}}}cmLst":
        raise CommentRefusal(f"{part} root is not a cmLst")
    return tuple(findall_ooxml(root, f"{{{P_NS}}}cm"))


def comment_part_names(parts: Mapping[str, bytes]) -> tuple[str, ...]:
    """Return every legacy comments part the package declares or reaches."""
    names = {
        part
        for part, content_type in content_type_overrides(parts).items()
        if content_type == LEGACY_COMMENTS_CONTENT_TYPE and part in parts
    }
    for _index, _slide_id, slide_part in presentation_slide_parts(parts):
        relationship = slide_comment_relationship(parts, slide_part)
        if (
            relationship is not None
            and relationship.kind == "legacy"
            and relationship.part in parts
        ):
            names.add(relationship.part)
    return tuple(sorted(names))


def highest_comment_index(parts: Mapping[str, bytes]) -> int:
    """Return the highest ``p:cm/@idx`` any author or part already occupies."""
    highest = 0
    for author in legacy_comment_authors(parts):
        highest = max(highest, author.last_index)
    for part in comment_part_names(parts):
        for element in comment_elements(parts[part], part):
            highest = max(highest, int_attribute(element, "idx", f"{part} comment"))
    return highest


def parse_comment_elements(
    parts: Mapping[str, bytes],
    part: str,
    authors: Mapping[int, CommentAuthor],
) -> tuple[DiscoveredComment, ...]:
    """Read one comments part into discovered comments, keyed by ``p:cm/@idx``."""
    comments: list[DiscoveredComment] = []
    seen: set[int] = set()
    for ordinal, element in enumerate(comment_elements(parts[part], part)):
        comment_id = int_attribute(element, "idx", f"{part} comment")
        if comment_id in seen:
            raise CommentRefusal(f"{part} declares comment id {comment_id} twice")
        seen.add(comment_id)
        author_id = int_attribute(element, "authorId", f"{part} comment {comment_id}")
        author = authors.get(author_id)
        text = find_ooxml(element, f"{{{P_NS}}}text")

        comments.append(
            DiscoveredComment(
                comment_id=comment_id,
                ordinal=ordinal,
                author_id=author_id,
                author="" if author is None else author.name,
                initials="" if author is None else author.initials,
                date=element.get("dt", ""),
                text="" if text is None else (text.text or ""),
                position=comment_position(element),
                content_sha256=element_content_sha256(element),
            )
        )
    return tuple(comments)


def comment_position(element: ET.Element) -> tuple[int, int]:
    """Return one comment's ``p:pos`` anchor, defaulting to the slide origin."""
    position = find_ooxml(element, f"{{{P_NS}}}pos")
    if position is None:
        return (0, 0)
    return (int(position.get("x") or 0), int(position.get("y") or 0))


def modern_comment_authors(
    parts: Mapping[str, bytes],
) -> tuple[ModernCommentAuthor, ...]:
    """Return presentation-scoped modern comment authors from ppt/authors.xml."""
    payload = parts.get(AUTHORS_PART)
    if payload is None:
        return ()
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CommentRefusal(f"{AUTHORS_PART} is malformed") from exc
    authors: list[ModernCommentAuthor] = []
    ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else MODERN_POWERPOINT_NS
    elements = root.findall(f"{{{ns}}}author")
    if not elements and ns != MODERN_POWERPOINT_NS:
        elements = root.findall(f"{{{MODERN_POWERPOINT_NS}}}author")
    for element in elements:
        authors.append(
            ModernCommentAuthor(
                id=element.get("id", ""),
                name=element.get("name", ""),
                initials=element.get("initials", ""),
                user_id=element.get("userId", ""),
                provider_id=element.get("providerId", "AD"),
            )
        )
    return tuple(authors)


def body_text_runs(tx_body: ET.Element) -> list[str]:
    """Read the non-empty ``a:t`` runs of a comment body in document order.

    The DrawingML namespace follows the package profile (Transitional or Strict), and the
    p188 body element itself carries no profile marker, so both run names are matched.
    """
    run_tags = (f"{{{A_NS}}}t", f"{{{STRICT_A_NS}}}t")
    return [el.text for el in tx_body.iter() if el.tag in run_tags and el.text]


def parse_modern_comment_elements(
    parts: Mapping[str, bytes],
    part: str,
    authors: Mapping[str, ModernCommentAuthor],
) -> tuple[DiscoveredComment, ...]:
    """Read one modern comments part into discovered comments."""
    try:
        root = ET.fromstring(parts[part])
    except ET.ParseError as exc:
        raise CommentRefusal(f"{part} is malformed") from exc
    ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else MODERN_POWERPOINT_NS
    cm_elements = root.findall(f"{{{ns}}}cm")
    if not cm_elements and ns != MODERN_POWERPOINT_NS:
        cm_elements = root.findall(f"{{{MODERN_POWERPOINT_NS}}}cm")
    spans = _comment_xml_spans(parts[part], root)
    comments: list[DiscoveredComment] = []
    for ordinal, element in enumerate(cm_elements):
        comment_id = element.get("id", f"cm{ordinal + 1}")
        author_id = element.get("authorId", "")
        author = authors.get(author_id)
        author_name = "" if author is None else author.name
        author_initials = "" if author is None else author.initials

        pos_el = element.find(f"{{{ns}}}pos")
        if pos_el is None and ns != MODERN_POWERPOINT_NS:
            pos_el = element.find(f"{{{MODERN_POWERPOINT_NS}}}pos")
        pos = (
            (int(pos_el.get("x") or 0), int(pos_el.get("y") or 0)) if pos_el is not None else (0, 0)
        )

        text_parts = []
        tx_body = element.find(f"{{{ns}}}txBody")
        if tx_body is None and ns != MODERN_POWERPOINT_NS:
            tx_body = element.find(f"{{{MODERN_POWERPOINT_NS}}}txBody")
        if tx_body is not None:
            text_parts = body_text_runs(tx_body)
        text = "\n".join(text_parts)

        replies: list[DiscoveredReply] = []
        reply_lst = element.find(f"{{{ns}}}replyLst")
        if reply_lst is None and ns != MODERN_POWERPOINT_NS:
            reply_lst = element.find(f"{{{MODERN_POWERPOINT_NS}}}replyLst")
        if reply_lst is not None:
            reply_elements = reply_lst.findall(f"{{{ns}}}reply")
            if not reply_elements and ns != MODERN_POWERPOINT_NS:
                reply_elements = reply_lst.findall(f"{{{MODERN_POWERPOINT_NS}}}reply")
            for r_ord, r_el in enumerate(reply_elements):
                r_id = r_el.get("id", f"reply{r_ord + 1}")
                r_auth_id = r_el.get("authorId", "")
                r_auth = authors.get(r_auth_id)
                r_text_parts = []
                r_tx = r_el.find(f"{{{ns}}}txBody")
                if r_tx is None and ns != MODERN_POWERPOINT_NS:
                    r_tx = r_el.find(f"{{{MODERN_POWERPOINT_NS}}}txBody")
                if r_tx is not None:
                    r_text_parts = body_text_runs(r_tx)

                # Parse reactions on the reply
                reply_reactions: list[DiscoveredReaction] = []
                r_reaction_lst = r_el.find(f"{{{ns}}}reactionLst")
                if r_reaction_lst is None and ns != MODERN_POWERPOINT_NS:
                    r_reaction_lst = r_el.find(f"{{{MODERN_POWERPOINT_NS}}}reactionLst")
                if r_reaction_lst is not None:
                    reaction_elements = r_reaction_lst.findall(f"{{{ns}}}reaction")
                    if not reaction_elements and ns != MODERN_POWERPOINT_NS:
                        reaction_elements = r_reaction_lst.findall(
                            f"{{{MODERN_POWERPOINT_NS}}}reaction"
                        )
                    for rxn_el in reaction_elements:
                        rxn_id = rxn_el.get("id", "")
                        rxn_author_id = rxn_el.get("authorId", "")
                        rxn_auth = authors.get(rxn_author_id)
                        rxn_type = rxn_el.get("type", "")
                        rxn_date = rxn_el.get("created", "")
                        reply_reactions.append(
                            DiscoveredReaction(
                                reaction_id=rxn_id,
                                author_id=rxn_author_id,
                                author="" if rxn_auth is None else rxn_auth.name,
                                initials="" if rxn_auth is None else rxn_auth.initials,
                                reaction_type=rxn_type,
                                date=rxn_date,
                                content_sha256=element_content_sha256(rxn_el),
                            )
                        )

                replies.append(
                    DiscoveredReply(
                        reply_id=r_id,
                        author_id=r_auth_id,
                        author="" if r_auth is None else r_auth.name,
                        initials="" if r_auth is None else r_auth.initials,
                        date=r_el.get("created", ""),
                        text="\n".join(r_text_parts),
                        status=r_el.get("status", "active"),
                        content_sha256=element_content_sha256(r_el),
                        reactions=tuple(reply_reactions),
                    )
                )

        # Parse reactions on the comment itself
        comment_reactions: list[DiscoveredReaction] = []
        cm_reaction_lst = element.find(f"{{{ns}}}reactionLst")
        if cm_reaction_lst is None and ns != MODERN_POWERPOINT_NS:
            cm_reaction_lst = element.find(f"{{{MODERN_POWERPOINT_NS}}}reactionLst")
        if cm_reaction_lst is not None:
            reaction_elements = cm_reaction_lst.findall(f"{{{ns}}}reaction")
            if not reaction_elements and ns != MODERN_POWERPOINT_NS:
                reaction_elements = cm_reaction_lst.findall(f"{{{MODERN_POWERPOINT_NS}}}reaction")
            for rxn_el in reaction_elements:
                rxn_id = rxn_el.get("id", "")
                rxn_author_id = rxn_el.get("authorId", "")
                rxn_auth = authors.get(rxn_author_id)
                rxn_type = rxn_el.get("type", "")
                rxn_date = rxn_el.get("created", "")
                comment_reactions.append(
                    DiscoveredReaction(
                        reaction_id=rxn_id,
                        author_id=rxn_author_id,
                        author="" if rxn_auth is None else rxn_auth.name,
                        initials="" if rxn_auth is None else rxn_auth.initials,
                        reaction_type=rxn_type,
                        date=rxn_date,
                        content_sha256=element_content_sha256(rxn_el),
                    )
                )

        moniker = element.find(f"{{{COMMENT_COMMAND_NS}}}sldMkLst")
        anchor = None
        if moniker is not None:
            document = moniker.find(f"{{{COMMENT_COMMAND_NS}}}docMk")
            slide = moniker.find(f"{{{COMMENT_COMMAND_NS}}}sldMk")
            anchor = CommentAnchorMoniker(
                None if document is None else MappingProxyType(dict(document.attrib)),
                None if slide is None else MappingProxyType(dict(slide.attrib)),
            )
        extensions = []
        for child in element:
            if child.tag in {
                f"{{{modern_ns}}}extLst" for modern_ns in MODERN_POWERPOINT_NAMESPACES
            }:
                for extension in child:
                    start, end, namespaces = spans[id(extension)]
                    extensions.append(
                        OpaqueCommentExtension(
                            MappingProxyType(dict(extension.attrib)),
                            parts[part][start:end],
                            namespaces,
                        )
                    )

        comments.append(
            DiscoveredComment(
                comment_id=comment_id,
                ordinal=ordinal,
                author_id=author_id,
                author=author_name,
                initials=author_initials,
                date=element.get("created", ""),
                text=text,
                position=pos,
                content_sha256=element_content_sha256(element),
                kind="modern",
                replies=tuple(replies),
                status=element.get("status", "active"),
                reactions=tuple(comment_reactions),
                anchor_moniker=anchor,
                attributes=MappingProxyType(dict(element.attrib)),
                opaque_extensions=tuple(extensions),
            )
        )
    return tuple(comments)


def slide_comment_targets(
    parts: Mapping[str, bytes],
) -> tuple[SlideCommentTarget, ...]:
    """Read every slide's comment state under one package version."""
    legacy_authors = {author.author_id: author for author in legacy_comment_authors(parts)}
    modern_authors_map = {author.id: author for author in modern_comment_authors(parts)}
    targets: list[SlideCommentTarget] = []
    for slide_index, slide_id, slide_part in presentation_slide_parts(parts):
        relationship = slide_comment_relationship(parts, slide_part)
        if relationship is None:
            targets.append(
                SlideCommentTarget(slide_index, slide_id, slide_part, None, None, "", ())
            )
            continue
        if relationship.kind not in ("legacy", "modern") or relationship.part not in parts:
            targets.append(
                SlideCommentTarget(
                    slide_index,
                    slide_id,
                    slide_part,
                    relationship.part,
                    relationship.relationship_id,
                    relationship.kind,
                    (),
                )
            )
            continue
        if relationship.kind == "modern":
            comments = parse_modern_comment_elements(parts, relationship.part, modern_authors_map)
        else:
            comments = parse_comment_elements(parts, relationship.part, legacy_authors)
        targets.append(
            SlideCommentTarget(
                slide_index=slide_index,
                slide_id=slide_id,
                slide_part=slide_part,
                comments_part=relationship.part,
                relationship_id=relationship.relationship_id,
                relationship_kind=relationship.kind,
                comments=comments,
            )
        )
    return tuple(targets)


def modern_comment_markers(parts: Mapping[str, bytes]) -> tuple[str, ...]:
    """Return every package fact that marks modern/threaded comments.

    Four independent signals are checked, so detection never depends on one
    producer's naming: declared content types, part names, relationship types,
    and the markup namespace of the candidate parts.
    """
    markers: list[str] = []
    modern_types = {
        MODERN_COMMENTS_CONTENT_TYPE,
        MODERN_AUTHORS_CONTENT_TYPE,
        MODERN_PERSON_CONTENT_TYPE,
    }
    for part, content_type in content_type_overrides(parts).items():
        if content_type in modern_types:
            markers.append(f"content type of {part}: {content_type}")
    for name in parts:
        normalized = part_name(name)
        if normalized in _MODERN_PART_NAMES or (
            normalized.startswith(f"{COMMENTS_DIRECTORY}/")
            and posixpath.basename(normalized).startswith("modernComment")
        ):
            markers.append(f"part {normalized}")
    modern_relationships = {
        MODERN_COMMENT_REL,
        MODERN_AUTHORS_REL,
        MODERN_PERSON_REL,
    }
    for name in parts:
        if not posixpath.basename(name).endswith(".rels"):
            continue
        for relationship in relationship_elements(parts[name], part_name(name)):
            relationship_type = relationship.get("Type", "")
            if relationship_type in modern_relationships:
                markers.append(f"relationship {relationship_type} in {part_name(name)}")
    candidates = comment_part_names(parts) + tuple(
        part_name(name) for name in parts if part_name(name) in _MODERN_PART_NAMES
    )
    for part in candidates:
        try:
            root = ET.fromstring(parts[part])
        except ET.ParseError:
            continue
        if any(
            root.tag.startswith(f"{{{target_ns}}}") for target_ns in MODERN_POWERPOINT_NAMESPACES
        ):
            markers.append(f"markup namespace of {part}")
    return tuple(dict.fromkeys(markers))


def next_modern_comments_part_name(taken: Iterable[str], slide_index: int | None = None) -> str:
    """Return a free ppt/comments/modernComment_N.xml part name."""
    reserved = {part_name(name) for name in taken}
    if slide_index is not None:
        candidate = f"{COMMENTS_DIRECTORY}/modernComment_{slide_index + 1}.xml"
        if candidate not in reserved:
            return candidate
    index = 1
    while (
        f"{COMMENTS_DIRECTORY}/modernComment_{index}.xml" in reserved
        or f"{COMMENTS_DIRECTORY}/modernComment{index}.xml" in reserved
    ):
        index += 1
    return f"{COMMENTS_DIRECTORY}/modernComment_{index}.xml"


def modern_comment_part_names(parts: Mapping[str, bytes]) -> tuple[str, ...]:
    """Return every modern comments part the package declares or reaches."""
    names = {
        part
        for part, content_type in content_type_overrides(parts).items()
        if content_type == MODERN_COMMENTS_CONTENT_TYPE and part in parts
    }
    for _index, _slide_id, slide_part in presentation_slide_parts(parts):
        relationship = slide_comment_relationship(parts, slide_part)
        if (
            relationship is not None
            and relationship.kind == "modern"
            and relationship.part in parts
        ):
            names.add(relationship.part)
    return tuple(sorted(names))


def next_comments_part_name(taken: Iterable[str]) -> str:
    """Return a free ``ppt/comments/commentN.xml`` part name."""
    reserved = {part_name(name) for name in taken}
    index = 1
    while f"{COMMENTS_DIRECTORY}/comment{index}.xml" in reserved:
        index += 1
    return f"{COMMENTS_DIRECTORY}/comment{index}.xml"


def next_relationship_id(existing: Iterable[str]) -> str:
    """Return a relationship ID no relationship of one part already uses."""
    used = {str(value) for value in existing}
    index = 1
    while f"rId{index}" in used:
        index += 1
    return f"rId{index}"


def relative_part_target(owner_part: str, target_part: str) -> str:
    """Return the relationship target that reaches one part from another."""
    return posixpath.relpath(part_name(target_part), posixpath.dirname(part_name(owner_part)))


def discover_comment_targets(
    source: str | Path,
    *,
    slides: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Report the comment state of a package under its current source digest.

    The receipt is read-only: it names the source digest a caller must state
    back when it authors a comment, the presentation-scoped author directory,
    and every slide's comment part, relationship, and comments with their own
    content digests.
    """
    path = Path(source).expanduser()
    if not path.is_file():
        raise CommentRefusal(f"deck {path} does not exist")
    parts = read_package(path)
    markers = modern_comment_markers(parts)
    targets = slide_comment_targets(parts)
    if slides is not None:
        wanted = set()
        for index in slides:
            if not isinstance(index, int) or index < 0 or index >= len(targets):
                raise CommentRefusal(
                    f"slide index {index} is outside the presentation's {len(targets)} slides"
                )
            wanted.add(index)
        targets = tuple(target for target in targets if target.slide_index in wanted)
    return {
        "operation": "comment-targets",
        "source": str(path),
        "source_sha256": sha256_file(path),
        "slide_count": len(presentation_slide_parts(parts)),
        "selected_slide_count": len(targets),
        "authors": [author.as_dict() for author in legacy_comment_authors(parts)],
        "modern_authors": [author.as_dict() for author in modern_comment_authors(parts)],
        "slides": [target.as_dict() for target in targets],
        "comment_parts": list(comment_part_names(parts)),
        "modern_comment_parts": list(modern_comment_part_names(parts)),
        "modern_comments": {
            "present": bool(markers),
            "markers": list(markers),
            "mutable": True,
        },
        "operations": list(OPERATIONS),
        "identity": {
            "author": "ppt/commentAuthors.xml p:cmAuthor/@id",
            "modern_author": "ppt/authors.xml p188:author/@id",
            "comment": "p:cm/@idx within one slide's own comments part",
            "modern_comment": "p188:cm/@id within one slide's modern comments part",
            "content": "sha256 of the p:cm element subtree",
        },
    }


__all__ = [
    "AUTHORS_PART",
    "A_NS",
    "COMMENTS_DIRECTORY",
    "COMMENT_AUTHORS_PART",
    "COMMENT_DATE",
    "DISCOVERY_NOTES",
    "LEGACY_COMMENTS_CONTENT_TYPE",
    "LEGACY_COMMENTS_REL",
    "LEGACY_COMMENT_AUTHORS_CONTENT_TYPE",
    "LEGACY_COMMENT_AUTHORS_REL",
    "MODERN_AUTHORS_CONTENT_TYPE",
    "MODERN_AUTHORS_REL",
    "MODERN_COMMENTS_CONTENT_TYPE",
    "MODERN_COMMENT_REL",
    "MODERN_PERSON_CONTENT_TYPE",
    "MODERN_PERSON_REL",
    "MODERN_POWERPOINT_NAMESPACES",
    "MODERN_POWERPOINT_NS",
    "MODERN_POWERPOINT_NS_ALT",
    "OPERATIONS",
    "SHA256_DIGEST",
    "CommentAnchorMoniker",
    "CommentAuthor",
    "CommentRefusal",
    "CommentRelationship",
    "DiscoveredComment",
    "DiscoveredReply",
    "DiscoveredReaction",
    "ModernCommentAuthor",
    "OpaqueCommentExtension",
    "SlideCommentTarget",
    "comment_elements",
    "comment_part_names",
    "comment_position",
    "comment_relationship_kind",
    "comment_timestamp",
    "content_type_overrides",
    "derived_initials",
    "discover_comment_targets",
    "element_content_sha256",
    "highest_comment_index",
    "int_attribute",
    "legacy_comment_authors",
    "modern_comment_authors",
    "modern_comment_markers",
    "modern_comment_part_names",
    "next_comments_part_name",
    "next_modern_comments_part_name",
    "next_relationship_id",
    "parse_comment_elements",
    "parse_modern_comment_elements",
    "part_name",
    "presentation_partname",
    "presentation_slide_parts",
    "read_package",
    "relationship_elements",
    "relationships_xml",
    "relative_part_target",
    "sha256_file",
    "slide_comment_relationship",
    "slide_comment_targets",
]
