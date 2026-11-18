"""Source-bound background picture request parsing, validation, and safe publication.

This module provides a validated, source-bound request protocol for authoring slide
background pictures into presentations.  A request stretches the picture over the
slide unless it carries ``tile``: ``offset_x``/``offset_y`` (EMU), ``scale_x``/
``scale_y`` (fractions of the image's natural size), ``alignment`` (``tl``, ``t``,
``tr``, ``l``, ``ctr``, ``r``, ``bl``, ``b``, ``br``) and ``flip`` (a `TileMirrorMode`
or its token ``none``, ``x``, ``y``, ``xy``), which tiles it as ``a:tile``.  Validated
tiles return ``flip`` as a `TileMirrorMode`, and `read_background_picture_tile` reads
the tiling of a saved slide background back.  No claim of Office layout or
render equivalence is made.

Publication contract:
- The input presentation is opened from a private snapshot and is never modified.
- Output publication stages in a private directory beside the destination.
- Destinations that already exist, are symlinks, or match the input presentation are
  strictly refused before any mutation or publication.
- Publication uses an atomic hard link (os.link), guaranteeing that existing files
  are never clobbered and partially written packages are never exposed.
- If publication fails or is refused, the source deck and existing destination are
  left intact and absent/unmodified.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import posixpath
import re
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    TileMirrorMode,
    TileMirrorModeRefusal,
    blip_fill_tile,
    set_blip_fill_tile,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_REQUEST_KEYS = frozenset({"source_sha256", "slide_index", "image_path", "crop", "tile"})
_ALLOWED_CROP_KEYS = frozenset({"left", "top", "right", "bottom", "l", "t", "r", "b"})
_ALLOWED_TILE_KEYS = frozenset({"offset_x", "offset_y", "scale_x", "scale_y", "alignment", "flip"})
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE_DOCUMENT_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)


class BackgroundPictureRefusal(ValueError):
    """Raised when a background picture request is invalid or cannot be applied safely."""


class _BackgroundTileMirrorModeRefusal(BackgroundPictureRefusal, TileMirrorModeRefusal):
    """A background picture request named an unknown tile mirror mode."""


def _validate_crop(
    crop: tuple[float, float, float, float] | list[float] | Mapping[str, Any] | None,
) -> tuple[float, float, float, float]:
    """Validate and normalize crop fractions (left, top, right, bottom).

    Rejects non-numbers, boolean values, non-finite fractions (NaN/inf), negative
    values, values >= 1.0, and crops that leave empty visible area.
    """
    if crop is None:
        return (0.0, 0.0, 0.0, 0.0)

    if isinstance(crop, Mapping):
        unknown = sorted(set(crop) - _ALLOWED_CROP_KEYS)
        if unknown:
            raise BackgroundPictureRefusal(
                f"crop object contains unrecognized keys: {', '.join(unknown)}"
            )
        cl = crop.get("left", crop.get("l", 0.0))
        ct = crop.get("top", crop.get("t", 0.0))
        cr = crop.get("right", crop.get("r", 0.0))
        cb = crop.get("bottom", crop.get("b", 0.0))
    elif isinstance(crop, (tuple, list)):
        if len(crop) != 4:
            raise BackgroundPictureRefusal(
                "crop tuple/list must contain exactly 4 elements: (left, top, right, bottom)"
            )
        cl, ct, cr, cb = crop
    else:
        raise BackgroundPictureRefusal(
            f"crop must be a 4-element tuple/list or mapping, got {type(crop).__name__}"
        )

    fractions = [("left", cl), ("top", ct), ("right", cr), ("bottom", cb)]
    for name, val in fractions:
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise BackgroundPictureRefusal(f"crop fraction {name} must be a number, got {val!r}")
        if not math.isfinite(val):
            raise BackgroundPictureRefusal(f"crop fraction {name} must be finite, got {val!r}")
        if val < 0.0 or val >= 1.0:
            raise BackgroundPictureRefusal(
                f"crop fraction {name} must be in the range [0.0, 1.0), got {val}"
            )

    cl_f, ct_f, cr_f, cb_f = float(cl), float(ct), float(cr), float(cb)
    if cl_f + cr_f >= 1.0:
        raise BackgroundPictureRefusal(f"empty cropped area: left ({cl_f}) + right ({cr_f}) >= 1.0")
    if ct_f + cb_f >= 1.0:
        raise BackgroundPictureRefusal(f"empty cropped area: top ({ct_f}) + bottom ({cb_f}) >= 1.0")

    return (cl_f, ct_f, cr_f, cb_f)


def _validate_tile(tile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Validate picture tiling options into a complete settings mapping.

    ``None`` keeps the picture stretched. Omitted keys take the DrawingML
    defaults: no offset, 100 % scale, top-left alignment and no flip.
    """
    if tile is None:
        return None
    if not isinstance(tile, Mapping):
        raise BackgroundPictureRefusal(
            f"tile must be a mapping of tiling options, got {type(tile).__name__}"
        )
    unknown = sorted(set(tile) - _ALLOWED_TILE_KEYS)
    if unknown:
        raise BackgroundPictureRefusal(
            f"tile object contains unrecognized keys: {', '.join(unknown)}"
        )
    holder = ET.Element(f"{{{_A_NS}}}blipFill")
    try:
        set_blip_fill_tile(
            holder,
            offset_x=tile.get("offset_x", 0),
            offset_y=tile.get("offset_y", 0),
            scale_x=tile.get("scale_x", 1.0),
            scale_y=tile.get("scale_y", 1.0),
            alignment=tile.get("alignment", "tl"),
            flip=tile.get("flip", TileMirrorMode.NONE),
        )
    except TileMirrorModeRefusal as exc:
        raise _BackgroundTileMirrorModeRefusal(f"invalid tile: {exc}") from exc
    except ValueError as exc:
        raise BackgroundPictureRefusal(f"invalid tile: {exc}") from exc
    return blip_fill_tile(holder)


