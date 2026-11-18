"""Extended document property facade, XML serialization, and type models."""

from __future__ import annotations

import copy
import re
import zipfile
from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import package_part_content_type

EP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
VTYPES_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

EXTENDED_PROPERTIES_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
)
EXTENDED_PROPERTIES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.extended-properties+xml"
)
EXTENDED_PROPERTIES_PARTNAME = "docProps/app.xml"
STRICT_EP_NS = "http://purl.oclc.org/ooxml/officeDocument/extendedProperties"
STRICT_VTYPES_NS = "http://purl.oclc.org/ooxml/officeDocument/docPropsVTypes"
STRICT_EXTENDED_PROPERTIES_REL_TYPE = (
    "http://purl.oclc.org/ooxml/officeDocument/relationships/extendedProperties"
)
EXTENDED_PROPERTIES_REL_TYPES = (
    EXTENDED_PROPERTIES_REL_TYPE,
    STRICT_EXTENDED_PROPERTIES_REL_TYPE,
)

INT32_MIN = -2147483648
INT32_MAX = 2147483647

ET.register_namespace("", EP_NS)
ET.register_namespace("vt", VTYPES_NS)


class ExtendedPropertiesRefusal(ValueError):
    """Raised when an extended properties part cannot be safely read or rewritten."""


_CANONICAL_ELEMENT_ORDER: tuple[str, ...] = (
    "Template",
    "Manager",
    "Company",
    "Pages",
    "Words",
    "Characters",
    "PresentationFormat",
    "Lines",
    "Paragraphs",
    "Slides",
    "Notes",
    "TotalTime",
    "HiddenSlides",
    "MMClips",
    "ScaleCrop",
    "HeadingPairs",
    "TitlesOfParts",
    "LinksUpToDate",
    "CharactersWithSpaces",
    "SharedDoc",
    "HyperlinkBase",
    "HLinks",
    "HyperlinksChanged",
    "DigSig",
    "Application",
    "AppVersion",
    "DocSecurity",
)

_ORDER_INDEX: dict[str, int] = {name: idx for idx, name in enumerate(_CANONICAL_ELEMENT_ORDER)}

_BOOLEAN_TAGS: frozenset[str] = frozenset(
    {"SharedDoc", "ScaleCrop", "LinksUpToDate", "HyperlinksChanged"}
)

_INTEGER_TAGS: frozenset[str] = frozenset(
    {
        "TotalTime",
        "Pages",
        "Words",
        "Characters",
        "Lines",
        "Paragraphs",
        "Slides",
        "Notes",
        "HiddenSlides",
        "MMClips",
        "CharactersWithSpaces",
        "DocSecurity",
    }
)

_STRING_TAGS: frozenset[str] = frozenset(
    {
        "Company",
        "Manager",
        "Application",
        "AppVersion",
        "Template",
        "HyperlinkBase",
        "PresentationFormat",
    }
)

_VECTOR_TAGS: frozenset[str] = frozenset({"HeadingPairs", "TitlesOfParts", "HLinks", "DigSig"})

_MUTABLE_TAGS: frozenset[str] = frozenset(
    {
        "Company",
        "Manager",
        "Application",
        "AppVersion",
        "Template",
        "HyperlinkBase",
        "SharedDoc",
        "TotalTime",
    }
)

_READONLY_TAGS: frozenset[str] = frozenset(
    (_INTEGER_TAGS | _STRING_TAGS | _BOOLEAN_TAGS | _VECTOR_TAGS) - _MUTABLE_TAGS
)

_SNAKE_TO_CANONICAL: dict[str, str] = {
    "company": "Company",
    "manager": "Manager",
    "application": "Application",
    "app_version": "AppVersion",
    "template": "Template",
    "hyperlink_base": "HyperlinkBase",
    "shared_doc": "SharedDoc",
    "total_time": "TotalTime",
    "slides": "Slides",
    "hidden_slides": "HiddenSlides",
    "notes": "Notes",
    "paragraphs": "Paragraphs",
    "words": "Words",
    "lines": "Lines",
    "characters": "Characters",
    "characters_with_spaces": "CharactersWithSpaces",
    "mm_clips": "MMClips",
    "doc_security": "DocSecurity",
    "pages": "Pages",
    "presentation_format": "PresentationFormat",
    "scale_crop": "ScaleCrop",
    "links_up_to_date": "LinksUpToDate",
    "hyperlinks_changed": "HyperlinksChanged",
    "heading_pairs": "HeadingPairs",
    "titles_of_parts": "TitlesOfParts",
    "h_links": "HLinks",
    "dig_sig": "DigSig",
}


def _validate_xml_text(value: Any, prop_name: str) -> str:
    """Validate that value is a string containing only valid XML 1.0 characters.

    XML 1.0 valid characters:
    #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    """
    if not isinstance(value, str):
        raise TypeError(f"{prop_name} property requires str, got {type(value).__name__!r}")
    for idx, char in enumerate(value):
        cp = ord(char)
        if (
            cp in (0x9, 0xA, 0xD)
            or (0x20 <= cp <= 0xD7FF)
            or (0xE000 <= cp <= 0xFFFD)
            or (0x10000 <= cp <= 0x10FFFF)
        ):
            continue
        raise ValueError(
            f"{prop_name} contains invalid XML character {char!r} "
            f"(code point U+{cp:04X}) at index {idx}"
        )
    return value


def _validate_bool(value: Any, prop_name: str) -> bool:
    """Validate that value is a boolean."""
    if not isinstance(value, bool):
        raise TypeError(f"{prop_name} property requires bool, got {type(value).__name__!r}")
    return value


