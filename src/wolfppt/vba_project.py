"""Edit source-only VBA projects in presentation decks, without executing code.

Use ``VbaProjectEditor(path)`` to read modules, references and signature presence;
queue edits with its methods, then ``save(output_path)`` and reopen the result.
Library identifiers use MS-OVBA LibidReference strings; project identifiers use
ProjectReference strings, with the referenced project's major/minor version.
References are declarations only: no library or referenced deck is loaded.
Use ``clear_references()`` to queue removal of every reference, including defaults;
save and reopen to persist the empty collection. References may then be added again.

Unprotected, source-only standard, class and document modules use the declared
project codepage. Compiled projects, forms, control references and signatures
are refused before mutation. Signature presence is reported, not authenticated.
Untouched ZIP entries and VBA streams are retained byte-for-byte. Renaming changes
module metadata, not identifiers in user code. An empty project retains references
and is readable through this module (the older Presentation view requires modules).
Saving a project under a macro-free main content type converts that type to PPTM.
"""

from __future__ import annotations

import re
import struct
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from xml.etree import ElementTree as ET

from .package_parts import (
    MACRO_ENABLED_PRESENTATION_CONTENT_TYPE,
    PKG_REL_NS,
    PRESENTATION_CONTENT_TYPE,
    VBA_PROJECT_PART,
    VBA_PROJECT_REL_TYPE,
    VbaModule,
    VbaProjectError,
    _build_projectwm_stream,
    _CompoundFile,
    _CompoundFileWriter,
    _compress_ovba,
    _content_types_xml,
    _decompress_ovba,
    _validate_vba_module_name,
    _validate_vba_source,
    copy_package_with_replacements,
)
from .vba_module_records import (
    declared_codepage,
    encode_text,
    encoding_for,
    module_block,
    module_declaration,
    read_modules,
    transcode_records,
)

_SOURCE_ONLY = bytes.fromhex("cc61ffff000000")
_LIBRARY_ID = re.compile(
    r"\*\\[GH]\{[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}\}"
    r"#[0-9A-Fa-f]{1,4}\.[0-9A-Fa-f]{1,4}#[0-9A-Fa-f]{1,8}#[^#\x00\r\n]*#[^\x00\r\n]{0,255}"
)