class BackgroundPictureRequest:
    """One validated, source-bound slide background picture authoring request."""

    __slots__ = ("_crop", "_image_path", "_slide_index", "_source_sha256", "_tile")

    def __init__(
        self,
        source_sha256: str,
        slide_index: int,
        image_path: str | Path,
        crop: tuple[float, float, float, float] | list[float] | Mapping[str, Any] = (
            0.0,
            0.0,
            0.0,
            0.0,
        ),
        tile: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(source_sha256, str) or not _SHA256_RE.fullmatch(source_sha256):
            raise BackgroundPictureRefusal(
                "source_sha256 must be a 64-character lowercase SHA-256 hexadecimal string"
            )

        if isinstance(slide_index, bool) or not isinstance(slide_index, int) or slide_index < 0:
            raise BackgroundPictureRefusal(
                "slide_index must be a non-negative integer (zero-based slide index)"
            )

        if isinstance(image_path, (str, Path)):
            path_str = str(image_path).strip()
            if not path_str:
                raise BackgroundPictureRefusal("image_path must be a non-empty path")
            img_path = Path(image_path)
        else:
            raise BackgroundPictureRefusal(
                f"image_path must be a str or Path, got {type(image_path).__name__}"
            )

        validated_crop = _validate_crop(crop)
        validated_tile = _validate_tile(tile)

        self._source_sha256: str = source_sha256
        self._slide_index: int = slide_index
        self._image_path: Path = img_path
        self._crop: tuple[float, float, float, float] = validated_crop
        self._tile: dict[str, Any] | None = validated_tile

    @property
    def source_sha256(self) -> str:
        return self._source_sha256

    @property
    def slide_index(self) -> int:
        return self._slide_index

    @property
    def image_path(self) -> Path:
        return self._image_path

    @property
    def crop(self) -> tuple[float, float, float, float]:
        return self._crop

    @property
    def tile(self) -> dict[str, Any] | None:
        """Tiling settings, or ``None`` when the picture is stretched."""
        return None if self._tile is None else dict(self._tile)

    @property
    def crop_left(self) -> float:
        return self._crop[0]

    @property
    def crop_top(self) -> float:
        return self._crop[1]

    @property
    def crop_right(self) -> float:
        return self._crop[2]

    @property
    def crop_bottom(self) -> float:
        return self._crop[3]

    def as_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "source_sha256": self._source_sha256,
            "slide_index": self._slide_index,
            "image_path": str(self._image_path),
            "crop": {
                "left": self._crop[0],
                "top": self._crop[1],
                "right": self._crop[2],
                "bottom": self._crop[3],
            },
        }
        if self._tile is not None:
            document["tile"] = dict(self._tile)
        return document

    def to_dict(self) -> dict[str, Any]:
        return self.as_dict()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BackgroundPictureRequest):
            return False
        return (
            self._source_sha256 == other._source_sha256
            and self._slide_index == other._slide_index
            and self._image_path == other._image_path
            and self._crop == other._crop
            and self._tile == other._tile
        )

    def __hash__(self) -> int:
        tile = None if self._tile is None else tuple(sorted(self._tile.items()))
        return hash((self._source_sha256, self._slide_index, self._image_path, self._crop, tile))

    def __repr__(self) -> str:
        return (
            f"BackgroundPictureRequest(source_sha256={self._source_sha256!r}, "
            f"slide_index={self._slide_index!r}, image_path={self._image_path!r}, "
            f"crop={self._crop!r}" + ("" if self._tile is None else f", tile={self._tile!r}") + ")"
        )


