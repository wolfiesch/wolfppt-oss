"""Native binding wrappers split from wolfppt.native.

The module also owns the pure-package side of embedded audio and video:
:func:`inspect_embedded_media` lists every media part the slides reference and
:func:`media_replacement_parts` swaps one part's bytes.  A replacement touches
only the media part, the relationships that target it and the content types,
so slide XML -- including every timing and trigger node -- keeps its bytes.

Saved-package audio workflow::

    from wolfppt.native_media import add_linked_audio, audio_rewind, audio_start_mode

    audio = add_linked_audio(deck, 0, "https://example.invalid/clip.wav",
                             0, 0, 914400, 914400, poster_frame=png_bytes)
    audio_rewind(deck, 0, audio.shape_id, enabled=True)
    audio_start_mode(deck, 0, audio.shape_id, mode="in_click_sequence")
    deck.save("audio.pptx")

:func:`linked_audio` reads typed external targets without fetching;
:func:`replace_linked_audio` retargets one owning shape. Save pending facade
edits before these operations and reacquire shapes after their package reload.
Stream audio insertion uses its declared supported MIME extension. Playback
declarations survive save/reopen; static rendering paints posters, not sound.

Named audio/video playback presets::

    from wolfppt.enum.shapes import PP_MEDIA_START_MODE, PP_MEDIA_VOLUME
    from wolfppt.native_media import media_start_mode

    media_start_mode(deck, 0, video_id, mode=PP_MEDIA_START_MODE.IN_CLICK_SEQUENCE)
    # Reacquire facade shapes after a saved-package operation.
    video = next(s for s in deck.slides[0].shapes if s.shape_id == video_id)
    video.media_format.volume_preset = PP_MEDIA_VOLUME.LOW
    deck.save("video.pptx")

Start-mode edits require a saved deck with no pending facade edits. Named
volume presets reuse numeric volume and leave the separate mute control intact.
"""

from __future__ import annotations

import errno
import hashlib
import json
import posixpath
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import (
    NativeAudioAddResult,
    NativeImageAddResult,
    NativeImageReplacementResult,
    NativeMovieAddResult,
    NativeOleObjectAddResult,
)


def _raise_if_media_missing(
    exc: RuntimeError, sources: tuple[tuple[str, str | Path | None], ...]
) -> None:
    for role, path in sources:
        if path is not None and not Path(path).is_file():
            raise FileNotFoundError(errno.ENOENT, f"{role} file not found", str(path)) from exc


def replace_image(
    input_path: str | Path,
    output_path: str | Path,
    relationship_id: str,
    image_path: str | Path,
    slide_index: int | None = None,
) -> NativeImageReplacementResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    if slide_index is None:
        payload = json.loads(
            wolfppt_native.replace_slide_image_json(
                str(input_path),
                str(output_path),
                relationship_id,
                str(image_path),
            )
        )
    else:
        payload = json.loads(
            wolfppt_native.replace_slide_image_at_index_json(
                str(input_path),
                str(output_path),
                slide_index,
                relationship_id,
                str(image_path),
            )
        )
    return NativeImageReplacementResult(
        path=payload["path"],
        relationship_id=payload["relationship_id"],
        replacements=int(payload["replacements"]),
        replaced_parts=list(payload["replaced_parts"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_image(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    image_path: str | Path,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> NativeImageAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_image_json(
            str(input_path),
            str(output_path),
            slide_index,
            str(image_path),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    )
    return NativeImageAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        image_part=payload["image_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_group_image(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    image_path: str | Path,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> NativeImageAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_group_image_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            str(image_path),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    )
    return NativeImageAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        image_part=payload["image_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_nested_group_image(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    image_path: str | Path,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> NativeImageAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_nested_group_image_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            str(image_path),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    )
    return NativeImageAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        image_part=payload["image_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_deeper_nested_group_image(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
    image_path: str | Path,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> NativeImageAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_deeper_nested_group_image_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            str(image_path),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    )
    return NativeImageAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        image_part=payload["image_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_nested_group_image_in_new_group(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    image_path: str | Path,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> NativeImageAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_nested_group_image_in_new_group_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            str(image_path),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
    )
    return NativeImageAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        relationship_id=payload["relationship_id"],
        image_part=payload["image_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_movie(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    movie_path: str | Path,
    poster_frame_path: str | Path | None,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    mime_type: str = "video/unknown",
    minimum_timing_id: int | None = None,
) -> NativeMovieAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    try:
        raw_payload = wolfppt_native.add_slide_movie_json(
            str(input_path),
            str(output_path),
            slide_index,
            str(movie_path),
            None if poster_frame_path is None else str(poster_frame_path),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type,
            minimum_timing_id,
        )
    except RuntimeError as exc:
        _raise_if_media_missing(exc, (("movie", movie_path), ("poster frame", poster_frame_path)))
        raise
    payload = json.loads(raw_payload)
    return NativeMovieAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        media_relationship_id=payload["media_relationship_id"],
        video_relationship_id=payload["video_relationship_id"],
        poster_relationship_id=payload["poster_relationship_id"],
        media_part=payload["media_part"],
        poster_part=payload["poster_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_audio(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    audio_path: str | Path,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    mime_type: str,
    minimum_timing_id: int | None = None,
    poster_frame_path: str | Path | None = None,
) -> NativeAudioAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    try:
        raw_payload = wolfppt_native.add_slide_audio_json(
            str(input_path),
            str(output_path),
            slide_index,
            str(audio_path),
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type,
            minimum_timing_id,
            None if poster_frame_path is None else str(poster_frame_path),
        )
    except RuntimeError as exc:
        _raise_if_media_missing(exc, (("audio", audio_path), ("poster frame", poster_frame_path)))
        raise
    payload = json.loads(raw_payload)
    return NativeAudioAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        media_relationship_id=payload["media_relationship_id"],
        audio_relationship_id=payload["audio_relationship_id"],
        poster_relationship_id=payload["poster_relationship_id"],
        media_part=payload["media_part"],
        poster_part=payload["poster_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def set_media_playback(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    shape_id: int,
    loop_playback: bool,
    play_across_slides: bool,
    volume: int,
    auto_play: bool,
    controls: dict[str, Any] | None = None,
) -> None:
    if not 0 <= volume <= 100:
        raise ValueError("media volume must be between 0 and 100")
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    rewind_part = _saved_audio_rewind_part(input_path, slide_index, shape_id)

    try:
        wolfppt_native.set_slide_media_playback_json(
            str(input_path),
            str(output_path),
            slide_index,
            shape_id,
            loop_playback,
            play_across_slides,
            volume,
            auto_play,
            None if controls is None else json.dumps(controls, allow_nan=False),
        )
    except RuntimeError as exc:
        if "MediaControlRefusalError" in str(exc):
            from .shape_picture_inspection import MediaControlRefusalError

            raise MediaControlRefusalError(str(exc)) from exc
        raise
    if rewind_part is not None:
        _restore_audio_rewind(output_path, rewind_part, shape_id)


def add_ole_object(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    object_path: str | Path,
    prog_id: str,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    icon_path: str | Path | None,
    icon_cx_emu: int,
    icon_cy_emu: int,
) -> NativeOleObjectAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_ole_object_json(
            str(input_path),
            str(output_path),
            slide_index,
            str(object_path),
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            None if icon_path is None else str(icon_path),
            icon_cx_emu,
            icon_cy_emu,
        )
    )
    return NativeOleObjectAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        ole_relationship_id=payload["ole_relationship_id"],
        icon_relationship_id=payload["icon_relationship_id"],
        ole_part=payload["ole_part"],
        icon_part=payload["icon_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_group_ole_object(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    object_path: str | Path,
    prog_id: str,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    icon_path: str | Path | None,
    icon_cx_emu: int,
    icon_cy_emu: int,
) -> NativeOleObjectAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_group_ole_object_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            str(object_path),
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            None if icon_path is None else str(icon_path),
            icon_cx_emu,
            icon_cy_emu,
        )
    )
    return NativeOleObjectAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        ole_relationship_id=payload["ole_relationship_id"],
        icon_relationship_id=payload["icon_relationship_id"],
        ole_part=payload["ole_part"],
        icon_part=payload["icon_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_nested_group_ole_object(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    object_path: str | Path,
    prog_id: str,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    icon_path: str | Path | None,
    icon_cx_emu: int,
    icon_cy_emu: int,
) -> NativeOleObjectAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_nested_group_ole_object_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            str(object_path),
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            None if icon_path is None else str(icon_path),
            icon_cx_emu,
            icon_cy_emu,
        )
    )
    return NativeOleObjectAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        ole_relationship_id=payload["ole_relationship_id"],
        icon_relationship_id=payload["icon_relationship_id"],
        ole_part=payload["ole_part"],
        icon_part=payload["icon_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_deeper_nested_group_ole_object(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    nested_group_child_index: int,
    deeper_group_child_index: int,
    object_path: str | Path,
    prog_id: str,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    icon_path: str | Path | None,
    icon_cx_emu: int,
    icon_cy_emu: int,
) -> NativeOleObjectAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_deeper_nested_group_ole_object_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            str(object_path),
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            None if icon_path is None else str(icon_path),
            icon_cx_emu,
            icon_cy_emu,
        )
    )
    return NativeOleObjectAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        ole_relationship_id=payload["ole_relationship_id"],
        icon_relationship_id=payload["icon_relationship_id"],
        ole_part=payload["ole_part"],
        icon_part=payload["icon_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


def add_nested_group_ole_object_in_new_group(
    input_path: str | Path,
    output_path: str | Path,
    slide_index: int,
    group_index: int,
    object_path: str | Path,
    prog_id: str,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    icon_path: str | Path | None,
    icon_cx_emu: int,
    icon_cy_emu: int,
) -> NativeOleObjectAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_nested_group_ole_object_in_new_group_json(
            str(input_path),
            str(output_path),
            slide_index,
            group_index,
            str(object_path),
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            None if icon_path is None else str(icon_path),
            icon_cx_emu,
            icon_cy_emu,
        )
    )
    return NativeOleObjectAddResult(
        path=payload["path"],
        slide_index=int(payload["slide_index"]),
        slide_part=payload["slide_part"],
        ole_relationship_id=payload["ole_relationship_id"],
        icon_relationship_id=payload["icon_relationship_id"],
        ole_part=payload["ole_part"],
        icon_part=payload["icon_part"],
        shape_id=int(payload["shape_id"]),
        part_count=int(payload["part_count"]),
        has_vba=bool(payload["has_vba"]),
    )


