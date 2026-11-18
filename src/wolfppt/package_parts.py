"""Package part metadata, atomic relocation, and XML element facades."""

from __future__ import annotations

import math
import posixpath
import re
import struct
import zipfile
from collections.abc import Iterator, Sequence
from copy import copy, deepcopy
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from xml.etree import ElementTree as ET

from .package_copy_io import (
    _copy_raw_zip_entry,
    _raw_zip_entry_spans,
    staged_package_output,
)
from .package_read_scope import BorrowedPackage, borrow_shared_package
from .vba_compound_file import (
    _CFB_ENDOFCHAIN,
    _CFB_FREESECT,
    _CFB_MAGIC,
    _CFB_MINI_CUTOFF,
    _CFB_MINI_SECTOR_SIZE,
    _CFB_NOSTREAM,
    _CFB_SECTOR_SIZE,
    _CompoundDirectoryEntry,
    _CompoundFileWriter,
)
from .vba_module_records import encode_text

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_PRECOMPRESSED_EXTENSIONS = {
    ".bin",
    ".gif",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp4",
    ".png",
    ".xlsb",
    ".xlsm",
    ".xlsx",
    ".zip",
}

_XML_NAMESPACES = {
    "a": A_NS,
    "c": C_NS,
    "cp": CP_NS,
    "dc": DC_NS,
    "dcterms": DCTERMS_NS,
    "p": P_NS,
    "r": R_NS,
    "xsi": XSI_NS,
}

WE_NS = "http://schemas.microsoft.com/office/webextensions/webextension/2010/11"
WETP_NS = "http://schemas.microsoft.com/office/webextensions/taskpanes/2010/11"

ET.register_namespace("we", WE_NS)
ET.register_namespace("wetp", WETP_NS)