def load_background_picture_request(path: str | Path) -> dict[str, Any]:
    """Read and parse one background picture JSON request document from disk."""
    req_path = Path(path).expanduser()
    if not req_path.is_file():
        raise BackgroundPictureRefusal(f"request file does not exist: {req_path}")
    try:
        content = req_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BackgroundPictureRefusal(f"cannot read request file ({req_path}): {exc}") from exc
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise BackgroundPictureRefusal(
            f"request file is not valid JSON ({req_path}): {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise BackgroundPictureRefusal(
            f"request document must be a JSON object, got {type(data).__name__}"
        )
    return data


def parse_background_picture_request(
    document: Mapping[str, Any],
    base_dir: str | Path | None = None,
) -> BackgroundPictureRequest:
    """Validate one background picture request document into a typed request."""
    if not isinstance(document, Mapping):
        raise BackgroundPictureRefusal(
            f"request document must be a mapping, got {type(document).__name__}"
        )

    unknown = sorted(set(document) - _ALLOWED_REQUEST_KEYS)
    if unknown:
        raise BackgroundPictureRefusal(
            f"background picture request does not accept unexpected field(s): {', '.join(unknown)}"
        )

    missing = [
        key
        for key in ("source_sha256", "slide_index", "image_path")
        if key not in document or document[key] is None
    ]
    if missing:
        raise BackgroundPictureRefusal(
            f"background picture request missing required field(s): {', '.join(missing)}"
        )

    raw_image_path = document["image_path"]
    if isinstance(raw_image_path, (str, Path)):
        path_str = str(raw_image_path).strip()
        if not path_str:
            raise BackgroundPictureRefusal("image_path must be a non-empty path")
        img_path = Path(raw_image_path)
    else:
        raise BackgroundPictureRefusal(
            f"image_path must be a str or Path, got {type(raw_image_path).__name__}"
        )

    if not img_path.is_absolute() and base_dir is not None:
        img_path = (Path(base_dir).expanduser() / img_path).resolve()
    else:
        img_path = img_path.expanduser()

    crop = document.get("crop")

    return BackgroundPictureRequest(
        source_sha256=document["source_sha256"],
        slide_index=document["slide_index"],
        image_path=img_path,
        crop=crop,
        tile=document.get("tile"),
    )


def ensure_publishable_paths(source: Path, destination: Path) -> None:
    """Refuse a source/destination pair that cannot be published safely."""
    if not source.is_file():
        raise BackgroundPictureRefusal(f"source presentation does not exist: {source}")
    if destination.is_symlink():
        raise BackgroundPictureRefusal(
            f"destination {destination} is a symbolic link; "
            "background picture publication refuses to follow links"
        )
    if destination.exists():
        raise BackgroundPictureRefusal(
            f"destination {destination} already exists; "
            "background picture publication never overwrites an existing file"
        )
    if source.resolve() == destination.resolve():
        raise BackgroundPictureRefusal(
            f"destination {destination} matches source deck; in-place modification is refused"
        )
    if not destination.parent.is_dir():
        raise BackgroundPictureRefusal(
            f"destination directory does not exist: {destination.parent}"
        )