# -- embedded audio and video ---------------------------------------------

_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_MEDIA_REL_TYPE = "http://schemas.microsoft.com/office/2007/relationships/media"
_RELATIONSHIP_NAMESPACES = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "http://purl.oclc.org/ooxml/officeDocument/relationships",
)
_SHAPE_NV_TAGS = ("nvSpPr", "nvPicPr", "nvGrpSpPr", "nvCxnSpPr", "nvGraphicFramePr")
_VIDEO_FILE_TAGS = frozenset(("videoFile", "quickTimeFile"))
_AUDIO_FILE_TAGS = frozenset(("audioFile", "wavAudioFile", "audioCd", "snd"))

#: The media formats a replacement may declare, by content type.  Several
#: aliases name one format; the first content type listed for an extension is
#: the one a path-inferred replacement declares.
MEDIA_EXTENSIONS: Mapping[str, str] = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-ms-wmv": "wmv",
    "video/x-msvideo": "avi",
    "video/avi": "avi",
    "video/msvideo": "avi",
    "video/mpeg": "mpg",
    "video/x-ms-asf": "asf",
    "video/x-m4v": "m4v",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/x-ms-wma": "wma",
    "audio/x-aiff": "aiff",
    "audio/midi": "mid",
}
_CONTENT_TYPE_BY_EXTENSION: dict[str, str] = {}
for _content_type, _extension in MEDIA_EXTENSIONS.items():
    _CONTENT_TYPE_BY_EXTENSION.setdefault(_extension, _content_type)
_CONTENT_TYPE_BY_EXTENSION.update({"mpeg": "video/mpeg", "aif": "audio/x-aiff"})


class MediaCollectionRefusal(ValueError):
    """A reusable media asset cannot be added, removed or placed safely."""


class MediaReplacementRefusal(ValueError):
    """A media replacement cannot be applied without breaking the package."""


@dataclass(frozen=True)
class MediaReference:
    """One slide object (or slide transition sound) that plays a media part."""

    slide_index: int
    slide_part: str
    #: The ``p:cNvPr/@id`` of the playing shape; ``None`` for a transition sound.
    shape_id: int | None
    shape_name: str
    #: The slide relationships that target the media part from this object.
    relationship_ids: tuple[str, ...]


@dataclass(frozen=True)
class EmbeddedMedia:
    """One embedded audio or video part and every slide object that plays it."""

    partname: str
    kind: str
    content_type: str
    size: int
    sha256: str
    references: tuple[MediaReference, ...]


def media_content_type_for_path(path: str | Path) -> str:
    """Return the media content type a file extension names."""
    extension = Path(path).suffix.lower().lstrip(".")
    content_type = _CONTENT_TYPE_BY_EXTENSION.get(extension)
    if content_type is None:
        raise MediaReplacementRefusal(
            f"cannot infer a media content type from extension {extension!r}; pass content_type"
        )
    return content_type


def _rels_name(part: str) -> str:
    return posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")


def _owner_of_rels(rels_name: str) -> str:
    if rels_name == "_rels/.rels":
        return ""
    directory, name = posixpath.split(rels_name)
    return posixpath.join(posixpath.dirname(directory), name[: -len(".rels")])


def _resolve(owner: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(owner), target))


def _content_types(package: Any) -> tuple[dict[str, str], dict[str, str]]:
    root = ET.fromstring(package.read("[Content_Types].xml"))
    defaults = {
        node.get("Extension", "").lower(): node.get("ContentType", "")
        for node in root.findall(f"{{{_CT_NS}}}Default")
    }
    overrides = {
        node.get("PartName", "").lstrip("/"): node.get("ContentType", "")
        for node in root.findall(f"{{{_CT_NS}}}Override")
    }
    return defaults, overrides


