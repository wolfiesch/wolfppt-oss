"""Shared helpers for media-oriented drop-in benchmark details."""

from __future__ import annotations

import posixpath
from hashlib import sha1
from pathlib import Path
from typing import Any, NamedTuple
from xml.etree import ElementTree as ET
from zipfile import ZipFile


class _PictureParts(NamedTuple):
    slide_part: str
    rels_part: str
    media_part: str


TOP_LEVEL_PICTURE_FIXTURES = (
    "text_basic/title_body_bullets",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)
TOP_LEVEL_MEDIA_FIXTURES = TOP_LEVEL_PICTURE_FIXTURES
PICTURE_REPLACE_FIXTURES = (
    "media/png_picture",
    "workloads/mixed_real_world_deck",
)
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


def _part_metadata(part_owner: Any) -> dict[str, Any]:
    part = part_owner.part
    try:
        name = part.name
    except AttributeError:
        name = None
    return {
        "partname": str(part.partname),
        "content_type": part.content_type,
        "has_blob": len(part.blob) > 0,
        "part_is_self": part.part is part,
        "name": name,
    }


def _dropin_expected_picture_bytes(fixture_id: str, fixture_path: Path) -> bytes:
    fixture_root = fixture_path
    for _ in Path(fixture_id).parts:
        fixture_root = fixture_root.parent
    with ZipFile(fixture_root / "media" / "png_picture.pptx") as package:
        return package.read("ppt/media/image1.png")


def _expected_picture_image_metadata(
    fixture_id: str,
    fixture_path: Path,
) -> dict[str, Any]:
    blob = _dropin_expected_picture_image_bytes(fixture_path)
    digest = sha1(blob).hexdigest()
    return {
        "blob_length": len(blob),
        "blob_sha1": digest,
        "content_type": "image/png",
        "dpi": (72, 72),
        "ext": "png",
        "filename": "image.png",
        "image_sha1": digest,
        "size": (1, 1),
    }


def _dropin_expected_picture_image_bytes(fixture_path: Path) -> bytes:
    picture_parts = _first_slide_picture_parts(fixture_path)
    with ZipFile(fixture_path) as package:
        return package.read(picture_parts.media_part)


def _first_slide_picture_parts(fixture_path: Path) -> _PictureParts:
    return _slide_picture_parts(fixture_path, 0)


def _last_slide_picture_parts(
    fixture_path: Path,
    *,
    slide_index: int = 0,
) -> _PictureParts:
    return _slide_picture_parts(fixture_path, -1, slide_index=slide_index)


def _slide_picture_parts(
    fixture_path: Path,
    blip_index: int,
    *,
    slide_index: int = 0,
) -> _PictureParts:
    slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    rels_part = f"ppt/slides/_rels/slide{slide_index + 1}.xml.rels"
    with ZipFile(fixture_path) as package:
        slide_root = ET.fromstring(package.read(slide_part))
        rels_root = ET.fromstring(package.read(rels_part))
        relationships = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root
            if "Id" in rel.attrib and "Target" in rel.attrib
        }
        blips = slide_root.findall(
            ".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
        )
        if not blips:
            raise RuntimeError(f"fixture {fixture_path} does not contain a picture")
        blip = blips[blip_index]
        relationship_id = blip.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        )
        if relationship_id is None or relationship_id not in relationships:
            raise RuntimeError(f"fixture {fixture_path} has no picture relationship")
        target = relationships[relationship_id]
        if target.startswith("/"):
            partname = target.lstrip("/")
        else:
            partname = posixpath.normpath(
                posixpath.join(posixpath.dirname(slide_part), target)
            )
        return _PictureParts(slide_part, rels_part, partname)


def _dropin_expected_replacement_picture_bytes(
    fixture_id: str,
    fixture_path: Path,
) -> bytes:
    return _dropin_expected_picture_bytes(fixture_id, fixture_path) + b"replacement"


def _dropin_expected_movie_bytes() -> bytes:
    return b"wolfppt benchmark movie bytes"


def _dropin_expected_ole_object_bytes() -> bytes:
    return b"wolfppt benchmark embedded object bytes"
