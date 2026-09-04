"""Media drop-in benchmark edit actions."""

from __future__ import annotations

from hashlib import sha1
from io import BytesIO
from pathlib import Path
from typing import Any

from .benchmark_cases import (
    ADD_MOVIE_EXPECTED_TRANSFORM,
    ADD_OLE_OBJECT_EXPECTED_TRANSFORM,
    ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM,
    ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM,
)
from .benchmark_dropin_common_actions import _shape_at, _shape_collection_at
from .presentation import Presentation as WolfPresentation
from .shape_core_facade import Shape

TOP_LEVEL_PICTURE_FIXTURES = (
    "text_basic/title_body_bullets",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)
PICTURE_REPLACE_FIXTURES = (
    "media/png_picture",
    "workloads/mixed_real_world_deck",
)
TOP_LEVEL_MEDIA_FIXTURES = TOP_LEVEL_PICTURE_FIXTURES
PICTURE_IMAGE_INSPECTION_FIXTURES = (
    "media/png_picture",
    "workloads/mixed_real_world_deck",
    "workloads/customer_success_review_pack",
)
GROUP_PICTURE_TARGETS = {
    "shapes/grouped_shapes": (0, 0),
    "workloads/management_reporting_deck": (2, 1),
    "workloads/customer_success_review_pack": (4, 1),
}
GROUP_OLE_OBJECT_TARGETS = GROUP_PICTURE_TARGETS


