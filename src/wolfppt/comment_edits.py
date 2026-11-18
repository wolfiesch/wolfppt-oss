"""Queued legacy comment authoring for the PowerPoint presentation facade.

The facade exposes comments the way it exposes every other editable thing: a
discovered object reads from the source package, a setter queues work on the
presentation, and :meth:`Presentation.save` applies the queue through the same
staging pipeline as every other edit.

Two rules shape this module:

* **Presentation-scoped authors.**  ``ppt/commentAuthors.xml`` owns every author
  ID in the document, so an author is registered once and reused by identity.
  Only a genuinely new author name consumes the next free ID.
* **Source-bound slides.**  A comment belongs to one slide's own comments part.
  Work is therefore keyed by slide part name, exactly like layout removals and
  base-layer removals, so it survives slide deletion and duplication instead of
  addressing a mutable list index.

Legacy and modern threaded comments share this queue. Modern collaboration
authoring writes the schema-defined ``likes``, ``tags`` and ``assignedTo``
attributes; opaque extensions remain untouched. Every part a queued edit does
not change is copied as its original raw ZIP entry.
"""

from __future__ import annotations

import posixpath
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .comments_facade import (
    A_NS,
    AUTHORS_PART,
    COMMENT_AUTHORS_PART,
    COMMENT_DATE,
    CONTENT_TYPES_NS,
    LEGACY_COMMENT_AUTHORS_CONTENT_TYPE,
    LEGACY_COMMENT_AUTHORS_REL,
    LEGACY_COMMENTS_CONTENT_TYPE,
    LEGACY_COMMENTS_REL,
    MODERN_AUTHORS_CONTENT_TYPE,
    MODERN_AUTHORS_REL,
    MODERN_COMMENT_REL,
    MODERN_COMMENTS_CONTENT_TYPE,
    MODERN_POWERPOINT_NS,
    P_NS,
    PKG_REL_NS,
    CommentAuthor,
    CommentRefusal,
    ModernCommentAuthor,
    SlideCommentTarget,
    _preserve_modern_extensions,
    comment_elements,
    comment_part_names,
    derived_initials,
    element_content_sha256,
    highest_comment_index,
    int_attribute,
    legacy_comment_authors,
    modern_comment_authors,
    modern_comment_markers,
    next_comments_part_name,
    next_modern_comments_part_name,
    next_relationship_id,
    part_name,
    presentation_partname,
    presentation_slide_parts,
    read_package,
    relationship_elements,
    relationships_xml,
    relative_part_target,
    slide_comment_relationship,
    slide_comment_targets,
)
from .package_parts import copy_package_with_replacements, rels_part_for_package_part
from .xml_helpers import content_types_xml, findall_ooxml

_P15_NS = "http://schemas.microsoft.com/office/powerpoint/2012/main"
_PC_NS = "http://schemas.microsoft.com/office/powerpoint/2013/main/command"
_LEGACY_PARENT_TAG = f"{{{_P15_NS}}}parentCm"


def _legacy_threading_info(element: ET.Element) -> Iterator[ET.Element]:
    for extension in findall_ooxml(element, f"{{{P_NS}}}extLst/{{{P_NS}}}ext"):
        yield from extension.findall(f"{{{_P15_NS}}}threadingInfo")


def required_text(value: Any, label: str) -> str:
    """Return one required non-empty comment string."""
    if not isinstance(value, str) or not value:
        raise CommentRefusal(f"{label} must be a non-empty string")
    return value


def required_comment_date(value: Any, label: str = "comment date") -> str:
    """Return one validated ``p:cm/@dt`` timestamp."""
    if not isinstance(value, str) or COMMENT_DATE.match(value) is None:
        raise CommentRefusal(
            f"{label} must be an ISO-8601 UTC instant such as 2026-09-16T00:00:00Z"
        )
    return value


def required_comment_status(value: Any) -> str:
    """Validate ST_CommentStatus before changing queued or live state."""
    if not isinstance(value, str) or value not in ("active", "resolved", "closed"):
        raise CommentRefusal("comment status must be active, resolved or closed")
    return value


def required_comment_position(value: Any) -> tuple[int, int]:
    """Return one validated comment anchor in English Metric Units."""
    if value is None:
        return (0, 0)
    coordinates: tuple[Any, Any]
    if isinstance(value, (tuple, list)) and len(value) == 2:
        coordinates = (value[0], value[1])
    elif isinstance(value, Mapping) and "x" in value and "y" in value:
        coordinates = (value["x"], value["y"])
    else:
        raise CommentRefusal("comment position must be an (x, y) pair or an object with x and y")
    for coordinate in coordinates:
        if not isinstance(coordinate, int) or isinstance(coordinate, bool):
            raise CommentRefusal("comment position coordinates must be integers in EMU")
    return (int(coordinates[0]), int(coordinates[1]))


@dataclass
class CommentAdd:
    """One comment queued to be appended to a slide's comments part."""

    slide_part: str
    comment_id: int
    author_id: int
    date: str
    text: str
    x: int = 0
    y: int = 0


@dataclass
class CommentUpdate:
    """One queued edit of an existing comment, bound to its discovered digest."""

    slide_part: str
    comment_id: int
    expected_content_sha256: str
    text: str | None = None
    date: str | None = None
    position: tuple[int, int] | None = None


@dataclass(frozen=True)
class CommentDelete:
    """One queued removal of an existing comment, bound to its digest."""

    slide_part: str
    comment_id: int
    expected_content_sha256: str


@dataclass
class ModernCommentAdd:
    """One modern comment queued to be appended to a slide's modern comments part."""

    slide_part: str
    comment_id: str
    author_id: str
    date: str
    text: str
    x: int = 0
    y: int = 0
    status: str = "active"
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class ModernReplyAdd:
    """One threaded reply queued to be appended to a modern comment."""

    slide_part: str
    parent_comment_id: str
    reply_id: str
    author_id: str
    date: str
    text: str
    status: str = "active"