class InMemoryPackageSource:
    """Owned, read-only PPTX bytes for bounded no-disk presentation inspection."""

    def __init__(self, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise TypeError("in-memory package payload must be bytes")
        with zipfile.ZipFile(BytesIO(payload)) as package:
            package.infolist()
        self._payload: bytes | None = payload

    @property
    def disposed(self) -> bool:
        return self._payload is None

    def open(self) -> zipfile.ZipFile:
        if self._payload is None:
            raise RuntimeError("in-memory presentation source is disposed")
        return zipfile.ZipFile(BytesIO(self._payload))

    def read_bytes(self) -> bytes:
        if self._payload is None:
            raise RuntimeError("in-memory presentation source is disposed")
        return self._payload

    def dispose(self) -> None:
        self._payload = None


def open_package_source(
    source: Path | InMemoryPackageSource,
) -> zipfile.ZipFile | BorrowedPackage:
    """Open a path-backed or owned in-memory package without materializing bytes.

    Inside :func:`wolfppt.package_read_scope.shared_package_reads` the scope
    owns the handle and leaving the ``with`` block keeps it open.
    """

    borrowed = borrow_shared_package(source, _open_package_source)
    return _open_package_source(source) if borrowed is None else borrowed


def _open_package_source(source: Path | InMemoryPackageSource) -> zipfile.ZipFile:
    if isinstance(source, InMemoryPackageSource):
        return source.open()
    return zipfile.ZipFile(source)


class PackagePartRenameError(ValueError):
    """Raised when an OPC part cannot be relocated safely."""


class PackagePart:
    """python-pptx-style package part metadata and atomic OPC relocation."""

    def __init__(
        self,
        presentation: Any,
        partname: str,
        name: str | None = "",
    ) -> None:
        self._presentation = presentation
        self._partname = normalize_package_partname(partname)
        self._name = name

    @property
    def partname(self) -> str:
        return self._partname

    @property
    def content_type(self) -> str:
        return package_part_content_type(
            self._presentation.path,
            self._partname,
        )

    @property
    def blob(self) -> bytes:
        with zipfile.ZipFile(self._presentation.path) as package:
            return package.read(self._partname.lstrip("/"))

    @property
    def part(self) -> PackagePart:
        return self

    @property
    def package(self) -> Any:
        return self._presentation

    def drop_rel(self, rId: str) -> None:
        self._presentation._drop_part_rel(self._partname, rId)

    def rename(self, partname: str) -> None:
        """Relocate this part in the saved package; save pending edits first.

        Incoming targets, the content type and outgoing relationships move
        together. The caller's source file is unchanged until an explicit save.
        """
        with self._presentation._mutation_lock:
            destination = _rename_partname(partname)
            source = _rename_partname(self._partname)

            def plan(package: zipfile.ZipFile) -> tuple[dict[str, bytes], set[str], None]:
                return (
                    _part_rename_mutation(package, source, destination),
                    {
                        source,
                        rels_part_for_package_part(source),
                    }
                    - {destination, rels_part_for_package_part(destination)},
                    None,
                )

            self._presentation._rewrite_package("renaming a package part", plan)
            self._partname = f"/{destination}"

    @property
    def name(self) -> str:
        if self._name is None:
            raise AttributeError("package part does not expose a name")
        return self._name


def _rename_partname(value: str) -> str:
    # Require an unambiguous canonical OPC URI, rather than normalizing unsafe
    # names into a different destination. Percent-encoded names stay opaque.
    from urllib.parse import quote, unquote

    if not isinstance(value, str):
        raise TypeError("package part name must be str")
    name = value.removeprefix("/")
    decoded = unquote(name)
    if (
        not name
        or any(c in name for c in "\\?#:")
        or quote(name, safe="/!$&'()*+,;=@%._~-") != name
        or re.search(r"%(?![0-9a-fA-F]{2})", name) is not None
        or any(c.isspace() or ord(c) < 32 for c in name)
        or any(segment in {"", ".", ".."} or segment.endswith(".") for segment in name.split("/"))
        or decoded.count("/") != name.count("/")
        or "\\" in decoded
        or any(segment in {".", ".."} for segment in decoded.split("/"))
        or name == "[Content_Types].xml"
        or "_rels" in name.lower().split("/")
        or name.lower().endswith(".rels")
    ):
        raise PackagePartRenameError(f"not a relocatable OPC data-part name: {value!r}")
    return name


def _part_rename_mutation(
    package: zipfile.ZipFile, source: str, destination: str
) -> dict[str, bytes]:
    from .package_closure import _relationship_target
    from .presentation_package_validation import _relationship_owner

    names = package.namelist()
    if len(names) != len(set(names)):
        raise PackagePartRenameError("cannot rename in a package with duplicate ZIP members")
    if source not in names:
        raise PackagePartRenameError(f"source package part is missing: {source}")
    source_rels = rels_part_for_package_part(source)
    destination_rels = rels_part_for_package_part(destination)
    reserved = {name.casefold() for name in names if name not in {source, source_rels}}
    if destination.casefold() in reserved or destination_rels.casefold() in reserved:
        raise PackagePartRenameError(f"destination package part already exists: {destination}")
    if source == destination:
        return {}

    replacements = {destination: package.read(source)}
    try:
        types = ET.fromstring(package.read("[Content_Types].xml"))
        overrides = types.findall(f"{{{CONTENT_TYPES_NS}}}Override")
        content_type = next(
            (node.get("ContentType") for node in overrides if node.get("PartName") == f"/{source}"),
            None,
        )
        if content_type is None:
            extension = source.rsplit(".", 1)[-1].lower()
            content_type = next(
                (
                    node.get("ContentType")
                    for node in types.findall(f"{{{CONTENT_TYPES_NS}}}Default")
                    if node.get("Extension", "").lower() == extension
                ),
                None,
            )
        if not content_type:
            raise PackagePartRenameError(f"source package part has no content type: {source}")
        # A destination override also preserves a default-derived content type
        # when the destination uses a different extension.
        for node in overrides:
            if node.get("PartName") in {f"/{source}", f"/{destination}"}:
                types.remove(node)
        _set_content_type_override(types, f"/{destination}", content_type)
        for node in overrides:
            if node.get("PartName") == f"/{source_rels}":
                node.set("PartName", f"/{destination_rels}")
        replacements["[Content_Types].xml"] = _content_types_xml(types)

        for name in names:
            owner = _relationship_owner(name)
            if owner is None:
                continue
            root = ET.fromstring(package.read(name))
            new_owner = destination if owner == source else owner
            changed = owner == source
            for relation in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
                if relation.get("TargetMode", "Internal") == "External":
                    continue
                target = _relationship_target(owner, relation)
                if target != source and owner != source:
                    continue
                relocated = destination if target == source else target
                raw_target = relation.get("Target", "")
                fragment = raw_target.partition("#")[2]
                rewritten = (
                    f"/{relocated}"
                    if raw_target.startswith("/")
                    else _relative_package_target(new_owner, relocated)
                )
                relation.set("Target", f"{rewritten}#{fragment}" if fragment else rewritten)
                changed = True
            if changed:
                replacements[destination_rels if owner == source else name] = _xml_bytes(root)
    except (ET.ParseError, KeyError, ValueError) as exc:
        if isinstance(exc, PackagePartRenameError):
            raise
        raise PackagePartRenameError(f"cannot relocate package graph: {exc}") from exc
    return replacements


class XmlElementProxy:
    """Read-only XML element facade for python-pptx-style inspection."""

    def __init__(self, element: ET.Element) -> None:
        self._element = deepcopy(element)

    @property
    def tag(self) -> str:
        return self._element.tag

    @property
    def attrib(self) -> dict[str, str]:
        return dict(self._element.attrib)

    @property
    def text(self) -> str | None:
        return self._element.text

    @property
    def xml(self) -> str:
        return ET.tostring(self._element, encoding="unicode")

    def get(self, key: str, default: Any = None) -> Any:
        return self._element.attrib.get(key, default)

    def find(
        self,
        path: str,
        namespaces: dict[str, str] | None = None,
    ) -> XmlElementProxy | None:
        found = self._element.find(path, namespaces or _XML_NAMESPACES)
        return None if found is None else XmlElementProxy(found)

    def findall(
        self,
        path: str,
        namespaces: dict[str, str] | None = None,
    ) -> list[XmlElementProxy]:
        return [
            XmlElementProxy(element)
            for element in self._element.findall(path, namespaces or _XML_NAMESPACES)
        ]

    def xpath(self, path: str) -> list[XmlElementProxy]:
        return self.findall(path, _XML_NAMESPACES)

    def __iter__(self) -> Iterator[XmlElementProxy]:
        for child in self._element:
            yield XmlElementProxy(child)

    def __getitem__(
        self,
        index: int | slice,
    ) -> XmlElementProxy | list[XmlElementProxy]:
        if isinstance(index, slice):
            return [XmlElementProxy(child) for child in self._element[index]]
        return XmlElementProxy(self._element[index])

    def __len__(self) -> int:
        return len(self._element)

    def __repr__(self) -> str:
        return f"<XmlElementProxy tag={self.tag!r} children={len(self)}>"


class PresentationAttributeError(ValueError):
    """Refuse an invalid or unsafe presentation-root attribute edit atomically."""


class PresentationElementProxy(XmlElementProxy):
    """Live presentation root with validated, package-backed attribute edits.

    Children and all other ``XmlElementProxy`` instances remain read-only.
    Like package-part relocation, mutation requires saving queued edits first.
    """

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation

    @property
    def _element(self) -> ET.Element:
        owner = self._presentation
        with owner._mutation_lock:
            if owner._disposed:
                raise RuntimeError("presentation is disposed")
            return package_xml_element(owner._source_path, owner.part.partname)._element

    def set(self, key: str, value: str) -> None:
        """Set one root attribute, leaving the caller's input package untouched."""
        from .package_conformance import _ATTRIBUTE, _insert_attribute
        from .presentation_save_state import _element_spans, _tag_end
        from .xml_helpers import STRICT_P_NS, percentage_value

        if not isinstance(key, str) or not isinstance(value, str):
            raise PresentationAttributeError("presentation attribute name and value must be str")
        booleans = {
            "rtl",
            "saveSubsetFonts",
            "embedTrueTypeFonts",
            "autoCompressPictures",
            "removePersonalInfoOnSave",
            "strictFirstAndLastChars",
            "compatMode",
            "showSpecialPlsOnTitleSld",
        }
        if key in booleans:
            valid = value in {"0", "1", "false", "true"}
        elif key in {"firstSlideNum", "bookmarkIdSeed"}:
            minimum = -(2**31) if key == "firstSlideNum" else 1
            digits = value.lstrip("+-").lstrip("0") or "0"
            valid = (
                re.fullmatch(r"[+-]?[0-9]+", value) is not None
                and len(digits) <= 10
                and minimum <= int(("-" if value.startswith("-") else "") + digits) <= 2**31 - 1
            )
        elif key == "conformance":
            valid = value in {"strict", "transitional"}
        elif key == "serverZoom":
            valid = re.fullmatch(r"[+-]?[0-9]+|-?[0-9]+(?:\.[0-9]+)?%", value) is not None
        else:
            raise PresentationAttributeError(f"unsupported presentation attribute: {key!r}")
        if not valid:
            raise PresentationAttributeError(f"invalid {key} value: {value!r}")

        owner = self._presentation
        with owner._mutation_lock:
            try:
                owner._require_saved_package("editing presentation attributes")
            except ValueError as exc:
                raise PresentationAttributeError(str(exc)) from exc
            part = owner.part.partname.lstrip("/")

            def plan(package: zipfile.ZipFile) -> tuple[dict[str, bytes], set[str], None]:
                source = package.read(part)
                root = ET.fromstring(source)
                if root.tag not in {f"{{{P_NS}}}presentation", f"{{{STRICT_P_NS}}}presentation"}:
                    raise PresentationAttributeError("unexpected presentation root")
                strict = root.tag == f"{{{STRICT_P_NS}}}presentation"
                if key == "conformance" and value != ("strict" if strict else "transitional"):
                    raise PresentationAttributeError(
                        "conformance must match package namespaces; use save(conformance=...)"
                    )
                if key == "serverZoom":
                    try:
                        percentage_value(root, value)
                        if not value.endswith("%") and not -(2**31) <= int(value) <= 2**31 - 1:
                            raise ValueError("integer percentage exceeds signed 32-bit range")
                    except (ValueError, OverflowError) as exc:
                        raise PresentationAttributeError(
                            f"invalid serverZoom value: {value!r}"
                        ) from exc
                if root.get(key) == value:
                    return {}, set(), None
                # Splice only the root opening tag, preserving extension markup,
                # QName-valued namespace bindings, comments and all child bytes.
                if b"\x00" in source:
                    raise PresentationAttributeError("attribute editing requires UTF-8 XML")
                start = _element_spans(source)[0]["start"]
                end = _tag_end(source, start)
                opening = source[start:end]
                match = next(
                    (
                        match
                        for match in _ATTRIBUTE.finditer(opening)
                        if match.group(2) == key.encode()
                    ),
                    None,
                )
                if match is None:
                    opening = _insert_attribute(opening, f' {key}="{value}"'.encode())
                else:
                    opening = opening[: match.start(5)] + value.encode() + opening[match.end(5) :]
                replacement = source[:start] + opening + source[end:]
                return {part: replacement}, set(), None

            owner._rewrite_package("editing presentation attributes", plan)


def normalize_package_partname(partname: str) -> str:
    part = str(partname).strip()
    if not part:
        raise AttributeError("package part is unavailable")
    return f"/{part.lstrip('/')}"


def resolve_package_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def rels_part_for_package_part(part: str) -> str:
    return posixpath.join(posixpath.dirname(part), "_rels", f"{posixpath.basename(part)}.rels")


def package_xml_element(path: Path | InMemoryPackageSource, partname: str) -> XmlElementProxy:
    normalized = normalize_package_partname(partname).lstrip("/")
    try:
        with open_package_source(path) as package:
            return XmlElementProxy(ET.fromstring(package.read(normalized)))
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ) as exc:
        raise AttributeError("package XML element is unavailable") from exc


def package_part_content_type(path: Path | InMemoryPackageSource, partname: str) -> str:
    normalized = normalize_package_partname(partname)
    try:
        with open_package_source(path) as package:
            root = ET.fromstring(package.read("[Content_Types].xml"))
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return ""
    for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == normalized:
            return override.attrib.get("ContentType", "")
    extension = normalized.rsplit(".", 1)[-1].lower()
    for default in root.findall(f"{{{CONTENT_TYPES_NS}}}Default"):
        if default.attrib.get("Extension", "").lower() == extension:
            return default.attrib.get("ContentType", "")
    return ""