def part_content_type(package: Any, part: str) -> str:
    """Return the declared content type of one package part."""
    defaults, overrides = _content_types(package)
    if part in overrides:
        return overrides[part]
    return defaults.get(part.rsplit(".", 1)[-1].lower(), "")


def _media_kind(relationship_type: str, content_type: str, tags: set[str]) -> str | None:
    namespace, _, local = relationship_type.rpartition("/")
    if local in ("video", "audio") and namespace in _RELATIONSHIP_NAMESPACES:
        return local
    if relationship_type != _MEDIA_REL_TYPE:
        return None
    if tags & _VIDEO_FILE_TAGS:
        return "video"
    if tags & _AUDIO_FILE_TAGS:
        return "audio"
    major = content_type.split("/", 1)[0]
    return major if major in ("video", "audio") else None


def _local(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _relationship_attribute_ids(element: ET.Element) -> set[str]:
    return {
        value
        for name, value in element.attrib.items()
        if name.startswith("{") and name[1:].split("}", 1)[0] in _RELATIONSHIP_NAMESPACES
    }


def _shape_identity(element: ET.Element) -> tuple[int | None, str]:
    for child in element:
        if _local(child.tag) in _SHAPE_NV_TAGS:
            for grandchild in child:
                if _local(grandchild.tag) == "cNvPr":
                    raw = grandchild.get("id", "")
                    name = grandchild.get("name", "")
                    return (int(raw) if raw.isdigit() else None), name
    return None, ""


def _media_users(
    root: ET.Element, relationship_ids: set[str]
) -> dict[str, tuple[ET.Element | None, set[str]]]:
    """Map each media relationship id to its innermost owning shape and tags."""
    users: dict[str, tuple[ET.Element | None, set[str]]] = {}

    def visit(element: ET.Element, shape: ET.Element | None) -> None:
        if any(_local(child.tag) in _SHAPE_NV_TAGS for child in element):
            shape = element
        for rel_id in _relationship_attribute_ids(element) & relationship_ids:
            users.setdefault(rel_id, (shape, set()))[1].add(_local(element.tag))
        for child in element:
            visit(child, shape)

    visit(root, None)
    return users


def inspect_embedded_media(package: Any, slide_parts: Iterable[str]) -> tuple[EmbeddedMedia, ...]:
    """List embedded audio/video, slide references first, then retained unplaced assets.

    A shared part is listed once with one reference per playing object.
    Linked (external) media is excluded; unplaced assets have no references.
    """
    names = set(package.namelist())
    references: dict[str, list[MediaReference]] = {}
    kinds: dict[str, str] = {}
    for slide_index, slide_part in enumerate(slide_parts):
        rels_name = _rels_name(slide_part)
        if rels_name not in names:
            continue
        rels = ET.fromstring(package.read(rels_name))
        targets: dict[str, tuple[str, str]] = {}
        for relationship in rels.findall(f"{{{_PKG_REL_NS}}}Relationship"):
            if relationship.get("TargetMode", "Internal") != "Internal":
                continue
            rel_type = relationship.get("Type", "")
            if not rel_type.endswith(("/video", "/audio", "/media")):
                continue
            target = _resolve(slide_part, relationship.get("Target", ""))
            if target in names:
                targets[relationship.get("Id", "")] = (target, rel_type)
        if not targets:
            continue
        users = _media_users(ET.fromstring(package.read(slide_part)), set(targets))
        by_object: dict[tuple[str, int | None], tuple[str, list[str], set[str]]] = {}
        for rel_id in sorted(targets, key=_rid_key):
            if rel_id not in users:
                continue
            target = targets[rel_id][0]
            shape, tags = users[rel_id]
            shape_id, shape_name = (None, "") if shape is None else _shape_identity(shape)
            entry = by_object.setdefault((target, shape_id), (shape_name, [], set()))
            entry[1].append(rel_id)
            entry[2].update(tags)
        for (target, shape_id), (shape_name, rel_ids, tags) in by_object.items():
            content_type = part_content_type(package, target)
            kind = next(
                (
                    found
                    for rel_id in rel_ids
                    if (found := _media_kind(targets[rel_id][1], content_type, tags)) is not None
                ),
                None,
            )
            if kind is None:
                continue
            kinds.setdefault(target, kind)
            references.setdefault(target, []).append(
                MediaReference(
                    slide_index=slide_index,
                    slide_part=slide_part,
                    shape_id=shape_id,
                    shape_name=shape_name,
                    relationship_ids=tuple(rel_ids),
                )
            )
    # Presentation-level relationships retain assets even without playing shapes.
    collection_rels = "ppt/_rels/presentation.xml.rels"
    if collection_rels in names:
        for rel in ET.fromstring(package.read(collection_rels)):
            rel_type = rel.get("Type", "")
            if rel.get("TargetMode", "Internal") != "Internal":
                continue
            kind = _media_kind(rel_type, "", set())
            target = _resolve("ppt/presentation.xml", rel.get("Target", ""))
            if kind is not None and target in names:
                kinds.setdefault(target, kind)
                references.setdefault(target, [])
    media = []
    for partname, refs in references.items():
        payload = package.read(partname)
        media.append(
            EmbeddedMedia(
                partname=partname,
                kind=kinds[partname],
                content_type=part_content_type(package, partname),
                size=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
                references=tuple(refs),
            )
        )
    return tuple(media)


def _rid_key(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"rId(\d+)", value)
    return (int(match.group(1)) if match else 1 << 62, value)


def media_replacement_parts(
    package: Any,
    media: EmbeddedMedia,
    data: bytes,
    *,
    content_type: str | None = None,
) -> tuple[dict[str, bytes], set[str], str]:
    """Plan the package rewrite that swaps one media part's bytes.

    Returns ``(replacements, removals, partname)``.  A replacement in the
    part's own format keeps the part name; another format moves the bytes to
    a part with that format's extension and retargets every relationship that
    pointed at the old part.  Slide XML is never rewritten, so the playing
    shapes, their timing and trigger nodes, and their poster frames are kept.
    """
    from .presentation_tags import parse_xml, serialize_xml

    if not isinstance(data, bytes):
        raise TypeError("replacement media must be bytes")
    if not data:
        raise MediaReplacementRefusal("replacement media is empty")
    names = set(package.namelist())
    if media.partname not in names:
        raise MediaReplacementRefusal(f"media part {media.partname} no longer exists")
    if hashlib.sha256(package.read(media.partname)).hexdigest() != media.sha256:
        raise MediaReplacementRefusal(f"media part {media.partname} changed since it was listed")
    declared = media.content_type if content_type is None else content_type
    if not isinstance(declared, str) or "/" not in declared:
        raise MediaReplacementRefusal(f"invalid media content type {declared!r}")
    if declared.split("/", 1)[0] != media.kind:
        raise MediaReplacementRefusal(
            f"cannot replace {media.kind} part {media.partname} with {declared}; "
            "the playing shape and its timing nodes are typed by media kind"
        )
    old_extension = media.partname.rsplit(".", 1)[-1].lower()
    if declared == media.content_type:
        extension = old_extension
    else:
        found = MEDIA_EXTENSIONS.get(declared)
        if found is None:
            raise MediaReplacementRefusal(
                f"unsupported media content type {declared!r}; supported: "
                + ", ".join(sorted(MEDIA_EXTENSIONS))
            )
        extension = found
    replacements: dict[str, bytes] = {}
    removals: set[str] = set()
    partname = media.partname
    if extension != old_extension:
        directory, base = posixpath.split(media.partname)
        stem = base.rsplit(".", 1)[0]
        partname = posixpath.join(directory, f"{stem}.{extension}")
        counter = 1
        while partname in names:
            partname = posixpath.join(directory, f"{stem}_{counter}.{extension}")
            counter += 1
        removals.add(media.partname)
        for rels_name in sorted(name for name in names if name.endswith(".rels")):
            owner = _owner_of_rels(rels_name)
            rels = parse_xml(package.read(rels_name))
            changed = False
            for relationship in rels.findall(f"{{{_PKG_REL_NS}}}Relationship"):
                if relationship.get("TargetMode", "Internal") != "Internal":
                    continue
                target = relationship.get("Target", "")
                if _resolve(owner, target) != media.partname:
                    continue
                relationship.set(
                    "Target",
                    "/" + partname
                    if target.startswith("/")
                    else posixpath.relpath(partname, posixpath.dirname(owner) or "."),
                )
                changed = True
            if changed:
                replacements[rels_name] = serialize_xml(rels)
    defaults, _overrides = _content_types(package)
    types_root = parse_xml(package.read("[Content_Types].xml"))
    types_changed = False
    for node in list(types_root.findall(f"{{{_CT_NS}}}Override")):
        if node.get("PartName", "").lstrip("/") in (media.partname, partname):
            types_root.remove(node)
            types_changed = True
    if extension not in defaults:
        ET.SubElement(
            types_root,
            f"{{{_CT_NS}}}Default",
            {"Extension": extension, "ContentType": declared},
        )
        types_changed = True
    elif defaults[extension] != declared:
        ET.SubElement(
            types_root,
            f"{{{_CT_NS}}}Override",
            {"PartName": "/" + partname, "ContentType": declared},
        )
        types_changed = True
    if types_changed:
        replacements["[Content_Types].xml"] = ordered_content_types_xml(types_root)
    replacements[partname] = data
    return replacements, removals, partname


def ordered_content_types_xml(root: ET.Element) -> bytes:
    """Serialize content types with every Default ahead of every Override."""
    from .presentation_tags import serialize_xml

    children = list(root)
    for child in children:
        root.remove(child)
    root.extend(child for child in children if _local(child.tag) == "Default")
    root.extend(child for child in children if _local(child.tag) != "Default")
    return serialize_xml(root)


class PresentationMedia:
    """A handle on one embedded media part of a :class:`Presentation`.

    ``blob`` and ``extract()`` return the embedded part's exact bytes.
    ``replace()`` swaps them in place: the playing shapes, their timing and
    trigger nodes, and their poster frames are kept.  A part is shared by
    every reference, so all of its playing shapes play the replacement.
    """

    def __init__(self, presentation: Any, media: EmbeddedMedia) -> None:
        self._presentation = presentation
        self._media = media

    def __repr__(self) -> str:
        return (
            f"PresentationMedia({self.partname!r}, kind={self.kind!r}, "
            f"content_type={self.content_type!r}, size={self.size})"
        )

    @property
    def partname(self) -> str:
        return self._media.partname

    @property
    def kind(self) -> str:
        return self._media.kind

    @property
    def content_type(self) -> str:
        return self._media.content_type

    @property
    def size(self) -> int:
        return self._media.size

    @property
    def sha256(self) -> str:
        return self._media.sha256

    @property
    def extension(self) -> str:
        return self.partname.rsplit(".", 1)[-1].lower()

    @property
    def references(self) -> tuple[MediaReference, ...]:
        return self._media.references

    @property
    def blob(self) -> bytes:
        """The embedded part's exact bytes."""
        from .package_parts import open_package_source

        with open_package_source(self._presentation._source_path) as package:
            if self.partname not in package.namelist():
                raise MediaReplacementRefusal(f"media part {self.partname} no longer exists")
            payload = package.read(self.partname)
        if hashlib.sha256(payload).hexdigest() != self.sha256:
            raise MediaReplacementRefusal(f"media part {self.partname} changed since it was listed")
        return payload

    def extract(self, destination: Any) -> int:
        """Write the embedded bytes to a path or writable stream; return the size."""
        payload = self.blob
        if callable(getattr(destination, "write", None)):
            destination.write(payload)
        else:
            Path(destination).write_bytes(payload)
        return len(payload)

    @property
    def stream(self) -> Any:
        """A fresh binary stream positioned at the start of the exact asset bytes."""
        from io import BytesIO

        return BytesIO(self.blob)

    def replace(self, media: Any, *, content_type: str | None = None) -> PresentationMedia:
        """Replace the embedded bytes; see :meth:`Presentation.replace_media`."""
        return self._presentation.replace_media(self, media, content_type=content_type)


class MediaCollection:
    """Saved-package audio/video assets, including unplaced retained assets.

    ``add`` accepts bytes, paths or binary streams and deduplicates bytes plus
    content type. ``remove`` deletes unused assets only. Place handles using
    ``slide.shapes.add_audio`` or ``add_movie``. Save pending edits before
    collection operations, and reacquire shapes after collection mutations.
    """

    def __init__(self, presentation: Any, kind: str) -> None:
        self._presentation = presentation
        self._kind = kind

    def _items(self) -> tuple[PresentationMedia, ...]:
        return tuple(item for item in self._presentation.media if item.kind == self._kind)

    def __len__(self) -> int:
        return len(self._items())

    def __iter__(self) -> Any:
        return iter(self._items())

    def __getitem__(self, index: Any) -> Any:
        return self._items()[index]

    def add(self, data: Any, *, content_type: str | None = None) -> PresentationMedia:
        from .image_inputs import collection_add_parts, collection_input

        payload, declared = collection_input(data, content_type, self._kind)
        deck = self._presentation
        with deck._mutation_lock:
            partname = deck._rewrite_package(
                "adding reusable media",
                lambda package: collection_add_parts(package, payload, declared),
            )
            return next(item for item in self._items() if item.partname == partname)

    def remove(self, asset: Any) -> None:
        from .image_inputs import collection_remove_parts

        deck = self._presentation
        with deck._mutation_lock:
            if type(asset) is int:
                asset = self[asset]
            if (
                not isinstance(asset, PresentationMedia)
                or asset._presentation is not deck
                or asset.kind != self._kind
            ):
                raise MediaCollectionRefusal("asset belongs to another collection")
            try:
                deck._rewrite_package(
                    "removing reusable media",
                    lambda package: collection_remove_parts(package, asset._media),
                )
            except MediaReplacementRefusal as exc:
                raise MediaCollectionRefusal(str(exc)) from exc


# Saved-package media operations share one mutation policy. Save pending shape
# edits first; every operation reloads the facade.
_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"


class AudioControlRefusal(ValueError):
    """An audio operation cannot model the input without losing package data."""


class LinkedMediaRefusal(AudioControlRefusal):
    """A linked audio/video operation cannot be applied atomically."""


@dataclass(frozen=True)
class LinkedAudio:
    """An external audio target; inspection never fetches the target."""

    slide_index: int
    shape_id: int
    target: str
    relationship_ids: tuple[str, ...]
    _presentation: Any


@dataclass(frozen=True)
class LinkedVideo:
    """An external video target; inspection never fetches the target."""

    slide_index: int
    shape_id: int
    target: str
    relationship_ids: tuple[str, ...]
    _presentation: Any


def _linked_media_target(target: Any) -> str:
    from urllib.parse import urlsplit

    if not isinstance(target, str) or any(
        c.isspace() or ord(c) < 33 or 127 <= ord(c) <= 159 for c in target
    ):
        raise LinkedMediaRefusal("linked media target must be an absolute URI without whitespace")
    try:
        parsed = urlsplit(target)
    except ValueError as exc:
        raise LinkedMediaRefusal("linked media URI is malformed") from exc
    if parsed.scheme not in {"https", "http", "file"} or not parsed.path:
        raise LinkedMediaRefusal("linked media requires an absolute http, https or file URI")
    if parsed.scheme != "file" and not parsed.hostname:
        raise LinkedMediaRefusal("linked media HTTP URI requires a host")
    if parsed.username is not None or parsed.password is not None:
        raise LinkedMediaRefusal("linked media URI credentials are unsupported")
    if parsed.scheme == "file" and not parsed.path.startswith("/"):
        raise LinkedMediaRefusal("linked media file URI requires an absolute path")
    return target


def _audio_slide(presentation: Any, slide_index: int) -> str:
    try:
        presentation._require_saved_package("editing audio")
    except ValueError as exc:
        raise AudioControlRefusal(str(exc)) from exc
    if type(slide_index) is not int or not 0 <= slide_index < len(presentation.slides):
        raise AudioControlRefusal("audio slide index is out of range")
    return presentation.slides[slide_index].partname


def _audio_shape(root: ET.Element, shape_id: int) -> ET.Element:
    if type(shape_id) is not int or shape_id <= 0:
        raise AudioControlRefusal("audio shape id must be a positive integer")
    shapes = [node for node in root.iter(f"{{{_P_NS}}}pic") if _shape_identity(node)[0] == shape_id]
    if len(shapes) != 1 or shapes[0].find(f".//{{{_A_NS}}}audioFile") is None:
        raise AudioControlRefusal("expected one Transitional audio picture with this shape id")
    return shapes[0]


def linked_audio(presentation: Any, slide_index: int) -> tuple[LinkedAudio, ...]:
    """Read external audio URIs and owning shape IDs without accessing the network."""
    return _linked_media(presentation, slide_index, "audio")


def linked_video(presentation: Any, slide_index: int) -> tuple[LinkedVideo, ...]:
    """Read external video targets without accessing them."""
    return _linked_media(presentation, slide_index, "video")


def _linked_media(presentation: Any, slide_index: int, kind: str) -> tuple:
    from .package_parts import open_package_source
    from .presentation_tags import parse_xml

    with presentation._mutation_lock:
        part = _audio_slide(presentation, slide_index)
        with open_package_source(presentation._source_path) as package:
            relname = _rels_name(part)
            if relname not in package.namelist():
                return ()
            rels = parse_xml(package.read(relname), read_only=True)
            root = parse_xml(package.read(part), read_only=True)
            result = []
            for shape in root.iter(f"{{{_P_NS}}}pic"):
                audio = shape.find(f".//{{{_A_NS}}}{kind}File")
                if audio is None:
                    continue
                ids = {rid for node in shape.iter() for rid in _relationship_attribute_ids(node)}
                external = [
                    rel
                    for rel in rels
                    if rel.get("Id") in ids
                    and rel.get("Type", "") in {_R_NS + "/" + kind, _MEDIA_REL_TYPE}
                    and rel.get("TargetMode") == "External"
                ]
                if not external:
                    continue
                targets = {rel.get("Target", "") for rel in external}
                sid = _shape_identity(shape)[0]
                if len(targets) != 1 or sid is None:
                    raise LinkedMediaRefusal("linked media has ambiguous targets or shape identity")
                result.append(
                    (LinkedAudio if kind == "audio" else LinkedVideo)(
                        slide_index,
                        sid,
                        targets.pop(),
                        tuple(rel.get("Id") for rel in external),
                        presentation,
                    )
                )
            return tuple(result)


def add_linked_audio(
    presentation: Any,
    slide_index: int,
    target: str,
    left: int,
    top: int,
    width: int,
    height: int,
    *,
    poster_frame: bytes,
) -> LinkedAudio:
    """Add externally linked audio with a caller-supplied PNG poster.

    Coordinates are EMU. No audio is downloaded or embedded. The PNG is the
    static visual representation; playback and captions belong to slide-show
    consumers, not static rendering. Save pending facade edits before calling.
    """
    return _add_linked_media(
        presentation,
        slide_index,
        target,
        left,
        top,
        width,
        height,
        poster_frame=poster_frame,
        kind="audio",
    )


def add_linked_video(
    presentation: Any,
    slide_index: int,
    target: str,
    left: int,
    top: int,
    width: int,
    height: int,
    *,
    poster_frame: bytes,
) -> LinkedVideo:
    """Add inert external video metadata with a validated PNG preview."""
    return _add_linked_media(
        presentation,
        slide_index,
        target,
        left,
        top,
        width,
        height,
        poster_frame=poster_frame,
        kind="video",
    )


def _add_linked_media(
    presentation: Any,
    slide_index: int,
    target: str,
    left: int,
    top: int,
    width: int,
    height: int,
    *,
    poster_frame: bytes,
    kind: str,
) -> LinkedAudio | LinkedVideo:
    from .presentation_tags import parse_xml, serialize_xml

    target = _linked_media_target(target)
    if (
        any(type(value) is not int for value in (left, top, width, height))
        or min(width, height) <= 0
    ):
        raise LinkedMediaRefusal("media frame requires integer EMU and positive dimensions")
    if not isinstance(poster_frame, bytes) or not poster_frame.startswith(b"\x89PNG\r\n\x1a\n"):
        raise LinkedMediaRefusal("linked media poster must be PNG bytes")
    # Decode before staging so corrupt images are a named, atomic refusal.
    import io

    from PIL import Image

    try:
        with Image.open(io.BytesIO(poster_frame)) as image:
            image.verify()
    except (OSError, ValueError) as exc:
        raise LinkedMediaRefusal("linked media poster is not a valid PNG") from exc
    with presentation._mutation_lock:
        part = _audio_slide(presentation, slide_index)

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], int]:
            root = parse_xml(package.read(part))
            tree = root.find(f"{{{_P_NS}}}cSld/{{{_P_NS}}}spTree")
            if tree is None:
                raise LinkedMediaRefusal("linked media requires a Transitional slide shape tree")
            shape_id = (
                max((int(n.get("id", "0")) for n in root.iter(f"{{{_P_NS}}}cNvPr")), default=0) + 1
            )
            relname = _rels_name(part)
            rels = (
                parse_xml(package.read(relname))
                if relname in package.namelist()
                else ET.Element(f"{{{_PKG_REL_NS}}}Relationships")
            )
            next_id = (
                max(
                    (
                        _rid_key(r.get("Id", ""))[0]
                        for r in rels
                        if re.fullmatch(r"rId\d+", r.get("Id", ""))
                    ),
                    default=0,
                )
                + 1
            )
            audio_id, media_id, poster_id = (f"rId{next_id + i}" for i in range(3))
            poster_part = f"ppt/media/linked{kind.title()}{shape_id}.png"
            counter = 1
            while poster_part in package.namelist():
                poster_part = f"ppt/media/linked{kind.title()}{shape_id}_{counter}.png"
                counter += 1
            for rid, reltype in ((audio_id, _R_NS + "/" + kind), (media_id, _MEDIA_REL_TYPE)):
                ET.SubElement(
                    rels,
                    f"{{{_PKG_REL_NS}}}Relationship",
                    Id=rid,
                    Type=reltype,
                    Target=target,
                    TargetMode="External",
                )
            ET.SubElement(
                rels,
                f"{{{_PKG_REL_NS}}}Relationship",
                Id=poster_id,
                Type=_R_NS + "/image",
                Target=posixpath.relpath(poster_part, posixpath.dirname(part)),
            )
            # Values interpolated here are validated integers or generated IDs.
            picture = ET.fromstring(
                f'<p:pic xmlns:p="{_P_NS}" xmlns:a="{_A_NS}" '
                f'xmlns:r="{_R_NS}" xmlns:p14="{_P14_NS}">'
                f'<p:nvPicPr><p:cNvPr id="{shape_id}" name="Linked {kind.title()} {shape_id}">'
                '<a:hlinkClick r:id="" action="ppaction://media"/></p:cNvPr>'
                "<p:cNvPicPr/><p:nvPr>"
                f'<a:{kind}File r:link="{audio_id}"/><p:extLst>'
                '<p:ext uri="{DAA4B4D4-6D71-4841-9C94-3DE7FCFB9230}">'
                f'<p14:media r:link="{media_id}"/></p:ext></p:extLst>'
                "</p:nvPr></p:nvPicPr>"
                f'<p:blipFill><a:blip r:embed="{poster_id}"/><a:stretch><a:fillRect/>'
                "</a:stretch></p:blipFill><p:spPr><a:xfrm>"
                f'<a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/>'
                '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
                "</p:spPr></p:pic>"
            )
            tree.append(picture)
            children = _audio_timing_children(root)
            timing_id = _next_audio_timing_id(root)
            children.append(
                ET.fromstring(
                    f'<p:{kind} xmlns:p="{_P_NS}"><p:cMediaNode vol="80000">'
                    f'<p:cTn id="{timing_id}" fill="hold" display="0"><p:stCondLst>'
                    '<p:cond delay="indefinite"/></p:stCondLst></p:cTn>'
                    f'<p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>'
                    f"</p:cMediaNode></p:{kind}>"
                )
            )
            types = parse_xml(package.read("[Content_Types].xml"))
            ET.SubElement(
                types, f"{{{_CT_NS}}}Override", PartName="/" + poster_part, ContentType="image/png"
            )
            return (
                {
                    part: serialize_xml(root),
                    relname: serialize_xml(rels),
                    poster_part: poster_frame,
                    "[Content_Types].xml": ordered_content_types_xml(types),
                },
                set(),
                shape_id,
            )

        shape_id = presentation._rewrite_package(f"adding linked {kind}", plan)
        return next(
            item
            for item in _linked_media(presentation, slide_index, kind)
            if item.shape_id == shape_id
        )