def _apply_background_picture_request(
    presentation_path: str | Path,
    request: BackgroundPictureRequest | Mapping[str, Any],
    output_path: str | Path,
) -> dict[str, Any]:
    """Apply one validated background picture request and return publication metadata."""
    source = Path(presentation_path).expanduser()
    destination = Path(output_path).expanduser()

    ensure_publishable_paths(source, destination)

    if isinstance(request, BackgroundPictureRequest):
        req = request
    elif isinstance(request, Mapping):
        req = parse_background_picture_request(request)
    else:
        raise BackgroundPictureRefusal(
            f"request must be BackgroundPictureRequest or mapping, got {type(request).__name__}"
        )

    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != req.source_sha256:
        raise BackgroundPictureRefusal(
            f"source digest mismatch for {source}: "
            f"expected {req.source_sha256}, got {source_sha256}"
        )

    if not req.image_path.is_file():
        raise BackgroundPictureRefusal(f"image file does not exist: {req.image_path}")

    try:
        image_bytes = req.image_path.read_bytes()
    except OSError as exc:
        raise BackgroundPictureRefusal(f"cannot read image file {req.image_path}: {exc}") from exc
    image_sha256 = hashlib.sha256(image_bytes).hexdigest()

    with tempfile.TemporaryDirectory(
        prefix=".wolfppt-bgpicture-",
        dir=destination.parent,
    ) as temp_dir:
        staging_dir = Path(temp_dir)
        snapshot_deck = staging_dir / f"source{source.suffix or '.pptx'}"
        snapshot_deck.write_bytes(source_bytes)

        from .presentation import Presentation

        prs = Presentation(snapshot_deck)
        slides = list(prs.slides)
        if req.slide_index < 0 or req.slide_index >= len(slides):
            raise BackgroundPictureRefusal(
                f"slide_index {req.slide_index} is out of range; "
                f"presentation has {len(slides)} slides"
            )
        slide = slides[req.slide_index]

        cl, ct, cr, cb = req.crop
        slide.background.fill.picture(
            image_bytes,
            crop_left=cl,
            crop_top=ct,
            crop_right=cr,
            crop_bottom=cb,
        )

        staged_output = staging_dir / destination.name
        prs.save(staged_output)
        if req.tile is not None:
            _tile_slide_background(staged_output, req.slide_index, req.tile)
        output_sha256 = hashlib.sha256(staged_output.read_bytes()).hexdigest()

        if hashlib.sha256(source.read_bytes()).hexdigest() != source_sha256:
            raise BackgroundPictureRefusal(
                f"source deck {source} changed while background picture was being staged; "
                "nothing was published"
            )

        if destination.exists() or destination.is_symlink():
            raise BackgroundPictureRefusal(
                f"destination {destination} already exists; publication never clobbers"
            )

        try:
            os.link(staged_output, destination)
        except FileExistsError as exc:
            raise BackgroundPictureRefusal(
                f"output {destination} already exists; "
                "background picture authoring never overwrites a destination"
            ) from exc
        except OSError as exc:
            raise BackgroundPictureRefusal(
                f"output {destination} cannot be published atomically: this filesystem "
                f"does not support hard-link publication ({exc.strerror or exc}); "
                "choose a destination on a filesystem that does"
            ) from exc

    return {
        "crop": req.crop,
        "tile": req.tile,
        "destination": destination,
        "image_path": req.image_path,
        "image_sha256": image_sha256,
        "output_sha256": output_sha256,
        "slide_index": req.slide_index,
        "source_sha256": source_sha256,
    }


