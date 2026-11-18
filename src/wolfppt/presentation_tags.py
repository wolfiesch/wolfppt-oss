"""Owner-bound string tags and lifecycle staging primitives.

Tag keys are exact, case-sensitive strings, in package/insertion order. No
application-specific case folding or duplicate precedence is inferred.
"""

from __future__ import annotations

import io
import posixpath
import re
from collections.abc import Callable, Iterator, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    CONTENT_TYPES_NS,
    P_NS,
    PKG_REL_NS,
    R_NS,
    open_package_source,
    rels_part_for_package_part,
    resolve_package_target,
)
from .slide_metadata import presentation_partname
from .xml_helpers import (
    STRICT_R_NS,
    find_ooxml,
    findall_ooxml,
    ooxml_namespace,
    ooxml_path,
)

TAG_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.tags+xml"
)


class LifecycleRefusal(ValueError):
    """A lifecycle operation cannot identify or preserve its target safely."""


def xml_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if any(
        not (
            c in "\t\n\r"
            or 0x20 <= ord(c) <= 0xD7FF
            or 0xE000 <= ord(c) <= 0xFFFD
            or 0x10000 <= ord(c) <= 0x10FFFF
        )
        for c in value
    ):
        raise LifecycleRefusal(f"{name} contains invalid XML characters")
    return value


def parse_xml(payload: bytes, *, read_only: bool = False) -> ET.Element:
    """Retain comments, PIs and namespace bindings used in extension values.

    ElementTree does not retain unused namespace declarations. Keep those on
    the declaring element too; serialize_xml avoids duplicate root bindings.

    Inspection permits scoped rebinding: expanded names retain their namespace
    meaning and opaque lexical values keep their declaring-element bindings.
    Mutation parsing remains conservative because serialization cannot preserve
    conflicting bindings. Never share inspection roots with mutation staging.
    """
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    pending: list[tuple[str, str]] = []
    root = None
    bindings: dict[str, str] = {}
    for event, value in ET.iterparse(
        io.BytesIO(payload), events=("start-ns", "start"), parser=parser
    ):
        if event == "start-ns":
            pending.append(value)
        else:
            if root is None:
                root = value
            for prefix, uri in pending:
                if not read_only:
                    if prefix in bindings and bindings[prefix] != uri:
                        raise LifecycleRefusal(
                            "namespace prefix rebinding is unsupported for lifecycle mutation"
                        )
                    bindings[prefix] = uri
                value.set("xmlns" + (":" + prefix if prefix else ""), uri)
            pending.clear()
    if root is None:
        raise LifecycleRefusal("empty lifecycle XML")
    return root


def serialize_xml(root: ET.Element) -> bytes:
    # Validate every retained declaration before changing the tree or the
    # process-global namespace registry, including inspection-only trees.
    bindings: dict[str, str] = {}
    declarations = []
    for element in root.iter():
        for name, uri in element.attrib.items():
            if name == "xmlns" or name.startswith("xmlns:"):
                if name in bindings and bindings[name] != uri:
                    raise LifecycleRefusal(
                        "namespace prefix rebinding is unsupported for lifecycle mutation"
                    )
                bindings[name] = uri
                declarations.append((element, name, uri))
    # Reuse the package's ElementTree serialization convention only once the
    # retained bindings are safe for its document-wide prefix registration.
    # The registration is scoped to this call: document prefixes (for example
    # Strict p:/a:) must not evict the process-wide Transitional mappings.
    registry = dict(ET._namespace_map)
    for element, name, uri in declarations:
        prefix = name.partition(":")[2]
        if not re.fullmatch(r"ns\d+", prefix):
            ET.register_namespace(prefix, uri)
        del element.attrib[name]
    try:
        first = ET.tostring(root, encoding="utf-8")
        header = first.split(b">", 1)[0]
        for element, name, uri in declarations:
            token = (name + '="').encode()
            if token not in header:
                element.set(name, uri)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    finally:
        ET._namespace_map.clear()
        ET._namespace_map.update(registry)
        for element, name, uri in declarations:
            element.set(name, uri)


