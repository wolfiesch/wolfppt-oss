"""Package edits for creating notes-slide parts."""

from __future__ import annotations

import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
    natural_key as _natural_key,
    rels_part_for_package_part as _rels_part_for_package_part,
    resolve_package_target as _resolve_package_target,
)
from .slide_metadata import (
    package_relationships as _package_relationships,
    presentation_notes_master_partname as _presentation_notes_master_partname,
    presentation_partname as _presentation_partname,
)


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

NOTES_MASTER_CT = (
    "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"
)
NOTES_SLIDE_CT = (
    "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
)
THEME_CT = "application/vnd.openxmlformats-officedocument.theme+xml"
REL_NOTES_MASTER = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster"
)
REL_NOTES_SLIDE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
)
REL_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
REL_THEME = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"


def default_notes_slide_shape_payloads() -> list[dict[str, Any]]:
    return [
        _placeholder_payload("2", "Slide Image Placeholder 1", "sldImg", "2", None),
        _placeholder_payload("3", "Notes Placeholder 2", "body", "3", "quarter"),
        _placeholder_payload("4", "Slide Number Placeholder 3", "sldNum", "5", "quarter"),
    ]


def next_notes_slide_partname(path: Path, reserved: set[str] | None = None) -> str:
    taken = set(reserved or set())
    try:
        with zipfile.ZipFile(path) as package:
            taken.update(
                name
                for name in package.namelist()
                if name.startswith("ppt/notesSlides/notesSlide")
                and name.endswith(".xml")
            )
    except (FileNotFoundError, zipfile.BadZipFile):
        pass
    return _next_numbered_partname("ppt/notesSlides/notesSlide{}.xml", taken)


def apply_notes_slide_adds(
    input_path: Path,
    output_path: Path,
    adds: list[tuple[int, str, str]],
) -> None:
    if not adds:
        _copy_package_with_replacements(input_path, output_path, {})
        return

    with zipfile.ZipFile(input_path) as package:
        presentation_part = _presentation_partname(input_path)
        existing_notes_master = _existing_notes_master_partname(input_path)
        notes_master_part = existing_notes_master or _next_notes_master_partname(package)
        replacements: dict[str, bytes] = {}

        content_types = ET.fromstring(package.read("[Content_Types].xml"))
        for _, _, notes_part in adds:
            _ensure_content_type(content_types, f"/{notes_part}", NOTES_SLIDE_CT)
            replacements[notes_part] = _notes_slide_xml()
            replacements[_rels_part_for_package_part(notes_part)] = _notes_slide_rels_xml(
                notes_part,
                notes_master_part,
                _slide_part_for_add(adds, notes_part),
            )

        if existing_notes_master is None:
            theme_source_part = _first_theme_part(package, presentation_part)
            theme_part = _next_theme_partname(package)
            _ensure_content_type(
                content_types,
                f"/{notes_master_part}",
                NOTES_MASTER_CT,
            )
            _ensure_content_type(content_types, f"/{theme_part}", THEME_CT)
            replacements[notes_master_part] = _notes_master_xml()
            replacements[theme_part] = package.read(theme_source_part)
            replacements[_rels_part_for_package_part(notes_master_part)] = (
                _notes_master_rels_xml(_relative_target(notes_master_part, theme_part))
            )
            replacements[_rels_part_for_package_part(presentation_part)] = (
                _presentation_rels_with_notes_master(
                    package,
                    presentation_part,
                    notes_master_part,
                )
            )

        replacements["[Content_Types].xml"] = _xml_bytes(content_types)
        replacements.update(_slide_rels_replacements(package, adds))

    _copy_package_with_replacements(input_path, output_path, replacements)


def _placeholder_payload(
    shape_id: str,
    name: str,
    placeholder_type: str,
    placeholder_idx: str,
    placeholder_size: str | None,
) -> dict[str, Any]:
    has_text = placeholder_type == "body"
    return {
        "id": shape_id,
        "name": name,
        "kind": "shape",
        "text": "",
        "paragraphs": [""] if has_text else [],
        "paragraph_runs": [[]] if has_text else [],
        "paragraph_run_bold": [[]] if has_text else [],
        "paragraph_run_italic": [[]] if has_text else [],
        "paragraph_run_underline": [[]] if has_text else [],
        "paragraph_run_font_size": [[]] if has_text else [],
        "paragraph_run_font_name": [[]] if has_text else [],
        "paragraph_run_font_rgb": [[]] if has_text else [],
        "paragraph_run_font_fill_type": [[]] if has_text else [],
        "paragraph_run_font_language": [[]] if has_text else [],
        "is_placeholder": True,
        "placeholder_type": placeholder_type,
        "placeholder_idx": placeholder_idx,
        "placeholder_orient": None,
        "placeholder_size": placeholder_size,
        "paragraph_line_breaks": [[]] if has_text else [],
    }


def _existing_notes_master_partname(path: Path) -> str | None:
    try:
        return _presentation_notes_master_partname(path)
    except AttributeError:
        return None


def _next_notes_master_partname(package: zipfile.ZipFile) -> str:
    taken = {
        name
        for name in package.namelist()
        if name.startswith("ppt/notesMasters/notesMaster")
        and name.endswith(".xml")
    }
    return _next_numbered_partname("ppt/notesMasters/notesMaster{}.xml", taken)


def _next_theme_partname(package: zipfile.ZipFile) -> str:
    taken = {
        name
        for name in package.namelist()
        if name.startswith("ppt/theme/theme") and name.endswith(".xml")
    }
    return _next_numbered_partname("ppt/theme/theme{}.xml", taken)