def _validate_total_time(value: Any, prop_name: str = "TotalTime") -> int:
    """Validate that value is a non-negative 32-bit integer representing minutes."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{prop_name} property requires int, got {type(value).__name__!r}")
    if value < 0:
        raise ValueError(f"{prop_name} property must be non-negative int, got {value}")
    if value > INT32_MAX:
        raise ValueError(f"{prop_name} property exceeds 32-bit signed integer range: {value}")
    return value


@dataclass(frozen=True)
class HeadingPair:
    """One heading pair entry consisting of part category name and part count."""

    name: str
    count: int

    def __iter__(self):
        return iter((self.name, self.count))


def _validate_heading_pairs_and_titles(
    heading_pairs: Any, titles_of_parts: Any
) -> tuple[tuple[HeadingPair, ...], tuple[str, ...]]:
    """Normalize an ordered, coherent pair of property vectors before mutation."""
    pairs: list[HeadingPair] = []
    titles: list[str] = []
    try:
        for value, name in (
            (heading_pairs, "heading_pairs"),
            (titles_of_parts, "titles_of_parts"),
        ):
            if not isinstance(value, Iterable) or isinstance(
                value, (str, bytes, bytearray, Mapping, Set)
            ):
                raise ExtendedPropertiesRefusal(f"{name} requires an ordered iterable")
        for index, pair in enumerate(heading_pairs):
            if isinstance(pair, HeadingPair):
                name, count = pair.name, pair.count
            elif isinstance(pair, (tuple, list)) and len(pair) == 2:
                name, count = pair
            else:
                raise ExtendedPropertiesRefusal(
                    f"heading_pairs[{index}] requires HeadingPair or a (name, count) pair"
                )
            pairs.append(
                HeadingPair(
                    _validate_vector_text(name, f"heading_pairs[{index}].name"),
                    _validate_total_time(count, f"heading_pairs[{index}].count"),
                )
            )
        for index, title in enumerate(titles_of_parts):
            titles.append(_validate_vector_text(title, f"titles_of_parts[{index}]"))
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ExtendedPropertiesRefusal):
            raise
        raise ExtendedPropertiesRefusal(str(exc)) from exc
    if sum(pair.count for pair in pairs) != len(titles):
        raise ExtendedPropertiesRefusal(
            "sum of heading pair counts must equal the number of titles of parts"
        )
    return tuple(pairs), tuple(titles)


def _validate_vector_text(value: Any, prop_name: str) -> str:
    text = _validate_xml_text(value, prop_name)
    if "\r" in text:
        raise ExtendedPropertiesRefusal(
            f"{prop_name} contains carriage returns that XML parsing would normalize"
        )
    return text


def _parse_heading_pairs(elem: ET.Element) -> tuple[HeadingPair, ...]:
    """Parse HeadingPairs vector element into a tuple of HeadingPair instances."""
    vt = STRICT_VTYPES_NS if elem.tag.startswith(f"{{{STRICT_EP_NS}}}") else VTYPES_NS
    vec = elem.find(f"{{{vt}}}vector")
    if vec is None:
        return ()
    items: list[Any] = []
    for var in vec.findall(f"{{{vt}}}variant"):
        if len(var) == 0:
            continue
        child = var[0]
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if child_tag in ("lpstr", "lpwstr", "bstr"):
            items.append(child.text or "")
        elif child_tag in ("i4", "int", "i2", "ui4"):
            try:
                items.append(int((child.text or "").strip()))
            except ValueError:
                items.append(0)
        elif child_tag == "bool":
            items.append((child.text or "").strip().lower() in ("true", "1"))
        else:
            items.append(child.text or "")
    pairs: list[HeadingPair] = []
    for i in range(0, len(items) - 1, 2):
        name = str(items[i])
        try:
            cnt = int(items[i + 1])
        except (ValueError, TypeError):
            cnt = 0
        pairs.append(HeadingPair(name, cnt))
    return tuple(pairs)


def _parse_titles_of_parts(elem: ET.Element) -> tuple[str, ...]:
    """Parse TitlesOfParts vector element into a tuple of title strings."""
    vt = STRICT_VTYPES_NS if elem.tag.startswith(f"{{{STRICT_EP_NS}}}") else VTYPES_NS
    vec = elem.find(f"{{{vt}}}vector")
    if vec is None:
        return ()
    titles: list[str] = []
    for child in vec:
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if child_tag in ("lpstr", "lpwstr", "bstr"):
            titles.append(child.text or "")
        elif child_tag == "variant" and len(child) > 0:
            inner = child[0]
            titles.append(inner.text or "")
    return tuple(titles)


def _vt_namespace(elem: ET.Element) -> str:
    return STRICT_VTYPES_NS if elem.tag.startswith(f"{{{STRICT_EP_NS}}}") else VTYPES_NS


def _parse_hlinks(elem: ET.Element) -> tuple[str, ...]:
    """Parse ep:HLinks into the text of each vt:variant's typed value, in document order."""
    vec = elem.find(f"{{{_vt_namespace(elem)}}}vector")
    if vec is None:
        return ()
    items: list[str] = []
    for child in vec:
        node = child[0] if child.tag.endswith("}variant") and len(child) > 0 else child
        items.append(node.text or "")
    return tuple(items)


def _parse_dig_sig(elem: ET.Element) -> str:
    """Parse ep:DigSig into the base64 text of its vt:blob (empty when there is none)."""
    blob = elem.find(f"{{{_vt_namespace(elem)}}}blob")
    return "" if blob is None else blob.text or ""


