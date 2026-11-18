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
)
from .package_parts import (
    natural_key as _natural_key,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .package_parts import (
    resolve_package_target as _resolve_package_target,
)
from .slide_metadata import (
    package_relationships as _package_relationships,
)
from .slide_metadata import (
    presentation_notes_master_partname as _presentation_notes_master_partname,
)
from .slide_metadata import (
    presentation_partname as _presentation_partname,
)
from .xml_helpers import ooxml_namespace

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

NOTES_MASTER_CT = "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"
NOTES_SLIDE_CT = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
THEME_CT = "application/vnd.openxmlformats-officedocument.theme+xml"


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
                if name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")
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
        presentation_root = ET.fromstring(package.read(presentation_part))
        p_ns = ooxml_namespace(presentation_root, P_NS)
        a_ns = ooxml_namespace(presentation_root, A_NS)
        r_ns = ooxml_namespace(presentation_root, R_NS)
        existing_notes_master = _existing_notes_master_partname(input_path)
        notes_master_part = existing_notes_master or _next_notes_master_partname(package)
        replacements: dict[str, bytes] = {}

        content_types = ET.fromstring(package.read("[Content_Types].xml"))
        for _, _, notes_part in adds:
            _ensure_content_type(content_types, f"/{notes_part}", NOTES_SLIDE_CT)
            replacements[notes_part] = _notes_slide_xml(p_ns, a_ns, r_ns)
            replacements[_rels_part_for_package_part(notes_part)] = _notes_slide_rels_xml(
                notes_part,
                notes_master_part,
                _slide_part_for_add(adds, notes_part),
                r_ns,
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
            replacements[notes_master_part] = _notes_master_xml(
                p_ns, a_ns, r_ns, _presentation_notes_size(presentation_root, p_ns)
            )
            replacements[theme_part] = package.read(theme_source_part)
            replacements[_rels_part_for_package_part(notes_master_part)] = _notes_master_rels_xml(
                _relative_target(notes_master_part, theme_part), r_ns
            )
            presentation_rels, notes_master_rid = _presentation_rels_with_notes_master(
                package,
                presentation_part,
                notes_master_part,
                r_ns,
            )
            replacements[_rels_part_for_package_part(presentation_part)] = presentation_rels
            replacements[presentation_part] = _presentation_xml_with_notes_master_id(
                package.read(presentation_part), notes_master_rid, r_ns
            )

        replacements["[Content_Types].xml"] = _xml_bytes(content_types)
        replacements.update(_slide_rels_replacements(package, adds, r_ns))

    _copy_package_with_replacements(input_path, output_path, replacements)


def _presentation_notes_size(presentation_root: ET.Element, p_ns: str) -> tuple[int, int]:
    """Notes page size from p:notesSz, else PowerPoint's portrait default."""
    element = presentation_root.find(f"{{{p_ns}}}notesSz")
    try:
        width, height = int(element.attrib["cx"]), int(element.attrib["cy"])  # type: ignore[union-attr]
    except (AttributeError, KeyError, ValueError):
        return 6858000, 9144000
    return (width, height) if width > 0 and height > 0 else (6858000, 9144000)


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
        "paragraph_run_strike": [[]] if has_text else [],
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
        if name.startswith("ppt/notesMasters/notesMaster") and name.endswith(".xml")
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
    r_ns: str,
) -> dict[str, bytes]:
    replacements: dict[str, bytes] = {}
    for _, slide_part, notes_part in adds:
        rels_part = _rels_part_for_package_part(slide_part)
        try:
            root = ET.fromstring(package.read(rels_part))
        except KeyError:
            root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
        target = _relative_target(slide_part, notes_part)
        _ensure_relationship(root, f"{r_ns}/notesSlide", target)
        replacements[rels_part] = _xml_bytes(root)
    return replacements


def _presentation_rels_with_notes_master(
    package: zipfile.ZipFile,
    presentation_part: str,
    notes_master_part: str,
    r_ns: str,
) -> tuple[bytes, str]:
    rels_part = _rels_part_for_package_part(presentation_part)
    root = ET.fromstring(package.read(rels_part))
    relationship_id = _ensure_relationship(
        root,
        f"{r_ns}/notesMaster",
        _relative_target(presentation_part, notes_master_part),
    )
    return _xml_bytes(root), relationship_id


_NOTES_MASTER_ID_LIST_SUCCESSORS = (
    "handoutMasterIdLst",
    "sldIdLst",
    "sldSz",
    "notesSz",
    "defaultTextStyle",
    "extLst",
)


def _presentation_xml_with_notes_master_id(
    payload: bytes, relationship_id: str, r_ns: str
) -> bytes:
    """Insert p:notesMasterIdLst after p:sldMasterIdLst, keeping every other byte."""
    root_tag = re.search(rb"<(?:([\w.-]+):)?presentation\b[^>]*>", payload)
    if root_tag is None:
        raise ValueError("presentation part root element is unavailable")
    prefix = root_tag.group(1) + b":" if root_tag.group(1) else b""
    if re.search(rb"<" + re.escape(prefix) + rb"notesMasterIdLst\b", payload):
        return payload
    r_prefix = re.search(
        rb'xmlns:([\w.-]+)=["\']' + re.escape(r_ns.encode()) + rb'["\']', root_tag.group(0)
    )
    r_attr = f"{r_prefix.group(1).decode()}:id" if r_prefix else "r:id"
    r_declaration = "" if r_prefix else f' xmlns:r="{r_ns}"'
    tag_prefix = prefix.decode()
    element = (
        f"<{tag_prefix}notesMasterIdLst><{tag_prefix}notesMasterId{r_declaration} "
        f'{r_attr}="{relationship_id}"/></{tag_prefix}notesMasterIdLst>'
    ).encode()
    closing = re.search(rb"</" + re.escape(prefix) + rb"sldMasterIdLst\s*>", payload)
    if closing is not None:
        return payload[: closing.end()] + element + payload[closing.end() :]
    for successor in _NOTES_MASTER_ID_LIST_SUCCESSORS:
        opening = re.search(
            rb"<" + re.escape(prefix) + successor.encode() + rb"[\s/>]",
            payload[root_tag.end() :],
        )
        if opening is not None:
            at = root_tag.end() + opening.start()
            return payload[:at] + element + payload[at:]
    raise ValueError("presentation part has no position for a notes master id list")


def _ensure_relationship(root: ET.Element, rel_type: str, target: str) -> str:
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Type") == rel_type and rel.attrib.get("Target") == target:
            return str(rel.attrib.get("Id", ""))
    relationship_id = _next_relationship_id(root)
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": relationship_id, "Type": rel_type, "Target": target},
    )
    return relationship_id


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