def replace_linked_audio(presentation: Any, audio: LinkedAudio, target: str) -> LinkedAudio:
    """Retarget one linked audio shape; shared relationships are refused."""
    return _replace_linked_media(presentation, audio, target, "audio")


def replace_linked_video(presentation: Any, video: LinkedVideo, target: str) -> LinkedVideo:
    """Retarget one linked video shape; shared relationships are refused."""
    return _replace_linked_media(presentation, video, target, "video")


def _replace_linked_media(
    presentation: Any, audio: LinkedAudio | LinkedVideo, target: str, kind: str
) -> LinkedAudio | LinkedVideo:
    from .presentation_tags import parse_xml, serialize_xml

    target = _linked_media_target(target)
    handle_type = LinkedAudio if kind == "audio" else LinkedVideo
    if not isinstance(audio, handle_type) or audio._presentation is not presentation:
        raise LinkedMediaRefusal(f"expected a {handle_type.__name__} handle from this presentation")
    with presentation._mutation_lock:
        part = _audio_slide(presentation, audio.slide_index)

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            current = _linked_media(presentation, audio.slide_index, kind)
            if audio not in current:
                raise LinkedMediaRefusal("linked media handle is stale or belongs to another deck")
            root = parse_xml(package.read(part))
            shapes = [
                node
                for node in root.iter(f"{{{_P_NS}}}pic")
                if _shape_identity(node)[0] == audio.shape_id
                and node.find(f".//{{{_A_NS}}}{kind}File") is not None
            ]
            if len(shapes) != 1:
                raise LinkedMediaRefusal("expected one linked media picture with this shape id")
            shape = shapes[0]
            ids = set(audio.relationship_ids)
            for other in root.iter():
                if (
                    other.tag
                    in {f"{{{_P_NS}}}{tag}" for tag in ("pic", "sp", "graphicFrame", "cxnSp")}
                    and other is not shape
                    and any(_relationship_attribute_ids(node) & ids for node in other.iter())
                ):
                    raise LinkedMediaRefusal("linked media relationship is shared by another shape")
            relname = _rels_name(part)
            rels = parse_xml(package.read(relname))
            for rel in rels:
                if rel.get("Id") in ids:
                    rel.set("Target", target)
            return {relname: serialize_xml(rels)}, set(), None

        presentation._rewrite_package(f"replacing linked {kind}", plan)
        return next(
            item
            for item in _linked_media(presentation, audio.slide_index, kind)
            if item.shape_id == audio.shape_id
        )


