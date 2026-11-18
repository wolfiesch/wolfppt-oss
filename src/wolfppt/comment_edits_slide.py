"""Part of ``comment_edits``; split out verbatim to keep modules reviewable."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from types import MappingProxyType
from typing import Any, overload

from .comment_edits import (
    _LEGACY_PARENT_TAG,
    CommentAdd,
    CommentDelete,
    CommentUpdate,
    ModernCommentAdd,
    ModernCommentDelete,
    ModernCommentUpdate,
    ModernReplyAdd,
    ModernReplyDelete,
    ModernReplyUpdate,
    PendingCommentEdits,
    _legacy_threading_info,
    pending_comment_edits,
    required_comment_date,
    required_comment_position,
    required_comment_status,
    required_text,
)
from .comments_facade import (
    CommentAnchorMoniker,
    CommentRefusal,
    DiscoveredComment,
    DiscoveredReaction,
    OpaqueCommentExtension,
    SlideCommentTarget,
    comment_elements,
    comment_timestamp,
    part_name,
)


class SlideCommentReply:
    """One modern threaded comment reply, and the edits queued against it."""

    def __init__(
        self,
        comment: SlideComment,
        *,
        reply_id: str,
        author_id: str,
        author: str,
        initials: str,
        date: str,
        text: str,
        status: str = "active",
        content_sha256: str | None = None,
        reactions: Sequence[DiscoveredReaction] = (),
        queued_add: ModernReplyAdd | None = None,
    ) -> None:
        self._comment = comment
        self._reply_id = reply_id
        self._author_id = author_id
        self._author = author
        self._initials = initials
        self._date = date
        self._text = text
        self._status = status
        self._content_sha256 = content_sha256
        self._reactions = tuple(reactions)
        self._queued_add = queued_add

    def __repr__(self) -> str:
        return (
            f"SlideCommentReply(reply_id={self._reply_id!r}, author={self._author!r}, "
            f"text={self._text!r})"
        )

    @property
    def comment(self) -> SlideComment:
        return self._comment

    @property
    def slide(self) -> Any:
        return self._comment.slide

    @property
    def slide_part(self) -> str:
        return self._comment.slide_part

    @property
    def reply_id(self) -> str:
        return self._reply_id

    @property
    def author_id(self) -> str:
        return self._author_id

    @property
    def author(self) -> str:
        return self._author

    @property
    def initials(self) -> str:
        return self._initials

    @property
    def date(self) -> str:
        return self._date

    @date.setter
    def date(self, value: Any) -> None:
        date = required_comment_date(value)
        if date == self._date:
            return
        self._date = date
        if self._queued_add is not None:
            self._queued_add.date = date
            return
        self._comment._comments.queue_modern_reply_update(self, date=date)

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: Any) -> None:
        text = required_text(value, "reply text")
        if text == self._text:
            return
        self._text = text
        if self._queued_add is not None:
            self._queued_add.text = text
            return
        self._comment._comments.queue_modern_reply_update(self, text=text)

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: Any) -> None:
        val = required_comment_status(value)
        if val == self._status:
            return
        self._status = val
        if self._queued_add is not None:
            self._queued_add.status = val
            return
        self._comment._comments.queue_modern_reply_update(self, status=val)

    @property
    def reactions(self) -> tuple[DiscoveredReaction, ...]:
        """The reactions on this reply (read-only)."""
        return self._reactions

    @property
    def content_sha256(self) -> str | None:
        return self._content_sha256

    def remove(self) -> None:
        self._comment._remove_reply(self)


class SlideComment:
    """One legacy or modern comment of one slide, and the edits queued against it."""

    def __init__(
        self,
        comments: SlideComments,
        *,
        comment_id: int | str,
        author_id: int | str,
        author: str,
        initials: str,
        date: str,
        text: str,
        position: tuple[int, int],
        content_sha256: str | None,
        kind: str = "legacy",
        status: str = "active",
        replies: Sequence[SlideCommentReply | SlideComment] = (),
        reactions: Sequence[DiscoveredReaction] = (),
        queued_add: CommentAdd | ModernCommentAdd | None = None,
        attributes: Mapping[str, str] | None = None,
        anchor_moniker: CommentAnchorMoniker | None = None,
        opaque_extensions: Sequence[OpaqueCommentExtension] = (),
    ) -> None:
        self._comments = comments
        self._comment_id = comment_id
        self._author_id = author_id
        self._author = author
        self._initials = initials
        self._date = date
        self._text = text
        self._position = position
        self._content_sha256 = content_sha256
        self._kind = kind
        self._status = status
        self._replies: list[SlideCommentReply | SlideComment] = list(replies)
        self._reactions = tuple(reactions)
        self._queued_add = queued_add
        self._attributes = dict(attributes or {})
        self._anchor_moniker = anchor_moniker
        self._opaque_extensions = tuple(opaque_extensions)

    def __repr__(self) -> str:
        return (
            f"SlideComment(comment_id={self._comment_id}, author={self._author!r}, "
            f"text={self._text!r}, kind={self._kind!r})"
        )

    @property
    def slide_part(self) -> str:
        """The slide part this comment belongs to."""
        return self._comments.slide_part

    @property
    def slide(self) -> Any:
        """The slide this comment belongs to."""
        return self._comments.slide

    @property
    def comment_id(self) -> int | str:
        """The comment ID inside its slide's own comments part."""
        return self._comment_id

    @property
    def kind(self) -> str:
        """Whether this comment is 'legacy' or 'modern'."""
        return self._kind

    @property
    def author(self) -> str:
        """The presentation-scoped author name."""
        return self._author

    @property
    def initials(self) -> str:
        """The presentation-scoped author initials."""
        return self._initials

    @property
    def author_id(self) -> int | str:
        """The presentation-scoped author ID."""
        return self._author_id

    @property
    def date(self) -> str:
        """The comment timestamp."""
        return self._date

    @date.setter
    def date(self, value: Any) -> None:
        date = required_comment_date(value)
        if date == self._date:
            return
        self._date = date
        if self._queued_add is not None:
            self._queued_add.date = date
            return
        if self._kind == "modern":
            self._comments.queue_modern_update(self, date=date)
        else:
            self._comments.queue_update(self, date=date)

    @property
    def text(self) -> str:
        """The comment text."""
        return self._text

    @text.setter
    def text(self, value: Any) -> None:
        text = required_text(value, "comment text")
        if text == self._text:
            return
        self._text = text
        if self._queued_add is not None:
            self._queued_add.text = text
            return
        if self._kind == "modern":
            self._comments.queue_modern_update(self, text=text)
        else:
            self._comments.queue_update(self, text=text)

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: Any) -> None:
        val = (
            required_comment_status(value)
            if self._kind == "modern"
            else required_text(value, "comment status")
        )
        if val == self._status:
            return
        self._status = val
        if self._queued_add is not None and isinstance(self._queued_add, ModernCommentAdd):
            self._queued_add.status = val
            return
        if self._kind == "modern":
            self._comments.queue_modern_update(self, status=val)

    @property
    def position(self) -> tuple[int, int]:
        """The comment anchor in English Metric Units."""
        return self._position

    @position.setter
    def position(self, value: Any) -> None:
        coordinates = required_comment_position(value)
        if self._kind != "legacy":
            raise CommentRefusal("position updates are supported only for legacy comments")
        if coordinates == self._position:
            return
        if isinstance(self._queued_add, CommentAdd):
            self._queued_add.x, self._queued_add.y = coordinates
        else:
            self._comments.queue_update(self, position=coordinates)
        self._position = coordinates

    @property
    def content_sha256(self) -> str | None:
        """Digest of the comment as the source package declares it."""
        return self._content_sha256

    @property
    def pending(self) -> bool:
        """Whether this comment is a queued addition or carries a queued edit."""
        return self._queued_add is not None or self._content_sha256 is None

    @property
    def replies(self) -> tuple[SlideCommentReply | SlideComment, ...]:
        """Direct replies, with legacy entries shared with the flat slide collection."""
        return tuple(self._replies)

    @property
    def reactions(self) -> tuple[DiscoveredReaction, ...]:
        """Existing reactions and likes authored through add_reaction."""
        return self._reactions

    @property
    def mentions(self) -> tuple[str, ...]:
        """Author IDs tagged in the schema-defined p188:cm/@tags list."""
        return tuple(self._attributes.get("tags", "").split())

    @property
    def anchor_moniker(self) -> CommentAnchorMoniker | None:
        """The declared pc:sldMkLst, or None when absent."""
        return self._anchor_moniker

    @property
    def task_attributes(self) -> Mapping[str, str]:
        """Present task attributes with their source lexical values, without defaults."""
        return MappingProxyType(
            {
                name: self._attributes[name]
                for name in ("assignedTo", "complete", "priority", "title", "dueDate")
                if name in self._attributes
            }
        )

    @property
    def opaque_extensions(self) -> tuple[OpaqueCommentExtension, ...]:
        """Uninterpreted extension XML, including any range-mention metadata."""
        return self._opaque_extensions

    def add_mention(
        self, author: Any, *, initials: Any = None, user_id: Any = None, provider_id: Any = "AD"
    ) -> str:
        """Tag an author; preserve opaque mention extensions without interpreting them.

        This edits package metadata only, without sending a notification.
        """
        record = self._collaboration_author(author, initials, user_id, provider_id)
        ids = list(self.mentions)
        if record.id not in ids:
            ids.append(record.id)
            self._set_attributes({"tags": " ".join(ids)})
        return record.id

    def add_reaction(
        self,
        reaction_type: Any,
        author: Any,
        *,
        initials: Any = None,
        user_id: Any = None,
        provider_id: Any = "AD",
    ) -> str:
        """Add an author's like through p188:cm/@likes.

        Other reaction kinds have no supported encoding and are refused atomically.
        """
        if reaction_type != "like":
            raise CommentRefusal("only the schema-defined like reaction is supported")
        record = self._collaboration_author(author, initials, user_id, provider_id)
        ids = self._attributes.get("likes", "").split()
        if record.id not in ids:
            ids.append(record.id)
            self._set_attributes({"likes": " ".join(ids)})
            self._reactions += (
                DiscoveredReaction(
                    reaction_id="",
                    author_id=record.id,
                    author=record.name,
                    initials=record.initials,
                    reaction_type="like",
                ),
            )
        return record.id

    def assign(
        self,
        author: Any,
        *,
        initials: Any = None,
        user_id: Any = None,
        provider_id: Any = "AD",
        title: Any = None,
        due_date: Any = None,
    ) -> str:
        """Assign this task to one author, optionally setting its title and due date.

        Existing completion, priority and other task metadata remain unchanged.
        """
        attributes = {}
        if title is not None:
            attributes["title"] = required_text(title, "task title")
        if due_date is not None:
            attributes["dueDate"] = required_comment_date(due_date, "task due date")
        record = self._collaboration_author(author, initials, user_id, provider_id)
        attributes["assignedTo"] = record.id
        self._set_attributes(attributes)
        return record.id

    def _collaboration_author(
        self, author: Any, initials: Any, user_id: Any, provider_id: Any
    ) -> Any:
        if self._kind != "modern":
            raise CommentRefusal("reactions, mentions and tasks require a modern comment")
        return self._comments._edits().modern_registry.resolve(
            author, initials, user_id=user_id, provider_id=provider_id
        )

    def _set_attributes(self, attributes: dict[str, str]) -> None:
        if isinstance(self._queued_add, ModernCommentAdd):
            self._queued_add.attributes.update(attributes)
        else:
            self._comments.queue_modern_update(self, attributes=attributes)
        self._attributes.update(attributes)

    def add_reply(
        self,
        text: Any,
        author: Any,
        *,
        initials: Any = None,
        date: Any = None,
        user_id: Any = None,
        provider_id: Any = "AD",
        status: str = "active",
    ) -> SlideCommentReply:
        """Queue a threaded reply to this modern comment and return it."""
        status = required_comment_status(status)
        slide_part = self.slide_part
        edits = self._comments._edits()
        body = required_text(text, "reply text")
        record = edits.modern_registry.resolve(
            author, initials, user_id=user_id, provider_id=provider_id
        )
        timestamp = comment_timestamp() if date is None else required_comment_date(date)
        reply_id = f"{{{str(uuid.uuid4()).upper()}}}"
        queued = ModernReplyAdd(
            slide_part=slide_part,
            parent_comment_id=str(self._comment_id),
            reply_id=reply_id,
            author_id=record.id,
            date=timestamp,
            text=body,
            status=status,
        )
        edits.modern_reply_adds.append(queued)
        reply = SlideCommentReply(
            self,
            reply_id=reply_id,
            author_id=record.id,
            author=record.name,
            initials=record.initials,
            date=timestamp,
            text=body,
            status=status,
            content_sha256=None,
            queued_add=queued,
        )
        self._replies.append(reply)
        return reply

    def reply(self, *args: Any, **kwargs: Any) -> SlideCommentReply:
        """Alias for add_reply."""
        return self.add_reply(*args, **kwargs)

    def remove(self) -> None:
        """Queue the removal of this comment."""
        self._comments.remove(self)

    def _remove_reply(self, reply: SlideCommentReply) -> None:
        edits = self._comments._edits()
        if reply._queued_add is not None:
            if reply._queued_add in edits.modern_reply_adds:
                edits.modern_reply_adds.remove(reply._queued_add)
        else:
            edits.modern_reply_deletes.append(
                ModernReplyDelete(
                    slide_part=self.slide_part,
                    parent_comment_id=str(self._comment_id),
                    reply_id=reply.reply_id,
                    expected_content_sha256=reply.content_sha256,
                )
            )
        if reply in self._replies:
            self._replies.remove(reply)