def _dropin_group_shape(
    fixture_id: str,
    prs: Any,
    operation: str,
    targets: dict[str, tuple[int, int]],
) -> Any:
    if fixture_id not in targets:
        raise RuntimeError(
            f"drop-in {operation} benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = targets[fixture_id]
    if isinstance(prs, WolfPresentation):
        return _shape_at(prs, slide_index, group_index)
    return prs.slides[slide_index].shapes[group_index]


def _first_picture_shape(prs: Any) -> Any:
    slide = prs.slides[0]
    shell_shape = _first_shell_picture_shape(slide)
    if shell_shape is not None:
        return shell_shape
    for shape in slide.shapes:
        if getattr(shape, "has_picture", False):
            return shape
        try:
            shape.image
        except AttributeError:
            continue
        return shape
    raise RuntimeError("fixture does not contain a replaceable picture")


def _first_shell_picture_shape(slide: Any) -> Any | None:
    payload = getattr(slide, "_payload", None)
    if not isinstance(payload, dict):
        return None
    hints = payload.get("picture_shape_hints")
    if not isinstance(hints, list):
        return None
    for hint in hints:
        if not isinstance(hint, dict) or not hint.get("has_picture"):
            continue
        return Shape(slide, int(hint.get("_shape_index", 0)), hint)
    return None


def _read_python_pptx_picture_image_metadata(
    fixture_id: str,
    prs: Any,
) -> dict[str, Any]:
    if fixture_id not in PICTURE_IMAGE_INSPECTION_FIXTURES:
        raise RuntimeError(
            "drop-in picture image inspection benchmark does not support fixture "
            f"{fixture_id}"
        )
    picture = _first_picture_shape(prs)
    image = picture.image
    return _picture_image_metadata(image)


def _read_wolfppt_picture_image_metadata(
    fixture_id: str,
    prs: WolfPresentation,
) -> dict[str, Any]:
    if fixture_id not in PICTURE_IMAGE_INSPECTION_FIXTURES:
        raise RuntimeError(
            "drop-in picture image inspection benchmark does not support fixture "
            f"{fixture_id}"
        )
    picture = _first_picture_shape(prs)
    image = picture.image
    return _picture_image_metadata(image)


def _picture_image_metadata(image: Any) -> dict[str, Any]:
    blob = image.blob
    return {
        "blob_length": len(blob),
        "blob_sha1": sha1(blob).hexdigest(),
        "content_type": image.content_type,
        "dpi": tuple(image.dpi),
        "ext": image.ext,
        "filename": image.filename,
        "image_sha1": image.sha1,
        "size": tuple(image.size),
    }


def _apply_python_pptx_dropin_add_picture_auto_size(
    fixture_id: str,
    prs: Any,
    image_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture auto-size benchmark does not support fixture {fixture_id}"
        )
    prs.slides[0].shapes.add_picture(
        str(image_path),
        ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM["y"],
    )


def _apply_wolfppt_dropin_add_picture_auto_size(
    fixture_id: str,
    prs: WolfPresentation,
    image_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture auto-size benchmark does not support fixture {fixture_id}"
        )
    _shape_collection_at(prs, 0).add_picture(
        image_path,
        ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM["y"],
    )


def _apply_python_pptx_dropin_add_picture(
    fixture_id: str,
    prs: Any,
    image_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture benchmark does not support fixture {fixture_id}"
        )
    prs.slides[0].shapes.add_picture(
        str(image_path),
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["y"],
        width=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cx"],
        height=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cy"],
    )


def _apply_wolfppt_dropin_add_picture(
    fixture_id: str,
    prs: WolfPresentation,
    image_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture benchmark does not support fixture {fixture_id}"
        )
    _shape_collection_at(prs, 0).add_picture(
        image_path,
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["y"],
        width=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cx"],
        height=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cy"],
    )


def _apply_python_pptx_dropin_add_group_picture(
    fixture_id: str,
    prs: Any,
    image_path: Path,
) -> None:
    if fixture_id not in GROUP_PICTURE_TARGETS:
        raise RuntimeError(
            f"drop-in add-group-picture benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_PICTURE_TARGETS[fixture_id]
    prs.slides[slide_index].shapes[group_index].shapes.add_picture(
        str(image_path),
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["y"],
        width=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cx"],
        height=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cy"],
    )


def _apply_wolfppt_dropin_add_group_picture(
    fixture_id: str,
    prs: WolfPresentation,
    image_path: Path,
) -> None:
    _dropin_group_shape(
        fixture_id, prs, "add-group-picture", GROUP_PICTURE_TARGETS
    ).shapes.add_picture(
        image_path,
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["y"],
        width=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cx"],
        height=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cy"],
    )


def _apply_python_pptx_dropin_add_nested_group_picture(
    fixture_id: str,
    prs: Any,
    image_path: Path,
) -> None:
    if fixture_id not in GROUP_PICTURE_TARGETS:
        raise RuntimeError(
            f"drop-in add-nested-group-picture benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_PICTURE_TARGETS[fixture_id]
    nested = prs.slides[slide_index].shapes[group_index].shapes.add_group_shape()
    nested.shapes.add_picture(
        str(image_path),
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["y"],
        width=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cx"],
        height=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cy"],
    )


def _apply_wolfppt_dropin_add_nested_group_picture(
    fixture_id: str,
    prs: WolfPresentation,
    image_path: Path,
) -> None:
    nested = _dropin_group_shape(
        fixture_id, prs, "add-nested-group-picture", GROUP_PICTURE_TARGETS
    ).shapes.add_group_shape()
    nested.shapes.add_picture(
        image_path,
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["y"],
        width=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cx"],
        height=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cy"],
    )


def _apply_python_pptx_dropin_add_deeper_nested_group_picture(
    fixture_id: str,
    prs: Any,
    image_path: Path,
) -> None:
    if fixture_id not in GROUP_PICTURE_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-picture benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_PICTURE_TARGETS[fixture_id]
    (
        prs.slides[slide_index]
        .shapes[group_index]
        .shapes.add_group_shape()
        .shapes.add_group_shape()
        .shapes.add_picture(
            str(image_path),
            ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["x"],
            ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["y"],
            width=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cx"],
            height=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cy"],
        )
    )


def _apply_wolfppt_dropin_add_deeper_nested_group_picture(
    fixture_id: str,
    prs: WolfPresentation,
    image_path: Path,
) -> None:
    (
        _dropin_group_shape(
            fixture_id,
            prs,
            "add-deeper-nested-group-picture",
            GROUP_PICTURE_TARGETS,
        )
        .shapes.add_group_shape()
        .shapes.add_group_shape()
        .shapes.add_picture(
            image_path,
            ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["x"],
            ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["y"],
            width=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cx"],
            height=ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM["cy"],
        )
    )


def _apply_python_pptx_dropin_add_picture_file_like(
    fixture_id: str,
    prs: Any,
    image_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture file-like benchmark does not support fixture {fixture_id}"
        )
    prs.slides[0].shapes.add_picture(
        BytesIO(image_path.read_bytes()),
        ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM["y"],
    )


def _apply_wolfppt_dropin_add_picture_file_like(
    fixture_id: str,
    prs: WolfPresentation,
    image_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture file-like benchmark does not support fixture {fixture_id}"
        )
    _shape_collection_at(prs, 0).add_picture(
        BytesIO(image_path.read_bytes()),
        ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM["x"],
        ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM["y"],
    )


def _apply_python_pptx_dropin_replace_picture(
    fixture_id: str,
    prs: Any,
    image_path: Path,
) -> None:
    if fixture_id not in PICTURE_REPLACE_FIXTURES:
        raise RuntimeError(
            f"drop-in replace-picture benchmark does not support fixture {fixture_id}"
        )
    picture = _first_picture_shape(prs)
    relationship_id = picture._pic.blipFill.blip.rEmbed
    picture.part.related_part(relationship_id)._blob = image_path.read_bytes()


def _apply_wolfppt_dropin_replace_picture(
    fixture_id: str,
    prs: WolfPresentation,
    image_path: Path,
) -> None:
    if fixture_id not in PICTURE_REPLACE_FIXTURES:
        raise RuntimeError(
            f"drop-in replace-picture benchmark does not support fixture {fixture_id}"
        )
    _first_picture_shape(prs).replace_image(image_path)


def _apply_python_pptx_dropin_add_movie(
    fixture_id: str,
    prs: Any,
    movie_path: Path,
    poster_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-movie benchmark does not support fixture {fixture_id}"
        )
    prs.slides[0].shapes.add_movie(
        str(movie_path),
        ADD_MOVIE_EXPECTED_TRANSFORM["x"],
        ADD_MOVIE_EXPECTED_TRANSFORM["y"],
        ADD_MOVIE_EXPECTED_TRANSFORM["cx"],
        ADD_MOVIE_EXPECTED_TRANSFORM["cy"],
        poster_frame_image=str(poster_path),
        mime_type="video/mp4",
    )


def _apply_wolfppt_dropin_add_movie(
    fixture_id: str,
    prs: WolfPresentation,
    movie_path: Path,
    poster_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-movie benchmark does not support fixture {fixture_id}"
        )
    _shape_collection_at(prs, 0).add_movie(
        movie_path,
        ADD_MOVIE_EXPECTED_TRANSFORM["x"],
        ADD_MOVIE_EXPECTED_TRANSFORM["y"],
        ADD_MOVIE_EXPECTED_TRANSFORM["cx"],
        ADD_MOVIE_EXPECTED_TRANSFORM["cy"],
        poster_frame_image=poster_path,
        mime_type="video/mp4",
    )


def _apply_python_pptx_dropin_add_movie_file_like(
    fixture_id: str,
    prs: Any,
    movie_path: Path,
    poster_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-movie file-like benchmark does not support fixture {fixture_id}"
        )
    prs.slides[0].shapes.add_movie(
        BytesIO(movie_path.read_bytes()),
        ADD_MOVIE_EXPECTED_TRANSFORM["x"],
        ADD_MOVIE_EXPECTED_TRANSFORM["y"],
        ADD_MOVIE_EXPECTED_TRANSFORM["cx"],
        ADD_MOVIE_EXPECTED_TRANSFORM["cy"],
        poster_frame_image=BytesIO(poster_path.read_bytes()),
        mime_type="video/mp4",
    )


def _apply_wolfppt_dropin_add_movie_file_like(
    fixture_id: str,
    prs: WolfPresentation,
    movie_path: Path,
    poster_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-movie file-like benchmark does not support fixture {fixture_id}"
        )
    _shape_collection_at(prs, 0).add_movie(
        BytesIO(movie_path.read_bytes()),
        ADD_MOVIE_EXPECTED_TRANSFORM["x"],
        ADD_MOVIE_EXPECTED_TRANSFORM["y"],
        ADD_MOVIE_EXPECTED_TRANSFORM["cx"],
        ADD_MOVIE_EXPECTED_TRANSFORM["cy"],
        poster_frame_image=BytesIO(poster_path.read_bytes()),
        mime_type="video/mp4",
    )


def _apply_python_pptx_dropin_add_ole_object(
    fixture_id: str,
    prs: Any,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-ole-object benchmark does not support fixture {fixture_id}"
        )
    prs.slides[0].shapes.add_ole_object(
        str(embedded_path),
        "Package",
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
        icon_file=str(icon_path),
        icon_width=914400,
        icon_height=914400,
    )


def _apply_wolfppt_dropin_add_ole_object(
    fixture_id: str,
    prs: WolfPresentation,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-ole-object benchmark does not support fixture {fixture_id}"
        )
    _shape_collection_at(prs, 0).add_ole_object(
        embedded_path,
        "Package",
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
        icon_file=icon_path,
        icon_width=914400,
        icon_height=914400,
    )


def _apply_python_pptx_dropin_add_group_ole_object(
    fixture_id: str,
    prs: Any,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    if fixture_id not in GROUP_OLE_OBJECT_TARGETS:
        raise RuntimeError(
            f"drop-in add-group-ole-object benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_OLE_OBJECT_TARGETS[fixture_id]
    prs.slides[slide_index].shapes[group_index].shapes.add_ole_object(
        str(embedded_path),
        "Package",
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
        icon_file=str(icon_path),
        icon_width=914400,
        icon_height=914400,
    )


def _apply_wolfppt_dropin_add_group_ole_object(
    fixture_id: str,
    prs: WolfPresentation,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    _dropin_group_shape(
        fixture_id, prs, "add-group-ole-object", GROUP_OLE_OBJECT_TARGETS
    ).shapes.add_ole_object(
        embedded_path,
        "Package",
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
        icon_file=icon_path,
        icon_width=914400,
        icon_height=914400,
    )


def _apply_python_pptx_dropin_add_nested_group_ole_object(
    fixture_id: str,
    prs: Any,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    if fixture_id not in GROUP_OLE_OBJECT_TARGETS:
        raise RuntimeError(
            f"drop-in add-nested-group-ole-object benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_OLE_OBJECT_TARGETS[fixture_id]
    nested = prs.slides[slide_index].shapes[group_index].shapes.add_group_shape()
    nested.shapes.add_ole_object(
        str(embedded_path),
        "Package",
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
        icon_file=str(icon_path),
        icon_width=914400,
        icon_height=914400,
    )


def _apply_wolfppt_dropin_add_nested_group_ole_object(
    fixture_id: str,
    prs: WolfPresentation,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    nested = _dropin_group_shape(
        fixture_id, prs, "add-nested-group-ole-object", GROUP_OLE_OBJECT_TARGETS
    ).shapes.add_group_shape()
    nested.shapes.add_ole_object(
        embedded_path,
        "Package",
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
        icon_file=icon_path,
        icon_width=914400,
        icon_height=914400,
    )


def _apply_python_pptx_dropin_add_deeper_nested_group_ole_object(
    fixture_id: str,
    prs: Any,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    if fixture_id not in GROUP_OLE_OBJECT_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-ole-object benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_OLE_OBJECT_TARGETS[fixture_id]
    (
        prs.slides[slide_index]
        .shapes[group_index]
        .shapes.add_group_shape()
        .shapes.add_group_shape()
        .shapes.add_ole_object(
            str(embedded_path),
            "Package",
            ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
            ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
            ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
            ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
            icon_file=str(icon_path),
            icon_width=914400,
            icon_height=914400,
        )
    )


def _apply_wolfppt_dropin_add_deeper_nested_group_ole_object(
    fixture_id: str,
    prs: WolfPresentation,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    (
        _dropin_group_shape(
            fixture_id,
            prs,
            "add-deeper-nested-group-ole-object",
            GROUP_OLE_OBJECT_TARGETS,
        )
        .shapes.add_group_shape()
        .shapes.add_group_shape()
        .shapes.add_ole_object(
            embedded_path,
            "Package",
            ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
            ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
            ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
            ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
            icon_file=icon_path,
            icon_width=914400,
            icon_height=914400,
        )
    )


def _apply_python_pptx_dropin_add_ole_object_file_like(
    fixture_id: str,
    prs: Any,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-ole-object file-like benchmark does not support fixture {fixture_id}"
        )
    prs.slides[0].shapes.add_ole_object(
        BytesIO(embedded_path.read_bytes()),
        "Package",
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
        icon_file=BytesIO(icon_path.read_bytes()),
        icon_width=914400,
        icon_height=914400,
    )


def _apply_wolfppt_dropin_add_ole_object_file_like(
    fixture_id: str,
    prs: WolfPresentation,
    embedded_path: Path,
    icon_path: Path,
) -> None:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-ole-object file-like benchmark does not support fixture {fixture_id}"
        )
    _shape_collection_at(prs, 0).add_ole_object(
        BytesIO(embedded_path.read_bytes()),
        "Package",
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["x"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["y"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cx"],
        ADD_OLE_OBJECT_EXPECTED_TRANSFORM["cy"],
        icon_file=BytesIO(icon_path.read_bytes()),
        icon_width=914400,
        icon_height=914400,
    )