def audio_rewind(
    presentation: Any, slide_index: int, shape_id: int, *, enabled: bool | None = None
) -> bool:
    """Read/set rewind-after-playing (media timing fill=remove, not autoReverse).

    Only an unambiguous existing audio timing node is editable. Native playback
    updates preserve this policy; it is independent of loop and trim controls.
    """
    from .package_parts import open_package_source
    from .presentation_tags import parse_xml, serialize_xml

    if enabled is not None and type(enabled) is not bool:
        raise AudioControlRefusal("audio rewind must be bool")
    with presentation._mutation_lock:
        part = _audio_slide(presentation, slide_index)

        def node(root: ET.Element) -> ET.Element:
            _audio_shape(root, shape_id)
            nodes = [
                media.find(f"{{{_P_NS}}}cTn")
                for media in root.iter(f"{{{_P_NS}}}cMediaNode")
                if media.find(f"{{{_P_NS}}}tgtEl/{{{_P_NS}}}spTgt[@spid='{shape_id}']") is not None
            ]
            if len(nodes) != 1 or nodes[0] is None:
                raise AudioControlRefusal("audio rewind requires one existing media timing node")
            return nodes[0]

        if enabled is None:
            with open_package_source(presentation._source_path) as package:
                return node(parse_xml(package.read(part), read_only=True)).get("fill") == "remove"

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], bool]:
            root = parse_xml(package.read(part))
            node(root).set("fill", "remove" if enabled else "hold")
            return {part: serialize_xml(root)}, set(), enabled

        return presentation._rewrite_package("setting audio rewind", plan)