def read_extended_properties(xml_bytes: bytes) -> dict[str, Any]:
    """Parse extended properties XML into a structured dictionary.

    Returns a dict with keys:
      - 'values': dict[str, Any] mapping property tag to typed value
      - 'raw_elements': dict[str, ET.Element] mapping tag to element clone
      - 'raw_root': ET.Element root clone
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ExtendedPropertiesRefusal("extended properties part is malformed XML") from exc

    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if tag != "Properties":
        raise ExtendedPropertiesRefusal(
            f"invalid extended properties root element tag: {root.tag!r}"
        )

    values: dict[str, Any] = {}
    raw_elements: dict[str, ET.Element] = {}

    for child in root:
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        raw_elements[child_tag] = copy.deepcopy(child)

        if child_tag in _BOOLEAN_TAGS:
            text = (child.text or "").strip().lower()
            values[child_tag] = text in ("true", "1")
        elif child_tag in _INTEGER_TAGS:
            text = (child.text or "").strip()
            try:
                values[child_tag] = int(text)
            except ValueError as exc:
                raise ExtendedPropertiesRefusal(
                    f"extended property {child_tag} is not an integer: {text!r}"
                ) from exc
        elif child_tag in _STRING_TAGS:
            values[child_tag] = child.text or ""
        elif child_tag == "HeadingPairs":
            values[child_tag] = _parse_heading_pairs(child)
        elif child_tag == "TitlesOfParts":
            values[child_tag] = _parse_titles_of_parts(child)
        elif child_tag == "HLinks":
            values[child_tag] = _parse_hlinks(child)
        elif child_tag == "DigSig":
            values[child_tag] = _parse_dig_sig(child)
        else:
            values[child_tag] = child.text or ""

    return {
        "values": values,
        "raw_elements": raw_elements,
        "raw_root": copy.deepcopy(root),
    }


def _insert_canonical(parent: ET.Element, new_elem: ET.Element, tag_name: str) -> None:
    """Insert new_elem into parent respecting the ECMA-376 canonical element ordering."""
    target_idx = _ORDER_INDEX.get(tag_name, 999)
    for i, child in enumerate(list(parent)):
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        child_idx = _ORDER_INDEX.get(child_tag, 999)
        if child_idx > target_idx:
            parent.insert(i, new_elem)
            return
    parent.append(new_elem)


def _profile_namespaces(strict: bool) -> tuple[str, str]:
    """(extended-properties namespace, docPropsVTypes namespace) of one file profile."""
    return (STRICT_EP_NS, STRICT_VTYPES_NS) if strict else (EP_NS, VTYPES_NS)


def _root_is_strict(root: ET.Element) -> bool:
    return root.tag.startswith(f"{{{STRICT_EP_NS}}}")


def _tostring_normalized(root: ET.Element) -> bytes:
    """Serialize root element ensuring default namespace without ns0 prefix."""
    ns, vt = _profile_namespaces(_root_is_strict(root))
    ET.register_namespace("", ns)
    ET.register_namespace("vt", vt)
    try:
        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    finally:
        # The registry is process-wide: leave the transitional prefixes registered.
        ET.register_namespace("", EP_NS)
        ET.register_namespace("vt", VTYPES_NS)
    match = re.search(rb"<(?P<prefix>[A-Za-z_][A-Za-z0-9_.-]*):Properties(?=[\s>/])", payload)
    if match is not None:
        prefix = match.group("prefix").decode("ascii")
        qualified = re.compile(
            rb"(</?)" + re.escape(prefix.encode("ascii")) + rb":([A-Za-z_][\w.-]*)(?=[\s>/])"
        )
        normalized = qualified.sub(rb"\1\2", payload)
        payload = normalized.replace(
            f' xmlns:{prefix}="{ns}"'.encode("ascii"),
            f' xmlns="{ns}"'.encode("ascii"),
            1,
        )
    return payload


def _set_vector_value(element: ET.Element, key: str, value: tuple, vt: str = VTYPES_NS) -> None:
    """Replace a property's vector, retaining its attributes and other children."""
    previous = element.find(f"{{{vt}}}vector")
    position = list(element).index(previous) if previous is not None else 0
    for child in list(element):
        if child.tag == f"{{{vt}}}vector":
            element.remove(child)
    element.text = None
    vector = ET.Element(
        f"{{{vt}}}vector",
        {
            "size": str(2 * len(value) if key == "HeadingPairs" else len(value)),
            "baseType": "variant" if key == "HeadingPairs" else "lpstr",
        },
    )
    if key == "HeadingPairs":
        for pair in value:
            name = ET.SubElement(vector, f"{{{vt}}}variant")
            ET.SubElement(name, f"{{{vt}}}lpstr").text = pair.name
            count = ET.SubElement(vector, f"{{{vt}}}variant")
            ET.SubElement(count, f"{{{vt}}}i4").text = str(pair.count)
    else:
        for title in value:
            ET.SubElement(vector, f"{{{vt}}}lpstr").text = title
    element.insert(position, vector)


