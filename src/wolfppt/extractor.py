"""PPTX semantic and plain-text extraction.

This module intentionally uses only the Python standard library. The harness
needs to inspect fixtures and candidate outputs before any third-party PPTX
library is installed.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .comments_facade import (
    MODERN_POWERPOINT_NAMESPACES,
    CommentRefusal,
    SlideCommentTarget,
    presentation_partname,
    presentation_slide_parts,
    read_package,
    relationship_elements,
    slide_comment_targets,
)
from .package_parts import rels_part_for_package_part, resolve_package_target
from .xml_helpers import (
    STRICT_A_NS,
    STRICT_P_NS,
    STRICT_R_NS,
    ooxml_namespaces,
)

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
MC_SUPPORTED_NAMESPACE_URIS = frozenset({P_NS, A_NS, R_NS, C_NS})

NS = {
    "p": P_NS,
    "a": A_NS,
    "r": R_NS,
    "rel": REL_NS,
}


class SemanticExtractionRefusal(ValueError):
    """Raised when semantic extraction reaches unsupported required markup."""


class TextExtractionRefusal(SemanticExtractionRefusal):
    """Raised when requested plain text cannot be extracted without omission."""


@dataclass(frozen=True)
class Relationship:
    source: str
    id: str
    type: str
    target: str
    target_mode: str | None = None


@dataclass(frozen=True)
class Table:
    rows: list[list[str]]
    row_count: int
    col_count: int


@dataclass(frozen=True)
class Transform:
    x: int
    y: int
    cx: int
    cy: int


@dataclass(frozen=True)
class _CoordinateFrame:
    x: int
    y: int
    cx: int
    cy: int
    ch_x: int
    ch_y: int
    ch_cx: int
    ch_cy: int


@dataclass(frozen=True)
class Shape:
    id: str | None
    name: str | None
    kind: str
    text: str
    paragraphs: list[str] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    relationship_ids: list[str] = field(default_factory=list)
    has_chart: bool = False
    has_picture: bool = False
    has_group: bool = False
    transform: Transform | None = None
    effective_transform: Transform | None = None
    children: list[Shape] = field(default_factory=list)


@dataclass(frozen=True)
class Slide:
    part: str
    shape_count: int
    texts: list[str]
    shapes: list[Shape]
    notes: list[str] = field(default_factory=list)
    has_transition: bool = False
    has_timing: bool = False


@dataclass(frozen=True)
class PresentationSemantics:
    format: str
    path: str
    part_count: int
    parts: list[str]
    has_vba: bool
    relationships: list[Relationship]
    slides: list[Slide]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def extract_semantics(path: str | Path) -> PresentationSemantics:
    """Extract a stable semantic summary from a PPTX/PPTM package."""

    deck_path = Path(path)
    with zipfile.ZipFile(deck_path) as zf:
        parts = sorted(zf.namelist())
        relationships = _extract_relationships(zf, parts)
        slide_parts = _ordered_slide_parts(zf, parts)
        notes_by_slide = _notes_by_slide(zf, relationships)
        slides = [
            _extract_slide(zf, slide_part, notes_by_slide.get(slide_part, []))
            for slide_part in slide_parts
        ]

    return PresentationSemantics(
        format="wolfppt.semantic.v1",
        path=str(deck_path),
        part_count=len(parts),
        parts=parts,
        has_vba=any(part.endswith("vbaProject.bin") for part in parts),
        relationships=relationships,
        slides=slides,
    )


def extract_text(
    path: str | Path, *, include_notes: bool = False, include_comments: bool = False
) -> str:
    """Read slide text from a saved PPTX/PPTM package, without writing anything.

    Slides follow presentation order. Within a slide, text bodies follow XML
    shape order, descending into groups once and visiting table cells row-major.
    Bodies and paragraphs are separated by ``\\n``; explicit line breaks remain
    ``\\v``. Empty bodies are omitted, but blank paragraphs inside a nonempty
    body are preserved. No slide labels, author metadata or trailing separator
    are added.

    Requested notes follow the slide's shapes. Requested comments follow its
    notes, in comments-part order, with each modern comment immediately followed
    by its replies in reply-list order (including resolved/closed entries).
    Only slide-owned comments are included; orphan parts are not scanned.
    Transitional and Strict base namespaces are supported. Malformed consumed
    parts, unsupported required markup and ambiguous or unavailable requested
    notes/comments raise :class:`TextExtractionRefusal`. Unrequested notes and
    comments are not parsed. ``extract_semantics`` and its schema are unchanged.
    """
    if not isinstance(include_notes, bool) or not isinstance(include_comments, bool):
        raise TextExtractionRefusal("include_notes and include_comments must be bool")
    try:
        parts = read_package(path)
        presentation_part = presentation_partname(parts)
        presentation = _parse_text_xml(parts, presentation_part)
        if presentation.tag != f"{{{P_NS}}}presentation":
            raise TextExtractionRefusal("the presentation part has an unsupported root")
        slides = presentation_slide_parts(parts)
        if len(slides) != len(presentation.findall("./p:sldIdLst/p:sldId", NS)):
            raise TextExtractionRefusal(
                "the presentation has an unresolved or external slide relationship"
            )
        targets = (
            {target.slide_part: target for target in slide_comment_targets(parts)}
            if include_comments
            else {}
        )
        blocks: list[str] = []
        for _index, _slide_id, slide_part in slides:
            root = _parse_text_xml(parts, slide_part)
            if root.tag != f"{{{P_NS}}}sld":
                raise TextExtractionRefusal(f"{slide_part} has an unsupported slide root")
            tree = root.find("./p:cSld/p:spTree", NS)
            if tree is None:
                raise TextExtractionRefusal(f"{slide_part} has no slide shape tree")
            blocks.extend(_text_body_blocks(tree))
            if include_notes:
                blocks.extend(_slide_notes_text(parts, slide_part))
            if include_comments:
                blocks.extend(_slide_comments_text(parts, targets[slide_part]))
        return "\n".join(blocks)
    except TextExtractionRefusal:
        raise
    except (
        CommentRefusal,
        SemanticExtractionRefusal,
        ET.ParseError,
        KeyError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
    ) as exc:
        raise TextExtractionRefusal(f"cannot extract text: {exc}") from exc


def _parse_text_xml(parts: dict[str, bytes], part: str, *, modern: bool = False) -> ET.Element:
    """Select consumed MC markup and normalize only this private read tree."""
    if part not in parts:
        raise TextExtractionRefusal(f"requested part {part!r} is missing")
    root, scopes = _parse_with_namespace_scopes(parts[part])
    strict_to_transitional = {
        STRICT_P_NS: P_NS,
        STRICT_A_NS: A_NS,
        STRICT_R_NS: R_NS,
    }
    supported = MC_SUPPORTED_NAMESPACE_URIS | frozenset(strict_to_transitional)
    if modern:
        supported |= MODERN_POWERPOINT_NAMESPACES
    _select_effective_mc_children(root, scopes, part, supported_namespaces=supported)
    # Existing paragraph/shape selectors remain unchanged for semantic snapshots.
    # Namespace adaptation affects neither package bytes nor discovery identity.
    for element in root.iter():
        namespace = _namespace_uri(element.tag)
        if namespace in strict_to_transitional:
            element.tag = f"{{{strict_to_transitional[namespace]}}}{_local_name(element.tag)}"
    return root


def _text_body_blocks(root: ET.Element) -> list[str]:
    """Visit each text body once, including grouped shapes and table cells."""
    blocks: list[str] = []
    for body in root.iter():
        if body.tag not in {f"{{{P_NS}}}txBody", f"{{{A_NS}}}txBody"}:
            continue
        paragraphs = _extract_texts(body)
        if any(paragraphs):
            blocks.append("\n".join(paragraphs))
    return blocks


def _slide_notes_text(parts: dict[str, bytes], slide_part: str) -> list[str]:
    rels_part = rels_part_for_package_part(slide_part)
    if rels_part not in parts:
        return []
    relationships = [
        rel
        for rel in relationship_elements(parts[rels_part], slide_part)
        if rel.get("Type", "") in {f"{R_NS}/notesSlide", f"{STRICT_R_NS}/notesSlide"}
    ]
    if not relationships:
        return []
    if len(relationships) != 1:
        raise TextExtractionRefusal(f"{slide_part} declares multiple notes relationships")
    rel = relationships[0]
    target = rel.get("Target", "")
    if not target or rel.get("TargetMode") == "External":
        raise TextExtractionRefusal(f"{slide_part} has an unsupported notes target")
    notes_part = resolve_package_target(slide_part, target)
    root = _parse_text_xml(parts, notes_part)
    if root.tag != f"{{{P_NS}}}notes":
        raise TextExtractionRefusal(f"{notes_part} has an unsupported notes root")
    tree = root.find("./p:cSld/p:spTree", NS)
    if tree is None:
        raise TextExtractionRefusal(f"{notes_part} has no notes shape tree")
    return _text_body_blocks(tree)


def _slide_comments_text(parts: dict[str, bytes], target: SlideCommentTarget) -> list[str]:
    if not target.relationship_kind:
        return []
    if target.relationship_kind not in {"legacy", "modern"}:
        raise TextExtractionRefusal(f"{target.slide_part} has an unsupported comments relationship")
    if target.comments_part is None:
        raise TextExtractionRefusal(f"{target.slide_part} has no comments target")
    modern = target.relationship_kind == "modern"
    root = _parse_text_xml(parts, target.comments_part, modern=modern)
    namespace = _namespace_uri(root.tag)
    if (
        (modern and namespace not in MODERN_POWERPOINT_NAMESPACES)
        or (not modern and namespace != P_NS)
        or _local_name(root.tag) != "cmLst"
    ):
        raise TextExtractionRefusal(f"{target.comments_part} has an unsupported comments root")
    elements = root.findall(f"{{{namespace}}}cm")
    if len(elements) != len(target.comments):
        raise TextExtractionRefusal(
            f"{target.comments_part} has comment markup not represented by discovery"
        )
    blocks: list[str] = []
    for comment, element in zip(target.comments, elements, strict=True):
        actual_id = (
            element.get("id", f"cm{comment.ordinal + 1}") if modern else element.get("idx", "")
        )
        if str(comment.comment_id) != actual_id:
            raise TextExtractionRefusal(
                f"{target.comments_part} has comment order not represented by discovery"
            )
        if not modern:
            text = element.find(f"{{{P_NS}}}text")
            if text is None or len(text):
                raise TextExtractionRefusal(
                    f"{target.comments_part} has unsupported legacy comment text"
                )
            if text.text:
                blocks.append(text.text)
            continue
        # Discovery owns slide association, identity and reply order. Read the
        # same bodies as paragraphs so run boundaries do not become line breaks
        # and Strict DrawingML text and explicit breaks are not silently lost.
        body = element.find(f"{{{namespace}}}txBody")
        if body is None:
            raise TextExtractionRefusal(f"{target.comments_part} has a comment without text body")
        paragraphs = _extract_texts(body)
        if any(paragraphs):
            blocks.append("\n".join(paragraphs))
        replies = element.findall(f"./{{{namespace}}}replyLst/{{{namespace}}}reply")
        if len(replies) != len(comment.replies):
            raise TextExtractionRefusal(
                f"{target.comments_part} has reply markup not represented by discovery"
            )
        for ordinal, (discovered, reply) in enumerate(zip(comment.replies, replies, strict=True)):
            if reply.get("id", f"reply{ordinal + 1}") != discovered.reply_id:
                raise TextExtractionRefusal(
                    f"{target.comments_part} has reply order not represented by discovery"
                )
            body = reply.find(f"{{{namespace}}}txBody")
            if body is None:
                raise TextExtractionRefusal(f"{target.comments_part} has a reply without text body")
            paragraphs = _extract_texts(body)
            if any(paragraphs):
                blocks.append("\n".join(paragraphs))
    return blocks


def _extract_relationships(zf: zipfile.ZipFile, parts: list[str]) -> list[Relationship]:
    rels: list[Relationship] = []
    for part in parts:
        if not part.endswith(".rels"):
            continue
        source = _rels_source(part)
        try:
            root = _parse_effective_xml(zf.read(part), part)
        except ET.ParseError:
            continue
        for rel in root.findall("rel:Relationship", NS):
            rels.append(
                Relationship(
                    source=source,
                    id=rel.attrib.get("Id", ""),
                    type=rel.attrib.get("Type", ""),
                    target=rel.attrib.get("Target", ""),
                    target_mode=rel.attrib.get("TargetMode"),
                )
            )
    return sorted(rels, key=lambda item: (item.source, _natural_key(item.id), item.target))


def _rels_source(rels_part: str) -> str:
    if rels_part == "_rels/.rels":
        return "/"
    prefix, name = rels_part.rsplit("/_rels/", 1)
    return f"{prefix}/{name.removesuffix('.rels')}"


def _ordered_slide_parts(zf: zipfile.ZipFile, parts: list[str]) -> list[str]:
    presentation_rels = {
        rel.id: rel
        for rel in _extract_relationships(zf, ["ppt/_rels/presentation.xml.rels"])
        if rel.type.endswith("/slide")
    }
    if "ppt/presentation.xml" in parts and presentation_rels:
        try:
            root = _parse_effective_xml(zf.read("ppt/presentation.xml"), "ppt/presentation.xml")
            ordered: list[str] = []
            for slide_id in root.findall(".//p:sldId", NS):
                rel_id = slide_id.attrib.get(f"{{{R_NS}}}id")
                rel = presentation_rels.get(rel_id or "")
                if rel:
                    ordered.append(_resolve_target("ppt/presentation.xml", rel.target))
            if ordered:
                return ordered
        except ET.ParseError:
            pass
    return sorted(
        [part for part in parts if re.fullmatch(r"ppt/slides/slide\d+\.xml", part)],
        key=_natural_key,
    )


def _notes_by_slide(zf: zipfile.ZipFile, relationships: list[Relationship]) -> dict[str, list[str]]:
    notes: dict[str, list[str]] = {}
    for rel in relationships:
        if rel.source.startswith("ppt/slides/slide") and rel.type.endswith("/notesSlide"):
            notes_part = _resolve_target(rel.source, rel.target)
            try:
                notes[rel.source] = _extract_texts(
                    _parse_effective_xml(zf.read(notes_part), notes_part)
                )
            except (KeyError, ET.ParseError):
                notes[rel.source] = []
    return notes


def _extract_slide(zf: zipfile.ZipFile, part: str, notes: list[str]) -> Slide:
    try:
        root = _parse_effective_xml(zf.read(part), part)
    except ET.ParseError:
        return Slide(part=part, shape_count=0, texts=[], shapes=[], notes=notes)

    shapes = [_extract_shape(el) for el in _shape_elements(root)]
    texts = [shape.text for shape in shapes if shape.text]
    return Slide(
        part=part,
        shape_count=len(shapes),
        texts=texts,
        shapes=shapes,
        notes=notes,
        has_transition=root.find(".//p:transition", NS) is not None,
        has_timing=root.find(".//p:timing", NS) is not None,
    )


def _parse_effective_xml(xml: bytes, part: str = "<XML>") -> ET.Element:
    """Parse XML and select supported MC branches in consumed markup."""
    root, namespace_scopes = _parse_with_namespace_scopes(xml)
    _select_effective_mc_children(root, namespace_scopes, part)
    return root


def _parse_with_namespace_scopes(
    xml: bytes,
) -> tuple[ET.Element, dict[int, dict[str, str]]]:
    """Parse XML, mapping each element's ``id`` to its in-scope prefix bindings."""
    namespace_scopes: dict[int, dict[str, str]] = {}
    scope_stack: list[dict[str, str]] = [{}]
    pending_bindings: list[tuple[str, str]] = []
    root: ET.Element | None = None

    for event, value in ET.iterparse(
        io.BytesIO(xml),
        events=("start", "end", "start-ns"),
    ):
        if event == "start-ns":
            pending_bindings.append(value)
            continue
        if event == "start":
            scope = scope_stack[-1].copy()
            scope.update(pending_bindings)
            pending_bindings.clear()
            namespace_scopes[id(value)] = scope
            scope_stack.append(scope)
            if root is None:
                root = value
            continue
        scope_stack.pop()

    if root is None:
        raise ET.ParseError("XML document has no root element")
    return root, namespace_scopes


