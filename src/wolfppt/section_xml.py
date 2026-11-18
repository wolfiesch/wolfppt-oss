"""OpenXML PresentationML section XML parsing, manipulation, and serialization.

Implements the MS-PPTX 2010 presentation sections extension schema:
p:presentation / p:extLst / p:ext uri='{521415D9-36F7-43E2-AB2F-B90AF26B5E84}'
  / p14:sectionLst / p14:section @name @id='{GUID}'
    / p14:sldIdLst / p14:sldId @id='...'
"""

from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from .presentation_save_state import _element_spans
from .xml_helpers import find_ooxml, findall_ooxml

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

SECTION_EXTENSION_URI = "{521415D9-36F7-43E2-AB2F-B90AF26B5E84}"

_GUID_REGEX = re.compile(
    r"^\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}$"
)


def is_valid_guid(val: str) -> bool:
    """Check whether val matches standard {GUID} representation."""
    if not isinstance(val, str):
        return False
    return bool(_GUID_REGEX.match(val.strip()))


def generate_section_id() -> str:
    """Generate a valid uppercase OpenXML ST_Guid string."""
    return f"{{{str(uuid.uuid4()).upper()}}}"


@dataclass
class SectionRecord:
    """Low-level record representing a <p14:section> entry in XML."""

    id: str
    name: str
    slide_ids: list[int] = field(default_factory=list)


def read_presentation_slide_ids(root: ET.Element) -> list[int]:
    """Read the ordered list of slide IDs from <p:presentation>/<p:sldIdLst>."""
    sld_id_lst = root.find(f"{{{P_NS}}}sldIdLst")
    if sld_id_lst is None:
        return []
    slide_ids: list[int] = []
    for sld_id in sld_id_lst.findall(f"{{{P_NS}}}sldId"):
        raw_id = sld_id.attrib.get("id")
        if raw_id is not None and raw_id.isdigit():
            slide_ids.append(int(raw_id))
    return slide_ids


def find_section_extension_element(
    root: ET.Element,
) -> tuple[ET.Element | None, ET.Element | None]:
    """Find (<p:extLst>, <p:ext uri='...'>) for sections if present."""
    ext_lst = find_ooxml(root, f"{{{P_NS}}}extLst")
    if ext_lst is None:
        return None, None
    for ext in findall_ooxml(ext_lst, f"{{{P_NS}}}ext"):
        uri = ext.attrib.get("uri", "")
        if uri.strip().upper() == SECTION_EXTENSION_URI.upper():
            return ext_lst, ext
    return ext_lst, None


def read_sections_from_element(root: ET.Element) -> list[SectionRecord]:
    """Parse <p14:sectionLst> from <p:extLst>/<p:ext uri='...'> into SectionRecords."""
    _, ext = find_section_extension_element(root)
    if ext is None:
        return []
    section_lst = ext.find(f"{{{P14_NS}}}sectionLst")
    if section_lst is None:
        return []

    records: list[SectionRecord] = []
    for section_elem in section_lst.findall(f"{{{P14_NS}}}section"):
        sec_id = section_elem.attrib.get("id", "")
        name = section_elem.attrib.get("name", "")
        slide_ids: list[int] = []
        sld_id_lst = section_elem.find(f"{{{P14_NS}}}sldIdLst")
        if sld_id_lst is not None:
            for sld_id in sld_id_lst.findall(f"{{{P14_NS}}}sldId"):
                raw_id = sld_id.attrib.get("id")
                if raw_id is not None and raw_id.isdigit():
                    slide_ids.append(int(raw_id))
        records.append(SectionRecord(id=sec_id, name=name, slide_ids=slide_ids))
    return records