def _next_audio_timing_id(root: ET.Element) -> int:
    return max((int(n.get("id", "0")) for n in root.iter(f"{{{_P_NS}}}cTn")), default=0) + 1


def _audio_timing_children(root: ET.Element) -> ET.Element:
    roots = [n for n in root.iter(f"{{{_P_NS}}}cTn") if n.get("nodeType") == "tmRoot"]
    if len(roots) > 1:
        raise AudioControlRefusal("multiple timing roots are unsupported")
    if not roots:
        if root.find(f"{{{_P_NS}}}timing") is not None:
            raise AudioControlRefusal("existing timing has no main timing root")
        timing = ET.Element(f"{{{_P_NS}}}timing")
        extension = root.find(f"{{{_P_NS}}}extLst")
        root.insert(list(root).index(extension) if extension is not None else len(root), timing)
        listing = ET.SubElement(timing, f"{{{_P_NS}}}tnLst")
        par = ET.SubElement(listing, f"{{{_P_NS}}}par")
        roots = [
            ET.SubElement(
                par,
                f"{{{_P_NS}}}cTn",
                id=str(_next_audio_timing_id(root)),
                dur="indefinite",
                restart="never",
                nodeType="tmRoot",
            )
        ]
    children = roots[0].find(f"{{{_P_NS}}}childTnLst")
    return children if children is not None else ET.SubElement(roots[0], f"{{{_P_NS}}}childTnLst")