@dataclass
class ModernCommentUpdate:
    """One queued edit of an existing modern comment."""

    slide_part: str
    comment_id: str
    expected_content_sha256: str | None = None
    text: str | None = None
    date: str | None = None
    status: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class ModernReplyUpdate:
    """One queued edit of an existing modern reply."""

    slide_part: str
    parent_comment_id: str
    reply_id: str
    expected_content_sha256: str | None = None
    text: str | None = None
    date: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class ModernCommentDelete:
    """One queued removal of an existing modern comment."""

    slide_part: str
    comment_id: str
    expected_content_sha256: str | None = None


@dataclass(frozen=True)
class ModernReplyDelete:
    """One queued removal of an existing modern reply."""

    slide_part: str
    parent_comment_id: str
    reply_id: str
    expected_content_sha256: str | None = None


@dataclass
class _SlideModernCommentWork:
    """Every queued modern comment edit addressed to one slide part."""

    adds: list[ModernCommentAdd] = field(default_factory=list)
    reply_adds: list[ModernReplyAdd] = field(default_factory=list)
    updates: list[ModernCommentUpdate] = field(default_factory=list)
    reply_updates: list[ModernReplyUpdate] = field(default_factory=list)
    deletes: list[ModernCommentDelete] = field(default_factory=list)
    reply_deletes: list[ModernReplyDelete] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (
            self.adds
            or self.reply_adds
            or self.updates
            or self.reply_updates
            or self.deletes
            or self.reply_deletes
        )


@dataclass
class _SlideCommentWork:
    """Every queued edit addressed to one slide part."""

    adds: list[CommentAdd] = field(default_factory=list)
    updates: list[CommentUpdate] = field(default_factory=list)
    deletes: list[CommentDelete] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.adds or self.updates or self.deletes)


class CommentRegistry:
    """The presentation-scoped legacy comment author directory.

    An author belongs to the presentation rather than to a slide, so a name is
    resolved to the author that already carries it.  Renaming an existing name
    or restating its initials differently refuses, because two authors with one
    name would be indistinguishable to every consumer of the package.
    """

    def __init__(self, authors: Sequence[CommentAuthor]) -> None:
        self._authors: list[CommentAuthor] = list(authors)

    @property
    def authors(self) -> tuple[CommentAuthor, ...]:
        return tuple(self._authors)

    def resolve(self, name: str, initials: str | None = None) -> CommentAuthor:
        """Return the author for one name, registering a new one when needed."""
        label = required_text(name, "comment author")
        resolved_initials = (
            None if initials is None else required_text(initials, "comment author initials")
        )
        for author in self._authors:
            if author.name != label:
                continue
            if resolved_initials is not None and resolved_initials != author.initials:
                raise CommentRefusal(
                    f"author {label!r} is already registered with initials "
                    f"{author.initials!r}; one presentation-scoped author keeps "
                    "one name and one set of initials"
                )
            return author
        author = CommentAuthor(
            author_id=max((item.author_id for item in self._authors), default=-1) + 1,
            name=label,
            initials=resolved_initials or derived_initials(label),
            last_index=0,
            color_index=len(self._authors),
        )
        self._authors.append(author)
        return author

    def by_id(self, author_id: int) -> CommentAuthor | None:
        for author in self._authors:
            if author.author_id == author_id:
                return author
        return None


class ModernCommentRegistry:
    """The presentation-scoped modern comment author directory (ppt/authors.xml)."""

    def __init__(self, authors: Sequence[ModernCommentAuthor]) -> None:
        self._authors: list[ModernCommentAuthor] = list(authors)

    @property
    def authors(self) -> tuple[ModernCommentAuthor, ...]:
        return tuple(self._authors)

    def resolve(
        self,
        name: str,
        initials: str | None = None,
        user_id: str | None = None,
        provider_id: str = "AD",
    ) -> ModernCommentAuthor:
        label = required_text(name, "comment author")
        resolved_initials = (
            None if initials is None else required_text(initials, "comment author initials")
        )
        for author in self._authors:
            if author.name != label:
                continue
            if resolved_initials is not None and resolved_initials != author.initials:
                raise CommentRefusal(
                    f"author {label!r} is already registered with initials "
                    f"{author.initials!r}; one presentation-scoped author keeps "
                    "one name and one set of initials"
                )
            return author
        author_id = f"{{{str(uuid.uuid4()).upper()}}}"
        author = ModernCommentAuthor(
            id=author_id,
            name=label,
            initials=resolved_initials or derived_initials(label),
            user_id=user_id or f"{label.lower().replace(' ', '.')}@example.com",
            provider_id=provider_id or "AD",
        )
        self._authors.append(author)
        return author

    def by_id(self, author_id: str) -> ModernCommentAuthor | None:
        for author in self._authors:
            if author.id == author_id:
                return author
        return None


