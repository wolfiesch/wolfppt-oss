"""Core document property facade and XML serialization helpers."""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import package_part_content_type


CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
DCMITYPE_NS = "http://purl.org/dc/dcmitype/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("cp", CP_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("dcterms", DCTERMS_NS)
ET.register_namespace("dcmitype", DCMITYPE_NS)
ET.register_namespace("xsi", XSI_NS)

CORE_PROPERTIES_PARTNAME = "docProps/core.xml"
_CORE_PROPERTIES_CONTENT_TYPE = "application/vnd.openxmlformats-package.core-properties+xml"
_CORE_PROPERTY_STRING_LIMIT = 255
_CORE_PROPERTY_TEXT_TAGS = {
    "title": (DC_NS, "title"),
    "subject": (DC_NS, "subject"),
    "author": (DC_NS, "creator"),
    "keywords": (CP_NS, "keywords"),
    "comments": (DC_NS, "description"),
    "last_modified_by": (CP_NS, "lastModifiedBy"),
    "category": (CP_NS, "category"),
    "content_status": (CP_NS, "contentStatus"),
    "identifier": (DC_NS, "identifier"),
    "language": (DC_NS, "language"),
    "version": (CP_NS, "version"),
}
_CORE_PROPERTY_DATETIME_TAGS = {
    "created": (DCTERMS_NS, "created"),
    "modified": (DCTERMS_NS, "modified"),
    "last_printed": (CP_NS, "lastPrinted"),
}


class CoreProperties:
    """python-pptx-style core document properties facade."""

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation
        self._values = read_core_properties(presentation.path)

    @property
    def partname(self) -> str:
        return f"/{CORE_PROPERTIES_PARTNAME}"

    @property
    def content_type(self) -> str:
        content_type = package_part_content_type(self._presentation.path, self.partname)
        return content_type or _CORE_PROPERTIES_CONTENT_TYPE

    @property
    def blob(self) -> bytes:
        return serialize_core_properties(self._values)

    @property
    def part(self) -> "CoreProperties":
        return self

    @property
    def package(self) -> Any:
        return self._presentation

    @property
    def title(self) -> str:
        return self._text_property("title")

    @title.setter
    def title(self, value: Any) -> None:
        self._set_text_property("title", value)

    @property
    def subject(self) -> str:
        return self._text_property("subject")

    @subject.setter
    def subject(self, value: Any) -> None:
        self._set_text_property("subject", value)

    @property
    def author(self) -> str:
        return self._text_property("author")

    @author.setter
    def author(self, value: Any) -> None:
        self._set_text_property("author", value)

    @property
    def keywords(self) -> str:
        return self._text_property("keywords")

    @keywords.setter
    def keywords(self, value: Any) -> None:
        self._set_text_property("keywords", value)

    @property
    def comments(self) -> str:
        return self._text_property("comments")

    @comments.setter
    def comments(self, value: Any) -> None:
        self._set_text_property("comments", value)

    @property
    def last_modified_by(self) -> str:
        return self._text_property("last_modified_by")

    @last_modified_by.setter
    def last_modified_by(self, value: Any) -> None:
        self._set_text_property("last_modified_by", value)

    @property
    def category(self) -> str:
        return self._text_property("category")

    @category.setter
    def category(self, value: Any) -> None:
        self._set_text_property("category", value)

    @property
    def content_status(self) -> str:
        return self._text_property("content_status")

    @content_status.setter
    def content_status(self, value: Any) -> None:
        self._set_text_property("content_status", value)

    @property
    def identifier(self) -> str:
        return self._text_property("identifier")

    @identifier.setter
    def identifier(self, value: Any) -> None:
        self._set_text_property("identifier", value)

    @property
    def language(self) -> str:
        return self._text_property("language")

    @language.setter
    def language(self, value: Any) -> None:
        self._set_text_property("language", value)

    @property
    def version(self) -> str:
        return self._text_property("version")

    @version.setter
    def version(self, value: Any) -> None:
        self._set_text_property("version", value)

    @property
    def revision(self) -> int:
        return int(self._values.get("revision") or 0)

    @revision.setter
    def revision(self, value: Any) -> None:
        if not isinstance(value, int) or value < 1:
            raise ValueError(f"revision property requires positive int, got '{value}'")
        if int(value) == self.revision:
            return
        self._values["revision"] = int(value)
        self._queue_edit()

    @property
    def created(self) -> datetime | None:
        return _core_property_datetime_value(self._values.get("created"))

    @created.setter
    def created(self, value: datetime) -> None:
        self._set_datetime_property("created", value)

    @property
    def modified(self) -> datetime | None:
        return _core_property_datetime_value(self._values.get("modified"))

    @modified.setter
    def modified(self, value: datetime) -> None:
        self._set_datetime_property("modified", value)

    @property
    def last_printed(self) -> datetime | None:
        return _core_property_datetime_value(self._values.get("last_printed"))

    @last_printed.setter
    def last_printed(self, value: datetime) -> None:
        self._set_datetime_property("last_printed", value)

    def _text_property(self, name: str) -> str:
        return str(self._values.get(name) or "")

    def _set_text_property(self, name: str, value: Any) -> None:
        text = str(value)
        if len(text) > _CORE_PROPERTY_STRING_LIMIT:
            raise ValueError(
                "exceeded 255 char limit for property, got:\n\n"
                f"{text!r}"
            )
        if text == self._text_property(name):
            return
        self._values[name] = text
        self._queue_edit()

    def _set_datetime_property(self, name: str, value: datetime) -> None:
        if not isinstance(value, datetime):
            raise ValueError(
                "property requires <type 'datetime.datetime'> object, "
                f"got {type(value)!r}"
            )
        normalized = _naive_utc_datetime(value)
        if normalized == self._values.get(name):
            return
        self._values[name] = normalized
        self._queue_edit()

    def _queue_edit(self) -> None:
        self._presentation._queue_core_properties(self._values)