def _select_effective_mc_children(
    parent: ET.Element,
    namespace_scopes: dict[int, dict[str, str]],
    part: str,
    ignored_namespaces: frozenset[str] = frozenset(),
    process_content_qnames: frozenset[str] = frozenset(),
    *,
    validate_current: bool = True,
    supported_namespaces: frozenset[str] = MC_SUPPORTED_NAMESPACE_URIS,
) -> None:
    if validate_current:
        _refuse_unsupported_must_understand(parent, namespace_scopes, part, supported_namespaces)
    active_ignored = _active_ignorable_namespaces(
        parent, namespace_scopes, ignored_namespaces, supported_namespaces
    )
    active_process_content = process_content_qnames | _process_content_qnames(
        parent, namespace_scopes
    )
    effective_children: list[ET.Element] = []
    for child in list(parent):
        if child.tag == f"{{{MC_NS}}}AlternateContent":
            effective_children.extend(
                _effective_mc_children(
                    child,
                    namespace_scopes,
                    part,
                    active_ignored,
                    active_process_content,
                    supported_namespaces,
                )
            )
            continue
        if _namespace_uri(child.tag) in active_ignored:
            if child.tag in active_process_content:
                effective_children.extend(
                    _process_ignored_content(
                        child,
                        namespace_scopes,
                        part,
                        active_ignored,
                        active_process_content,
                        supported_namespaces,
                    )
                )
            continue
        _select_effective_mc_children(
            child,
            namespace_scopes,
            part,
            active_ignored,
            active_process_content,
            supported_namespaces=supported_namespaces,
        )
        effective_children.append(child)
    parent[:] = effective_children