def copy_package_with_replacements(
    input_path: Path,
    output_path: Path,
    replacements: dict[str, bytes],
    removals: set[str] | None = None,
) -> None:
    """Copy a package, atomically publishing filesystem output even in place."""
    with (
        staged_package_output(output_path) as staged,
        zipfile.ZipFile(input_path) as source,
    ):
        copy_open_package_with_replacements(source, staged, replacements, removals)


def copy_open_package_with_replacements(
    source: zipfile.ZipFile,
    output_path: Path | BinaryIO,
    replacements: dict[str, bytes],
    removals: set[str] | None = None,
) -> None:
    """Copy atomically to paths; preserve member metadata, date new parts at 1980."""
    if isinstance(output_path, Path):
        with staged_package_output(output_path) as staged:
            copy_open_package_with_replacements(source, staged, replacements, removals)
        return
    removed = removals or set()
    raw_spans = _raw_zip_entry_spans(source)
    with zipfile.ZipFile(
        output_path,
        "w",
        zipfile.ZIP_DEFLATED,
        compresslevel=1,
    ) as target:
        written: set[str] = set()
        for item in source.infolist():
            if item.filename in removed:
                continue
            payload = replacements.get(item.filename)
            if payload is None:
                if not _copy_raw_zip_entry(source, target, item, raw_spans):
                    payload = source.read(item.filename)
                    target.writestr(_copy_zip_info_for_payload(item), payload)
            elif payload == source.read(item.filename):
                if not _copy_raw_zip_entry(source, target, item, raw_spans):
                    target.writestr(_copy_zip_info_for_payload(item), payload)
            else:
                target.writestr(_copy_zip_info_for_payload(item), payload)
            written.add(item.filename)
        for name, payload in replacements.items():
            if name not in written and name not in removed:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                target.writestr(info, payload, compresslevel=1)


def _copy_zip_info_for_payload(item: zipfile.ZipInfo) -> zipfile.ZipInfo:
    copied = copy(item)
    if _should_store_without_deflate(copied.filename):
        copied.compress_type = zipfile.ZIP_STORED
    return copied


def _should_store_without_deflate(filename: str) -> bool:
    lower_name = filename.lower()
    return any(lower_name.endswith(extension) for extension in _PRECOMPRESSED_EXTENSIONS)


def natural_key(value: str) -> list[int | str]:
    key: list[int | str] = []
    token = ""
    token_is_digit: bool | None = None
    for char in value:
        char_is_digit = char.isdigit()
        if token and char_is_digit != token_is_digit:
            key.append(int(token) if token_is_digit else token)
            token = ""
        token += char
        token_is_digit = char_is_digit
    if token:
        key.append(int(token) if token_is_digit else token)
    return key


WEB_EXTENSION_PART_DIRECTORY = "ppt/webextensions"
WEB_EXTENSION_TASKPANES_PART = f"{WEB_EXTENSION_PART_DIRECTORY}/taskpanes.xml"
WEB_EXTENSION_CONTENT_TYPE = "application/vnd.ms-office.webextension+xml"
WEB_EXTENSION_TASKPANES_CONTENT_TYPE = "application/vnd.ms-office.webextensiontaskpanes+xml"
WEB_EXTENSION_REL_TYPE = "http://schemas.microsoft.com/office/2011/relationships/webextension"
WEB_EXTENSION_TASKPANES_REL_TYPE = (
    "http://schemas.microsoft.com/office/2011/relationships/webextensiontaskpanes"
)


class WebExtensionError(ValueError):
    """Raised when web-extension package records cannot be read or written safely."""


@dataclass(frozen=True)
class WebExtension:
    """One declared Office web extension and its persisted taskpane settings."""

    _presentation: Any = field(repr=False, compare=False)
    id: str
    reference_id: str
    version: str
    store: str | None
    store_type: str | None
    partname: str
    taskpane_partname: str
    taskpane_relationship_id: str | None
    relationship_id: str | None
    dock_state: str
    visibility: bool | None
    width: float | None
    row: int | None
    locked: bool | None
    frozen: bool | None

    @property
    def part(self) -> PackagePart:
        """The web-extension package part."""

        return PackagePart(self._presentation, self.partname, name=None)

    @property
    def element(self) -> XmlElementProxy:
        """The web-extension XML root without evaluating or fetching the add-in."""

        return package_xml_element(self._presentation.path, self.partname)

    @property
    def taskpane_part(self) -> PackagePart:
        """The package part that stores this extension's taskpane declaration."""

        return PackagePart(
            self._presentation,
            self.taskpane_partname,
            name=None,
        )

    @property
    def visible(self) -> bool | None:
        """Whether the taskpane is declared visible when the document opens."""

        return self.visibility


class WebExtensionCollection(Sequence[WebExtension]):
    """Declared Office web extensions reachable from the presentation package."""

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation
        self._extensions = list(_web_extensions_from_package(presentation))

    def __len__(self) -> int:
        return len(self._extensions)

    def __iter__(self) -> Iterator[WebExtension]:
        return iter(self._extensions)

    def __getitem__(
        self,
        index: int | slice,
    ) -> WebExtension | list[WebExtension]:
        return self._extensions[index]

    def add(
        self,
        reference_id: str,
        version: str,
        *,
        store: str = "",
        store_type: str = "SPCatalog",
        instance_id: str | None = None,
        dock_state: str = "right",
        visible: bool = True,
        width: float = 350.0,
        row: int = 0,
        locked: bool = False,
        frozen: bool = False,
    ) -> WebExtension:
        """Queue an Office web-extension reference and its taskpane declaration.

        This writes only the declared package reference. It never downloads,
        activates, or executes the referenced extension.
        """

        reference_id = _required_web_extension_string(reference_id, "reference_id")
        version = _required_web_extension_string(version, "version")
        store = _web_extension_string(store, "store")
        store_type = _required_web_extension_string(store_type, "store_type")
        resolved_instance_id = (
            str(uuid4())
            if instance_id is None
            else _required_web_extension_string(instance_id, "instance_id")
        )
        dock_state = _required_web_extension_string(dock_state, "dock_state")
        if not isinstance(visible, bool):
            raise TypeError("visible must be bool")
        if not isinstance(locked, bool):
            raise TypeError("locked must be bool")
        if not isinstance(frozen, bool):
            raise TypeError("frozen must be bool")
        if isinstance(width, bool) or not isinstance(width, (int, float)):
            raise TypeError("width must be a finite non-negative number")
        resolved_width = float(width)
        if not math.isfinite(resolved_width) or resolved_width < 0:
            raise ValueError("width must be a finite non-negative number")
        if isinstance(row, bool) or not isinstance(row, int):
            raise TypeError("row must be a non-negative integer")
        if row < 0:
            raise ValueError("row must be a non-negative integer")

        partname = _next_web_extension_partname(
            self._presentation.path,
            {extension.partname.lstrip("/") for extension in self._extensions},
        )
        taskpane_partname = (
            _web_extension_taskpane_partname(self._presentation.path)
            or WEB_EXTENSION_TASKPANES_PART
        )
        extension = WebExtension(
            self._presentation,
            id=resolved_instance_id,
            reference_id=reference_id,
            version=version,
            store=store or None,
            store_type=store_type,
            partname=partname,
            taskpane_partname=taskpane_partname,
            taskpane_relationship_id=None,
            relationship_id=None,
            dock_state=dock_state,
            visibility=visible,
            width=resolved_width,
            row=row,
            locked=locked,
            frozen=frozen,
        )
        self._extensions.append(extension)
        self._presentation._pending_web_extensions.append(extension)
        return extension

    def _mark_saved(self) -> None:
        self._extensions = list(_web_extensions_from_package(self._presentation))


def add_web_extensions(
    input_path: Path,
    output_path: Path,
    extensions: Sequence[WebExtension],
) -> None:
    """Attach queued web-extension parts without touching unrelated package data."""

    if not extensions:
        copy_package_with_replacements(input_path, output_path, {})
        return
    with zipfile.ZipFile(input_path) as package:
        replacements = _web_extension_addition_mutation(package, extensions)
    copy_package_with_replacements(input_path, output_path, replacements)


