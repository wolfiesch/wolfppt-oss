"""Transactional embedded TrueType assets for saved presentations.

``FontManager(presentation).add(family, path)`` embeds an explicitly supplied
single-face TrueType file. Use ``registry()`` as the ``fonts`` argument to Wolf
rendering; no installed-font discovery or substitution is performed. Save
pending facade edits before using this manager, and save the presentation to
persist its rewritten package. Reacquire slide/shape handles after a mutation.
"""

from __future__ import annotations

import posixpath
import re
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from .font_assets import FontAsset, FontRegistry, admit_font_bytes
from .package_parts import (
    CONTENT_TYPES_NS,
    P_NS,
    PKG_REL_NS,
    R_NS,
    open_package_source,
    rels_part_for_package_part,
    resolve_package_target,
)
from .presentation_tags import parse_xml, serialize_xml, xml_string
from .xml_helpers import STRICT_P_NS, STRICT_R_NS, ooxml_namespace

_FONT_CONTENT_TYPE = "application/x-fontdata"
_PITCH_FAMILIES = frozenset(family + pitch for family in range(0, 81, 16) for pitch in range(3))
_STYLES = {
    "regular": (False, False),
    "bold": (True, False),
    "italic": (False, True),
    "boldItalic": (True, True),
}
_ERRORS = (
    ValueError,
    RuntimeError,
    OSError,
    KeyError,
    TypeError,
    ET.ParseError,
    zipfile.BadZipFile,
    struct.error,
    IndexError,
)


class EmbeddedFontRefusal(ValueError):
    """A font cannot be admitted or its package model cannot be safely changed."""


def _xml(payload: bytes) -> ET.Element:
    # DTDs are not retained by the lifecycle serializer. Refuse rather than
    # silently removing declarations (including UTF-16/32 encoded declarations).
    markup = payload.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in markup or b"<!ENTITY" in markup:
        raise EmbeddedFontRefusal("XML declarations with DTDs or entities are unsupported")
    return parse_xml(payload)


@dataclass(frozen=True)
class EmbeddedFont:
    """One family/style's exact, non-obfuscated embedded TrueType bytes."""

    family: str
    bold: bool
    italic: bool
    partname: str
    payload: bytes


@dataclass
class _Entry:
    asset: EmbeddedFont
    owner: ET.Element
    variant: ET.Element
    relationship: ET.Element


@dataclass
class _Model:
    part: str
    root: ET.Element
    rels_part: str
    rels: ET.Element
    types: ET.Element
    fonts: ET.Element | None
    entries: list[_Entry]
    names: set[str]


def _attributes(element: ET.Element, allowed: set[str], label: str) -> None:
    if any(
        name not in allowed and name != "xmlns" and not name.startswith("xmlns:")
        for name in element.attrib
    ):
        raise EmbeddedFontRefusal(f"unsupported {label} attributes")


def _plain(element: ET.Element, label: str) -> None:
    if len(element) or (element.text and element.text.strip()):
        raise EmbeddedFontRefusal(f"unsupported {label} children or text")


def _family(family: str, bold: bool, italic: bool) -> str:
    try:
        xml_string(family, "font family")
    except (TypeError, ValueError) as exc:
        raise EmbeddedFontRefusal(str(exc)) from exc
    if not family.strip() or family != family.strip():
        raise EmbeddedFontRefusal("font family must be nonblank without surrounding whitespace")
    if not isinstance(bold, bool) or not isinstance(italic, bool):
        raise EmbeddedFontRefusal("font bold and italic must be bools")
    return family


def _target(source: str, target: str) -> str:
    if not target or "\\" in target or "%" in target:
        raise EmbeddedFontRefusal("unsupported font relationship target")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise EmbeddedFontRefusal("external or qualified font relationship target")
    part = resolve_package_target(source, target)
    if not part or part.startswith("../") or part.startswith("/") or part == ".":
        raise EmbeddedFontRefusal("font relationship escapes the package")
    return part


def _relationships(package: Any, part: str, *, optional: bool = False) -> ET.Element:
    if optional and part not in package.namelist():
        return ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    root = _xml(package.read(part))
    if root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise EmbeddedFontRefusal("invalid package relationships root")
    ids: set[str] = set()
    for node in root:
        if not isinstance(node.tag, str):
            continue
        if node.tag != f"{{{PKG_REL_NS}}}Relationship":
            raise EmbeddedFontRefusal("unsupported relationship model")
        rid = node.get("Id", "")
        if not rid or rid in ids:
            raise EmbeddedFontRefusal("missing or duplicate relationship id")
        ids.add(rid)
    return root