def _effective_mc_children(
    alternate: ET.Element,
    namespace_scopes: dict[int, dict[str, str]],
    part: str,
    ignored_namespaces: frozenset[str],
    process_content_qnames: frozenset[str],
    supported_namespaces: frozenset[str],
) -> list[ET.Element]:
    _refuse_unsupported_must_understand(alternate, namespace_scopes, part, supported_namespaces)
    wrapper_ignored = _active_ignorable_namespaces(
        alternate, namespace_scopes, ignored_namespaces, supported_namespaces
    )
    wrapper_process_content = process_content_qnames | _process_content_qnames(
        alternate, namespace_scopes
    )
    selected_branch = _selected_mc_branch(alternate, namespace_scopes, supported_namespaces)
    if selected_branch is None:
        return []

    _refuse_unsupported_must_understand(
        selected_branch, namespace_scopes, part, supported_namespaces
    )
    active_ignored = _active_ignorable_namespaces(
        selected_branch, namespace_scopes, wrapper_ignored, supported_namespaces
    )
    active_process_content = wrapper_process_content | _process_content_qnames(
        selected_branch, namespace_scopes
    )
    effective_children: list[ET.Element] = []
    for child in list(selected_branch):
        if child.tag == f"{{{MC_NS}}}AlternateContent":
            effective_children.extend(
                _effective_mc_children(
                    child,
                    namespace_scopes,
                    part,
                    active_ignored,
                    active_process_content,
                    supported_namespaces,
                )
            )
            continue
        if _namespace_uri(child.tag) in active_ignored:
            if child.tag in active_process_content:
                effective_children.extend(
                    _process_ignored_content(
                        child,
                        namespace_scopes,
                        part,
                        active_ignored,
                        active_process_content,
                        supported_namespaces,
                    )
                )
            continue
        _select_effective_mc_children(
            child,
            namespace_scopes,
            part,
            active_ignored,
            active_process_content,
            supported_namespaces=supported_namespaces,
        )
        effective_children.append(child)
    return effective_children


