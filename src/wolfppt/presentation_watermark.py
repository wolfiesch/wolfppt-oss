"""Watermark geometry, shape markup and package rewrite planning."""

from __future__ import annotations

import posixpath
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_STRICT_REL_NS = "http://purl.oclc.org/ooxml/officeDocument/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_EMU_PER_POINT = 12700
_EMU_PER_INCH = 914400
_IMAGE_CONTENT_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
}
_SHAPE_LOCKS = (
    "noGrp",
    "noSelect",
    "noRot",
    "noChangeAspect",
    "noMove",
    "noResize",
    "noEditPoints",
    "noAdjustHandles",
    "noChangeArrowheads",
    "noChangeShapeType",
)


@dataclass(frozen=True)
class _WatermarkSpec:
    text: str | None
    image: bytes | None
    slide_width: int
    slide_height: int
    font_size: float
    font_name: str | None
    bold: bool
    color: str
    #: ``a:alpha`` / ``a:alphaModFix`` amount: 100000 is opaque.
    opacity: int
    rotation: float
    box: tuple[int | None, int | None, int | None, int | None]
    name: str


def _image_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    raise ValueError("unsupported watermark image; expected PNG, JPEG, GIF, BMP or TIFF")


def _watermark_box(spec: _WatermarkSpec) -> tuple[int, int, int, int]:
    left, top, width, height = spec.box
    for label, value in (("left", left), ("top", top)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise TypeError(f"{label} must be an integer EMU value")
    for label, value in (("width", width), ("height", height)):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
        ):
            raise ValueError(f"{label} must be a positive integer EMU value")
    if spec.image is not None:
        from .image_dimensions import image_size_and_dpi

        pixels_x, pixels_y, dpi_x, dpi_y = image_size_and_dpi(spec.image)
        if pixels_x <= 0 or pixels_y <= 0:
            raise ValueError("watermark image has no pixels")
        native_x = pixels_x / (dpi_x or 96.0) * _EMU_PER_INCH
        native_y = pixels_y / (dpi_y or 96.0) * _EMU_PER_INCH
        scale = min(0.6 * spec.slide_width / native_x, 0.6 * spec.slide_height / native_y)
        natural = (round(native_x * scale), round(native_y * scale))
    else:
        assert spec.text is not None
        lines = spec.text.split("\n")
        em = spec.font_size * _EMU_PER_POINT
        natural = (
            round(max(len(line) for line in lines) * em * 0.6 + 2 * 91440),
            round(len(lines) * em * 1.2 + 2 * 45720),
        )
    width = natural[0] if width is None else width
    height = natural[1] if height is None else height
    left = (spec.slide_width - width) // 2 if left is None else left
    top = (spec.slide_height - height) // 2 if top is None else top
    return left, top, width, height


def _watermark_shape(
    spec: _WatermarkSpec,
    namespaces: tuple[str, str, str],
    shape_id: int,
    relationship_id: str | None,
    box: tuple[int, int, int, int],
) -> ET.Element:
    p_ns, a_ns, r_ns = namespaces
    left, top, width, height = box
    rotation = round((spec.rotation % 360) * 60000) % 21600000
    locks = {name: "1" for name in _SHAPE_LOCKS}
    image = relationship_id is not None
    shape = ET.Element(f"{{{p_ns}}}{'pic' if image else 'sp'}")
    properties = ET.SubElement(shape, f"{{{p_ns}}}{'nvPicPr' if image else 'nvSpPr'}")
    ET.SubElement(
        properties,
        f"{{{p_ns}}}cNvPr",
        {"id": str(shape_id), "name": spec.name, "descr": spec.name},
    )
    if image:
        drawing = ET.SubElement(properties, f"{{{p_ns}}}cNvPicPr")
        ET.SubElement(drawing, f"{{{a_ns}}}picLocks", {**locks, "noCrop": "1"})
    else:
        drawing = ET.SubElement(properties, f"{{{p_ns}}}cNvSpPr", {"txBox": "1"})
        ET.SubElement(drawing, f"{{{a_ns}}}spLocks", {**locks, "noTextEdit": "1"})
    ET.SubElement(properties, f"{{{p_ns}}}nvPr")
    if image:
        fill = ET.SubElement(shape, f"{{{p_ns}}}blipFill")
        blip = ET.SubElement(fill, f"{{{a_ns}}}blip", {f"{{{r_ns}}}embed": relationship_id})
        if spec.opacity < 100000:
            ET.SubElement(blip, f"{{{a_ns}}}alphaModFix", {"amt": str(spec.opacity)})
        stretch = ET.SubElement(fill, f"{{{a_ns}}}stretch")
        ET.SubElement(stretch, f"{{{a_ns}}}fillRect")
    geometry = ET.SubElement(shape, f"{{{p_ns}}}spPr")
    transform = ET.SubElement(
        geometry, f"{{{a_ns}}}xfrm", {"rot": str(rotation)} if rotation else {}
    )
    ET.SubElement(transform, f"{{{a_ns}}}off", {"x": str(left), "y": str(top)})
    ET.SubElement(transform, f"{{{a_ns}}}ext", {"cx": str(width), "cy": str(height)})
    preset = ET.SubElement(geometry, f"{{{a_ns}}}prstGeom", {"prst": "rect"})
    ET.SubElement(preset, f"{{{a_ns}}}avLst")
    if image:
        return shape
    ET.SubElement(geometry, f"{{{a_ns}}}noFill")
    body = ET.SubElement(shape, f"{{{p_ns}}}txBody")
    ET.SubElement(body, f"{{{a_ns}}}bodyPr", {"wrap": "none", "rtlCol": "0", "anchor": "ctr"})
    ET.SubElement(body, f"{{{a_ns}}}lstStyle")
    assert spec.text is not None
    for line in spec.text.split("\n"):
        paragraph = ET.SubElement(body, f"{{{a_ns}}}p")
        ET.SubElement(paragraph, f"{{{a_ns}}}pPr", {"algn": "ctr"})
        attributes = {"lang": "en-US", "sz": str(round(spec.font_size * 100))}
        if spec.bold:
            attributes["b"] = "1"
        attributes["dirty"] = "0"
        if not line:
            ET.SubElement(paragraph, f"{{{a_ns}}}endParaRPr", attributes)
            continue
        run = ET.SubElement(paragraph, f"{{{a_ns}}}r")
        run_properties = ET.SubElement(run, f"{{{a_ns}}}rPr", attributes)
        solid = ET.SubElement(run_properties, f"{{{a_ns}}}solidFill")
        colour = ET.SubElement(solid, f"{{{a_ns}}}srgbClr", {"val": spec.color})
        if spec.opacity < 100000:
            ET.SubElement(colour, f"{{{a_ns}}}alpha", {"val": str(spec.opacity)})
        if spec.font_name is not None:
            for script in ("latin", "ea", "cs"):
                ET.SubElement(run_properties, f"{{{a_ns}}}{script}", {"typeface": spec.font_name})
        ET.SubElement(run, f"{{{a_ns}}}t").text = line
    return shape