def one(parent: ET.Element, tag: str) -> ET.Element | None:
    found = findall_ooxml(parent, tag)
    if len(found) > 1:
        raise LifecycleRefusal(f"ambiguous lifecycle element {tag}")
    return found[0] if found else None


def _shape_members(shapes: Any) -> Iterator[Any]:
    for shape in shapes:
        yield shape
        if getattr(shape, "_payload", {}).get("kind") == "group":
            yield from _shape_members(shape.shapes)


@dataclass(frozen=True)
class OwnerRef:
    presentation: Any
    owner: Any
    part_owner: Any
    shape_id: str | None
    creation_token: Any = None

    @classmethod
    def capture(cls, presentation: Any, owner: Any) -> OwnerRef:
        from .presentation_slides import NotesSlide, Slide
        from .shape_core_facade import Shape

        if owner is presentation:
            ref = cls(presentation, owner, owner, None)
        elif isinstance(owner, (Slide, NotesSlide)):
            ref = cls(
                presentation,
                owner,
                owner,
                None,
                getattr(owner, "_payload", {}).get("_creation_token"),
            )
        elif isinstance(owner, Shape):
            ref = cls(
                presentation,
                owner,
                owner._slide,
                None
                if owner.shape_id is None
                or owner._payload.get("_pending_shape")
                or owner._payload.get("_pending_group_child")
                else str(owner.shape_id),
                getattr(owner._slide, "_payload", {}).get("_creation_token"),
            )
        else:
            raise TypeError(
                "owner must be this Presentation, a Slide, NotesSlide or Shape"
            )
        ref.validate()
        return ref

    def validate(self) -> None:
        prs = self.presentation
        if prs._disposed:
            raise RuntimeError("presentation is disposed")
        if self.owner is prs:
            return
        part_owner = self.part_owner
        if getattr(part_owner, "_presentation", None) is not prs:
            raise LifecycleRefusal("owner belongs to another presentation")
        slide = (
            part_owner._slide
            if getattr(part_owner, "_is_notes_slide", False)
            else part_owner
        )
        if getattr(slide, "_deleted", False) or not any(s is slide for s in prs.slides):
            raise LifecycleRefusal("owner slide is no longer available")
        if self.owner is not part_owner and not any(
            s is self.owner for s in _shape_members(part_owner.shapes)
        ):
            raise LifecycleRefusal("owner shape is no longer available")

    def source_part(self) -> str | None:
        if self.owner is self.presentation:
            return presentation_partname(self.presentation._source_path)
        if self.owner is not self.part_owner and self.shape_id is None:
            return None
        if getattr(
            self.part_owner, "_is_notes_slide", False
        ) and self.part_owner.partname in getattr(
            self.presentation, "_pending_notes_slide_payloads", {}
        ):
            return None
        payload = getattr(self.part_owner, "_payload", {})
        if payload.get("_pending_creation"):
            return payload.get("_source_part")
        return str(self.part_owner.partname).lstrip("/") or None

    def resolve(
        self, staged_parts: Mapping[Any, str], resolver: Callable | None
    ) -> tuple[str, str | None]:
        self.validate()
        if resolver is not None:
            result = resolver(self)
            if result is not None:
                part, shape_id = result
                if not isinstance(part, str) or not part:
                    raise LifecycleRefusal("identity resolver returned no owner part")
                if self.owner is not self.part_owner and shape_id is None:
                    raise LifecycleRefusal("identity resolver returned no shape id")
                return part.lstrip("/"), None if shape_id is None else str(shape_id)
        if self.creation_token is not None and getattr(
            self.part_owner, "_payload", {}
        ).get("_pending_creation"):
            part = staged_parts.get(self.creation_token)
            if part is None:
                raise LifecycleRefusal("pending owner has no staged materialization")
        else:
            part = (
                presentation_partname(self.presentation._source_path)
                if self.owner is self.presentation
                else str(self.part_owner.partname).lstrip("/")
            )
        if not part:
            raise LifecycleRefusal("owner part is unavailable")
        if self.owner is not self.part_owner and self.shape_id is None:
            raise LifecycleRefusal(
                "authored shape requires an authoritative staged shape identity"
            )
        return part.lstrip("/"), self.shape_id