class VbaProjectRefusal(VbaProjectError):
    """A named, pre-write refusal with a machine-readable ``reason``."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(f"{reason}: {detail}")


@dataclass(frozen=True)
class LibraryReference:
    """An MS-OVBA registered Automation library declaration."""

    name: str
    libid: str


@dataclass(frozen=True)
class ProjectReference:
    """An external VBA project declaration, including its declared version."""

    name: str
    absolute_libid: str
    relative_libid: str
    major_version: int
    minor_version: int


@dataclass(frozen=True)
class VbaSignatures:
    """Signature package parts; no cryptographic validity claim is made."""

    parts: tuple[str, ...]

    @property
    def signed(self) -> bool:
        return bool(self.parts)


def inspect_vba_signatures(path: str | Path) -> VbaSignatures:
    """Report VBA signatures even when module contents are unsupported."""
    try:
        with zipfile.ZipFile(path) as package:
            return _signatures(package)
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise VbaProjectRefusal("unsupported_package", str(exc)) from exc


def _signatures(package: zipfile.ZipFile) -> VbaSignatures:
    parts: set[str] = set()
    types = ET.fromstring(package.read("[Content_Types].xml"))
    for child in types:
        if "vbaprojectsignature" in child.get("ContentType", "").lower():
            if child.get("PartName"):
                parts.add(child.attrib["PartName"].lstrip("/"))
            elif child.get("Extension"):
                parts.update(
                    name
                    for name in package.namelist()
                    if name.lower().endswith("." + child.attrib["Extension"].lower())
                )
    # Include familiar signature parts even if a damaged content-type table omits them.
    parts.update(name for name in package.namelist() if "vbaprojectsignature" in name.lower())
    return VbaSignatures(tuple(sorted(parts)))


def _text(value: object, label: str, encoding: str = "cp1252") -> str:
    if not isinstance(value, str) or not value or any(c in value for c in "\x00\r\n"):
        raise VbaProjectRefusal(
            "invalid_reference", f"{label} must be nonempty text without NUL or newlines"
        )
    try:
        encode_text(value, encoding)
    except ValueError as exc:
        raise VbaProjectRefusal("invalid_reference", f"{label} must be {encoding}") from exc
    return value


def _module(
    name: str,
    source: str,
    kind: str = "standard",
    codepage: int = 1252,
    document_version: int | None = None,
) -> VbaModule:
    if not isinstance(kind, str) or kind not in {"standard", "class", "document"}:
        raise VbaProjectRefusal("unsupported_component", f"unsupported module kind: {kind!r}")
    try:
        if kind == "document" and document_version is None:
            document_version = 0
        if document_version is not None and (
            kind != "document"
            or type(document_version) is not int
            or not 0 <= document_version <= 0xFFFFFFFF
        ):
            raise ValueError("document_version must be a 32-bit integer for a document module")
        encoding = encoding_for(codepage)
        return VbaModule(
            _validate_vba_module_name(name, encoding),
            _validate_vba_source(source, encoding),
            kind,
            codepage,
            document_version,
        )
    except (TypeError, ValueError) as exc:
        raise VbaProjectRefusal("invalid_module", str(exc)) from exc


def _record(kind: int, value: bytes) -> bytes:
    return struct.pack("<HI", kind, len(value)) + value


def _records(data: bytes) -> list[tuple[int, bytes, bytes]]:
    """Read bounded records, retaining composite ANSI/Unicode bytes unchanged."""
    records = []
    position = 0
    while position < len(data):
        start = position
        if position + 6 > len(data):
            raise VbaProjectRefusal("malformed_directory", "truncated record header")
        kind, size = struct.unpack_from("<HI", data, position)
        if kind in {0x002F, 0x0033}:
            raise VbaProjectRefusal("unsupported_reference", "control references cannot be edited")
        position += 6
        actual_size = 6 if kind == 0x0009 and size == 4 else size
        end = position + actual_size
        if end > len(data):
            raise VbaProjectRefusal("malformed_directory", "record exceeds directory stream")
        value = data[position:end]
        position = end
        if kind in {0x0005, 0x0006, 0x000C, 0x001A, 0x001C}:
            if position + 6 > len(data):
                raise VbaProjectRefusal("malformed_directory", "truncated Unicode tail")
            marker, tail_size = struct.unpack_from("<HI", data, position)
            expected = {
                0x0005: 0x0040,
                0x0006: 0x003D,
                0x000C: 0x003C,
                0x001A: 0x0032,
                0x001C: 0x0048,
            }[kind]
            position += 6 + tail_size
            if marker != expected or tail_size % 2 or position > len(data):
                raise VbaProjectRefusal("malformed_directory", "invalid Unicode tail")
        records.append((kind, value, data[start:position]))
    return records


def _decode(data: bytes, encoding: str = "cp1252") -> str:
    try:
        return data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise VbaProjectRefusal("unsupported_encoding", f"invalid {encoding} text") from exc


def _sized(data: bytes, offset: int, encoding: str) -> tuple[str, int]:
    if offset + 4 > len(data):
        raise VbaProjectRefusal("malformed_reference", "truncated string size")
    size = struct.unpack_from("<I", data, offset)[0]
    end = offset + 4 + size
    if end > len(data):
        raise VbaProjectRefusal("malformed_reference", "string exceeds record")
    return _decode(data[offset + 4 : end], encoding), end


def _reference(
    kind: int, name: str, value: bytes, encoding: str
) -> LibraryReference | ProjectReference:
    first, position = _sized(value, 0, encoding)
    if kind == 0x000D:
        if value[position:] != bytes(6):
            raise VbaProjectRefusal(
                "malformed_reference", "invalid registered reference reserved fields"
            )
        return LibraryReference(name, first)
    second, position = _sized(value, position, encoding)
    if position + 6 != len(value):
        raise VbaProjectRefusal("malformed_reference", "invalid project reference version")
    major, minor = struct.unpack_from("<IH", value, position)
    return ProjectReference(name, first, second, major, minor)


def _reference_bytes(
    reference: LibraryReference | ProjectReference, encoding: str = "cp1252"
) -> bytes:
    name = encode_text(reference.name, encoding)
    result = _record(0x0016, name) + _record(0x003E, reference.name.encode("utf-16le"))
    if isinstance(reference, LibraryReference):
        libid = encode_text(reference.libid, encoding)
        return result + _record(0x000D, struct.pack("<I", len(libid)) + libid + bytes(6))
    absolute = encode_text(reference.absolute_libid, encoding)
    relative = encode_text(reference.relative_libid, encoding)
    return result + _record(
        0x000E,
        struct.pack("<I", len(absolute))
        + absolute
        + struct.pack("<I", len(relative))
        + relative
        + struct.pack("<IH", reference.major_version, reference.minor_version),
    )


class VbaProjectEditor:
    """Transactional source-only module and reference edits over an existing project.

    All mutations remain in memory until save. Reopen the saved file with a new
    editor. Save refuses a source changed since opening and atomically publishes
    output, including in-place output. No VBA code or reference is executed.
    ``add_module(..., kind="class"|"document")`` declares module kind.
    ``set_codepage(number)`` strictly transcodes the whole source-only project;
    unsupported or unrepresentable text is refused without changing queued edits.
    Source attributes other than VB_Name remain part of the caller's source.
    Document modules expose ``document_version``, the declared 32-bit Automation
    server version. Author it with ``add_module(..., document_version=number)``.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._original = self.path.read_bytes()
        self._dirty = False
        self._metadata_dirty = False
        try:
            with zipfile.ZipFile(self.path) as package:
                names = package.namelist()
                if len(set(names)) != len(names):
                    raise VbaProjectRefusal("ambiguous_package", "duplicate ZIP members")
                types = ET.fromstring(package.read("[Content_Types].xml"))
                main = next(
                    (child for child in types if child.get("PartName") == "/ppt/presentation.xml"),
                    None,
                )
                if main is None or main.get("ContentType") not in {
                    MACRO_ENABLED_PRESENTATION_CONTENT_TYPE,
                    PRESENTATION_CONTENT_TYPE,
                }:
                    raise VbaProjectRefusal("unsupported_format", "expected a presentation")
                self._content_types = None
                if main.get("ContentType") == PRESENTATION_CONTENT_TYPE:
                    main.set("ContentType", MACRO_ENABLED_PRESENTATION_CONTENT_TYPE)
                    self._content_types = _content_types_xml(types)
                rels = ET.fromstring(package.read("ppt/_rels/presentation.xml.rels"))
                projects = [
                    rel
                    for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
                    if rel.get("Type") == VBA_PROJECT_REL_TYPE
                ]
                if (
                    len(projects) != 1
                    or projects[0].get("Target") not in {"vbaProject.bin", "/ppt/vbaProject.bin"}
                    or projects[0].get("TargetMode", "Internal") != "Internal"
                ):
                    raise VbaProjectRefusal("unsupported_project", "ambiguous VBA project relation")
                self.signatures = _signatures(package)
                payload = package.read(VBA_PROJECT_PART)
                self._package_signed = any(name.startswith("_xmlsignatures/") for name in names)
            archive = _CompoundFile(payload)
            directory_sector = struct.unpack_from("<I", payload, 48)[0]
            raw_directory = archive._read_regular(directory_sector, None)
            self._storage_metadata = any(
                raw_directory[offset + 66] and any(raw_directory[offset + 80 : offset + 116])
                for offset in range(0, len(raw_directory), 128)
            )
            self._streams = _streams(archive)
            directory = _decompress_ovba(archive.read(("VBA", "dir")))
            try:
                self._codepage = declared_codepage(directory)
                self._encoding = encoding_for(self._codepage)
            except VbaProjectRefusal:
                raise
            except ValueError as exc:
                raise VbaProjectRefusal("unsupported_encoding", str(exc)) from exc
            self._project = _decode(archive.read(("PROJECT",)), self._encoding)
            self._load_directory(directory, archive)
            self._guard_reason = self._editable_reason()
        except VbaProjectRefusal:
            raise
        except (
            VbaProjectError,
            KeyError,
            ValueError,
            struct.error,
            ET.ParseError,
            zipfile.BadZipFile,
            RecursionError,
        ) as exc:
            raise VbaProjectRefusal("unsupported_project", str(exc)) from exc

    def _load_directory(self, directory: bytes, archive: _CompoundFile) -> None:
        records = _records(directory)
        counts = [index for index, (kind, _, _) in enumerate(records) if kind == 0x000F]
        if len(counts) != 1 or len(records[counts[0]][1]) != 2:
            raise VbaProjectRefusal("malformed_directory", "missing or duplicate module count")
        count_index = counts[0]
        reference_start = next(
            (
                i
                for i, (kind, _, _) in enumerate(records[:count_index])
                if kind in {0x0016, 0x000D, 0x000E}
            ),
            count_index,
        )
        self._header = b"".join(raw for _, _, raw in records[:reference_start])
        self._references: list[LibraryReference | ProjectReference] = []
        self._reference_records: list[bytes] = []
        pending = b""
        name = ""
        for kind, value, raw in records[reference_start:count_index]:
            pending += raw
            if kind == 0x0016:
                if name:
                    raise VbaProjectRefusal("malformed_reference", "unpaired reference name")
                name = _decode(value, self._encoding)
            elif kind == 0x003E:
                continue
            elif kind in {0x000D, 0x000E}:
                self._references.append(_reference(kind, name, value, self._encoding))
                self._reference_records.append(pending)
                name, pending = "", b""
            else:
                raise VbaProjectRefusal("unsupported_reference", f"record {kind:#x}")
        if pending:
            raise VbaProjectRefusal("malformed_reference", "missing reference declaration")
        self._blocks: list[bytes] = []
        current = b""
        module_prefix = b""
        tail = b""
        for kind, _, raw in records[count_index + 1 :]:
            if kind == 0x0019:
                if current:
                    raise VbaProjectRefusal("malformed_directory", "unterminated module")
                current = raw
            elif current:
                current += raw
                if kind == 0x002B:
                    self._blocks.append(current)
                    current = b""
            elif kind == 0x0013 and not self._blocks:
                module_prefix += raw
            elif kind == 0x0010:
                tail += raw
            else:
                raise VbaProjectRefusal("malformed_directory", "unexpected module-table record")
        count = struct.unpack("<H", records[count_index][1])[0]
        if current or count != len(self._blocks) or tail != _record(0x0010, b""):
            raise VbaProjectRefusal("malformed_directory", "module count or terminator mismatch")
        self._module_prefix = module_prefix
        self._tail = tail
        self._modules: list[VbaModule] = []
        self._stream_names: list[str] = []
        self._compiled_offsets = False
        try:
            self._modules, self._stream_names, self._compiled_offsets = read_modules(
                archive, directory, self._project
            )
        except UnicodeDecodeError as exc:
            raise VbaProjectRefusal("unsupported_encoding", str(exc)) from exc
        except ValueError as exc:
            raise VbaProjectRefusal("unsupported_component", str(exc)) from exc
        if len(set(name.casefold() for name in self.module_names)) != count:
            raise VbaProjectRefusal("ambiguous_modules", "duplicate module names")

    def _editable_reason(self) -> str | None:
        if self.signatures.signed or self._package_signed:
            return "signed_project"
        if self._compiled_offsets or self._streams.get(("VBA", "_VBA_PROJECT")) != _SOURCE_ONLY:
            return "compiled_project"
        expected = {
            ("PROJECT",),
            ("PROJECTwm",),
            ("VBA", "dir"),
            ("VBA", "_VBA_PROJECT"),
            *(("VBA", name) for name in self._stream_names),
        }
        if self._storage_metadata or set(self._streams) - expected:
            return "unsupported_component"
        if any(
            ord(char) > 0xFFFF
            for name in (*self.module_names, *self._stream_names)
            for char in name
        ):
            return "unsupported_component"
        if not _unprotected(self._project):
            return "protected_project"
        return None

    @property
    def codepage(self) -> int:
        """The declared MS-OVBA project codepage."""
        return self._codepage

    def set_codepage(self, codepage: int) -> None:
        """Strictly transcode all text in memory before committing any state."""
        self._guard()
        try:
            encoding = encoding_for(codepage)
            if codepage == self._codepage:
                return
            header = transcode_records(self._header, self._encoding, encoding, codepage)
            blocks = [
                transcode_records(block, self._encoding, encoding, codepage)
                for block in self._blocks
            ]
            references = [_reference_bytes(ref, encoding) for ref in self._references]
            modules = [replace(module, codepage=codepage) for module in self._modules]
            streams = dict(self._streams)
            streams[("PROJECT",)] = encode_text(self._project, encoding)
            streams[("PROJECTwm",)] = _build_projectwm_stream(tuple(modules), encoding)
            for module, stream in zip(modules, self._stream_names, strict=True):
                streams[("VBA", stream)] = _source_bytes(module)
        except (ValueError, LookupError) as exc:
            raise VbaProjectRefusal("unsupported_encoding", str(exc)) from exc
        self._header, self._blocks, self._reference_records = header, blocks, references
        self._modules, self._streams = modules, streams
        self._codepage, self._encoding = codepage, encoding
        self._metadata_dirty = True
        self._dirty = True

    def _guard(self) -> None:
        if self._guard_reason:
            raise VbaProjectRefusal(self._guard_reason, "project cannot be safely rewritten")

    @property
    def modules(self) -> tuple[VbaModule, ...]:
        return tuple(self._modules)

    @property
    def module_names(self) -> tuple[str, ...]:
        return tuple(module.name for module in self._modules)

    @property
    def references(self) -> tuple[LibraryReference | ProjectReference, ...]:
        return tuple(self._references)

    @property
    def signed(self) -> bool:
        return self.signatures.signed

    def _index(self, name: str) -> int:
        if isinstance(name, str):
            for index, module in enumerate(self._modules):
                if module.name.casefold() == name.casefold():
                    return index
        raise VbaProjectRefusal("missing_module", repr(name))

    def module_source(self, name: str) -> str:
        return self._modules[self._index(name)].source

    def add_module(
        self,
        name: str,
        source: str,
        *,
        kind: str = "standard",
        document_version: int | None = None,
    ) -> None:
        self._guard()
        module = _module(name, source, kind, self._codepage, document_version)
        if any(existing.casefold() == module.name.casefold() for existing in self.module_names):
            raise VbaProjectRefusal("duplicate_module", module.name)
        if module.name.casefold() in {"dir", "_vba_project"}:
            raise VbaProjectRefusal("invalid_module", "name collides with a VBA storage stream")
        if any(stream.casefold() == module.name.casefold() for stream in self._stream_names):
            raise VbaProjectRefusal("duplicate_module", "name collides with a module stream")
        if len(self._modules) == 65535:
            raise VbaProjectRefusal("module_limit", "MS-OVBA permits at most 65535 modules")
        self._modules.append(module)
        self._stream_names.append(module.name)
        self._blocks.append(module_block(module))
        self._streams[("VBA", module.name)] = _source_bytes(module)
        self._project = _project_modules(self._project, self._modules)
        self._metadata_dirty = True
        self._dirty = True

    def edit_module(self, name: str, source: str) -> None:
        self._guard()
        index = self._index(name)
        old = self._modules[index]
        module = _module(old.name, source, old.kind, self._codepage, old.document_version)
        self._streams[("VBA", self._stream_names[index])] = _source_bytes(module)
        self._modules[index] = module
        self._dirty = True

    def rename_module(self, name: str, new_name: str) -> None:
        self._guard()
        index = self._index(name)
        old = self._modules[index]
        module = _module(new_name, old.source, old.kind, self._codepage, old.document_version)
        if any(
            i != index and old.name.casefold() == module.name.casefold()
            for i, old in enumerate(self._modules)
        ):
            raise VbaProjectRefusal("duplicate_module", module.name)
        if module.name.casefold() in {"dir", "_vba_project"}:
            raise VbaProjectRefusal("invalid_module", "name collides with a VBA storage stream")
        old_name = self._modules[index].name
        old_stream = self._stream_names[index]
        if any(
            i != index and stream.casefold() == module.name.casefold()
            for i, stream in enumerate(self._stream_names)
        ):
            raise VbaProjectRefusal("duplicate_module", "name collides with a module stream")
        new_block = bytearray()
        encoded = encode_text(module.name, self._encoding)
        unicode = module.name.encode("utf-16le")
        for kind, _, raw in _records(self._blocks[index]):
            if kind in {0x0019, 0x0047}:
                raw = _record(kind, encoded if kind == 0x0019 else unicode)
            elif kind == 0x001A:
                raw = _record(kind, encoded) + _record(0x0032, unicode)
            new_block.extend(raw)
        del self._streams[("VBA", old_stream)]
        self._streams[("VBA", module.name)] = _source_bytes(module)
        self._blocks[index] = bytes(new_block)
        self._stream_names[index] = module.name
        self._modules[index] = module
        self._project = _project_modules(self._project, self._modules, {old_name: module.name})
        self._metadata_dirty = True
        self._dirty = True

    def remove_module(self, name: str) -> None:
        self._guard()
        index = self._index(name)
        removed = self._modules[index].name
        del self._streams[("VBA", self._stream_names.pop(index))]
        self._blocks.pop(index)
        self._modules.pop(index)
        self._project = _project_modules(self._project, self._modules, {removed: None})
        self._metadata_dirty = True
        self._dirty = True

    def _add_reference(self, reference: LibraryReference | ProjectReference) -> None:
        if any(old.name.casefold() == reference.name.casefold() for old in self._references):
            raise VbaProjectRefusal("duplicate_reference", reference.name)
        self._references.append(reference)
        self._reference_records.append(_reference_bytes(reference, self._encoding))
        self._dirty = True

    def add_library_reference(self, name: str, libid: str) -> None:
        self._guard()
        name = _text(name, "reference name", self._encoding)
        libid = _text(libid, "library identifier", self._encoding)
        if not _LIBRARY_ID.fullmatch(libid):
            raise VbaProjectRefusal(
                "invalid_reference", "expected an MS-OVBA registered library identifier"
            )
        self._add_reference(LibraryReference(name, libid))

    def add_project_reference(
        self,
        name: str,
        absolute_libid: str,
        relative_libid: str,
        major_version: int,
        minor_version: int,
    ) -> None:
        self._guard()
        name = _text(name, "reference name", self._encoding)
        for label, value in (
            ("absolute identifier", absolute_libid),
            ("relative identifier", relative_libid),
        ):
            _text(value, label, self._encoding)
            if len(value) < 4 or not value.startswith("*\\") or value[2] not in "ABCD":
                raise VbaProjectRefusal(
                    "invalid_reference", "expected an MS-OVBA project identifier"
                )
        for label, value, maximum in (
            ("major version", major_version, 0xFFFFFFFF),
            ("minor version", minor_version, 0xFFFF),
        ):
            if type(value) is not int or not 0 <= value <= maximum:
                raise VbaProjectRefusal("invalid_reference", f"{label} must be in 0..{maximum}")
        self._add_reference(
            ProjectReference(name, absolute_libid, relative_libid, major_version, minor_version)
        )

    def remove_reference(self, name: str) -> None:
        self._guard()
        if isinstance(name, str):
            for index, reference in enumerate(self._references):
                if reference.name.casefold() == name.casefold():
                    self._references.pop(index)
                    self._reference_records.pop(index)
                    self._dirty = True
                    return
        raise VbaProjectRefusal("missing_reference", repr(name))

    def clear_references(self) -> None:
        """Queue removal of all references; an editable empty collection is a no-op."""
        self._guard()
        if not self._references:
            return
        self._references.clear()
        self._reference_records.clear()
        self._dirty = True

    def save(self, output_path: str | Path) -> None:
        self._guard()
        output = Path(output_path)
        if output.suffix.lower() != ".pptm":
            raise VbaProjectRefusal("invalid_destination", "save VBA projects as .pptm")
        if self.path.read_bytes() != self._original:
            raise VbaProjectRefusal("source_changed", "reopen the changed source before saving")
        replacements = {}
        if self._content_types is not None:
            replacements["[Content_Types].xml"] = self._content_types
        if self._dirty:
            streams = dict(self._streams)
            if self._metadata_dirty:
                streams[("PROJECT",)] = encode_text(self._project, self._encoding)
                streams[("PROJECTwm",)] = _build_projectwm_stream(
                    tuple(self._modules), self._encoding
                )
            directory = (
                self._header
                + b"".join(self._reference_records)
                + _record(0x000F, struct.pack("<H", len(self._modules)))
                + self._module_prefix
                + b"".join(self._blocks)
                + self._tail
            )
            streams[("VBA", "dir")] = _compress_ovba(directory)
            replacements[VBA_PROJECT_PART] = _CompoundFileWriter(streams).to_bytes()
        copy_package_with_replacements(self.path, output, replacements)