def _process_ignored_content(
    element: ET.Element,
    namespace_scopes: dict[int, dict[str, str]],
    part: str,
    ignored_namespaces: frozenset[str],
    process_content_qnames: frozenset[str],
    supported_namespaces: frozenset[str],
) -> list[ET.Element]:
    _select_effective_mc_children(
        element,
        namespace_scopes,
        part,
        ignored_namespaces,
        process_content_qnames,
        validate_current=False,
        supported_namespaces=supported_namespaces,
    )
    return list(element)


def _selected_mc_branch(
    alternate: ET.Element,
    namespace_scopes: dict[int, dict[str, str]],
    supported_namespaces: frozenset[str],
) -> ET.Element | None:
    for choice in alternate.findall(f"{{{MC_NS}}}Choice"):
        requires = choice.get("Requires")
        if requires is not None and all(
            namespace_scopes.get(id(choice), {}).get(prefix) in supported_namespaces
            for prefix in requires.split()
        ):
            return choice
    return alternate.find(f"{{{MC_NS}}}Fallback")


def _namespace_uri(tag: str) -> str | None:
    if not tag.startswith("{"):
        return None
    return tag[1:].partition("}")[0]


def _active_ignorable_namespaces(
    element: ET.Element,
    namespace_scopes: dict[int, dict[str, str]],
    inherited: frozenset[str],
    supported_namespaces: frozenset[str],
) -> frozenset[str]:
    prefixes = element.get(f"{{{MC_NS}}}Ignorable")
    if not prefixes:
        return inherited
    scope = namespace_scopes.get(id(element), {})
    return inherited | frozenset(
        uri
        for prefix in prefixes.split()
        if (uri := scope.get(prefix)) is not None and uri not in supported_namespaces
    )


