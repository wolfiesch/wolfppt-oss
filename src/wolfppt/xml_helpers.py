"""Small XML scalar helpers shared across presentation editing code."""

from __future__ import annotations

from xml.etree import ElementTree as ET


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
