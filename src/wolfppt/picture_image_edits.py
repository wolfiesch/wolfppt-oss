"""Copy-on-write image replacement for one saved picture shape."""

from __future__ import annotations

import posixpath
from pathlib import Path
from zipfile import ZipFile

from .package_parts import (
    A_NS,
    P_NS,
    R_NS,
    copy_package_with_replacements,
    rels_part_for_package_part,
    resolve_package_target,
)
from .presentation_images import _add_asset, _relationship
from .presentation_tags import parse_xml, serialize_xml
from .shape_picture_inspection import PictureImage
from .slide_metadata import package_relationships, presentation_partname
from .xml_helpers import find_ooxml, findall_ooxml, ooxml_path


def apply_picture_image_replace(
    source: Path, destination: Path, slide_index: int, shape_id: str, image_path: Path
) -> None:
    """Replace only the selected shape; retain shared media and other consumers."""
    with ZipFile(source) as package:
        presentation_part = presentation_partname(source)
        presentation = parse_xml(package.read(presentation_part), read_only=True)
        presentation_rels = package_relationships(package, presentation_part)
        slide_ids = findall_ooxml(presentation, f".//{{{P_NS}}}sldId")
        slide_id = slide_ids[slide_index]
        slide_rel = presentation_rels[slide_id.get(ooxml_path(slide_id, f"{{{R_NS}}}id"))]
        slide_part = resolve_package_target(presentation_part, slide_rel.get("Target", ""))
        root = parse_xml(package.read(slide_part))
        candidates = []
        for element in root.iter():
            # Inspect each drawable object's own identity, including grouped pictures.
            for nv in ("nvPicPr", "nvSpPr"):
                identity = find_ooxml(element, f"{{{P_NS}}}{nv}/{{{P_NS}}}cNvPr")
                if identity is not None and identity.get("id") == shape_id:
                    candidates.append(element)
        if len(candidates) != 1:
            raise ValueError("picture identity is unavailable or ambiguous")
        blip = find_ooxml(candidates[0], f".//{{{A_NS}}}blip")
        if blip is None:
            raise ValueError("picture image relationship is unavailable")
        embed = ooxml_path(blip, f"{{{R_NS}}}embed")
        rid = blip.get(embed)
        rel_part = rels_part_for_package_part(slide_part)
        rels = parse_xml(package.read(rel_part))
        matches = [rel for rel in rels if rel.get("Id") == rid]
        if len(matches) != 1 or matches[0].get("TargetMode") == "External":
            raise ValueError("picture image relationship is unavailable or external")
        original_part = resolve_package_target(slide_part, matches[0].get("Target", ""))
        image = PictureImage.from_image_input(image_path)
        blob = image.blob
        replacements: dict[str, bytes] = {}
        if package.read(original_part) != blob:
            shared = sum(node.get(embed) == rid for node in root.iter()) > 1
            if not shared:
                for name in package.namelist():
                    if not name.endswith(".rels"):
                        continue
                    owner = posixpath.join(
                        posixpath.dirname(posixpath.dirname(name)), posixpath.basename(name)[:-5]
                    )
                    for rel in parse_xml(package.read(name), read_only=True):
                        if rel.get("TargetMode") == "External":
                            continue
                        if name == rel_part and rel.get("Id") == rid:
                            continue
                        if resolve_package_target(owner, rel.get("Target", "")) == original_part:
                            shared = True
                            break
                    if shared:
                        break
            if shared:
                media_part = _add_asset(package, replacements, blob, image.content_type, image.ext)
                blip.set(embed, _relationship(rels, slide_part, media_part))
                rels[-1].set("Type", matches[0].get("Type", ""))
                replacements[slide_part] = serialize_xml(root)
                replacements[rel_part] = serialize_xml(rels)
            else:
                # Keep the established relationship-preserving single-consumer path.
                replacements[original_part] = blob
    copy_package_with_replacements(source, destination, replacements)