def serialize_extended_properties(
    values: dict[str, Any],
    modified_keys: set[str] | None = None,
    raw_elements: dict[str, ET.Element] | None = None,
    raw_root: ET.Element | None = None,
    strict: bool = False,
) -> bytes:
    """Serialize extended property values to standard OpenXML extended properties XML.

    When raw_root is provided, existing elements are updated in-place and non-modified
    elements (including unknown vendor tags) are preserved completely intact, in the
    root's own (transitional or strict) namespaces. A fresh part uses the strict
    namespaces when ``strict`` is set.
    """
    keys_to_update = set(modified_keys) if modified_keys is not None else set(values)
    vector_keys = {"HeadingPairs", "TitlesOfParts"}
    if keys_to_update & vector_keys:
        if not vector_keys <= values.keys():
            raise ExtendedPropertiesRefusal(
                "HeadingPairs and TitlesOfParts must be supplied together"
            )
        pairs, titles = _validate_heading_pairs_and_titles(
            values["HeadingPairs"], values["TitlesOfParts"]
        )
        values = {**values, "HeadingPairs": pairs, "TitlesOfParts": titles}
        keys_to_update.update(vector_keys)
    if raw_root is not None:
        root = copy.deepcopy(raw_root)
        ns, vt = _profile_namespaces(_root_is_strict(root))
        # Only the requested properties are rewritten; retained metadata is untouched.

        for key in keys_to_update:
            if key not in values:
                continue
            val = values[key]
            elem = root.find(f"{{{ns}}}{key}")
            if elem is None:
                elem = root.find(key)

            if elem is not None:
                if key in vector_keys:
                    _set_vector_value(elem, key, val, vt)
                elif key in _BOOLEAN_TAGS:
                    elem.text = "true" if val else "false"
                elif key in _INTEGER_TAGS:
                    elem.text = str(val)
                else:
                    elem.text = str(val)
            else:
                new_elem = ET.Element(f"{{{ns}}}{key}")
                if key in vector_keys:
                    _set_vector_value(new_elem, key, val, vt)
                elif key in _BOOLEAN_TAGS:
                    new_elem.text = "true" if val else "false"
                elif key in _INTEGER_TAGS:
                    new_elem.text = str(val)
                else:
                    new_elem.text = str(val)
                _insert_canonical(root, new_elem, key)

        return _tostring_normalized(root)
    # Creating fresh Properties element
    ns, vt = _profile_namespaces(strict)
    root = ET.Element(f"{{{ns}}}Properties")
    all_keys = dict(values)
    if "Application" not in all_keys:
        all_keys["Application"] = "WolfPPT"
    if "AppVersion" not in all_keys:
        all_keys["AppVersion"] = "16.0000"

    sorted_keys = sorted(
        all_keys.keys(),
        key=lambda k: _ORDER_INDEX.get(k, 999),
    )

    for key in sorted_keys:
        val = all_keys[key]
        elem = ET.SubElement(root, f"{{{ns}}}{key}")
        if key in vector_keys:
            _set_vector_value(elem, key, val, vt)
        elif key in _BOOLEAN_TAGS:
            elem.text = "true" if val else "false"
        elif key in _INTEGER_TAGS:
            elem.text = str(val)
        else:
            elem.text = str(val)

    return _tostring_normalized(root)


class ExtendedPropertiesSnapshot(dict[str, Any]):
    """Snapshot of extended properties passed to edit queues and save operations."""

    def __init__(
        self,
        values: dict[str, Any],
        modified_keys: set[str],
        raw_elements: dict[str, ET.Element],
        part_name: str,
        existing_rel_id: str | None,
        source_xml: bytes | None = None,
        raw_root: ET.Element | None = None,
    ) -> None:
        super().__init__(values)
        self.modified_keys: set[str] = set(modified_keys)
        self.raw_elements: dict[str, ET.Element] = {
            k: copy.deepcopy(v) for k, v in raw_elements.items()
        }
        self.part_name: str = part_name
        self.existing_rel_id: str | None = existing_rel_id
        self.source_xml: bytes | None = source_xml
        self.raw_root: ET.Element | None = copy.deepcopy(raw_root) if raw_root is not None else None

    def copy(self) -> ExtendedPropertiesSnapshot:
        return ExtendedPropertiesSnapshot(
            values=dict(self),
            modified_keys=set(self.modified_keys),
            raw_elements={k: copy.deepcopy(v) for k, v in self.raw_elements.items()},
            part_name=self.part_name,
            existing_rel_id=self.existing_rel_id,
            source_xml=self.source_xml,
            raw_root=copy.deepcopy(self.raw_root) if self.raw_root is not None else None,
        )


# ---------------------------------------------------------------------------
# Slide counters and HeadingPairs / TitlesOfParts refresh from a staged deck
# ---------------------------------------------------------------------------

SLIDE_TITLES_HEADING = "Slide Titles"
UNTITLED_SLIDE_TITLE = "PowerPoint Presentation"
# PowerPoint lists these part categories ahead of the slide titles.
_LEADING_HEADINGS = ("Fonts Used", "Theme", "Design Template")


def _staged_root(package: Any, roots: dict, part: str) -> ET.Element | None:
    """A part as staged so far, parsed privately when not yet staged."""
    from .presentation_tags import parse_xml

    if part in roots:
        return roots[part]
    if part not in package.namelist():
        return None
    return parse_xml(package.read(part), read_only=True)


def _relationship_targets(package: Any, roots: dict, part: str) -> dict[str, tuple[str, str]]:
    from .package_parts import rels_part_for_package_part, resolve_package_target

    rels = _staged_root(package, roots, rels_part_for_package_part(part))
    if rels is None:
        return {}
    return {
        rel.get("Id", ""): (
            rel.get("Type", ""),
            resolve_package_target(part, rel.get("Target", "")),
        )
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        if rel.get("TargetMode", "Internal") == "Internal"
    }


