"""Read-only package part and XML element facades."""

from __future__ import annotations

import posixpath
import zipfile
from collections.abc import Iterator
from copy import copy, deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


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


class PackagePart:
    """Read-only python-pptx-style package part metadata."""

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
    def part(self) -> "PackagePart":
        return self

    @property
    def package(self) -> Any:
        return self._presentation

    @property
    def name(self) -> str:
        if self._name is None:
            raise AttributeError("package part does not expose a name")
        return self._name


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
    ) -> "XmlElementProxy | None":
        found = self._element.find(path, namespaces or _XML_NAMESPACES)
        return None if found is None else XmlElementProxy(found)

    def findall(
        self,
        path: str,
        namespaces: dict[str, str] | None = None,
    ) -> list["XmlElementProxy"]:
        return [
            XmlElementProxy(element)
            for element in self._element.findall(path, namespaces or _XML_NAMESPACES)
        ]

    def xpath(self, path: str) -> list["XmlElementProxy"]:
        return self.findall(path, _XML_NAMESPACES)

    def __iter__(self) -> Iterator["XmlElementProxy"]:
        for child in self._element:
            yield XmlElementProxy(child)

    def __getitem__(
        self,
        index: int | slice,
    ) -> "XmlElementProxy | list[XmlElementProxy]":
        if isinstance(index, slice):
            return [XmlElementProxy(child) for child in self._element[index]]
        return XmlElementProxy(self._element[index])

    def __len__(self) -> int:
        return len(self._element)

    def __repr__(self) -> str:
        return f"<XmlElementProxy tag={self.tag!r} children={len(self)}>"


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
    return f"{posixpath.dirname(part)}/_rels/{posixpath.basename(part)}.rels"


def package_xml_element(path: Path, partname: str) -> XmlElementProxy:
    normalized = normalize_package_partname(partname).lstrip("/")
    try:
        with zipfile.ZipFile(path) as package:
            return XmlElementProxy(ET.fromstring(package.read(normalized)))
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ) as exc:
        raise AttributeError("package XML element is unavailable") from exc


def package_part_content_type(path: Path, partname: str) -> str:
    normalized = normalize_package_partname(partname)
    try:
        with zipfile.ZipFile(path) as package:
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
    with zipfile.ZipFile(input_path) as source:
        copy_open_package_with_replacements(source, output_path, replacements, removals)


def copy_open_package_with_replacements(
    source: zipfile.ZipFile,
    output_path: Path,
    replacements: dict[str, bytes],
    removals: set[str] | None = None,
) -> None:
    removed = removals or set()
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
                target.writestr(name, payload)


def _raw_zip_entry_spans(source: zipfile.ZipFile) -> dict[int, int]:
    if source.fp is None:
        return {}
    try:
        central_directory_offset = source.start_dir
    except AttributeError:
        return {}
    infos = sorted(source.infolist(), key=lambda item: item.header_offset)
    spans: dict[int, int] = {}
    for index, item in enumerate(infos):
        next_offset = (
            infos[index + 1].header_offset
            if index + 1 < len(infos)
            else central_directory_offset
        )
        span = next_offset - item.header_offset
        if span > 0:
            spans[item.header_offset] = span
    return spans


def _copy_raw_zip_entry(
    source: zipfile.ZipFile,
    target: zipfile.ZipFile,
    item: zipfile.ZipInfo,
    raw_spans: dict[int, int],
) -> bool:
    span = raw_spans.get(item.header_offset)
    if span is None or source.fp is None or target.fp is None:
        return False

    copied = copy(item)
    if _should_store_without_deflate(copied.filename):
        return False

    target.fp.seek(target.start_dir)
    copied.header_offset = target.fp.tell()
    source.fp.seek(item.header_offset)
    remaining = span
    while remaining:
        chunk = source.fp.read(min(1024 * 1024, remaining))
        if not chunk:
            raise zipfile.BadZipFile(f"could not copy raw ZIP member {item.filename}")
        target.fp.write(chunk)
        remaining -= len(chunk)
    target.start_dir = target.fp.tell()
    target.filelist.append(copied)
    target.NameToInfo[copied.filename] = copied
    target._didModify = True
    return True


def _copy_zip_info_for_payload(item: zipfile.ZipInfo) -> zipfile.ZipInfo:
    copied = copy(item)
    if _should_store_without_deflate(copied.filename):
        copied.compress_type = zipfile.ZIP_STORED
    return copied


def _should_store_without_deflate(filename: str) -> bool:
    lower_name = filename.lower()
    return any(
        lower_name.endswith(extension)
        for extension in _PRECOMPRESSED_EXTENSIONS
    )


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
