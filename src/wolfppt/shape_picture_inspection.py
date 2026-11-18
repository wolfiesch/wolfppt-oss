"""Picture image and crop inspection helpers for shape facades."""

from __future__ import annotations

import base64
import hashlib
import io
import math
import os
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from xml.etree import ElementTree as ET

from .editions import commercial_module
from .enum.shapes import PP_MEDIA_START_MODE, PP_MEDIA_TYPE, PP_MEDIA_VOLUME
from .facade_values import coerce_crop_fraction as _coerce_crop_fraction
from .image_dimensions import image_size_and_dpi as _image_size_and_dpi
from .image_inputs import (
    image_extension_from_blob as _image_extension_from_blob,
)
from .image_inputs import (
    image_input_bytes as _image_input_bytes,
)
from .image_inputs import (
    image_input_filename as _image_input_filename,
)
from .image_inputs import (
    image_source_for_queue as _image_source_for_queue,
)
from .package_parts import (
    InMemoryPackageSource,
    open_package_source,
)
from .package_parts import (
    package_part_content_type as _package_part_content_type,
)
from .package_parts import (
    resolve_package_target as _resolve_package_target,
)
from .render_refusals import RenderRefusal
from .shape_edit_refs import (
    ShapeEditRef,
)
from .shape_edit_refs import (
    shape_edit_ref as _shape_edit_ref,
)
from .shape_xml import _picture_blip_fill_element, _shape_xml_element
from .slide_metadata import package_relationships as _package_relationships
from .xml_helpers import ooxml_path as _ooxml_path
from .xml_helpers import xml_local_name as _xml_local_name


def _shape_picture_edit_ref(shape: Any) -> ShapeEditRef:
    return _shape_edit_ref(shape)


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"

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


class SvgPictureRefusal(ValueError):
    """An SVG picture has unsupported or ambiguous representation references."""


@dataclass(frozen=True)
class SvgPicture:
    """Exact vector source and the raster fallback used by WolfPPT rendering."""

    svg: bytes
    svg_partname: str
    raster_fallback: PictureImage
    fallback_partname: str