def _source_bytes(module: VbaModule) -> bytes:
    return _compress_ovba(
        encode_text(
            f'Attribute VB_Name = "{module.name}"\r\n{module.source}',
            encoding_for(module.codepage),
        )
    )


def _streams(archive: _CompoundFile) -> dict[tuple[str, ...], bytes]:
    streams: dict[tuple[str, ...], bytes] = {}
    seen: set[int] = set()

    def visit(entry, path: tuple[str, ...]) -> None:
        identity = id(entry)
        if identity in seen:
            raise VbaProjectRefusal("malformed_project", "cyclic or shared storage entry")
        seen.add(identity)
        children = archive._children(entry.child)
        if path and not children:
            raise VbaProjectRefusal("unsupported_component", "empty storage cannot be preserved")
        keys = [child.name.casefold() for child in children]
        if len(set(keys)) != len(keys):
            raise VbaProjectRefusal("malformed_project", "duplicate storage names")
        for child in children:
            child_path = (*path, child.name)
            if child.entry_type == 1:
                visit(child, child_path)
            elif child.entry_type == 2:
                streams[child_path] = archive.read(child_path)
            else:
                raise VbaProjectRefusal("unsupported_component", "invalid storage entry kind")

    visit(archive._entries[0], ())
    return streams


def _project_modules(
    project: str, modules: list[VbaModule], renames: dict[str, str | None] | None = None
) -> str:
    renames = renames or {}
    lines = project.split("\r\n")
    result = []
    inserted = False
    workspace = False
    for line in lines:
        if line.startswith(("Module=", "Class=", "Document=")):
            if not inserted:
                result.extend(module_declaration(module) for module in modules)
                inserted = True
            continue
        if line.startswith("["):
            workspace = line == "[Workspace]"
        if workspace and "=" in line:
            key, separator, value = line.partition("=")
            if key in renames:
                if renames[key] is None:
                    continue
                line = f"{renames[key]}{separator}{value}"
        result.append(line)
    if not inserted:
        result[1:1] = [module_declaration(module) for module in modules]
    return "\r\n".join(result)


def _unprotected(project: str) -> bool:
    """Read protection declarations solely to refuse protected projects."""
    fields = dict(line.split("=", 1) for line in project.split("\r\n") if "=" in line)
    try:
        project_id = fields["ID"].strip('"')
        key = sum(project_id.encode("ascii")) & 0xFF
        for field, expected in (("CMG", bytes(4)), ("DPB", b"\x00"), ("GC", b"\xff")):
            data = bytes.fromhex(fields[field].strip('"'))
            seed, version, encoded_key = data[:3]
            if seed ^ version != 2 or seed ^ encoded_key != key:
                return False
            previous, previous2, plain_previous = encoded_key, version, key
            plain = bytearray()
            for byte in data[3:]:
                value = byte ^ ((previous2 + plain_previous) & 0xFF)
                plain.append(value)
                previous2, previous, plain_previous = previous, byte, value
            skip = (seed & 6) // 2
            length = struct.unpack_from("<I", plain, skip)[0]
            if plain[skip + 4 :] != expected or length != len(expected):
                return False
    except (KeyError, ValueError, UnicodeEncodeError, struct.error):
        return False
    return True