def shape_element(root: ET.Element, shape_id: str) -> ET.Element:
    matches = []
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        for nv_name in (
            "nvSpPr",
            "nvPicPr",
            "nvGrpSpPr",
            "nvCxnSpPr",
            "nvGraphicFramePr",
        ):
            nv = find_ooxml(element, f"{{{P_NS}}}{nv_name}/{{{P_NS}}}cNvPr")
            if nv is not None and nv.get("id") == shape_id:
                matches.append(element)
    if len(matches) != 1:
        raise LifecycleRefusal(f"missing or ambiguous shape id {shape_id!r}")
    return matches[0]


def _tag_container(
    root: ET.Element, shape_id: str | None, create: bool = False
) -> ET.Element | None:
    p_ns = ooxml_namespace(root, P_NS)
    if shape_id is not None:
        shape = shape_element(root, shape_id)
        candidates = [
            child
            for child in shape
            if isinstance(child.tag, str) and child.tag.startswith(f"{{{p_ns}}}nv")
        ]
        if len(candidates) != 1:
            raise LifecycleRefusal("shape has ambiguous nonvisual properties")
        parent = one(candidates[0], f"{{{P_NS}}}nvPr")
        if parent is None:
            raise LifecycleRefusal("shape has no application nonvisual properties")
    elif root.tag == f"{{{p_ns}}}presentation":
        parent = root
    else:
        parent = one(root, f"{{{P_NS}}}cSld")
        if parent is None:
            raise LifecycleRefusal("tag owner has no common slide data")
    container = one(parent, f"{{{P_NS}}}custDataLst")
    if container is None and create:
        container = ET.Element(f"{{{p_ns}}}custDataLst")
        # CT_Presentation and CT_CommonSlideData place customer data before
        # these successors; nvPr places it before extLst.
        successors = {
            "kinsoku",
            "defaultTextStyle",
            "modifyVerifier",
            "extLst",
            "controls",
        }
        index = next(
            (
                i
                for i, child in enumerate(parent)
                if child.tag in {f"{{{p_ns}}}{n}" for n in successors}
            ),
            len(parent),
        )
        parent.insert(index, container)
    return container


def relationships(
    package: Any,
    part: str,
    roots: dict[str, ET.Element],
    *,
    read_only: bool = False,
) -> ET.Element:
    """Resolve within a caller-owned cache of one parse intent, never a mixed cache."""
    name = rels_part_for_package_part(part)
    if name not in roots:
        roots[name] = (
            parse_xml(package.read(name), read_only=read_only)
            if name in package.namelist()
            else ET.Element(f"{{{PKG_REL_NS}}}Relationships")
        )
    return roots[name]


def relationship_target(
    package: Any,
    source: str,
    rels: ET.Element,
    *,
    rel_type: str,
    rel_id: str | None = None,
) -> str | None:
    # Both exact profile URIs identify the same singleton relationship family.
    # A second profile must be treated as ambiguity, not as an absent target.
    namespace, _, local = rel_type.rpartition("/")
    types = (
        (R_NS + "/" + local, STRICT_R_NS + "/" + local)
        if namespace in (R_NS, STRICT_R_NS)
        else (rel_type,)
    )
    matches = [
        r
        for r in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        if (r.get("Id") == rel_id if rel_id is not None else r.get("Type") in types)
    ]
    if not matches and rel_id is None:
        return None
    if (
        len(matches) != 1
        or matches[0].get("Type") != rel_type
        or matches[0].get("TargetMode", "Internal") != "Internal"
    ):
        raise LifecycleRefusal("missing, external or ambiguous lifecycle relationship")
    target = matches[0].get("Target")
    if not target:
        raise LifecycleRefusal("lifecycle relationship has no target")
    part = resolve_package_target(source, target)
    if part not in package.namelist():
        raise LifecycleRefusal("lifecycle relationship target is missing")
    return part


