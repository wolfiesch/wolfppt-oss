"""Signature-line metadata, independent of OPC digital signing."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any
from uuid import UUID
from xml.etree import ElementTree as ET

from .package_parts import open_package_source, rels_part_for_package_part, resolve_package_target
from .presentation_tags import LifecycleRefusal, parse_xml, serialize_xml
from .xml_helpers import A_NS, P_NS, find_ooxml, ooxml_namespace

O_NS = "urn:schemas-microsoft-com:office:office"
V_NS = "urn:schemas-microsoft-com:vml"
A15_NS = "http://schemas.microsoft.com/office/drawing/2012/main"
SIGNATURE_EXTENSION_URI = "{F385189D-CB6C-4498-A905-10932F83BE7A}"
VML_TAG = f"{{{O_NS}}}signatureline"
A15_TAG = f"{{{A15_NS}}}signatureLine"
_FIELDS = (
    "id",
    "provId",
    "isSignatureLine",
    "suggestedSigner",
    "suggestedSigner2",
    "suggestedSignerEmail",
    "signingInstructions",
    "signingInstructionsSet",
    "showSignDate",
    "allowComments",
    "sigProvUrl",
    "addlXml",
)
_VML_FIELDS = (
    "id",
    "provid",
    "issignatureline",
    "suggestedsigner",
    "suggestedsigner2",
    "suggestedsigneremail",
    "signinginstructions",
    "signinginstructionsset",
    "showsigndate",
    "allowcomments",
    "sigprovurl",
    "addlxml",
)
_QUALIFIED = {
    "suggestedsigner",
    "suggestedsigner2",
    "suggestedsigneremail",
    "sigprovurl",
    "addlxml",
}
_BOOLS = {"isSignatureLine", "signingInstructionsSet", "showSignDate", "allowComments"}
_TRUE = {"1", "true", "t"}
_FALSE = {"0", "false", "f"}


class SignatureLineError(ValueError):
    """Atomic signature-line refusal; ``code`` identifies the failed precondition."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _key(name: str, kind: str) -> str:
    if kind == "a15":
        return name
    name = _VML_FIELDS[_FIELDS.index(name)]
    return f"{{{O_NS}}}{name}" if name in _QUALIFIED else name


def _diagnose(element: ET.Element, kind: str) -> tuple[str, ...]:
    issues = []
    for name in ("id", "provId"):
        value = element.get(_key(name, kind))
        if value is None and name == "provId":
            continue
        try:
            UUID(value or "")
        except ValueError:
            issues.append(f"invalid_{name}")
    for name in _BOOLS:
        value = element.get(_key(name, kind))
        allowed = _TRUE | _FALSE if kind == "vml" else {"1", "0", "true", "false"}
        if value is not None and value not in allowed:
            issues.append(f"invalid_{name}")
    return tuple(issues)


def _attributes(element: ET.Element, kind: str) -> dict[str, str]:
    return {
        name: element.attrib[key] for name in _FIELDS if (key := _key(name, kind)) in element.attrib
    }


def _patch(element: ET.Element, kind: str, attributes: dict[str, Any]) -> None:
    for name, value in attributes.items():
        if name not in _FIELDS:
            raise SignatureLineError("unknown_attribute", name)
        key = _key(name, kind)
        if value is None:
            element.attrib.pop(key, None)
        elif isinstance(value, bool) and name in _BOOLS:
            element.set(key, "1" if value else "0")
        elif isinstance(value, str) and all(
            c in "\t\n\r"
            or 0x20 <= ord(c) <= 0xD7FF
            or 0xE000 <= ord(c) <= 0xFFFD
            or 0x10000 <= ord(c) <= 0x10FFFF
            for c in value
        ):
            element.set(key, value)
        else:
            raise SignatureLineError("invalid_attribute", name)
    issues = _diagnose(element, kind)
    if issues:
        raise SignatureLineError("invalid_metadata", ", ".join(issues))


def _roots(package: Any, slide_part: str) -> Iterator[tuple[str, ET.Element]]:
    yield slide_part, parse_xml(package.read(slide_part), read_only=True)
    rels = rels_part_for_package_part(slide_part)
    if rels not in package.namelist():
        return
    seen = set()
    for rel in ET.fromstring(package.read(rels)):
        if not rel.get("Type", "").endswith("/vmlDrawing"):
            continue
        if rel.get("TargetMode") == "External":
            raise SignatureLineError("external_vml", "external VML targets are not followed")
        part = resolve_package_target(slide_part, rel.get("Target", ""))
        if part not in seen:
            seen.add(part)
            if part not in package.namelist():
                raise SignatureLineError("missing_vml", part)
            yield part, parse_xml(package.read(part), read_only=True)


def _hosts(root: ET.Element, kind: str) -> Iterator[tuple[str, ET.Element]]:
    if kind == "vml":
        for host in root.iter(f"{{{V_NS}}}shape"):
            yield host.get("id", ""), host
    else:
        for host in root.iter(f"{{{ooxml_namespace(root, P_NS)}}}pic"):
            props = find_ooxml(host, f"{{{P_NS}}}nvPicPr/{{{P_NS}}}cNvPr")
            if props is not None:
                yield props.get("id", ""), host