def _content_types(package: Any) -> ET.Element:
    root = _xml(package.read("[Content_Types].xml"))
    if root.tag != f"{{{CONTENT_TYPES_NS}}}Types":
        raise EmbeddedFontRefusal("invalid content types root")
    seen: set[tuple[str, str]] = set()
    for node in root:
        if not isinstance(node.tag, str):
            continue
        if node.tag == f"{{{CONTENT_TYPES_NS}}}Override":
            key = ("override", node.get("PartName", ""))
        elif node.tag == f"{{{CONTENT_TYPES_NS}}}Default":
            key = ("default", node.get("Extension", "").casefold())
        else:
            raise EmbeddedFontRefusal("unsupported content types model")
        if not key[1] or key in seen or not node.get("ContentType"):
            raise EmbeddedFontRefusal("missing or duplicate content type declaration")
        seen.add(key)
    return root


def _content_type(types: ET.Element, part: str) -> str | None:
    default = None
    extension = posixpath.splitext(part)[1].lstrip(".").casefold()
    for node in types:
        if node.tag == f"{{{CONTENT_TYPES_NS}}}Override" and node.get("PartName") == "/" + part:
            return node.get("ContentType")
        if (
            node.tag == f"{{{CONTENT_TYPES_NS}}}Default"
            and node.get("Extension", "").casefold() == extension
        ):
            default = node.get("ContentType")
    return default