def _process_content_qnames(
    element: ET.Element, namespace_scopes: dict[int, dict[str, str]]
) -> frozenset[str]:
    names = element.get(f"{{{MC_NS}}}ProcessContent")
    if not names:
        return frozenset()
    scope = namespace_scopes.get(id(element), {})
    qualified: set[str] = set()
    for name in names.split():
        prefix, separator, local_name = name.partition(":")
        if not separator or not local_name:
            continue
        uri = scope.get(prefix)
        if uri is not None:
            qualified.add(f"{{{uri}}}{local_name}")
    return frozenset(qualified)


def _refuse_unsupported_must_understand(
    element: ET.Element,
    namespace_scopes: dict[int, dict[str, str]],
    part: str,
    supported_namespaces: frozenset[str],
) -> None:
    required = element.get(f"{{{MC_NS}}}MustUnderstand")
    if not required:
        return
    scope = namespace_scopes.get(id(element), {})
    for prefix in required.split():
        uri = scope.get(prefix)
        if uri is None:
            raise SemanticExtractionRefusal(
                f"part {part!r} has mc:MustUnderstand prefix {prefix!r} "
                "without a lexical namespace binding"
            )
        if uri not in supported_namespaces:
            raise SemanticExtractionRefusal(
                f"part {part!r} has mc:MustUnderstand prefix {prefix!r} "
                f"for unsupported namespace {uri!r}"
            )