class SignatureLine:
    """Live handle addressed by part, host ID and occurrence, including malformed IDs."""

    def __init__(
        self, collection: SignatureLines, part: str, kind: str, host_id: str, index: int
    ) -> None:
        self._collection = collection
        self.partname = part
        self.kind = kind
        self.host_id = host_id
        self._index = index

    def _locate(self, root: ET.Element) -> ET.Element:
        for host_id, host in _hosts(root, self.kind):
            if host_id == self.host_id:
                lines = list(host.iter(A15_TAG if self.kind == "a15" else VML_TAG))
                if self._index < len(lines):
                    return lines[self._index]
        raise SignatureLineError("stale_line", "signature-line host or occurrence no longer exists")

    @property
    def attributes(self) -> dict[str, str]:
        with open_package_source(self._collection._presentation.path) as package:
            return _attributes(self._locate(ET.fromstring(package.read(self.partname))), self.kind)

    def diagnose(self) -> tuple[str, ...]:
        """Return invalid UUID/boolean field codes without modifying the package."""
        with open_package_source(self._collection._presentation.path) as package:
            return _diagnose(self._locate(ET.fromstring(package.read(self.partname))), self.kind)

    def update(self, **attributes: Any) -> None:
        """Patch canonical a15-style attributes; pass None to remove an optional field."""

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            root = parse_xml(package.read(self.partname))
            _patch(self._locate(root), self.kind, attributes)
            return {self.partname: serialize_xml(root)}, set(), None

        self._collection._rewrite(plan)


class SignatureLines(Sequence[SignatureLine]):
    """DrawingML picture lines followed by lines in slide-related VML parts.

    Mutations require a saved presentation and rebase the presentation facade.
    Reacquire slide/shape handles after a mutation, as with replace_text.
    """

    def __init__(self, slide: Any) -> None:
        self._presentation = slide._presentation
        self._part = str(slide.partname).lstrip("/")
        if not self._part or getattr(slide, "_deleted", False):
            raise SignatureLineError("unsaved_slide", "save the slide before signature-line access")

    def _items(self) -> list[SignatureLine]:
        items = []
        with open_package_source(self._presentation.path) as package:
            for part, root in _roots(package, self._part):
                kind = "a15" if part == self._part else "vml"
                for host_id, host in _hosts(root, kind):
                    for index, _ in enumerate(host.iter(A15_TAG if kind == "a15" else VML_TAG)):
                        items.append(SignatureLine(self, part, kind, host_id, index))
        return items

    def __iter__(self) -> Iterator[SignatureLine]:
        return iter(self._items())

    def __len__(self) -> int:
        return len(self._items())

    def __getitem__(self, index: int | slice) -> SignatureLine | list[SignatureLine]:
        return self._items()[index]

    def for_picture(self, picture: Any) -> SignatureLine | None:
        lines = [
            line for line in self if line.kind == "a15" and line.host_id == str(picture.shape_id)
        ]
        if len(lines) > 1:
            raise SignatureLineError("ambiguous_line", "picture has multiple signature lines")
        return lines[0] if lines else None

    def _rewrite(self, plan: Any) -> Any:
        try:
            return self._presentation._rewrite_package("signature-line mutation", plan)
        except SignatureLineError:
            raise
        except LifecycleRefusal as exc:
            raise SignatureLineError("unsupported_xml", str(exc)) from exc
        except ValueError as exc:
            raise SignatureLineError("pending_edits", str(exc)) from exc

    def add(
        self, *, picture: Any = None, vml_shape_id: str | None = None, **attributes: Any
    ) -> SignatureLine:
        """Insert metadata on a saved picture or an existing slide-related VML shape."""
        if (picture is None) == (vml_shape_id is None):
            raise SignatureLineError("invalid_host", "choose picture or vml_shape_id")
        if picture is not None and (
            picture._slide._presentation is not self._presentation
            or str(picture._slide.partname).lstrip("/") != self._part
            or not picture.has_picture
            or picture._payload.get("_pending_shape")
            or picture._payload.get("_deleted")
        ):
            raise SignatureLineError("invalid_host", "picture must be saved on this slide")
        kind = "a15" if picture is not None else "vml"
        host_id = str(picture.shape_id) if picture is not None else str(vml_shape_id)
        element = ET.Element(A15_TAG if kind == "a15" else VML_TAG)
        _patch(element, kind, {"isSignatureLine": True, **attributes})

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], str]:
            candidates = [
                (part, root, host)
                for part, root in _roots(package, self._part)
                if (part == self._part) == (kind == "a15")
                for candidate_id, host in _hosts(root, kind)
                if candidate_id == host_id
            ]
            if len(candidates) != 1:
                raise SignatureLineError(
                    "invalid_host", "expected one existing signature-line host"
                )
            part, root, host = candidates[0]
            if list(host.iter(element.tag)):
                raise SignatureLineError("duplicate_line", "host already has a signature line")
            if kind == "vml":
                host.append(element)
            else:
                parent = find_ooxml(host, f"{{{P_NS}}}nvPicPr/{{{P_NS}}}cNvPicPr")
                if parent is None:
                    raise SignatureLineError("invalid_host", "missing cNvPicPr")
                a = ooxml_namespace(root, A_NS)
                extensions = parent.find(f"{{{a}}}extLst")
                if extensions is None:
                    extensions = ET.SubElement(parent, f"{{{a}}}extLst")
                extension = ET.SubElement(extensions, f"{{{a}}}ext", uri=SIGNATURE_EXTENSION_URI)
                extension.append(element)
            return {part: serialize_xml(root)}, set(), part

        part = self._rewrite(plan)
        return SignatureLine(self, part, kind, host_id, 0)