def _model(package: Any) -> _Model:
    names_list = package.namelist()
    names = set(names_list)
    if len(names) != len(names_list):
        raise EmbeddedFontRefusal("duplicate package parts are unsupported")
    package_rels = _relationships(package, "_rels/.rels")
    documents = [
        node
        for node in package_rels
        if isinstance(node.tag, str)
        and node.get("Type") in {f"{R_NS}/officeDocument", f"{STRICT_R_NS}/officeDocument"}
    ]
    if len(documents) != 1 or documents[0].get("TargetMode", "Internal") != "Internal":
        raise EmbeddedFontRefusal("presentation needs one internal office document relationship")
    part = _target("", documents[0].get("Target", ""))
    root = _xml(package.read(part))
    if root.tag not in {f"{{{P_NS}}}presentation", f"{{{STRICT_P_NS}}}presentation"}:
        raise EmbeddedFontRefusal("unsupported presentation root")
    flag = root.get("embedTrueTypeFonts")
    if flag is not None and flag not in {"true", "false", "1", "0"}:
        raise EmbeddedFontRefusal("invalid embedTrueTypeFonts flag")
    pns, rns = ooxml_namespace(root, P_NS), ooxml_namespace(root, R_NS)
    for element in root.iter():
        if (
            isinstance(element.tag, str)
            and element.tag.rsplit("}", 1)[-1] == "embeddedFontLst"
            and (element.tag != f"{{{pns}}}embeddedFontLst" or element not in list(root))
        ):
            raise EmbeddedFontRefusal("unsupported nested or mixed-profile embedded font list")
    font_lists = root.findall(f"{{{pns}}}embeddedFontLst")
    if len(font_lists) > 1:
        raise EmbeddedFontRefusal("duplicate embedded font lists")
    fonts = font_lists[0] if font_lists else None
    rels_part = rels_part_for_package_part(part)
    rels = _relationships(package, rels_part, optional=True)
    relationships = {node.get("Id"): node for node in rels if isinstance(node.tag, str)}
    types = _content_types(package)
    entries: list[_Entry] = []
    seen_families: set[str] = set()
    used_ids: set[str] = set()
    if fonts is not None:
        _attributes(fonts, set(), "embedded font list")
        if fonts.text and fonts.text.strip():
            raise EmbeddedFontRefusal("unsupported embedded font list text")
        if fonts.tail and fonts.tail.strip():
            raise EmbeddedFontRefusal("unsupported embedded font list tail text")
        for owner in fonts:
            if owner.tag != f"{{{pns}}}embeddedFont":
                raise EmbeddedFontRefusal("unsupported embedded font list metadata")
            _attributes(owner, set(), "embedded font")
            if owner.text and owner.text.strip():
                raise EmbeddedFontRefusal("unsupported embedded font text")
            if owner.tail and owner.tail.strip():
                raise EmbeddedFontRefusal("unsupported embedded font tail text")
            children = list(owner)
            if not children or children[0].tag != f"{{{pns}}}font":
                raise EmbeddedFontRefusal("embedded font needs a leading font declaration")
            font = children[0]
            _attributes(font, {"typeface", "panose", "pitchFamily", "charset"}, "font metadata")
            _plain(font, "font metadata")
            if any(child.tail and child.tail.strip() for child in children):
                raise EmbeddedFontRefusal("unsupported embedded font metadata tail text")
            family = _family(font.get("typeface", ""), False, False)
            if family.casefold() in seen_families:
                raise EmbeddedFontRefusal("duplicate embedded font family")
            seen_families.add(family.casefold())
            panose = font.get("panose")
            if panose is not None and re.fullmatch(r"[0-9A-Fa-f]{20}", panose) is None:
                raise EmbeddedFontRefusal("unsupported font panose metadata")
            for attr in ("pitchFamily", "charset"):
                value = font.get(attr)
                if value is None:
                    continue
                if re.fullmatch(r"[+-]?[0-9]+", value) is None:
                    raise EmbeddedFontRefusal(f"unsupported font {attr} metadata")
                number = int(value)
                if (attr == "pitchFamily" and number not in _PITCH_FAMILIES) or (
                    attr == "charset" and not -128 <= number <= 127
                ):
                    raise EmbeddedFontRefusal(f"unsupported font {attr} metadata")
            if len(children) == 1:
                raise EmbeddedFontRefusal("embedded font family has no asset")
            seen_styles: set[str] = set()
            previous_style = -1
            for variant in children[1:]:
                style = next((name for name in _STYLES if variant.tag == f"{{{pns}}}{name}"), None)
                if style is None or style in seen_styles:
                    raise EmbeddedFontRefusal("unsupported or duplicate embedded font style")
                position = tuple(_STYLES).index(style)
                if position < previous_style:
                    raise EmbeddedFontRefusal("embedded font styles are out of schema order")
                previous_style = position
                seen_styles.add(style)
                _attributes(variant, {f"{{{rns}}}id"}, "embedded font style")
                _plain(variant, "embedded font style")
                rid = variant.get(f"{{{rns}}}id", "")
                if not rid or rid in used_ids or rid not in relationships:
                    raise EmbeddedFontRefusal("dangling or shared embedded font relationship")
                used_ids.add(rid)
                relationship = relationships[rid]
                _attributes(
                    relationship, {"Id", "Type", "Target", "TargetMode"}, "font relationship"
                )
                _plain(relationship, "font relationship")
                if relationship.tail and relationship.tail.strip():
                    raise EmbeddedFontRefusal("unsupported font relationship tail text")
                if relationship.get("Type") != f"{rns}/font":
                    raise EmbeddedFontRefusal("embedded font uses a non-font relationship")
                if relationship.get("TargetMode", "Internal") != "Internal":
                    raise EmbeddedFontRefusal("external embedded fonts are unsupported")
                font_part = _target(part, relationship.get("Target", ""))
                if (
                    not font_part.startswith("ppt/fonts/")
                    or posixpath.dirname(font_part) != "ppt/fonts"
                    or not font_part.endswith(".fntdata")
                ):
                    raise EmbeddedFontRefusal("unsupported embedded font part model")
                if font_part not in names:
                    raise EmbeddedFontRefusal("dangling embedded font part")
                if _content_type(types, font_part) != _FONT_CONTENT_TYPE:
                    raise EmbeddedFontRefusal("unsupported embedded font content type")
                bold, italic = _STYLES[style]
                entries.append(
                    _Entry(
                        EmbeddedFont(family, bold, italic, font_part, package.read(font_part)),
                        owner,
                        variant,
                        relationship,
                    )
                )
    for rid, relationship in relationships.items():
        if (
            relationship.get("Type") in {f"{R_NS}/font", f"{STRICT_R_NS}/font"}
            and rid not in used_ids
        ):
            raise EmbeddedFontRefusal("unmanaged font relationship is unsupported")
    return _Model(part, root, rels_part, rels, types, fonts, entries, names)


