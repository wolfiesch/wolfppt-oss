"""Saved-presentation image assets and SVG pictures with explicit raster fallback.

Use ``ImageCollection(presentation)`` to add, find and replace embedded images.
Mutations use the presentation's transactional package rewrite, then persist with
ordinary ``presentation.save(destination)``. Save pending facade edits first and
reacquire slide/shape handles after a rewrite. Raster replacement affects every
consumer of the selected part; ``edit_svg_picture`` isolates one picture instead.
SVG bytes remain vector assets for readers that support them. WolfPPT renders the
caller-supplied fallback; this API does not rasterize SVG or verify its visual
agreement with that fallback. No external resources or active SVG are admitted.

Timed, multi-frame GIFs retain their exact authored bytes on add/replace/save.
``PresentationImage.animation`` exposes their validated ``AnimatedRaster``
metadata; static rasters and SVG assets return ``None``. GIF frame timing and
loop/disposal semantics follow ``render_image_frames``. Every frame is validated
before a package rewrite, while SVG fallbacks remain strictly static rasters.
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .image_inputs import image_input_bytes
from .package_parts import (
    A_NS,
    CONTENT_TYPES_NS,
    P_NS,
    PKG_REL_NS,
    R_NS,
    open_package_source,
    rels_part_for_package_part,
)
from .presentation_tags import parse_xml, serialize_xml
from .render_image_frames import AnimatedRaster, AnimatedRasterRefusal, raster_animation
from .shape_picture_inspection import PictureImage, SvgPictureRefusal, inspect_svg_picture

SVG_NS = "http://www.w3.org/2000/svg"
SVG_BLIP_NS = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
SVG_CONTENT_TYPE = "image/svg+xml"
IMAGE_REL_TYPE = f"{R_NS}/image"
SVG_EXT_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"


class ImageCollectionRefusal(ValueError):
    """An image operation cannot preserve package or raster semantics safely."""


@dataclass(frozen=True)
class PresentationImage:
    """Exact embedded asset bytes, including assets not yet placed on a slide."""

    partname: str
    blob: bytes
    content_type: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.blob).hexdigest()

    @property
    def image(self) -> PictureImage:
        return PictureImage(
            self.blob,
            content_type=self.content_type,
            fallback_ext=Path(self.partname).suffix.lstrip("."),
        )

    @property
    def animation(self) -> AnimatedRaster | None:
        """Validated timed GIF metadata, or ``None`` for a static image or SVG."""
        return None if self.content_type == SVG_CONTENT_TYPE else raster_animation(self.blob)


def _bytes(data: Any) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, PictureImage):
        return data.blob
    try:
        return image_input_bytes(data)
    except (TypeError, ValueError, OSError) as exc:
        raise ImageCollectionRefusal(
            "image input must be bytes, a PictureImage, a path or a binary stream"
        ) from exc


def _raster(data: Any, *, static_only: bool = False) -> tuple[bytes, str, str]:
    blob = _bytes(data)
    try:
        animation = raster_animation(blob)
        if static_only and animation is not None:
            raise ImageCollectionRefusal(
                "SVG fallback must be static; animated raster is unsupported"
            )
        image = PictureImage.from_blob(blob)
        ext, content_type = image.ext, image.content_type
    except (ValueError, OSError) as exc:
        if isinstance(exc, ImageCollectionRefusal):
            raise
        if isinstance(exc, AnimatedRasterRefusal):
            raise ImageCollectionRefusal(str(exc)) from exc
        raise ImageCollectionRefusal("unsupported or corrupt raster image") from exc
    return blob, content_type, ext


def _svg(data: Any) -> bytes:
    blob = _bytes(data)
    try:
        text = blob.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SvgPictureRefusal("SVG input must be UTF-8") from exc
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise SvgPictureRefusal("SVG DTDs and entities are unsupported")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SvgPictureRefusal("invalid SVG XML") from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise SvgPictureRefusal("SVG input needs an svg root in the SVG namespace")
    elements = {
        "svg",
        "g",
        "defs",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "path",
        "text",
        "tspan",
        "linearGradient",
        "radialGradient",
        "stop",
        "clipPath",
        "mask",
        "title",
        "desc",
        "use",
    }
    attributes = {
        "id",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "width",
        "height",
        "viewBox",
        "preserveAspectRatio",
        "version",
        "d",
        "points",
        "transform",
        "fill",
        "fill-opacity",
        "fill-rule",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "opacity",
        "clip-path",
        "clip-rule",
        "mask",
        "gradientUnits",
        "gradientTransform",
        "spreadMethod",
        "offset",
        "stop-color",
        "stop-opacity",
        "font-family",
        "font-size",
        "font-weight",
        "font-style",
        "text-anchor",
        "dx",
        "dy",
        "href",
    }
    expanded_elements = {f"{{{SVG_NS}}}{name}" for name in elements}
    for node in root.iter():
        if node.tag not in expanded_elements:
            raise SvgPictureRefusal(f"unsupported SVG element {node.tag!r}")
        for key, value in node.attrib.items():
            local = key.rsplit("}", 1)[-1]
            if key.startswith("{") and key != "{http://www.w3.org/1999/xlink}href":
                raise SvgPictureRefusal(f"unsupported SVG attribute {key!r}")
            if local not in attributes:
                raise SvgPictureRefusal(f"unsupported SVG attribute {key!r}")
            if local == "href" and not re.fullmatch(r"#[A-Za-z_][\w.-]*", value):
                raise SvgPictureRefusal("SVG external references are unsupported")
            if "url" in value.lower() and not re.fullmatch(r"url\(#[A-Za-z_][\w.-]*\)", value):
                raise SvgPictureRefusal("SVG external paint resources are unsupported")
    return blob


def _assets(package: Any) -> tuple[PresentationImage, ...]:
    types = parse_xml(package.read("[Content_Types].xml"), read_only=True)
    defaults = {
        n.get("Extension"): n.get("ContentType", "") for n in types if n.tag.endswith("}Default")
    }
    overrides = {
        n.get("PartName", "").lstrip("/"): n.get("ContentType", "")
        for n in types
        if n.tag.endswith("}Override")
    }
    result = []
    for name in package.namelist():
        content_type = overrides.get(name, defaults.get(Path(name).suffix.lstrip("."), ""))
        if content_type.startswith("image/"):
            result.append(PresentationImage(name, package.read(name), content_type))
    return tuple(result)


def _add_asset(
    package: Any, replacements: dict[str, bytes], blob: bytes, content_type: str, ext: str
) -> str:
    # Reuse exact assets, never a digest alone. Existing bytes can be replaced in
    # the same transaction, so inspect the effective replacement payload too.
    for asset in _assets(package):
        if (
            asset.content_type == content_type
            and replacements.get(asset.partname, asset.blob) == blob
        ):
            return asset.partname
    for name, payload in replacements.items():
        if name.startswith("ppt/media/") and name.endswith(f".{ext}") and payload == blob:
            return name
    names = set(package.namelist()) | set(replacements)
    index = 1
    while f"ppt/media/image{index}.{ext}" in names:
        index += 1
    part = f"ppt/media/image{index}.{ext}"
    replacements[part] = blob
    types = parse_xml(replacements.get("[Content_Types].xml", package.read("[Content_Types].xml")))
    ET.SubElement(
        types,
        f"{{{CONTENT_TYPES_NS}}}Override",
        {"PartName": f"/{part}", "ContentType": content_type},
    )
    replacements["[Content_Types].xml"] = serialize_xml(types)
    return part


def _relationship(rels: ET.Element, slide_part: str, image_part: str) -> str:
    ids = {node.get("Id") for node in rels}
    index = 1
    while f"rId{index}" in ids:
        index += 1
    rid = f"rId{index}"
    ET.SubElement(
        rels,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": rid,
            "Type": IMAGE_REL_TYPE,
            "Target": posixpath.relpath(image_part, posixpath.dirname(slide_part)),
        },
    )
    return rid


class ImageCollection(Sequence[PresentationImage]):
    """Presentation-wide image parts, including SVGs, backgrounds and unused assets.

    ``find(data)`` matches exact bytes. ``replace(partname, data)`` preserves the
    raster content type and all relationships, changing every use of that part.
    For an SVG use ``edit_svg_picture`` with both vector and fallback inputs.
    ``add_picture`` places an asset on a saved slide by its zero-based index.
    ``add_svg_picture`` and ``edit_svg_picture`` require an explicit static raster
    fallback. SVG markup outside the passive subset raises SvgPictureRefusal.
    """

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation

    def _snapshot(self) -> tuple[PresentationImage, ...]:
        prs = self._presentation
        with prs._mutation_lock:
            try:
                prs._require_saved_package("listing images")
                with open_package_source(prs._source_path) as package:
                    return _assets(package)
            except ValueError as exc:
                raise ImageCollectionRefusal(str(exc)) from exc

    def __len__(self) -> int:
        return len(self._snapshot())

    def __getitem__(self, index: int | slice) -> Any:
        return self._snapshot()[index]

    def __iter__(self) -> Iterator[PresentationImage]:
        return iter(self._snapshot())

    def find(self, data: Any) -> tuple[PresentationImage, ...]:
        blob = _bytes(data)
        return tuple(asset for asset in self if asset.blob == blob)

    def get(self, partname: str) -> PresentationImage:
        normalized = partname.lstrip("/")
        for asset in self:
            if asset.partname == normalized:
                return asset
        raise ImageCollectionRefusal(f"no image part {partname!r}")

    def _rewrite(self, operation: str, plan: Any) -> Any:
        prs = self._presentation
        with prs._mutation_lock:
            try:
                prs._require_saved_package(operation)
                prs._validate_required_namespaces()
                return prs._rewrite_package(operation, plan)
            except ValueError as exc:
                if isinstance(exc, (ImageCollectionRefusal, SvgPictureRefusal)):
                    raise
                raise ImageCollectionRefusal(str(exc)) from exc

    def add(self, data: Any) -> PresentationImage:
        """Add a validated static raster or timed GIF without placing a shape."""
        blob, content_type, ext = _raster(data)

        def plan(package: Any) -> Any:
            replacements: dict[str, bytes] = {}
            part = _add_asset(package, replacements, blob, content_type, ext)
            if part not in package.namelist():
                # Retain collection-only assets through the OPC root so adding
                # an image does not create an unreachable package part.
                rels = parse_xml(package.read("_rels/.rels"))
                _relationship(rels, "", part)
                replacements["_rels/.rels"] = serialize_xml(rels)
            return replacements, set(), part

        return self.get(self._rewrite("adding an image", plan))

    def replace(self, partname: str, data: Any) -> PresentationImage:
        """Replace a raster part globally; changing its content type is refused."""
        blob, content_type, _ = _raster(data)
        normalized = partname.lstrip("/")

        def plan(package: Any) -> Any:
            asset = next((a for a in _assets(package) if a.partname == normalized), None)
            if asset is None:
                raise ImageCollectionRefusal(f"no image part {partname!r}")
            if asset.content_type != content_type:
                raise ImageCollectionRefusal(
                    "replacement raster content type must match; use edit_svg_picture for SVG"
                )
            return {normalized: blob}, set(), normalized

        return self.get(self._rewrite("replacing an image", plan))

    def add_picture(
        self, slide_index: int, partname: str, *, left: int, top: int, width: int, height: int
    ) -> Any:
        """Place a raster asset, with geometry in EMUs, on one saved slide."""
        asset = self.get(partname)
        if asset.content_type == SVG_CONTENT_TYPE:
            raise SvgPictureRefusal("SVG placement requires a raster fallback")
        raster = _raster(asset.blob)
        return self._picture(slide_index, (left, top, width, height), raster, None, None)

    def add_svg_picture(
        self,
        slide_index: int,
        svg: Any,
        *,
        raster_fallback: Any,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> Any:
        """Author a vector picture plus its explicitly supplied raster fallback."""
        vector = _svg(svg)
        raster = _raster(raster_fallback, static_only=True)
        return self._picture(slide_index, (left, top, width, height), raster, vector, None)

    def edit_svg_picture(self, shape: Any, svg: Any, *, raster_fallback: Any) -> Any:
        """Replace both representations of one SVG picture without changing peers."""
        if shape._slide._presentation is not self._presentation:
            raise SvgPictureRefusal("shape belongs to another presentation")
        inspect_svg_picture(shape)
        vector, raster = _svg(svg), _raster(raster_fallback, static_only=True)
        part, shape_id = shape._slide.partname, str(shape.shape_id)
        slide_index = next(
            (i for i, slide in enumerate(self._presentation.slides) if slide.partname == part), None
        )
        if slide_index is None:
            raise SvgPictureRefusal("SVG picture slide is unavailable")
        return self._picture(slide_index, None, raster, vector, shape_id)

    def _picture(
        self,
        slide_index: int,
        box: Any,
        raster: tuple[bytes, str, str],
        vector: bytes | None,
        shape_id: str | None,
    ) -> Any:
        if (
            isinstance(slide_index, bool)
            or not isinstance(slide_index, int)
            or not 0 <= slide_index < len(self._presentation.slides)
        ):
            raise ImageCollectionRefusal("slide index must identify an existing slide")
        if box is not None and (
            any(isinstance(v, bool) or not isinstance(v, int) for v in box)
            or box[2] <= 0
            or box[3] <= 0
        ):
            raise ImageCollectionRefusal(
                "picture geometry needs integer EMUs and positive width and height"
            )
        slide_part = self._presentation.slides[slide_index].partname

        def plan(package: Any) -> Any:
            replacements: dict[str, bytes] = {}
            root = parse_xml(package.read(slide_part))
            # Strict namespace authoring is deliberately refused, not mixed with
            # Transitional elements. Existing strict decks remain readable.
            if root.tag != f"{{{P_NS}}}sld":
                raise ImageCollectionRefusal("picture authoring requires Transitional slide XML")
            tree = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
            if tree is None:
                raise ImageCollectionRefusal("slide has no shape tree")
            rel_part = rels_part_for_package_part(slide_part)
            rels = (
                parse_xml(package.read(rel_part))
                if rel_part in package.namelist()
                else ET.Element(f"{{{PKG_REL_NS}}}Relationships")
            )
            if shape_id is not None:
                pictures = [
                    p
                    for p in tree.iter(f"{{{P_NS}}}pic")
                    if (n := p.find(f"{{{P_NS}}}nvPicPr/{{{P_NS}}}cNvPr")) is not None
                    and n.get("id") == shape_id
                ]
                if len(pictures) != 1:
                    raise SvgPictureRefusal("SVG picture identity is unavailable or ambiguous")
                picture = pictures[0]
                blip = picture.find(f"{{{P_NS}}}blipFill/{{{A_NS}}}blip")
                if (
                    blip is None
                    or blip.find(f"{{{A_NS}}}extLst/{{{A_NS}}}ext/{{{SVG_BLIP_NS}}}svgBlip") is None
                ):
                    raise SvgPictureRefusal("shape is not an SVG picture")
                if blip.get(f"{{{R_NS}}}link") is not None:
                    raise SvgPictureRefusal("linked SVG pictures are unsupported")
                identifier = shape_id
            else:
                ids = [int(n.get("id", "0")) for n in tree.iter(f"{{{P_NS}}}cNvPr")]
                identifier = str(max(ids, default=0) + 1)
                picture = ET.Element(f"{{{P_NS}}}pic")
                nv = ET.SubElement(picture, f"{{{P_NS}}}nvPicPr")
                ET.SubElement(
                    nv, f"{{{P_NS}}}cNvPr", {"id": identifier, "name": f"Picture {identifier}"}
                )
                ET.SubElement(nv, f"{{{P_NS}}}cNvPicPr")
                ET.SubElement(nv, f"{{{P_NS}}}nvPr")
                fill = ET.SubElement(picture, f"{{{P_NS}}}blipFill")
                blip = ET.SubElement(fill, f"{{{A_NS}}}blip")
                ET.SubElement(ET.SubElement(fill, f"{{{A_NS}}}stretch"), f"{{{A_NS}}}fillRect")
                props = ET.SubElement(picture, f"{{{P_NS}}}spPr")
                transform = ET.SubElement(props, f"{{{A_NS}}}xfrm")
                ET.SubElement(transform, f"{{{A_NS}}}off", {"x": str(box[0]), "y": str(box[1])})
                ET.SubElement(transform, f"{{{A_NS}}}ext", {"cx": str(box[2]), "cy": str(box[3])})
                ET.SubElement(
                    ET.SubElement(props, f"{{{A_NS}}}prstGeom", {"prst": "rect"}),
                    f"{{{A_NS}}}avLst",
                )
                # Keep any trailing extension list in its schema position.
                tail = tree.find(f"{{{P_NS}}}extLst")
                tree.insert(list(tree).index(tail) if tail is not None else len(tree), picture)
            blob, content_type, ext = raster
            fallback = _add_asset(package, replacements, blob, content_type, ext)
            blip.set(f"{{{R_NS}}}embed", _relationship(rels, slide_part, fallback))
            if vector is not None:
                svg_part = _add_asset(package, replacements, vector, SVG_CONTENT_TYPE, "svg")
                svg_blip = blip.find(f"{{{A_NS}}}extLst/{{{A_NS}}}ext/{{{SVG_BLIP_NS}}}svgBlip")
                if svg_blip is None:
                    extensions = blip.find(f"{{{A_NS}}}extLst")
                    if extensions is None:
                        extensions = ET.SubElement(blip, f"{{{A_NS}}}extLst")
                    extension = ET.SubElement(extensions, f"{{{A_NS}}}ext", {"uri": SVG_EXT_URI})
                    svg_blip = ET.SubElement(extension, f"{{{SVG_BLIP_NS}}}svgBlip")
                svg_blip.set(f"{{{R_NS}}}embed", _relationship(rels, slide_part, svg_part))
            replacements[slide_part] = serialize_xml(root)
            replacements[rel_part] = serialize_xml(rels)
            return replacements, set(), identifier

        identifier = self._rewrite("editing presentation pictures", plan)

        def members(shapes: Any) -> Iterator[Any]:
            for shape in shapes:
                yield shape
                if shape.shape_type == 6:
                    yield from members(shape.shapes)

        return next(
            shape
            for shape in members(self._presentation.slides[slide_index].shapes)
            if str(shape.shape_id) == identifier
        )