def read_core_properties(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as package:
            root = ET.fromstring(package.read(CORE_PROPERTIES_PARTNAME))
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return _default_core_properties()
    values = _default_core_properties()
    for name, (namespace, local_name) in _CORE_PROPERTY_TEXT_TAGS.items():
        element = root.find(f"{{{namespace}}}{local_name}")
        values[name] = "" if element is None else element.text or ""
    revision = root.find(f"{{{CP_NS}}}revision")
    if revision is not None and revision.text:
        try:
            values["revision"] = int(revision.text)
        except ValueError:
            values["revision"] = 0
    for name, (namespace, local_name) in _CORE_PROPERTY_DATETIME_TAGS.items():
        element = root.find(f"{{{namespace}}}{local_name}")
        values[name] = _parse_core_property_datetime(
            None if element is None else element.text
        )
    return values


def serialize_core_properties(values: dict[str, Any]) -> bytes:
    root = ET.Element(f"{{{CP_NS}}}coreProperties")
    for name in [
        "title",
        "subject",
        "author",
        "keywords",
        "comments",
        "last_modified_by",
        "revision",
        "created",
        "modified",
        "category",
        "content_status",
        "identifier",
        "language",
        "version",
        "last_printed",
    ]:
        if name == "revision":
            element = ET.SubElement(root, f"{{{CP_NS}}}revision")
            element.text = str(values.get("revision") or 0)
            continue
        if name in _CORE_PROPERTY_TEXT_TAGS:
            text = str(values.get(name) or "")
            if not text and name in {
                "content_status",
                "identifier",
                "language",
                "version",
            }:
                continue
            namespace, local_name = _CORE_PROPERTY_TEXT_TAGS[name]
            element = ET.SubElement(root, f"{{{namespace}}}{local_name}")
            element.text = text
            continue
        if name in _CORE_PROPERTY_DATETIME_TAGS:
            value = _core_property_datetime_value(values.get(name))
            if value is None:
                continue
            namespace, local_name = _CORE_PROPERTY_DATETIME_TAGS[name]
            element = ET.SubElement(root, f"{{{namespace}}}{local_name}")
            if name in {"created", "modified"}:
                element.set(f"{{{XSI_NS}}}type", "dcterms:W3CDTF")
            element.text = _format_core_property_datetime(value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _default_core_properties() -> dict[str, Any]:
    values: dict[str, Any] = {name: "" for name in _CORE_PROPERTY_TEXT_TAGS}
    values["revision"] = 1
    values["created"] = None
    values["modified"] = None
    values["last_printed"] = None
    return values


def _parse_core_property_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _naive_utc_datetime(parsed)


def _core_property_datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return None


def _naive_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(microsecond=0)
    return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)


def _format_core_property_datetime(value: datetime) -> str:
    return f"{_naive_utc_datetime(value).isoformat()}Z"