def _shape_elements(root: ET.Element) -> list[ET.Element]:
    elements: list[ET.Element] = []
    for child in root.findall(".//p:cSld/p:spTree/*", NS):
        tag = _local_name(child.tag)
        if tag in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}:
            elements.append(child)
    return elements


def _extract_shape(el: ET.Element, parent_frame: _CoordinateFrame | None = None) -> Shape:
    nv = el.find(".//p:cNvPr", NS)
    shape_id = nv.attrib.get("id") if nv is not None else None
    name = nv.attrib.get("name") if nv is not None else None
    paragraphs = _extract_texts(el)
    tables = [_extract_table(tbl) for tbl in el.findall(".//a:tbl", NS)]
    rel_ids = sorted(
        {
            value
            for key, value in _walk_attribs(el)
            if key == f"{{{R_NS}}}embed" or key == f"{{{R_NS}}}link" or key == f"{{{R_NS}}}id"
        }
    )
    kind = {
        "sp": "shape",
        "pic": "picture",
        "graphicFrame": "graphic_frame",
        "grpSp": "group",
        "cxnSp": "connector",
    }.get(_local_name(el.tag), "unknown")
    if kind == "graphic_frame" and el.find(".//p:oleObj", NS) is not None:
        kind = "ole_object"
    local_transform = _extract_transform(el)
    effective_transform = _apply_parent_transform(local_transform, parent_frame)
    child_frame = _group_frame(el, parent_frame)
    children = [_extract_shape(child, child_frame) for child in _shape_child_elements(el)]
    return Shape(
        id=shape_id,
        name=name,
        kind=kind,
        text="\n".join(paragraphs),
        paragraphs=paragraphs,
        tables=tables,
        relationship_ids=rel_ids,
        has_chart=el.find(".//c:chart", {"c": C_NS}) is not None,
        has_picture=_local_name(el.tag) == "pic",
        has_group=_local_name(el.tag) == "grpSp",
        transform=local_transform,
        effective_transform=effective_transform,
        children=children,
    )


def _shape_child_elements(root: ET.Element) -> list[ET.Element]:
    elements: list[ET.Element] = []
    for child in root:
        tag = _local_name(child.tag)
        if tag in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}:
            elements.append(child)
    return elements


