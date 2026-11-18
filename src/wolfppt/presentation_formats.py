"""Content-based presentation formats and read-only protection inspection.

Use :func:`inspect_presentation_format` with a path or seekable binary stream.
Inspection reads package metadata without constructing a ``Presentation``,
converting alternate formats, decrypting input, or writing temporary files.
For example, ``inspect_presentation_format("deck.data").format`` identifies
the document by content even when its suffix is misleading.

Existing boolean probes and save-time content-type retargeting remain the
format dispatch used by the presentation facade.
"""

from __future__ import annotations

import re
import struct
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from os import PathLike
from pathlib import Path
from typing import IO, Any, BinaryIO
from xml.etree import ElementTree as ET

from .package_limits import PPTX_PACKAGE_LIMITS, _xml_part_refusal, _zip_entries_refusal
from .package_parts import (
    CONTENT_TYPES_NS,
    P_NS,
    PKG_REL_NS,
    R_NS,
    InMemoryPackageSource,
    VbaProjectError,
    _CompoundFile,
    open_package_source,
    resolve_package_target,
)

ODP_MIMETYPE = "application/vnd.oasis.opendocument.presentation"
CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class OdpFormatError(ValueError):
    """Raised when an ODP construct cannot be represented losslessly."""


def is_odp_package(path: Path) -> bool:
    """Return whether *path* is an ODF presentation package, never guessing by suffix."""

    try:
        with open_package_source(path) as package:
            return package.read("mimetype") == ODP_MIMETYPE.encode("ascii")
    except (FileNotFoundError, KeyError, zipfile.BadZipFile):
        return False


def has_cfbf_signature(path: Path) -> bool:
    """Return whether *path* has a CFBF header, without considering its suffix."""

    try:
        with path.open("rb") as source:
            return source.read(len(CFB_MAGIC)) == CFB_MAGIC
    except OSError:
        return False


# Legacy suffixes share one binary format; PowerPoint picks slideshow or
# template behavior from the extension alone.
BINARY_PPT_SUFFIXES = frozenset({".ppt", ".pps", ".pot"})

_PML = "application/vnd.openxmlformats-officedocument.presentationml"
_MACRO = "application/vnd.ms-powerpoint"
# suffix -> (document family, macro-enabled)
_OOXML_SUFFIXES = {
    ".pptx": ("presentation", False),
    ".pptm": ("presentation", True),
    ".ppsx": ("slideshow", False),
    ".ppsm": ("slideshow", True),
    ".potx": ("template", False),
    ".potm": ("template", True),
}
_MAIN_CONTENT_TYPES = {
    (family, macro): (
        f"{_MACRO}.{family}.macroEnabled.main+xml" if macro else f"{_PML}.{family}.main+xml"
    )
    for family, macro in _OOXML_SUFFIXES.values()
}
_CONTENT_TYPE_KEYS = {value: key for key, value in _MAIN_CONTENT_TYPES.items()}
_CONTENT_TYPE_ATTRIBUTE = re.compile(rb'ContentType="([^"]+)"')
# Slideshow and template suffixes encode the macro state, so a save to one
# must inspect the output package even when the source family already matches.
SPLIT_OOXML_SUFFIXES = frozenset({".ppsx", ".ppsm", ".potx", ".potm"})


def main_content_type_differs(package: Path | IO[bytes], suffix: str) -> bool:
    """Return whether saving ``package`` as ``suffix`` changes its family."""

    target = _OOXML_SUFFIXES.get(suffix.casefold())
    if target is None:
        return False
    with zipfile.ZipFile(package) as archive:
        types = archive.read("[Content_Types].xml")
    families = {
        _CONTENT_TYPE_KEYS[name][0]
        for match in _CONTENT_TYPE_ATTRIBUTE.finditer(types)
        if (name := match.group(1).decode("ascii", "replace")) in _CONTENT_TYPE_KEYS
    }
    return families != {target[0]}


