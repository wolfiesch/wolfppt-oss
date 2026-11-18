"""Presentation-wide slide identities and theme ownership for authored masters."""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping
from xml.etree import ElementTree as ET

from .package_closure import copy_rooted_relationship_closure
from .xml_helpers import content_types_xml

_IDENTITY_FLOOR = 2_147_483_648
_IDENTITY_CEILING = 4_294_967_295
_IDENTITY_TAGS = frozenset({"sldMasterId", "sldLayoutId"})
_MASTER_PART = re.compile(r"ppt/slideMasters/[^/]+\.xml")
_OWNED_REL_TYPES = frozenset(
    f"http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}"
    for kind in ("theme", "tags")
)


class SlideIdentities:
    """One allocator for ``p:sldMasterId`` and ``p:sldLayoutId`` values.

    The two id kinds share a single numeric space across the presentation, so
    every new value lies above every master and layout id already present and
    above every value handed out earlier in the same publication.
    """

    def __init__(self, parts: Mapping[str, bytes], presentation: ET.Element) -> None:
        roots = [presentation]
        roots.extend(
            ET.fromstring(payload)
            for name, payload in parts.items()
            if _MASTER_PART.fullmatch(name)
        )
        last = _IDENTITY_FLOOR - 1
        for root in roots:
            for node in root.iter():
                raw = node.get("id", "")
                if node.tag.rsplit("}", 1)[-1] in _IDENTITY_TAGS and raw.isdigit():
                    last = max(last, int(raw))
        self._last = last

    def take(self) -> int:
        if self._last >= _IDENTITY_CEILING:
            raise ValueError("presentation has no available slide master or layout identities")
        self._last += 1
        return self._last


def copy_closure(
    parts: dict[str, bytes],
    content_types: ET.Element,
    source: Mapping[str, bytes],
    roots: Mapping[str, str],
) -> dict[str, str]:
    """Copy a relationship closure into ``parts`` keeping ``content_types`` authoritative."""
    parts["[Content_Types].xml"] = content_types_xml(content_types)
    mapping = copy_rooted_relationship_closure(parts, source, roots)
    merged = ET.fromstring(parts["[Content_Types].xml"])
    content_types.clear()
    content_types.attrib.update(merged.attrib)
    content_types.extend(merged)
    return mapping


def copy_owned_parts(
    parts: dict[str, bytes],
    content_types: ET.Element,
    source_owner: str,
    destination_owner: str,
    rels: ET.Element,
) -> None:
    """Give cloned masters and layouts private theme and custom-data tag parts."""
    copies: dict[str, str] = {}
    for relation in rels:
        target = relation.get("Target", "")
        if relation.get("Type") not in _OWNED_REL_TYPES or relation.get("TargetMode") == "External":
            continue
        source_part = (
            posixpath.normpath(target.lstrip("/"))
            if target.startswith("/")
            else posixpath.normpath(posixpath.join(posixpath.dirname(source_owner), target))
        )
        if source_part not in parts:
            continue
        if source_part not in copies:
            copies[source_part] = _free_owned_part(parts, source_part)
            copy_closure(parts, content_types, dict(parts), {source_part: copies[source_part]})
        relation.set(
            "Target", posixpath.relpath(copies[source_part], posixpath.dirname(destination_owner))
        )


def _free_owned_part(parts: Mapping[str, bytes], source_part: str) -> str:
    directory, filename = posixpath.split(source_part)
    stem, extension = posixpath.splitext(filename)
    stem = re.sub(r"\d+$", "", stem)
    number = 1
    while f"{directory}/{stem}{number}{extension}" in parts or (
        f"{directory}/_rels/{stem}{number}{extension}.rels" in parts
    ):
        number += 1
    return f"{directory}/{stem}{number}{extension}"
