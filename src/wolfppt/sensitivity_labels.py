"""Modern OPC sensitivity labels and explicit, non-encrypting content marks.

The package-root classificationlabels relationship identifies the LabelInfo
part (MS-OI29500 section 2.1.22). Header/footer/watermark bits are 1/2/4;
encryption bit 8 and policy operations are refused. Callers supply every mark's
text, slide and geometry. No tenant lookup or legacy migration occurs. Save
queued edits first, then publish the atomic label/shape rewrite with save.

Only the requested label's known attributes are changed. Byte-local XML edits
retain unknown attributes, extensions, namespace scopes, comments, and all
unrelated part payloads. Removal records a tombstone, retaining unknown metadata;
``read`` excludes tombstones but includes disabled, nonremoved labels.
"""

from __future__ import annotations

import json
import math
import posixpath
import re
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Any
from xml.etree import ElementTree as ET
from xml.parsers import expat
from xml.sax.saxutils import quoteattr

from .package_conformance import _ATTRIBUTE, _insert_attribute, _tag_end
from .package_parts import A_NS, P_NS, R_NS, open_package_source
from .presentation_fields import _signature
from .presentation_tags import LifecycleRefusal, xml_string
from .xml_helpers import ooxml_namespace

_LABEL_NS = "http://schemas.microsoft.com/office/2020/mipLabelMetadata"
_LABEL_REL = "http://schemas.microsoft.com/office/2020/02/relationships/classificationlabels"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_LABEL_PART = "docMetadata/LabelInfo.xml"
_GUID = re.compile(r"\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}")
_MARK_NS = "urn:wolfppt:sensitivity-content-mark:1"
_MARK_BITS = {"header": 1, "footer": 2, "watermark": 4}


class SensitivityLabelRefusal(ValueError):
    """Label metadata cannot be safely read or edited; no policy was applied."""


@dataclass(frozen=True)
class SensitivityLabel:
    """A metadata value; construction does not authorize a labeling operation.

    ``id`` and ``site_id`` use braced GUIDs, matched case-insensitively. Reads
    retain their authored spelling, method, and unsigned content bitmask. Apply
    accepts Standard/Privileged methods, real bools and ``removed=False``.
    Nonzero bits require matching explicit content marks, never encryption.
    Unknown XML metadata stays in the package, not in this immutable value.
    """

    id: str
    site_id: str
    method: str = "Standard"
    enabled: bool = True
    content_bits: int | None = 0
    removed: bool = False


@dataclass(frozen=True)
class SensitivityContentMark:
    """One text mark on one zero-based slide; geometry is explicit integer EMU.

    ``kind`` is header, footer or watermark. Font size is points, color is RGB
    hex, and rotation is clockwise degrees. Marks are ordinary rendered shapes
    with persisted ownership metadata. Updating/removing an externally changed
    owned shape refuses instead of deleting user work.
    """

    kind: str
    text: str
    slide_index: int
    left: int
    top: int
    width: int
    height: int
    font_name: str
    font_size: float = 18.0
    color: str = "808080"
    rotation: float = 0.0


@dataclass
class _Node:
    name: str
    attributes: dict[str, str]
    start: int
    tag_end: int
    close: int = 0
    end: int = 0
    children: list[_Node] = field(default_factory=list)


@dataclass
class _Document:
    source: bytes
    root: _Node


def _parse(source: bytes, description: str) -> _Document:
    try:
        source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SensitivityLabelRefusal(f"{description} must be UTF-8 XML") from exc
    parser = expat.ParserCreate(namespace_separator="}")
    stack: list[_Node] = []
    roots: list[_Node] = []

    def start(name: str, attributes: dict[str, str]) -> None:
        offset = parser.CurrentByteIndex
        node = _Node(name, attributes, offset, _tag_end(source, offset))
        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)

    def end(_name: str) -> None:
        node = stack.pop()
        node.close = parser.CurrentByteIndex
        node.end = (
            node.tag_end
            if source[node.start : node.tag_end].endswith(b"/>")
            else _tag_end(source, node.close)
        )

    def declaration(_version: str, encoding: str | None, _standalone: int) -> None:
        if encoding is not None and encoding.casefold() not in {"utf-8", "us-ascii"}:
            raise SensitivityLabelRefusal(f"{description} must be UTF-8 XML")

    def doctype(_name: str, _system: str | None, _public: str | None, _internal: int) -> None:
        raise SensitivityLabelRefusal(f"{description} DTDs and entities are unsupported")

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.XmlDeclHandler = declaration
    parser.StartDoctypeDeclHandler = doctype
    try:
        parser.Parse(source, True)
    except (expat.ExpatError, ValueError) as exc:
        if isinstance(exc, SensitivityLabelRefusal):
            raise
        raise SensitivityLabelRefusal(f"{description} is malformed XML") from exc
    return _Document(source, roots[0])


