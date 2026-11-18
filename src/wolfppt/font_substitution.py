"""Deck-persisted, explicit font substitutions for the built-in renderer.

Rules do not edit text or admit fonts. They select a real, already admitted
asset, preserving the requested bold/italic style without synthetic variants.
"""

from __future__ import annotations

import posixpath
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from .font_assets import FontAsset, FontRefusal, FontRegistry, UnadmittedFontRefusal
from .package_parts import (
    CONTENT_TYPES_NS,
    P_NS,
    PKG_REL_NS,
    R_NS,
    _next_relationship_id,
    open_package_source,
    rels_part_for_package_part,
    resolve_package_target,
)
from .presentation_tags import LifecycleRefusal, parse_xml, serialize_xml, xml_string
from .slide_metadata import presentation_partname
from .xml_helpers import STRICT_R_NS, ooxml_namespace

__all__ = ["FontSubstitutionRefusal", "FontSubstitutionRule", "FontSubstitutions"]

_NAMESPACE = "urn:wolfppt:font-substitutions"
_PART = "customXml/wolfppt-font-substitutions.xml"
_CUSTOM_XML_TYPES = (R_NS + "/customXml", STRICT_R_NS + "/customXml")


class FontSubstitutionRefusal(FontRefusal):
    """Invalid rules, unsafe storage/lifecycle, or an unadmitted target style."""


@dataclass(frozen=True)
class FontSubstitutionRule:
    """One ordered family rule with optional exact style constraints.

    Family matching is case-insensitive, as in :class:`FontRegistry`. ``None``
    matches either value of that style flag. ``missing`` applies only when the
    original family and requested style are not admitted; ``always`` also
    overrides admitted originals. The first applicable rule wins, and its
    replacement is resolved once, never through another substitution rule.
    """

    source: str
    replacement: str
    condition: str = "missing"
    bold: bool | None = None
    italic: bool | None = None

    def __post_init__(self) -> None:
        for field in ("source", "replacement"):
            try:
                value = xml_string(getattr(self, field), field)
            except (TypeError, LifecycleRefusal) as exc:
                raise FontSubstitutionRefusal(str(exc)) from exc
            if not value.strip():
                raise FontSubstitutionRefusal(f"{field} family must not be blank")
        if not isinstance(self.condition, str) or self.condition not in ("missing", "always"):
            raise FontSubstitutionRefusal("condition must be exactly 'missing' or 'always'")
        for field in ("bold", "italic"):
            value = getattr(self, field)
            if value is not None and type(value) is not bool:
                raise FontSubstitutionRefusal(f"{field} must be bool or None")


def _validated_rules(values: Iterable[FontSubstitutionRule]) -> tuple[FontSubstitutionRule, ...]:
    try:
        rules = tuple(values)
    except (TypeError, ValueError) as exc:
        raise FontSubstitutionRefusal("rules must be an iterable of FontSubstitutionRule") from exc
    identities = set()
    for rule in rules:
        if not isinstance(rule, FontSubstitutionRule):
            raise FontSubstitutionRefusal("rules must contain only FontSubstitutionRule values")
        rule.__post_init__()
        identity = (
            rule.source.casefold(),
            rule.replacement.casefold(),
            rule.condition,
            rule.bold,
            rule.italic,
        )
        if identity in identities:
            raise FontSubstitutionRefusal("duplicate font substitution rule")
        identities.add(identity)
    return rules


def _attributes(element: ET.Element) -> dict[str, str]:
    return {
        key: value
        for key, value in element.attrib.items()
        if key != "xmlns" and not key.startswith("xmlns:")
    }