class PendingCommentEdits:
    """The comment work one presentation has queued for its next save."""

    def __init__(self, parts: Mapping[str, bytes]) -> None:
        self.parts: Mapping[str, bytes] = parts
        self.registry = CommentRegistry(legacy_comment_authors(parts))
        self.modern_registry = ModernCommentRegistry(modern_comment_authors(parts))
        self.markers = modern_comment_markers(parts)
        self.adds: list[CommentAdd] = []
        self.updates: list[CommentUpdate] = []
        self.deletes: list[CommentDelete] = []
        self.modern_adds: list[ModernCommentAdd] = []
        self.modern_reply_adds: list[ModernReplyAdd] = []
        self.modern_updates: list[ModernCommentUpdate] = []
        self.modern_reply_updates: list[ModernReplyUpdate] = []
        self.modern_deletes: list[ModernCommentDelete] = []
        self.modern_reply_deletes: list[ModernReplyDelete] = []
        self._next_comment_id = highest_comment_index(parts) + 1

    @property
    def is_modern(self) -> bool:
        return bool(
            AUTHORS_PART in self.parts
            or any(t.modern for t in slide_comment_targets(self.parts))
            or self.modern_adds
            or self.modern_reply_adds
            or self.modern_updates
            or self.modern_reply_updates
            or self.modern_deletes
            or self.modern_reply_deletes
        )

    def has_work(self) -> bool:
        return bool(
            self.adds
            or self.updates
            or self.deletes
            or self.modern_adds
            or self.modern_reply_adds
            or self.modern_updates
            or self.modern_reply_updates
            or self.modern_deletes
            or self.modern_reply_deletes
        )

    def refuse_modern(self) -> None:
        """Refuse legacy edits of threaded packages without modern authoring."""
        if self.markers and AUTHORS_PART not in self.parts:
            raise CommentRefusal(
                "the deck holds modern/threaded comments ("
                + ", ".join(self.markers)
                + "); legacy comment authoring is refused so those parts stay "
                "unchanged"
            )

    def consume_comment_id(self) -> int:
        """Return the next free comment ID, above every ID the package uses."""
        comment_id = self._next_comment_id
        self._next_comment_id += 1
        return comment_id

    def slide_target(self, slide_part: str) -> SlideCommentTarget:
        """Return one slide's comment state as the source package declares it."""
        normalized = part_name(slide_part)
        for target in slide_comment_targets(self.parts):
            if target.slide_part == normalized:
                return target
        raise CommentRefusal(f"{normalized} is not a slide of this presentation")

    def update_for(self, slide_part: str, comment_id: int) -> CommentUpdate | None:
        for record in self.updates:
            if record.slide_part == slide_part and record.comment_id == comment_id:
                return record
        return None

    def modern_update_for(self, slide_part: str, comment_id: str) -> ModernCommentUpdate | None:
        for record in self.modern_updates:
            if record.slide_part == slide_part and record.comment_id == comment_id:
                return record
        return None

    def modern_reply_update_for(
        self, slide_part: str, parent_id: str, reply_id: str
    ) -> ModernReplyUpdate | None:
        for record in self.modern_reply_updates:
            if (
                record.slide_part == slide_part
                and record.parent_comment_id == parent_id
                and record.reply_id == reply_id
            ):
                return record
        return None

    def drop_slide(self, slide_part: str) -> None:
        """Discard every queued edit addressed to one slide that no longer exists."""
        normalized = part_name(slide_part)
        self.adds[:] = [add for add in self.adds if add.slide_part != normalized]
        self.updates[:] = [record for record in self.updates if record.slide_part != normalized]
        self.deletes[:] = [record for record in self.deletes if record.slide_part != normalized]

    def drop_comment(self, slide_part: str, comment_id: int) -> None:
        """Discard the queued edit of one comment, if one is queued."""
        normalized = part_name(slide_part)
        self.updates[:] = [
            record
            for record in self.updates
            if not (record.slide_part == normalized and record.comment_id == comment_id)
        ]