def inspect_svg_picture(shape: Any) -> SvgPicture:
    """Read both representations of a saved embedded SVG picture.

    SVG input remains byte-preserved. Linked images, missing parts, ambiguous
    SVG references and non-image relationships raise SvgPictureRefusal.
    """
    svg_ns = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    if not shape.has_picture or shape._payload.get("_pending_shape"):
        raise SvgPictureRefusal("only a saved picture can contain an SVG representation")
    prs = shape._slide._presentation
    with prs._mutation_lock:
        try:
            prs._require_saved_package("inspecting an SVG picture")
        except ValueError as exc:
            raise SvgPictureRefusal(str(exc)) from exc
        source = _shape_package_source(shape)
        try:
            with open_package_source(source) as package:
                root = ET.fromstring(package.read(shape._slide.partname))
                picture = _shape_xml_element(root, shape._payload)
                fill = _picture_blip_fill_element(picture)
                blip = fill.find(f"{{{A_NS}}}blip")
                vectors = list(fill.iter(f"{{{svg_ns}}}svgBlip"))
                if blip is None or len(vectors) != 1:
                    raise SvgPictureRefusal("shape needs exactly one SVG and one raster blip")
                relationships = _package_relationships(package, shape._slide.partname)
                parts = []
                for node in (vectors[0], blip):
                    if node.get(f"{{{r_ns}}}link"):
                        raise SvgPictureRefusal("linked SVG pictures are unsupported")
                    rid = node.get(f"{{{r_ns}}}embed")
                    rel = relationships.get(rid)
                    if (
                        rel is None
                        or rel.get("TargetMode", "Internal") != "Internal"
                        or not rel.get("Type", "").endswith("/image")
                        or not rel.get("Target")
                    ):
                        raise SvgPictureRefusal("SVG picture needs internal image relationships")
                    parts.append(_resolve_package_target(shape._slide.partname, rel.get("Target")))
                vector, fallback = (package.read(part) for part in parts)
        except (AttributeError, IndexError, KeyError, ET.ParseError) as exc:
            raise SvgPictureRefusal("SVG picture representation is unavailable") from exc
        if _package_part_content_type(source, parts[0]) != "image/svg+xml":
            raise SvgPictureRefusal("SVG representation must have image/svg+xml content type")
        fallback_image = PictureImage.from_blob(fallback)
        try:
            _ = fallback_image.ext, fallback_image.size
        except ValueError as exc:
            raise SvgPictureRefusal("SVG picture needs a supported raster fallback") from exc
        return SvgPicture(vector, parts[0], fallback_image, parts[1])


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
    def from_image_input(cls, image_file: Any) -> PictureImage:
        return cls(
            _image_input_bytes(image_file),
            _image_input_filename(image_file),
        )

    @classmethod
    def from_blob(cls, blob: bytes) -> PictureImage:
        return cls(bytes(blob))

    @classmethod
    def from_file(cls, image_file: Any) -> PictureImage:
        return cls.from_image_input(image_file)

    @classmethod
    def from_package_part(
        cls,
        presentation: Any,
        partname: str,
    ) -> PictureImage:
        return cls.from_package_source(presentation.path, partname)

    @classmethod
    def from_package_source(
        cls,
        source: Path | InMemoryPackageSource,
        partname: str,
    ) -> PictureImage:
        normalized = partname.lstrip("/")
        try:
            with open_package_source(source) as package:
                blob = package.read(normalized)
        except (
            FileNotFoundError,
            KeyError,
            zipfile.BadZipFile,
        ) as exc:
            raise AttributeError("picture image is unavailable") from exc
        suffix = Path(normalized).suffix.lower().lstrip(".") or None
        content_type = (
            None if suffix in _CONTENT_TYPE_BY_EXT else _package_part_content_type(source, partname)
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
    def width(self) -> int:
        """Pixel width read from the image header."""
        return self.size[0]

    @property
    def height(self) -> int:
        """Pixel height read from the image header."""
        return self.size[1]

    def save(self, destination: Any, format: Any = None, *, quality: Any = None) -> None:
        """Write this image to a path or writable binary stream.

        Without ``format`` the exact source bytes are written. A named
        :class:`ImageFormat` encodes through :func:`encode_image`; JPEG takes an
        optional ``quality`` from 1 to 100. Every refusal precedes the write.
        """
        check_image_destination(destination)
        if format is None:
            if quality is not None:
                raise ImageFormatRefusal("quality needs format=ImageFormat.JPEG")
            payload = self._blob
        else:
            try:
                dpi = self.dpi
            except ValueError:
                dpi = None
            payload = encode_image(self._blob, format, quality=quality, dpi=dpi)
        write_image_output(destination, payload)

    @property
    def size(self) -> tuple[int, int]:
        width, height, _, _ = self._size_and_dpi
        return (width, height)

    @property
    def _size_and_dpi(self) -> tuple[int, int, float, float]:
        if self._size_and_dpi_cache is None:
            self._size_and_dpi_cache = _image_size_and_dpi(self._blob)
        return self._size_and_dpi_cache


#: JPEG quality used when a JPEG output names no explicit quality.
DEFAULT_JPEG_QUALITY = 95
_PNG_MODES = frozenset(("1", "L", "LA", "I", "I;16", "P", "RGB", "RGBA"))


class ImageFormat(StrEnum):
    """Named encoded outputs for image saves and shape renders.

    Members equal their lowercase names, so either spelling is accepted.
    """

    PNG = "png"
    JPEG = "jpeg"
    SVG = "svg"
    PDF = "pdf"

    @property
    def extension(self) -> str:
        return "jpg" if self is ImageFormat.JPEG else self.value

    @property
    def content_type(self) -> str:
        named = {"svg": "image/svg+xml", "pdf": "application/pdf"}
        return named.get(self.value, f"image/{self.value}")


class ImageFormatRefusal(RenderRefusal):
    """An image save names an unsupported format, quality, source or destination."""


def image_format(value: Any) -> ImageFormat:
    """Resolve an :class:`ImageFormat` or its name; ``"jpg"`` names JPEG."""
    if isinstance(value, str):
        name = value.strip().lower().lstrip(".")
        try:
            return ImageFormat("jpeg" if name == "jpg" else name)
        except ValueError:
            pass
    raise ImageFormatRefusal(
        f"image format {value!r} is not supported; choose one of png, jpeg, svg or pdf"
    )


def jpeg_quality(value: Any) -> int:
    """Return an explicit JPEG quality from 1 to 100, or the default for None."""
    if value is None:
        return DEFAULT_JPEG_QUALITY
    if type(value) is not int or not 1 <= value <= 100:
        raise ImageFormatRefusal("JPEG quality must be an integer from 1 to 100")
    return value


def load_image(source: Any) -> PictureImage:
    """Create a standalone :class:`PictureImage` from a path, bytes or binary stream.

    The header is parsed at once, so unsupported or truncated data raises
    :class:`ImageFormatRefusal` before the image is placed or saved anywhere.
    """
    if isinstance(source, (bytes, bytearray, memoryview)):
        image = PictureImage(bytes(source))
    else:
        try:
            image = PictureImage.from_image_input(source)
        except TypeError as exc:
            raise ImageFormatRefusal(
                "image source must be a path, bytes or a binary stream"
            ) from exc
    try:
        _ = image.ext, image.size
    except (ValueError, IndexError) as exc:
        raise ImageFormatRefusal(f"unsupported or corrupt image: {exc}") from exc
    return image


def check_image_destination(destination: Any) -> None:
    """Refuse a destination that is neither a path nor a writable stream."""
    if callable(getattr(destination, "write", None)):
        return
    if not isinstance(destination, (str, os.PathLike)):
        raise ImageFormatRefusal("image destination must be a path or a writable binary stream")


def write_image_output(destination: Any, payload: bytes) -> None:
    """Write encoded image bytes to a path or writable binary stream."""
    if callable(getattr(destination, "write", None)):
        destination.write(payload)
    else:
        Path(destination).write_bytes(payload)


def encode_image(
    blob: bytes,
    format: Any,
    *,
    quality: Any = None,
    dpi: tuple[int, int] | None = None,
) -> bytes:
    """Encode one decodable raster as PNG, JPEG, SVG or a one-page PDF.

    A PNG or JPEG target matching the source returns the exact bytes unless a
    JPEG ``quality`` is named. JPEG composites transparency over white. SVG
    embeds the PNG or JPEG payload at its pixel size. PDF places the lossless
    raster, with an alpha soft mask, on a page sized from ``dpi`` (default 72).
    Animated, vector-only or undecodable sources raise ImageFormatRefusal.
    """
    target = image_format(format)
    if quality is not None and target is not ImageFormat.JPEG:
        raise ImageFormatRefusal("quality applies only to JPEG output")
    level = jpeg_quality(quality)
    image = _decoded_raster(blob)
    try:
        source_ext = _image_extension_from_blob(blob)
    except ValueError:
        source_ext = None
    if quality is None and (target, source_ext) in (
        (ImageFormat.PNG, "png"),
        (ImageFormat.JPEG, "jpg"),
    ):
        return bytes(blob)
    if target is ImageFormat.PDF:
        return _image_pdf(blob, image.size, dpi or (72, 72))
    if target is ImageFormat.SVG:
        if source_ext in ("png", "jpg"):
            return _svg_wrapper(blob, "png" if source_ext == "png" else "jpeg", image.size)
        return _svg_wrapper(_encoded(_png_ready(image), "PNG", dpi), "png", image.size)
    if target is ImageFormat.JPEG:
        return _encoded(_opaque(image), "JPEG", dpi, quality=level)
    return _encoded(_png_ready(image), "PNG", dpi)


def _decoded_raster(blob: bytes) -> Any:
    from PIL import Image

    try:
        with Image.open(io.BytesIO(blob)) as decoded:
            if getattr(decoded, "n_frames", 1) != 1:
                raise ImageFormatRefusal("animated images cannot be re-encoded")
            decoded.load()
            return decoded.copy()
    except ImageFormatRefusal:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ImageFormatRefusal("image bytes cannot be decoded as a raster") from exc


def _encoded(image: Any, name: str, dpi: tuple[int, int] | None, **options: Any) -> bytes:
    stream = io.BytesIO()
    if dpi is not None:
        options["dpi"] = dpi
    image.save(stream, format=name, **options)
    return stream.getvalue()


def _png_ready(image: Any) -> Any:
    return image if image.mode in _PNG_MODES else image.convert("RGBA")


def _opaque(image: Any) -> Any:
    """Composite alpha over white: a JPEG carries no transparency."""
    from PIL import Image

    if image.mode in ("RGB", "L", "CMYK"):
        return image
    if image.mode == "1":
        return image.convert("L")
    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", rgba.size, (255, 255, 255))
    canvas.paste(rgba, mask=rgba.getchannel("A"))
    return canvas


def _svg_wrapper(payload: bytes, media: str, size: tuple[int, int]) -> bytes:
    width, height = size
    data = base64.b64encode(payload).decode("ascii")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<image width="{width}" height="{height}" '
        f'xlink:href="data:image/{media};base64,{data}"/></svg>\n'
    ).encode("ascii")