def _extract_transform(el: ET.Element) -> Transform | None:
    namespaces = ooxml_namespaces(el, NS)
    xfrm = el.find("./p:spPr/a:xfrm", namespaces)
    if xfrm is None:
        xfrm = el.find("./p:grpSpPr/a:xfrm", namespaces)
    if xfrm is None:
        xfrm = el.find("./p:xfrm", namespaces)
    if xfrm is None:
        return None
    off = xfrm.find("./a:off", namespaces)
    ext = xfrm.find("./a:ext", namespaces)
    if off is None or ext is None:
        return None
    return Transform(
        x=int(off.attrib.get("x", "0")),
        y=int(off.attrib.get("y", "0")),
        cx=int(ext.attrib.get("cx", "0")),
        cy=int(ext.attrib.get("cy", "0")),
    )


def _group_frame(el: ET.Element, parent_frame: _CoordinateFrame | None) -> _CoordinateFrame | None:
    xfrm = el.find("./p:grpSpPr/a:xfrm", NS)
    if xfrm is None:
        return None
    local = _extract_transform(el)
    effective = _apply_parent_transform(local, parent_frame)
    if effective is None:
        return None
    ch_off = xfrm.find("./a:chOff", NS)
    ch_ext = xfrm.find("./a:chExt", NS)
    return _CoordinateFrame(
        x=effective.x,
        y=effective.y,
        cx=effective.cx,
        cy=effective.cy,
        ch_x=int(ch_off.attrib.get("x", "0")) if ch_off is not None else 0,
        ch_y=int(ch_off.attrib.get("y", "0")) if ch_off is not None else 0,
        ch_cx=int(ch_ext.attrib.get("cx", str(effective.cx)))
        if ch_ext is not None
        else effective.cx,
        ch_cy=int(ch_ext.attrib.get("cy", str(effective.cy)))
        if ch_ext is not None
        else effective.cy,
    )


def _apply_parent_transform(
    transform: Transform | None,
    parent_frame: _CoordinateFrame | None,
) -> Transform | None:
    if transform is None:
        return None
    if parent_frame is None:
        return transform
    return Transform(
        x=parent_frame.x
        + _scale_child_coordinate(
            transform.x - parent_frame.ch_x,
            parent_frame.cx,
            parent_frame.ch_cx,
        ),
        y=parent_frame.y
        + _scale_child_coordinate(
            transform.y - parent_frame.ch_y,
            parent_frame.cy,
            parent_frame.ch_cy,
        ),
        cx=_scale_child_coordinate(transform.cx, parent_frame.cx, parent_frame.ch_cx),
        cy=_scale_child_coordinate(transform.cy, parent_frame.cy, parent_frame.ch_cy),
    )


def _scale_child_coordinate(value: int, parent_extent: int, child_extent: int) -> int:
    if child_extent == 0:
        return value
    return round(value * parent_extent / child_extent)


def _extract_texts(root: ET.Element) -> list[str]:
    return [_paragraph_text(paragraph) for paragraph in root.findall(".//a:p", NS)]


def _paragraph_text(paragraph: ET.Element) -> str:
    """Return one ``a:p`` paragraph's text, with ``a:br`` line breaks as ``\\v``."""
    parts: list[str] = []
    for child in list(paragraph):
        if _local_name(child.tag) == "br":
            parts.append("\v")
        else:
            parts.append("".join(node.text or "" for node in child.findall(".//a:t", NS)))
    return "".join(parts)


def _extract_table(tbl: ET.Element) -> Table:
    rows: list[list[str]] = []
    for row in tbl.findall("./a:tr", NS):
        cells: list[str] = []
        for cell in row.findall("./a:tc", NS):
            cells.append("\n".join(_extract_texts(cell)))
        rows.append(cells)
    return Table(
        rows=rows,
        row_count=len(rows),
        col_count=max((len(row) for row in rows), default=0),
    )


def _walk_attribs(root: ET.Element) -> list[tuple[str, str]]:
    attrs: list[tuple[str, str]] = []
    for el in root.iter():
        attrs.extend(el.attrib.items())
    return attrs


def _resolve_target(source: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base = Path(source).parent
    normalized = (base / target).as_posix()
    parts: list[str] = []
    for part in normalized.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part and part != ".":
            parts.append(part)
    return "/".join(parts)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _natural_key(value: str) -> list[int | str]:
    return [int(chunk) if chunk.isdigit() else chunk for chunk in re.split(r"(\d+)", value)]