class _CommentPackageWriter:
    """One package rewrite that applies queued legacy comment work.

    The writer owns a private view of the package so a refusal leaves the queue
    and the source untouched.  Only parts an edit genuinely changes are
    replaced; everything else is copied as its original raw ZIP entry.
    """

    def __init__(
        self,
        input_path: Path,
        edits: PendingCommentEdits,
        deleted_slide_parts: Iterable[str],
    ) -> None:
        self._input = Path(input_path)
        self._edits = edits
        self._parts: dict[str, bytes] = dict(edits.parts)
        self._deleted = {part_name(part) for part in deleted_slide_parts}
        self._replacements: dict[str, bytes] = {}
        self._removals: set[str] = set()
        self._added: set[str] = set()
        self._changed: list[str] = []

    def write(self, output_path: Path) -> dict[str, Any]:
        has_modern = bool(
            self._edits.modern_adds
            or self._edits.modern_reply_adds
            or self._edits.modern_updates
            or self._edits.modern_reply_updates
            or self._edits.modern_deletes
            or self._edits.modern_reply_deletes
        )
        has_legacy = bool(self._edits.adds or self._edits.updates or self._edits.deletes)
        if has_legacy:
            self._edits.refuse_modern()
            for slide_part, work in self._work().items():
                self._apply_slide(slide_part, work)
            self._write_authors()

        if has_modern:
            for slide_part, mwork in self._modern_work().items():
                self._apply_modern_slide(slide_part, mwork)
            self._write_modern_authors()

        if not self._replacements:
            raise CommentRefusal("no comment edit changed any package part")
        copy_package_with_replacements(
            self._input,
            Path(output_path),
            self._replacements,
            self._removals or None,
        )
        return {
            "changed_parts": sorted(self._changed),
            "added_parts": sorted(self._added),
            "removed_parts": sorted(self._removals),
        }

    def _modern_work(self) -> dict[str, _SlideModernCommentWork]:
        known = {
            slide_part for _index, _slide_id, slide_part in presentation_slide_parts(self._parts)
        }
        work: dict[str, _SlideModernCommentWork] = {}
        for add in self._edits.modern_adds:
            if self._targetable(add.slide_part, known):
                work.setdefault(part_name(add.slide_part), _SlideModernCommentWork()).adds.append(
                    add
                )
        for radd in self._edits.modern_reply_adds:
            if self._targetable(radd.slide_part, known):
                work.setdefault(
                    part_name(radd.slide_part), _SlideModernCommentWork()
                ).reply_adds.append(radd)
        for update in self._edits.modern_updates:
            if self._targetable(update.slide_part, known):
                work.setdefault(
                    part_name(update.slide_part), _SlideModernCommentWork()
                ).updates.append(update)
        for rupdate in self._edits.modern_reply_updates:
            if self._targetable(rupdate.slide_part, known):
                work.setdefault(
                    part_name(rupdate.slide_part), _SlideModernCommentWork()
                ).reply_updates.append(rupdate)
        for delete in self._edits.modern_deletes:
            if self._targetable(delete.slide_part, known):
                work.setdefault(
                    part_name(delete.slide_part), _SlideModernCommentWork()
                ).deletes.append(delete)
        for rdel in self._edits.modern_reply_deletes:
            if self._targetable(rdel.slide_part, known):
                work.setdefault(
                    part_name(rdel.slide_part), _SlideModernCommentWork()
                ).reply_deletes.append(rdel)
        return {part: item for part, item in work.items() if not item.empty}

    def _create_modern_comments_part(self, slide_part: str) -> str:
        all_parts = tuple(self._parts) + tuple(self._replacements)
        slide_idx = None
        for idx, _sid, spart in presentation_slide_parts(self._parts):
            if spart == slide_part:
                slide_idx = idx
                break
        comments_part = next_modern_comments_part_name(all_parts, slide_idx)
        self._register_content_type(comments_part, MODERN_COMMENTS_CONTENT_TYPE)
        self._add_comment_relationship(
            slide_part, comments_part, relationship_type=MODERN_COMMENT_REL
        )
        return comments_part

    def _remove_modern_comments_part(self, slide_part: str, comments_part: str) -> None:
        self._remove_part(comments_part)
        self._remove_content_type(comments_part)
        self._remove_comment_relationship(
            slide_part, comments_part, relationship_type=MODERN_COMMENT_REL
        )

    def _apply_modern_slide(self, slide_part: str, work: _SlideModernCommentWork) -> None:
        relationship = slide_comment_relationship(self._parts, slide_part)
        if relationship is not None and relationship.kind == "legacy":
            raise CommentRefusal(
                f"{slide_part} reaches legacy comments; cannot add modern comments"
            )
        comments_part = None if relationship is None else relationship.part
        payload = None
        if comments_part is None:
            if work.updates or work.deletes or work.reply_updates or work.reply_deletes:
                raise CommentRefusal(f"{slide_part} owns no modern comments part to edit")
            comments_part = self._create_modern_comments_part(slide_part)
            root = ET.Element(f"{{{MODERN_POWERPOINT_NS}}}cmLst")
            ns = MODERN_POWERPOINT_NS
        else:
            payload = self._parts.get(comments_part)
            if payload is None:
                raise CommentRefusal(
                    f"{comments_part} is declared by {slide_part} but is not in package"
                )
            try:
                root = ET.fromstring(payload)
            except ET.ParseError as exc:
                raise CommentRefusal(f"{comments_part} is malformed") from exc
            ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else MODERN_POWERPOINT_NS

        cm_by_id: dict[str, ET.Element] = {}
        for cm_el in root.findall(f"{{{ns}}}cm"):
            cid = cm_el.get("id", "")
            if cid:
                cm_by_id[cid] = cm_el
        if not cm_by_id and ns != MODERN_POWERPOINT_NS:
            for cm_el in root.findall(f"{{{MODERN_POWERPOINT_NS}}}cm"):
                cid = cm_el.get("id", "")
                if cid:
                    cm_by_id[cid] = cm_el

        # 1. Updates on comments
        for update in work.updates:
            cm_el = cm_by_id.get(update.comment_id)
            if cm_el is None:
                raise CommentRefusal(f"{comments_part} has no comment id {update.comment_id}")
            if update.expected_content_sha256:
                found = element_content_sha256(cm_el)
                if found != update.expected_content_sha256:
                    raise CommentRefusal(
                        f"comment {update.comment_id} changed since discovered "
                        f"({found} != {update.expected_content_sha256})"
                    )
            if update.text is not None:
                tx_body = cm_el.find(f"{{{ns}}}txBody") or cm_el.find(
                    f"{{{MODERN_POWERPOINT_NS}}}txBody"
                )
                if tx_body is None:
                    tx_body = ET.SubElement(cm_el, f"{{{ns}}}txBody")
                for child in list(tx_body):
                    tx_body.remove(child)
                ET.SubElement(tx_body, f"{{{A_NS}}}bodyPr")
                ET.SubElement(tx_body, f"{{{A_NS}}}lstStyle")
                for line in update.text.split("\n"):
                    p_el = ET.SubElement(tx_body, f"{{{A_NS}}}p")
                    r_el = ET.SubElement(p_el, f"{{{A_NS}}}r")
                    ET.SubElement(r_el, f"{{{A_NS}}}rPr")
                    t_el = ET.SubElement(r_el, f"{{{A_NS}}}t")
                    t_el.text = line
            if update.date is not None:
                cm_el.set("created", update.date)
            if update.status is not None:
                cm_el.set("status", update.status)
            cm_el.attrib.update(update.attributes)

        # 2. Reply updates
        for rupdate in work.reply_updates:
            cm_el = cm_by_id.get(rupdate.parent_comment_id)
            if cm_el is None:
                raise CommentRefusal(
                    f"{comments_part} has no parent comment id {rupdate.parent_comment_id}"
                )
            reply_lst = cm_el.find(f"{{{ns}}}replyLst") or cm_el.find(
                f"{{{MODERN_POWERPOINT_NS}}}replyLst"
            )
            if reply_lst is None:
                raise CommentRefusal(f"comment {rupdate.parent_comment_id} has no replies")
            rel = None
            for r in reply_lst.findall(f"{{{ns}}}reply"):
                if r.get("id") == rupdate.reply_id:
                    rel = r
                    break
            if rel is None and ns != MODERN_POWERPOINT_NS:
                for r in reply_lst.findall(f"{{{MODERN_POWERPOINT_NS}}}reply"):
                    if r.get("id") == rupdate.reply_id:
                        rel = r
                        break
            if rel is None:
                raise CommentRefusal(
                    f"reply {rupdate.reply_id} not found in comment {rupdate.parent_comment_id}"
                )
            if rupdate.expected_content_sha256:
                found = element_content_sha256(rel)
                if found != rupdate.expected_content_sha256:
                    raise CommentRefusal(
                        f"reply {rupdate.reply_id} changed since discovered "
                        f"({found} != {rupdate.expected_content_sha256})"
                    )
            if rupdate.text is not None:
                tx_body = rel.find(f"{{{ns}}}txBody") or rel.find(
                    f"{{{MODERN_POWERPOINT_NS}}}txBody"
                )
                if tx_body is None:
                    tx_body = ET.SubElement(rel, f"{{{ns}}}txBody")
                for child in list(tx_body):
                    tx_body.remove(child)
                ET.SubElement(tx_body, f"{{{A_NS}}}bodyPr")
                ET.SubElement(tx_body, f"{{{A_NS}}}lstStyle")
                for line in rupdate.text.split("\n"):
                    p_el = ET.SubElement(tx_body, f"{{{A_NS}}}p")
                    r_el = ET.SubElement(p_el, f"{{{A_NS}}}r")
                    ET.SubElement(r_el, f"{{{A_NS}}}rPr")
                    t_el = ET.SubElement(r_el, f"{{{A_NS}}}t")
                    t_el.text = line
            if rupdate.date is not None:
                rel.set("created", rupdate.date)
            if rupdate.status is not None:
                rel.set("status", rupdate.status)

        # 3. Reply deletes
        for rdel in work.reply_deletes:
            cm_el = cm_by_id.get(rdel.parent_comment_id)
            if cm_el is not None:
                reply_lst = cm_el.find(f"{{{ns}}}replyLst") or cm_el.find(
                    f"{{{MODERN_POWERPOINT_NS}}}replyLst"
                )
                if reply_lst is not None:
                    for r in list(reply_lst):
                        if r.get("id") == rdel.reply_id:
                            reply_lst.remove(r)

        # 4. Comment deletes
        for delete in work.deletes:
            cm_el = cm_by_id.get(delete.comment_id)
            if cm_el is not None:
                root.remove(cm_el)
                cm_by_id.pop(delete.comment_id, None)

        # 5. Comment adds
        if work.adds:
            slide_id = next(
                sid
                for _index, sid, part in presentation_slide_parts(self._parts)
                if part == slide_part
            )
        for add in work.adds:
            cm_el = ET.SubElement(
                root,
                f"{{{ns}}}cm",
                {
                    "id": add.comment_id,
                    "authorId": add.author_id,
                    "status": add.status,
                    "created": add.date,
                },
            )
            moniker = ET.SubElement(cm_el, f"{{{_PC_NS}}}sldMkLst")
            ET.SubElement(moniker, f"{{{_PC_NS}}}docMk")
            ET.SubElement(moniker, f"{{{_PC_NS}}}sldMk", {"sldId": str(slide_id)})
            ET.SubElement(cm_el, f"{{{ns}}}pos", {"x": str(add.x), "y": str(add.y)})
            tx = ET.SubElement(cm_el, f"{{{ns}}}txBody")
            ET.SubElement(tx, f"{{{A_NS}}}bodyPr")
            ET.SubElement(tx, f"{{{A_NS}}}lstStyle")
            for line in add.text.split("\n"):
                p_el = ET.SubElement(tx, f"{{{A_NS}}}p")
                r_el = ET.SubElement(p_el, f"{{{A_NS}}}r")
                ET.SubElement(r_el, f"{{{A_NS}}}rPr")
                t_el = ET.SubElement(r_el, f"{{{A_NS}}}t")
                t_el.text = line
            cm_el.attrib.update(add.attributes)
            cm_by_id[add.comment_id] = cm_el

        # 6. Reply adds
        for radd in work.reply_adds:
            cm_el = cm_by_id.get(radd.parent_comment_id)
            if cm_el is None:
                raise CommentRefusal(
                    f"cannot reply to comment {radd.parent_comment_id}: comment not found"
                )
            reply_lst = cm_el.find(f"{{{ns}}}replyLst") or cm_el.find(
                f"{{{MODERN_POWERPOINT_NS}}}replyLst"
            )
            if reply_lst is None:
                pos_idx = -1
                tx_idx = -1
                for idx, ch in enumerate(list(cm_el)):
                    tag_name = ch.tag.split("}")[-1]
                    if tag_name == "pos":
                        pos_idx = idx
                    elif tag_name == "txBody" and tx_idx == -1:
                        tx_idx = idx
                reply_lst = ET.Element(f"{{{ns}}}replyLst")
                if tx_idx != -1:
                    cm_el.insert(tx_idx, reply_lst)
                elif pos_idx != -1:
                    cm_el.insert(pos_idx + 1, reply_lst)
                else:
                    cm_el.insert(0, reply_lst)
            rel = ET.SubElement(
                reply_lst,
                f"{{{ns}}}reply",
                {
                    "id": radd.reply_id,
                    "authorId": radd.author_id,
                    "status": radd.status,
                    "created": radd.date,
                },
            )
            tx = ET.SubElement(rel, f"{{{ns}}}txBody")
            ET.SubElement(tx, f"{{{A_NS}}}bodyPr")
            ET.SubElement(tx, f"{{{A_NS}}}lstStyle")
            for line in radd.text.split("\n"):
                p_el = ET.SubElement(tx, f"{{{A_NS}}}p")
                r_el = ET.SubElement(p_el, f"{{{A_NS}}}r")
                ET.SubElement(r_el, f"{{{A_NS}}}rPr")
                t_el = ET.SubElement(r_el, f"{{{A_NS}}}t")
                t_el.text = line
        remaining = root.findall(f"{{{ns}}}cm")
        if not remaining and ns != MODERN_POWERPOINT_NS:
            remaining = root.findall(f"{{{MODERN_POWERPOINT_NS}}}cm")
        if not remaining:
            self._remove_modern_comments_part(slide_part, comments_part)
        else:
            self._store(
                comments_part,
                (
                    ET.tostring(root, encoding="utf-8", xml_declaration=True)
                    if payload is None
                    else _preserve_modern_extensions(payload, root)
                ),
            )

    def _write_modern_authors(self) -> None:
        authors = self._edits.modern_registry.authors
        if not authors:
            return
        payload = self._parts.get(AUTHORS_PART)
        if payload is None:
            root = ET.Element(f"{{{MODERN_POWERPOINT_NS}}}authorLst")
            elements: dict[str, ET.Element] = {}
            changed = True
            self._register_content_type(AUTHORS_PART, MODERN_AUTHORS_CONTENT_TYPE)
            self._add_presentation_relationship(MODERN_AUTHORS_REL, AUTHORS_PART)
        else:
            try:
                root = ET.fromstring(payload)
            except ET.ParseError as exc:
                raise CommentRefusal(f"{AUTHORS_PART} is malformed") from exc
            ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else MODERN_POWERPOINT_NS
            elements = {}
            for element in root.findall(f"{{{ns}}}author"):
                aid = element.get("id", "")
                if aid:
                    elements[aid] = element
            changed = False
        ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else MODERN_POWERPOINT_NS
        for author in authors:
            element = elements.get(author.id)
            if element is None:
                ET.SubElement(
                    root,
                    f"{{{ns}}}author",
                    {
                        "id": author.id,
                        "name": author.name,
                        "initials": author.initials,
                        "userId": author.user_id or author.name,
                        "providerId": author.provider_id or "AD",
                    },
                )
                elements[author.id] = root[-1]
                changed = True
        if not changed:
            return
        self._store(
            AUTHORS_PART,
            ET.tostring(root, encoding="utf-8", xml_declaration=True),
        )

    # -- queue plumbing -------------------------------------------------

    def _work(self) -> dict[str, _SlideCommentWork]:
        known = {
            slide_part for _index, _slide_id, slide_part in presentation_slide_parts(self._parts)
        }
        work: dict[str, _SlideCommentWork] = {}
        for add in self._edits.adds:
            if self._targetable(add.slide_part, known):
                self._group(work, add.slide_part).adds.append(add)
        for update in self._edits.updates:
            if self._targetable(update.slide_part, known):
                self._group(work, update.slide_part).updates.append(update)
        for delete in self._edits.deletes:
            if self._targetable(delete.slide_part, known):
                self._group(work, delete.slide_part).deletes.append(delete)
        return {part: item for part, item in work.items() if not item.empty}

    def _targetable(self, slide_part: str, known: set[str]) -> bool:
        normalized = part_name(slide_part)
        if normalized in self._deleted:
            # The slide is gone, so its queued comment work goes with it.
            return False
        if normalized not in known:
            raise CommentRefusal(
                f"comment target slide {normalized} is not part of the presentation"
            )
        return True

    @staticmethod
    def _group(work: dict[str, _SlideCommentWork], slide_part: str) -> _SlideCommentWork:
        return work.setdefault(part_name(slide_part), _SlideCommentWork())

    # -- one slide ------------------------------------------------------

    def _apply_slide(self, slide_part: str, work: _SlideCommentWork) -> None:
        relationship = slide_comment_relationship(self._parts, slide_part)
        if relationship is not None and relationship.kind != "legacy":
            raise CommentRefusal(
                f"{slide_part} reaches {relationship.relationship_type}, which is "
                "not a legacy comment relationship; it is preserved unchanged"
            )
        comments_part = None if relationship is None else relationship.part
        if comments_part is None:
            if work.updates or work.deletes:
                raise CommentRefusal(f"{slide_part} owns no legacy comments part to edit")
            root = ET.Element(f"{{{P_NS}}}cmLst")
            comments_part = self._create_comments_part(slide_part)
        else:
            payload = self._parts.get(comments_part)
            if payload is None:
                raise CommentRefusal(
                    f"{comments_part} is declared by {slide_part} but is not in the package"
                )
            try:
                root = ET.fromstring(payload)
            except ET.ParseError as exc:
                raise CommentRefusal(f"{comments_part} is malformed") from exc
            if root.tag != f"{{{P_NS}}}cmLst":
                raise CommentRefusal(f"{comments_part} root is not a cmLst")
        by_id: dict[int, ET.Element] = {}
        for element in root.findall(f"{{{P_NS}}}cm"):
            comment_id = int_attribute(element, "idx", f"{comments_part} comment")
            if comment_id in by_id:
                raise CommentRefusal(f"{comments_part} declares comment id {comment_id} twice")
            by_id[comment_id] = element
        deleted_parents: set[tuple[str | None, str | None]] = set()
        for delete in work.deletes:
            element = self._require_comment(
                by_id, delete.comment_id, delete.expected_content_sha256, comments_part
            )
            deleted_parents.add((element.get("authorId"), element.get("idx")))
            root.remove(element)
            del by_id[delete.comment_id]
        for update in work.updates:
            element = self._require_comment(
                by_id, update.comment_id, update.expected_content_sha256, comments_part
            )
            if update.text is not None:
                text = element.find(f"{{{P_NS}}}text")
                if text is None:
                    raise CommentRefusal(
                        f"{comments_part} comment {update.comment_id} has no p:text"
                    )
                text.text = update.text
            if update.date is not None:
                element.set("dt", update.date)
            if update.position is not None:
                pos = element.find(f"{{{P_NS}}}pos")
                if pos is None:
                    pos = ET.Element(f"{{{P_NS}}}pos")
                    element.insert(0, pos)
                pos.set("x", str(update.position[0]))
                pos.set("y", str(update.position[1]))
        for add in work.adds:
            if add.comment_id in by_id:
                raise CommentRefusal(
                    f"{comments_part} already declares comment id {add.comment_id}"
                )
            element = _comment_element(add)
            self._insert_comment(root, element)
            by_id[add.comment_id] = element
        # Detach survivors only after digest-bound updates and deletes have been
        # checked against their original subtrees. Keep timezone and opaque data.
        if deleted_parents:
            for element in by_id.values():
                for threading in _legacy_threading_info(element):
                    for parent in threading.findall(_LEGACY_PARENT_TAG):
                        if (parent.get("authorId"), parent.get("idx")) in deleted_parents:
                            threading.remove(parent)
        if by_id or len(root):
            self._store(comments_part, _comment_xml(root))
        else:
            self._remove_comments_part(slide_part, comments_part)

    @staticmethod
    def _require_comment(
        by_id: Mapping[int, ET.Element],
        comment_id: int,
        expected_content_sha256: str,
        comments_part: str,
    ) -> ET.Element:
        element = by_id.get(comment_id)
        if element is None:
            raise CommentRefusal(
                f"{comments_part} has no comment id {comment_id}; re-discover the "
                "target before editing it"
            )
        found = element_content_sha256(element)
        if found != expected_content_sha256:
            raise CommentRefusal(
                f"comment {comment_id} of {comments_part} changed since it was "
                f"discovered ({found} != {expected_content_sha256})"
            )
        return element

    @staticmethod
    def _insert_comment(root: ET.Element, element: ET.Element) -> None:
        extensions = root.find(f"{{{P_NS}}}extLst")
        if extensions is None:
            root.append(element)
        else:
            root.insert(list(root).index(extensions), element)

    # -- package-level parts --------------------------------------------

    def _create_comments_part(self, slide_part: str) -> str:
        comments_part = next_comments_part_name(tuple(self._parts) + tuple(self._replacements))
        self._register_content_type(comments_part, LEGACY_COMMENTS_CONTENT_TYPE)
        self._add_comment_relationship(slide_part, comments_part)
        return comments_part

    def _remove_comments_part(self, slide_part: str, comments_part: str) -> None:
        self._remove_part(comments_part)
        self._remove_content_type(comments_part)
        self._remove_comment_relationship(slide_part, comments_part)

    def _write_authors(self) -> None:
        authors = self._edits.registry.authors
        if not authors:
            return
        payload = self._parts.get(COMMENT_AUTHORS_PART)
        if payload is None:
            root = ET.Element(f"{{{P_NS}}}cmAuthorLst")
            elements: dict[int, ET.Element] = {}
            changed = True
            self._register_content_type(COMMENT_AUTHORS_PART, LEGACY_COMMENT_AUTHORS_CONTENT_TYPE)
            self._add_presentation_relationship(LEGACY_COMMENT_AUTHORS_REL, COMMENT_AUTHORS_PART)
        else:
            try:
                root = ET.fromstring(payload)
            except ET.ParseError as exc:
                raise CommentRefusal("ppt/commentAuthors.xml is malformed") from exc
            if root.tag != f"{{{P_NS}}}cmAuthorLst":
                raise CommentRefusal("ppt/commentAuthors.xml root is not a cmAuthorLst")
            elements = {}
            for element in root.findall(f"{{{P_NS}}}cmAuthor"):
                author_id = int_attribute(element, "id", "ppt/commentAuthors.xml author")
                if author_id in elements:
                    raise CommentRefusal(
                        f"ppt/commentAuthors.xml declares author id {author_id} twice"
                    )
                elements[author_id] = element
            changed = False
        highest = self._highest_comment_index_by_author()
        for author in authors:
            element = elements.get(author.author_id)
            if element is None:
                ET.SubElement(
                    root,
                    f"{{{P_NS}}}cmAuthor",
                    {
                        "id": str(author.author_id),
                        "name": author.name,
                        "initials": author.initials,
                        "lastIdx": str(highest.get(author.author_id, 0)),
                        "clrIdx": str(author.color_index),
                    },
                )
                elements[author.author_id] = root[-1]
                changed = True
                continue
            last_index = max(int(element.get("lastIdx") or 0), highest.get(author.author_id, 0))
            if str(last_index) != element.get("lastIdx"):
                element.set("lastIdx", str(last_index))
                changed = True
        if not changed:
            return
        self._store(
            COMMENT_AUTHORS_PART,
            ET.tostring(root, encoding="utf-8", xml_declaration=True),
        )

    def _highest_comment_index_by_author(self) -> dict[int, int]:
        highest: dict[int, int] = {}
        for part in comment_part_names(self._parts):
            payload = self._parts.get(part)
            if payload is None:
                continue
            for element in comment_elements(payload, part):
                author_id = int_attribute(element, "authorId", f"{part} comment")
                comment_id = int_attribute(element, "idx", f"{part} comment")
                highest[author_id] = max(highest.get(author_id, 0), comment_id)
        return highest

    def _register_content_type(self, part: str, content_type: str) -> None:
        payload = self._parts.get("[Content_Types].xml")
        if payload is None:
            raise CommentRefusal("the package has no [Content_Types].xml part")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise CommentRefusal("the package content types are malformed") from exc
        partname = f"/{part_name(part)}"
        for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
            if override.get("PartName") != partname:
                continue
            if override.get("ContentType") != content_type:
                raise CommentRefusal(
                    f"{partname} is declared with content type {override.get('ContentType')!r}"
                )
            return
        ET.SubElement(
            root,
            f"{{{CONTENT_TYPES_NS}}}Override",
            {"PartName": partname, "ContentType": content_type},
        )
        self._store("[Content_Types].xml", content_types_xml(root))

    def _remove_content_type(self, part: str) -> None:
        payload = self._parts.get("[Content_Types].xml")
        if payload is None:
            return
        root = ET.fromstring(payload)
        partname = f"/{part_name(part)}"
        removed = False
        for override in list(root.findall(f"{{{CONTENT_TYPES_NS}}}Override")):
            if override.get("PartName") == partname:
                root.remove(override)
                removed = True
        if removed:
            self._store("[Content_Types].xml", content_types_xml(root))

    def _add_comment_relationship(
        self,
        slide_part: str,
        comments_part: str,
        relationship_type: str = LEGACY_COMMENTS_REL,
    ) -> None:
        rels_part = rels_part_for_package_part(slide_part)
        root = self._relationship_root(rels_part, slide_part)
        relationship_id = _free_relationship_id(root)
        ET.SubElement(
            root,
            f"{{{PKG_REL_NS}}}Relationship",
            {
                "Id": relationship_id,
                "Type": relationship_type,
                "Target": relative_part_target(slide_part, comments_part),
            },
        )
        self._store(rels_part, relationships_xml(root))

    def _remove_comment_relationship(
        self,
        slide_part: str,
        comments_part: str,
        relationship_type: str = LEGACY_COMMENTS_REL,
    ) -> None:
        rels_part = rels_part_for_package_part(slide_part)
        payload = self._parts.get(rels_part)
        if payload is None:
            return
        root = ET.fromstring(payload)
        target = part_name(comments_part)
        removed = False
        for relationship in list(root.findall(f"{{{PKG_REL_NS}}}Relationship")):
            if relationship.get("Type") != relationship_type:
                continue
            if (
                part_name(
                    posixpath.normpath(
                        posixpath.join(
                            posixpath.dirname(part_name(slide_part)),
                            relationship.get("Target", ""),
                        )
                    )
                )
                != target
            ):
                continue
            root.remove(relationship)
            removed = True
        if removed:
            self._store(rels_part, relationships_xml(root))

    def _add_presentation_relationship(self, relationship_type: str, target_part: str) -> None:
        presentation_part = presentation_partname(self._parts)
        rels_part = rels_part_for_package_part(presentation_part)
        root = self._relationship_root(rels_part, presentation_part)
        for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
            if relationship.get("Type") != relationship_type:
                continue
            if part_name(
                posixpath.normpath(
                    posixpath.join(
                        posixpath.dirname(presentation_part),
                        relationship.get("Target", ""),
                    )
                )
            ) == part_name(target_part):
                return
            raise CommentRefusal(
                f"{presentation_part} already relates a different part as {relationship_type}"
            )
        ET.SubElement(
            root,
            f"{{{PKG_REL_NS}}}Relationship",
            {
                "Id": _free_relationship_id(root),
                "Type": relationship_type,
                "Target": relative_part_target(presentation_part, target_part),
            },
        )
        self._store(rels_part, relationships_xml(root))

    def _relationship_root(self, rels_part: str, owner: str) -> ET.Element:
        payload = self._parts.get(rels_part)
        if payload is None:
            raise CommentRefusal(f"{owner} has no relationship part")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise CommentRefusal(f"{owner} relationships are malformed") from exc
        if root.tag != f"{{{PKG_REL_NS}}}Relationships":
            raise CommentRefusal(f"{owner} relationships have an invalid root element")
        return root

    def _store(self, part: str, payload: bytes) -> None:
        normalized = part_name(part)
        if normalized not in self._parts:
            self._added.add(normalized)
        self._parts[normalized] = payload
        self._replacements[normalized] = payload
        if normalized not in self._changed:
            self._changed.append(normalized)

    def _remove_part(self, part: str) -> None:
        normalized = part_name(part)
        if normalized not in self._parts:
            return
        del self._parts[normalized]
        self._replacements.pop(normalized, None)
        self._added.discard(normalized)
        self._removals.add(normalized)
        if normalized in self._changed:
            self._changed.remove(normalized)


