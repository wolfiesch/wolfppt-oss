"""Native binding wrappers split from wolfppt.native."""

from __future__ import annotations

import json
from pathlib import Path

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import (
    NativeImageAddResult,
    NativeImageReplacementResult,
    NativeMovieAddResult,
    NativeOleObjectAddResult,
)


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
) -> NativeMovieAddResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(
        wolfppt_native.add_slide_movie_json(
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
        )
    )
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