def _image_pdf(blob: bytes, size: tuple[int, int], dpi: tuple[int, int]) -> bytes:
    """One deterministic page holding the raster through WolfPPT's PDF writer."""
    pdf = commercial_module("render_pdf", "Saving an image as PDF")
    number = pdf._number

    width = number(size[0] * 72.0 / dpi[0])
    height = number(size[1] * 72.0 / dpi[1])
    writer = pdf._Writer()
    image, _ = pdf._image_objects(writer, SimpleNamespace(part="image", data=blob), {})
    content = writer.stream("", f"q {width} 0 0 {height} 0 0 cm /Im0 Do Q".encode("ascii"))
    pages = writer.reserve()
    page = writer.add(
        f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {width} {height}] "
        f"/Resources << /XObject << /Im0 {image} 0 R >> >> /Contents {content} 0 R >>".encode(
            "ascii"
        )
    )
    writer.put(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>".encode("ascii"))
    return writer.build(
        writer.add(f"<< /Type /Catalog /Pages {pages} 0 R >>".encode("ascii")), None
    )


class MediaFormat:
    """Writable playback settings for audio and movie shapes.

    Extension edits queue only the assigned control. Invalid extension values or
    unsafe source topology raise :class:`MediaControlRefusalError` without changing
    the cached controls or edit queue. Bookmarks and triggers accept immutable tuples
    of :class:`MediaBookmark` and :class:`MediaTrigger` values.

    New media triggers require explicit positive timing identifiers. Source
    ownership is checked at assignment; collisions with timing IDs allocated by
    other queued additions are checked during save, before staged output is
    published. Use a save/reload boundary when targeting newly allocated timing.

    ``volume_preset`` maps MUTE/LOW/MEDIUM/HIGH to 0/25/50/100 percent;
    non-preset numeric volume reads as None. The independent mute flag is
    preserved. ``start_mode`` uses PP_MEDIA_START_MODE and edits a saved
    package immediately: save pending edits first and reacquire shapes after
    assignment. Rendering stays static; playback settings do not alter posters.
    """

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

    @property
    def loop(self) -> bool:
        return bool(_media_playback(self._shape)["loop"])

    @loop.setter
    def loop(self, value: bool) -> None:
        _set_media_playback(self._shape, "loop", value)

    @property
    def play_across_slides(self) -> bool:
        return bool(_media_playback(self._shape)["play_across_slides"])

    @play_across_slides.setter
    def play_across_slides(self, value: bool) -> None:
        _set_media_playback(self._shape, "play_across_slides", value)

    @property
    def volume(self) -> int:
        return int(_media_playback(self._shape)["volume"])

    @volume.setter
    def volume(self, value: int) -> None:
        _set_media_playback(self._shape, "volume", value)

    @property
    def volume_preset(self) -> PP_MEDIA_VOLUME | None:
        """Exact named volume, or None for a custom numeric percentage."""
        try:
            return PP_MEDIA_VOLUME(self.volume)
        except ValueError:
            return None

    @volume_preset.setter
    def volume_preset(self, value: PP_MEDIA_VOLUME) -> None:
        if not isinstance(value, PP_MEDIA_VOLUME):
            raise MediaControlRefusalError("volume_preset must be PP_MEDIA_VOLUME")
        _set_media_playback(self._shape, "volume", int(value))

    @property
    def start_mode(self) -> PP_MEDIA_START_MODE:
        return PP_MEDIA_START_MODE(self._saved_start_mode())

    @start_mode.setter
    def start_mode(self, value: PP_MEDIA_START_MODE) -> None:
        if not isinstance(value, PP_MEDIA_START_MODE):
            raise MediaControlRefusalError("start_mode must be PP_MEDIA_START_MODE")
        self._saved_start_mode(value.value)

    def _saved_start_mode(self, mode: str | None = None) -> str:
        from .native_media import MediaStartModeRefusal, media_start_mode

        shape = self._shape
        try:
            return media_start_mode(
                shape._slide._presentation, shape._slide._index, shape.shape_id, mode=mode
            )
        except MediaStartModeRefusal as exc:
            raise MediaControlRefusalError(str(exc)) from exc

    @property
    def auto_play(self) -> bool:
        return bool(_media_playback(self._shape)["auto_play"])

    @auto_play.setter
    def auto_play(self, value: bool) -> None:
        _set_media_playback(self._shape, "auto_play", value)

    @property
    def mute(self) -> bool:
        """``p:cMediaNode@mute`` (ECMA-376 Part 1 19.5.9); default ``False``."""
        return _media_extension(self._shape)["mute"]

    @mute.setter
    def mute(self, value: Any) -> None:
        _set_media_extension(self._shape, "mute", value)

    @property
    def show_when_stopped(self) -> bool:
        """``p:cMediaNode@showWhenStopped``; default ``True``."""
        return _media_extension(self._shape)["show_when_stopped"]

    @show_when_stopped.setter
    def show_when_stopped(self, value: Any) -> None:
        _set_media_extension(self._shape, "show_when_stopped", value)

    @property
    def trim_start(self) -> float:
        """``p14:media/p14:trim@st`` in milliseconds ([MS-PPTX] CT_MediaTrim)."""
        return _media_extension(self._shape)["trim_start"]

    @trim_start.setter
    def trim_start(self, value: Any) -> None:
        _set_media_extension(self._shape, "trim_start", value)

    @property
    def trim_end(self) -> float:
        """``p14:media/p14:trim@end`` in milliseconds trimmed from the end."""
        return _media_extension(self._shape)["trim_end"]

    @trim_end.setter
    def trim_end(self, value: Any) -> None:
        _set_media_extension(self._shape, "trim_end", value)

    @property
    def fade_in(self) -> float:
        """``p14:media/p14:fade@in`` in milliseconds ([MS-PPTX] CT_MediaFade)."""
        return _media_extension(self._shape)["fade_in"]

    @fade_in.setter
    def fade_in(self, value: Any) -> None:
        _set_media_extension(self._shape, "fade_in", value)

    @property
    def fade_out(self) -> float:
        """``p14:media/p14:fade@out`` in milliseconds."""
        return _media_extension(self._shape)["fade_out"]

    @fade_out.setter
    def fade_out(self, value: Any) -> None:
        _set_media_extension(self._shape, "fade_out", value)

    @property
    def bookmarks(self) -> tuple[MediaBookmark, ...]:
        """``p14:media/p14:bmkLst/p14:bmk`` in document order."""
        return _media_extension(self._shape)["bookmarks"]

    @bookmarks.setter
    def bookmarks(self, value: Any) -> None:
        _set_media_extension(self._shape, "bookmarks", value)

    @property
    def triggers(self) -> tuple[MediaTrigger, ...]:
        """Start conditions governing this shape's media timing node.

        Conditions of the media node's own ``p:cTn`` come first, then those of each
        enclosing time node outward, each in document order.
        """
        return _media_extension(self._shape)["triggers"]

    @triggers.setter
    def triggers(self, value: Any) -> None:
        _set_media_extension(self._shape, "triggers", value)


class MediaControlRefusalError(ValueError):
    """An unsupported media assignment; no cache or queued edit was changed."""


@dataclass(frozen=True)
class MediaBookmark:
    """A named media bookmark; ``time`` is milliseconds from the media start."""

    name: str
    time: float


@dataclass(frozen=True)
class MediaTrigger:
    """One ``p:cond`` start condition (ECMA-376 Part 1 19.5.25).

    ``node_id`` is the ``p:cTn@id`` owning the condition; ``shape_id`` and
    ``bookmark`` come from ``p:tgtEl/p:spTgt``; ``time_node`` is ``p:tn@val``.
    """

    event: str | None
    delay: str | None
    node_id: str | None
    shape_id: str | None
    bookmark: str | None
    time_node: str | None


def _media_milliseconds(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MediaControlRefusalError(f"media {name} must be finite nonnegative milliseconds")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise MediaControlRefusalError(
            f"media {name} must be finite nonnegative milliseconds"
        ) from None
    if not math.isfinite(number) or number < 0:
        raise MediaControlRefusalError(f"media {name} must be finite nonnegative milliseconds")
    return number


def _media_identifier(name: str, value: Any) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdecimal()
        or len(value) > 10
    ):
        raise MediaControlRefusalError(f"media {name} must be a positive decimal identifier")
    if not 0 < int(value) <= 4294967295 or str(int(value)) != value:
        raise MediaControlRefusalError(
            f"media {name} must be a canonical positive 32-bit identifier"
        )
    return value


def _media_bookmark_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MediaControlRefusalError("media bookmark name must be a nonempty string")
    if any(
        not (
            character in "\t\n\r"
            or "\x20" <= character <= "\ud7ff"
            or "\ue000" <= character <= "\ufffd"
            or "\U00010000" <= character <= "\U0010ffff"
        )
        for character in value
    ):
        raise MediaControlRefusalError("media bookmark name contains an invalid XML character")
    return value


def _media_control_context(shape: Any) -> dict[str, Any]:
    """Read source topology without materializing or changing facade caches."""
    root = None
    if shape._slide.partname:
        try:
            with open_package_source(_shape_package_source(shape)) as package:
                root = ET.fromstring(package.read(shape._slide.partname))
        except (AttributeError, OSError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
            raise MediaControlRefusalError(
                "media source XML is unavailable for a safe edit"
            ) from error
        if root.tag != f"{{{P_NS}}}sld":
            raise MediaControlRefusalError(
                "strict or unsupported media source namespace is not writable"
            )
    elif not shape._payload.get("_pending_shape"):
        raise MediaControlRefusalError("media source slide is unavailable for a safe edit")
    shape_id = str(shape._payload.get("id", ""))
    _media_identifier("shape_id", shape_id)
    shape_elements: dict[str, ET.Element] = {}
    time_nodes: dict[str, ET.Element] = {}
    chain: list[ET.Element] = []
    media_node = None
    shape_element = None
    parents: dict[ET.Element, ET.Element] = {}
    if root is not None:
        parents = {child: parent for parent in root.iter() for child in parent}
        for properties in root.iter(f"{{{P_NS}}}cNvPr"):
            identifier = properties.attrib.get("id", "")
            if identifier in shape_elements:
                raise MediaControlRefusalError(
                    "media source contains ambiguous duplicate shape identifiers"
                )
            owner = parents.get(parents.get(properties))
            if owner is not None:
                shape_elements[identifier] = owner
        if not shape._payload.get("_pending_shape"):
            shape_element = _shape_xml_element(root, shape._payload)
            if shape_element is None or _shape_element_id(root, shape_element) != shape_id:
                raise MediaControlRefusalError("media source shape target is missing or ambiguous")
        for node in root.iter(f"{{{P_NS}}}cTn"):
            identifier = node.attrib.get("id", "")
            _media_identifier("source time node id", identifier)
            if identifier in time_nodes:
                raise MediaControlRefusalError(
                    "media source contains ambiguous duplicate time node identifiers"
                )
            time_nodes[identifier] = node
        matching = []
        for node in root.iter(f"{{{P_NS}}}cMediaNode"):
            targets = list(node.iterfind(f"{{{P_NS}}}tgtEl/{{{P_NS}}}spTgt"))
            if len(targets) != 1 or targets[0].attrib.get("spid") not in shape_elements:
                raise MediaControlRefusalError(
                    "media source contains a missing or ambiguous timing target"
                )
            if targets[0].attrib.get("spid") == shape_id:
                matching.append(node)
        if len(matching) > 1:
            raise MediaControlRefusalError(
                "media source contains multiple timing nodes for this shape"
            )
        if matching:
            media_node = matching[0]
            own = media_node.find(f"{{{P_NS}}}cTn")
            if own is None:
                raise MediaControlRefusalError("media timing node has no own cTn")
            chain.append(own)
            node = parents.get(media_node)
            while node is not None:
                if node.tag == f"{{{P_NS}}}cTn":
                    chain.append(node)
                node = parents.get(node)
        if shape_element is not None:
            extensions = list(shape_element.iter(f"{{{P14_NS}}}media"))
            if len(extensions) > 1:
                raise MediaControlRefusalError("media source contains ambiguous extension controls")
            if extensions:
                for tag in ("trim", "fade", "bmkLst"):
                    if len(extensions[0].findall(f"{{{P14_NS}}}{tag}")) > 1:
                        raise MediaControlRefusalError(
                            f"media source contains ambiguous {tag} controls"
                        )
    values = _media_extension_defaults()
    if root is not None and shape_element is not None:
        values.update(_media_extension_from_xml(root, shape_element))
    cached = shape._payload.get("_media_extension")
    if isinstance(cached, dict):
        values.update(cached)
    return {
        "root": root,
        "shape_id": shape_id,
        "shape_elements": shape_elements,
        "time_nodes": time_nodes,
        "chain": chain,
        "parents": parents,
        "values": values,
    }


def _media_shared_node(context: dict[str, Any], node: ET.Element) -> bool:
    parents = context["parents"]
    own = bool(context["chain"]) and node is context["chain"][0]
    subtree = parents.get(node) if own else node
    if subtree is None:
        return True
    if len(list(subtree.iter(f"{{{P_NS}}}cMediaNode"))) != 1:
        return True
    if any(element.tag in {f"{{{P_NS}}}cBhvr", f"{{{P_NS}}}cmd"} for element in subtree.iter()):
        return True
    for target in subtree.iter(f"{{{P_NS}}}spTgt"):
        ancestor = parents.get(target)
        while ancestor is not None and ancestor is not subtree:
            if ancestor.tag == f"{{{P_NS}}}cond":
                break
            ancestor = parents.get(ancestor)
        else:
            if target.attrib.get("spid") != context["shape_id"]:
                return True
    return False


def _media_current_playback(
    shape: Any, context: dict[str, Any] | None = None
) -> dict[str, bool | int]:
    playback = shape._payload.get("media_playback")
    if not isinstance(playback, dict):
        playback = {}
    normalized = {
        "loop": bool(playback.get("loop", False)),
        "play_across_slides": bool(playback.get("play_across_slides", False)),
        "volume": int(playback.get("volume", 80)),
        "auto_play": bool(playback.get("auto_play", False)),
    }
    if shape._payload.get("_media_playback_source_loaded") or shape._payload.get("_pending_shape"):
        return normalized
    root = None if context is None else context["root"]
    if context is None and shape._slide.partname:
        try:
            with open_package_source(_shape_package_source(shape)) as package:
                root = ET.fromstring(package.read(shape._slide.partname))
        except (AttributeError, OSError, KeyError, ET.ParseError, zipfile.BadZipFile):
            return normalized
    if root is None:
        return normalized
    timing = root.find(_ooxml_path(root, f"{{{P_NS}}}timing"))
    if timing is None:
        return normalized
    media_node = _shape_media_node(root, timing, str(shape._payload.get("id", "")))
    if media_node is None:
        return normalized
    own = media_node.find(_ooxml_path(root, f"{{{P_NS}}}cTn"))
    if own is not None:
        normalized["loop"] = own.attrib.get("repeatCount") == "indefinite"
    try:
        volume = round(int(media_node.attrib.get("vol", "80000")) / 1000)
    except ValueError:
        volume = 80
    normalized["volume"] = min(100, max(0, volume))
    try:
        normalized["play_across_slides"] = int(media_node.attrib.get("numSld", "1")) > 1
    except ValueError:
        normalized["play_across_slides"] = False
    # The established main-sequence parser owns auto_play; trigger delays do not
    # independently indicate that the Playback setting is Start Automatically.
    return normalized


def _queue_media_controls(
    shape: Any, playback: dict[str, bool | int], controls: dict[str, Any]
) -> None:
    shape._slide._presentation._queue_media_playback(
        shape._slide._index,
        _shape_picture_edit_ref(shape),
        bool(playback["loop"]),
        bool(playback["play_across_slides"]),
        int(playback["volume"]),
        bool(playback["auto_play"]),
        controls,
    )


def _media_trigger_bookmarks(shape: Any, context: dict[str, Any], shape_id: str) -> set[str]:
    if shape_id == context["shape_id"]:
        return {bookmark.name for bookmark in context["values"]["bookmarks"]}
    # Prefer another loaded media facade's accepted bookmark delta, if present.
    for sibling in shape._slide.shapes:
        if str(sibling._payload.get("id")) == shape_id:
            cached = sibling._payload.get("_media_extension")
            if isinstance(cached, dict):
                return {bookmark.name for bookmark in cached["bookmarks"]}
    element = context["shape_elements"].get(shape_id)
    if element is None:
        return set()
    return {bookmark.attrib.get("name", "") for bookmark in element.iter(f"{{{P14_NS}}}bmk")}


def _validate_media_triggers(
    shape: Any, context: dict[str, Any], value: Any
) -> tuple[MediaTrigger, ...]:
    if not isinstance(value, tuple) or not all(isinstance(item, MediaTrigger) for item in value):
        raise MediaControlRefusalError("media triggers must be a tuple of MediaTrigger values")
    for node in context["chain"]:
        lists = node.findall(f"{{{P_NS}}}stCondLst")
        if len(lists) > 1:
            raise MediaControlRefusalError("media source contains ambiguous start condition lists")
        for conditions in lists:
            if conditions.attrib:
                raise MediaControlRefusalError(
                    "media source contains unsupported start condition attributes"
                )
            for condition in conditions:
                if condition.tag != f"{{{P_NS}}}cond" or set(condition.attrib) - {"evt", "delay"}:
                    raise MediaControlRefusalError(
                        "media source contains unsupported start conditions"
                    )
                if condition.attrib.get("evt") not in {None, "onClick", "onBegin", "onEnd"}:
                    raise MediaControlRefusalError(
                        "media source contains unsupported trigger events"
                    )
                children = list(condition)
                if len(children) > 1:
                    raise MediaControlRefusalError(
                        "media source contains ambiguous trigger targets"
                    )
                for target in children:
                    if target.tag == f"{{{P_NS}}}tn":
                        if list(target) or set(target.attrib) != {"val"}:
                            raise MediaControlRefusalError(
                                "media source contains unsupported timing targets"
                            )
                    elif target.tag == f"{{{P_NS}}}tgtEl":
                        targets = list(target)
                        if target.attrib or len(targets) != 1:
                            raise MediaControlRefusalError(
                                "media source contains ambiguous shape targets"
                            )
                        shape_target = targets[0]
                        if (
                            shape_target.tag != f"{{{P_NS}}}spTgt"
                            or list(shape_target)
                            or set(shape_target.attrib) - {"spid", "bmkName"}
                        ):
                            raise MediaControlRefusalError(
                                "media source contains unsupported shape targets"
                            )
                    else:
                        raise MediaControlRefusalError(
                            "media source contains unsupported trigger targets"
                        )
    chain_ids = {node.attrib["id"] for node in context["chain"]}
    shared = [node for node in context["chain"] if _media_shared_node(context, node)]
    if any(node.find(f"{{{P_NS}}}stCondLst") is not None for node in shared):
        raise MediaControlRefusalError("media triggers cannot replace shared ancestor conditions")
    shape_ids = set(context["shape_elements"])
    shape_ids.update(str(sibling._payload.get("id")) for sibling in shape._slide.shapes)
    requested_ids = {_media_identifier("node_id", item.node_id) for item in value}
    requested_ids.discard(None)
    known_time_ids = set(context["time_nodes"]) | requested_ids
    normalized = []
    for item in value:
        if not isinstance(item.event, str) or item.event not in {"onClick", "onBegin", "onEnd"}:
            raise MediaControlRefusalError("media trigger event must be onClick, onBegin, or onEnd")
        node_id = _media_identifier("node_id", item.node_id)
        if node_id is None:
            if shape._payload.get("_pending_shape") or not context["chain"]:
                raise MediaControlRefusalError(
                    "media trigger node_id must be explicit for new media; "
                    "use a free positive identifier"
                )
            node_id = context["chain"][0].attrib["id"]
        if node_id in context["time_nodes"] and node_id not in chain_ids:
            raise MediaControlRefusalError(
                "media trigger node_id does not identify its own or ancestor wrapper"
            )
        if any(node.attrib["id"] == node_id for node in shared):
            raise MediaControlRefusalError("media trigger node_id identifies a shared wrapper")
        shape_id = _media_identifier("shape_id", item.shape_id)
        time_node = _media_identifier("time_node", item.time_node)
        if (shape_id is None) == (time_node is None):
            raise MediaControlRefusalError(
                "media trigger requires exactly one shape_id or time_node target"
            )
        if item.event == "onClick" and time_node is not None:
            raise MediaControlRefusalError("media onClick trigger requires a shape target")
        if shape_id is not None and shape_id not in shape_ids:
            raise MediaControlRefusalError("media trigger references an unknown shape_id")
        if time_node is not None:
            if time_node not in known_time_ids:
                raise MediaControlRefusalError("media trigger references an unknown time_node")
            if time_node == node_id or time_node in chain_ids or time_node in requested_ids:
                raise MediaControlRefusalError(
                    "media trigger contains a cyclic own or ancestor timing dependency"
                )
        bookmark = item.bookmark
        if bookmark is not None:
            bookmark = _media_bookmark_name(bookmark)
            if shape_id is None or bookmark not in _media_trigger_bookmarks(
                shape, context, shape_id
            ):
                raise MediaControlRefusalError(
                    "media trigger bookmark is missing from its shape target"
                )
        delay = item.delay
        if delay is not None:
            if not isinstance(delay, str):
                raise MediaControlRefusalError(
                    "media trigger delay must be a millisecond decimal string or None"
                )
            try:
                number = float(delay)
            except (ValueError, OverflowError):
                raise MediaControlRefusalError(
                    "media trigger delay must be finite nonnegative milliseconds"
                ) from None
            _media_milliseconds("trigger delay", number)
            if delay != delay.strip() or not delay:
                raise MediaControlRefusalError(
                    "media trigger delay must be a millisecond decimal string"
                )
        if (
            shape_id == context["shape_id"]
            and item.event in {"onBegin", "onEnd"}
            and bookmark is None
        ):
            raise MediaControlRefusalError("media trigger cannot depend on its own shape event")
        normalized.append(MediaTrigger(item.event, delay, node_id, shape_id, bookmark, time_node))
    # New wrappers sit between the own node and existing enclosing nodes.
    existing = [node.attrib["id"] for node in context["chain"]]
    created = list(
        dict.fromkeys(item.node_id for item in normalized if item.node_id not in chain_ids)
    )
    order = existing[:1] + created + existing[1:]
    ranks = [order.index(item.node_id) for item in normalized]
    if ranks != sorted(ranks):
        raise MediaControlRefusalError(
            "media triggers must list own conditions first, then enclosing wrappers outward"
        )
    return tuple(normalized)


def _set_media_extension(shape: Any, name: str, value: Any) -> None:
    if name in {"mute", "show_when_stopped"}:
        if not isinstance(value, bool):
            raise MediaControlRefusalError(f"media {name} must be bool")
    elif name in {"trim_start", "trim_end", "fade_in", "fade_out"}:
        value = _media_milliseconds(name, value)
    elif name == "bookmarks":
        if not isinstance(value, tuple) or not all(
            isinstance(item, MediaBookmark) for item in value
        ):
            raise MediaControlRefusalError(
                "media bookmarks must be a tuple of MediaBookmark values"
            )
        value = tuple(
            MediaBookmark(
                _media_bookmark_name(item.name), _media_milliseconds("bookmark time", item.time)
            )
            for item in value
        )
        if len({item.name for item in value}) != len(value):
            raise MediaControlRefusalError("media bookmark names must be unique")
    context = _media_control_context(shape)
    if name == "triggers":
        if value and _media_changed_controls(shape).get("auto_play") is True:
            raise MediaControlRefusalError("auto_play=True and explicit triggers are ambiguous")
        value = _validate_media_triggers(shape, context, value)
    elif name == "bookmarks":
        names = {item.name for item in value}
        for sibling in shape._slide.shapes:
            if sibling is shape:
                continue
            cached = sibling._payload.get("_media_extension")
            if isinstance(cached, dict) and any(
                trigger.shape_id == context["shape_id"]
                and trigger.bookmark is not None
                and trigger.bookmark not in names
                for trigger in cached["triggers"]
            ):
                raise MediaControlRefusalError(
                    "media bookmarks are still referenced by another media trigger"
                )
        for trigger in context["values"]["triggers"]:
            if (
                trigger.shape_id == context["shape_id"]
                and trigger.bookmark is not None
                and trigger.bookmark not in names
            ):
                raise MediaControlRefusalError(
                    "media bookmarks are still referenced by a retained trigger"
                )
        root = context["root"]
        if root is not None:
            for target in root.iter(f"{{{P_NS}}}spTgt"):
                if target.attrib.get("spid") == context["shape_id"]:
                    bookmark = target.attrib.get("bmkName")
                    if bookmark is not None and bookmark not in names:
                        # Own conditions replaced by an accepted trigger delta no longer apply.
                        node = context["parents"].get(target)
                        while node is not None and node.tag != f"{{{P_NS}}}cTn":
                            node = context["parents"].get(node)
                        cached = shape._payload.get("_media_extension")
                        if (
                            not isinstance(cached, dict)
                            or node not in context["chain"]
                            or "triggers" not in _media_changed_controls(shape)
                        ):
                            raise MediaControlRefusalError(
                                "media bookmarks are referenced by source timing conditions"
                            )
    serialized: Any = value
    if name == "bookmarks":
        serialized = [{"name": item.name, "time": item.time} for item in value]
    elif name == "triggers":
        serialized = [
            {
                "event": item.event,
                "delay": item.delay,
                "node_id": item.node_id,
                "shape_id": item.shape_id,
                "bookmark": item.bookmark,
                "time_node": item.time_node,
            }
            for item in value
        ]
    playback = _media_current_playback(shape, context)
    _queue_media_controls(shape, playback, {name: serialized})
    values = context["values"]
    values[name] = value
    shape._payload["_media_extension"] = values


def _media_changed_controls(shape: Any) -> dict[str, Any]:
    edits = shape._slide._presentation._media_playback_edits
    queued = edits.get((shape._slide._index, _shape_picture_edit_ref(shape)))
    return {} if queued is None or len(queued) < 5 else queued[4]


def _media_extension_defaults() -> dict[str, Any]:
    return {
        "mute": False,
        "show_when_stopped": True,
        "trim_start": 0.0,
        "trim_end": 0.0,
        "fade_in": 0.0,
        "fade_out": 0.0,
        "bookmarks": (),
        "triggers": (),
    }


def _media_extension(shape: Any) -> dict[str, Any]:
    cached = shape._payload.get("_media_extension")
    if isinstance(cached, dict):
        return cached
    values = _media_extension_defaults()
    if not shape._payload.get("_pending_shape") and shape._slide.partname:
        try:
            with open_package_source(_shape_package_source(shape)) as package:
                root = ET.fromstring(package.read(shape._slide.partname))
            shape_element = _shape_xml_element(root, shape._payload)
        except (
            AttributeError,
            FileNotFoundError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            shape_element = None
        if shape_element is not None:
            values.update(_media_extension_from_xml(root, shape_element))
    shape._payload["_media_extension"] = values
    return values


def _xml_float(element: ET.Element | None, attr: str) -> float:
    if element is None:
        return 0.0
    try:
        return float(element.attrib.get(attr, "0"))
    except ValueError:
        return 0.0


def _media_extension_from_xml(root: ET.Element, shape_element: ET.Element) -> dict[str, Any]:
    values: dict[str, Any] = {}
    media = None
    for extension in shape_element.iter(f"{{{P14_NS}}}media"):
        media = extension
        break
    if media is not None:
        trim = media.find(f"{{{P14_NS}}}trim")
        fade = media.find(f"{{{P14_NS}}}fade")
        values.update(
            trim_start=_xml_float(trim, "st"),
            trim_end=_xml_float(trim, "end"),
            fade_in=_xml_float(fade, "in"),
            fade_out=_xml_float(fade, "out"),
            bookmarks=tuple(
                MediaBookmark(bookmark.attrib.get("name", ""), _xml_float(bookmark, "time"))
                for bookmark in media.iterfind(f"{{{P14_NS}}}bmkLst/{{{P14_NS}}}bmk")
            ),
        )
    shape_id = str(_shape_element_id(root, shape_element))
    timing = root.find(_ooxml_path(root, f"{{{P_NS}}}timing"))
    if timing is None:
        return values
    parents = {child: parent for parent in timing.iter() for child in parent}
    media_node = _shape_media_node(root, timing, shape_id)
    if media_node is None:
        return values
    values["mute"] = media_node.attrib.get("mute") in {"1", "true"}
    values["show_when_stopped"] = media_node.attrib.get("showWhenStopped") not in {
        "0",
        "false",
    }
    triggers: list[MediaTrigger] = []
    time_node_tag = _ooxml_path(root, f"{{{P_NS}}}cTn")
    own = media_node.find(time_node_tag)
    chain = [] if own is None else [own]
    node = parents.get(media_node)
    while node is not None:
        if node.tag == time_node_tag:
            chain.append(node)
        node = parents.get(node)
    for time_node in chain:
        for condition in time_node.iterfind(
            _ooxml_path(root, f"{{{P_NS}}}stCondLst/{{{P_NS}}}cond")
        ):
            target = condition.find(_ooxml_path(root, f"{{{P_NS}}}tgtEl/{{{P_NS}}}spTgt"))
            time_target = condition.find(_ooxml_path(root, f"{{{P_NS}}}tn"))
            triggers.append(
                MediaTrigger(
                    event=condition.attrib.get("evt"),
                    delay=condition.attrib.get("delay"),
                    node_id=time_node.attrib.get("id"),
                    shape_id=None if target is None else target.attrib.get("spid"),
                    bookmark=None if target is None else target.attrib.get("bmkName"),
                    time_node=None if time_target is None else time_target.attrib.get("val"),
                )
            )
    values["triggers"] = tuple(triggers)
    return values


def _shape_element_id(root: ET.Element, shape_element: ET.Element) -> str | None:
    properties = shape_element.find(_ooxml_path(root, f".//{{{P_NS}}}cNvPr"))
    return None if properties is None else properties.attrib.get("id")


def _shape_media_node(root: ET.Element, timing: ET.Element, shape_id: str) -> ET.Element | None:
    media_tags = {
        _ooxml_path(root, f"{{{P_NS}}}audio"),
        _ooxml_path(root, f"{{{P_NS}}}video"),
    }
    node_tag = _ooxml_path(root, f"{{{P_NS}}}cMediaNode")
    target_path = _ooxml_path(root, f".//{{{P_NS}}}spTgt")
    for media in timing.iter():
        if media.tag not in media_tags:
            continue
        media_node = media.find(node_tag)
        if media_node is None:
            continue
        target = media_node.find(target_path)
        if target is not None and target.attrib.get("spid") == shape_id:
            return media_node
    return None


def _media_playback(shape: Any) -> dict[str, bool | int]:
    normalized = _media_current_playback(shape)
    shape._payload["media_playback"] = normalized
    shape._payload["_media_playback_source_loaded"] = True
    return normalized


def _set_media_playback(shape: Any, name: str, value: Any) -> None:
    if name == "volume":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"media volume must be an integer between 0 and 100, got {type(value).__name__}"
            )
        if not 0 <= value <= 100:
            raise ValueError("media volume must be between 0 and 100")
    elif not isinstance(value, bool):
        raise TypeError(f"media {name} must be bool, got {type(value).__name__}")
    is_video = shape._payload.get("kind") == "movie"
    if is_video and name == "play_across_slides" and value:
        raise MediaControlRefusalError(
            "play_across_slides is not supported for video: PowerPoint offers Play "
            "Across Slides for audio only and will not play a video that sets it"
        )
    context = _media_control_context(shape)
    playback = _media_current_playback(shape, context)
    playback[name] = value
    if is_video:
        playback["play_across_slides"] = False
    if playback["auto_play"] and _media_changed_controls(shape).get("triggers"):
        raise MediaControlRefusalError("auto_play=True and explicit triggers are ambiguous")
    if name == "auto_play" and any(
        _media_shared_node(context, node) and node.find(f"{{{P_NS}}}stCondLst") is not None
        for node in context["chain"]
    ):
        raise MediaControlRefusalError("media auto_play cannot replace shared ancestor conditions")
    # Preserve the established six-argument base queue contract.
    shape._slide._presentation._queue_media_playback(
        shape._slide._index,
        _shape_picture_edit_ref(shape),
        bool(playback["loop"]),
        bool(playback["play_across_slides"]),
        int(playback["volume"]),
        bool(playback["auto_play"]),
    )
    shape._payload["media_playback"] = playback
    shape._payload["_media_playback_source_loaded"] = True


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
        return PictureImage.from_package_source(_shape_package_source(shape), image_part)
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
    shape_id = shape.shape_id
    if shape_id is None:
        raise ValueError("picture identity is unavailable")
    shape._payload["_replacement_image_file"] = image_source
    shape._slide._presentation._queue_picture_replace(
        shape._slide._index,
        str(shape_id),
        image_source,
    )
    return replacement_image


def _shape_media_format(shape: Any) -> MediaFormat:
    if shape._payload.get("kind") not in {"audio", "movie"}:
        raise AttributeError("'Shape' object has no attribute 'media_format'")
    return MediaFormat(shape)


def _shape_media_type(shape: Any) -> Any:
    kind = shape._payload.get("kind")
    if kind not in {"audio", "movie"}:
        raise AttributeError("'Shape' object has no attribute 'media_type'")
    if kind == "audio":
        return getattr(PP_MEDIA_TYPE, "SOUND", "AUDIO")
    return PP_MEDIA_TYPE.MOVIE


def _shape_poster_frame(shape: Any) -> PictureImage:
    if shape._payload.get("kind") not in {"audio", "movie"}:
        raise AttributeError("'Shape' object has no attribute 'poster_frame'")
    poster_frame = shape._payload.get("_poster_frame_file")
    if poster_frame is not None:
        return PictureImage.from_image_input(poster_frame)
    image_part = _shape_image_partname(shape)
    if image_part is not None:
        return PictureImage.from_package_source(_shape_package_source(shape), image_part)
    raise AttributeError("media poster frame is unavailable")


def _set_picture_crop_value(shape: Any, key: str, value: Any) -> None:
    crop = _picture_crop(shape)
    coerced = _coerce_crop_fraction(value)
    if crop.get(key) == coerced:
        return
    from .shape_locks import check_shape_locks

    check_shape_locks(shape, "crop", "no_crop")
    crop[key] = coerced
    shape._payload["crop"] = crop
    shape._slide._presentation._queue_picture_crop(
        shape._slide._index,
        _shape_picture_edit_ref(shape),
        crop,
    )


def _shape_package_source(shape: Any) -> Path | InMemoryPackageSource:
    return shape._slide._presentation._source_path


def _shape_image_partname(shape: Any) -> str | None:
    if shape._payload.get("_image_part"):
        return str(shape._payload["_image_part"])
    relationship = _shape_image_relationship(shape)
    if relationship is None:
        return None
    _relationship_id, target = relationship
    return _resolve_package_target(shape._slide.partname, target)


def _shape_image_relationship_id(shape: Any) -> str | None:
    if shape._payload.get("_image_relationship_id"):
        return str(shape._payload["_image_relationship_id"])
    relationship = _shape_image_relationship(shape)
    return None if relationship is None else relationship[0]


def _shape_image_relationship(shape: Any) -> tuple[str, str] | None:
    """Return ``(relationship id, target)`` for the shape's image relationship.

    An explicit ``_image_relationship_id`` is trusted regardless of type;
    otherwise the first shape relationship typed ``.../image`` wins.
    """
    explicit_id = shape._payload.get("_image_relationship_id")
    candidates = (
        [str(explicit_id)]
        if explicit_id
        else [str(rid) for rid in shape._payload.get("relationship_ids") or []]
    )
    if not candidates or not shape._slide.partname:
        return None
    try:
        with open_package_source(_shape_package_source(shape)) as package:
            relationships = _package_relationships(package, shape._slide.partname)
    except (FileNotFoundError, zipfile.BadZipFile):
        return None
    for relationship_id in candidates:
        relationship = relationships.get(relationship_id)
        if relationship is None:
            continue
        relationship_type = relationship.attrib.get("Type", "")
        target = relationship.attrib.get("Target")
        if not relationship_type or not target:
            continue
        if explicit_id or relationship_type.endswith("/image"):
            return relationship_id, target
    return None


def _shape_has_crop(shape: Any) -> bool:
    return bool(shape.has_picture) or shape._payload.get("kind") == "movie"


def _normalized_dpi(value: float) -> int:
    try:
        dpi = round(float(value))
    except (TypeError, ValueError):
        return 72
    if dpi < 1 or dpi > 2048:
        return 72
    return dpi


def _shape_picture_crop(shape: Any) -> dict[str, float]:
    if not _shape_has_crop(shape) or not shape._slide.partname:
        return {"l": 0.0, "r": 0.0, "t": 0.0, "b": 0.0}
    try:
        with open_package_source(_shape_package_source(shape)) as package:
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
    return {key: int(src_rect.attrib.get(key, "0")) / 100000 for key in ("l", "r", "t", "b")}