class MediaStartModeRefusal(AudioControlRefusal):
    """A saved audio/video start mode cannot be changed without losing data."""


def media_start_mode(
    presentation: Any, slide_index: int, shape_id: int, *, mode: str | None = None
) -> str:
    """Read/set a saved audio/video start mode, accepting PP_MEDIA_START_MODE.

    Save queued edits first and reacquire facade shapes after assignment.
    Existing custom timing is refused before publishing any package change.
    """
    try:
        return _media_start_mode(presentation, slide_index, shape_id, mode=mode, audio_only=False)
    except AudioControlRefusal as exc:
        raise MediaStartModeRefusal(str(exc)) from exc


def audio_start_mode(
    presentation: Any, slide_index: int, shape_id: int, *, mode: str | None = None
) -> str:
    """Read/set ``on_click``, ``automatically``, or ``in_click_sequence``.

    The latter two emit a real main-sequence playFrom media call; on_click
    removes that call and keeps the picture's media-click action. Custom
    trigger topology is refused instead of silently discarded. Save pending
    facade edits first. Linked audio works without fetching its target.
    """
    return _media_start_mode(presentation, slide_index, shape_id, mode=mode, audio_only=True)


def _media_start_mode(
    presentation: Any,
    slide_index: int,
    shape_id: int,
    *,
    mode: str | None,
    audio_only: bool,
) -> str:
    from .package_parts import open_package_source
    from .presentation_tags import parse_xml, serialize_xml

    def media_shape(root: ET.Element) -> ET.Element:
        if audio_only:
            return _audio_shape(root, shape_id)
        if type(shape_id) is not int or shape_id <= 0:
            raise AudioControlRefusal("media shape id must be a positive integer")
        shapes = [
            node for node in root.iter(f"{{{_P_NS}}}pic") if _shape_identity(node)[0] == shape_id
        ]
        if (
            len(shapes) != 1
            or sum(
                len(shapes[0].findall(f".//{{{_A_NS}}}{tag}")) for tag in ("audioFile", "videoFile")
            )
            != 1
        ):
            raise AudioControlRefusal("expected one Transitional audio/video picture")
        nodes = [
            node
            for node in root.iter(f"{{{_P_NS}}}cMediaNode")
            if node.find(f"{{{_P_NS}}}tgtEl/{{{_P_NS}}}spTgt[@spid='{shape_id}']") is not None
        ]
        if len(nodes) != 1 or nodes[0].find(f"{{{_P_NS}}}cTn") is None:
            raise AudioControlRefusal("start mode requires one existing media timing node")
        return shapes[0]

    if mode is not None and (
        not isinstance(mode, str) or mode not in ("on_click", "automatically", "in_click_sequence")
    ):
        raise AudioControlRefusal("unsupported media start mode")
    with presentation._mutation_lock:
        part = _audio_slide(presentation, slide_index)

        def calls(root: ET.Element) -> list[ET.Element]:
            media_shape(root)
            for media in root.iter(f"{{{_P_NS}}}cMediaNode"):
                if media.find(f"{{{_P_NS}}}tgtEl/{{{_P_NS}}}spTgt[@spid='{shape_id}']") is not None:
                    ctn = media.find(f"{{{_P_NS}}}cTn")
                    if ctn is not None and any(
                        condition.get("evt") is not None
                        or condition.get("delay") != "indefinite"
                        or list(condition)
                        for condition in ctn.iter(f"{{{_P_NS}}}cond")
                    ):
                        raise AudioControlRefusal("custom media start triggers are unsupported")
            found = []
            for ctn in root.iter(f"{{{_P_NS}}}cTn"):
                if ctn.get("presetClass") != "mediacall":
                    continue
                commands = list(ctn.iter(f"{{{_P_NS}}}cmd"))
                if any(
                    t.get("spid") == str(shape_id)
                    for cmd in commands
                    for t in cmd.iter(f"{{{_P_NS}}}spTgt")
                ):
                    if len(commands) != 1 or commands[0].get("cmd") != "playFrom(0.0)":
                        raise AudioControlRefusal("custom media-call commands are unsupported")
                    if ctn.get("nodeType") not in {"clickEffect", "afterEffect", "withEffect"}:
                        raise AudioControlRefusal("custom media-call start timing is unsupported")
                    found.append(ctn)
            if len(found) > 1:
                raise AudioControlRefusal("multiple media start calls are unsupported")
            return found

        if mode is None:
            with open_package_source(presentation._source_path) as package:
                found = calls(parse_xml(package.read(part), read_only=True))
                if not found:
                    return "on_click"
                return (
                    "in_click_sequence"
                    if found[0].get("nodeType") == "clickEffect"
                    else "automatically"
                )

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], str]:
            root = parse_xml(package.read(part))
            found = calls(root)
            parents = {child: parent for parent in root.iter() for child in parent}
            for ctn in found:
                par = parents.get(ctn)
                if par is None or par.tag != f"{{{_P_NS}}}par" or list(par) != [ctn]:
                    raise AudioControlRefusal("media call shares its wrapper with other content")
                removed_ids = {n.get("id") for n in ctn.iter(f"{{{_P_NS}}}cTn")}
                if any(n.get("val") in removed_ids for n in root.iter(f"{{{_P_NS}}}tn")):
                    raise AudioControlRefusal("media call timing is referenced by another effect")
                parents[par].remove(par)
                listing = parents[par]
                while listing.tag == f"{{{_P_NS}}}childTnLst" and not list(listing):
                    owner = parents.get(listing)
                    wrapper = parents.get(owner)
                    if (
                        owner is None
                        or owner.get("nodeType") is not None
                        or wrapper is None
                        or wrapper.tag != f"{{{_P_NS}}}par"
                        or list(wrapper) != [owner]
                        or set(owner.attrib) - {"id", "fill"}
                        or any(
                            child.tag not in {f"{{{_P_NS}}}stCondLst", f"{{{_P_NS}}}childTnLst"}
                            for child in owner
                        )
                        or any(n.get("val") == owner.get("id") for n in root.iter(f"{{{_P_NS}}}tn"))
                    ):
                        break
                    outer = parents.get(wrapper)
                    if outer is None:
                        break
                    outer.remove(wrapper)
                    listing = outer
            shape = media_shape(root)
            hyperlink = shape.find(f"{{{_P_NS}}}nvPicPr/{{{_P_NS}}}cNvPr/{{{_A_NS}}}hlinkClick")
            if hyperlink is None or hyperlink.get("action") != "ppaction://media":
                raise AudioControlRefusal("media has no media-click action")
            if mode != "on_click":
                children = _audio_timing_children(root)
                sequences = [
                    n for n in root.iter(f"{{{_P_NS}}}cTn") if n.get("nodeType") == "mainSeq"
                ]
                if len(sequences) > 1:
                    raise AudioControlRefusal("multiple main sequences are unsupported")
                next_id = _next_audio_timing_id(root)
                if sequences:
                    sequence = sequences[0]
                    if parents.get(sequence) not in list(children):
                        raise AudioControlRefusal("nested main sequences are unsupported")
                    listing = sequence.find(f"{{{_P_NS}}}childTnLst")
                    if listing is None:
                        listing = ET.SubElement(sequence, f"{{{_P_NS}}}childTnLst")
                else:
                    seq = ET.Element(f"{{{_P_NS}}}seq", concurrent="1", nextAc="seek")
                    sequence = ET.SubElement(
                        seq,
                        f"{{{_P_NS}}}cTn",
                        id=str(next_id),
                        dur="indefinite",
                        nodeType="mainSeq",
                    )
                    next_id += 1
                    listing = ET.SubElement(sequence, f"{{{_P_NS}}}childTnLst")
                    for tag, event in (("prevCondLst", "onPrev"), ("nextCondLst", "onNext")):
                        cond = ET.SubElement(
                            ET.SubElement(seq, f"{{{_P_NS}}}{tag}"),
                            f"{{{_P_NS}}}cond",
                            evt=event,
                            delay="0",
                        )
                        ET.SubElement(
                            ET.SubElement(cond, f"{{{_P_NS}}}tgtEl"), f"{{{_P_NS}}}sldTgt"
                        )
                    children.insert(0, seq)
                automatic = mode == "automatically"
                start = (
                    f'<p:cond evt="onBegin" delay="0"><p:tn val="{sequence.get("id")}"/></p:cond>'
                    if automatic
                    else ""
                )
                group = ET.fromstring(
                    f'<p:par xmlns:p="{_P_NS}"><p:cTn id="{next_id}" fill="hold">'
                    f'<p:stCondLst><p:cond delay="indefinite"/>{start}</p:stCondLst>'
                    f'<p:childTnLst><p:par><p:cTn id="{next_id + 1}" fill="hold">'
                    '<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst><p:par>'
                    f'<p:cTn id="{next_id + 2}" presetID="1" '
                    'presetClass="mediacall" presetSubtype="0" '
                    f'fill="hold" nodeType="{"afterEffect" if automatic else "clickEffect"}">'
                    '<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
                    '<p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr>'
                    f'<p:cTn id="{next_id + 3}" dur="1" fill="hold"/><p:tgtEl>'
                    f'<p:spTgt spid="{shape_id}"/></p:tgtEl></p:cBhvr></p:cmd>'
                    "</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>"
                    "</p:childTnLst></p:cTn></p:par>"
                )
                listing.insert(0, group) if automatic else listing.append(group)
            return {part: serialize_xml(root)}, set(), mode

        return presentation._rewrite_package("setting media start mode", plan)