def _admit(family: str, bold: bool, italic: bool, payload: bytes, path: Path) -> FontAsset:
    # fsType is in the OS/2 table at offset eight. No subsetting is performed,
    # so the no-subsetting bit is compatible with these exact full-file assets.
    if payload[:4] not in {b"\x00\x01\x00\x00", b"true"}:
        raise EmbeddedFontRefusal("only single-face TrueType sfnt fonts are supported")
    if len(payload) < 12:
        raise EmbeddedFontRefusal("truncated TrueType header")
    count = struct.unpack_from(">H", payload, 4)[0]
    directory_end = 12 + count * 16
    if not count or directory_end > len(payload):
        raise EmbeddedFontRefusal("truncated TrueType table directory")
    tables: dict[bytes, tuple[int, int]] = {}
    spans: list[tuple[int, int]] = []
    for index in range(count):
        record = 12 + index * 16
        tag = payload[record : record + 4]
        offset, length = struct.unpack_from(">II", payload, record + 8)
        if tag in tables or offset < directory_end or offset + length > len(payload):
            raise EmbeddedFontRefusal("invalid TrueType table directory")
        tables[tag] = (offset, length)
        if length:
            spans.append((offset, offset + length))
    spans.sort()
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:], strict=False)):
        raise EmbeddedFontRefusal("overlapping TrueType tables")
    if b"glyf" not in tables or b"loca" not in tables or b"CFF " in tables or b"CFF2" in tables:
        raise EmbeddedFontRefusal("font must contain TrueType outlines")
    os2 = tables.get(b"OS/2")
    if os2 is None or os2[1] < 10:
        raise EmbeddedFontRefusal("font has no readable OS/2 embedding permissions")
    fs_type = struct.unpack_from(">H", payload, os2[0] + 8)[0]
    if fs_type & 0x0002:
        raise EmbeddedFontRefusal("font prohibits embedding (restricted fsType)")
    if fs_type & 0x0200:
        raise EmbeddedFontRefusal("font allows bitmap-only embedding")
    if fs_type & ~0x030E:
        raise EmbeddedFontRefusal("unsupported font embedding permission bits")
    asset = admit_font_bytes(family, bold, italic, payload, path=path)
    if not asset.has_true_type_outlines:
        raise EmbeddedFontRefusal("font must contain TrueType outlines")
    return asset


def _entry(model: _Model, family: str, bold: bool, italic: bool) -> _Entry | None:
    return next(
        (
            entry
            for entry in model.entries
            if (entry.asset.family.casefold(), entry.asset.bold, entry.asset.italic)
            == (family.casefold(), bold, italic)
        ),
        None,
    )


def _exclusive(package: Any, model: _Model, entry: _Entry) -> None:
    part, rid = entry.asset.partname, entry.relationship.get("Id")
    if rels_part_for_package_part(part) in model.names:
        raise EmbeddedFontRefusal("font part has unsupported relationships")
    if sum(item.asset.partname == part for item in model.entries) != 1:
        raise EmbeddedFontRefusal("font part is shared by embedded variants")
    for element in model.root.iter():
        if element is entry.variant:
            continue
        if rid in element.attrib.values():
            raise EmbeddedFontRefusal("font relationship is shared by presentation metadata")
    references = 0
    for name in sorted(model.names):
        if not name.endswith(".rels"):
            continue
        if name == "_rels/.rels":
            source = ""
        else:
            directory, basename = posixpath.split(name)
            if posixpath.basename(directory) != "_rels":
                raise EmbeddedFontRefusal("unsupported relationship part location")
            source = posixpath.join(posixpath.dirname(directory), basename[:-5])
        rels = model.rels if name == model.rels_part else _relationships(package, name)
        for relationship in rels:
            if not isinstance(relationship.tag, str):
                continue
            if relationship.get("TargetMode", "Internal") not in {"Internal", "External"}:
                raise EmbeddedFontRefusal("unsupported relationship target mode")
            if relationship.get("TargetMode", "Internal") == "External":
                continue
            target = urlsplit(relationship.get("Target", ""))
            resolved = resolve_package_target(source, unquote(target.path))
            if not target.scheme and not target.netloc and resolved == part:
                references += 1
                if name != model.rels_part or relationship.get("Id") != rid:
                    raise EmbeddedFontRefusal("font part is shared by package relationships")
    if references != 1:
        raise EmbeddedFontRefusal("font part ownership is ambiguous")


def _fresh_part(model: _Model) -> str:
    occupied = model.names | {node.get("PartName", "").lstrip("/") for node in model.types}
    number = 1
    while True:
        part = f"ppt/fonts/font{number}.fntdata"
        if part not in occupied and rels_part_for_package_part(part) not in occupied:
            return part
        number += 1


def _fresh_id(model: _Model) -> str:
    occupied = {node.get("Id") for node in model.rels}
    occupied.update(value for element in model.root.iter() for value in element.attrib.values())
    number = 1
    while f"rIdFont{number}" in occupied:
        number += 1
    return f"rIdFont{number}"