def _web_extension_addition_mutation(
    package: zipfile.ZipFile,
    extensions: Sequence[WebExtension],
) -> dict[str, bytes]:
    try:
        content_types = ET.fromstring(package.read("[Content_Types].xml"))
    except (KeyError, ET.ParseError) as exc:
        raise WebExtensionError("package content types are unavailable") from exc
    package_rels_part = "_rels/.rels"
    package_rels = _relationship_root(package, package_rels_part)
    taskpane_relations = [
        relationship
        for relationship in package_rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        if relationship.attrib.get("Type") == WEB_EXTENSION_TASKPANES_REL_TYPE
    ]
    if len(taskpane_relations) > 1:
        raise WebExtensionError("package declares more than one web-extension taskpanes part")
    if taskpane_relations:
        taskpane_part = resolve_package_target(
            "",
            taskpane_relations[0].attrib.get("Target", ""),
        )
        if taskpane_part not in package.namelist():
            raise WebExtensionError("declared web-extension taskpanes part is missing")
        taskpanes = _taskpanes_root(package.read(taskpane_part))
    else:
        taskpane_part = _next_taskpane_partname(set(package.namelist()))
        taskpanes = ET.Element(f"{{{WETP_NS}}}taskpanes")
        ET.SubElement(
            package_rels,
            f"{{{PKG_REL_NS}}}Relationship",
            {
                "Id": _next_relationship_id(_relationship_ids(package_rels)),
                "Type": WEB_EXTENSION_TASKPANES_REL_TYPE,
                "Target": _relative_package_target(
                    "",
                    taskpane_part,
                ),
            },
        )

    taskpane_rels_part = rels_part_for_package_part(taskpane_part)
    taskpane_rels = _relationship_root(package, taskpane_rels_part)
    names = set(package.namelist())
    replacements: dict[str, bytes] = {}
    _set_content_type_override(
        content_types,
        f"/{taskpane_part}",
        WEB_EXTENSION_TASKPANES_CONTENT_TYPE,
    )
    for extension in extensions:
        partname = extension.partname.lstrip("/")
        if partname in names:
            raise WebExtensionError(f"web-extension part already exists: /{partname}")
        if not partname.startswith(f"{WEB_EXTENSION_PART_DIRECTORY}/"):
            raise WebExtensionError("web-extension part must be stored beneath /ppt/webextensions")
        relationship_id = _next_relationship_id(_relationship_ids(taskpane_rels))
        ET.SubElement(
            taskpane_rels,
            f"{{{PKG_REL_NS}}}Relationship",
            {
                "Id": relationship_id,
                "Type": WEB_EXTENSION_REL_TYPE,
                "Target": _relative_package_target(taskpane_part, partname),
            },
        )
        taskpane = ET.SubElement(
            taskpanes,
            f"{{{WETP_NS}}}taskpane",
            {
                "dockstate": extension.dock_state,
                "visibility": _xml_boolean(extension.visibility),
                "width": _xml_double(extension.width),
                "row": str(extension.row),
                "locked": _xml_boolean(extension.locked),
            },
        )
        ET.SubElement(
            taskpane,
            f"{{{WETP_NS}}}webextensionref",
            {f"{{{R_NS}}}id": relationship_id},
        )
        replacements[partname] = _web_extension_xml(extension)
        _set_content_type_override(
            content_types,
            f"/{partname}",
            WEB_EXTENSION_CONTENT_TYPE,
        )
        names.add(partname)
    replacements.update(
        {
            "[Content_Types].xml": _content_types_xml(content_types),
            package_rels_part: _xml_bytes(package_rels),
            taskpane_part: _xml_bytes(taskpanes),
            taskpane_rels_part: _xml_bytes(taskpane_rels),
        }
    )
    return replacements


def _web_extensions_from_package(presentation: Any) -> tuple[WebExtension, ...]:
    try:
        with zipfile.ZipFile(presentation.path) as package:
            package_rels = _relationship_root(package, "_rels/.rels")
            extensions: list[WebExtension] = []
            for package_relation in package_rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
                if package_relation.attrib.get("Type") != WEB_EXTENSION_TASKPANES_REL_TYPE:
                    continue
                taskpane_part = resolve_package_target(
                    "",
                    package_relation.attrib.get("Target", ""),
                )
                if taskpane_part not in package.namelist():
                    continue
                taskpanes = _taskpanes_root(package.read(taskpane_part))
                taskpane_rels = _relationship_root(
                    package,
                    rels_part_for_package_part(taskpane_part),
                )
                relationships = {
                    relation.attrib.get("Id"): relation
                    for relation in taskpane_rels.findall(f"{{{PKG_REL_NS}}}Relationship")
                }
                for taskpane in taskpanes.findall(f"{{{WETP_NS}}}taskpane"):
                    ref = taskpane.find(f"{{{WETP_NS}}}webextensionref")
                    relationship_id = None if ref is None else ref.attrib.get(f"{{{R_NS}}}id")
                    relationship = relationships.get(relationship_id)
                    if (
                        relationship is None
                        or relationship.attrib.get("Type") != WEB_EXTENSION_REL_TYPE
                    ):
                        continue
                    partname = resolve_package_target(
                        taskpane_part,
                        relationship.attrib.get("Target", ""),
                    )
                    if partname not in package.namelist():
                        continue
                    extension_root = ET.fromstring(package.read(partname))
                    if extension_root.tag != f"{{{WE_NS}}}webextension":
                        continue
                    reference = extension_root.find(f"{{{WE_NS}}}reference")
                    if reference is None:
                        continue
                    extensions.append(
                        WebExtension(
                            presentation,
                            id=extension_root.attrib.get("id", ""),
                            reference_id=reference.attrib.get("id", ""),
                            version=reference.attrib.get("version", ""),
                            store=reference.attrib.get("store"),
                            store_type=reference.attrib.get("storeType"),
                            partname=partname,
                            taskpane_partname=taskpane_part,
                            taskpane_relationship_id=package_relation.attrib.get("Id"),
                            relationship_id=relationship_id,
                            dock_state=taskpane.attrib.get("dockstate", ""),
                            visibility=_optional_xml_boolean(taskpane.attrib.get("visibility")),
                            width=_optional_xml_double(taskpane.attrib.get("width")),
                            row=_optional_xml_uint(taskpane.attrib.get("row")),
                            locked=_optional_xml_boolean(taskpane.attrib.get("locked")),
                            frozen=_optional_xml_boolean(extension_root.attrib.get("frozen")),
                        )
                    )
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        WebExtensionError,
        zipfile.BadZipFile,
    ):
        return ()
    return tuple(extensions)