def splice_sections_into_presentation_xml(
    payload: bytes,
    sections: list[SectionRecord],
) -> bytes:
    """Return ``payload`` with only its section extension replaced or removed.

    Every other byte is kept verbatim: sibling extensions, namespace prefixes
    and declarations, and the ``mc:Ignorable`` tokens that must keep resolving
    to them. An empty ``sections`` list removes the extension, and the
    ``p:extLst`` too when nothing else is left in it. A new ``p:extLst`` is
    appended as the last child of ``p:presentation``.
    """
    payload = _utf8_payload(payload)
    nodes = _element_spans(payload)
    ext_list = next(
        (
            index
            for index, node in enumerate(nodes)
            if node["parent"] == 0 and node["tag"] == f"{{{P_NS}}}extLst"
        ),
        None,
    )
    extensions = (
        [index for index, node in enumerate(nodes) if node["parent"] == ext_list]
        if ext_list is not None
        else []
    )
    section_ext = next(
        (
            index
            for index in extensions
            if nodes[index]["tag"] == f"{{{P_NS}}}ext"
            and nodes[index]["attrib"].get("uri", "").strip().upper() == SECTION_EXTENSION_URI
        ),
        None,
    )
    p_declaration = (
        b"" if _root_prefixes(payload).get("p") == P_NS else f' xmlns:p="{P_NS}"'.encode()
    )
    fragment = _section_extension_xml(sections, p_declaration) if sections else b""
    if section_ext is not None:
        if not fragment and len(extensions) == 1:
            return _replace_span(payload, nodes[ext_list], b"")
        return _replace_span(payload, nodes[section_ext], fragment)
    if not fragment:
        return payload
    if ext_list is None:
        root_end_tag = payload.rindex(b"</", 0, nodes[0]["end"])
        wrapped = b"<p:extLst" + p_declaration + b">" + fragment + b"</p:extLst>"
        return payload[:root_end_tag] + wrapped + payload[root_end_tag:]
    node = nodes[ext_list]
    if payload[node["end"] - 2 : node["end"]] == b"/>":
        wrapped = b"<p:extLst" + p_declaration + b">" + fragment + b"</p:extLst>"
        return _replace_span(payload, node, wrapped)
    end_tag = payload.rindex(b"</", node["start"], node["end"])
    return payload[:end_tag] + fragment + payload[end_tag:]


def _section_extension_xml(sections: list[SectionRecord], p_declaration: bytes) -> bytes:
    from xml.sax.saxutils import quoteattr

    # PowerPoint declares p14 on the section list itself; doing the same keeps
    # the fragment self-contained whatever the root declares.
    parts = [
        (
            f'<p:ext{p_declaration.decode()} uri="{SECTION_EXTENSION_URI}">'
            f'<p14:sectionLst xmlns:p14="{P14_NS}">'
        )
    ]
    for section in sections:
        parts.append(
            f"<p14:section name={quoteattr(section.name)} id={quoteattr(section.id)}><p14:sldIdLst>"
        )
        parts.extend(f'<p14:sldId id="{int(slide_id)}"/>' for slide_id in section.slide_ids)
        parts.append("</p14:sldIdLst></p14:section>")
    parts.append("</p14:sectionLst></p:ext>")
    return "".join(parts).encode("utf-8")


def _replace_span(payload: bytes, node: dict, replacement: bytes) -> bytes:
    return payload[: node["start"]] + replacement + payload[node["end"] :]


def _root_prefixes(payload: bytes) -> dict[str, str]:
    """Namespace prefixes declared on the document element itself."""
    prefixes: dict[str, str] = {}
    for event, item in ET.iterparse(io.BytesIO(payload), events=("start-ns", "start")):
        if event == "start":
            break
        prefix, uri = item
        prefixes[prefix] = uri
    return prefixes


def _utf8_payload(payload: bytes) -> bytes:
    """Byte offsets are spliced as UTF-8; transcode any other declared encoding."""
    head = payload[:200]
    match = re.match(rb"<\?xml[^>]*encoding=[\"']([A-Za-z0-9._-]+)[\"']", head)
    utf8 = not head.startswith((b"\xff\xfe", b"\xfe\xff")) and (
        match is None or match.group(1).lower() in (b"utf-8", b"utf8")
    )
    if utf8:
        return payload
    return ET.tostring(ET.fromstring(payload), encoding="utf-8", xml_declaration=True)