def _read_rules(root: ET.Element) -> tuple[FontSubstitutionRule, ...]:
    if root.tag != f"{{{_NAMESPACE}}}fontSubstitutions":
        raise FontSubstitutionRefusal("unsupported font substitution namespace or root")
    if _attributes(root) != {"version": "1"}:
        raise FontSubstitutionRefusal("unsupported font substitution version or attributes")
    if (root.text or "").strip():
        raise FontSubstitutionRefusal("font substitution storage contains unexpected text")
    rules = []
    for child in root:
        if (child.tail or "").strip():
            raise FontSubstitutionRefusal("font substitution storage contains unexpected text")
        if not isinstance(child.tag, str):
            continue
        if child.tag != f"{{{_NAMESPACE}}}rule" or len(child):
            raise FontSubstitutionRefusal("unsupported font substitution extension element")
        if (child.text or "").strip() or (child.tail or "").strip():
            raise FontSubstitutionRefusal("font substitution rule contains unexpected text")
        attributes = _attributes(child)
        if not {"source", "replacement", "condition"} <= attributes.keys():
            raise FontSubstitutionRefusal("font substitution rule is missing required attributes")
        if attributes.keys() - {"source", "replacement", "condition", "bold", "italic"}:
            raise FontSubstitutionRefusal("unsupported font substitution rule attributes")
        flags: dict[str, bool | None] = {}
        for field in ("bold", "italic"):
            value = attributes.get(field)
            if value not in (None, "true", "false"):
                raise FontSubstitutionRefusal(f"stored {field} must be 'true' or 'false'")
            flags[field] = None if value is None else value == "true"
        rules.append(
            FontSubstitutionRule(
                attributes["source"],
                attributes["replacement"],
                attributes["condition"],
                flags["bold"],
                flags["italic"],
            )
        )
    return _validated_rules(rules)


def _rules_xml(rules: tuple[FontSubstitutionRule, ...]) -> bytes:
    root = ET.Element(f"{{{_NAMESPACE}}}fontSubstitutions", {"version": "1"})
    for rule in rules:
        attributes = {
            "source": rule.source,
            "replacement": rule.replacement,
            "condition": rule.condition,
        }
        for field in ("bold", "italic"):
            value = getattr(rule, field)
            if value is not None:
                attributes[field] = "true" if value else "false"
        ET.SubElement(root, f"{{{_NAMESPACE}}}rule", attributes)
    return serialize_xml(root)


def _xml(package: Any, part: str) -> ET.Element:
    try:
        return parse_xml(package.read(part), read_only=True)
    except (KeyError, ET.ParseError, LifecycleRefusal, ValueError) as exc:
        raise FontSubstitutionRefusal(
            f"invalid or missing font substitution package XML: {part}"
        ) from exc


def _target(source: str, relationship: ET.Element) -> str:
    target = relationship.get("Target", "")
    if not target or any(character in target for character in ("\\", "?", "#", ":", "%")):
        raise FontSubstitutionRefusal("unsupported font substitution relationship target")
    part = resolve_package_target(source, target)
    if part in ("", ".", "..") or part.startswith("../"):
        raise FontSubstitutionRefusal("font substitution relationship escapes the package")
    return part


def _foreign_target(source: str, relationship: ET.Element) -> str:
    # Only compare foreign targets; do not impose our storage grammar on
    # unrelated image, media, or extension relationships.
    target = relationship.get("Target", "").split("#", 1)[0].split("?", 1)[0]
    return posixpath.normpath(resolve_package_target(source, unquote(target).replace("\\", "/")))