def retarget_main_content_type(package: Path, suffix: str) -> bool:
    """Rewrite the main part content type of ``package`` to match ``suffix``.

    The document family (presentation, slideshow, template) follows the
    suffix; the macro state follows the package. A slideshow or template
    suffix whose macro state disagrees with the package is refused, because
    PowerPoint rejects such a file. Returns whether the package changed.
    """

    target = _OOXML_SUFFIXES.get(suffix.casefold())
    if target is None:
        return False
    with zipfile.ZipFile(package) as archive:
        types = archive.read("[Content_Types].xml")
        current = [
            match
            for match in _CONTENT_TYPE_ATTRIBUTE.finditer(types)
            if match.group(1).decode("ascii", "replace") in _CONTENT_TYPE_KEYS
        ]
        if len(current) != 1:
            raise ValueError("presentation package has no unique main content type")
        family, macro = _CONTENT_TYPE_KEYS[current[0].group(1).decode("ascii")]
        if target[1] != macro and suffix.casefold() in SPLIT_OOXML_SUFFIXES:
            state = "macro-enabled" if macro else "macro-free"
            raise ValueError(f"a {state} presentation cannot be saved as {suffix.casefold()}")
        if family == target[0]:
            return False
        replacement = _MAIN_CONTENT_TYPES[(target[0], macro)].encode("ascii")
        start, end = current[0].span(1)
        rewritten = types[:start] + replacement + types[end:]
        entries = [
            (info, rewritten if info.filename == "[Content_Types].xml" else None)
            for info in archive.infolist()
        ]
        staged = package.with_name(package.name + ".retype")
        with zipfile.ZipFile(staged, "w") as output:
            for info, data in entries:
                output.writestr(info, archive.read(info) if data is None else data)
    staged.replace(package)
    return True


class MacroStateRefusal(ValueError):
    """A macro-enabled package refused a macro-free save destination before any write."""


def refuse_macro_package_as_pptx(presentation: Any, path: Any) -> None:
    """Refuse a ``.pptx`` save path for a macro-enabled package, before any write.

    Streams, other suffixes and saves that carry a pending VBA lifecycle edit
    (which applies its own destination rule) are not examined.
    """

    if callable(getattr(path, "write", None)) or Path(path).suffix.casefold() != ".pptx":
        return
    if presentation._pending_vba_modules or presentation._pending_vba_removal:
        return
    source = presentation._source_path
    stream = BytesIO(source.read_bytes()) if isinstance(source, InMemoryPackageSource) else source
    try:
        observed = inspect_presentation_format(stream).format
    except PresentationInspectionRefusal:
        return
    if observed in _MACRO_ENABLED_FORMATS:
        raise MacroStateRefusal(
            "a macro-enabled presentation cannot be saved as .pptx; "
            "call remove_vba_project() first or save as .pptm"
        )


class PresentationFormat(StrEnum):
    """Content identities; encrypted package contents cannot be inferred."""

    PRESENTATION = "pptx"
    MACRO_ENABLED_PRESENTATION = "pptm"
    SLIDESHOW = "ppsx"
    MACRO_ENABLED_SLIDESHOW = "ppsm"
    TEMPLATE = "potx"
    MACRO_ENABLED_TEMPLATE = "potm"
    OPENDOCUMENT = "odp"
    OPENDOCUMENT_TEMPLATE = "otp"
    LEGACY_BINARY = "ppt"
    ENCRYPTED_PACKAGE = "encrypted_package"


_MACRO_ENABLED_FORMATS = frozenset(
    {
        PresentationFormat.MACRO_ENABLED_PRESENTATION,
        PresentationFormat.MACRO_ENABLED_SLIDESHOW,
        PresentationFormat.MACRO_ENABLED_TEMPLATE,
    }
)