def _slide_title(root: ET.Element) -> str:
    from .package_parts import A_NS, P_NS
    from .xml_helpers import ooxml_namespace

    p_ns = ooxml_namespace(root, P_NS)
    a_ns = ooxml_namespace(root, A_NS)
    for shape in root.iter(f"{{{p_ns}}}sp"):
        placeholder = shape.find(f"{{{p_ns}}}nvSpPr/{{{p_ns}}}nvPr/{{{p_ns}}}ph")
        if placeholder is None or placeholder.get("type") not in ("title", "ctrTitle"):
            continue
        paragraphs = [
            "".join(text.text or "" for text in paragraph.iter(f"{{{a_ns}}}t"))
            for paragraph in shape.iter(f"{{{a_ns}}}p")
        ]
        return " ".join(p.strip() for p in paragraphs if p.strip()) or UNTITLED_SLIDE_TITLE
    return UNTITLED_SLIDE_TITLE


def staged_slide_summary(package: Any, roots: dict, source: str) -> list[tuple[str, bool, bool]]:
    """(title, hidden, has notes) for each slide in staged presentation order."""
    from .package_parts import P_NS, R_NS
    from .xml_helpers import ooxml_namespace

    presentation = _staged_root(package, roots, source)
    if presentation is None:
        return []
    p_ns = ooxml_namespace(presentation, P_NS)
    r_ns = ooxml_namespace(presentation, R_NS)
    targets = _relationship_targets(package, roots, source)
    slides = []
    for slide_id in presentation.iterfind(f"{{{p_ns}}}sldIdLst/{{{p_ns}}}sldId"):
        _, part = targets.get(slide_id.get(f"{{{r_ns}}}id", ""), ("", ""))
        root = _staged_root(package, roots, part) if part else None
        if root is None:
            raise ExtendedPropertiesRefusal(f"slide id {slide_id.get('id')} has no part")
        notes = any(
            kind.endswith("/notesSlide")
            for kind, _ in _relationship_targets(package, roots, part).values()
        )
        slides.append((_slide_title(root), root.get("show", "true") in ("0", "false"), notes))
    return slides


def _vector_items(element: ET.Element | None, vt: str) -> list[ET.Element] | None:
    vector = None if element is None else element.find(f"{{{vt}}}vector")
    return None if vector is None else list(vector)


def _set_counter(root: ET.Element, ns: str, name: str, value: int) -> None:
    element = root.find(f"{{{ns}}}{name}")
    if element is None:
        element = ET.Element(f"{{{ns}}}{name}")
        _insert_canonical(root, element, name)
    try:
        if element.text is not None and int(element.text.strip()) == value:
            return
    except ValueError:
        pass
    element.text = str(value)


def _refresh_vectors(root: ET.Element, ns: str, vt: str, titles: list[str]) -> None:
    """Rewrite only the slide-title pair and its span; keep other categories.

    A stored pair/title mismatch leaves both vectors unchanged: the span of
    the slide titles cannot be located without guessing.
    """
    headings = root.find(f"{{{ns}}}HeadingPairs")
    parts = root.find(f"{{{ns}}}TitlesOfParts")
    if headings is None and parts is None:
        for name, base in (
            ("HeadingPairs", "variant"),
            ("TitlesOfParts", "lpstr"),
        ):
            element = ET.Element(f"{{{ns}}}{name}")
            ET.SubElement(element, f"{{{vt}}}vector", {"size": "0", "baseType": base})
            _insert_canonical(root, element, name)
        headings = root.find(f"{{{ns}}}HeadingPairs")
        parts = root.find(f"{{{ns}}}TitlesOfParts")
    variants = _vector_items(headings, vt)
    title_items = _vector_items(parts, vt)
    if variants is None or title_items is None or len(variants) % 2:
        return
    names: list[str] = []
    counts: list[int] = []
    for name_variant, count_variant in zip(variants[::2], variants[1::2], strict=True):
        if len(name_variant) != 1 or len(count_variant) != 1:
            return
        try:
            counts.append(int((count_variant[0].text or "").strip()))
        except ValueError:
            return
        names.append(name_variant[0].text or "")
    if sum(counts) != len(title_items):
        return
    heading_vector = headings.find(f"{{{vt}}}vector")
    title_vector = parts.find(f"{{{vt}}}vector")
    if SLIDE_TITLES_HEADING in names:
        index = names.index(SLIDE_TITLES_HEADING)
        variants[2 * index + 1][0].text = str(len(titles))
    else:
        index = max(
            (i + 1 for i, name in enumerate(names) if name in _LEADING_HEADINGS),
            default=0,
        )
        counts.insert(index, 0)
        name_variant = ET.Element(f"{{{vt}}}variant")
        ET.SubElement(name_variant, f"{{{vt}}}lpstr").text = SLIDE_TITLES_HEADING
        count_variant = ET.Element(f"{{{vt}}}variant")
        ET.SubElement(count_variant, f"{{{vt}}}i4").text = str(len(titles))
        heading_vector.insert(2 * index, name_variant)
        heading_vector.insert(2 * index + 1, count_variant)
    offset = sum(counts[:index])
    for item in title_items[offset : offset + counts[index]]:
        title_vector.remove(item)
    base = title_vector.get("baseType", "lpstr")
    tag = f"{{{vt}}}{base if base in ('lpstr', 'lpwstr') else 'lpstr'}"
    for position, title in enumerate(titles):
        item = ET.Element(tag)
        item.text = title
        title_vector.insert(offset + position, item)
    heading_vector.set("size", str(len(heading_vector)))
    title_vector.set("size", str(len(title_vector)))


