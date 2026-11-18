"""Media, table, and chart shape-add dispatch helpers."""

from __future__ import annotations

import hashlib
import posixpath
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from . import native
from .image_inputs import InMemoryFile, InMemoryImage, StoredMediaSource
from .native_media import MediaCollectionRefusal, part_content_type
from .native_results import NativeAudioAddResult, NativeMovieAddResult
from .package_parts import (
    CONTENT_TYPES_NS,
    PKG_REL_NS,
    copy_open_package_with_replacements,
    rels_part_for_package_part,
    resolve_package_target,
)
from .presentation_tags import parse_xml, serialize_xml
from .table_adds import apply_table_add

ChartAddFn = Callable[..., None]
MediaFrameResult = NativeAudioAddResult | NativeMovieAddResult


def _materialize_stored_media(
    current: Path, step: Path, source: StoredMediaSource, kind: str
) -> Path:
    """Validate the saved asset before writing either a source file or a frame."""
    partname = source.partname.lstrip("/")
    try:
        with ZipFile(current) as package:
            blob = package.read(partname)
            content_type = part_content_type(package, partname)
    except (KeyError, OSError, BadZipFile, ET.ParseError, ValueError) as exc:
        raise MediaCollectionRefusal("stored media source is unavailable") from exc
    if (
        content_type != source.content_type
        or not content_type.startswith(f"{kind}/")
        or hashlib.sha256(blob).hexdigest() != source.sha256
    ):
        raise MediaCollectionRefusal("stored media source has changed")
    return InMemoryFile(blob, posixpath.basename(partname)).materialize(
        step.parent, f"{step.stem}-stored-media"
    )


def _retarget_stored_media_frame(
    current: Path,
    generated: Path,
    step: Path,
    source: StoredMediaSource,
    result: MediaFrameResult,
) -> None:
    """Keep only the native frame/poster delta, reusing the original media part."""
    slide_part = result.slide_part.lstrip("/")
    rels_part = rels_part_for_package_part(slide_part)
    generated_media = result.media_part.lstrip("/")
    source_part = source.partname.lstrip("/")
    file_relationship_id = (
        result.audio_relationship_id
        if isinstance(result, NativeAudioAddResult)
        else result.video_relationship_id
    )
    relationship_ids = {result.media_relationship_id, file_relationship_id}
    with ZipFile(current) as original, ZipFile(generated) as package:
        if generated_media in original.namelist():
            raise MediaCollectionRefusal("native frame did not create a separate media part")
        rels = parse_xml(package.read(rels_part))
        relationships = [
            node
            for node in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
            if node.get("Id") in relationship_ids
        ]
        if len(relationships) != len(relationship_ids):
            raise MediaCollectionRefusal("native media frame relationships are unavailable")
        target = posixpath.relpath(source_part, posixpath.dirname(slide_part))
        for relationship in relationships:
            if (
                relationship.get("TargetMode", "Internal") != "Internal"
                or resolve_package_target(slide_part, relationship.get("Target", ""))
                != generated_media
            ):
                raise MediaCollectionRefusal("native media frame target is unavailable")
            relationship.set("Target", target)

        poster_part = result.poster_part.lstrip("/")
        replacements = {
            slide_part: package.read(slide_part),
            rels_part: serialize_xml(rels),
            poster_part: package.read(poster_part),
        }
        poster_type = part_content_type(package, poster_part)
        if not poster_type:
            raise MediaCollectionRefusal("native media frame poster type is unavailable")
        if part_content_type(original, poster_part) != poster_type:
            types = parse_xml(original.read("[Content_Types].xml"))
            for node in list(types.findall(f"{{{CONTENT_TYPES_NS}}}Override")):
                if node.get("PartName", "").lstrip("/") == poster_part:
                    types.remove(node)
            ET.SubElement(
                types,
                f"{{{CONTENT_TYPES_NS}}}Override",
                PartName="/" + poster_part,
                ContentType=poster_type,
            )
            replacements["[Content_Types].xml"] = serialize_xml(types)
        # Copy the original rather than the generated package: its new media
        # payload and content-type declaration never enter the final package.
        # Every untouched original member retains its raw ZIP entry bytes.
        copy_open_package_with_replacements(original, step, replacements)


def _write_media_frame(
    current: Path,
    step: Path,
    source: StoredMediaSource | None,
    add_frame: Callable[[Path], MediaFrameResult],
) -> None:
    if source is None:
        add_frame(step)
        return
    with TemporaryDirectory(prefix=f".{step.stem}-media-", dir=step.parent) as directory:
        generated = Path(directory) / "frame.pptx"
        result = add_frame(generated)
        _retarget_stored_media_frame(current, generated, step, source, result)