def _comment_xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _comment_element(add: CommentAdd) -> ET.Element:
    element = ET.Element(
        f"{{{P_NS}}}cm",
        {
            "authorId": str(add.author_id),
            "dt": add.date,
            "idx": str(add.comment_id),
        },
    )
    ET.SubElement(element, f"{{{P_NS}}}pos", {"x": str(add.x), "y": str(add.y)})
    text = ET.SubElement(element, f"{{{P_NS}}}text")
    text.text = add.text
    return element


def _free_relationship_id(root: ET.Element) -> str:
    return next_relationship_id(
        relationship.get("Id") or ""
        for relationship in relationship_elements(
            ET.tostring(root, encoding="utf-8"), "relationship"
        )
    )


def apply_legacy_comment_edits(
    input_path: Path,
    output_path: Path,
    edits: PendingCommentEdits,
    *,
    deleted_slide_parts: Iterable[str] = (),
) -> dict[str, Any]:
    """Write one package with every queued legacy comment edit applied.

    ``input_path`` is only read, and ``output_path`` is a staging path: the
    caller publishes it through the presentation save pipeline.
    """
    return _CommentPackageWriter(input_path, edits, deleted_slide_parts).write(output_path)


def pending_comment_edits(presentation: Any) -> PendingCommentEdits:
    edits = getattr(presentation, "_comment_edits", None)
    if edits is None:
        edits = PendingCommentEdits(read_package(presentation.path))
        presentation._comment_edits = edits
    return edits