def _next_numbered_partname(pattern: str, taken: set[str]) -> str:
    index = 1
    for name in sorted(taken, key=_natural_key):
        match = re.search(r"(\d+)\.xml$", name)
        if match:
            index = max(index, int(match.group(1)) + 1)
    while pattern.format(index) in taken:
        index += 1
    return pattern.format(index)


def _slide_part_for_add(adds: list[tuple[int, str, str]], notes_part: str) -> str:
    for _, slide_part, candidate in adds:
        if candidate == notes_part:
            return slide_part
    raise KeyError(notes_part)


def _ensure_content_type(root: ET.Element, partname: str, content_type: str) -> None:
    for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == partname:
            override.set("ContentType", content_type)
            return
    ET.SubElement(
        root,
        f"{{{CONTENT_TYPES_NS}}}Override",
        {"PartName": partname, "ContentType": content_type},
    )


def _slide_rels_replacements(
    package: zipfile.ZipFile,
    adds: list[tuple[int, str, str]],
) -> dict[str, bytes]:
    replacements: dict[str, bytes] = {}
    for _, slide_part, notes_part in adds:
        rels_part = _rels_part_for_package_part(slide_part)
        try:
            root = ET.fromstring(package.read(rels_part))
        except KeyError:
            root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
        target = _relative_target(slide_part, notes_part)
        _ensure_relationship(root, REL_NOTES_SLIDE, target)
        replacements[rels_part] = _xml_bytes(root)
    return replacements


def _presentation_rels_with_notes_master(
    package: zipfile.ZipFile,
    presentation_part: str,
    notes_master_part: str,
) -> bytes:
    rels_part = _rels_part_for_package_part(presentation_part)
    root = ET.fromstring(package.read(rels_part))
    _ensure_relationship(
        root,
        REL_NOTES_MASTER,
        _relative_target(presentation_part, notes_master_part),
    )
    return _xml_bytes(root)


def _ensure_relationship(root: ET.Element, rel_type: str, target: str) -> None:
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Type") == rel_type and rel.attrib.get("Target") == target:
            return
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": _next_relationship_id(root), "Type": rel_type, "Target": target},
    )


def _next_relationship_id(root: ET.Element) -> str:
    highest = 0
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        raw = rel.attrib.get("Id", "")
        if raw.startswith("rId") and raw[3:].isdigit():
            highest = max(highest, int(raw[3:]))
    return f"rId{highest + 1}"


def _first_theme_part(
    package: zipfile.ZipFile,
    presentation_part: str,
) -> str:
    for rel in _package_relationships(package, presentation_part).values():
        if rel.attrib.get("Type", "").endswith("/theme"):
            return _resolve_package_target(
                presentation_part,
                rel.attrib.get("Target", ""),
            )
    themes = sorted(
        [
            name
            for name in package.namelist()
            if name.startswith("ppt/theme/theme") and name.endswith(".xml")
        ],
        key=_natural_key,
    )
    if themes:
        return themes[0]
    raise AttributeError("theme part is unavailable")


def _relative_target(source_part: str, target_part: str) -> str:
    source_dir = posixpath.dirname(source_part)
    return posixpath.relpath(target_part, source_dir)


def _notes_slide_xml() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        b'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        b'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        b"<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/>"
        b"<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>"
        b'<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
        b'<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        b'<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/>'
        b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
        b'<p:ph type="sldImg" idx="2"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
        b'<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/>'
        b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
        b'<p:ph type="body" idx="3" sz="quarter"/></p:nvPr></p:nvSpPr>'
        b"<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>"
        b'<p:sp><p:nvSpPr><p:cNvPr id="4" name="Slide Number Placeholder 3"/>'
        b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
        b'<p:ph type="sldNum" idx="5" sz="quarter"/></p:nvPr></p:nvSpPr>'
        b"<p:spPr/></p:sp></p:spTree></p:cSld><p:clrMapOvr>"
        b"<a:masterClrMapping/></p:clrMapOvr></p:notes>"
    )


def _notes_slide_rels_xml(
    notes_part: str,
    notes_master_part: str,
    slide_part: str,
) -> bytes:
    root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": "rId1",
            "Type": REL_NOTES_MASTER,
            "Target": _relative_target(notes_part, notes_master_part),
        },
    )
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": "rId2",
            "Type": REL_SLIDE,
            "Target": _relative_target(notes_part, slide_part),
        },
    )
    return _xml_bytes(root)


def _notes_master_xml() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<p:notesMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        b'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        b'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        b'<p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef>'
        b'</p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
        b'<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>'
        b'<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
        b'<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        b'<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/>'
        b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
        b'<p:ph type="sldImg" idx="2"/></p:nvPr></p:nvSpPr><p:spPr/>'
        b'<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
        b'<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/>'
        b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
        b'<p:ph type="body" idx="3" sz="quarter"/></p:nvPr></p:nvSpPr>'
        b'<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
        b'<p:sp><p:nvSpPr><p:cNvPr id="4" name="Slide Number Placeholder 3"/>'
        b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
        b'<p:ph type="sldNum" idx="5" sz="quarter"/></p:nvPr></p:nvSpPr>'
        b'<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
        b'</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" '
        b'tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
        b'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" '
        b'folHlink="folHlink"/><p:notesStyle><a:lvl1pPr><a:defRPr sz="1200"/>'
        b'</a:lvl1pPr></p:notesStyle></p:notesMaster>'
    )


def _notes_master_rels_xml(theme_target: str) -> bytes:
    root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": "rId1", "Type": REL_THEME, "Target": theme_target},
    )
    return _xml_bytes(root)


def _xml_bytes(root: ET.Element) -> bytes:
    _register_namespaces(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _register_namespaces(root: ET.Element) -> None:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)
    ET.register_namespace("", _namespace_uri(root.tag))


def _namespace_uri(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""
