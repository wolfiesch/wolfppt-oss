"""Source-only VBA module kinds and declared text encodings, never execution.

Class and document modules share MODULETYPE 0x0022 in MS-OVBA. Distinguish
these using Class=/Document= declarations in PROJECT, not source heuristics.
Document metadata includes the declared 32-bit Automation server version.
Supported codepages are ASCII-compatible Windows encodings listed below;
all conversion is strict, with no replacement characters or best-fit mapping.
Module identifiers use BMP characters to retain compound-storage name semantics;
UTF-8 source text may contain supplementary Unicode characters.
"""

from __future__ import annotations

import re
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .package_parts import VbaModule, VbaProject, _CompoundFile

SUPPORTED_CODEPAGES = (874, 932, 936, 949, 950, *range(1250, 1259), 65001)


def encoding_for(codepage: int) -> str:
    if type(codepage) is not int or codepage not in SUPPORTED_CODEPAGES:
        raise ValueError(f"unsupported declared VBA codepage: {codepage!r}")
    return "utf-8" if codepage == 65001 else f"cp{codepage}"


def encode_text(value: str, encoding: str) -> bytes:
    """Refuse codec best-fit mappings that would change caller-visible text."""
    encoded = value.encode(encoding)
    if encoded.decode(encoding) != value:
        raise ValueError(f"text cannot round-trip through {encoding}")
    return encoded


def declared_codepage(directory: bytes) -> int:
    # Import lazily: package_parts delegates its reader to this module.
    from .vba_project import _records

    values = [value for kind, value, _ in _records(directory) if kind == 0x0003]
    if len(values) != 1 or len(values[0]) != 2:
        raise ValueError("missing or duplicate VBA codepage declaration")
    codepage = struct.unpack("<H", values[0])[0]
    encoding_for(codepage)
    return codepage


def module_declarations(project: str) -> dict[str, tuple[str, int | None]]:
    declarations = {}
    for line in project.split("\r\n"):
        prefix, separator, name = line.partition("=")
        if prefix == "BaseClass":
            raise ValueError("form modules cannot be edited")
        if not separator or prefix not in {"Module", "Class", "Document"}:
            continue
        version = None
        if prefix == "Document":
            name, slash, suffix = name.partition("/")
            if not slash or not re.fullmatch(r"&H[0-9A-Fa-f]{1,8}", suffix, re.IGNORECASE):
                raise ValueError("malformed document module version")
            version = int(suffix[2:], 16)
        key = name.casefold()
        if not name or key in declarations:
            raise ValueError("ambiguous module declarations")
        kind = {"Module": "standard", "Class": "class", "Document": "document"}[prefix]
        declarations[key] = kind, version
    return declarations


def module_declaration(module: VbaModule) -> str:
    prefix = {"standard": "Module", "class": "Class", "document": "Document"}[module.kind]
    suffix = f"/&H{module.document_version:08X}" if module.kind == "document" else ""
    return f"{prefix}={module.name}{suffix}"


def module_block(module: VbaModule) -> bytes:
    from .vba_project import _record

    name = encode_text(module.name, encoding_for(module.codepage))
    unicode = module.name.encode("utf-16le")
    return (
        _record(0x0019, name)
        + _record(0x0047, unicode)
        + _record(0x001A, name)
        + _record(0x0032, unicode)
        + _record(0x001C, b"")
        + _record(0x0048, b"")
        + _record(0x0031, struct.pack("<I", 0))
        + _record(0x001E, bytes(4))
        + _record(0x002C, b"\xff\xff")
        + _record(0x0021 if module.kind == "standard" else 0x0022, b"")
        + _record(0x002B, b"")
    )


def transcode_records(data: bytes, old: str, new: str, codepage: int) -> bytes:
    from .vba_project import _record, _records

    result = bytearray()
    for kind, value, raw in _records(data):
        if kind == 0x0003:
            raw = _record(kind, struct.pack("<H", codepage))
        elif kind in {0x0004, 0x0005, 0x0006, 0x000C, 0x0019, 0x001A, 0x001C}:
            raw = _record(kind, encode_text(value.decode(old), new)) + raw[6 + len(value) :]
        result.extend(raw)
    return bytes(result)


def read_modules(
    archive: _CompoundFile, directory: bytes, project: str
) -> tuple[list[VbaModule], list[str], bool]:
    from .package_parts import VbaModule, _decompress_ovba, _parse_vba_directory

    codepage = declared_codepage(directory)
    encoding = encoding_for(codepage)
    declarations = module_declarations(project)
    modules = []
    streams = []
    compiled = False
    from .vba_project import _records

    parsed = (
        _parse_vba_directory(directory)
        if any(kind == 0x0019 for kind, _, _ in _records(directory))
        else []
    )
    for name, stream, offset, directory_kind in parsed:
        declaration = declarations.pop(name.casefold(), None)
        if declaration is None:
            raise ValueError("PROJECT module declaration missing")
        kind, document_version = declaration
        expected = "standard" if kind == "standard" else "document"
        if directory_kind != expected:
            raise ValueError("PROJECT and directory module kinds disagree")
        data = archive.read(("VBA", stream))
        compiled |= offset != 0
        source = _decompress_ovba(data[offset:]).decode(encoding)
        header, separator, body = source.partition("\r\n")
        if not separator or header != f'Attribute VB_Name = "{name}"':
            raise ValueError("source name attribute mismatch")
        modules.append(VbaModule(name, body, kind, codepage, document_version))
        streams.append(stream)
    if declarations:
        raise ValueError("PROJECT contains undeclared directory modules")
    return modules, streams, compiled


def inspect_project(payload: bytes) -> VbaProject:
    from .package_parts import VbaProject, VbaProjectError, _CompoundFile, _decompress_ovba

    try:
        archive = _CompoundFile(payload)
        directory = _decompress_ovba(archive.read(("VBA", "dir")))
        encoding = encoding_for(declared_codepage(directory))
        project = archive.read(("PROJECT",)).decode(encoding)
        modules, _, _ = read_modules(archive, directory, project)
        if not modules:
            raise VbaProjectError("VBA project contains no readable modules")
        return VbaProject(tuple(modules))
    except (ValueError, LookupError, KeyError) as exc:
        raise VbaProjectError(str(exc)) from exc