class _Storage:
    """One validated package snapshot; only its owned members may be changed."""

    def __init__(self, package: Any, presentation_part: str) -> None:
        self.package = package
        self.presentation_part = presentation_part
        names = package.namelist()
        if len(names) != len(set(names)):
            raise FontSubstitutionRefusal(
                "duplicate package members make substitution storage ambiguous"
            )
        self.names = set(names)
        collisions = [name for name in names if name.casefold() == _PART.casefold()]
        if collisions and collisions != [_PART]:
            raise FontSubstitutionRefusal("font substitution part name collision")
        presentation = _xml(package, presentation_part)
        if presentation.tag not in (
            f"{{{P_NS}}}presentation",
            "{http://purl.oclc.org/ooxml/presentationml/main}presentation",
        ):
            raise FontSubstitutionRefusal("font substitutions require a presentation package")
        self.relationship_type = ooxml_namespace(presentation, R_NS) + "/customXml"
        self.rels_part = rels_part_for_package_part(presentation_part)
        self.rels = (
            _xml(package, self.rels_part)
            if self.rels_part in self.names
            else ET.Element(f"{{{PKG_REL_NS}}}Relationships")
        )
        if self.rels.tag != f"{{{PKG_REL_NS}}}Relationships":
            raise FontSubstitutionRefusal("invalid presentation relationship root")
        ids = [rel.get("Id") for rel in self.rels if rel.tag == f"{{{PKG_REL_NS}}}Relationship"]
        if any(not value for value in ids) or len(ids) != len(set(ids)):
            raise FontSubstitutionRefusal("missing or duplicate presentation relationship identity")
        self.relationship: ET.Element | None = None
        self.rules: tuple[FontSubstitutionRule, ...] = ()
        for rel in self.rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
            if rel.get("Type") not in _CUSTOM_XML_TYPES:
                continue
            if rel.get("TargetMode", "Internal") != "Internal":
                if "wolfppt-font-substitutions" in rel.get("Target", "").casefold():
                    raise FontSubstitutionRefusal(
                        "external font substitution storage is unsupported"
                    )
                continue
            part = _foreign_target(presentation_part, rel)
            root = _xml(package, part)
            tag = root.tag if isinstance(root.tag, str) else ""
            owned = tag.startswith("{" + _NAMESPACE)
            if part.casefold() == _PART.casefold() and not owned:
                raise FontSubstitutionRefusal(
                    "foreign custom XML collides with substitution storage"
                )
            if not owned:
                continue
            if _target(presentation_part, rel) != part:
                raise FontSubstitutionRefusal("unsupported font substitution relationship target")
            if self.relationship is not None:
                raise FontSubstitutionRefusal("duplicate font substitution relationships or parts")
            if part != _PART:
                raise FontSubstitutionRefusal("unsupported font substitution storage location")
            self.rules = _read_rules(root)
            self.relationship = rel
        self.types = _xml(package, "[Content_Types].xml")
        if self.types.tag != f"{{{CONTENT_TYPES_NS}}}Types":
            raise FontSubstitutionRefusal("invalid package content-types root")
        overrides = [
            element
            for element in self.types.findall(f"{{{CONTENT_TYPES_NS}}}Override")
            if element.get("PartName", "").casefold() == "/" + _PART.casefold()
        ]
        if len(overrides) > 1:
            raise FontSubstitutionRefusal("duplicate substitution content-type overrides")
        self.override = overrides[0] if overrides else None
        if self.override is not None and (
            self.override.get("PartName") != "/" + _PART
            or self.override.get("ContentType") != "application/xml"
        ):
            raise FontSubstitutionRefusal("font substitution content-type collision")
        if self.relationship is not None and self.override is None:
            raise FontSubstitutionRefusal(
                "substitution storage requires an application/xml override"
            )
        self.detached_shared = self.relationship is None and _PART in self.names and self.shared()
        if self.relationship is None and (_PART in self.names or self.override is not None):
            if not self.detached_shared or self.override is None:
                raise FontSubstitutionRefusal(
                    "unrelated or orphaned substitution storage collision"
                )
            # A detached, foreign-referenced owned part is not an orphan. Its
            # rules no longer belong to this presentation, but its format must
            # still be recognized before any attempt to reuse its name.
            _read_rules(_xml(package, _PART))
        if rels_part_for_package_part(_PART) in self.names:
            raise FontSubstitutionRefusal(
                "substitution storage has unsupported outgoing relationships"
            )
        self.referenced_id = self.relationship is not None and any(
            element.get(f"{{{namespace}}}id") == self.relationship.get("Id")
            for element in presentation.iter()
            for namespace in (R_NS, STRICT_R_NS)
        )

    def shared(self) -> bool:
        for name in sorted(self.names):
            if not name.endswith(".rels"):
                continue
            directory, basename = posixpath.split(name)
            source = (
                ""
                if name == "_rels/.rels"
                else posixpath.join(posixpath.dirname(directory), basename[:-5])
            )
            if name != "_rels/.rels" and rels_part_for_package_part(source) != name:
                raise FontSubstitutionRefusal("unsupported package relationship part location")
            root = self.rels if name == self.rels_part else _xml(self.package, name)
            if root.tag != f"{{{PKG_REL_NS}}}Relationships":
                raise FontSubstitutionRefusal("invalid package relationship root")
            for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
                if rel is self.relationship or rel.get("TargetMode", "Internal") == "External":
                    continue
                if _foreign_target(source, rel).casefold() == _PART.casefold():
                    if rel.get("TargetMode", "Internal") != "Internal":
                        raise FontSubstitutionRefusal("invalid foreign substitution reference mode")
                    return True
        return False

    def plan(
        self, rules: tuple[FontSubstitutionRule, ...]
    ) -> tuple[dict[str, bytes], set[str], None]:
        replacements: dict[str, bytes] = {}
        removals: set[str] = set()
        if self.rules == rules and (rules or self.relationship is None):
            return replacements, removals, None
        if self.referenced_id:
            raise FontSubstitutionRefusal(
                "substitution relationship is referenced by foreign presentation data"
            )
        shared = self.shared()
        if rules:
            if self.detached_shared:
                raise FontSubstitutionRefusal(
                    "foreign references retain detached substitution storage"
                )
            if shared:
                raise FontSubstitutionRefusal(
                    "cannot replace substitution storage shared by foreign relationships"
                )
            replacements[_PART] = _rules_xml(rules)
            if self.relationship is None:
                ids = {rel.get("Id", "") for rel in self.rels}
                ET.SubElement(
                    self.rels,
                    f"{{{PKG_REL_NS}}}Relationship",
                    {
                        "Id": _next_relationship_id(ids),
                        "Type": self.relationship_type,
                        "Target": posixpath.relpath(
                            _PART, posixpath.dirname(self.presentation_part)
                        ),
                    },
                )
                replacements[self.rels_part] = serialize_xml(self.rels)
                ET.SubElement(
                    self.types,
                    f"{{{CONTENT_TYPES_NS}}}Override",
                    {
                        "PartName": "/" + _PART,
                        "ContentType": "application/xml",
                    },
                )
                replacements["[Content_Types].xml"] = serialize_xml(self.types)
        elif self.relationship is not None:
            self.rels.remove(self.relationship)
            replacements[self.rels_part] = serialize_xml(self.rels)
            if not shared:
                removals.add(_PART)
                self.types.remove(self.override)
                replacements["[Content_Types].xml"] = serialize_xml(self.types)
        return replacements, removals, None