@dataclass(frozen=True, slots=True)
class PresentationFormatInfo:
    """Metadata observed without opening the presentation model.

    ``None`` means the fact is hidden by encryption or unavailable in that
    format's metadata, never an assertion that protection is absent.
    ``ENCRYPTED_PACKAGE`` does not assert a presentation inside the container:
    its actual format, macro state and modification flags require decryption.
    Legacy binary slideshow/template behavior is suffix-only and therefore
    cannot be distinguished by a content inspector.
    Legacy ``PIDSI_DOC_SECURITY`` identifies password protection without saying
    whether it protects opening or modifying, so ``has_modify_password`` is
    unknown when that flag is set. OpenDocument modification metadata uses
    ``ModifyPasswordInfo`` and ``LoadReadonly`` in its configuration settings.
    """

    format: PresentationFormat
    is_encrypted: bool
    has_modify_password: bool | None
    is_write_protected: bool | None
    read_only_recommended: bool | None


class PresentationInspectionRefusal(ValueError):
    """Unreadable, ambiguous, unsupported or out-of-bounds inspection input."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


_INSPECT_FORMATS = {
    content_type: PresentationFormat(suffix.lstrip("."))
    for suffix, key in _OOXML_SUFFIXES.items()
    for content_type in (_MAIN_CONTENT_TYPES[key],)
}
_STRICT_P = "http://purl.oclc.org/ooxml/presentationml/main"
_STRICT_R = "http://purl.oclc.org/ooxml/officeDocument/relationships"
_APP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
_STRICT_APP = "http://purl.oclc.org/ooxml/officeDocument/extendedProperties"
_ODF_MANIFEST = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
_ODF_CONFIG = "urn:oasis:names:tc:opendocument:xmlns:config:1.0"
_ODF_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"


def inspect_presentation_format(
    source: str | PathLike[str] | BinaryIO,
) -> PresentationFormatInfo:
    """Inspect format and protection metadata from offset zero, without writes.

    Borrowed streams must support seek/tell and binary reads. Their original
    offset is restored on success and refusal; they are never closed. The
    shared package bounds apply before expanding ZIP members. Only package
    roots and protection metadata are read, never slide or media parts.
    """

    try:
        with _inspection_source(source) as stream:
            signature = stream.read(len(CFB_MAGIC))
            if not isinstance(signature, bytes):
                raise PresentationInspectionRefusal("input_unreadable", "expected binary input")
            stream.seek(0)
            if signature == CFB_MAGIC:
                return _inspect_compound(stream.read(PPTX_PACKAGE_LIMITS.max_archive_size + 1))
            with zipfile.ZipFile(stream) as package:
                refusal = _zip_entries_refusal(package.infolist(), PPTX_PACKAGE_LIMITS)
                if refusal is not None:
                    raise PresentationInspectionRefusal(refusal.code, refusal.recovery)
                if "mimetype" in package.namelist():
                    mimetype = package.read("mimetype")
                    if mimetype in {
                        ODP_MIMETYPE.encode("ascii"),
                        (ODP_MIMETYPE + "-template").encode("ascii"),
                    }:
                        return _inspect_opendocument(package, mimetype)
                return _inspect_ooxml(package)
    except PresentationInspectionRefusal:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        EOFError,
        KeyError,
        RuntimeError,
        NotImplementedError,
        RecursionError,
        struct.error,
        zipfile.BadZipFile,
        ET.ParseError,
    ) as exc:
        raise PresentationInspectionRefusal(
            "input_unreadable", "input metadata is unreadable or unsupported"
        ) from exc


@contextmanager
def _inspection_source(source: str | PathLike[str] | BinaryIO) -> Iterator[BinaryIO]:
    if isinstance(source, (str, PathLike)):
        with Path(source).open("rb") as stream, _inspection_source(stream) as borrowed:
            yield borrowed
        return
    stream = source
    position = None
    try:
        position = stream.tell()
        stream.seek(0, 2)
        size = stream.tell()
        if size > PPTX_PACKAGE_LIMITS.max_archive_size:
            raise PresentationInspectionRefusal(
                "archive_size_limit",
                f"requested {size}, limit {PPTX_PACKAGE_LIMITS.max_archive_size} bytes",
            )
        stream.seek(0)
        yield stream
    except AttributeError as exc:
        raise PresentationInspectionRefusal(
            "input_unreadable", "expected a path or seekable binary stream"
        ) from exc
    finally:
        if position is not None:
            stream.seek(position)


class _MetadataTreeBuilder(ET.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise PresentationInspectionRefusal(
            "xml_dtd_unsupported", "metadata must not declare a DTD"
        )


def _inspection_xml(package: zipfile.ZipFile, part: str) -> ET.Element:
    payload = package.read(part)
    refusal = _xml_part_refusal(BytesIO(payload), PPTX_PACKAGE_LIMITS)
    if refusal is not None:
        raise PresentationInspectionRefusal(refusal.code, refusal.recovery)
    return ET.fromstring(payload, parser=ET.XMLParser(target=_MetadataTreeBuilder()))


def _root_relationships(package: zipfile.ZipFile) -> ET.Element:
    root = _inspection_xml(package, "_rels/.rels")
    if root.tag != f"{{{PKG_REL_NS}}}Relationships":
        raise PresentationInspectionRefusal("unsupported_format", "invalid package relationships")
    identities = [child.get("Id") for child in root]
    if any(not identity for identity in identities) or len(set(identities)) != len(identities):
        raise PresentationInspectionRefusal("ambiguous_metadata", "invalid relationship identities")
    return root


def _relationship_part(root: ET.Element, kind: str, *, required: bool) -> str | None:
    relations = [
        child
        for child in root.findall(f"{{{PKG_REL_NS}}}Relationship")
        if child.get("Type") in {f"{R_NS}/{kind}", f"{_STRICT_R}/{kind}"}
    ]
    if not relations and not required:
        return None
    if len(relations) != 1:
        raise PresentationInspectionRefusal(
            "ambiguous_metadata", f"expected one {kind} relationship"
        )
    target = relations[0].get("Target", "")
    if not target or relations[0].get("TargetMode", "Internal") != "Internal":
        raise PresentationInspectionRefusal("unsupported_format", f"invalid {kind} target")
    part = resolve_package_target("", target)
    if part.startswith("../") or part == ".." or "\\" in part:
        raise PresentationInspectionRefusal("unsupported_format", f"invalid {kind} part")
    return part


def _inspect_ooxml(package: zipfile.ZipFile) -> PresentationFormatInfo:
    relationships = _root_relationships(package)
    main = _relationship_part(relationships, "officeDocument", required=True)
    types = _inspection_xml(package, "[Content_Types].xml")
    if types.tag != f"{{{CONTENT_TYPES_NS}}}Types":
        raise PresentationInspectionRefusal("unsupported_format", "invalid content types root")
    overrides = [
        child
        for child in types.findall(f"{{{CONTENT_TYPES_NS}}}Override")
        if child.get("PartName") == f"/{main}"
    ]
    if len(overrides) != 1:
        raise PresentationInspectionRefusal("ambiguous_metadata", "expected one main content type")
    format_choice = _INSPECT_FORMATS.get(overrides[0].get("ContentType", ""))
    if format_choice is None:
        raise PresentationInspectionRefusal("unsupported_format", "unsupported presentation format")
    presentation = _inspection_xml(package, main)
    if presentation.tag not in {f"{{{P_NS}}}presentation", f"{{{_STRICT_P}}}presentation"}:
        raise PresentationInspectionRefusal("unsupported_format", "invalid presentation root")
    namespace = presentation.tag[1:].split("}", 1)[0]
    verifiers = presentation.findall(f"{{{namespace}}}modifyVerifier")
    if len(verifiers) > 1:
        raise PresentationInspectionRefusal(
            "ambiguous_metadata", "duplicate modify-password verifier"
        )
    security = 0
    app = _relationship_part(relationships, "extended-properties", required=False)
    if app is not None:
        properties = _inspection_xml(package, app)
        if properties.tag not in {f"{{{_APP}}}Properties", f"{{{_STRICT_APP}}}Properties"}:
            raise PresentationInspectionRefusal(
                "unsupported_metadata", "invalid extended properties"
            )
        namespace = properties.tag[1:].split("}", 1)[0]
        entries = properties.findall(f"{{{namespace}}}DocSecurity")
        if len(entries) > 1:
            raise PresentationInspectionRefusal("ambiguous_metadata", "duplicate DocSecurity")
        if entries:
            security = int(entries[0].text or "")
            if not 0 <= security <= 15:
                raise PresentationInspectionRefusal(
                    "unsupported_metadata", "invalid DocSecurity bits"
                )
    return PresentationFormatInfo(
        format_choice,
        False,
        bool(verifiers),
        bool(verifiers) or bool(security & 5),
        bool(security & 2),
    )


def _inspect_compound(payload: bytes) -> PresentationFormatInfo:
    try:
        compound = _CompoundFile(payload)
        root_names = compound.root_entry_names()
        names = {name.casefold() for name in root_names}
        if len(names) != len(root_names):
            raise PresentationInspectionRefusal(
                "ambiguous_metadata", "duplicate compound root names"
            )
        encryption = {"encryptioninfo", "encryptedpackage"}
        if names & encryption:
            if not encryption <= names or "powerpoint document" in names:
                raise PresentationInspectionRefusal(
                    "ambiguous_metadata", "incomplete or mixed encrypted package container"
                )
            for name, minimum in (("EncryptionInfo", 4), ("EncryptedPackage", 9)):
                _inspect_compound_stream(compound, name, minimum)
            return PresentationFormatInfo(
                PresentationFormat.ENCRYPTED_PACKAGE, True, None, None, None
            )
        if not {"powerpoint document", "current user"} <= names:
            raise PresentationInspectionRefusal("unsupported_format", "compound file is not a deck")
        _inspect_compound_stream(compound, "PowerPoint Document", 8)
        current_user = compound.read(("Current User",))
        if len(current_user) < 28 or struct.unpack_from("<HH", current_user) != (0, 0x0FF6):
            raise PresentationInspectionRefusal(
                "input_unreadable", "invalid legacy CurrentUserAtom"
            )
        token = struct.unpack_from("<I", current_user, 12)[0]
        if token == 0xF3D1C4DF:
            return PresentationFormatInfo(PresentationFormat.LEGACY_BINARY, True, None, None, None)
        if token != 0xE391C05F:
            raise PresentationInspectionRefusal(
                "input_unreadable", "invalid legacy encryption token"
            )
        security = (
            _legacy_security(compound.read(("\x05SummaryInformation",)))
            if compound.exists(("\x05SummaryInformation",))
            else 0
        )
        # PIDSI_DOC_SECURITY has no distinction between open and modify passwords.
        return PresentationFormatInfo(
            PresentationFormat.LEGACY_BINARY,
            False,
            None if security & 1 else False,
            bool(security & 5),
            bool(security & 2),
        )
    except (VbaProjectError, UnicodeError, IndexError) as exc:
        raise PresentationInspectionRefusal(
            "input_unreadable", "unsupported compound metadata"
        ) from exc


def _inspect_compound_stream(compound: _CompoundFile, name: str, minimum: int) -> None:
    """Check declared stream bounds without materializing the document/ciphertext."""
    entry = compound._entry_for_path((name,))
    if entry.entry_type != 2 or not minimum <= entry.size <= PPTX_PACKAGE_LIMITS.max_archive_size:
        raise PresentationInspectionRefusal("input_unreadable", "invalid compound stream")
    mini = entry.size < 4096
    sector_size = 64 if mini else 512
    table = compound._mini_fat if mini else compound._fat
    chain = compound._chain(entry.start_sector, table)
    if len(chain) * sector_size < entry.size:
        raise PresentationInspectionRefusal("input_unreadable", "truncated compound stream")
    for sector in chain:
        if mini:
            if (sector + 1) * sector_size > len(compound._mini_stream):
                raise PresentationInspectionRefusal(
                    "input_unreadable", "invalid mini stream sector"
                )
        else:
            compound._sector(sector)


def _legacy_security(payload: bytes) -> int:
    if len(payload) < 48 or struct.unpack_from("<H", payload)[0] != 0xFFFE:
        raise PresentationInspectionRefusal("input_unreadable", "invalid summary property stream")
    if struct.unpack_from("<I", payload, 24)[0] != 1:
        raise PresentationInspectionRefusal(
            "unsupported_metadata", "unsupported summary property sets"
        )
    section = struct.unpack_from("<I", payload, 44)[0]
    size, count = struct.unpack_from("<II", payload, section)
    if section + size > len(payload) or size < 8 or count > (size - 8) // 8:
        raise PresentationInspectionRefusal("input_unreadable", "invalid summary property bounds")
    result = 0
    seen: set[int] = set()
    for index in range(count):
        identity, offset = struct.unpack_from("<II", payload, section + 8 + index * 8)
        if identity in seen:
            raise PresentationInspectionRefusal("ambiguous_metadata", "duplicate summary property")
        seen.add(identity)
        if identity == 0x13:
            if offset < 8 + count * 8 or offset + 8 > size:
                raise PresentationInspectionRefusal("input_unreadable", "invalid security property")
            kind, result = struct.unpack_from("<II", payload, section + offset)
            if kind != 3 or not 0 <= result <= 15:
                raise PresentationInspectionRefusal(
                    "unsupported_metadata", "invalid security property"
                )
    return result


def _inspect_opendocument(package: zipfile.ZipFile, mimetype: bytes) -> PresentationFormatInfo:
    manifest = _inspection_xml(package, "META-INF/manifest.xml")
    if manifest.tag != f"{{{_ODF_MANIFEST}}}manifest":
        raise PresentationInspectionRefusal("unsupported_format", "invalid OpenDocument manifest")
    if "content.xml" not in package.namelist():
        raise PresentationInspectionRefusal("input_unreadable", "OpenDocument content is missing")
    encrypted_parts = {
        entry.get(f"{{{_ODF_MANIFEST}}}full-path")
        for entry in manifest.findall(f"{{{_ODF_MANIFEST}}}file-entry")
        if entry.find(f"{{{_ODF_MANIFEST}}}encryption-data") is not None
    }
    format_choice = (
        PresentationFormat.OPENDOCUMENT
        if mimetype == ODP_MIMETYPE.encode("ascii")
        else PresentationFormat.OPENDOCUMENT_TEMPLATE
    )
    if encrypted_parts:
        return PresentationFormatInfo(format_choice, True, None, None, None)
    password = False
    recommended = False
    if "settings.xml" in package.namelist():
        settings = _inspection_xml(package, "settings.xml")
        if settings.tag != f"{{{_ODF_OFFICE}}}document-settings":
            raise PresentationInspectionRefusal(
                "unsupported_metadata", "invalid OpenDocument settings"
            )
        seen: set[str] = set()
        for item in settings.iter():
            name = item.get(f"{{{_ODF_CONFIG}}}name")
            if name in {"ModifyPasswordInfo", "LoadReadonly"}:
                if name in seen:
                    raise PresentationInspectionRefusal(
                        "ambiguous_metadata", "duplicate ODF setting"
                    )
                seen.add(name)
            if name == "ModifyPasswordInfo":
                password = bool(len(item)) or bool((item.text or "").strip())
            elif name == "LoadReadonly":
                value = (item.text or "").strip()
                if value not in {"true", "false"}:
                    raise PresentationInspectionRefusal(
                        "unsupported_metadata", "invalid LoadReadonly"
                    )
                recommended = value == "true"
    return PresentationFormatInfo(format_choice, False, password, password, recommended)