def add_part(
    package: Any,
    roots: dict[str, ET.Element],
    source: str,
    stem: str,
    rel_type: str,
    content_type: str,
    root: ET.Element,
) -> tuple[str, str]:
    names = set(package.namelist()) | roots.keys()
    part = stem + ".xml"
    index = 1
    while part in names:
        part = f"{stem}{index}.xml"
        index += 1
    rels = relationships(package, source, roots)
    ids = {r.get("Id") for r in rels}
    index = 1
    while f"rId{index}" in ids:
        index += 1
    rel_id = f"rId{index}"
    ET.SubElement(
        rels,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Id": rel_id,
            "Type": rel_type,
            "Target": posixpath.relpath(part, posixpath.dirname(source)),
        },
    )
    ct = roots.setdefault(
        "[Content_Types].xml", parse_xml(package.read("[Content_Types].xml"))
    )
    ET.SubElement(
        ct,
        f"{{{CONTENT_TYPES_NS}}}Override",
        {"PartName": "/" + part, "ContentType": content_type},
    )
    roots[part] = root
    return part, rel_id


def _tag_part(
    package: Any,
    source: str,
    root: ET.Element,
    shape_id: str | None,
    roots: dict[str, ET.Element],
    *,
    read_only: bool = False,
) -> tuple[str | None, ET.Element | None]:
    container = _tag_container(root, shape_id)
    tag = None if container is None else one(container, f"{{{P_NS}}}tags")
    if tag is None:
        return None, None
    r_ns = ooxml_namespace(root, R_NS)
    rel_id = tag.get(f"{{{r_ns}}}id")
    if rel_id is None:
        raise LifecycleRefusal("tag reference has no relationship id")
    part = relationship_target(
        package,
        source,
        relationships(package, source, roots, read_only=read_only),
        rel_type=r_ns + "/tags",
        rel_id=rel_id,
    )
    tag_root = roots.setdefault(part, parse_xml(package.read(part), read_only=read_only))
    if tag_root.tag != ooxml_path(tag_root, f"{{{P_NS}}}tagLst"):
        raise LifecycleRefusal("invalid tag part root")
    return part, tag_root


def _records(root: ET.Element | None) -> dict[str, str]:
    records: dict[str, str] = {}
    if root is not None:
        for tag in findall_ooxml(root, f"{{{P_NS}}}tag"):
            key, value = tag.get("name"), tag.get("val")
            if key is None or value is None or key in records:
                raise LifecycleRefusal("tag names/values are missing or duplicate")
            records[key] = value
    return records


class TagCollection(MutableMapping[str, str]):
    """Inspect scoped metadata; queued edits still require mutation-safe staging."""

    def __init__(self, presentation: Any, owner: Any) -> None:
        self._ref = OwnerRef.capture(presentation, owner)
        self._edits: dict[str, str | None] = {}
        part = self._ref.source_part()
        self._values: dict[str, str] = {}
        if part is not None:
            with open_package_source(presentation._source_path) as package:
                root = parse_xml(package.read(part), read_only=True)
                _, tags = _tag_part(
                    package, part, root, self._ref.shape_id, {}, read_only=True
                )
                self._values = _records(tags)

    def __getitem__(self, key: str) -> str:
        self._ref.validate()
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        self._ref.validate()
        return iter(self._values)

    def __len__(self) -> int:
        self._ref.validate()
        return len(self._values)

    def __setitem__(self, key: str, value: str) -> None:
        self.update({xml_string(key, "tag name"): value})

    def __delitem__(self, key: str) -> None:
        self._ref.validate()
        del self._values[key]
        self._edits[key] = None

    def update(self, other: Any = (), **kwargs: str) -> None:
        self._ref.validate()
        incoming = dict(other, **kwargs)
        for key, value in incoming.items():
            xml_string(key, "tag name")
            xml_string(value, "tag value")
        for key, value in incoming.items():
            if self._values.get(key) != value:
                self._values[key] = value
                self._edits[key] = value

    def clear(self) -> None:
        self._ref.validate()
        self._edits.update((key, None) for key in self._values)
        self._values.clear()

    @property
    def dirty(self) -> bool:
        return bool(self._edits)

    def snapshot(self) -> tuple[OwnerRef, tuple[tuple[str, str | None], ...]]:
        self._ref.validate()
        return self._ref, tuple(self._edits.items())

    def acknowledge(self, edits: tuple[tuple[str, str | None], ...]) -> None:
        for key, value in edits:
            if key in self._edits and self._edits[key] == value:
                del self._edits[key]