def _insert_list(model: _Model) -> ET.Element:
    pns = ooxml_namespace(model.root, P_NS)
    fonts = ET.Element(f"{{{pns}}}embeddedFontLst")
    # CT_Presentation order places embeddedFontLst after notesSz/smartTags and
    # before custShowLst, photoAlbum, custDataLst, kinsoku, defaultTextStyle, extLst.
    following = {
        f"{{{pns}}}{name}"
        for name in (
            "custShowLst",
            "photoAlbum",
            "custDataLst",
            "kinsoku",
            "defaultTextStyle",
            "extLst",
        )
    }
    index = next(
        (index for index, node in enumerate(model.root) if node.tag in following), len(model.root)
    )
    model.root.insert(index, fonts)
    return fonts


class FontManager:
    """Manage saved-package embedded fonts by case-insensitive family and style.

    Only explicit, identity/style-matching single-face TrueType assets with
    compatible OS/2 embedding permissions are admitted. Obfuscated fonts,
    collections, external references and unsupported embedded-font metadata are
    refused, never flattened. Mutations are transactional and do not edit text
    font selections. Shared parts cannot be replaced or removed.
    """

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation

    def _require_saved(self, operation: str) -> None:
        prs = self._presentation
        prs._require_saved_package(operation)
        if prs._theme_edits is not None and prs._theme_edits.dirty:
            raise EmbeddedFontRefusal(f"save pending theme edits before {operation}")

    def list(self) -> tuple[EmbeddedFont, ...]:
        """Read embedded assets in presentation family/style order, with exact bytes.

        Save pending edits first. Unsupported or dangling package font metadata
        raises EmbeddedFontRefusal; reading does not rewrite the package.
        """
        prs = self._presentation
        with prs._mutation_lock:
            try:
                self._require_saved("listing embedded fonts")
                with open_package_source(prs._source_path) as package:
                    return tuple(entry.asset for entry in _model(package).entries)
            except _ERRORS as exc:
                if isinstance(exc, EmbeddedFontRefusal):
                    raise
                raise EmbeddedFontRefusal(str(exc)) from exc

    def registry(self) -> FontRegistry:
        """Admit every embedded asset for rendering from its owned byte snapshot.

        Pass this registry to Wolf rendering. No operating-system fonts are
        discovered; invalid identity/style, outlines or permissions are refused.
        """
        try:
            return FontRegistry(
                _admit(font.family, font.bold, font.italic, font.payload, Path(font.partname))
                for font in self.list()
            )
        except _ERRORS as exc:
            if isinstance(exc, EmbeddedFontRefusal):
                raise
            raise EmbeddedFontRefusal(str(exc)) from exc

    def _rewrite(self, operation: str, plan: Any) -> Any:
        prs = self._presentation
        with prs._mutation_lock:
            try:
                self._require_saved(operation)
                prs._validate_required_namespaces()
                return prs._rewrite_package(operation, plan)
            except _ERRORS as exc:
                if isinstance(exc, EmbeddedFontRefusal):
                    raise
                raise EmbeddedFontRefusal(str(exc)) from exc

    def _input(self, family: str, path: Any, bold: bool, italic: bool) -> bytes:
        _family(family, bold, italic)
        try:
            source = Path(path).expanduser()
            payload = source.read_bytes()
            _admit(family, bold, italic, payload, source)
            return payload
        except _ERRORS as exc:
            if isinstance(exc, EmbeddedFontRefusal):
                raise
            raise EmbeddedFontRefusal(str(exc)) from exc

    def add(
        self, family: str, path: Any, *, bold: bool = False, italic: bool = False
    ) -> EmbeddedFont:
        """Embed a new family/style from a local TrueType file and return its bytes.

        The family/style must not already exist. Identity, outline format and
        embedding permissions are checked before any package rewrite.
        """
        payload = self._input(family, path, bold, italic)

        def plan(package: Any) -> Any:
            model = _model(package)
            if _entry(model, family, bold, italic) is not None:
                raise EmbeddedFontRefusal("embedded font family/style already exists; use replace")
            pns, rns = ooxml_namespace(model.root, P_NS), ooxml_namespace(model.root, R_NS)
            fonts = model.fonts if model.fonts is not None else _insert_list(model)
            owner = next(
                (
                    entry.owner
                    for entry in model.entries
                    if entry.asset.family.casefold() == family.casefold()
                ),
                None,
            )
            stored_family = family
            if owner is None:
                owner = ET.SubElement(fonts, f"{{{pns}}}embeddedFont")
                ET.SubElement(owner, f"{{{pns}}}font", {"typeface": family})
            else:
                stored_family = owner[0].get("typeface", family)
            part, rid = _fresh_part(model), _fresh_id(model)
            style = next(name for name, flags in _STYLES.items() if flags == (bold, italic))
            variant = ET.Element(f"{{{pns}}}{style}", {f"{{{rns}}}id": rid})
            rank = tuple(_STYLES).index(style)
            index = next(
                (
                    index
                    for index, node in enumerate(owner)
                    if node.tag in {f"{{{pns}}}{name}" for name in tuple(_STYLES)[rank + 1 :]}
                ),
                len(owner),
            )
            owner.insert(index, variant)
            ET.SubElement(
                model.rels,
                f"{{{PKG_REL_NS}}}Relationship",
                {
                    "Id": rid,
                    "Type": f"{rns}/font",
                    "Target": posixpath.relpath(part, posixpath.dirname(model.part)),
                },
            )
            ET.SubElement(
                model.types,
                f"{{{CONTENT_TYPES_NS}}}Override",
                {
                    "PartName": "/" + part,
                    "ContentType": _FONT_CONTENT_TYPE,
                },
            )
            model.root.set("embedTrueTypeFonts", "1")
            return (
                {
                    model.part: serialize_xml(model.root),
                    model.rels_part: serialize_xml(model.rels),
                    "[Content_Types].xml": serialize_xml(model.types),
                    part: payload,
                },
                set(),
                EmbeddedFont(stored_family, bold, italic, part, payload),
            )

        return self._rewrite("adding an embedded font", plan)

    def replace(
        self, family: str, path: Any, *, bold: bool = False, italic: bool = False
    ) -> EmbeddedFont:
        """Replace an existing, exclusively owned family/style with admitted bytes.

        Other variants are unchanged. A missing variant or shared part is a
        refusal, not an add or a presentation-wide shared-asset replacement.
        """
        payload = self._input(family, path, bold, italic)

        def plan(package: Any) -> Any:
            model = _model(package)
            entry = _entry(model, family, bold, italic)
            if entry is None:
                raise EmbeddedFontRefusal("embedded font family/style does not exist")
            _exclusive(package, model, entry)
            replacements = {entry.asset.partname: payload}
            if model.root.get("embedTrueTypeFonts") not in {"1", "true"}:
                model.root.set("embedTrueTypeFonts", "1")
                replacements[model.part] = serialize_xml(model.root)
            return (
                replacements,
                set(),
                EmbeddedFont(entry.asset.family, bold, italic, entry.asset.partname, payload),
            )

        return self._rewrite("replacing an embedded font", plan)

    def remove(self, family: str, *, bold: bool = False, italic: bool = False) -> None:
        """Remove an exclusively owned family/style and its font part.

        The embedding flag is cleared only after the final embedded variant is
        removed. Other variants and their metadata remain intact.
        """
        _family(family, bold, italic)

        def plan(package: Any) -> Any:
            model = _model(package)
            entry = _entry(model, family, bold, italic)
            if entry is None:
                raise EmbeddedFontRefusal("embedded font family/style does not exist")
            _exclusive(package, model, entry)
            assert model.fonts is not None
            entry.owner.remove(entry.variant)
            if len(entry.owner) == 1:
                model.fonts.remove(entry.owner)
            if len(model.fonts) == 0:
                model.root.remove(model.fonts)
                model.root.set("embedTrueTypeFonts", "0")
            model.rels.remove(entry.relationship)
            types_changed = False
            for node in list(model.types):
                if (
                    node.tag == f"{{{CONTENT_TYPES_NS}}}Override"
                    and node.get("PartName") == "/" + entry.asset.partname
                ):
                    _attributes(node, {"PartName", "ContentType"}, "font content type")
                    _plain(node, "font content type")
                    if node.tail and node.tail.strip():
                        raise EmbeddedFontRefusal("unsupported font content type tail text")
                    model.types.remove(node)
                    types_changed = True
            replacements = {
                model.part: serialize_xml(model.root),
                model.rels_part: serialize_xml(model.rels),
            }
            if types_changed:
                replacements["[Content_Types].xml"] = serialize_xml(model.types)
            return replacements, {entry.asset.partname}, None

        self._rewrite("removing an embedded font", plan)