def _notes_slide_xml(p_ns: str, a_ns: str, r_ns: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<p:notes xmlns:a="{a_ns}" xmlns:p="{p_ns}" xmlns:r="{r_ns}">'
    ).encode() + (
        b'<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
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
    r_ns: str,
) -> bytes:
    root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": "rId1",
            "Type": f"{r_ns}/notesMaster",
            "Target": _relative_target(notes_part, notes_master_part),
        },
    )
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": "rId2",
            "Type": f"{r_ns}/slide",
            "Target": _relative_target(notes_part, slide_part),
        },
    )
    return _xml_bytes(root)


def _notes_master_xml(p_ns: str, a_ns: str, r_ns: str, notes_size: tuple[int, int]) -> bytes:
    return (
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<p:notesMaster xmlns:a="{a_ns}" xmlns:p="{p_ns}" xmlns:r="{r_ns}">'
        ).encode()
        + (
            b'<p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef>'
            b'</p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
            b"<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>"
            b'<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/>'
            b'<a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            b'<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/>'
            b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
            b'<p:ph type="sldImg" idx="2"/></p:nvPr></p:nvSpPr><p:spPr/>'
            b"<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>"
            b'<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/>'
            b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
            b'<p:ph type="body" idx="3" sz="quarter"/></p:nvPr></p:nvSpPr>'
            b"<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>"
            b'<p:sp><p:nvSpPr><p:cNvPr id="4" name="Slide Number Placeholder 3"/>'
            b'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
            b'<p:ph type="sldNum" idx="5" sz="quarter"/></p:nvPr></p:nvSpPr>'
            b"<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>"
        )
        + _notes_master_header_footer_xml(notes_size)
        + (
            b'</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" '
            b'tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
            b'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" '
            b'folHlink="folHlink"/><p:notesStyle><a:lvl1pPr><a:defRPr sz="1200"/>'
            b"</a:lvl1pPr></p:notesStyle></p:notesMaster>"
        )
    )