def _root(document: _Document, namespace: str, local: str) -> None:
    if document.root.name != f"{namespace}}}{local}":
        raise SensitivityLabelRefusal(f"unsupported {local} XML namespace or root")


def _guid(value: Any, description: str) -> str:
    if not isinstance(value, str) or _GUID.fullmatch(value) is None:
        raise SensitivityLabelRefusal(f"{description} must be a braced GUID")
    return value.casefold()


def _identity(label: SensitivityLabel) -> tuple[str, str]:
    return _guid(label.id, "label id"), _guid(label.site_id, "label site_id")


def _bool(value: str | None, description: str) -> bool:
    if value not in {"0", "1", "false", "true"}:
        raise SensitivityLabelRefusal(f"{description} must be an XML boolean")
    return value in {"1", "true"}


def _label(node: _Node) -> SensitivityLabel:
    attributes = node.attributes
    id_value = attributes.get("id", "")
    site_id = attributes.get("siteId", "")
    _guid(id_value, "label id")
    _guid(site_id, "label siteId")
    if "method" not in attributes:
        raise SensitivityLabelRefusal("label method is missing")
    raw_bits = attributes.get("contentBits")
    bits = None
    if raw_bits is not None:
        if re.fullmatch(r"\+?[0-9]+", raw_bits) is None:
            raise SensitivityLabelRefusal("label contentBits must be an unsigned integer")
        bits = int(raw_bits)
        if bits > 0xFFFFFFFF:
            raise SensitivityLabelRefusal("label contentBits exceeds the unsigned integer range")
    return SensitivityLabel(
        id=id_value,
        site_id=site_id,
        method=attributes["method"],
        enabled=_bool(attributes.get("enabled"), "label enabled"),
        content_bits=bits,
        removed=_bool(attributes.get("removed"), "label removed"),
    )


def _labels(document: _Document) -> list[tuple[_Node, SensitivityLabel]]:
    _root(document, _LABEL_NS, "labelList")
    records: list[tuple[_Node, SensitivityLabel]] = []
    identities: set[tuple[str, str]] = set()
    for node in document.root.children:
        if node.name != f"{_LABEL_NS}}}label":
            continue
        label = _label(node)
        identity = _identity(label)
        if identity in identities:
            raise SensitivityLabelRefusal("duplicate sensitivity label identity")
        identities.add(identity)
        records.append((node, label))
    return records


def _target(value: str) -> str:
    if not value or any(character in value for character in "\\%?#:"):
        raise SensitivityLabelRefusal("label relationship target is empty or unsupported")
    if value != value.strip() or ".." in value.split("/") or value.startswith("//"):
        raise SensitivityLabelRefusal("label relationship target is unsafe")
    target = posixpath.normpath(value.lstrip("/"))
    if target in {"", "."}:
        raise SensitivityLabelRefusal("label relationship target is empty")
    return target