def refresh_titles_of_parts(package: Any, roots: dict, source: str) -> str | None:
    """Update app.xml slide counters and slide titles from the staged deck.

    Returns the extended properties part, or None when the package has none
    (no part is created). Unknown elements and other title categories stay.
    """
    from .presentation_tags import parse_xml

    package_rels = _relationship_targets(package, roots, "")
    part = next(
        (
            target
            for kind, target in package_rels.values()
            if kind.rpartition("/")[2] in ("extended-properties", "extendedProperties")
        ),
        None,
    )
    if part is None or (part not in roots and part not in package.namelist()):
        return None
    root = roots.setdefault(part, parse_xml(package.read(part)))
    ns = root.tag[1:].partition("}")[0] if root.tag.startswith("{") else ""
    if ns not in (EP_NS, STRICT_EP_NS) or root.tag != f"{{{ns}}}Properties":
        raise ExtendedPropertiesRefusal(f"invalid extended properties root {root.tag!r}")
    vt = STRICT_VTYPES_NS if ns == STRICT_EP_NS else VTYPES_NS
    slides = staged_slide_summary(package, roots, source)
    _set_counter(root, ns, "Slides", len(slides))
    _set_counter(root, ns, "Notes", sum(notes for _, _, notes in slides))
    _set_counter(root, ns, "HiddenSlides", sum(hidden for _, hidden, _ in slides))
    _refresh_vectors(root, ns, vt, [title for title, _, _ in slides])
    return part


@dataclass(frozen=True, eq=False)
class TitlesOfPartsRefresh:
    """Queued view-lifecycle operation running refresh_titles_of_parts."""

    presentation: Any

    def validate(self) -> None:
        if self.presentation._disposed:
            raise RuntimeError("presentation is disposed")

    def apply(self, package: Any, roots: dict, source: str) -> None:
        refresh_titles_of_parts(package, roots, source)


@dataclass(frozen=True, eq=False)
class _HeadingPairsAndTitlesEdit:
    """One atomic paired-vector edit on the final staged package."""

    presentation: Any
    heading_pairs: tuple[HeadingPair, ...]
    titles_of_parts: tuple[str, ...]

    def validate(self) -> None:
        if self.presentation._disposed:
            raise ExtendedPropertiesRefusal("presentation is disposed")
        _validate_heading_pairs_and_titles(self.heading_pairs, self.titles_of_parts)

    def apply(self, package: Any, roots: dict, source: str) -> None:
        from .presentation_tags import add_part

        self.validate()
        targets = _relationship_targets(package, roots, "")
        part = next(
            (
                target
                for kind, target in targets.values()
                if kind.rpartition("/")[2] in ("extended-properties", "extendedProperties")
            ),
            None,
        )
        if part is None:
            root = ET.fromstring(serialize_extended_properties({}))
            part, _ = add_part(
                package,
                roots,
                "",
                EXTENDED_PROPERTIES_PARTNAME.removesuffix(".xml"),
                EXTENDED_PROPERTIES_REL_TYPE,
                EXTENDED_PROPERTIES_CONTENT_TYPE,
                root,
            )
        else:
            root = _staged_root(package, roots, part)
            if root is None:
                raise ExtendedPropertiesRefusal("extended properties part is missing")
            roots[part] = root
        ns = root.tag[1:].partition("}")[0] if root.tag.startswith("{") else ""
        if ns not in (EP_NS, STRICT_EP_NS) or root.tag != f"{{{ns}}}Properties":
            raise ExtendedPropertiesRefusal(f"invalid extended properties root {root.tag!r}")
        vt = STRICT_VTYPES_NS if ns == STRICT_EP_NS else VTYPES_NS
        for key, value in (
            ("HeadingPairs", self.heading_pairs),
            ("TitlesOfParts", self.titles_of_parts),
        ):
            element = root.find(f"{{{ns}}}{key}")
            if element is None:
                element = ET.Element(f"{{{ns}}}{key}")
                _insert_canonical(root, element, key)
            _set_vector_value(element, key, value, vt)