def _tile_slide_background(package_path: Path, slide_index: int, tile: Mapping[str, Any]) -> None:
    """Switch the background picture of one slide in ``package_path`` to tiling."""
    with zipfile.ZipFile(package_path) as package:
        entries = [(info, package.read(info.filename)) for info in package.infolist()]
    parts = {info.filename: data for info, data in entries}
    slide_part = _slide_part_names(parts)[slide_index]
    namespaces = {
        prefix: uri
        for _event, (prefix, uri) in ET.iterparse(
            io.BytesIO(parts[slide_part]), events=("start-ns",)
        )
    }
    root = ET.fromstring(parts[slide_part])
    fill = root.find(f"{{{_P_NS}}}cSld/{{{_P_NS}}}bg/{{{_P_NS}}}bgPr/{{{_A_NS}}}blipFill")
    if fill is None:
        raise BackgroundPictureRefusal(
            f"slide {slide_index} background has no picture fill to tile"
        )
    set_blip_fill_tile(fill, **tile)
    for prefix, uri in namespaces.items():
        if prefix and not re.fullmatch(r"ns\d+", prefix):
            ET.register_namespace(prefix, uri)
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    staged = package_path.with_name(package_path.name + ".tile")
    with zipfile.ZipFile(staged, "w") as package:
        for info, data in entries:
            package.writestr(info, payload if info.filename == slide_part else data)
    os.replace(staged, package_path)


def read_background_picture_tile(
    presentation_path: str | Path, slide_index: int
) -> dict[str, Any] | None:
    """Read the tiling of one saved slide's background picture.

    Returns the settings a request takes (``flip`` as a `TileMirrorMode`), or
    ``None`` when the slide background is not a tiled picture.
    """
    if isinstance(slide_index, bool) or not isinstance(slide_index, int) or slide_index < 0:
        raise BackgroundPictureRefusal(
            "slide_index must be a non-negative integer (zero-based slide index)"
        )
    with zipfile.ZipFile(Path(presentation_path).expanduser()) as package:
        parts = {name: package.read(name) for name in package.namelist()}
    slide_parts = _slide_part_names(parts)
    if slide_index >= len(slide_parts):
        raise BackgroundPictureRefusal(
            f"slide_index {slide_index} is out of range; presentation has {len(slide_parts)} slides"
        )
    fill = ET.fromstring(parts[slide_parts[slide_index]]).find(
        f"{{{_P_NS}}}cSld/{{{_P_NS}}}bg/{{{_P_NS}}}bgPr/{{{_A_NS}}}blipFill"
    )
    return None if fill is None else blip_fill_tile(fill)


def _slide_part_names(parts: Mapping[str, bytes]) -> list[str]:
    root_rels = ET.fromstring(parts["_rels/.rels"])
    presentation_part = next(
        rel.get("Target", "").lstrip("/")
        for rel in root_rels.findall(f"{{{_PKG_REL_NS}}}Relationship")
        if rel.get("Type") == _OFFICE_DOCUMENT_REL
    )
    presentation_dir = PurePosixPath(presentation_part).parent
    rels_part = str(presentation_dir / "_rels" / f"{PurePosixPath(presentation_part).name}.rels")
    targets = {
        rel.get("Id"): rel.get("Target", "")
        for rel in ET.fromstring(parts[rels_part]).findall(f"{{{_PKG_REL_NS}}}Relationship")
    }
    presentation = ET.fromstring(parts[presentation_part])
    names = []
    for slide_id in presentation.findall(f"{{{_P_NS}}}sldIdLst/{{{_P_NS}}}sldId"):
        target = targets[slide_id.get(f"{{{_R_NS}}}id")]
        if target.startswith("/"):
            names.append(target.lstrip("/"))
        else:
            names.append(posixpath.normpath(str(presentation_dir / target)))
    return names


def apply_background_picture_request(
    presentation_path: str | Path,
    request: BackgroundPictureRequest | Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    """Apply one validated background picture request using safe atomic publication.

    The source presentation is opened from a private snapshot and is never modified.
    Destination must be a non-existent regular file on a filesystem supporting
    atomic publication.
    """
    publication = _apply_background_picture_request(
        presentation_path=presentation_path,
        request=request,
        output_path=output_path,
    )
    return publication["destination"]


__all__ = [
    "BackgroundPictureRefusal",
    "BackgroundPictureRequest",
    "TileMirrorMode",
    "TileMirrorModeRefusal",
    "apply_background_picture_request",
    "ensure_publishable_paths",
    "load_background_picture_request",
    "parse_background_picture_request",
    "read_background_picture_tile",
]
