"""CLI entry points for source-bound PowerPoint comment authoring.

Two surfaces, matching the rest of the harness CLI:

``comment-targets --source DECK.pptx``
    read-only discovery.  Reports the source digest a request must state, the
    presentation-scoped authors, and every slide's comments part, relationship,
    and comments with their own content digests.

``comment --request REQUEST.json --input DECK.pptx --output OUT.pptx``
    one mutation.  A request is a strict JSON object: unknown keys, a stale
    ``source_sha256``, an occupied destination, an ambiguous slide target, or a
    comment whose discovered content changed all refuse before anything is
    published.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .comment_edits import (
    required_comment_date,
    required_comment_position,
    required_text,
)
from .comments_facade import (
    P_NS,
    SHA256_DIGEST,
    CommentRefusal,
    discover_comment_targets,
    element_content_sha256,
    part_name,
    sha256_file,
)

OPERATIONS = ("add", "update", "delete", "reply")

_TARGET_KEYS = frozenset({"source_sha256", "operation", "slide_index", "slide_part"})
_REQUEST_KEYS = {
    "add": _TARGET_KEYS
    | {
        "author",
        "initials",
        "date",
        "text",
        "position",
        "modern",
        "status",
        "user_id",
        "provider_id",
    },
    "reply": _TARGET_KEYS
    | {
        "comment_id",
        "parent_id",
        "comment_sha256",
        "author",
        "initials",
        "date",
        "text",
        "status",
        "user_id",
        "provider_id",
    },
    "update": _TARGET_KEYS
    | {"comment_id", "reply_id", "comment_sha256", "text", "date", "status"},
    "delete": _TARGET_KEYS | {"comment_id", "reply_id", "comment_sha256"},
}
_REQUIRED_KEYS = {
    "add": ("source_sha256", "author", "text"),
    "reply": ("source_sha256", "author", "text"),
    "update": ("source_sha256", "comment_id", "comment_sha256"),
    "delete": ("source_sha256", "comment_id", "comment_sha256"),
}


@dataclass(frozen=True)
class CommentRequest:
    """One validated, source-bound legacy or modern comment mutation."""

    source_sha256: str
    operation: str
    slide_index: int | None
    slide_part: str | None
    author: str | None
    initials: str | None
    date: str | None
    text: str | None
    position: tuple[int, int] | None
    comment_id: int | str | None
    comment_sha256: str | None
    modern: bool | None = None
    status: str | None = None
    reply_id: str | None = None
    parent_id: str | None = None
    user_id: str | None = None
    provider_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "source_sha256": self.source_sha256,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "author": self.author,
            "initials": self.initials,
            "date": self.date,
            "text": self.text,
            "position": None
            if self.position is None
            else {"x": self.position[0], "y": self.position[1]},
            "comment_id": self.comment_id,
            "comment_sha256": self.comment_sha256,
            "modern": self.modern,
            "status": self.status,
            "reply_id": self.reply_id,
            "parent_id": self.parent_id,
            "user_id": self.user_id,
            "provider_id": self.provider_id,
        }


def load_comment_request(path: str | Path) -> dict[str, Any]:
    """Read one comment request document from disk."""
    request_path = Path(path).expanduser()
    if not request_path.is_file():
        raise CommentRefusal(f"comment request {request_path} does not exist")
    try:
        document = json.loads(request_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CommentRefusal(f"{request_path} is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise CommentRefusal("a comment request must be a JSON object")
    return document


def parse_comment_request(document: Mapping[str, Any]) -> CommentRequest:
    """Validate one comment request document into a typed request."""
    operation = document.get("operation")
    if operation not in OPERATIONS:
        raise CommentRefusal(f"operation must be one of {', '.join(OPERATIONS)}")
    unknown = sorted(set(document) - _REQUEST_KEYS[operation])
    if unknown:
        raise CommentRefusal(
            f"a {operation} request does not accept {', '.join(unknown)}"
        )
    missing = [key for key in _REQUIRED_KEYS[operation] if document.get(key) is None]
    if missing:
        raise CommentRefusal(f"a {operation} request requires {', '.join(missing)}")
    source_sha256 = document.get("source_sha256")
    if not isinstance(source_sha256, str) or SHA256_DIGEST.match(source_sha256) is None:
        raise CommentRefusal("source_sha256 must be the lowercase sha256 of the source")
    slide_index, slide_part = _parse_slide_target(document)
    if operation == "add":
        return CommentRequest(
            source_sha256=source_sha256,
            operation=operation,
            slide_index=slide_index,
            slide_part=slide_part,
            author=required_text(document.get("author"), "comment author"),
            initials=_optional_text(document.get("initials"), "comment initials"),
            date=_optional_date(document.get("date")),
            text=required_text(document.get("text"), "comment text"),
            position=required_comment_position(document.get("position")),
            comment_id=None,
            comment_sha256=None,
            modern=document.get("modern"),
            status=_optional_text(document.get("status"), "comment status"),
            user_id=_optional_text(document.get("user_id"), "user id"),
            provider_id=_optional_text(document.get("provider_id"), "provider id"),
        )
    if operation == "reply":
        cid = document.get("comment_id") or document.get("parent_id")
        if cid is None:
            raise CommentRefusal("a reply request requires comment_id or parent_id")
        comment_id = _parse_comment_id(cid)
        comment_sha256 = (
            _parse_comment_digest(document.get("comment_sha256"))
            if document.get("comment_sha256") is not None
            else None
        )
        return CommentRequest(
            source_sha256=source_sha256,
            operation=operation,
            slide_index=slide_index,
            slide_part=slide_part,
            author=required_text(document.get("author"), "comment author"),
            initials=_optional_text(document.get("initials"), "comment initials"),
            date=_optional_date(document.get("date")),
            text=required_text(document.get("text"), "reply text"),
            position=None,
            comment_id=comment_id,
            comment_sha256=comment_sha256,
            status=_optional_text(document.get("status"), "reply status"),
            user_id=_optional_text(document.get("user_id"), "user id"),
            provider_id=_optional_text(document.get("provider_id"), "provider id"),
        )
    comment_id = _parse_comment_id(document.get("comment_id"))
    comment_sha256 = _parse_comment_digest(document.get("comment_sha256"))
    reply_id = _optional_text(document.get("reply_id"), "reply id")
    status = _optional_text(document.get("status"), "status")
    if operation == "delete":
        text = None
        date = None
    else:
        text = _optional_text(document.get("text"), "comment text")
        date = _optional_date(document.get("date"))
        if text is None and date is None and status is None:
            raise CommentRefusal("an update request requires text or date")
    return CommentRequest(
        source_sha256=source_sha256,
        operation=operation,
        slide_index=slide_index,
        slide_part=slide_part,
        author=None,
        initials=None,
        date=date,
        text=text,
        position=None,
        comment_id=comment_id,
        comment_sha256=comment_sha256,
        reply_id=reply_id,
        status=status,
    )


def _parse_slide_target(document: Mapping[str, Any]) -> tuple[int | None, str | None]:
    slide_index = document.get("slide_index")
    slide_part = document.get("slide_part")
    if slide_index is None and slide_part is None:
        raise CommentRefusal("a request requires slide_index or slide_part")
    if slide_index is not None and (
        not isinstance(slide_index, int) or isinstance(slide_index, bool)
    ):
        raise CommentRefusal("slide_index must be an integer")
    if slide_part is not None:
        if not isinstance(slide_part, str) or not slide_part:
            raise CommentRefusal("slide_part must be a package part name")
        slide_part = part_name(slide_part)
    return slide_index, slide_part


def _parse_comment_id(value: Any) -> int | str:
    if isinstance(value, bool):
        raise CommentRefusal("comment_id cannot be a boolean")
    if isinstance(value, int):
        if value < 0:
            raise CommentRefusal("comment_id must be non-negative")
        return value
    if isinstance(value, str):
        val = value.strip()
        if not val:
            raise CommentRefusal("comment_id cannot be empty")
        return val
    raise CommentRefusal("comment_id must be an integer or non-empty string")


def _parse_comment_digest(value: Any) -> str:
    if not isinstance(value, str) or SHA256_DIGEST.match(value) is None:
        raise CommentRefusal("comment_sha256 must be the comment's lowercase sha256")
    return value


def _optional_text(value: Any, label: str) -> str | None:
    return None if value is None else required_text(value, label)


def _optional_date(value: Any) -> str | None:
    return None if value is None else required_comment_date(value)


def ensure_publishable_paths(source: Path, destination: Path) -> None:
    """Refuse a source/destination pair that cannot be published safely.

    The Python facade save overwrites by design; the CLI mutation surface does
    not, because a mistyped destination would silently destroy a deck.
    """
    if not source.is_file():
        raise CommentRefusal(f"source deck {source} does not exist")
    if destination.is_symlink():
        raise CommentRefusal(f"destination {destination} is a symbolic link")
    if destination.resolve() == source.resolve():
        raise CommentRefusal(f"destination {destination} is the source deck")
    if destination.exists():
        raise CommentRefusal(f"destination {destination} already exists")
    if not destination.parent.is_dir():
        raise CommentRefusal(
            f"destination directory {destination.parent} does not exist"
        )


def package_diff(source: Path, output: Path) -> dict[str, list[str]]:
    """Compare two packages part by part, by raw member bytes."""
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
        before_members = {name: before.read(name) for name in before.namelist()}
        after_members = {name: after.read(name) for name in after.namelist()}
    return {
        "changed": sorted(
            name
            for name, payload in before_members.items()
            if name in after_members and after_members[name] != payload
        ),
        "added": sorted(set(after_members) - set(before_members)),
        "removed": sorted(set(before_members) - set(after_members)),
        "identical": sorted(
            name
            for name, payload in before_members.items()
            if after_members.get(name) == payload
        ),
    }


def published_comment_sha256(
    path: Path, comments_part: str | None, comment_id: int | str
) -> str | None:
    """Digest one comment as the published package declares it."""
    if comments_part is None:
        return None
    with zipfile.ZipFile(path) as package:
        try:
            payload = package.read(comments_part)
        except KeyError:
            return None
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return None
    # Check if modern
    for cm in root.findall(f".//{{{P_NS}}}cm"):
        if cm.get("idx") == str(comment_id) or (
            int(cm.get("idx") or -1) == comment_id
            if isinstance(comment_id, int)
            else False
        ):
            return element_content_sha256(cm)
    for cm in root.findall(".//*"):
        if cm.tag.endswith("}cm") and cm.get("id") == str(comment_id):
            return element_content_sha256(cm)
    return None


def _resolve_slide(presentation: Any, request: CommentRequest) -> Any:
    slides = list(presentation.slides)
    if request.slide_part is not None:
        matches = [
            slide for slide in slides if part_name(slide.partname) == request.slide_part
        ]
        if not matches:
            raise CommentRefusal(
                f"the presentation has no slide part {request.slide_part}"
            )
        if len(matches) > 1:
            raise CommentRefusal(
                f"{request.slide_part} addresses more than one slide; address the "
                "slide by index"
            )
        if (
            request.slide_index is not None
            and slides.index(matches[0]) != request.slide_index
        ):
            raise CommentRefusal("slide_index and slide_part address different slides")
        return matches[0]
    index = request.slide_index
    if index is None or index < 0 or index >= len(slides):
        raise CommentRefusal(f"slide_index must address one of {len(slides)} slides")
    return slides[index]


def _resolve_reply(comment: Any, reply_id: str) -> Any:
    for reply in getattr(comment, "replies", ()):
        if reply.reply_id == reply_id:
            return reply
    raise CommentRefusal(
        f"comment {comment.comment_id} has no reply with id {reply_id}"
    )


def _resolve_comment(comments: Any, request: CommentRequest) -> Any:
    label = comments.comments_part or comments.slide_part
    for comment in comments:
        if str(comment.comment_id) != str(request.comment_id):
            continue
        if (
            request.comment_sha256 is not None
            and comment.content_sha256 != request.comment_sha256
        ):
            raise CommentRefusal(
                f"comment {request.comment_id} of {label} changed since it was "
                "discovered; re-discover the target before editing it"
            )
        return comment
    raise CommentRefusal(f"{label} has no comment id {request.comment_id}")


def apply_comment_request(
    source: str | Path,
    destination: str | Path,
    request: CommentRequest,
) -> dict[str, Any]:
    """Apply one validated comment request through the native save pipeline.

    The source is re-digested after staging, so a deck that changes underneath
    the request refuses without publishing anything.
    """
    from .presentation import Presentation

    source_path = Path(source).expanduser()
    output_path = Path(destination).expanduser()
    ensure_publishable_paths(source_path, output_path)
    source_sha256 = sha256_file(source_path)
    if source_sha256 != request.source_sha256:
        raise CommentRefusal(
            f"source mismatch: {source_path} digests {source_sha256} but the "
            f"request expects {request.source_sha256}"
        )
    presentation = Presentation(source_path)
    slide = _resolve_slide(presentation, request)
    comments = slide.comments
    if request.operation == "add":
        comment = comments.add(
            request.text,
            request.author,
            initials=request.initials,
            date=request.date,
            position=request.position,
            modern=request.modern,
            status=request.status or "active",
            user_id=request.user_id,
            provider_id=request.provider_id or "AD",
        )
    elif request.operation == "reply":
        parent = _resolve_comment(comments, request)
        parent.add_reply(
            request.text,
            request.author,
            initials=request.initials,
            date=request.date,
            status=request.status or "active",
            user_id=request.user_id,
            provider_id=request.provider_id or "AD",
        )
        comment = parent
    else:
        comment = _resolve_comment(comments, request)
        if request.operation == "update":
            target_entity = (
                _resolve_reply(comment, request.reply_id)
                if request.reply_id is not None
                else comment
            )
            if request.text is not None:
                target_entity.text = request.text
            if request.date is not None:
                target_entity.date = request.date
            if request.status is not None:
                target_entity.status = request.status
        else:
            if request.reply_id is not None:
                reply = _resolve_reply(comment, request.reply_id)
                reply.remove()
            else:
                comments.remove(comment)
    if sha256_file(source_path) != source_sha256:
        raise CommentRefusal(
            f"{source_path} changed while the comment was staged; nothing was published"
        )
    presentation.save(output_path)
    diff = package_diff(source_path, output_path)
    return {
        "operation": "comment",
        "request_operation": request.operation,
        "source": str(source_path),
        "output": str(output_path),
        "source_sha256": source_sha256,
        "output_sha256": sha256_file(output_path),
        "slide_index": list(presentation.slides).index(slide),
        "slide_part": part_name(slide.partname),
        "comments_part": comments.comments_part,
        "comment_id": comment.comment_id,
        "comment_author": comment.author,
        "comment_sha256": published_comment_sha256(
            output_path, comments.comments_part, comment.comment_id
        ),
        "changed_parts": diff["changed"],
        "added_parts": diff["added"],
        "removed_parts": diff["removed"],
        "identical_parts": diff["identical"],
    }


def handle_comment_targets_command(args: argparse.Namespace) -> int:
    """Run ``comment-targets`` and print the discovery receipt."""
    if args.source is None:
        print("comment-targets requires --source", file=sys.stderr)
        return 2
    try:
        receipt = discover_comment_targets(args.source, slides=args.slides)
    except CommentRefusal as exc:
        print(f"comment-targets refused: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"comment-targets failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2))
    return 0


def handle_comment_command(args: argparse.Namespace) -> int:
    """Run ``comment`` for one validated request and print the receipt."""
    missing = [
        f"--{name}"
        for name in ("request", "input", "output")
        if getattr(args, name) is None
    ]
    if missing:
        print(f"comment requires {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        request = parse_comment_request(load_comment_request(args.request))
        receipt = apply_comment_request(args.input, args.output, request)
    except CommentRefusal as exc:
        print(f"comment refused: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"comment failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def register_comment_commands(subparsers: Any) -> None:
    """Register the ``comment-targets`` and ``comment`` subcommands."""
    targets = subparsers.add_parser(
        "comment-targets",
        help="discover a presentation's source-bound legacy comments",
        description=(
            "Report the source digest, presentation-scoped authors, and every "
            "slide's legacy comments part, relationship, and comments. Nothing "
            "is written."
        ),
    )
    targets.add_argument("--source", type=Path, help="source presentation to read")
    targets.add_argument(
        "--slide",
        dest="slides",
        action="append",
        type=int,
        help="restrict discovery to one slide index; repeatable",
    )
    targets.set_defaults(handler=handle_comment_targets_command)

    comment = subparsers.add_parser(
        "comment",
        help="add, update, or delete one legacy comment",
        description=(
            "Apply one source-bound comment request through the native save "
            "pipeline. The request must state the source digest reported by "
            "comment-targets."
        ),
    )
    comment.add_argument("--request", type=Path, help="comment request JSON file")
    comment.add_argument("--input", type=Path, help="source presentation")
    comment.add_argument("--output", type=Path, help="destination presentation")
    comment.set_defaults(handler=handle_comment_command)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wolfppt-comments",
        description="Source-bound legacy comment discovery and authoring.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_comment_commands(subparsers)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CommentRequest",
    "apply_comment_request",
    "ensure_publishable_paths",
    "handle_comment_command",
    "handle_comment_targets_command",
    "load_comment_request",
    "main",
    "package_diff",
    "parse_comment_request",
    "published_comment_sha256",
    "register_comment_commands",
]
