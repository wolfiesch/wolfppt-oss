"""Part-scoped background fill edits for slide-like XML parts."""

from __future__ import annotations

import posixpath
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import set_shape_gradient_fill as _set_shape_gradient_fill
from .dml_fill import set_solid_fill_color as _set_solid_fill_color
from .image_inputs import (
    InMemoryFile as _InMemoryFile,
)
from .image_inputs import (
    image_extension_from_blob as _image_extension_from_blob,
)
from .image_inputs import (
    image_input_bytes as _image_input_bytes,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    normalize_package_partname as _normalize_package_partname,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .xml_helpers import (
    STRICT_A_NS,
    STRICT_P_NS,
    STRICT_R_NS,
    find_ooxml,
    ooxml_namespace,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def profile_element(element: ET.Element, context: ET.Element) -> ET.Element:
    """Copy DrawingML into the destination's profile, retaining foreign namespaces."""
    result = deepcopy(element)
    for node in result.iter():
        for namespace, strict in ((A_NS, STRICT_A_NS), (P_NS, STRICT_P_NS), (R_NS, STRICT_R_NS)):
            target = ooxml_namespace(context, namespace)
            for source in (namespace, strict):
                if node.tag.startswith(f"{{{source}}}"):
                    node.tag = node.tag.replace(f"{{{source}}}", f"{{{target}}}", 1)
                for name in tuple(node.attrib):
                    if name.startswith(f"{{{source}}}"):
                        node.set(
                            name.replace(f"{{{source}}}", f"{{{target}}}", 1), node.attrib.pop(name)
                        )
    return result


_MEDIA_PART = re.compile(r"ppt/media/image(\d+)\.[a-z0-9]+")
_IMAGE_CONTENT_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "wmf": "image/x-wmf",
}


def apply_background_fill_edits(
    input_path: Path,
    output_path: Path,
    solid_edits: list[str],
    background_edits: list[str],
    color_edits: list[tuple[str, str | dict[str, Any]]],
    picture_edits: list[tuple[str, Any]] | None = None,
) -> None:
    edits: dict[str, dict[str, Any]] = {}
    for partname in solid_edits:
        edits[_normalize_package_partname(partname).lstrip("/")] = {"type": "solid"}
    for partname in background_edits:
        edits[_normalize_package_partname(partname).lstrip("/")] = {"type": "background"}
    for partname, payload_or_rgb in color_edits:
        norm = _normalize_package_partname(partname).lstrip("/")
        payload = edits.setdefault(norm, {"type": "solid"})
        if isinstance(payload_or_rgb, dict) and payload_or_rgb.get("type") in {
            "properties",
            "reference",
            "solid",
            "background",
        }:
            edits[norm] = dict(payload_or_rgb)
            continue
        if isinstance(payload_or_rgb, dict) and payload_or_rgb.get("type") == "picture":
            payload["type"] = "picture"
            payload["image_source"] = payload_or_rgb.get("image_source")
            payload["crop"] = payload_or_rgb.get("crop", (0.0, 0.0, 0.0, 0.0))
        elif isinstance(payload_or_rgb, dict) and payload_or_rgb.get("type") == "gradient":
            payload["type"] = "gradient"
            payload["gradient"] = payload_or_rgb.get("gradient") or {}
        else:
            payload["type"] = "solid"
            payload["rgb"] = payload_or_rgb
        if isinstance(payload_or_rgb, dict) and "_properties" in payload_or_rgb:
            payload["_properties"] = payload_or_rgb["_properties"]
    if picture_edits:
        for partname, pic_payload in picture_edits:
            norm = _normalize_package_partname(partname).lstrip("/")
            payload = edits.setdefault(norm, {"type": "picture"})
            payload["type"] = "picture"
            if isinstance(pic_payload, dict):
                payload["image_source"] = pic_payload.get("image_source")
                payload["crop"] = pic_payload.get("crop", (0.0, 0.0, 0.0, 0.0))
            else:
                payload["image_source"] = pic_payload
                payload["crop"] = (0.0, 0.0, 0.0, 0.0)

    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(input_path) as package:
        existing_parts = set(package.namelist())
        used_media_nums = {
            int(m.group(1))
            for name in existing_parts
            if (m := _MEDIA_PART.fullmatch(name)) is not None
        }
        next_media_num = max(used_media_nums, default=0) + 1

        for partname, edit in edits.items():
            if partname not in existing_parts:
                continue
            root = ET.fromstring(package.read(partname))
            common_slide_data = find_ooxml(root, f"{{{P_NS}}}cSld")
            if common_slide_data is None:
                raise ValueError(
                    f"slide part {partname} has no <p:cSld> common slide data; "
                    "cannot apply background edits"
                )
            properties = edit.get("_properties", {})
            background = find_ooxml(common_slide_data, f"{{{P_NS}}}bg")
            if background is None:
                background = ET.Element(f"{{{ooxml_namespace(common_slide_data, P_NS)}}}bg")
                common_slide_data.insert(_background_insert_index(common_slide_data), background)
            if "bw_mode" in properties:
                if properties["bw_mode"] is None:
                    background.attrib.pop("bwMode", None)
                else:
                    background.set("bwMode", properties["bw_mode"])
            if edit["type"] == "reference":
                for child in list(background):
                    if _local_name(child.tag) in {"bgRef", "bgPr"}:
                        background.remove(child)
                reference = ET.SubElement(
                    background,
                    f"{{{ooxml_namespace(background, P_NS)}}}bgRef",
                    {"idx": str(edit["index"])},
                )
                reference.append(profile_element(ET.fromstring(edit["color"]), background))
            needs_properties = edit["type"] not in {"properties", "reference"} or any(
                key in properties for key in ("shade_to_title", "effects")
            )
            background_properties = (
                _background_properties(common_slide_data) if needs_properties else None
            )
            if background_properties is not None:
                if "shade_to_title" in properties:
                    if properties["shade_to_title"] is None:
                        background_properties.attrib.pop("shadeToTitle", None)
                    else:
                        background_properties.set(
                            "shadeToTitle", "1" if properties["shade_to_title"] else "0"
                        )
                if "effects" in properties:
                    for child in list(background_properties):
                        if _local_name(child.tag) in {"effectLst", "effectDag"}:
                            background_properties.remove(child)
                    if properties["effects"] is not None:
                        effect = profile_element(
                            ET.fromstring(properties["effects"]), background_properties
                        )
                        extension = find_ooxml(background_properties, f"{{{A_NS}}}extLst")
                        index = (
                            len(background_properties)
                            if extension is None
                            else list(background_properties).index(extension)
                        )
                        background_properties.insert(index, effect)
            rel_id = None
            if edit["type"] == "picture":
                src = edit["image_source"]
                if isinstance(src, (bytes, bytearray)):
                    blob = bytes(src)
                elif isinstance(src, _InMemoryFile):
                    blob = src.blob
                else:
                    blob = _image_input_bytes(src)
                try:
                    ext = _image_extension_from_blob(blob)
                except ValueError:
                    ext = "png"
                media_part = f"ppt/media/image{next_media_num}.{ext}"
                next_media_num += 1
                replacements[media_part] = blob
                _ensure_content_type(package, replacements, ext)
                rels_part = _rels_part_for_package_part(partname).lstrip("/")
                rel_id = _add_image_relationship(
                    package, replacements, rels_part, media_part, partname
                )

            if edit["type"] not in {"properties", "reference"}:
                assert background_properties is not None
                _replace_fill(
                    background_properties,
                    str(edit["type"]),
                    color=edit.get("rgb"),
                    relationship_id=rel_id,
                    crop=edit.get("crop"),
                    gradient=edit.get("gradient"),
                )
            _register_namespaces()
            replacements[partname] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _background_properties(common_slide_data: ET.Element) -> ET.Element:
    namespace = ooxml_namespace(common_slide_data, P_NS)
    background = find_ooxml(common_slide_data, f"{{{P_NS}}}bg")
    if background is None:
        background = ET.Element(f"{{{namespace}}}bg")
        common_slide_data.insert(_background_insert_index(common_slide_data), background)
    background_properties = find_ooxml(background, f"{{{P_NS}}}bgPr")
    if background_properties is None:
        for child in list(background):
            if _local_name(child.tag) == "bgRef":
                background.remove(child)
        background_properties = ET.SubElement(background, f"{{{namespace}}}bgPr")
        ET.SubElement(background_properties, f"{{{ooxml_namespace(background, A_NS)}}}noFill")
    if (
        find_ooxml(background_properties, f"{{{A_NS}}}effectLst") is None
        and find_ooxml(background_properties, f"{{{A_NS}}}effectDag") is None
    ):
        extension = find_ooxml(background_properties, f"{{{A_NS}}}extLst")
        effect = ET.Element(f"{{{ooxml_namespace(background, A_NS)}}}effectLst")
        index = (
            len(background_properties)
            if extension is None
            else list(background_properties).index(extension)
        )
        background_properties.insert(index, effect)
    return background_properties


def _background_insert_index(common_slide_data: ET.Element) -> int:
    for index, child in enumerate(list(common_slide_data)):
        if _local_name(child.tag) == "spTree":
            return index
    return 0


def _replace_fill(
    background_properties: ET.Element,
    fill_type: str,
    color: str | dict[str, Any] | None = None,
    relationship_id: str | None = None,
    crop: tuple[float, float, float, float] | dict[str, float] | None = None,
    gradient: dict[str, Any] | None = None,
) -> None:
    for child in list(background_properties):
        if _local_name(child.tag).endswith("Fill"):
            background_properties.remove(child)
    if fill_type == "background":
        fill = ET.Element(f"{{{A_NS}}}noFill")
    elif fill_type == "solid":
        fill = ET.Element(f"{{{A_NS}}}solidFill")
        if color is not None:
            _set_solid_fill_color(fill, color)
    elif fill_type == "picture":
        fill = ET.Element(f"{{{A_NS}}}blipFill")
        fill.set("dpi", "0")
        fill.set("rotWithShape", "1")
        blip = ET.SubElement(fill, f"{{{A_NS}}}blip")
        if relationship_id:
            blip.set(f"{{{R_NS}}}embed", relationship_id)
        cl, ct, cr, cb = 0.0, 0.0, 0.0, 0.0
        if isinstance(crop, (list, tuple)) and len(crop) == 4:
            cl, ct, cr, cb = crop
        elif isinstance(crop, dict):
            cl = float(crop.get("l", 0.0))
            ct = float(crop.get("t", 0.0))
            cr = float(crop.get("r", 0.0))
            cb = float(crop.get("b", 0.0))
        if any(v > 0.0 for v in (cl, ct, cr, cb)):
            src_rect = ET.SubElement(fill, f"{{{A_NS}}}srcRect")
            if cl > 0.0:
                src_rect.set("l", str(round(cl * 100000)))
            if ct > 0.0:
                src_rect.set("t", str(round(ct * 100000)))
            if cr > 0.0:
                src_rect.set("r", str(round(cr * 100000)))
            if cb > 0.0:
                src_rect.set("b", str(round(cb * 100000)))
        stretch = ET.SubElement(fill, f"{{{A_NS}}}stretch")
        ET.SubElement(stretch, f"{{{A_NS}}}fillRect")
    elif fill_type == "gradient":
        holder = ET.Element("fill-holder")
        _set_shape_gradient_fill(holder, gradient or {})
        fill = holder[0]
    else:
        raise ValueError(f"unsupported background fill type: {fill_type}")
    background_properties.insert(0, profile_element(fill, background_properties))


def _ensure_content_type(
    package: zipfile.ZipFile, replacements: dict[str, bytes], extension: str
) -> None:
    ct_name = "[Content_Types].xml"
    if ct_name in replacements:
        raw = replacements[ct_name]
    elif ct_name in package.namelist():
        raw = package.read(ct_name)
    else:
        return
    root = ET.fromstring(raw)
    for default in root.findall(f"{{{CONTENT_TYPES_NS}}}Default"):
        if default.attrib.get("Extension", "").lower() == extension.lower():
            return
    default = ET.Element(f"{{{CONTENT_TYPES_NS}}}Default")
    default.set("Extension", extension)
    default.set("ContentType", _IMAGE_CONTENT_TYPES.get(extension.lower(), f"image/{extension}"))
    overrides = root.findall(f"{{{CONTENT_TYPES_NS}}}Override")
    if overrides:
        root.insert(list(root).index(overrides[0]), default)
    else:
        root.append(default)
    ET.register_namespace("", CONTENT_TYPES_NS)
    replacements[ct_name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _add_image_relationship(
    package: zipfile.ZipFile,
    replacements: dict[str, bytes],
    rels_part: str,
    media_part: str,
    owner_part: str,
) -> str:
    if rels_part in replacements:
        raw = replacements[rels_part]
    elif rels_part in package.namelist():
        raw = package.read(rels_part)
    else:
        raw = f'<Relationships xmlns="{PKG_REL_NS}"/>'.encode()
    root = ET.fromstring(raw)
    highest = 0
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        raw_id = rel.attrib.get("Id", "")
        if raw_id.startswith("rId") and raw_id[3:].isdigit():
            highest = max(highest, int(raw_id[3:]))
    rel_id = f"rId{highest + 1}"
    target = posixpath.relpath(media_part, posixpath.dirname(owner_part))
    rel = ET.SubElement(root, f"{{{PKG_REL_NS}}}Relationship")
    rel.set("Id", rel_id)
    rel.set(
        "Type",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
    )
    rel.set("Target", target)
    ET.register_namespace("", PKG_REL_NS)
    replacements[rels_part] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return rel_id


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _register_namespaces() -> None:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)