def _inspect(package: Any) -> tuple[_Document, _Document, str | None, _Document | None]:
    names = package.namelist()
    if len(names) != len(set(names)):
        raise SensitivityLabelRefusal("duplicate OPC package entries are unsupported")
    rels = _parse(package.read("_rels/.rels"), "package relationships")
    types = _parse(package.read("[Content_Types].xml"), "package content types")
    _root(rels, _REL_NS, "Relationships")
    _root(types, _CT_NS, "Types")
    relationships = [node for node in rels.root.children if node.name == f"{_REL_NS}}}Relationship"]
    ids = [node.attributes.get("Id", "") for node in relationships]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise SensitivityLabelRefusal("package relationship ids are missing or ambiguous")
    matching = [node for node in relationships if node.attributes.get("Type") == _LABEL_REL]
    if len(matching) > 1:
        raise SensitivityLabelRefusal("multiple sensitivity label relationships are unsupported")
    if not matching:
        if _LABEL_PART in names:
            raise SensitivityLabelRefusal("orphaned sensitivity label part is unsupported")
        return rels, types, None, None
    rel = matching[0]
    if rel.attributes.get("TargetMode", "Internal") != "Internal":
        raise SensitivityLabelRefusal("external sensitivity label targets are unsupported")
    part = _target(rel.attributes.get("Target", ""))
    if part not in names:
        raise SensitivityLabelRefusal("sensitivity label relationship target is missing")
    overrides = [
        node.attributes.get("ContentType")
        for node in types.root.children
        if node.name == f"{_CT_NS}}}Override" and node.attributes.get("PartName") == f"/{part}"
    ]
    defaults = [
        node.attributes.get("ContentType")
        for node in types.root.children
        if node.name == f"{_CT_NS}}}Default"
        and node.attributes.get("Extension") == part.rsplit(".", 1)[-1]
    ]
    if len(overrides) > 1 or (not overrides and len(defaults) > 1):
        raise SensitivityLabelRefusal("ambiguous sensitivity label content type")
    declared = overrides or defaults
    # The specification uses application/xml; existing decks also use the
    # dedicated Office classification-label MIME type. Keep either unchanged.
    if len(declared) != 1 or declared[0] not in {
        "application/xml",
        "application/vnd.ms-office.classificationlabels+xml",
    }:
        raise SensitivityLabelRefusal("unsupported sensitivity label content type")
    document = _parse(package.read(part), "sensitivity label metadata")
    _labels(document)
    return rels, types, part, document


def _require_editable(package: Any, rels: _Document, types: _Document) -> None:
    if any(name.casefold().startswith("_xmlsignatures/") for name in package.namelist()):
        raise SensitivityLabelRefusal("signed packages cannot have label metadata edited")
    if any(
        "digital-signature" in node.attributes.get("Type", "") for node in rels.root.children
    ) or any(
        "digital-signature" in node.attributes.get("ContentType", "")
        for node in types.root.children
    ):
        raise SensitivityLabelRefusal("signed packages cannot have label metadata edited")
    for rel in rels.root.children:
        if rel.attributes.get("Type", "").endswith("/custom-properties"):
            if rel.attributes.get("TargetMode", "Internal") != "Internal":
                raise SensitivityLabelRefusal("external custom label metadata is unsupported")
            part = _target(rel.attributes.get("Target", ""))
            properties = _parse(package.read(part), "custom properties")
            if any(
                node.attributes.get("name", "").startswith("MSIP_Label_")
                for node in properties.root.children
            ):
                raise SensitivityLabelRefusal("legacy sensitivity labels must not be overwritten")


def _attributes(label: SensitivityLabel) -> dict[str, str | None]:
    return {
        "id": label.id,
        "enabled": "1" if label.enabled else "0",
        "method": label.method,
        "siteId": label.site_id,
        "contentBits": None if label.content_bits is None else str(label.content_bits),
        "removed": "1" if label.removed else "0",
    }


def _replace_attributes(document: _Document, node: _Node, values: dict[str, str | None]) -> bytes:
    pending = dict(values)

    def replace(match: re.Match[bytes]) -> bytes:
        name = match.group(2).decode("utf-8")
        if name not in pending:
            return match.group(0)
        value = pending.pop(name)
        if value is None:
            return b""
        if node.attributes.get(name) == value:
            return match.group(0)
        return match.group(1) + match.group(2) + match.group(3) + quoteattr(value).encode()

    tag = _ATTRIBUTE.sub(replace, document.source[node.start : node.tag_end])
    for name, value in pending.items():
        if value is not None:
            tag = _insert_attribute(tag, f" {name}={quoteattr(value)}".encode())
    return document.source[: node.start] + tag + document.source[node.tag_end :]


def _insert(document: _Document, element: bytes, before: _Node | None = None) -> bytes:
    root = document.root
    tag = document.source[root.start : root.tag_end]
    if tag.endswith(b"/>"):
        qname = tag[1:].split(None, 1)[0].rstrip(b"/>")
        return (
            document.source[: root.tag_end - 2]
            + b">"
            + element
            + b"</"
            + qname
            + b">"
            + document.source[root.tag_end :]
        )
    offset = root.close if before is None else before.start
    return document.source[:offset] + element + document.source[offset:]