def _web_extension_taskpane_partname(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as package:
            relationships = _relationship_root(package, "_rels/.rels")
            targets = [
                resolve_package_target(
                    "",
                    relation.attrib.get("Target", ""),
                )
                for relation in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
                if relation.attrib.get("Type") == WEB_EXTENSION_TASKPANES_REL_TYPE
            ]
    except (FileNotFoundError, KeyError, ET.ParseError, zipfile.BadZipFile):
        return None
    return targets[0] if len(targets) == 1 else None


def _next_web_extension_partname(path: Path, reserved: set[str]) -> str:
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
    except (FileNotFoundError, zipfile.BadZipFile) as exc:
        raise WebExtensionError("web-extension source package is unavailable") from exc
    names = {name.casefold() for name in names | reserved}
    index = 1
    while True:
        partname = f"{WEB_EXTENSION_PART_DIRECTORY}/webextension{index}.xml"
        if partname.casefold() not in names:
            return partname
        index += 1


def _next_taskpane_partname(names: set[str]) -> str:
    names = {name.casefold() for name in names}
    if WEB_EXTENSION_TASKPANES_PART.casefold() not in names:
        return WEB_EXTENSION_TASKPANES_PART
    index = 1
    while True:
        partname = f"{WEB_EXTENSION_PART_DIRECTORY}/taskpanes{index}.xml"
        if partname.casefold() not in names:
            return partname
        index += 1


def _relationship_root(
    package: zipfile.ZipFile,
    partname: str,
) -> ET.Element:
    try:
        return ET.fromstring(package.read(partname))
    except KeyError:
        return ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    except ET.ParseError as exc:
        raise WebExtensionError(f"relationship part is not valid XML: /{partname}") from exc


def _taskpanes_root(payload: bytes) -> ET.Element:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise WebExtensionError("web-extension taskpanes XML is invalid") from exc
    if root.tag != f"{{{WETP_NS}}}taskpanes":
        raise WebExtensionError("web-extension taskpanes root is invalid")
    return root


def _web_extension_xml(extension: WebExtension) -> bytes:
    attributes = {"id": extension.id}
    if extension.frozen:
        attributes["frozen"] = "true"
    root = ET.Element(f"{{{WE_NS}}}webextension", attributes)
    reference_attributes = {
        "id": extension.reference_id,
        "version": extension.version,
        "storeType": extension.store_type or "SPCatalog",
    }
    if extension.store is not None:
        reference_attributes["store"] = extension.store
    ET.SubElement(root, f"{{{WE_NS}}}reference", reference_attributes)
    ET.SubElement(root, f"{{{WE_NS}}}properties")
    ET.SubElement(root, f"{{{WE_NS}}}bindings")
    return _xml_bytes(root)


def _relationship_ids(root: ET.Element) -> set[str]:
    return {
        relation.attrib.get("Id", "") for relation in root.findall(f"{{{PKG_REL_NS}}}Relationship")
    }


def _relative_package_target(source_part: str, target_part: str) -> str:
    return posixpath.relpath(target_part, posixpath.dirname(source_part))


def _required_web_extension_string(value: Any, name: str) -> str:
    result = _web_extension_string(value, name)
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _web_extension_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    return value.strip()


def _xml_boolean(value: bool | None) -> str:
    return "true" if value else "false"


def _xml_double(value: float | None) -> str:
    if value is None:
        raise WebExtensionError("web-extension taskpane width is unavailable")
    return format(value, ".15g")


def _optional_xml_boolean(value: str | None) -> bool | None:
    if value in {"1", "true", "True"}:
        return True
    if value in {"0", "false", "False"}:
        return False
    return None


def _optional_xml_double(value: str | None) -> float | None:
    try:
        result = float(value) if value is not None else None
    except ValueError:
        return None
    return result if result is not None and math.isfinite(result) else None


def _optional_xml_uint(value: str | None) -> int | None:
    if value is None or not value.isdigit():
        return None
    return int(value)


VBA_PROJECT_PART = "ppt/vbaProject.bin"
VBA_PROJECT_CONTENT_TYPE = "application/vnd.ms-office.vbaProject"
VBA_PROJECT_REL_TYPE = "http://schemas.microsoft.com/office/2006/relationships/vbaProject"
PRESENTATION_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
)
MACRO_ENABLED_PRESENTATION_CONTENT_TYPE = (
    "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml"
)
_OVBA_SIGNATURE = b"\x01"
_VBA_HOST_EXTENDER = "&H00000001={3832D640-CF90-11CF-8E43-00A0C911005A};VBE;&H00000000"
# Default references of a PowerPoint-created project (the host and VBA
# libraries are implicit); Office resolves each by LIBID, not by path.
_VBA_REFERENCES = (
    (
        "stdole",
        (
            r"*\G{00020430-0000-0000-C000-000000000046}#2.0#0#"
            r"C:\Windows\System32\stdole2.tlb#OLE Automation"
        ),
    ),
    (
        "Office",
        (
            r"*\G{2DF8D04C-5BFA-101B-BDE5-00AA0044DE52}#2.0#0#"
            r"C:\Program Files\Common Files\Microsoft Shared\OFFICE16\MSO.DLL"
            r"#Microsoft Office 16.0 Object Library"
        ),
    ),
)
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class VbaProjectError(ValueError):
    """Raised when a VBA project cannot be inspected or safely rewritten."""


@dataclass(frozen=True)
class VbaModule:
    """Source and declared kind/codepage of a VBA module; no code is executed."""

    name: str
    source: str
    kind: str = "standard"
    codepage: int = 1252
    document_version: int | None = None


@dataclass(frozen=True)
class VbaProject:
    """Inspectable source modules in an MS-OVBA project."""

    modules: tuple[VbaModule, ...]

    @property
    def module_names(self) -> tuple[str, ...]:
        return tuple(module.name for module in self.modules)

    def module_source(self, name: str) -> str:
        for module in self.modules:
            if module.name.casefold() == name.casefold():
                return module.source
        raise KeyError(name)


def inspect_vba_project(path: Path) -> VbaProject | None:
    """Return declared VBA module sources without executing any macro code."""

    try:
        with zipfile.ZipFile(path) as package:
            try:
                payload = package.read(VBA_PROJECT_PART)
            except KeyError:
                return None
    except (FileNotFoundError, zipfile.BadZipFile) as exc:
        raise VbaProjectError("presentation package is unavailable") from exc
    return _read_vba_project(payload)


def add_standard_vba_module(
    input_path: Path,
    output_path: Path,
    name: str,
    source: str,
) -> None:
    """Add one standard VBA module and convert a presentation package to PPTM.

    Existing projects use the guarded editor, retaining metadata and codepage.
    Unsupported components are refused before publishing output.
    """

    with zipfile.ZipFile(input_path) as package:
        has_project = VBA_PROJECT_PART in package.namelist()
    if has_project:
        from .vba_project import VbaProjectEditor

        editor = VbaProjectEditor(input_path)
        editor.add_module(name, source)
        editor.save(output_path)
        return
    module_name = _validate_vba_module_name(name)
    module_source = _validate_vba_source(source)
    modules = (VbaModule(module_name, module_source),)
    _write_vba_project_package(
        input_path,
        output_path,
        modules,
        macro_enabled=True,
    )


def remove_vba_project(input_path: Path, output_path: Path) -> None:
    """Strip the VBA project, its relation, and its macro-enabled content type."""

    with zipfile.ZipFile(input_path) as package:
        replacements, removals = _vba_project_removal_mutation(package)
    copy_package_with_replacements(input_path, output_path, replacements, removals)


def _write_vba_project_package(
    input_path: Path,
    output_path: Path,
    modules: tuple[VbaModule, ...],
    *,
    macro_enabled: bool,
) -> None:
    with zipfile.ZipFile(input_path) as package:
        replacements = _vba_project_addition_mutation(
            package,
            _build_vba_project_bin(modules),
            macro_enabled=macro_enabled,
        )
    copy_package_with_replacements(input_path, output_path, replacements)


