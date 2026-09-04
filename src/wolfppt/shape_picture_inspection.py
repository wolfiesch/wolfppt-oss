"""Picture image and crop inspection helpers for shape facades."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .facade_values import coerce_crop_fraction as _coerce_crop_fraction
from .image_dimensions import image_size_and_dpi as _image_size_and_dpi
from .image_inputs import (
    image_source_for_queue as _image_source_for_queue,
    image_extension_from_blob as _image_extension_from_blob,
    image_input_bytes as _image_input_bytes,
    image_input_filename as _image_input_filename,
)
from .package_parts import (
    package_part_content_type as _package_part_content_type,
    resolve_package_target as _resolve_package_target,
)
from .shape_xml import _picture_blip_fill_element, _shape_xml_element
from .shape_edit_refs import (
    ShapeEditRef,
    shape_edit_ref as _shape_edit_ref,
)
from .slide_relationships import slide_relationship_info as _slide_relationship_info
from .xml_helpers import xml_local_name as _xml_local_name


def _shape_picture_edit_ref(shape: Any) -> ShapeEditRef:
    return _shape_edit_ref(shape)


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

_CONTENT_TYPE_BY_EXT = {
    "bmp": "image/bmp",
    "gif": "image/gif",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "tiff": "image/tiff",
    "wmf": "image/x-wmf",
}
_EXT_BY_CONTENT_TYPE = {
    "image/bmp": "bmp",
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/tiff": "tiff",
    "image/x-wmf": "wmf",
}


class PictureImage:
    """Immutable python-pptx-style image value object."""

    def __init__(
        self,
        blob: bytes,
        filename: str | None = None,
        content_type: str | None = None,
        fallback_ext: str | None = None,
    ) -> None:
        self._blob = blob
        self._filename = filename
        self._content_type = content_type
        self._fallback_ext = fallback_ext
        self._ext_cache: str | None = None
        self._sha1_cache: str | None = None
        self._size_and_dpi_cache: tuple[int, int, float, float] | None = None

    @classmethod
    def from_image_input(cls, image_file: Any) -> "PictureImage":
        return cls(
            _image_input_bytes(image_file),
            _image_input_filename(image_file),
        )

    @classmethod
    def from_blob(cls, blob: bytes) -> "PictureImage":
        return cls(bytes(blob))

    @classmethod
    def from_file(cls, image_file: Any) -> "PictureImage":
        return cls.from_image_input(image_file)

    @classmethod
    def from_package_part(
        cls,
        presentation: Any,
        partname: str,
    ) -> "PictureImage":
        normalized = partname.lstrip("/")
        try:
            with zipfile.ZipFile(presentation.path) as package:
                blob = package.read(normalized)
        except (
            FileNotFoundError,
            KeyError,
            zipfile.BadZipFile,
        ) as exc:
            raise AttributeError("picture image is unavailable") from exc
        suffix = Path(normalized).suffix.lower().lstrip(".") or None
        content_type = (
            None
            if suffix in _CONTENT_TYPE_BY_EXT
            else _package_part_content_type(presentation.path, partname)
        )
        return cls(
            blob,
            content_type=content_type,
            fallback_ext=suffix,
        )

    @property
    def blob(self) -> bytes:
        return self._blob

    @property
    def content_type(self) -> str:
        if self._content_type:
            return self._content_type
        return _CONTENT_TYPE_BY_EXT.get(self.ext, f"image/{self.ext}")

    @property
    def dpi(self) -> tuple[int, int]:
        _, _, dpi_x, dpi_y = self._size_and_dpi
        return (_normalized_dpi(dpi_x), _normalized_dpi(dpi_y))

    @property
    def ext(self) -> str:
        if self._ext_cache is not None:
            return self._ext_cache
        try:
            self._ext_cache = _image_extension_from_blob(self._blob)
        except ValueError:
            if self._content_type in _EXT_BY_CONTENT_TYPE:
                self._ext_cache = _EXT_BY_CONTENT_TYPE[self._content_type]
                return self._ext_cache
            if self._fallback_ext:
                self._ext_cache = self._fallback_ext
                return self._ext_cache
            raise
        return self._ext_cache

    @property
    def filename(self) -> str | None:
        if self._filename is not None:
            return self._filename
        return f"image.{self._fallback_ext or self.ext}"

    @property
    def sha1(self) -> str:
        if self._sha1_cache is None:
            self._sha1_cache = hashlib.sha1(self._blob).hexdigest()
        return self._sha1_cache

    @property
    def size(self) -> tuple[int, int]:
        width, height, _, _ = self._size_and_dpi
        return (width, height)

    @property
    def _size_and_dpi(self) -> tuple[int, int, float, float]:
        if self._size_and_dpi_cache is None:
            self._size_and_dpi_cache = _image_size_and_dpi(self._blob)
        return self._size_and_dpi_cache


class MediaFormat:
    """Small python-pptx-style media format proxy for movie shapes."""

    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def element(self) -> Any:
        return self._shape.element

    @property
    def parent(self) -> Any:
        return self._shape

    @property
    def part(self) -> Any:
        return self._shape.part


def _picture_crop(shape: Any) -> dict[str, float]:
    if not _shape_has_crop(shape):
        raise AttributeError("shape does not have picture cropping")
    raw = shape._payload.get("crop")
    if not isinstance(raw, dict):
        raw = _shape_picture_crop(shape)
        shape._payload["crop"] = raw
    return {
        "l": float(raw.get("l", 0.0)),
        "r": float(raw.get("r", 0.0)),
        "t": float(raw.get("t", 0.0)),
        "b": float(raw.get("b", 0.0)),
    }


def _picture_crop_value(shape: Any, key: str) -> float:
    return _picture_crop(shape)[key]


def _picture_image(shape: Any) -> PictureImage:
    if not shape.has_picture:
        raise AttributeError("'Shape' object has no attribute 'image'")
    replacement_image = shape._payload.get("_replacement_image_file")
    if replacement_image is not None:
        return PictureImage.from_image_input(replacement_image)
    image_part = _shape_image_partname(shape)
    if image_part is not None:
        return PictureImage.from_package_part(shape._slide._presentation, image_part)
    image_file = shape._payload.get("_image_file")
    if image_file:
        return PictureImage.from_image_input(image_file)
    raise AttributeError("picture image is unavailable")


def _replace_picture_image(shape: Any, image_file: Any) -> PictureImage:
    if not shape.has_picture:
        raise AttributeError("'Shape' object has no attribute 'replace_image'")
    if shape._payload.get("_pending_shape"):
        raise ValueError("cannot replace image bytes on an unsaved picture shape")
    relationship_id = _shape_image_relationship_id(shape)
    if relationship_id is None:
        raise AttributeError("picture image relationship is unavailable")
    image_source = _image_source_for_queue(image_file)
    replacement_image = PictureImage.from_image_input(image_source)
    existing_content_type = _picture_image(shape).content_type
    if replacement_image.content_type != existing_content_type:
        raise ValueError(
            "replacement image content type must match existing picture "
            f"content type {existing_content_type!r}"
        )
    shape._payload["_replacement_image_file"] = image_source
    shape._slide._presentation._queue_picture_replace(
        shape._slide._index,
        relationship_id,
        image_source,
    )
    return replacement_image


def _shape_media_format(shape: Any) -> MediaFormat:
    if shape._payload.get("kind") != "movie":
        raise AttributeError("'Shape' object has no attribute 'media_format'")
    return MediaFormat(shape)


def _shape_media_type(shape: Any) -> Any:
    if shape._payload.get("kind") != "movie":
        raise AttributeError("'Shape' object has no attribute 'media_type'")
    try:
        from pptx.enum.shapes import PP_MEDIA_TYPE
    except ImportError:
        return "MOVIE"
    return PP_MEDIA_TYPE.MOVIE


def _shape_poster_frame(shape: Any) -> PictureImage:
    if shape._payload.get("kind") != "movie":
        raise AttributeError("'Shape' object has no attribute 'poster_frame'")
    poster_frame = shape._payload.get("_poster_frame_file")
    if poster_frame is not None:
        return PictureImage.from_image_input(poster_frame)
    image_part = _shape_image_partname(shape)
    if image_part is not None:
        return PictureImage.from_package_part(shape._slide._presentation, image_part)
    raise AttributeError("movie poster frame is unavailable")


def _set_picture_crop_value(shape: Any, key: str, value: Any) -> None:
    crop = _picture_crop(shape)
    coerced = _coerce_crop_fraction(value)
    if crop.get(key) == coerced:
        return
    crop[key] = coerced
    shape._payload["crop"] = crop
    shape._slide._presentation._queue_picture_crop(
        shape._slide._index,
        _shape_picture_edit_ref(shape),
        crop,
    )


def _shape_image_partname(shape: Any) -> str | None:
    if shape._payload.get("_image_part"):
        return str(shape._payload["_image_part"])
    relationship_id = _shape_image_relationship_id(shape)
    if relationship_id is None:
        return None
    relationship = _slide_relationship_info(
        shape._slide._presentation.path,
        shape._slide.partname,
        relationship_id,
    )
    if relationship is None:
        return None
    _relationship_type, target = relationship
    return _resolve_package_target(shape._slide.partname, target)


def _shape_image_relationship_id(shape: Any) -> str | None:
    if shape._payload.get("_image_relationship_id"):
        return str(shape._payload["_image_relationship_id"])
    if not shape._slide.partname:
        return None
    relationship_ids = [
        str(relationship_id)
        for relationship_id in shape._payload.get("relationship_ids") or []
    ]
    for relationship_id in relationship_ids:
        relationship = _slide_relationship_info(
            shape._slide._presentation.path,
            shape._slide.partname,
            relationship_id,
        )
        if relationship is None:
            continue
        relationship_type, _target = relationship
        if relationship_type.endswith("/image"):
            return relationship_id
    return None


def _shape_has_crop(shape: Any) -> bool:
    return bool(shape.has_picture) or shape._payload.get("kind") == "movie"


def _normalized_dpi(value: float) -> int:
    try:
        dpi = int(round(float(value)))
    except (TypeError, ValueError):
        return 72
    if dpi < 1 or dpi > 2048:
        return 72
    return dpi


def _shape_picture_crop(shape: Any) -> dict[str, float]:
    if not _shape_has_crop(shape) or not shape._slide.partname:
        return {"l": 0.0, "r": 0.0, "t": 0.0, "b": 0.0}
    try:
        with zipfile.ZipFile(shape._slide._presentation.path) as package:
            root = ET.fromstring(package.read(shape._slide.partname))
        shape_element = _shape_xml_element(root, shape._payload)
        if _xml_local_name(shape_element.tag) != "pic":
            return {"l": 0.0, "r": 0.0, "t": 0.0, "b": 0.0}
        src_rect = _picture_blip_fill_element(shape_element).find(f"{{{A_NS}}}srcRect")
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return {"l": 0.0, "r": 0.0, "t": 0.0, "b": 0.0}
    if src_rect is None:
        return {"l": 0.0, "r": 0.0, "t": 0.0, "b": 0.0}
    return {
        key: int(src_rect.attrib.get(key, "0")) / 100000
        for key in ("l", "r", "t", "b")
    }