def _element(name: str, namespace: str, attributes: dict[str, str | None]) -> bytes:
    fields = "".join(
        f" {key}={quoteattr(value)}" for key, value in attributes.items() if value is not None
    )
    return f"<{name} xmlns={quoteattr(namespace)}{fields}/>".encode()


def _validate_apply(label: Any) -> None:
    if not isinstance(label, SensitivityLabel):
        raise SensitivityLabelRefusal("apply requires a SensitivityLabel value")
    _identity(label)
    if not isinstance(label.method, str) or label.method not in {"Standard", "Privileged"}:
        raise SensitivityLabelRefusal("unsupported sensitivity label method")
    if type(label.enabled) is not bool or type(label.removed) is not bool:
        raise SensitivityLabelRefusal("enabled and removed must be bool values")
    if label.removed:
        raise SensitivityLabelRefusal("use remove to record label removal")
    if label.content_bits is not None and (
        type(label.content_bits) is not int or not 0 <= label.content_bits <= 7
    ):
        raise SensitivityLabelRefusal("unknown content markings and encryption are unsupported")


def _validate_mark(mark: Any) -> None:
    if not isinstance(mark, SensitivityContentMark):
        raise SensitivityLabelRefusal("marks require SensitivityContentMark values")
    if not isinstance(mark.kind, str) or mark.kind not in _MARK_BITS:
        raise SensitivityLabelRefusal("unknown content marking kind")
    try:
        xml_string(mark.text, "content mark text")
        xml_string(mark.font_name, "content mark font")
    except (TypeError, LifecycleRefusal) as exc:
        raise SensitivityLabelRefusal(str(exc)) from exc
    if not mark.text.strip() or not mark.font_name.strip():
        raise SensitivityLabelRefusal("content mark text and font must not be blank")
    for name in ("slide_index", "left", "top", "width", "height"):
        value = getattr(mark, name)
        if type(value) is not int or not 0 <= value <= 2147483647:
            raise SensitivityLabelRefusal(f"content mark {name} must be a nonnegative integer")
    if mark.width == 0 or mark.height == 0:
        raise SensitivityLabelRefusal("content mark dimensions must be positive")
    for name in ("font_size", "rotation"):
        value = getattr(mark, name)
        if type(value) not in {int, float} or (type(value) is float and not math.isfinite(value)):
            raise SensitivityLabelRefusal(f"content mark {name} must be finite")
    if not 1 <= mark.font_size <= 4000 or not -360 <= mark.rotation <= 360:
        raise SensitivityLabelRefusal("content mark font size or rotation is out of range")
    if not isinstance(mark.color, str) or re.fullmatch(r"[0-9a-fA-F]{6}", mark.color) is None:
        raise SensitivityLabelRefusal("content mark color must be six-digit RGB hex")


def _mark_bits(marks: tuple[SensitivityContentMark, ...]) -> int:
    bits = 0
    for mark in marks:
        bits |= _MARK_BITS[mark.kind]
    return bits


def _mark_shape(
    mark: SensitivityContentMark,
    identity: tuple[str, str],
    namespaces: tuple[str, str, str],
    shape_id: int,
) -> ET.Element:
    # Reuse the existing text-watermark shape contract, including explicit font,
    # color and geometry. Header/footer are equally ordinary text shapes.
    from .presentation import _watermark_shape, _WatermarkSpec

    spec = _WatermarkSpec(
        text=mark.text,
        image=None,
        slide_width=0,
        slide_height=0,
        font_size=mark.font_size,
        font_name=mark.font_name,
        bold=False,
        color=mark.color.upper(),
        opacity=100000,
        rotation=mark.rotation,
        box=(mark.left, mark.top, mark.width, mark.height),
        name=f"Wolf sensitivity {mark.kind}",
    )
    shape = _watermark_shape(
        spec, namespaces, shape_id, None, (mark.left, mark.top, mark.width, mark.height)
    )
    properties = shape.find(f"{{{namespaces[0]}}}nvSpPr/{{{namespaces[0]}}}cNvPr")
    properties.set(
        "descr",
        _MARK_NS
        + ":"
        + json.dumps(
            {"identity": identity, "mark": asdict(mark)}, sort_keys=True, separators=(",", ":")
        ),
    )
    return shape