def apply_tag_edits(
    package: Any,
    roots: dict[str, ET.Element],
    snapshot: tuple,
    staged_parts: Mapping,
    resolver: Callable | None,
) -> None:
    ref, edits = snapshot
    source, shape_id = ref.resolve(staged_parts, resolver)
    root = roots.setdefault(source, parse_xml(package.read(source)))
    p_ns = ooxml_namespace(root, P_NS)
    r_ns = ooxml_namespace(root, R_NS)
    part, tags = _tag_part(package, source, root, shape_id, roots)
    if tags is None:
        if not any(value is not None for _, value in edits):
            return
        tags = ET.Element(f"{{{p_ns}}}tagLst")
        part, rel_id = add_part(
            package,
            roots,
            source,
            "ppt/tags/tag",
            r_ns + "/tags",
            TAG_CONTENT_TYPE,
            tags,
        )
        container = _tag_container(root, shape_id, create=True)
        ET.SubElement(container, f"{{{p_ns}}}tags", {f"{{{r_ns}}}id": rel_id})
    elif _shared_tag_part(package, roots, source, root, part):
        from copy import deepcopy

        tags = deepcopy(tags)
        part, rel_id = add_part(
            package,
            roots,
            source,
            "ppt/tags/tag",
            r_ns + "/tags",
            TAG_CONTENT_TYPE,
            tags,
        )
        container = _tag_container(root, shape_id)
        one(container, f"{{{P_NS}}}tags").set(f"{{{r_ns}}}id", rel_id)
    _records(tags)  # Validate before mutating the staged tree.
    tag_ns = ooxml_namespace(tags, P_NS)
    for key, value in edits:
        tag = next(
            (t for t in tags.findall(f"{{{tag_ns}}}tag") if t.get("name") == key), None
        )
        if value is None:
            if tag is not None:
                tags.remove(tag)
        elif tag is None:
            ET.SubElement(tags, f"{{{tag_ns}}}tag", {"name": key, "val": value})
        else:
            tag.set("val", value)
    # Retain an empty part/reference. Removing it could destroy unknown metadata
    # or another owner's relationship to a shared tags part.


def _shared_tag_part(
    package: Any, roots: dict, source: str, root: ET.Element, part: str
) -> bool:
    """Copy on write when several owners reference a user-defined tags part."""
    references = 0
    p_ns = ooxml_namespace(root, P_NS)
    r_ns = ooxml_namespace(root, R_NS)
    for name in set(package.namelist()) | roots.keys():
        if not name.endswith(".rels") or "/_rels/" not in name:
            continue
        rel_source = name.replace("/_rels/", "/")[:-5]
        rel_root = roots.get(name)
        if rel_root is None:
            rel_root = ET.fromstring(package.read(name))
        for rel in rel_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
            if rel.get("TargetMode", "Internal") != "Internal":
                continue
            if resolve_package_target(rel_source, rel.get("Target", "")) != part:
                continue
            if rel_source != source:
                references += 1
            else:
                references += sum(
                    t.get(f"{{{r_ns}}}id") == rel.get("Id")
                    for t in root.iter(f"{{{p_ns}}}tags")
                )
    return references > 1