def _watermark_plan(
    package: Any, parts: Sequence[str], spec: _WatermarkSpec
) -> tuple[dict[str, bytes], set[str], list[int]]:
    """Plan the rewrite that puts the watermark at the bottom of each slide."""
    from .native_media import _content_types, ordered_content_types_xml
    from .presentation_tags import parse_xml, relationships, serialize_xml
    from .xml_helpers import ooxml_namespace

    names = set(package.namelist())
    replacements: dict[str, bytes] = {}
    box = _watermark_box(spec)
    image_part = None
    if spec.image is not None:
        extension = _image_extension(spec.image)
        number = 1
        while f"ppt/media/image{number}.{extension}" in names:
            number += 1
        image_part = f"ppt/media/image{number}.{extension}"
        replacements[image_part] = spec.image
        defaults, _overrides = _content_types(package)
        content_type = _IMAGE_CONTENT_TYPES[extension]
        if defaults.get(extension) != content_type:
            types_root = parse_xml(package.read("[Content_Types].xml"))
            node = "Default" if extension not in defaults else "Override"
            attributes = (
                {"Extension": extension, "ContentType": content_type}
                if node == "Default"
                else {"PartName": "/" + image_part, "ContentType": content_type}
            )
            ET.SubElement(
                types_root,
                f"{{http://schemas.openxmlformats.org/package/2006/content-types}}{node}",
                attributes,
            )
            replacements["[Content_Types].xml"] = ordered_content_types_xml(types_root)
    roots: dict[str, ET.Element] = {}
    added: list[int] = []
    for part in parts:
        root = parse_xml(package.read(part))
        p_ns = ooxml_namespace(root, _PRESENTATION_NS)
        a_ns = ooxml_namespace(root, _DRAWING_NS)
        r_ns = ooxml_namespace(root, _REL_NS)
        tree = root.find(f"{{{p_ns}}}cSld/{{{p_ns}}}spTree")
        if tree is None:
            raise ValueError(f"slide {part} has no shape tree")
        shape_id = 1 + max(
            (
                int(node.get("id", "0"))
                for node in root.iter()
                if isinstance(node.tag, str)
                and node.tag.endswith("}cNvPr")
                and node.get("id", "").isdigit()
            ),
            default=1,
        )
        relationship_id = None
        if image_part is not None:
            rels = relationships(package, part, roots)
            taken = {node.get("Id") for node in rels}
            number = 1
            while f"rId{number}" in taken:
                number += 1
            relationship_id = f"rId{number}"
            ET.SubElement(
                rels,
                f"{{{_PACKAGE_REL_NS}}}Relationship",
                {
                    "Id": relationship_id,
                    "Type": f"{r_ns}/image",
                    "Target": posixpath.relpath(image_part, posixpath.dirname(part)),
                },
            )
        position = next(
            (index + 1 for index, child in enumerate(tree) if child.tag == f"{{{p_ns}}}grpSpPr"),
            None,
        )
        if position is None:
            raise ValueError(f"slide {part} has no group shape properties")
        tree.insert(
            position,
            _watermark_shape(spec, (p_ns, a_ns, r_ns), shape_id, relationship_id, box),
        )
        replacements[part] = serialize_xml(root)
        added.append(shape_id)
    for name, rels in roots.items():
        replacements[name] = serialize_xml(rels)
    return replacements, set(), added
