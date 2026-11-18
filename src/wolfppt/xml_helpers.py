"""Small XML scalar helpers shared across presentation editing code."""

from __future__ import annotations

import re
from functools import lru_cache
from xml.etree import ElementTree as ET

# Exact ECMA-376 profile pairs. Query adaptation never changes source tags,
# attributes, namespace declarations, or serialized package bytes.
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
STRICT_P_NS = "http://purl.oclc.org/ooxml/presentationml/main"
STRICT_A_NS = "http://purl.oclc.org/ooxml/drawingml/main"
STRICT_R_NS = "http://purl.oclc.org/ooxml/officeDocument/relationships"
_STRICT_NAMESPACES = {
    P_NS: STRICT_P_NS,
    A_NS: STRICT_A_NS,
    R_NS: STRICT_R_NS,
}
_STRICT_TAG_PREFIXES = tuple(f"{{{uri}}}" for uri in _STRICT_NAMESPACES.values())


def ooxml_namespace(element: ET.Element, namespace: str) -> str:
    """Select a known namespace in the context element's unchanged profile."""
    if element.tag.startswith(_STRICT_TAG_PREFIXES):
        return _STRICT_NAMESPACES.get(namespace, namespace)
    return namespace


@lru_cache(maxsize=512)
def _strict_path(path: str) -> str:
    for transitional, strict in _STRICT_NAMESPACES.items():
        path = path.replace(f"{{{transitional}}}", f"{{{strict}}}")
    return path


def ooxml_path(element: ET.Element, path: str) -> str:
    """Adapt a qualified selector, never a local-name wildcard."""
    return _strict_path(path) if element.tag.startswith(_STRICT_TAG_PREFIXES) else path


def find_ooxml(element: ET.Element, path: str) -> ET.Element | None:
    return element.find(ooxml_path(element, path))


def findall_ooxml(element: ET.Element, path: str) -> list[ET.Element]:
    return element.findall(ooxml_path(element, path))


def ooxml_namespaces(element: ET.Element, namespaces: dict[str, str]) -> dict[str, str]:
    if not element.tag.startswith(_STRICT_TAG_PREFIXES):
        return namespaces
    return {
        prefix: _STRICT_NAMESPACES.get(uri, uri) for prefix, uri in namespaces.items()
    }


def percentage_value(element: ET.Element, value: str) -> float:
    """Read a DrawingML percentage as a fraction, retaining lexical profile rules.

    ECMA-376 Strict shared-commonSimpleTypes.xsd ST_Percentage uses
    -?[0-9]+(\\.[0-9]+)?%; Transitional also permits integer thousandths.
    Range restrictions belong to the consuming property.
    """
    import math

    strict = element.tag.startswith(_STRICT_TAG_PREFIXES)
    if strict or value.endswith("%"):
        if re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?%", value) is None:
            raise ValueError(f"invalid percentage {value!r}")
        number = float(value[:-1]) / 100.0
    else:
        if re.fullmatch(r"[+-]?[0-9]+", value.strip()) is None:
            raise ValueError(f"invalid percentage {value!r}")
        number = int(value) / 100000.0
    if not math.isfinite(number):
        raise ValueError("percentage is not finite")
    return number


def xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def xml_bool_attr(element: ET.Element, attr: str) -> bool:
    value = element.attrib.get(attr)
    if value is None:
        return False
    return xml_bool_value(value, default=False)


def xml_bool_value(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value not in {"0", "false", "False"}


def optional_bool_xml_attr(element: ET.Element, attr: str) -> bool | None:
    value = element.attrib.get(attr)
    return None if value is None else xml_bool_value(value, default=False)


def xml_int_attr(element: ET.Element, attr: str, default: int) -> int:
    value = element.attrib.get(attr)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


_CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def content_types_xml(root: ET.Element) -> bytes:
    """Serialize an OPC content-types root using its required default namespace."""
    if root.tag != f"{{{_CONTENT_TYPES_NS}}}Types":
        raise ValueError("content types root has an invalid root")
    # A process-wide default-prefix registration for this namespace would make
    # ElementTree emit qualified attributes unprefixed, silently dropping their
    # namespace. Serialize against an explicit prefix regardless of that state.
    default_registered = ET._namespace_map.get(_CONTENT_TYPES_NS) == ""
    if default_registered:
        del ET._namespace_map[_CONTENT_TYPES_NS]
    try:
        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    finally:
        if default_registered:
            ET._namespace_map[_CONTENT_TYPES_NS] = ""
    match = re.search(
        rb"<(?P<prefix>[A-Za-z_][A-Za-z0-9_.-]*):Types(?=[\s>/])", payload
    )
    if match is None:
        return payload
    prefix = match.group("prefix")
    root_end = payload.find(b">", match.start())
    if root_end < 0:
        raise ValueError("content types XML has no root terminator")
    start = payload[match.start() : root_end + 1]
    declaration = (
        rb"\s+xmlns:"
        + re.escape(prefix)
        + rb"="
        + re.escape(f'"{_CONTENT_TYPES_NS}"'.encode())
    )
    uses_qualified_content_types_attribute = any(
        attribute.startswith(f"{{{_CONTENT_TYPES_NS}}}")
        for element in root.iter()
        for attribute in element.attrib
    )
    if not uses_qualified_content_types_attribute:
        start, replacements = re.subn(declaration, b"", start, count=1)
        if replacements != 1:
            raise ValueError("content types XML has no root namespace declaration")
    payload = payload[: match.start()] + start + payload[root_end + 1 :]
    qualified_tag = (
        rb"(<\/?)" + re.escape(prefix) + rb":([A-Za-z_][A-Za-z0-9_.-]*)(?=[\s>/])"
    )
    return re.sub(qualified_tag, rb"\1\2", payload).replace(
        b"<Types", f'<Types xmlns="{_CONTENT_TYPES_NS}"'.encode(), 1
    )
