"""DrawingML fields with explicit, deterministic cache refresh.

OOXML field meanings: ISO/IEC 29500-1 21.1.2.2.2 (fld), reproduced in
Microsoft Learn, DocumentFormat.OpenXml.Drawing.Field, revision
22742c84d020817424ad6c54d85d9ac1e69a0bae. Formatting below deliberately supports
only en-US, Gregorian dates and caller-supplied fixed UTC offsets. It never
consults the clock, process locale, timezone database or native Office.
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from xml.etree import ElementTree as ET

from .package_parts import (
    A_NS,
    CONTENT_TYPES_NS,
    P_NS,
    PKG_REL_NS,
    open_package_source,
    rels_part_for_package_part,
    resolve_package_target,
)
from .presentation_tags import (
    LifecycleRefusal,
    OwnerRef,
    one,
    parse_xml,
    serialize_xml,
    shape_element,
    xml_string,
)
from .slide_metadata import presentation_partname
from .xml_helpers import STRICT_A_NS, findall_ooxml, ooxml_namespace, ooxml_path

SUPPORTED_REFRESH_TYPES = frozenset(("slidenum", *(f"datetime{i}" for i in range(1, 13))))
_GUID = re.compile(
    r"\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}\Z"
)
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass(frozen=True)
class FieldRefreshContext:
    timestamp: datetime
    locale: str
    timezone: timezone

    def local_time(self) -> datetime:
        if not isinstance(self.timestamp, datetime):
            raise TypeError("refresh timestamp must be datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise LifecycleRefusal("refresh timestamp must be timezone-aware")
        if not isinstance(self.locale, str):
            raise TypeError("refresh locale must be str")
        if self.locale != "en-US":
            raise LifecycleRefusal(
                "field refresh supports only explicit en-US Gregorian formatting"
            )
        if not isinstance(self.timezone, timezone):
            raise LifecycleRefusal(
                "field refresh requires an explicit datetime.timezone fixed offset"
            )
        return self.timestamp.astimezone(self.timezone)


def _guid(value: Any) -> str:
    xml_string(value, "field id")
    if not _GUID.fullmatch(value):
        raise LifecycleRefusal("field id must be a braced OOXML GUID")
    return "{" + str(UUID(value)).upper() + "}"


def _guid_key(value: str | None) -> str | None:
    return value.upper() if value is not None else None


def _signature(element: ET.Element) -> tuple:
    return (
        element.tag,
        tuple(sorted((k, v) for k, v in element.attrib.items() if not k.startswith("xmlns"))),
        element.text or "",
        tuple(_signature(child) for child in element),
    )


def _xml_parts(package: Any) -> set[str]:
    ct = ET.fromstring(package.read("[Content_Types].xml"))
    defaults = {
        n.get("Extension"): n.get("ContentType", "")
        for n in ct.findall(f"{{{CONTENT_TYPES_NS}}}Default")
    }
    overrides = {
        n.get("PartName", "").lstrip("/"): n.get("ContentType", "")
        for n in ct.findall(f"{{{CONTENT_TYPES_NS}}}Override")
    }
    return {
        name
        for name in package.namelist()
        if (overrides.get(name, defaults.get(name.rsplit(".", 1)[-1], "")))
        .split(";")[0]
        .endswith(("/xml", "+xml"))
    }


def field_id_counts(package: Any, roots: dict | None = None) -> Counter:
    roots = roots or {}
    counts: Counter = Counter()
    field_tags = (f"{{{A_NS}}}fld", f"{{{STRICT_A_NS}}}fld")
    for part in _xml_parts(package) | roots.keys():
        root = roots[part] if part in roots else ET.fromstring(package.read(part))
        for field in root.iter():
            if field.tag in field_tags:
                counts[_guid_key(field.get("id"))] += 1
    return counts


def _body(shape: ET.Element) -> ET.Element:
    body = one(shape, f"{{{P_NS}}}txBody")
    if body is None:
        raise LifecycleRefusal("field owner has no shape text body")
    return body


@dataclass(frozen=True)
class FieldEdit:
    ref: OwnerRef
    field_id: str
    operation: str
    field_type: str | None
    cached_text: str | None
    expected_type: str | None
    expected_text: str | None
    language: str | None = None
    paragraph_anchor: tuple | None = None


class TextField:
    """Stable owner/field GUID handle; unsupported types stay inspectable."""

    def __init__(
        self,
        collection: FieldCollection,
        field_id: str | None,
        field_type: str | None,
        text: str | None,
        *,
        created: bool = False,
        language: str | None = None,
        anchor: tuple | None = None,
    ) -> None:
        self._collection = collection
        self._id = field_id
        self._type = field_type
        self._text = text
        self._baseline_type = field_type
        self._baseline_text = text
        self._created = created
        self._removed = False
        self._dirty = created
        self._language = language
        self._anchor = anchor

    @property
    def id(self) -> str | None:
        return self._id

    @property
    def type(self) -> str | None:
        return self._type

    @type.setter
    def type(self, value: str) -> None:
        """Retarget in place; retain the explicit cache until caller refreshes."""
        self._check()
        try:
            xml_string(value, "field type")
        except TypeError as exc:
            raise LifecycleRefusal(str(exc)) from exc
        if not value.strip():
            raise LifecycleRefusal("field type must not be blank")
        with open_package_source(self._collection._presentation._source_path) as package:
            _require_unsigned_fields(package)
            expected = 0 if self._created else 1
            if field_id_counts(package)[_guid_key(self.id)] != expected:
                raise LifecycleRefusal("field id is missing or ambiguous in document")
        if value != self._type:
            self._collection._check_text_edit_lock()
            self._type = value
            self._dirty = True

    @property
    def cached_text(self) -> str | None:
        return self._text

    @cached_text.setter
    def cached_text(self, value: str | None) -> None:
        self._check()
        if value is not None:
            xml_string(value, "cached field text")
        if value != self._text:
            self._collection._check_text_edit_lock()
            self._text = value
            self._dirty = True

    @property
    def refresh_supported(self) -> bool:
        return self._type in SUPPORTED_REFRESH_TYPES

    def _check(self) -> None:
        self._collection._ref.validate()
        if self._removed or self not in self._collection._fields:
            raise LifecycleRefusal("field has been removed")
        _guid(self._id)
        if sum(_guid_key(f.id) == _guid_key(self.id) for f in self._collection._fields) != 1:
            raise LifecycleRefusal("field id is ambiguous within owner")

    def remove(self) -> None:
        self._collection.remove(self)

    def _edit(self) -> FieldEdit:
        return FieldEdit(
            self._collection._ref,
            self._id,
            "delete" if self._removed else "add" if self._created else "cache",
            self._type,
            self._text,
            self._baseline_type,
            self._baseline_text,
            self._language,
            self._anchor,
        )


class FieldCollection(Sequence[TextField]):
    """Inspect scoped field metadata without relaxing save-time preservation."""

    def __init__(self, presentation: Any, shape: Any) -> None:
        self._presentation = presentation
        self._ref = OwnerRef.capture(presentation, shape)
        if self._ref.owner is self._ref.part_owner:
            raise TypeError("fields require a Shape owner")
        if not shape.has_text_frame:
            raise LifecycleRefusal("field owner has no text frame")
        self._fields: list[TextField] = []
        self._deleted: list[TextField] = []
        part = self._ref.source_part()
        if part is not None:
            with open_package_source(presentation._source_path) as package:
                root = parse_xml(package.read(part), read_only=True)
                body = _body(shape_element(root, self._ref.shape_id))
                for paragraph in findall_ooxml(body, f"{{{A_NS}}}p"):
                    for field in findall_ooxml(paragraph, f"{{{A_NS}}}fld"):
                        text = one(field, f"{{{A_NS}}}t")
                        self._fields.append(
                            TextField(
                                self,
                                field.get("id"),
                                field.get("type"),
                                None if text is None else text.text or "",
                            )
                        )

    def __len__(self) -> int:
        self._ref.validate()
        return len(self._fields)

    def __getitem__(self, index: int | slice) -> TextField | list[TextField]:
        self._ref.validate()
        return self._fields[index]

    def __iter__(self) -> Iterator[TextField]:
        self._ref.validate()
        return iter(self._fields)

    def get_by_id(self, field_id: str) -> TextField | None:
        key = _guid_key(_guid(field_id))
        matches = [f for f in self if _guid_key(f.id) == key]
        if len(matches) > 1:
            raise LifecycleRefusal("field id is ambiguous within owner")
        return matches[0] if matches else None

    def add(
        self,
        field_type: str,
        cached_text: str | None = "",
        *,
        field_id: str | None = None,
        language: str | None = None,
        paragraph: Any = None,
    ) -> TextField:
        """Append a field in a new paragraph, or a uniquely anchored loaded one.

        No paragraph ordinal is retained. For an explicit loaded paragraph,
        require a unique unchanged XML preimage at save; destructive edits
        refuse instead of silently retargeting a neighboring paragraph.
        """
        self._ref.validate()
        self._check_text_edit_lock()
        xml_string(field_type, "field type")
        if cached_text is not None:
            xml_string(cached_text, "cached field text")
        if language is not None:
            xml_string(language, "field language")
        identifier = _guid(field_id) if field_id is not None else "{" + str(uuid4()).upper() + "}"
        self._presentation.fields._require_unused_id(identifier)
        anchor = None
        if paragraph is not None:
            from .text_facade import TextParagraph

            if not isinstance(paragraph, TextParagraph):
                raise TypeError("paragraph must be a TextParagraph")
            if paragraph._shape is not self._ref.owner:
                raise LifecycleRefusal("paragraph belongs to another field owner")
            part = self._ref.source_part()
            if part is None:
                raise LifecycleRefusal(
                    "authored paragraphs lack a stable anchor; "
                    "omit paragraph to append a field paragraph"
                )
            with open_package_source(self._presentation._source_path) as package:
                body = _body(shape_element(parse_xml(package.read(part)), self._ref.shape_id))
                paragraphs = findall_ooxml(body, f"{{{A_NS}}}p")
                if not 0 <= paragraph._index < len(paragraphs):
                    raise LifecycleRefusal("paragraph has no persisted anchor")
                anchor = _signature(paragraphs[paragraph._index])
                if sum(_signature(p) == anchor for p in paragraphs) != 1:
                    raise LifecycleRefusal("paragraph anchor is ambiguous")
        field = TextField(
            self,
            identifier,
            field_type,
            cached_text,
            created=True,
            language=language,
            anchor=anchor,
        )
        self._fields.append(field)
        return field

    def remove(self, field: TextField) -> None:
        if not isinstance(field, TextField):
            raise TypeError("field must be TextField")
        if field._collection is not self:
            raise LifecycleRefusal("field belongs to another owner")
        field._check()
        self._check_text_edit_lock()
        self._fields.remove(field)
        field._removed = True
        if not field._created:
            self._deleted.append(field)

    def _check_text_edit_lock(self) -> None:
        from .shape_locks import check_shape_locks

        check_shape_locks(self._ref.owner, "field edit", "no_text_edit")

    @property
    def dirty(self) -> bool:
        return bool(self._deleted) or any(f._dirty for f in self._fields)

    def snapshot(self) -> tuple[tuple[TextField, FieldEdit], ...]:
        self._ref.validate()
        return tuple(
            (f, f._edit()) for f in (*self._fields, *self._deleted) if f._dirty or f._removed
        )

    def acknowledge(self, records: tuple) -> None:
        for field, edit in records:
            if edit.operation == "delete":
                if field in self._deleted:
                    self._deleted.remove(field)
            else:
                field._created = False
                field._baseline_type = edit.field_type
                field._baseline_text = edit.cached_text
                field._dirty = field._text != edit.cached_text or field._type != edit.field_type
                if field._removed and field not in self._deleted:
                    self._deleted.append(field)


class PresentationFields:
    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation
        self._collections: dict[Any, FieldCollection] = {}

    def for_shape(self, shape: Any) -> FieldCollection:
        OwnerRef.capture(self._presentation, shape)
        if shape not in self._collections:
            self._collections[shape] = FieldCollection(self._presentation, shape)
        return self._collections[shape]

    def _require_unused_id(self, field_id: str) -> None:
        with open_package_source(self._presentation._source_path) as package:
            counts = field_id_counts(package)
        if counts[_guid_key(field_id)] or any(
            _guid_key(f.id) == _guid_key(field_id)
            for c in self._collections.values()
            for f in c._fields
        ):
            raise LifecycleRefusal("field id already exists in this document")

    def refresh(
        self, fields: Iterable[TextField], *, context: FieldRefreshContext
    ) -> tuple[TextField, ...]:
        """Compute all selected caches before changing any; save never refreshes."""
        if not isinstance(context, FieldRefreshContext):
            raise TypeError("context must be FieldRefreshContext")
        local = context.local_time()
        selected = tuple(fields)
        if len({id(f) for f in selected}) != len(selected):
            raise LifecycleRefusal("refresh selection contains duplicate handles")
        with open_package_source(self._presentation._source_path) as package:
            counts = field_id_counts(package)
        replacements = []
        for field in selected:
            if not isinstance(field, TextField):
                raise TypeError("refresh selection must contain TextField handles")
            if field._collection._presentation is not self._presentation:
                raise LifecycleRefusal("refresh field belongs to another presentation")
            field._check()
            field._collection._check_text_edit_lock()
            expected = 0 if field._created else 1
            if counts[_guid_key(field.id)] != expected:
                raise LifecycleRefusal("refresh field id is missing or duplicated in document")
            if field.type not in SUPPORTED_REFRESH_TYPES:
                raise LifecycleRefusal(
                    f"unsupported refresh field type {field.type!r}; cache preserved"
                )
            if field.type == "slidenum":
                owner = field._collection._ref.part_owner
                slide = owner._slide if getattr(owner, "_is_notes_slide", False) else owner
                with open_package_source(self._presentation._source_path) as package:
                    root = ET.fromstring(
                        package.read(presentation_partname(self._presentation._source_path))
                    )
                    first = root.get("firstSlideNum", "1")
                try:
                    first_number = int(first)
                except ValueError as exc:
                    raise LifecycleRefusal("unsupported firstSlideNum value") from exc
                text = str(first_number + self._presentation.slides.index(slide))
            else:
                text = _date_text(field.type, local)
            replacements.append((field, text))
        for field, text in replacements:
            field.cached_text = text
        return selected

    @property
    def dirty(self) -> bool:
        return any(c.dirty for c in self._collections.values())


def _date_text(field_type: str, value: datetime) -> str:
    date = f"{value.month:02}/{value.day:02}/{value.year:04}"
    month = _MONTHS[value.month - 1]
    year = f"{value.year % 100:02}"
    hour12 = value.hour % 12 or 12
    ampm = "AM" if value.hour < 12 else "PM"
    time12 = f"{hour12}:{value.minute:02}"
    values = {
        "datetime1": date,
        "datetime2": f"{_DAYS[value.weekday()]}, {month} {value.day:02}, {value.year:04}",
        "datetime3": f"{value.day:02} {month} {value.year:04}",
        "datetime4": f"{month} {value.day:02}, {value.year:04}",
        "datetime5": f"{value.day:02}-{month[:3]}-{year}",
        "datetime6": f"{month} {year}",
        "datetime7": f"{month[:3]}-{year}",
        "datetime8": f"{date} {time12} {ampm}",
        "datetime9": f"{date} {time12}:{value.second:02} {ampm}",
        "datetime10": f"{value.hour:02}:{value.minute:02}",
        "datetime11": f"{value.hour:02}:{value.minute:02}:{value.second:02}",
        "datetime12": f"{time12} {ampm}",
    }
    return values[field_type]


def _require_unsigned_fields(package: Any) -> None:
    if any(name.casefold().startswith("_xmlsignatures/") for name in package.namelist()):
        raise LifecycleRefusal("signed packages cannot have fields edited")
    for part in ("[Content_Types].xml", "_rels/.rels"):
        root = ET.fromstring(package.read(part))
        if any(
            "digital-signature" in node.get("Type", "")
            or "digital-signature" in node.get("ContentType", "")
            for node in root
        ):
            raise LifecycleRefusal("signed packages cannot have fields edited")


def apply_field_edits(
    package: Any, roots: dict, records: tuple, staged_parts: dict, resolver: Any
) -> None:
    _require_unsigned_fields(package)
    counts = field_id_counts(package, roots)
    # Resolve every anchor against the same pre-edit trees, so two additions to
    # one paragraph do not invalidate each other's anchor.
    plans = []
    for _, edit in records:
        source, shape_id = edit.ref.resolve(staged_parts, resolver)
        root = roots.setdefault(source, parse_xml(package.read(source)))
        body = _body(shape_element(root, shape_id))
        identifier = _guid(edit.field_id)
        key = _guid_key(identifier)
        if edit.operation == "add":
            if counts[key]:
                raise LifecycleRefusal("field id already exists in staged document")
            counts[key] += 1
            if edit.paragraph_anchor is None:
                paragraph = None
            else:
                matches = [
                    p
                    for p in findall_ooxml(body, f"{{{A_NS}}}p")
                    if _signature(p) == edit.paragraph_anchor
                ]
                if len(matches) != 1:
                    raise LifecycleRefusal(
                        "field paragraph was changed, removed or became ambiguous"
                    )
                paragraph = matches[0]
            plans.append((edit, body, paragraph, None))
            continue
        if counts[key] != 1:
            raise LifecycleRefusal("field id is missing or ambiguous in staged document")
        matches = [
            (p, f)
            for p in findall_ooxml(body, f"{{{A_NS}}}p")
            for f in findall_ooxml(p, f"{{{A_NS}}}fld")
            if _guid_key(f.get("id")) == key
        ]
        if len(matches) != 1:
            raise LifecycleRefusal("field no longer belongs to its original shape")
        paragraph, field = matches[0]
        text_node = one(field, f"{{{A_NS}}}t")
        text = None if text_node is None else text_node.text or ""
        if field.get("type") != edit.expected_type or text != edit.expected_text:
            raise LifecycleRefusal("field cache/type changed through another edit path")
        plans.append((edit, body, paragraph, field))
    for edit, body, paragraph, field in plans:
        if edit.operation == "delete":
            paragraph.remove(field)
            continue
        if edit.operation == "add":
            a_ns = ooxml_namespace(body, A_NS)
            if paragraph is None:
                paragraph = ET.SubElement(body, f"{{{a_ns}}}p")
            field = ET.Element(
                f"{{{ooxml_namespace(paragraph, A_NS)}}}fld",
                {"id": edit.field_id, "type": edit.field_type},
            )
            if edit.language is not None:
                ET.SubElement(
                    field,
                    f"{{{ooxml_namespace(field, A_NS)}}}rPr",
                    {"lang": edit.language},
                )
            end = one(paragraph, f"{{{A_NS}}}endParaRPr")
            paragraph.insert(len(paragraph) if end is None else list(paragraph).index(end), field)
        else:
            if edit.field_type is None:
                field.attrib.pop("type", None)
            else:
                field.set("type", edit.field_type)
        text_node = one(field, f"{{{A_NS}}}t")
        if edit.cached_text is None:
            if text_node is not None:
                field.remove(text_node)
        else:
            if text_node is None:
                text_node = ET.SubElement(field, f"{{{ooxml_namespace(field, A_NS)}}}t")
            text_node.text = edit.cached_text


# -- header and footer placeholders ---------------------------------------

#: The slide placeholders each header/footer toggle shows or hides.
HEADER_FOOTER_PLACEHOLDERS = {
    "show_footer": "ftr",
    "show_slide_number": "sldNum",
    "show_date": "dt",
}


def _related_part(package: Any, owner: str, relationship: str) -> str | None:
    rels = rels_part_for_package_part(owner)
    if rels not in package.namelist():
        return None
    root = ET.fromstring(package.read(rels))
    for node in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if node.get("Type", "").rsplit("/", 1)[-1] == relationship and (
            node.get("TargetMode", "Internal") == "Internal"
        ):
            part = resolve_package_target(owner, node.get("Target", ""))
            if part in package.namelist():
                return part
    return None


def _placeholder_type(shape: ET.Element) -> str | None:
    placeholder = shape.find(ooxml_path(shape, f"{{{P_NS}}}nvSpPr/{{{P_NS}}}nvPr/{{{P_NS}}}ph"))
    return None if placeholder is None else placeholder.get("type", "body")


def _placeholders(tree: ET.Element, kind: str) -> list[tuple[ET.Element, ET.Element]]:
    """Return ``(parent, shape)`` for every ``kind`` placeholder under ``tree``."""
    shape_tag = ooxml_path(tree, f"{{{P_NS}}}sp")
    return [
        (parent, child)
        for parent in tree.iter()
        for child in parent
        if child.tag == shape_tag and _placeholder_type(child) == kind
    ]


def _shape_tree(root: ET.Element) -> ET.Element:
    tree = root.find(ooxml_path(root, f"{{{P_NS}}}cSld/{{{P_NS}}}spTree"))
    if tree is None:
        raise LifecycleRefusal("slide has no shape tree")
    return tree


def _max_shape_id(root: ET.Element) -> int:
    ids = [
        int(node.get("id", "0"))
        for node in root.iter()
        if isinstance(node.tag, str)
        and node.tag.endswith("}cNvPr")
        and node.get("id", "").isdigit()
    ]
    return max(ids, default=1)


def _set_paragraph_text(body: ET.Element, text: str) -> None:
    """Make ``text`` the whole content of a text body, keeping first formatting."""
    a_ns = ooxml_namespace(body, A_NS)
    paragraphs = findall_ooxml(body, f"{{{A_NS}}}p")
    first = paragraphs[0] if paragraphs else ET.SubElement(body, f"{{{a_ns}}}p")
    for extra in paragraphs[1:]:
        body.remove(extra)
    run_properties = None
    for child in first.iter():
        if child.tag == f"{{{a_ns}}}rPr":
            run_properties = deepcopy(child)
            break
    end = one(first, f"{{{A_NS}}}endParaRPr")
    for child in list(first):
        if child.tag not in (f"{{{a_ns}}}pPr", f"{{{a_ns}}}endParaRPr"):
            first.remove(child)
    if text:
        run = ET.Element(f"{{{a_ns}}}r")
        run.append(
            run_properties
            if run_properties is not None
            else ET.Element(f"{{{a_ns}}}rPr", {"lang": "en-US"})
        )
        ET.SubElement(run, f"{{{a_ns}}}t").text = text
        first.insert(len(first) if end is None else list(first).index(end), run)


def _placeholder_copy(
    template: ET.Element, from_layout: bool, shape_id: int, kind: str, number: int
) -> ET.Element:
    """Copy a layout or master placeholder into a slide.

    A layout copy keeps an empty ``p:spPr`` so position and size stay
    inherited from the layout, as PowerPoint writes it; a master copy keeps
    the master's geometry because no layout placeholder is there to inherit
    from.  Fields get fresh ids, so every field id stays unique in the deck.
    """
    shape = deepcopy(template)
    p_ns = ooxml_namespace(shape, P_NS)
    a_ns = ooxml_namespace(shape, A_NS)
    properties = shape.find(f"{{{p_ns}}}nvSpPr/{{{p_ns}}}cNvPr")
    if properties is None:
        raise LifecycleRefusal("header/footer placeholder has no cNvPr")
    properties.set("id", str(shape_id))
    if from_layout:
        geometry = shape.find(f"{{{p_ns}}}spPr")
        if geometry is not None:
            geometry.clear()
    for field in shape.iter(f"{{{a_ns}}}fld"):
        field.set("id", "{" + str(uuid4()).upper() + "}")
        if kind == "sldNum" and field.get("type") == "slidenum":
            text = field.find(f"{{{a_ns}}}t")
            if text is None:
                text = ET.SubElement(field, f"{{{a_ns}}}t")
            text.text = str(number)
    return shape


def _append_shape(tree: ET.Element, shape: ET.Element) -> None:
    extension = tree.find(ooxml_path(tree, f"{{{P_NS}}}extLst"))
    tree.insert(len(tree) if extension is None else list(tree).index(extension), shape)


def _set_master_flags(root: ET.Element, flags: dict[str, bool], create: bool) -> bool:
    """Mirror the toggles in a master's or layout's ``p:hf`` new-slide flags."""
    p_ns = ooxml_namespace(root, P_NS)
    flags_element = root.find(f"{{{p_ns}}}hf")
    if flags_element is None:
        if not create or all(flags.values()):
            return False
        successors = {f"{{{p_ns}}}txStyles", f"{{{p_ns}}}extLst"}
        index = next((i for i, child in enumerate(root) if child.tag in successors), len(root))
        flags_element = ET.Element(f"{{{p_ns}}}hf")
        root.insert(index, flags_element)
    before = dict(flags_element.attrib)
    for attribute, shown in flags.items():
        if shown:
            flags_element.attrib.pop(attribute, None)
        else:
            flags_element.set(attribute, "0")
    return before != flags_element.attrib


def header_footer_replacements(
    package: Any,
    slide_parts: Sequence[str],
    selection: Sequence[int],
    *,
    toggles: dict[str, bool],
    footer_text: str | None,
    update_masters: bool,
) -> dict[str, bytes]:
    """Plan the slide rewrites that show or hide footer, number and date.

    ``toggles`` maps ``ftr``/``sldNum``/``dt`` to shown or hidden.  Showing
    copies the placeholder from the slide's layout (or, failing that, its
    master) onto each selected slide that lacks one; hiding removes the
    slide's placeholders together with timing that animated only them.
    ``footer_text`` rewrites the text of every shown footer.  With
    ``update_masters`` the masters' and layouts' ``p:hf`` flags follow, so
    slides PowerPoint adds later agree with the deck.
    """
    from .presentation_save_state import _drop_deleted_shape_timing

    if footer_text is not None:
        xml_string(footer_text, "footer_text")
    presentation = ET.fromstring(package.read(_presentation_part_from_package(package)))
    try:
        first_number = int(presentation.get("firstSlideNum", "1"))
    except ValueError as exc:
        raise LifecycleRefusal("unsupported firstSlideNum value") from exc
    replacements: dict[str, bytes] = {}
    for index in selection:
        part = slide_parts[index]
        root = parse_xml(package.read(part))
        tree = _shape_tree(root)
        layout_part = _related_part(package, part, "slideLayout")
        layout = None if layout_part is None else ET.fromstring(package.read(layout_part))
        master_part = (
            None if layout_part is None else _related_part(package, layout_part, "slideMaster")
        )
        master = None if master_part is None else ET.fromstring(package.read(master_part))
        next_id = _max_shape_id(root)
        removed: set[str] = set()
        changed = False
        for kind, shown in toggles.items():
            present = _placeholders(tree, kind)
            if not shown:
                for parent, shape in present:
                    identity = shape.find(ooxml_path(shape, f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr"))
                    if identity is not None:
                        removed.add(identity.get("id", ""))
                    parent.remove(shape)
                    changed = True
                continue
            if present:
                continue
            template = None
            from_layout = False
            if layout is not None and _placeholders(_shape_tree(layout), kind):
                template = _placeholders(_shape_tree(layout), kind)[0][1]
                from_layout = True
            elif master is not None and _placeholders(_shape_tree(master), kind):
                template = _placeholders(_shape_tree(master), kind)[0][1]
            if template is None:
                raise LifecycleRefusal(
                    f"slide {index + 1} has no {kind} placeholder on its layout or master to show"
                )
            next_id += 1
            _append_shape(
                tree,
                _placeholder_copy(template, from_layout, next_id, kind, first_number + index),
            )
            changed = True
        if footer_text is not None and toggles.get("ftr", True):
            for _parent, shape in _placeholders(tree, "ftr"):
                body = one(shape, f"{{{P_NS}}}txBody")
                if body is None:
                    body = ET.SubElement(shape, f"{{{ooxml_namespace(shape, P_NS)}}}txBody")
                _set_paragraph_text(body, footer_text)
                changed = True
        if not changed:
            continue
        payload = serialize_xml(root)
        if removed:
            payload = _drop_deleted_shape_timing(payload, removed) or payload
        replacements[part] = payload
    if update_masters:
        flags = {kind: shown for kind, shown in toggles.items()}
        for name in sorted(package.namelist()):
            is_master = re.fullmatch(r"ppt/slideMasters/[^/]+\.xml", name) is not None
            is_layout = re.fullmatch(r"ppt/slideLayouts/[^/]+\.xml", name) is not None
            if not (is_master or is_layout):
                continue
            root = parse_xml(package.read(name))
            if _set_master_flags(root, flags, create=is_master):
                replacements[name] = serialize_xml(root)
    return replacements


def _presentation_part_from_package(package: Any) -> str:
    root = ET.fromstring(package.read("_rels/.rels"))
    for node in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if node.get("Type", "").endswith("/officeDocument"):
            return resolve_package_target("", node.get("Target", ""))
    return posixpath.join("ppt", "presentation.xml")