def _notes_header_footer_box(
    kind: str, notes_size: tuple[int, int]
) -> tuple[int, bool, bool, int, int]:
    """Margin, right-column, bottom-row flags and box size on a notes page."""
    width, height = notes_size
    margin = max(1, width // 20)
    box_width = max(1, (width - 3 * margin) // 2)
    box_height = max(1, height // 20)
    return margin, kind in {"dt", "sldNum"}, kind in {"ftr", "sldNum"}, box_width, box_height


def _notes_master_header_footer_xml(notes_size: tuple[int, int]) -> bytes:
    """The hdr, dt and ftr placeholders of PowerPoint's default notes master."""
    width, height = notes_size
    shapes = []
    for shape_id, name, kind, idx in (
        (5, "Header Placeholder 4", "hdr", 0),
        (6, "Date Placeholder 5", "dt", 1),
        (7, "Footer Placeholder 6", "ftr", 4),
    ):
        margin, right, bottom, box_width, box_height = _notes_header_footer_box(kind, notes_size)
        x = width - margin - box_width if right else margin
        y = height - margin - box_height if bottom else margin
        idx_attr = f' idx="{idx}"' if idx else ""
        align = "r" if right else "l"
        shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/>'
            '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>'
            f'<p:ph type="{kind}" sz="quarter"{idx_attr}/></p:nvPr></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{box_width}" cy="{box_height}"/>'
            '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
            '<p:txBody><a:bodyPr vert="horz" lIns="91440" tIns="45720" rIns="91440" '
            f'bIns="45720" rtlCol="0"/><a:lstStyle><a:lvl1pPr algn="{align}">'
            '<a:defRPr sz="1200"/></a:lvl1pPr></a:lstStyle><a:p/></p:txBody></p:sp>'
        )
    return "".join(shapes).encode()


def notes_header_footer_placeholder(
    kind: str,
    shape_id: int,
    idx: int,
    notes_size: tuple[int, int],
    part: str,
) -> ET.Element:
    """Build a page-scoped header/footer placeholder with explicit geometry.

    Notes masters need their own geometry: slide-sized footer boxes cannot be
    transplanted onto a portrait notes page. This helper is intentionally
    Transitional; callers must reject other profiles before materializing it.
    """
    from .slide_master_facade import placeholder_element, placeholder_spec

    if kind not in {"hdr", "ftr", "dt", "sldNum"}:
        raise ValueError("unsupported notes header/footer placeholder kind")
    width, height = notes_size
    if width <= 0 or height <= 0:
        raise ValueError("notes page dimensions must be positive")
    margin, right, bottom, box_width, box_height = _notes_header_footer_box(kind, notes_size)
    shape = placeholder_element(
        placeholder_spec(
            kind,
            shape_id,
            idx,
            (
                width - margin - box_width if right else margin,
                height - margin - box_height if bottom else margin,
                box_width,
                box_height,
            ),
            size="quarter",
        ),
        part,
    )
    body = shape.find(f"{{{P_NS}}}txBody")
    assert body is not None
    level = ET.SubElement(body.find(f"{{{A_NS}}}lstStyle"), f"{{{A_NS}}}lvl1pPr")
    level.set("algn", "r" if right else "l")
    ET.SubElement(level, f"{{{A_NS}}}defRPr", {"sz": "1200"})
    return shape


def _notes_master_rels_xml(theme_target: str, r_ns: str) -> bytes:
    root = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": "rId1", "Type": f"{r_ns}/theme", "Target": theme_target},
    )
    return _xml_bytes(root)


def _xml_bytes(root: ET.Element) -> bytes:
    _register_namespaces(root)
    try:
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    finally:
        # Registering the root as the default namespace unbinds its standard
        # prefix process-wide; restore it so later PresentationML writers keep
        # emitting ``p:`` elements that native readers match.
        ET.register_namespace("p", P_NS)


def _register_namespaces(root: ET.Element) -> None:
    ET.register_namespace("a", A_NS)
    ET.register_namespace("p", P_NS)
    ET.register_namespace("r", R_NS)
    ET.register_namespace("", _namespace_uri(root.tag))


def _namespace_uri(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""