class SlideComments(Sequence[SlideComment]):
    """The comments of one slide, discovered from the source package."""

    def __init__(self, slide: Any) -> None:
        self._slide = slide
        self._loaded = False
        self._target: SlideCommentTarget | None = None
        self._comments: list[SlideComment] = []

    def __repr__(self) -> str:
        return f"SlideComments(slide_part={self._target_slide_part()!r})"

    @property
    def slide(self) -> Any:
        return self._slide

    @property
    def slide_part(self) -> str:
        return self._target_slide_part()

    @property
    def is_modern(self) -> bool:
        self._ensure_loaded()
        if self._target is not None and self._target.modern:
            return True
        return self._edits().is_modern

    @property
    def comments_part(self) -> str | None:
        self._ensure_loaded()
        return None if self._target is None else self._target.comments_part

    @property
    def relationship_id(self) -> str | None:
        self._ensure_loaded()
        return None if self._target is None else self._target.relationship_id

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._comments)

    @overload
    def __getitem__(self, index: int) -> SlideComment: ...

    @overload
    def __getitem__(self, index: slice) -> list[SlideComment]: ...

    def __getitem__(self, index: int | slice) -> SlideComment | list[SlideComment]:
        self._ensure_loaded()
        return self._comments[index]

    def __iter__(self) -> Iterator[SlideComment]:
        self._ensure_loaded()
        return iter(self._comments)

    def add(
        self,
        text: Any,
        author: Any,
        *,
        initials: Any = None,
        date: Any = None,
        position: Any = None,
        modern: bool | None = None,
        user_id: Any = None,
        provider_id: Any = "AD",
        status: str = "active",
    ) -> SlideComment:
        """Queue a new comment on this slide and return it."""
        slide_part = self._target_slide_part()
        edits = self._edits()
        should_modern = (modern is True) or (modern is None and self.is_modern)

        if should_modern:
            return self.add_modern(
                text,
                author,
                initials=initials,
                date=date,
                position=position,
                user_id=user_id,
                provider_id=provider_id,
                status=status,
            )

        edits.refuse_modern()
        body = required_text(text, "comment text")
        record = edits.registry.resolve(author, initials)
        timestamp = comment_timestamp() if date is None else required_comment_date(date)
        coordinates = required_comment_position(position)
        comment_id = edits.consume_comment_id()
        queued = CommentAdd(
            slide_part=slide_part,
            comment_id=comment_id,
            author_id=record.author_id,
            date=timestamp,
            text=body,
            x=coordinates[0],
            y=coordinates[1],
        )
        edits.adds.append(queued)
        self._ensure_loaded()
        comment = SlideComment(
            self,
            comment_id=comment_id,
            author_id=record.author_id,
            author=record.name,
            initials=record.initials,
            date=timestamp,
            text=body,
            position=coordinates,
            content_sha256=None,
            kind="legacy",
            queued_add=queued,
        )
        self._comments.append(comment)
        return comment

    def add_modern(
        self,
        text: Any,
        author: Any,
        *,
        initials: Any = None,
        date: Any = None,
        position: Any = None,
        user_id: Any = None,
        provider_id: Any = "AD",
        status: str = "active",
    ) -> SlideComment:
        """Queue a new modern threaded comment on this slide and return it."""
        status = required_comment_status(status)
        slide_part = self._target_slide_part()
        edits = self._edits()
        body = required_text(text, "comment text")
        record = edits.modern_registry.resolve(
            author, initials, user_id=user_id, provider_id=provider_id
        )
        timestamp = comment_timestamp() if date is None else required_comment_date(date)
        coordinates = required_comment_position(position)
        comment_id = f"{{{str(uuid.uuid4()).upper()}}}"
        queued = ModernCommentAdd(
            slide_part=slide_part,
            comment_id=comment_id,
            author_id=record.id,
            date=timestamp,
            text=body,
            x=coordinates[0],
            y=coordinates[1],
            status=status,
        )
        edits.modern_adds.append(queued)
        self._ensure_loaded()
        comment = SlideComment(
            self,
            comment_id=comment_id,
            author_id=record.id,
            author=record.name,
            initials=record.initials,
            date=timestamp,
            text=body,
            position=coordinates,
            content_sha256=None,
            kind="modern",
            status=status,
            queued_add=queued,
        )
        self._comments.append(comment)
        return comment

    def remove(self, comment: int | str | SlideComment) -> None:
        """Queue the removal of one comment."""
        target = self._resolve(comment)
        edits = self._edits()
        if target.kind == "modern":
            if target._queued_add is not None:
                if target._queued_add in edits.modern_adds:
                    edits.modern_adds.remove(target._queued_add)
            else:
                edits.modern_deletes.append(
                    ModernCommentDelete(
                        slide_part=target.slide_part,
                        comment_id=str(target.comment_id),
                        expected_content_sha256=target.content_sha256,
                    )
                )
        else:
            edits.refuse_modern()
            if target._queued_add is not None:
                edits.adds.remove(target._queued_add)
            else:
                edits.drop_comment(target.slide_part, target.comment_id)
                edits.deletes.append(
                    CommentDelete(
                        slide_part=target.slide_part,
                        comment_id=target.comment_id,
                        expected_content_sha256=target.content_sha256 or "",
                    )
                )
        self._comments.remove(target)
        if target.kind == "legacy":
            for candidate in self._comments:
                if target in candidate._replies:
                    candidate._replies.remove(target)
            target._replies.clear()

    def index(self, comment: SlideComment, *args: Any) -> int:
        self._ensure_loaded()
        return self._comments.index(comment, *args)

    def queue_update(
        self,
        comment: SlideComment,
        *,
        text: str | None = None,
        date: str | None = None,
        position: tuple[int, int] | None = None,
    ) -> None:
        edits = self._edits()
        edits.refuse_modern()
        record = edits.update_for(comment.slide_part, comment.comment_id)
        if record is None:
            if comment.content_sha256 is None:
                raise CommentRefusal(
                    f"comment {comment.comment_id} of {comment.slide_part} has no "
                    "version in the source package to update"
                )
            record = CommentUpdate(
                slide_part=comment.slide_part,
                comment_id=comment.comment_id,
                expected_content_sha256=comment.content_sha256,
            )
            edits.updates.append(record)
        if text is not None:
            record.text = text
        if date is not None:
            record.date = date
        if position is not None:
            record.position = position

    def queue_modern_update(
        self,
        comment: SlideComment,
        *,
        text: str | None = None,
        date: str | None = None,
        status: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> None:
        edits = self._edits()
        record = edits.modern_update_for(comment.slide_part, str(comment.comment_id))
        if record is None:
            record = ModernCommentUpdate(
                slide_part=comment.slide_part,
                comment_id=str(comment.comment_id),
                expected_content_sha256=comment.content_sha256,
            )
            edits.modern_updates.append(record)
        if text is not None:
            record.text = text
        if date is not None:
            record.date = date
        if status is not None:
            record.status = status
        if attributes is not None:
            record.attributes.update(attributes)

    def queue_modern_reply_update(
        self,
        reply: SlideCommentReply,
        *,
        text: str | None = None,
        date: str | None = None,
        status: str | None = None,
    ) -> None:
        edits = self._edits()
        record = edits.modern_reply_update_for(
            reply.slide_part, str(reply.comment.comment_id), reply.reply_id
        )
        if record is None:
            record = ModernReplyUpdate(
                slide_part=reply.slide_part,
                parent_comment_id=str(reply.comment.comment_id),
                reply_id=reply.reply_id,
                expected_content_sha256=reply.content_sha256,
            )
            edits.modern_reply_updates.append(record)
        if text is not None:
            record.text = text
        if date is not None:
            record.date = date
        if status is not None:
            record.status = status

    def _resolve(self, comment: int | str | SlideComment) -> SlideComment:
        self._ensure_loaded()
        if isinstance(comment, SlideComment):
            for candidate in self._comments:
                if candidate is comment:
                    return candidate
            raise CommentRefusal("that comment does not belong to this slide")
        if isinstance(comment, int) and not isinstance(comment, bool):
            if 0 <= comment < len(self._comments):
                return self._comments[comment]
            raise CommentRefusal(f"comment index {comment} out of range")
        if isinstance(comment, str):
            for candidate in self._comments:
                if str(candidate.comment_id) == comment:
                    return candidate
            raise CommentRefusal(f"no comment with id {comment}")
        raise CommentRefusal("comment must be an index, id, or a SlideComment")

    def _edits(self) -> PendingCommentEdits:
        return pending_comment_edits(self.slide._presentation)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._target = self._edits().slide_target(self._target_slide_part())
        for discovered in self._target.comments:
            comment = SlideComment(self, **_discovered_arguments(discovered))
            for r in discovered.replies:
                comment._replies.append(
                    SlideCommentReply(
                        comment,
                        reply_id=r.reply_id,
                        author_id=r.author_id,
                        author=r.author,
                        initials=r.initials,
                        date=r.date,
                        text=r.text,
                        status=r.status,
                        content_sha256=r.content_sha256,
                        reactions=r.reactions,
                    )
                )
            for author_id in comment._attributes.get("likes", "").split():
                author = self._edits().modern_registry.by_id(author_id)
                comment._reactions += (
                    DiscoveredReaction(
                        reaction_id="",
                        author_id=author_id,
                        author="" if author is None else author.name,
                        initials="" if author is None else author.initials,
                        reaction_type="like",
                    ),
                )
            self._comments.append(comment)
        if not self._target.modern and self._target.comments_part is not None:
            by_key = {
                (str(comment.author_id), str(comment.comment_id)): comment
                for comment in self._comments
            }
            for element, comment in zip(
                comment_elements(
                    self._edits().parts[self._target.comments_part], self._target.comments_part
                ),
                self._comments,
                strict=True,
            ):
                for threading in _legacy_threading_info(element):
                    parent = threading.find(_LEGACY_PARENT_TAG)
                    if parent is not None:
                        owner = by_key.get((parent.get("authorId"), parent.get("idx")))
                        if owner is not None and owner is not comment:
                            owner._replies.append(comment)

    def _target_slide_part(self) -> str:
        slide = self._slide
        part = part_name(slide.partname)
        if not part:
            raise CommentRefusal(
                "a slide added in this session owns no package part until the "
                "presentation is saved; save the presentation before commenting on it"
            )
        if slide._payload.get("_pending_creation"):
            raise CommentRefusal(
                f"{part} belongs to a slide duplicated or added in this session; "
                "save the presentation before commenting on it"
            )
        return part


def _discovered_arguments(discovered: DiscoveredComment) -> dict[str, Any]:
    args: dict[str, Any] = {
        "comment_id": discovered.comment_id,
        "author_id": discovered.author_id,
        "author": discovered.author,
        "initials": discovered.initials,
        "date": discovered.date,
        "text": discovered.text,
        "position": discovered.position,
        "content_sha256": discovered.content_sha256,
        "kind": discovered.kind,
        "status": discovered.status,
        "reactions": discovered.reactions,
        "attributes": discovered.attributes,
        "anchor_moniker": discovered.anchor_moniker,
        "opaque_extensions": discovered.opaque_extensions,
    }
    return args