class ExtendedProperties:
    """Presentation extended document properties (docProps/app.xml) facade."""

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation
        self._source_path = (
            presentation
            if isinstance(presentation, (str, Path))
            else getattr(presentation, "path", None)
        )
        self._values: dict[str, Any] = {}
        self._raw_elements: dict[str, ET.Element] = {}
        self._raw_root: ET.Element | None = None
        self._source_xml: bytes | None = None
        self._part_name: str = EXTENDED_PROPERTIES_PARTNAME
        self._existing_rel_id: str | None = None
        self._modified_keys: set[str] = set()
        self._vectors_modified = False
        self._load()

    def _load(self) -> None:
        from .extended_property_edits import resolve_extended_properties_part

        if self._source_path is None or not Path(self._source_path).is_file():
            self._values = {}
            self._raw_elements = {}
            self._raw_root = None
            self._source_xml = None
            self._part_name = EXTENDED_PROPERTIES_PARTNAME
            self._existing_rel_id = None
            return

        with zipfile.ZipFile(self._source_path) as package:
            rel_id, part_name = resolve_extended_properties_part(package)
            self._existing_rel_id = rel_id
            if part_name is not None:
                self._part_name = part_name
                payload = package.read(part_name)
                self._source_xml = payload
                parsed = read_extended_properties(payload)
                self._values = parsed["values"]
                self._raw_elements = parsed["raw_elements"]
                self._raw_root = parsed["raw_root"]
            else:
                self._part_name = EXTENDED_PROPERTIES_PARTNAME
                self._values = {}
                self._raw_elements = {}
                self._raw_root = None
                self._source_xml = None

    @property
    def partname(self) -> str:
        """OPC part name starting with a forward slash."""
        name = self._part_name.lstrip("/")
        return f"/{name}"

    @property
    def content_type(self) -> str:
        """MIME content type for the extended properties part."""
        if self._source_path is not None and Path(self._source_path).is_file():
            ct = package_part_content_type(Path(self._source_path), self.partname)
            if ct:
                return ct
        return EXTENDED_PROPERTIES_CONTENT_TYPE

    @property
    def blob(self) -> bytes:
        """Serialized XML bytes of the current extended properties."""
        return serialize_extended_properties(
            values=self._values,
            modified_keys=self._modified_keys
            | ({"HeadingPairs", "TitlesOfParts"} if self._vectors_modified else set()),
            raw_elements=self._raw_elements,
            raw_root=self._raw_root,
        )

    @property
    def part(self) -> ExtendedProperties:
        return self

    @property
    def package(self) -> Any:
        return self._presentation

    # ------------------------------------------------------------------
    # Mutable properties (canonical snake_case only):
    # company, manager, application, app_version, template,
    # hyperlink_base, shared_doc, total_time (minutes)
    # ------------------------------------------------------------------

    @property
    def company(self) -> str:
        return str(self._values.get("Company") or "")

    @company.setter
    def company(self, value: Any) -> None:
        val = _validate_xml_text(value, "company")
        if val == self.company and "Company" in self._values:
            return
        self._values["Company"] = val
        self._modified_keys.add("Company")
        self._queue_edit()

    @property
    def manager(self) -> str:
        return str(self._values.get("Manager") or "")

    @manager.setter
    def manager(self, value: Any) -> None:
        val = _validate_xml_text(value, "manager")
        if val == self.manager and "Manager" in self._values:
            return
        self._values["Manager"] = val
        self._modified_keys.add("Manager")
        self._queue_edit()

    @property
    def application(self) -> str:
        return str(self._values.get("Application") or "")

    @application.setter
    def application(self, value: Any) -> None:
        val = _validate_xml_text(value, "application")
        if val == self.application and "Application" in self._values:
            return
        self._values["Application"] = val
        self._modified_keys.add("Application")
        self._queue_edit()

    @property
    def app_version(self) -> str:
        return str(self._values.get("AppVersion") or "")

    @app_version.setter
    def app_version(self, value: Any) -> None:
        val = _validate_xml_text(value, "app_version")
        if val == self.app_version and "AppVersion" in self._values:
            return
        self._values["AppVersion"] = val
        self._modified_keys.add("AppVersion")
        self._queue_edit()

    @property
    def template(self) -> str:
        return str(self._values.get("Template") or "")

    @template.setter
    def template(self, value: Any) -> None:
        val = _validate_xml_text(value, "template")
        if val == self.template and "Template" in self._values:
            return
        self._values["Template"] = val
        self._modified_keys.add("Template")
        self._queue_edit()

    @property
    def hyperlink_base(self) -> str:
        return str(self._values.get("HyperlinkBase") or "")

    @hyperlink_base.setter
    def hyperlink_base(self, value: Any) -> None:
        val = _validate_xml_text(value, "hyperlink_base")
        if val == self.hyperlink_base and "HyperlinkBase" in self._values:
            return
        self._values["HyperlinkBase"] = val
        self._modified_keys.add("HyperlinkBase")
        self._queue_edit()

    @property
    def shared_doc(self) -> bool:
        return bool(self._values.get("SharedDoc") or False)

    @shared_doc.setter
    def shared_doc(self, value: Any) -> None:
        val = _validate_bool(value, "shared_doc")
        if val == self.shared_doc and "SharedDoc" in self._values:
            return
        self._values["SharedDoc"] = val
        self._modified_keys.add("SharedDoc")
        self._queue_edit()

    @property
    def total_time(self) -> int:
        return int(self._values.get("TotalTime") or 0)

    @total_time.setter
    def total_time(self, value: Any) -> None:
        val = _validate_total_time(value, "total_time")
        if val == self.total_time and "TotalTime" in self._values:
            return
        self._values["TotalTime"] = val
        self._modified_keys.add("TotalTime")
        self._queue_edit()

    # ------------------------------------------------------------------
    # Read-only counters and vector accessors (paired edits use the method below)
    # ------------------------------------------------------------------

    @property
    def slides(self) -> int:
        return int(self._values.get("Slides") or 0)

    @property
    def hidden_slides(self) -> int:
        return int(self._values.get("HiddenSlides") or 0)

    @property
    def notes(self) -> int:
        return int(self._values.get("Notes") or 0)

    @property
    def paragraphs(self) -> int:
        return int(self._values.get("Paragraphs") or 0)

    @property
    def words(self) -> int:
        return int(self._values.get("Words") or 0)

    @property
    def lines(self) -> int:
        return int(self._values.get("Lines") or 0)

    @property
    def characters(self) -> int:
        return int(self._values.get("Characters") or 0)

    @property
    def characters_with_spaces(self) -> int:
        return int(self._values.get("CharactersWithSpaces") or 0)

    @property
    def mm_clips(self) -> int:
        return int(self._values.get("MMClips") or 0)

    @property
    def doc_security(self) -> int:
        return int(self._values.get("DocSecurity") or 0)

    @property
    def pages(self) -> int:
        return int(self._values.get("Pages") or 0)

    @property
    def presentation_format(self) -> str:
        return str(self._values.get("PresentationFormat") or "")

    @property
    def scale_crop(self) -> bool:
        return bool(self._values.get("ScaleCrop") or False)

    @property
    def links_up_to_date(self) -> bool:
        return bool(self._values.get("LinksUpToDate") or False)

    @property
    def hyperlinks_changed(self) -> bool:
        return bool(self._values.get("HyperlinksChanged") or False)

    @property
    def heading_pairs(self) -> tuple[HeadingPair, ...]:
        val = self._values.get("HeadingPairs")
        if isinstance(val, tuple):
            return val
        return ()

    @property
    def titles_of_parts(self) -> tuple[str, ...]:
        val = self._values.get("TitlesOfParts")
        if isinstance(val, tuple):
            return val
        return ()

    def set_heading_pairs_and_titles(
        self,
        heading_pairs: Iterable[HeadingPair | tuple[str, int]],
        titles_of_parts: Iterable[str],
    ) -> None:
        """Atomically replace the heading categories and their ordered title spans.

        Entries may be ``HeadingPair`` instances or ``(name, count)`` pairs.
        Names and titles must be XML strings without carriage returns (which XML
        parsing normalizes). Counts must be non-negative signed 32-bit integers,
        not booleans, and their sum must equal the title count.
        Invalid inputs raise ``ExtendedPropertiesRefusal`` before state or queues
        change. Separate assignment to either vector remains read-only.

        The paired write uses the package-operation queue, alongside title
        refresh, in call order; the existing scalar property queue is unchanged.
        """
        pairs, titles = _validate_heading_pairs_and_titles(heading_pairs, titles_of_parts)
        presentation = self._presentation
        if getattr(presentation, "_disposed", False):
            raise ExtendedPropertiesRefusal("presentation is disposed")
        view = getattr(presentation, "view_state", None)
        if view is None:
            raise ExtendedPropertiesRefusal(
                "set_heading_pairs_and_titles requires an open Presentation"
            )
        view.stage_package_operation(_HeadingPairsAndTitlesEdit(presentation, pairs, titles))
        self._values["HeadingPairs"] = pairs
        self._values["TitlesOfParts"] = titles
        self._vectors_modified = True

    @property
    def h_links(self) -> tuple[Any, ...]:
        val = self._values.get("HLinks")
        if isinstance(val, tuple):
            return val
        return ()

    @property
    def dig_sig(self) -> Any:
        return self._values.get("DigSig")

    # ------------------------------------------------------------------
    # Mapping-like inspection and unknown metadata preservation
    # ------------------------------------------------------------------

    def _canonical_key(self, key: str) -> str:
        if key in _SNAKE_TO_CANONICAL:
            return _SNAKE_TO_CANONICAL[key]
        return key

    def __getitem__(self, key: str) -> Any:
        canonical = self._canonical_key(key)
        if canonical in self._values:
            return self._values[canonical]
        if canonical in self._raw_elements:
            elem = self._raw_elements[canonical]
            return elem.text or ""
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        canonical = self._canonical_key(key)
        return canonical in self._values or canonical in self._raw_elements

    def __len__(self) -> int:
        return len(self.keys())

    def keys(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for k in self._values:
            if k not in seen:
                seen.add(k)
                result.append(k)
        for k in self._raw_elements:
            if k not in seen:
                seen.add(k)
                result.append(k)
        return result

    def items(self) -> list[tuple[str, Any]]:
        return [(k, self[k]) for k in self.keys()]

    def values(self) -> list[Any]:
        return [self[k] for k in self.keys()]

    # ------------------------------------------------------------------
    # Queue / snapshot integration
    # ------------------------------------------------------------------

    def _queue_edit(self) -> None:
        queue_fn = getattr(self._presentation, "_queue_extended_properties", None)
        if callable(queue_fn):
            queue_fn(self._snapshot())

    def _snapshot(self) -> ExtendedPropertiesSnapshot:
        return ExtendedPropertiesSnapshot(
            values=dict(self._values),
            modified_keys=set(self._modified_keys),
            raw_elements={k: copy.deepcopy(v) for k, v in self._raw_elements.items()},
            part_name=self._part_name,
            existing_rel_id=self._existing_rel_id,
            source_xml=self._source_xml,
            raw_root=copy.deepcopy(self._raw_root) if self._raw_root is not None else None,
        )

    def refresh_titles_of_parts(self) -> None:
        """Recompute slide counters and the slide-title vectors on next save.

        The refresh runs on the final staged package of that save, so slides
        added, deleted, reordered or retitled in the same session are counted.
        """
        presentation = self._presentation
        view = getattr(presentation, "view_state", None)
        if view is None:
            raise TypeError("refresh_titles_of_parts requires an open Presentation")
        if not any(
            isinstance(operation, TitlesOfPartsRefresh) for operation in view.pending_operations()
        ):
            view.stage_package_operation(TitlesOfPartsRefresh(presentation))

    def __repr__(self) -> str:
        return (
            f"<ExtendedProperties "
            f"app={self.application!r} "
            f"company={self.company!r} "
            f"manager={self.manager!r}>"
        )


__all__ = [
    "CONTENT_TYPES_NS",
    "EP_NS",
    "EXTENDED_PROPERTIES_CONTENT_TYPE",
    "EXTENDED_PROPERTIES_PARTNAME",
    "EXTENDED_PROPERTIES_REL_TYPE",
    "EXTENDED_PROPERTIES_REL_TYPES",
    "PKG_REL_NS",
    "SLIDE_TITLES_HEADING",
    "STRICT_EXTENDED_PROPERTIES_REL_TYPE",
    "UNTITLED_SLIDE_TITLE",
    "VTYPES_NS",
    "ExtendedProperties",
    "ExtendedPropertiesRefusal",
    "ExtendedPropertiesSnapshot",
    "HeadingPair",
    "TitlesOfPartsRefresh",
    "read_extended_properties",
    "refresh_titles_of_parts",
    "serialize_extended_properties",
    "staged_slide_summary",
]