def _saved_audio_rewind_part(input_path: Any, slide_index: int, shape_id: int) -> str | None:
    """Carry the fill policy through the native replacement of a media node."""
    import zipfile

    from .package_parts import open_package_source
    from .presentation_tags import parse_xml

    if not Path(input_path).is_file() or not zipfile.is_zipfile(input_path):
        return None
    with open_package_source(input_path) as package:
        from .slide_metadata import presentation_partname

        main = presentation_partname(input_path)
        rels = ET.fromstring(package.read(_rels_name(main)))
        targets = {
            rel.get("Id"): _resolve(main, rel.get("Target", ""))
            for rel in rels
            if rel.get("Type", "").endswith("/slide")
        }
        presentation = ET.fromstring(package.read(main))
        parts = [
            targets[n.get(f"{{{_R_NS}}}id")]
            for n in presentation.findall(f"{{{_P_NS}}}sldIdLst/{{{_P_NS}}}sldId")
        ]
        if not 0 <= slide_index < len(parts):
            return None
        root = parse_xml(package.read(parts[slide_index]), read_only=True)
        for media in root.iter(f"{{{_P_NS}}}cMediaNode"):
            if media.find(f"{{{_P_NS}}}tgtEl/{{{_P_NS}}}spTgt[@spid='{shape_id}']") is not None:
                ctn = media.find(f"{{{_P_NS}}}cTn")
                if ctn is not None and ctn.get("fill") == "remove":
                    return parts[slide_index]
    return None


def _restore_audio_rewind(output_path: Any, part: str, shape_id: int) -> None:
    import tempfile

    from .package_parts import copy_open_package_with_replacements, open_package_source
    from .presentation_tags import parse_xml, serialize_xml

    with tempfile.TemporaryDirectory(
        prefix="wolfppt-rewind-", dir=Path(output_path).parent
    ) as directory:
        staged = Path(directory) / "deck.pptx"
        with open_package_source(output_path) as package:
            root = parse_xml(package.read(part))
            for media in root.iter(f"{{{_P_NS}}}cMediaNode"):
                if media.find(f"{{{_P_NS}}}tgtEl/{{{_P_NS}}}spTgt[@spid='{shape_id}']") is not None:
                    ctn = media.find(f"{{{_P_NS}}}cTn")
                    if ctn is not None:
                        ctn.set("fill", "remove")
            copy_open_package_with_replacements(package, staged, {part: serialize_xml(root)}, set())
        import os

        os.replace(staged, output_path)