class _SubstitutionRegistry(FontRegistry):
    def __init__(self, fonts: FontRegistry, rules: tuple[FontSubstitutionRule, ...]) -> None:
        # Copy admitted assets, not another registry's resolve policy. A target
        # must be admitted directly; even wrapping a wrapper cannot chain rules.
        super().__init__(fonts)
        self._rules = rules

    def resolve(self, family: str, bold: bool, italic: bool) -> FontAsset:
        family_key = family.casefold()
        original = self._assets.get((family_key, bold, italic))
        for rule in self._rules:
            if rule.source.casefold() != family_key:
                continue
            if rule.bold is not None and rule.bold != bold:
                continue
            if rule.italic is not None and rule.italic != italic:
                continue
            if rule.condition == "missing" and original is not None:
                continue
            try:
                return super().resolve(rule.replacement, bold, italic)
            except UnadmittedFontRefusal as exc:
                raise FontSubstitutionRefusal(
                    f"substitution for {family!r} requires admitted replacement "
                    f"{rule.replacement!r} with bold={bold}, italic={italic}"
                ) from exc
        return super().resolve(family, bold, italic)


class FontSubstitutions:
    """Manage saved-deck rules and make a render-wide registry snapshot.

    Save pending facade edits before using this manager. ``set_rules`` stages
    package changes transactionally; a refusal leaves the source deck intact.
    Save the presentation to a deck path and reopen it to retain the rules.
    Construction, reading, and creating a registry never change the package.

    Admit explicit local or embedded assets into ``fonts``, then use
    ``registry = manager.registry(fonts)`` and ``resolve_deck(path, registry)``.
    Pass that same registry to ``render_slide_png`` and ``render_deck_pdf`` so
    measurement, rasterization, and PDF embedding use the same real bytes.
    Rendering does not rewrite the deck's requested font families. Replacement
    styles are checked on resolution; unused rules do not require font assets.
    No operating-system discovery, synthesis, or recursive fallback is used.
    """

    def __init__(self, presentation: Any) -> None:
        from .presentation import Presentation

        if not isinstance(presentation, Presentation):
            raise FontSubstitutionRefusal("font substitutions require a Presentation")
        self._presentation = presentation
        _ = self.rules

    def _require_saved(self) -> None:
        try:
            self._presentation._require_saved_package("managing font substitutions")
            theme_edits = self._presentation._theme_edits
            if theme_edits is not None and theme_edits.dirty:
                raise ValueError("save pending theme edits before managing font substitutions")
        except (ValueError, RuntimeError) as exc:
            raise FontSubstitutionRefusal(str(exc)) from exc

    def _storage(self, package: Any) -> _Storage:
        return _Storage(package, presentation_partname(self._presentation._source_path))

    @property
    def rules(self) -> tuple[FontSubstitutionRule, ...]:
        """Return ordered immutable rules from the current saved package."""
        with self._presentation._mutation_lock:
            self._require_saved()
            try:
                with open_package_source(self._presentation._source_path) as package:
                    return self._storage(package).rules
            except (OSError, zipfile.BadZipFile, LifecycleRefusal, ET.ParseError) as exc:
                raise FontSubstitutionRefusal(
                    f"cannot read font substitution storage: {exc}"
                ) from exc

    def set_rules(self, rules: Iterable[FontSubstitutionRule]) -> None:
        """Persist ordered rules atomically; empty rules detach only owned data.

        A part still referenced by foreign relationships and its content-type
        override are retained when detaching. Shared data cannot be overwritten.
        Caller-supplied rules are validated before any package rewrite begins.
        """
        admitted_rules = _validated_rules(rules)
        with self._presentation._mutation_lock:
            self._require_saved()
            try:
                with open_package_source(self._presentation._source_path) as package:
                    storage = self._storage(package)
                    if storage.rules == admitted_rules and (
                        admitted_rules or storage.relationship is None
                    ):
                        return
                try:
                    self._presentation._validate_required_namespaces()
                except (ValueError, RuntimeError) as exc:
                    raise FontSubstitutionRefusal(str(exc)) from exc
                self._presentation._rewrite_package(
                    "saving font substitutions",
                    lambda package: self._storage(package).plan(admitted_rules),
                )
            except (OSError, zipfile.BadZipFile, LifecycleRefusal, ET.ParseError) as exc:
                raise FontSubstitutionRefusal(
                    f"cannot save font substitution storage: {exc}"
                ) from exc

    def registry(self, fonts: FontRegistry) -> FontRegistry:
        """Wrap admitted assets with the current rules, without changing a deck.

        Recreate this snapshot after changing rules. First match wins even if
        its replacement is unadmitted, which raises FontSubstitutionRefusal;
        an unmatched missing original retains UnadmittedFontRefusal behavior.
        """
        if not isinstance(fonts, FontRegistry):
            raise FontSubstitutionRefusal("substitutions require an admitted FontRegistry")
        return _SubstitutionRegistry(fonts, self.rules)