def _walk(node: _Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _mark_plan(
    package: Any,
    parts: tuple[str, ...],
    identity: tuple[str, str],
    current: SensitivityLabel | None,
    requested: tuple[SensitivityContentMark, ...] | None,
) -> tuple[dict[str, bytes], tuple[SensitivityContentMark, ...]]:
    """Validate every preimage before a byte-local slide/metadata transaction."""
    if (
        current is not None
        and current.content_bits is not None
        and (not 0 <= current.content_bits <= 7)
    ):
        raise SensitivityLabelRefusal("unknown marking semantics or encrypted label is read-only")
    desired: dict[tuple[int, str], SensitivityContentMark] = {}
    for mark in requested or ():
        if mark.slide_index >= len(parts):
            raise SensitivityLabelRefusal("content mark slide index is out of range")
        key = (mark.slide_index, mark.kind)
        if key in desired:
            raise SensitivityLabelRefusal("duplicate content mark kind on a slide")
        desired[key] = mark
    if len(set(parts)) != len(parts):
        raise SensitivityLabelRefusal("ambiguous slide ownership for content marks")
    retained: list[SensitivityContentMark] = []
    plans = []
    for index, part in enumerate(parts):
        source = package.read(part)
        document = _parse(source, "content marking slide")
        root = ET.fromstring(source)
        p_ns = ooxml_namespace(root, P_NS)
        a_ns = ooxml_namespace(root, A_NS)
        r_ns = ooxml_namespace(root, R_NS)
        namespaces = p_ns, a_ns, r_ns
        trees = [node for node in _walk(document.root) if node.name == f"{p_ns}}}spTree"]
        if len(trees) != 1:
            raise SensitivityLabelRefusal("content marking slide has ambiguous shape tree")
        tree = trees[0]
        properties = list(root.iter(f"{{{p_ns}}}cNvPr"))
        ids = [node.get("id", "") for node in properties]
        if any(not value.isdecimal() for value in ids) or len(ids) != len(set(ids)):
            raise SensitivityLabelRefusal("content marking slide has ambiguous shape IDs")
        next_id = max((int(value) for value in ids), default=0) + 1
        owned = {}
        changes = []
        for node in _walk(tree):
            if node.name != f"{p_ns}}}cNvPr":
                continue
            description = node.attributes.get("descr", "")
            if not description.startswith(_MARK_NS + ":"):
                continue
            try:
                payload = json.loads(description[len(_MARK_NS) + 1 :])
                owner = tuple(payload["identity"])
                saved_mark = SensitivityContentMark(**payload["mark"])
                _validate_mark(saved_mark)
                if set(payload) != {"identity", "mark"} or len(owner) != 2:
                    raise ValueError("unknown ownership metadata")
                owner = (_guid(owner[0], "mark label id"), _guid(owner[1], "mark site id"))
            except (TypeError, ValueError, KeyError) as exc:
                raise SensitivityLabelRefusal(
                    "unknown content marking ownership semantics"
                ) from exc
            if owner != identity:
                continue
            shapes = [
                child
                for child in tree.children
                if child.name == f"{p_ns}}}sp" and node in tuple(_walk(child))
            ]
            if len(shapes) != 1:
                raise SensitivityLabelRefusal("content marking owner is not a top-level text shape")
            shape_node = shapes[0]
            shape_id = int(node.attributes["id"])
            actual = next(
                child
                for child in root.find(f"{{{p_ns}}}cSld/{{{p_ns}}}spTree")
                if child.tag == f"{{{p_ns}}}sp"
                and child.find(f"{{{p_ns}}}nvSpPr/{{{p_ns}}}cNvPr") is not None
                and child.find(f"{{{p_ns}}}nvSpPr/{{{p_ns}}}cNvPr").get("id") == str(shape_id)
            )
            expected = _mark_shape(saved_mark, identity, namespaces, shape_id)
            if _signature(actual) != _signature(expected):
                raise SensitivityLabelRefusal(
                    "owned content mark changed outside the label workflow"
                )
            mark = SensitivityContentMark(**{**asdict(saved_mark), "slide_index": index})
            if mark.kind in owned:
                raise SensitivityLabelRefusal("duplicate owned content marking kind on a slide")
            owned[mark.kind] = (mark, shape_id, shape_node)
            retained.append(mark)
        if requested is None:
            continue
        for kind, (_mark, shape_id, node) in owned.items():
            mark = desired.get((index, kind))
            replacement = (
                b""
                if mark is None
                else ET.tostring(
                    _mark_shape(mark, identity, namespaces, shape_id), encoding="utf-8"
                )
            )
            changes.append((node.start, node.end, replacement))
        additions = []
        for (slide_index, kind), mark in desired.items():
            if slide_index == index and kind not in owned:
                additions.append(
                    ET.tostring(_mark_shape(mark, identity, namespaces, next_id), encoding="utf-8")
                )
                next_id += 1
        if additions:
            extension = next(
                (node for node in tree.children if node.name == f"{p_ns}}}extLst"), None
            )
            offset = tree.close if extension is None else extension.start
            changes.append((offset, offset, b"".join(additions)))
        plans.append((part, source, changes))
    if _mark_bits(tuple(retained)) != (
        0 if current is None or current.removed else current.content_bits or 0
    ):
        raise SensitivityLabelRefusal("unknown or missing content marking ownership")
    replacements = {}
    for part, source, changes in plans:
        updated = source
        for start, end, replacement in sorted(changes, reverse=True):
            updated = updated[:start] + replacement + updated[end:]
        if updated != source:
            replacements[part] = updated
    return replacements, tuple(retained)


class SensitivityLabels:
    """Saved-package label metadata access for a real ``Presentation``.

    ``read()`` returns a tuple, excluding removed records. ``apply(label)``
    upserts only the (id, site_id) pair, without disabling other labels or
    resolving policy conflicts. ``remove(id, site_id)`` records a disabled
    tombstone with empty method and no contentBits; missing labels are a no-op.
    Both edits return None. Explicit ``marks=`` replaces the owned marking set
    atomically with label metadata; omitting it retains verified owned marks.
    ``read_marks(id, site_id)`` returns their persisted specifications.
    Unknown marking semantics, encryption, signed packages, legacy labels,
    ambiguous metadata, disposed presentations and pending edits refuse before
    writing. Reads of label metadata alone make no protection-policy claim.
    """

    def __init__(self, presentation: Any) -> None:
        from .presentation import Presentation

        if not isinstance(presentation, Presentation):
            raise SensitivityLabelRefusal("target must be a Presentation")
        self._presentation = presentation

    def read(self) -> tuple[SensitivityLabel, ...]:
        presentation = self._presentation
        with presentation._mutation_lock:
            if presentation._disposed:
                raise SensitivityLabelRefusal("presentation is disposed")
            try:
                with open_package_source(presentation._source_path) as package:
                    _, _, _, document = _inspect(package)
                    if document is None:
                        return ()
                    return tuple(label for _, label in _labels(document) if not label.removed)
            except (KeyError, OSError, zipfile.BadZipFile) as exc:
                raise SensitivityLabelRefusal(
                    "saved sensitivity label metadata is unavailable"
                ) from exc

    def apply(
        self,
        label: SensitivityLabel,
        *,
        marks: tuple[SensitivityContentMark, ...] | None = None,
    ) -> None:
        """Upsert a label and optional explicit marks; save, then reacquire handles."""
        _validate_apply(label)
        if marks is not None:
            if not isinstance(marks, (tuple, list)):
                raise SensitivityLabelRefusal("marks must be a sequence of SensitivityContentMark")
            marks = tuple(marks)
            for mark in marks:
                _validate_mark(mark)
            if _mark_bits(marks) != (label.content_bits or 0):
                raise SensitivityLabelRefusal("content_bits must match explicit content marks")
            if marks and not label.enabled:
                raise SensitivityLabelRefusal("content marks require an enabled label")
        self._edit(_identity(label), label, marks)

    def read_marks(self, id: str, site_id: str) -> tuple[SensitivityContentMark, ...]:
        """Read verified Wolf-authored marks; unknown marking ownership refuses."""
        identity = (_guid(id, "label id"), _guid(site_id, "label site_id"))
        presentation = self._presentation
        with presentation._mutation_lock:
            if presentation._disposed:
                raise SensitivityLabelRefusal("presentation is disposed")
            with open_package_source(presentation._source_path) as package:
                _, _, _, document = _inspect(package)
                records = [] if document is None else _labels(document)
                current = next(
                    (value for _, value in records if _identity(value) == identity), None
                )
                _, marks = _mark_plan(package, self._slide_parts(), identity, current, None)
                return marks

    def _slide_parts(self) -> tuple[str, ...]:
        return tuple(slide.partname.lstrip("/") for slide in self._presentation.slides)

    def remove(self, id: str, site_id: str) -> None:
        """Record removal without deleting unknown metadata or label history."""
        self._edit((_guid(id, "label id"), _guid(site_id, "label site_id")), None)

    def _edit(
        self,
        identity: tuple[str, str],
        label: SensitivityLabel | None,
        marks: tuple[SensitivityContentMark, ...] | None = None,
    ) -> None:
        presentation = self._presentation
        operation = "changing sensitivity label metadata"

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            try:
                rels, types, part, document = _inspect(package)
                _require_editable(package, rels, types)
                records = [] if document is None else _labels(document)
                existing = next(
                    ((node, value) for node, value in records if _identity(value) == identity),
                    None,
                )
                current = None if existing is None else existing[1]
                mark_replacements, retained = _mark_plan(
                    package,
                    self._slide_parts(),
                    identity,
                    current,
                    () if label is None else marks,
                )
                if label is not None:
                    effective_marks = retained if marks is None else marks
                    if _mark_bits(effective_marks) != (label.content_bits or 0):
                        raise SensitivityLabelRefusal(
                            "content_bits must match saved or explicit content marks"
                        )
                    if effective_marks and not label.enabled:
                        raise SensitivityLabelRefusal("content marks require an enabled label")
                if existing is not None:
                    node, current = existing
                    if current.method not in {"Standard", "Privileged", ""}:
                        raise SensitivityLabelRefusal("unknown existing label policy semantics")
                    if label is None:
                        values = {
                            "enabled": "0",
                            "removed": "1",
                            "method": "",
                            "contentBits": None,
                        }
                    else:
                        values = _attributes(label)
                    updated = _replace_attributes(document, node, values)
                    if updated != document.source:
                        mark_replacements[part] = updated
                    return mark_replacements, set(), None
                if label is None:
                    return mark_replacements, set(), None
                element = _element("label", _LABEL_NS, _attributes(label))
                if document is not None:
                    extension = next(
                        (
                            node
                            for node in document.root.children
                            if node.name == f"{_LABEL_NS}}}extLst"
                        ),
                        None,
                    )
                    mark_replacements[part] = _insert(document, element, extension)
                    return mark_replacements, set(), None
                relationship_ids = {node.attributes.get("Id") for node in rels.root.children}
                index = 1
                while f"rId{index}" in relationship_ids:
                    index += 1
                if any(
                    node.attributes.get("PartName") == f"/{_LABEL_PART}"
                    for node in types.root.children
                ):
                    raise SensitivityLabelRefusal("orphaned label content type declaration")
                replacements = {
                    _LABEL_PART: (
                        f'<labelList xmlns="{_LABEL_NS}">'.encode() + element + b"</labelList>"
                    ),
                    "_rels/.rels": _insert(
                        rels,
                        _element(
                            "Relationship",
                            _REL_NS,
                            {"Id": f"rId{index}", "Type": _LABEL_REL, "Target": _LABEL_PART},
                        ),
                    ),
                    "[Content_Types].xml": _insert(
                        types,
                        _element(
                            "Override",
                            _CT_NS,
                            {"PartName": f"/{_LABEL_PART}", "ContentType": "application/xml"},
                        ),
                    ),
                }
                replacements.update(mark_replacements)
                return replacements, set(), None
            except (KeyError, OSError, zipfile.BadZipFile) as exc:
                raise SensitivityLabelRefusal(
                    "saved label package metadata is unavailable"
                ) from exc

        with presentation._mutation_lock:
            try:
                presentation._require_saved_package(operation)
            except (ValueError, RuntimeError) as exc:
                raise SensitivityLabelRefusal(str(exc)) from exc
            presentation._rewrite_package(operation, plan)


__all__ = [
    "SensitivityLabel",
    "SensitivityContentMark",
    "SensitivityLabelRefusal",
    "SensitivityLabels",
]