def _vba_project_addition_mutation(
    package: zipfile.ZipFile,
    project_payload: bytes,
    *,
    macro_enabled: bool,
) -> dict[str, bytes]:
    content_types = ET.fromstring(package.read("[Content_Types].xml"))
    presentation_part = _presentation_part_from_content_types(content_types)
    _set_content_type_override(
        content_types,
        f"/{presentation_part}",
        (MACRO_ENABLED_PRESENTATION_CONTENT_TYPE if macro_enabled else PRESENTATION_CONTENT_TYPE),
    )
    _set_content_type_override(
        content_types,
        f"/{VBA_PROJECT_PART}",
        VBA_PROJECT_CONTENT_TYPE,
    )
    rels_part = rels_part_for_package_part(presentation_part)
    try:
        rels = ET.fromstring(package.read(rels_part))
    except KeyError:
        rels = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    existing = [
        rel
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        if rel.attrib.get("Type") == VBA_PROJECT_REL_TYPE
    ]
    if existing:
        for rel in existing:
            rel.attrib["Target"] = "vbaProject.bin"
            rel.attrib.pop("TargetMode", None)
    else:
        relationship_ids = {
            rel.attrib.get("Id", "") for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        relation_id = _next_relationship_id(relationship_ids)
        ET.SubElement(
            rels,
            f"{{{PKG_REL_NS}}}Relationship",
            {
                "Id": relation_id,
                "Type": VBA_PROJECT_REL_TYPE,
                "Target": "vbaProject.bin",
            },
        )
    return {
        "[Content_Types].xml": _content_types_xml(content_types),
        rels_part: _xml_bytes(rels),
        VBA_PROJECT_PART: project_payload,
    }


def _vba_project_removal_mutation(
    package: zipfile.ZipFile,
) -> tuple[dict[str, bytes], set[str]]:
    content_types = ET.fromstring(package.read("[Content_Types].xml"))
    presentation_part = _presentation_part_from_content_types(content_types)
    _set_content_type_override(
        content_types,
        f"/{presentation_part}",
        PRESENTATION_CONTENT_TYPE,
    )
    for override in list(content_types.findall(f"{{{CONTENT_TYPES_NS}}}Override")):
        if override.attrib.get("PartName") == f"/{VBA_PROJECT_PART}":
            content_types.remove(override)
    rels_part = rels_part_for_package_part(presentation_part)
    replacements = {"[Content_Types].xml": _content_types_xml(content_types)}
    removals = {VBA_PROJECT_PART}
    if rels_part in package.namelist():
        rels = ET.fromstring(package.read(rels_part))
        for rel in list(rels.findall(f"{{{PKG_REL_NS}}}Relationship")):
            is_vba = rel.attrib.get("Type") == VBA_PROJECT_REL_TYPE
            target = rel.attrib.get("Target", "")
            target_part = resolve_package_target(presentation_part, target)
            if is_vba or target_part == VBA_PROJECT_PART:
                rels.remove(rel)
                if target_part:
                    removals.add(target_part)
        replacements[rels_part] = _xml_bytes(rels)
    return replacements, removals


def _presentation_part_from_content_types(content_types: ET.Element) -> str:
    for override in content_types.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        content_type = override.attrib.get("ContentType", "")
        if content_type in {
            PRESENTATION_CONTENT_TYPE,
            MACRO_ENABLED_PRESENTATION_CONTENT_TYPE,
        }:
            return override.attrib["PartName"].lstrip("/")
    raise VbaProjectError("presentation main part is unavailable")


def _set_content_type_override(
    content_types: ET.Element,
    partname: str,
    content_type: str,
) -> None:
    for override in content_types.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == partname:
            override.attrib["ContentType"] = content_type
            return
    ET.SubElement(
        content_types,
        f"{{{CONTENT_TYPES_NS}}}Override",
        {"PartName": partname, "ContentType": content_type},
    )


def _next_relationship_id(ids: set[str]) -> str:
    index = 1
    while f"rId{index}" in ids:
        index += 1
    return f"rId{index}"


def _xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _content_types_xml(root: ET.Element) -> bytes:
    """Serialize an OPC content-types part with the required default namespace."""

    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    namespace = CONTENT_TYPES_NS.encode("ascii")
    return payload.replace(
        b'xmlns:ns0="' + namespace + b'"',
        b'xmlns="' + namespace + b'"',
        1,
    ).replace(b"ns0:", b"")


def _validate_vba_module_name(name: str, encoding: str = "cp1252") -> str:
    if not isinstance(name, str):
        raise TypeError("VBA module name must be str")
    candidate = name.strip()
    if not candidate or len(candidate) > 31:
        raise ValueError("VBA module name must contain 1 to 31 characters")
    if any(ord(char) > 0xFFFF for char in candidate):
        raise ValueError("VBA module names must use BMP characters for compound storage")
    if not (candidate[0].isalpha() or candidate[0] == "_") or any(
        not (char.isalnum() or char == "_") for char in candidate
    ):
        raise ValueError("VBA module name must be a valid identifier")
    try:
        encode_text(candidate, encoding)
    except ValueError as exc:
        raise ValueError(f"VBA module name must be {encoding} encodable") from exc
    return candidate


def _validate_vba_source(source: str, encoding: str = "cp1252") -> str:
    if not isinstance(source, str):
        raise TypeError("VBA module source must be str")
    if "\x00" in source:
        raise ValueError("VBA module source cannot contain NUL")
    try:
        encode_text(source, encoding)
    except ValueError as exc:
        raise ValueError(f"VBA module source must be {encoding} encodable") from exc
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    if _is_vba_name_attribute(normalized.partition("\n")[0]):
        raise ValueError(
            "VBA module source cannot declare Attribute VB_Name; the module name supplies it"
        )
    return normalized.replace("\n", "\r\n")


def _is_vba_name_attribute(line: str) -> bool:
    return line.replace(" ", "").casefold().startswith("attributevb_name=")


def _read_vba_project(payload: bytes) -> VbaProject:
    from .vba_module_records import inspect_project

    return inspect_project(payload)


def _parse_vba_directory(data: bytes) -> list[tuple[str, str, int, str]]:
    """Parse standard and shared class/document MODULETYPE directory records."""

    position = 0
    codepage = "cp1252"
    modules: list[tuple[str, str, int, str]] = []
    current: dict[str, Any] | None = None
    while position + 6 <= len(data):
        record_id, size = struct.unpack_from("<HI", data, position)
        position += 6
        if record_id == 0x0009:
            if size != 4 or position + 6 > len(data):
                raise VbaProjectError("VBA project version record is malformed")
            position += 6
            continue
        if record_id == 0x000F:
            if size != 2 or position + 2 > len(data):
                raise VbaProjectError("VBA project module table is malformed")
            position += 2
            continue
        if position + size > len(data):
            raise VbaProjectError("VBA project directory record exceeds stream")
        value = data[position : position + size]
        position += size
        if record_id in {0x0005, 0x0006, 0x000C}:
            position = _skip_vba_ansi_unicode_tail(data, position)
        elif record_id == 0x0003 and len(value) == 2:
            codepage_number = struct.unpack("<H", value)[0]
            codepage = f"cp{codepage_number}"
        elif record_id == 0x0019:
            if current is not None:
                modules.append(_finalize_vba_module_record(current))
            current = {
                "name": _decode_vba_text(value, codepage),
                "stream": None,
                "offset": None,
                "kind": None,
            }
        elif current is not None and record_id == 0x001A:
            if position + 6 > len(data):
                raise VbaProjectError("VBA module stream name is malformed")
            reserved, unicode_size = struct.unpack_from("<HI", data, position)
            position += 6
            if reserved != 0x0032 or position + unicode_size > len(data):
                raise VbaProjectError("VBA module stream name is malformed")
            position += unicode_size
            current["stream"] = _decode_vba_text(value, codepage)
        elif current is not None and record_id == 0x001C:
            position = _skip_vba_ansi_unicode_tail(data, position)
        elif current is not None and record_id == 0x0031 and len(value) == 4:
            current["offset"] = struct.unpack("<I", value)[0]
        elif current is not None and record_id == 0x0021 and not value:
            current["kind"] = "standard"
        elif current is not None and record_id == 0x0022 and not value:
            current["kind"] = "document"
        elif current is not None and record_id == 0x002B and not value:
            modules.append(_finalize_vba_module_record(current))
            current = None
        elif record_id == 0x0010 and not value:
            break
    if current is not None:
        modules.append(_finalize_vba_module_record(current))
    if not modules:
        raise VbaProjectError("VBA project contains no readable modules")
    return modules


def _skip_vba_ansi_unicode_tail(data: bytes, position: int) -> int:
    if position + 6 > len(data):
        raise VbaProjectError("VBA ANSI/Unicode record is truncated")
    reserved, unicode_size = struct.unpack_from("<HI", data, position)
    position += 6
    if reserved not in {0x003C, 0x003D, 0x0040, 0x0048}:
        raise VbaProjectError("VBA ANSI/Unicode record has an invalid marker")
    if position + unicode_size > len(data):
        raise VbaProjectError("VBA ANSI/Unicode record exceeds stream")
    return position + unicode_size


def _finalize_vba_module_record(record: dict[str, Any]) -> tuple[str, str, int, str]:
    name = record["name"]
    stream_name = record["stream"]
    text_offset = record["offset"]
    kind = record["kind"]
    if (
        not isinstance(name, str)
        or not isinstance(stream_name, str)
        or not isinstance(text_offset, int)
        or kind is None
    ):
        raise VbaProjectError("VBA module directory record is incomplete")
    return name, stream_name, text_offset, str(kind)


def _decode_vba_text(value: bytes, encoding: str) -> str:
    try:
        return value.decode(encoding)
    except (LookupError, UnicodeDecodeError) as exc:
        raise VbaProjectError("VBA project text encoding is unsupported") from exc


def _build_vba_project_bin(modules: tuple[VbaModule, ...]) -> bytes:
    if not modules:
        raise ValueError("at least one VBA module is required")
    identity = "\x00".join(f"{module.name}\x00{module.source}" for module in modules)
    project_guid = uuid5(NAMESPACE_URL, "wolfppt-vba:" + identity)
    streams: dict[tuple[str, ...], bytes] = {
        ("PROJECT",): _build_project_stream(modules, project_guid),
        ("PROJECTwm",): _build_projectwm_stream(modules),
        ("VBA", "dir"): _compress_ovba(_build_vba_directory(modules)),
        ("VBA", "_VBA_PROJECT"): struct.pack("<HHBH", 0x61CC, 0xFFFF, 0, 0),
    }
    for module in modules:
        # MS-VBAL procedural modules start with their VB_Name attribute header.
        text = f'Attribute VB_Name = "{module.name}"\r\n{module.source}'
        streams[("VBA", module.name)] = _compress_ovba(text.encode("cp1252"))
    return _CompoundFileWriter(streams).to_bytes()


def _build_project_stream(modules: tuple[VbaModule, ...], project_guid: UUID) -> bytes:
    project_id = "{" + str(project_guid).upper() + "}"
    seeds = project_guid.bytes
    protection = (
        (b"\x00\x00\x00\x00", seeds[0]),  # CMG: unprotected project
        (b"\x00", seeds[1]),  # DPB: no password
        (b"\xff", seeds[2]),  # GC: project visible
    )
    cmg, dpb, gc = (_encrypt_vba_project_data(project_id, seed, data) for data, seed in protection)
    lines = [
        f'ID="{project_id}"',
        *(f"Module={module.name}" for module in modules),
        'Name="VBAProject"',
        'HelpContextID="0"',
        'VersionCompatible32="393222000"',
        f'CMG="{cmg}"',
        f'DPB="{dpb}"',
        f'GC="{gc}"',
        "",
        "[Host Extender Info]",
        _VBA_HOST_EXTENDER,
        "",
        "[Workspace]",
    ]
    lines.extend(f"{module.name}=0, 0, 0, 0, C" for module in modules)
    return ("\r\n".join(lines) + "\r\n").encode("cp1252")


def _encrypt_vba_project_data(project_id: str, seed: int, data: bytes) -> str:
    """Apply MS-OVBA 2.4.3.2 data encryption, as used by CMG, DPB and GC."""

    project_key = sum(project_id.encode("ascii")) & 0xFF
    output = bytearray((seed, seed ^ 2, seed ^ project_key))
    unencrypted, encrypted1, encrypted2 = project_key, seed ^ project_key, seed ^ 2
    ignored = bytes((seed & 6) // 2)
    for byte in ignored + struct.pack("<I", len(data)) + data:
        encrypted = byte ^ ((encrypted2 + unencrypted) & 0xFF)
        output.append(encrypted)
        encrypted2, encrypted1, unencrypted = encrypted1, encrypted, byte
    return output.hex().upper()


def _build_projectwm_stream(modules: tuple[VbaModule, ...], encoding: str = "cp1252") -> bytes:
    payload = bytearray()
    for module in modules:
        name = encode_text(module.name, encoding) + b"\x00"
        payload.extend(name)
        payload.extend(module.name.encode("utf-16le") + b"\x00\x00")
    return bytes(payload + b"\x00\x00")


def _build_vba_directory(modules: tuple[VbaModule, ...]) -> bytes:
    data = bytearray()
    _append_vba_record(data, 0x0001, struct.pack("<I", 1))
    _append_vba_record(data, 0x0002, struct.pack("<I", 0x409))
    _append_vba_record(data, 0x0014, struct.pack("<I", 0x409))
    _append_vba_record(data, 0x0003, struct.pack("<H", 1252))
    _append_vba_record(data, 0x0004, b"VBAProject")
    _append_vba_ansi_unicode_record(data, 0x0005, b"", 0x0040)
    _append_vba_ansi_unicode_record(data, 0x0006, b"", 0x003D)
    _append_vba_record(data, 0x0007, struct.pack("<I", 0))
    _append_vba_record(data, 0x0008, struct.pack("<I", 0))
    data.extend(struct.pack("<HI", 0x0009, 4))
    data.extend(struct.pack("<IH", 1, 0))
    _append_vba_ansi_unicode_record(data, 0x000C, b"", 0x003C)
    for reference_name, libid in _VBA_REFERENCES:
        _append_vba_record(data, 0x0016, reference_name.encode("ascii"))
        _append_vba_record(data, 0x003E, reference_name.encode("utf-16le"))
        encoded = libid.encode("ascii")
        registered = struct.pack("<I", len(encoded)) + encoded + bytes(6)
        _append_vba_record(data, 0x000D, registered)
    _append_vba_record(data, 0x000F, struct.pack("<H", len(modules)))
    _append_vba_record(data, 0x0013, struct.pack("<H", 0xFFFF))
    for module in modules:
        encoded_name = module.name.encode("cp1252")
        _append_vba_record(data, 0x0019, encoded_name)
        _append_vba_record(data, 0x0047, module.name.encode("utf-16le"))
        _append_vba_record(data, 0x001A, encoded_name)
        data.extend(struct.pack("<HI", 0x0032, len(module.name.encode("utf-16le"))))
        data.extend(module.name.encode("utf-16le"))
        _append_vba_ansi_unicode_record(data, 0x001C, b"", 0x0048)
        _append_vba_record(data, 0x0031, struct.pack("<I", 0))
        _append_vba_record(data, 0x001E, struct.pack("<I", 0))
        _append_vba_record(data, 0x002C, struct.pack("<H", 0xFFFF))
        _append_vba_record(data, 0x0021, b"")
        _append_vba_record(data, 0x002B, b"")
    _append_vba_record(data, 0x0010, b"")
    return bytes(data)


def _append_vba_ansi_unicode_record(
    target: bytearray,
    record_id: int,
    text: bytes,
    marker: int,
) -> None:
    _append_vba_record(target, record_id, text)
    target.extend(struct.pack("<HI", marker, 0))


def _append_vba_record(target: bytearray, record_id: int, value: bytes) -> None:
    target.extend(struct.pack("<HI", record_id, len(value)))
    target.extend(value)


def _compress_ovba(data: bytes) -> bytes:
    """MS-OVBA 2.4.1 compression: 4096-byte chunks, raw when incompressible."""

    result = bytearray(_OVBA_SIGNATURE)
    for start in range(0, len(data), 4096):
        chunk = data[start : start + 4096]
        encoded = _compress_ovba_chunk(chunk)
        if len(encoded) <= 4096:
            result.extend(struct.pack("<H", 0xB000 | (len(encoded) - 1)))
            result.extend(encoded)
        else:
            result.extend(struct.pack("<H", 0x3FFF))
            result.extend(chunk.ljust(4096, b"\x00"))
    return bytes(result)


def _compress_ovba_chunk(chunk: bytes) -> bytes:
    output = bytearray()
    seen: dict[bytes, list[int]] = {}
    current = 0
    while current < len(chunk):
        flag_index = len(output)
        output.append(0)
        for bit in range(8):
            if current >= len(chunk):
                break
            bit_count = max(4, (current - 1).bit_length())
            limit = min((0xFFFF >> bit_count) + 3, len(chunk) - current)
            best_offset = best_length = 0
            for candidate in reversed(seen.get(chunk[current : current + 3], [])[-64:]):
                length = 0
                while length < limit and chunk[candidate + length] == chunk[current + length]:
                    length += 1
                if length > best_length:
                    best_offset, best_length = current - candidate, length
            step = best_length if best_length >= 3 else 1
            if step > 1:
                token = ((best_offset - 1) << (16 - bit_count)) | (step - 3)
                output.extend(struct.pack("<H", token))
                output[flag_index] |= 1 << bit
            else:
                output.append(chunk[current])
            for position in range(current, current + step):
                seen.setdefault(chunk[position : position + 3], []).append(position)
            current += step
    return bytes(output)


def _decompress_ovba(data: bytes) -> bytes:
    if not data.startswith(_OVBA_SIGNATURE):
        raise VbaProjectError("VBA stream is not an MS-OVBA compressed container")
    position = 1
    output = bytearray()
    while position < len(data):
        if position + 2 > len(data):
            raise VbaProjectError("VBA compressed chunk header is truncated")
        header = struct.unpack_from("<H", data, position)[0]
        position += 2
        if ((header >> 12) & 0x7) != 0x3:
            raise VbaProjectError("VBA compressed chunk signature is invalid")
        chunk_size = (header & 0x0FFF) + 3
        payload_size = chunk_size - 2
        if position + payload_size > len(data):
            raise VbaProjectError("VBA compressed chunk exceeds stream")
        chunk = data[position : position + payload_size]
        position += payload_size
        if header & 0x8000:
            output.extend(_decompress_ovba_chunk(chunk))
        else:
            if payload_size != 4096:
                raise VbaProjectError("VBA raw chunk has an invalid length")
            output.extend(chunk)
    return bytes(output)


def _decompress_ovba_chunk(chunk: bytes) -> bytes:
    output = bytearray()
    position = 0
    while position < len(chunk):
        flags = chunk[position]
        position += 1
        for bit in range(8):
            if position >= len(chunk):
                break
            if not flags & (1 << bit):
                output.append(chunk[position])
                position += 1
                continue
            if position + 2 > len(chunk):
                raise VbaProjectError("VBA copy token is truncated")
            token = struct.unpack_from("<H", chunk, position)[0]
            position += 2
            # MS-OVBA CopyToken help: ceil(log2(chunk position)), at least 4.
            length_bits = max(4, (len(output) - 1).bit_length())
            length_mask = (1 << (16 - length_bits)) - 1
            copy_offset = (token >> (16 - length_bits)) + 1
            copy_length = (token & length_mask) + 3
            if copy_offset > len(output):
                raise VbaProjectError("VBA copy token offset is invalid")
            for _ in range(copy_length):
                output.append(output[-copy_offset])
    return bytes(output)


class _CompoundFile:
    """Bounded CFB reader for the VBA streams needed by the public inspector."""

    def __init__(self, payload: bytes) -> None:
        if len(payload) < _CFB_SECTOR_SIZE or payload[:8] != _CFB_MAGIC:
            raise VbaProjectError("VBA project is not an OLE compound file")
        if struct.unpack_from("<H", payload, 28)[0] != 0xFFFE:
            raise VbaProjectError("VBA compound file byte order is unsupported")
        self._payload = payload
        self._sector_size = 1 << struct.unpack_from("<H", payload, 30)[0]
        if self._sector_size != _CFB_SECTOR_SIZE:
            raise VbaProjectError("VBA compound file sector size is unsupported")
        fat_count = struct.unpack_from("<I", payload, 44)[0]
        if fat_count > 109:
            raise VbaProjectError("VBA compound file DIFAT chains are unsupported")
        fat_ids = [
            struct.unpack_from("<I", payload, 76 + index * 4)[0] for index in range(fat_count)
        ]
        self._fat = self._read_fat(fat_ids)
        directory_start = struct.unpack_from("<I", payload, 48)[0]
        self._entries = self._read_entries(directory_start)
        if not self._entries or self._entries[0].entry_type != 5:
            raise VbaProjectError("VBA compound file root entry is unavailable")
        self._mini_fat = self._read_mini_fat()
        self._mini_stream = self._read_regular(
            self._entries[0].start_sector,
            self._entries[0].size,
        )

    def root_entry_names(self) -> tuple[str, ...]:
        """Return the direct root-storage entry names."""

        return tuple(entry.name for entry in self._children(self._entries[0].child))

    def exists(self, path: tuple[str, ...]) -> bool:
        try:
            self._entry_for_path(path)
        except VbaProjectError:
            return False
        return True

    def read(self, path: tuple[str, ...]) -> bytes:
        entry = self._entry_for_path(path)
        if entry.entry_type != 2:
            raise VbaProjectError(f"VBA compound entry {'/'.join(path)!r} is not a stream")
        if entry.size >= _CFB_MINI_CUTOFF:
            return self._read_regular(entry.start_sector, entry.size)
        return self._read_mini(entry.start_sector, entry.size)

    def _entry_for_path(self, path: tuple[str, ...]) -> _CompoundDirectoryEntry:
        current = self._entries[0]
        for name in path:
            for candidate in self._children(current.child):
                if candidate.name.casefold() == name.casefold():
                    current = candidate
                    break
            else:
                raise VbaProjectError(f"VBA compound stream {'/'.join(path)!r} is unavailable")
        return current

    def _children(self, index: int) -> list[_CompoundDirectoryEntry]:
        found: list[_CompoundDirectoryEntry] = []
        seen: set[int] = set()

        def visit(node: int) -> None:
            if node in {_CFB_NOSTREAM, _CFB_FREESECT}:
                return
            if node >= len(self._entries) or node in seen:
                raise VbaProjectError("VBA compound directory tree is invalid")
            seen.add(node)
            entry = self._entries[node]
            visit(entry.left)
            found.append(entry)
            visit(entry.right)

        visit(index)
        return found

    def _read_fat(self, sector_ids: list[int]) -> list[int]:
        payload = b"".join(self._sector(sector_id) for sector_id in sector_ids)
        return list(struct.unpack(f"<{len(payload) // 4}I", payload))

    def _read_entries(self, start_sector: int) -> list[_CompoundDirectoryEntry]:
        payload = self._read_regular(start_sector, None)
        entries = []
        for offset in range(0, len(payload), 128):
            raw = payload[offset : offset + 128]
            if len(raw) < 128:
                break
            if raw[66] == 0:
                entries.append(_CompoundDirectoryEntry("", 0))
                continue
            name_length = struct.unpack_from("<H", raw, 64)[0]
            if name_length < 2 or name_length > 64 or name_length % 2:
                raise VbaProjectError("VBA compound directory name is invalid")
            name = raw[: name_length - 2].decode("utf-16le")
            entries.append(
                _CompoundDirectoryEntry(
                    name,
                    raw[66],
                    struct.unpack_from("<I", raw, 116)[0],
                    struct.unpack_from("<Q", raw, 120)[0],
                    struct.unpack_from("<I", raw, 68)[0],
                    struct.unpack_from("<I", raw, 72)[0],
                    struct.unpack_from("<I", raw, 76)[0],
                    raw[67],
                )
            )
        return entries

    def _read_mini_fat(self) -> list[int]:
        start = struct.unpack_from("<I", self._payload, 60)[0]
        count = struct.unpack_from("<I", self._payload, 64)[0]
        if not count:
            return []
        payload = self._read_regular(start, count * _CFB_SECTOR_SIZE)
        return list(struct.unpack(f"<{len(payload) // 4}I", payload))

    def _read_regular(self, start: int, size: int | None) -> bytes:
        if start in {_CFB_ENDOFCHAIN, _CFB_FREESECT}:
            return b"" if size in {0, None} else self._invalid_chain()
        payload = bytearray()
        for sector_id in self._chain(start, self._fat):
            payload.extend(self._sector(sector_id))
        return bytes(payload if size is None else payload[:size])

    def _read_mini(self, start: int, size: int) -> bytes:
        if not size:
            return b""
        payload = bytearray()
        for sector_id in self._chain(start, self._mini_fat):
            begin = sector_id * _CFB_MINI_SECTOR_SIZE
            end = begin + _CFB_MINI_SECTOR_SIZE
            if end > len(self._mini_stream):
                raise VbaProjectError("VBA compound mini stream chain is invalid")
            payload.extend(self._mini_stream[begin:end])
        return bytes(payload[:size])

    def _chain(self, start: int, table: list[int]) -> list[int]:
        chain: list[int] = []
        seen: set[int] = set()
        sector_id = start
        while sector_id != _CFB_ENDOFCHAIN:
            if sector_id >= len(table) or sector_id in seen:
                raise VbaProjectError("VBA compound stream chain is invalid")
            seen.add(sector_id)
            chain.append(sector_id)
            sector_id = table[sector_id]
        return chain

    def _sector(self, sector_id: int) -> bytes:
        offset = _CFB_SECTOR_SIZE + sector_id * _CFB_SECTOR_SIZE
        end = offset + _CFB_SECTOR_SIZE
        if sector_id >= len(self._payload) // _CFB_SECTOR_SIZE or end > len(self._payload):
            raise VbaProjectError("VBA compound sector is outside the file")
        return self._payload[offset:end]

    def _invalid_chain(self) -> bytes:
        raise VbaProjectError("VBA compound stream chain is unavailable")