def has_pending_comment_edits(presentation: Any) -> bool:
    edits = getattr(presentation, "_comment_edits", None)
    return edits is not None and edits.has_work()


def presentation_comment_authors(presentation: Any) -> tuple[CommentAuthor, ...]:
    return pending_comment_edits(presentation).registry.authors


def presentation_modern_comment_authors(
    presentation: Any,
) -> tuple[ModernCommentAuthor, ...]:
    return pending_comment_edits(presentation).modern_registry.authors


def reset_comment_state(presentation: Any) -> None:
    presentation._comment_edits = None
    for slide in getattr(presentation, "_slides", ()) or ():
        slide._comments = None


__all__ = [
    "CommentAdd",
    "CommentDelete",
    "CommentRegistry",
    "CommentUpdate",
    "ModernCommentAdd",
    "ModernCommentDelete",
    "ModernCommentRegistry",
    "ModernCommentUpdate",
    "ModernReplyAdd",
    "ModernReplyDelete",
    "ModernReplyUpdate",
    "PendingCommentEdits",
    "SlideComment",
    "SlideCommentReply",
    "SlideComments",
    "apply_legacy_comment_edits",
    "has_pending_comment_edits",
    "pending_comment_edits",
    "presentation_comment_authors",
    "presentation_modern_comment_authors",
    "required_comment_date",
    "required_comment_position",
    "required_text",
    "reset_comment_state",
]


# Re-exported so existing ``comment_edits.<name>`` imports keep working.
# isort: split
from .comment_edits_slide import (  # noqa: E402 - shared edit records must exist first
    SlideComment,
    SlideCommentReply,
    SlideComments,
    _discovered_arguments,  # noqa: F401
)
# isort: split