def apply_media_or_chart_shape_add(
    add_kind: str,
    args: tuple[Any, ...],
    current: Path,
    step: Path,
    apply_chart_add: ChartAddFn,
) -> bool:
    if add_kind == "picture":
        slide_index, image_path, x_emu, y_emu, cx_emu, cy_emu = args
        if isinstance(image_path, InMemoryImage):
            image_path = image_path.materialize(step.parent, f"{step.stem}-image")
        native.add_image(
            current,
            step,
            slide_index,
            image_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        return True
    if add_kind == "movie":
        (
            slide_index,
            movie_path,
            poster_frame_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type,
            *minimum_timing_id_args,
        ) = args
        if len(minimum_timing_id_args) > 1:
            raise ValueError("movie add received multiple minimum timing IDs")
        minimum_timing_id = minimum_timing_id_args[0] if minimum_timing_id_args else None
        stored_source = movie_path if isinstance(movie_path, StoredMediaSource) else None
        if stored_source is not None:
            movie_path = _materialize_stored_media(current, step, stored_source, "video")
            mime_type = stored_source.content_type
        elif isinstance(movie_path, InMemoryFile):
            movie_path = movie_path.materialize(step.parent)
        if isinstance(poster_frame_path, InMemoryImage):
            poster_frame_path = poster_frame_path.materialize(
                step.parent,
                f"{step.stem}-poster",
            )
        _write_media_frame(
            current,
            step,
            stored_source,
            lambda output: native.add_movie(
                current,
                output,
                slide_index,
                movie_path,
                poster_frame_path,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                mime_type,
                minimum_timing_id=minimum_timing_id,
            ),
        )
        return True
    if add_kind == "audio":
        (
            slide_index,
            audio_path,
            poster_frame_path,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            mime_type,
            *minimum_timing_id_args,
        ) = args
        if len(minimum_timing_id_args) > 1:
            raise ValueError("audio add received multiple minimum timing IDs")
        minimum_timing_id = minimum_timing_id_args[0] if minimum_timing_id_args else None
        stored_source = audio_path if isinstance(audio_path, StoredMediaSource) else None
        if stored_source is not None:
            audio_path = _materialize_stored_media(current, step, stored_source, "audio")
            mime_type = stored_source.content_type
        elif isinstance(audio_path, InMemoryFile):
            from .native_media import MEDIA_EXTENSIONS, AudioControlRefusal

            extension = MEDIA_EXTENSIONS.get(mime_type)
            if extension is None or not mime_type.startswith("audio/"):
                raise AudioControlRefusal("stream audio requires a supported audio MIME type")
            audio_path = InMemoryFile(audio_path.blob, f"audio.{extension}").materialize(
                step.parent
            )
        if isinstance(poster_frame_path, InMemoryImage):
            poster_frame_path = poster_frame_path.materialize(
                step.parent,
                f"{step.stem}-poster",
            )
        _write_media_frame(
            current,
            step,
            stored_source,
            lambda output: native.add_audio(
                current,
                output,
                slide_index,
                audio_path,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                mime_type,
                minimum_timing_id=minimum_timing_id,
                poster_frame_path=poster_frame_path,
            ),
        )
        return True
    if add_kind == "ole_object":
        (
            slide_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        ) = args
        if isinstance(object_path, InMemoryFile):
            object_path = object_path.materialize(step.parent)
        if isinstance(icon_path, InMemoryImage):
            icon_path = icon_path.materialize(step.parent, f"{step.stem}-icon")
        native.add_ole_object(
            current,
            step,
            slide_index,
            object_path,
            prog_id,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            icon_path,
            icon_cx_emu,
            icon_cy_emu,
        )
        return True
    if add_kind == "table":
        (
            slide_index,
            _table_index,
            rows,
            cols,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            *cell_texts,
        ) = args
        apply_table_add(
            current,
            step,
            slide_index,
            rows,
            cols,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            cell_texts[0] if cell_texts else None,
        )
        return True
    if add_kind == "chart":
        slide_index, chart_type, chart_data, x_emu, y_emu, cx_emu, cy_emu = args
        apply_chart_add(
            current,
            step,
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        )
        return True
    if add_kind == "group_chart":
        (
            slide_index,
            group_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        apply_chart_add(
            current,
            step,
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index=group_index,
        )
        return True
    if add_kind == "nested_group_chart":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        apply_chart_add(
            current,
            step,
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index=group_index,
            nested_group_child_index=nested_group_child_index,
        )
        return True
    if add_kind == "deeper_nested_group_chart":
        (
            slide_index,
            group_index,
            nested_group_child_index,
            deeper_group_child_index,
            _child_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
        ) = args
        apply_chart_add(
            current,
            step,
            slide_index,
            chart_type,
            chart_data,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            group_index=group_index,
            nested_group_child_index=nested_group_child_index,
            deeper_group_child_index=deeper_group_child_index,
        )
        return True
    return False
