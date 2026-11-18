"""Custom document property facade, XML serialization, and type models."""

from __future__ import annotations

import copy
import math
import re
import uuid
import zipfile
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import package_part_content_type

CUSTPROPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
VTYPES_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
STRICT_CUSTPROPS_NS = "http://purl.oclc.org/ooxml/officeDocument/customProperties"
STRICT_VTYPES_NS = "http://purl.oclc.org/ooxml/officeDocument/docPropsVTypes"
STRICT_CUSTOM_PROPERTIES_REL_TYPE = (
    "http://purl.oclc.org/ooxml/officeDocument/relationships/customProperties"
)

CUSTOM_PROPERTIES_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties"
)
CUSTOM_PROPERTIES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.custom-properties+xml"
)
CUSTOM_PROPERTIES_REL_TYPES = (CUSTOM_PROPERTIES_REL_TYPE, STRICT_CUSTOM_PROPERTIES_REL_TYPE)
CUSTOM_PROPERTIES_PARTNAME = "docProps/custom.xml"
CUSTOM_PROPERTY_FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"

INT32_MIN = -2147483648
INT32_MAX = 2147483647
INT64_MIN = -9223372036854775808
INT64_MAX = 9223372036854775807
UINT64_MIN = 0
UINT64_MAX = 18446744073709551615
MAX_PROPERTY_NAME_LENGTH = 255


ET.register_namespace("", CUSTPROPS_NS)
ET.register_namespace("vt", VTYPES_NS)


class CustomPropertiesRefusal(ValueError):
    """Raised when a custom properties part cannot be safely read or rewritten."""


@dataclass(frozen=True)
class UntouchedVariant:
    """An untouched custom property value whose variant type is not mapped to a Python primitive."""

    tag: str
    raw_element: ET.Element

    def __repr__(self) -> str:
        return f"<UntouchedVariant tag={self.tag!r}>"


@dataclass
class CustomPropertyRecord:
    """Internal representation of one custom document property."""

    name: str
    value: Any
    pid: int
    fmtid: str = CUSTOM_PROPERTY_FMTID
    val_type: str = ""
    link_target: str | None = None
    raw_element: ET.Element | None = None

    def copy(self) -> CustomPropertyRecord:
        return CustomPropertyRecord(
            name=self.name,
            value=copy.deepcopy(self.value)
            if isinstance(self.value, UntouchedVariant)
            else self.value,
            pid=self.pid,
            fmtid=self.fmtid,
            val_type=self.val_type,
            link_target=self.link_target,
            raw_element=copy.deepcopy(self.raw_element),
        )


class CustomPropertiesSnapshot(dict[str, Any]):
    """Snapshot of custom properties passed to edit queues and save operations."""

    def __init__(
        self,
        values: dict[str, Any],
        records: dict[str, CustomPropertyRecord],
        part_name: str,
        existing_rel_id: str | None,
    ) -> None:
        super().__init__(values)
        self.records: dict[str, CustomPropertyRecord] = {k: v.copy() for k, v in records.items()}
        self.part_name: str = part_name
        self.existing_rel_id: str | None = existing_rel_id

    def copy(self) -> CustomPropertiesSnapshot:
        return CustomPropertiesSnapshot(
            values=dict(self),
            records={k: v.copy() for k, v in self.records.items()},
            part_name=self.part_name,
            existing_rel_id=self.existing_rel_id,
        )


def _validate_property_name(name: Any) -> str:
    if not isinstance(name, str):
        raise TypeError(f"property name must be str, got {type(name).__name__!r}")
    if not name:
        raise ValueError("property name cannot be empty")
    if len(name) > MAX_PROPERTY_NAME_LENGTH:
        raise ValueError(
            f"property name {name!r} exceeds maximum length of "
            f"{MAX_PROPERTY_NAME_LENGTH} characters"
        )
    if any(ord(char) < 32 for char in name):
        raise ValueError(f"property name contains invalid control characters: {name!r}")
    return name


def _naive_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(microsecond=0)
    return value.astimezone(UTC).replace(tzinfo=None, microsecond=0)


def _validate_and_normalize_value(
    value: Any,
    existing_type: str | None = None,
) -> tuple[Any, str]:
    if isinstance(value, bool):
        return bool(value), "bool"
    if isinstance(value, int):
        int_val = int(value)

        # Preserve loaded ui8 even small on normal value edits; bounds fail explicitly
        if existing_type == "ui8":
            if int_val < UINT64_MIN or int_val > UINT64_MAX:
                raise ValueError(
                    f"integer custom property value {int_val} outside 64-bit unsigned range "
                    f"[{UINT64_MIN}, {UINT64_MAX}]"
                )
            return int_val, "ui8"

        # Preserve loaded i8 even small on normal value edits; bounds fail explicitly
        if existing_type == "i8":
            if int_val < INT64_MIN or int_val > INT64_MAX:
                raise ValueError(
                    f"integer custom property value {int_val} outside 64-bit signed range "
                    f"[{INT64_MIN}, {INT64_MAX}]"
                )
            return int_val, "i8"

        # Preserve loaded i4 if representable in 32-bit signed range
        if existing_type == "i4" and INT32_MIN <= int_val <= INT32_MAX:
            return int_val, "i4"

        # Bounds check against admitted 64-bit integer universe
        if int_val < INT64_MIN or int_val > UINT64_MAX:
            raise ValueError(
                f"integer custom property value {int_val} outside admitted 64-bit range "
                f"[{INT64_MIN}, {UINT64_MAX}]"
            )

        # Choose i4/i8/ui8 by range for new or upgraded values
        if INT32_MIN <= int_val <= INT32_MAX:
            return int_val, "i4"
        if int_val < INT32_MIN:
            return int_val, "i8"
        if int_val <= INT64_MAX:
            return int_val, "i8"
        return int_val, "ui8"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"float custom property value {value} must be finite")
        return float(value), "r8"
    if isinstance(value, str):
        return str(value), "lpwstr"
    if isinstance(value, datetime):
        return _naive_utc_datetime(value), "filetime"
    if isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
        return _naive_utc_datetime(dt), "filetime"
    raise TypeError(f"unsupported custom property value type: {type(value).__name__!r}")


def _profile_namespaces(strict: bool) -> tuple[str, str]:
    """(custom-properties namespace, docPropsVTypes namespace) of one file profile."""
    return (STRICT_CUSTPROPS_NS, STRICT_VTYPES_NS) if strict else (CUSTPROPS_NS, VTYPES_NS)


def read_custom_properties(xml_bytes: bytes) -> dict[str, CustomPropertyRecord]:
    """Parse custom properties XML (transitional or strict) into property records."""
    return read_custom_properties_profile(xml_bytes)[0]


def read_custom_properties_profile(
    xml_bytes: bytes,
) -> tuple[dict[str, CustomPropertyRecord], bool]:
    """Parse custom properties XML into property records and whether the part is strict."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise CustomPropertiesRefusal("custom properties part is malformed XML") from exc

    strict = root.tag == f"{{{STRICT_CUSTPROPS_NS}}}Properties"
    custprops_ns, vt_ns = _profile_namespaces(strict)
    if root.tag != f"{{{custprops_ns}}}Properties":
        raise CustomPropertiesRefusal(f"invalid custom properties root element tag: {root.tag!r}")

    records: dict[str, CustomPropertyRecord] = {}
    seen_pids: set[int] = set()
    seen_names: set[str] = set()

    for child in root:
        if child.tag != f"{{{custprops_ns}}}property":
            raise CustomPropertiesRefusal(
                f"invalid child element in custom properties: {child.tag!r}"
            )

        name = child.attrib.get("name")
        if name is None or not name:
            raise CustomPropertiesRefusal("custom property element has missing or empty name")
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            raise CustomPropertiesRefusal(
                f"custom properties part contains duplicate property name: {name!r}"
            )
        seen_names.add(normalized_name)

        pid_str = child.attrib.get("pid")
        if pid_str is None:
            raise CustomPropertiesRefusal(
                f"custom property {name!r} missing required pid attribute"
            )
        try:
            pid = int(pid_str)
        except ValueError as exc:
            raise CustomPropertiesRefusal(
                f"custom property {name!r} pid is not an integer: {pid_str!r}"
            ) from exc

        if pid <= 1:
            raise CustomPropertiesRefusal(f"custom property {name!r} pid must be >= 2, got {pid}")
        if pid in seen_pids:
            raise CustomPropertiesRefusal(f"custom properties part contains duplicate pid: {pid}")
        seen_pids.add(pid)

        fmtid = child.attrib.get("fmtid", CUSTOM_PROPERTY_FMTID)

        if len(child) != 1:
            raise CustomPropertiesRefusal(
                f"custom property {name!r} must contain exactly one value child element, "
                f"got {len(child)}"
            )

        vt_child = child[0]
        vt_tag = vt_child.tag

        if vt_tag == f"{{{vt_ns}}}lpwstr":
            val_type = "lpwstr"
            value: Any = vt_child.text or ""
        elif vt_tag == f"{{{vt_ns}}}bool":
            val_type = "bool"
            text = (vt_child.text or "").strip().lower()
            if text in ("true", "1"):
                value = True
            elif text in ("false", "0"):
                value = False
            else:
                raise CustomPropertiesRefusal(
                    f"invalid boolean property value in {name!r}: {vt_child.text!r}"
                )
        elif vt_tag in (
            f"{{{vt_ns}}}i4",
            f"{{{vt_ns}}}int",
            f"{{{vt_ns}}}i2",
            f"{{{vt_ns}}}i1",
        ):
            val_type = "i4"
            text = (vt_child.text or "").strip()
            try:
                int_val = int(text)
            except ValueError as exc:
                raise CustomPropertiesRefusal(
                    f"invalid integer property value in {name!r}: {text!r}"
                ) from exc
            if int_val < INT32_MIN or int_val > INT32_MAX:
                raise CustomPropertiesRefusal(
                    f"integer property value in {name!r} out of 32-bit signed range: {int_val}"
                )
            value = int_val
        elif vt_tag == f"{{{vt_ns}}}i8":
            val_type = "i8"
            text = (vt_child.text or "").strip()
            try:
                int_val = int(text)
            except ValueError as exc:
                raise CustomPropertiesRefusal(
                    f"invalid integer property value in {name!r}: {text!r}"
                ) from exc
            if int_val < INT64_MIN or int_val > INT64_MAX:
                raise CustomPropertiesRefusal(
                    f"integer property value in {name!r} out of 64-bit signed range: {int_val}"
                )
            value = int_val
        elif vt_tag == f"{{{vt_ns}}}ui8":
            val_type = "ui8"
            text = (vt_child.text or "").strip()
            try:
                int_val = int(text)
            except ValueError as exc:
                raise CustomPropertiesRefusal(
                    f"invalid unsigned integer property value in {name!r}: {text!r}"
                ) from exc
            if int_val < UINT64_MIN or int_val > UINT64_MAX:
                raise CustomPropertiesRefusal(
                    f"unsigned integer property value in {name!r} out of 64-bit unsigned range: "
                    f"{int_val}"
                )
            value = int_val
        elif vt_tag in (f"{{{vt_ns}}}r8", f"{{{vt_ns}}}r4"):
            val_type = "r8"
            text = (vt_child.text or "").strip()
            try:
                flt_val = float(text)
            except ValueError as exc:
                raise CustomPropertiesRefusal(
                    f"invalid float property value in {name!r}: {text!r}"
                ) from exc
            if not math.isfinite(flt_val):
                raise CustomPropertiesRefusal(
                    f"non-finite float property value in {name!r}: {flt_val}"
                )
            value = flt_val
        elif vt_tag == f"{{{vt_ns}}}filetime":
            val_type = "filetime"
            text = (vt_child.text or "").strip()
            try:
                dt_val = datetime.fromisoformat(text)
                value = _naive_utc_datetime(dt_val)
            except Exception as exc:
                raise CustomPropertiesRefusal(
                    f"invalid filetime datetime value in {name!r}: {text!r}"
                ) from exc
        else:
            val_type = "variant"
            value = UntouchedVariant(tag=vt_tag, raw_element=copy.deepcopy(vt_child))

        records[name] = CustomPropertyRecord(
            name=name,
            value=value,
            pid=pid,
            fmtid=fmtid,
            val_type=val_type,
            link_target=child.get("linkTarget"),
            raw_element=copy.deepcopy(child),
        )

    return records, strict


def _tostring(root: ET.Element, strict: bool) -> bytes:
    """Serialize with the profile's default and vt prefixes, leaving the registry unchanged."""
    custprops_ns, vt_ns = _profile_namespaces(strict)
    ET.register_namespace("", custprops_ns)
    ET.register_namespace("vt", vt_ns)
    try:
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    finally:
        ET.register_namespace("", CUSTPROPS_NS)
        ET.register_namespace("vt", VTYPES_NS)


def serialize_custom_properties(
    records: list[CustomPropertyRecord] | dict[str, Any],
    strict: bool = False,
) -> bytes:
    """Serialize custom property records to standard OpenXML custom properties XML.

    Records without a retained source element are written in the strict namespaces
    when ``strict`` is set; retained elements keep their own.
    """
    custprops_ns, vt_ns = _profile_namespaces(strict)
    root = ET.Element(f"{{{custprops_ns}}}Properties")

    if isinstance(records, dict):
        record_list: list[CustomPropertyRecord] = []
        next_pid = 2
        for k, v in records.items():
            if isinstance(v, CustomPropertyRecord):
                record_list.append(v)
            else:
                norm_val, val_type = _validate_and_normalize_value(v)
                record_list.append(
                    CustomPropertyRecord(
                        name=_validate_property_name(k),
                        value=norm_val,
                        pid=next_pid,
                        fmtid=CUSTOM_PROPERTY_FMTID,
                        val_type=val_type,
                    )
                )
                next_pid += 1
    else:
        record_list = list(records)

    for record in record_list:
        if record.raw_element is not None:
            root.append(copy.deepcopy(record.raw_element))
            continue
        prop_elem = ET.SubElement(
            root,
            f"{{{custprops_ns}}}property",
            {
                "fmtid": record.fmtid,
                "pid": str(record.pid),
                "name": record.name,
            },
        )
        if record.link_target is not None:
            prop_elem.set("linkTarget", record.link_target)
        if record.val_type == "variant" and isinstance(record.value, UntouchedVariant):
            prop_elem.append(copy.deepcopy(record.value.raw_element))
        elif record.val_type == "lpwstr":
            vt_elem = ET.SubElement(prop_elem, f"{{{vt_ns}}}lpwstr")
            vt_elem.text = str(record.value)
        elif record.val_type == "bool":
            vt_elem = ET.SubElement(prop_elem, f"{{{vt_ns}}}bool")
            vt_elem.text = "true" if record.value else "false"
        elif record.val_type == "i4":
            if not isinstance(record.value, int) or isinstance(record.value, bool):
                raise CustomPropertiesRefusal(
                    f"property {record.name!r} with type 'i4' has non-integer value "
                    f"{record.value!r}"
                )
            if record.value < INT32_MIN or record.value > INT32_MAX:
                raise CustomPropertiesRefusal(
                    f"property {record.name!r} with type 'i4' outside 32-bit signed range: "
                    f"{record.value}"
                )
            vt_elem = ET.SubElement(prop_elem, f"{{{vt_ns}}}i4")
            vt_elem.text = str(record.value)
        elif record.val_type == "i8":
            if not isinstance(record.value, int) or isinstance(record.value, bool):
                raise CustomPropertiesRefusal(
                    f"property {record.name!r} with type 'i8' has non-integer value "
                    f"{record.value!r}"
                )
            if record.value < INT64_MIN or record.value > INT64_MAX:
                raise CustomPropertiesRefusal(
                    f"property {record.name!r} with type 'i8' outside 64-bit signed range: "
                    f"{record.value}"
                )
            vt_elem = ET.SubElement(prop_elem, f"{{{vt_ns}}}i8")
            vt_elem.text = str(record.value)
        elif record.val_type == "ui8":
            if not isinstance(record.value, int) or isinstance(record.value, bool):
                raise CustomPropertiesRefusal(
                    f"property {record.name!r} with type 'ui8' has non-integer value "
                    f"{record.value!r}"
                )
            if record.value < UINT64_MIN or record.value > UINT64_MAX:
                raise CustomPropertiesRefusal(
                    f"property {record.name!r} with type 'ui8' outside 64-bit unsigned range: "
                    f"{record.value}"
                )
            vt_elem = ET.SubElement(prop_elem, f"{{{vt_ns}}}ui8")
            vt_elem.text = str(record.value)
        elif record.val_type == "r8":
            vt_elem = ET.SubElement(prop_elem, f"{{{vt_ns}}}r8")
            vt_elem.text = str(record.value)
        elif record.val_type == "filetime":
            vt_elem = ET.SubElement(prop_elem, f"{{{vt_ns}}}filetime")
            norm_dt = _naive_utc_datetime(record.value)
            vt_elem.text = f"{norm_dt.isoformat()}Z"
        else:
            raise CustomPropertiesRefusal(
                f"cannot serialize property {record.name!r} with unknown type {record.val_type!r}"
            )

    return _tostring(root, strict)


class CustomProperties(MutableMapping[str, Any]):
    """Mapping-like facade for presentation custom document properties."""

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation
        self._source_path: Path | None = getattr(presentation, "path", None)
        if self._source_path is None:
            self._source_path = getattr(presentation, "_source_path", None)
        self._records: dict[str, CustomPropertyRecord] = {}
        self._part_name: str = CUSTOM_PROPERTIES_PARTNAME
        self._existing_rel_id: str | None = None
        self._max_pid: int = 1
        self._strict = False
        self._load()

    def _load(self) -> None:
        from .custom_property_edits import resolve_custom_properties_part
        from .extended_property_edits import package_is_strict

        self._strict = False
        if self._source_path is None or not Path(self._source_path).is_file():
            self._records = {}
            self._part_name = CUSTOM_PROPERTIES_PARTNAME
            self._existing_rel_id = None
            self._max_pid = 1
            return

        with zipfile.ZipFile(self._source_path) as package:
            rel_id, part_name = resolve_custom_properties_part(package)
            self._existing_rel_id = rel_id
            if part_name is not None:
                self._part_name = part_name
                payload = package.read(part_name)
                self._records, self._strict = read_custom_properties_profile(payload)
                self._max_pid = max((r.pid for r in self._records.values()), default=1)
            else:
                self._part_name = CUSTOM_PROPERTIES_PARTNAME
                self._records = {}
                self._max_pid = 1
                self._strict = package_is_strict(package)

    @property
    def partname(self) -> str:
        """The normalized package part name (e.g. ``/docProps/custom.xml``)."""
        return f"/{self._part_name.lstrip('/')}"

    @property
    def content_type(self) -> str:
        """The declared content type of the custom properties part."""
        if (
            self._source_path
            and Path(self._source_path).is_file()
            and self._existing_rel_id is not None
        ):
            ct = package_part_content_type(Path(self._source_path), self.partname)
            if ct and ct != "application/xml":
                return ct
        return CUSTOM_PROPERTIES_CONTENT_TYPE

    @property
    def blob(self) -> bytes:
        """Serialized XML bytes of the current custom properties."""
        return serialize_custom_properties(list(self._records.values()), strict=self._strict)

    @property
    def part(self) -> CustomProperties:
        """python-pptx-compatible part reference."""
        return self

    @property
    def package(self) -> Any:
        """The owning presentation package."""
        return self._presentation

    def _snapshot(self) -> CustomPropertiesSnapshot:
        values = {k: v.value for k, v in self._records.items()}
        return CustomPropertiesSnapshot(
            values=values,
            records=self._records,
            part_name=self._part_name,
            existing_rel_id=self._existing_rel_id,
        )

    def _queue_edit(self) -> None:
        queue_fn = getattr(self._presentation, "_queue_custom_properties", None)
        if callable(queue_fn):
            queue_fn(self._snapshot())

    def __getitem__(self, key: str) -> Any:
        if not isinstance(key, str):
            raise KeyError(key)
        record = self._records.get(key)
        if record is None:
            raise KeyError(key)
        return record.value

    def __setitem__(self, key: str, value: Any) -> None:
        norm_key = _validate_property_name(key)
        existing = self._records.get(norm_key)
        if existing is None and any(
            name.casefold() == norm_key.casefold() for name in self._records
        ):
            raise CustomPropertiesRefusal(
                f"custom properties contain duplicate property name: {norm_key!r}"
            )
        existing_type = existing.val_type if existing is not None else None
        norm_val, val_type = _validate_and_normalize_value(value, existing_type=existing_type)

        if existing is not None:
            if existing.val_type == "variant":
                raise CustomPropertiesRefusal(
                    f"cannot destructively rewrite unsupported property variant {norm_key!r}"
                )
            existing.value = norm_val
            existing.val_type = val_type
            existing.raw_element = None
        else:
            self._max_pid += 1
            new_record = CustomPropertyRecord(
                name=norm_key,
                value=norm_val,
                pid=self._max_pid,
                fmtid=CUSTOM_PROPERTY_FMTID,
                val_type=val_type,
            )
            self._records[norm_key] = new_record

        self._queue_edit()

    def __delitem__(self, key: str) -> None:
        if not isinstance(key, str) or key not in self._records:
            raise KeyError(key)
        del self._records[key]
        self._queue_edit()

    def __iter__(self) -> Iterator[str]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, key: object) -> bool:
        return key in self._records

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self) -> list[str]:  # type: ignore[override]
        return list(self._records.keys())

    def values(self) -> list[Any]:  # type: ignore[override]
        return [r.value for r in self._records.values()]

    def items(self) -> list[tuple[str, Any]]:  # type: ignore[override]
        return [(k, r.value) for k, r in self._records.items()]

    def clear(self) -> None:
        if self._records:
            self._records.clear()
            self._queue_edit()

    def pop(self, key: str, default: Any = ...) -> Any:
        try:
            val = self[key]
            del self[key]
            return val
        except KeyError:
            if default is not ...:
                return default
            raise

    def update(self, other: Any = (), **kwds: Any) -> None:  # type: ignore[override]
        if hasattr(other, "items"):
            for k, v in other.items():
                self[k] = v
        else:
            for k, v in other:
                self[k] = v
        for k, v in kwds.items():
            self[k] = v

    def __repr__(self) -> str:
        return f"<CustomProperties count={len(self)} keys={list(self.keys())}>"


# ---------------------------------------------------------------------------
# Custom XML parts (customer data) at presentation, slide and shape level
# ---------------------------------------------------------------------------

CUSTOM_XML_DS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/customXml"
STRICT_CUSTOM_XML_DS_NS = "http://purl.oclc.org/ooxml/officeDocument/customXml"
CUSTOM_XML_PROPERTIES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.customXmlProperties+xml"
)
CUSTOM_XML_DATA_CONTENT_TYPE = "application/xml"
_GUID = re.compile(r"\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}")


@dataclass(frozen=True)
class CustomXmlPart:
    """One custom XML part with its item properties (``ds:datastoreItem``).

    ``part_name`` and ``rel_id`` are None until the part is saved. Saved data
    is the staged XML serialization, so compare it as XML, not as bytes.
    """

    part_name: str | None
    rel_id: str | None
    xml: bytes
    item_id: str | None
    schema_refs: tuple[str, ...]


class _CustomXmlRoots(dict):
    """Lifecycle XML roots plus items detached during this private save."""

    def __init__(self) -> None:
        super().__init__()
        self.detached_items: set[str] = set()


def _prune_detached_custom_xml(package: Any, roots: _CustomXmlRoots) -> set[str]:
    from .package_parts import rels_part_for_package_part

    removed: set[str] = set()
    properties: set[str] = set()
    for item in roots.detached_items:
        if _references_to(package, roots, item):
            continue
        props, _, _ = _read_item_properties(
            package, item, roots, _custom_xml_namespace(package, roots, item)
        )
        removed.update((item, rels_part_for_package_part(item)))
        if props is not None:
            properties.add(props)
    removed.update(
        props for props in properties if not _references_to(package, roots, props, removed)
    )
    if removed:
        types = _content_types(package, roots)
        for override in list(types):
            if (override.get("PartName") or "").lstrip("/") in removed:
                types.remove(override)
        for part in removed:
            roots.pop(part, None)
    return removed


def _custom_xml_namespace(package: Any, roots: dict, item: str) -> str:
    from .package_parts import R_NS
    from .presentation_tags import relationships
    from .xml_helpers import STRICT_R_NS

    rels = relationships(package, item, roots, read_only=True)
    for rel in rels:
        if rel.get("Type") == STRICT_R_NS + "/customXmlProps":
            return STRICT_R_NS
    return R_NS


def _datastore_ids(package: Any, roots: dict) -> dict[str, str]:
    """Reject ambiguous identities across distinct items, including staged ones."""
    from .package_parts import resolve_package_target
    from .presentation_tags import parse_xml

    ids: dict[str, str] = {}
    for name in sorted(set(package.namelist()) | roots.keys()):
        if not name.endswith(".rels"):
            continue
        rels = roots.get(name)
        if rels is None:
            rels = parse_xml(package.read(name), read_only=True)
        item = name.replace("_rels/", "")[: -len(".rels")]
        for rel in rels:
            if not (rel.get("Type") or "").endswith("/customXmlProps"):
                continue
            props = resolve_package_target(item, rel.get("Target", ""))
            root = roots.get(props)
            if root is None:
                root = parse_xml(package.read(props), read_only=True)
            ns = root.tag[1:].partition("}")[0]
            value = root.get(f"{{{ns}}}itemID")
            if value is None:
                continue
            value = _item_id(value)
            if value in ids and ids[value] != item:
                raise CustomPropertiesRefusal(f"duplicate custom XML ds:itemID: {value}")
            ids[value] = item
    return ids


@dataclass(frozen=True, eq=False)
class _CustomXmlOperation:
    """Immutable queued add / replace / remove; equality is identity."""

    kind: str
    ref: Any
    target: str | None = None
    xml: bytes | None = None
    item_id: str | None = None
    schema_refs: tuple[str, ...] | None = None

    def validate(self) -> None:
        self.ref.validate()

    def apply(self, package: Any, roots: dict, source: str) -> None:
        _apply_custom_xml_operation(self, package, roots)


def _xml_payload(xml: Any) -> bytes:
    from .presentation_tags import parse_xml

    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    if not isinstance(xml, (bytes, bytearray)):
        raise TypeError("custom XML data must be bytes or str")
    payload = bytes(xml)
    try:
        parse_xml(payload)
    except ET.ParseError as exc:
        raise CustomPropertiesRefusal("custom XML data is not well-formed XML") from exc
    return payload


def _schema_refs(schema_refs: Any) -> tuple[str, ...]:
    from .presentation_tags import xml_string

    if isinstance(schema_refs, str) or not isinstance(schema_refs, (tuple, list)):
        raise TypeError("schema_refs must be a tuple or list of URI strings")
    refs = tuple(xml_string(uri, "schema reference") for uri in schema_refs)
    if any(not uri for uri in refs):
        raise CustomPropertiesRefusal("schema references must be non-empty URIs")
    return refs


def _item_id(item_id: Any) -> str:
    if item_id is None:
        return "{" + str(uuid.uuid4()).upper() + "}"
    if not isinstance(item_id, str):
        raise TypeError("item_id must be a GUID string")
    normalized = item_id.upper()
    if not normalized.startswith("{"):
        normalized = "{" + normalized + "}"
    if not _GUID.fullmatch(normalized):
        raise CustomPropertiesRefusal(f"item_id {item_id!r} is not a GUID")
    return normalized


def _ds_namespace(r_ns: str) -> str:
    from .xml_helpers import STRICT_R_NS

    return STRICT_CUSTOM_XML_DS_NS if r_ns == STRICT_R_NS else CUSTOM_XML_DS_NS


def _read_item_properties(
    package: Any, item: str, roots: dict, r_ns: str, *, read_only: bool = True
) -> tuple[str | None, str | None, tuple[str, ...]]:
    """Return (props part, itemID, schema reference URIs) of one item.

    ``roots`` must hold one parse intent: read-only inspection or staging.
    """
    from .presentation_tags import parse_xml, relationship_target, relationships

    props = relationship_target(
        package,
        item,
        relationships(package, item, roots, read_only=read_only),
        rel_type=r_ns + "/customXmlProps",
    )
    if props is None:
        return None, None, ()
    root = roots.get(props)
    if root is None:
        root = parse_xml(package.read(props), read_only=True)
    ns = next(
        (
            n
            for n in (CUSTOM_XML_DS_NS, STRICT_CUSTOM_XML_DS_NS)
            if root.tag == f"{{{n}}}datastoreItem"
        ),
        None,
    )
    if ns is None:
        raise CustomPropertiesRefusal(f"invalid custom XML properties root in {props}")
    refs = tuple(
        ref.get(f"{{{ns}}}uri", "") for ref in root.findall(f"{{{ns}}}schemaRefs/{{{ns}}}schemaRef")
    )
    return props, root.get(f"{{{ns}}}itemID"), refs


def _owner_references(
    package: Any, part: str, root: Any, ref: Any, roots: dict
) -> list[tuple[str, str]]:
    """(relationship id, item part) of the owner's custom XML, document order.

    Presentation scope lists every customXml relationship of the presentation
    part; slide and shape scope list the ``p:custData`` references of their
    ``p:custDataLst``.
    """
    from .package_parts import P_NS, R_NS, resolve_package_target
    from .presentation_tags import (
        _tag_container,
        relationship_target,
        relationships,
    )
    from .xml_helpers import STRICT_R_NS, ooxml_namespace

    r_ns = ooxml_namespace(root, R_NS)
    rels = relationships(package, part, roots, read_only=True)
    if ref.owner is ref.presentation:
        result = []
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
            if rel.get("Type") not in (R_NS + "/customXml", STRICT_R_NS + "/customXml"):
                continue
            if rel.get("TargetMode", "Internal") != "Internal":
                raise CustomPropertiesRefusal("external custom XML relationship")
            result.append((rel.get("Id"), resolve_package_target(part, rel.get("Target", ""))))
        return result
    container = _tag_container(root, ref.shape_id)
    if container is None:
        return []
    result = []
    for cust in container.findall(f"{{{ooxml_namespace(root, P_NS)}}}custData"):
        rel_id = cust.get(f"{{{r_ns}}}id")
        if not rel_id:
            raise CustomPropertiesRefusal("custom data reference has no relationship id")
        target = relationship_target(
            package, part, rels, rel_type=r_ns + "/customXml", rel_id=rel_id
        )
        result.append((rel_id, target))
    return result


def _next_item_names(package: Any, roots: dict) -> tuple[str, str]:
    names = set(package.namelist()) | roots.keys()
    index = 1
    while any(
        name in names
        for name in (
            f"customXml/item{index}.xml",
            f"customXml/itemProps{index}.xml",
            f"customXml/_rels/item{index}.xml.rels",
        )
    ):
        index += 1
    return f"customXml/item{index}.xml", f"customXml/itemProps{index}.xml"


def _content_types(package: Any, roots: dict) -> ET.Element:
    from .presentation_tags import parse_xml

    return roots.setdefault("[Content_Types].xml", parse_xml(package.read("[Content_Types].xml")))


def _register_content_type(package: Any, roots: dict, part: str, content_type: str) -> None:
    types = _content_types(package, roots)
    partname = "/" + part
    for override in types.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.get("PartName", "").casefold() == partname.casefold():
            override.set("ContentType", content_type)
            return
    extension = part.rpartition(".")[2].casefold()
    if any(
        default.get("Extension", "").casefold() == extension
        and default.get("ContentType") == content_type
        for default in types.findall(f"{{{CONTENT_TYPES_NS}}}Default")
    ):
        return
    ET.SubElement(
        types,
        f"{{{CONTENT_TYPES_NS}}}Override",
        {"PartName": partname, "ContentType": content_type},
    )


def _add_relationship(rels: ET.Element, rel_type: str, target: str) -> str:
    ids = {rel.get("Id") for rel in rels}
    index = 1
    while f"rId{index}" in ids:
        index += 1
    ET.SubElement(
        rels,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": f"rId{index}", "Type": rel_type, "Target": target},
    )
    return f"rId{index}"


def _write_item_properties(
    package: Any,
    roots: dict,
    item: str,
    r_ns: str,
    item_id: str | None,
    schema_refs: tuple[str, ...],
) -> None:
    """Create or rewrite the ``ds:datastoreItem`` related from ``item``."""
    from .presentation_tags import parse_xml, relationship_target, relationships

    rels = relationships(package, item, roots)
    props = relationship_target(package, item, rels, rel_type=r_ns + "/customXmlProps")
    if props is not None:
        root = roots.setdefault(props, parse_xml(package.read(props)))
        ns = root.tag[1:].partition("}")[0]
        item_id = root.get(f"{{{ns}}}itemID") if item_id is None else item_id
        for child in list(root):
            if child.tag == f"{{{ns}}}schemaRefs":
                root.remove(child)
    else:
        index = item.rpartition("/item")[2]
        props = f"customXml/itemProps{index}"
        if props in set(package.namelist()) | roots.keys():
            props = _next_item_names(package, roots)[1]
        ns = _ds_namespace(r_ns)
        root = ET.Element(f"{{{ns}}}datastoreItem", {"xmlns:ds": ns})
        roots[props] = root
        _add_relationship(rels, r_ns + "/customXmlProps", props.rpartition("/")[2])
        _register_content_type(package, roots, props, CUSTOM_XML_PROPERTIES_CONTENT_TYPE)
    root.set(f"{{{ns}}}itemID", _item_id(item_id))
    refs = ET.Element(f"{{{ns}}}schemaRefs")
    for uri in schema_refs:
        ET.SubElement(refs, f"{{{ns}}}schemaRef", {f"{{{ns}}}uri": uri})
    root.insert(0, refs)


def _references_to(package: Any, roots: dict, part: str, excluded: set[str] = frozenset()) -> int:
    from .package_parts import resolve_package_target
    from .presentation_tags import parse_xml

    count = 0
    for name in set(package.namelist()) | roots.keys():
        if name in excluded:
            continue
        if not name.endswith(".rels") or "_rels/" not in name:
            continue
        rels = roots.get(name)
        if rels is None:
            rels = parse_xml(package.read(name), read_only=True)
        source = name.replace("_rels/", "")[: -len(".rels")]
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
            if rel.get("TargetMode", "Internal") == "Internal" and (
                resolve_package_target(source, rel.get("Target", "")) == part
            ):
                count += 1
    return count


def _apply_custom_xml_operation(operation: _CustomXmlOperation, package: Any, roots: dict) -> None:
    import posixpath

    from .package_parts import P_NS, R_NS
    from .presentation_tags import (
        _tag_container,
        one,
        parse_xml,
        relationship_target,
        relationships,
    )
    from .xml_helpers import ooxml_namespace

    ref = operation.ref
    staged = getattr(ref.presentation, "_staged_slide_materializations", None) or {}
    source, shape_id = ref.resolve(staged, None)
    root = roots.setdefault(source, parse_xml(package.read(source)))
    p_ns = ooxml_namespace(root, P_NS)
    r_ns = ooxml_namespace(root, R_NS)
    rel_type = r_ns + "/customXml"
    rels = relationships(package, source, roots)
    if operation.kind in ("add", "bind"):
        if operation.kind == "bind":
            item = operation.target
            if item not in set(package.namelist()) | roots.keys():
                raise CustomPropertiesRefusal("shared custom XML item is no longer present")
        else:
            if operation.item_id in _datastore_ids(package, roots):
                raise CustomPropertiesRefusal(
                    f"duplicate custom XML ds:itemID: {operation.item_id}"
                )
            item, _ = _next_item_names(package, roots)
            roots[item] = parse_xml(operation.xml)
            _register_content_type(package, roots, item, CUSTOM_XML_DATA_CONTENT_TYPE)
            _write_item_properties(
                package, roots, item, r_ns, operation.item_id, operation.schema_refs or ()
            )
        rel_id = _add_relationship(
            rels, rel_type, posixpath.relpath(item, posixpath.dirname(source))
        )
        if ref.owner is not ref.presentation:
            container = _tag_container(root, shape_id, create=True)
            cust = ET.Element(f"{{{p_ns}}}custData", {f"{{{r_ns}}}id": rel_id})
            tags = one(container, f"{{{P_NS}}}tags")
            container.insert(len(container) if tags is None else list(container).index(tags), cust)
        return
    item = relationship_target(package, source, rels, rel_type=rel_type, rel_id=operation.target)
    relationship = next(
        r for r in rels.findall(f"{{{PKG_REL_NS}}}Relationship") if r.get("Id") == operation.target
    )
    shared_relationship = (
        sum(
            node.get(f"{{{r_ns}}}id") == operation.target
            for node in root.iter(f"{{{p_ns}}}custData")
        )
        > 1
    )
    if operation.kind == "remove":
        container = (
            one(root, f"{{{P_NS}}}custDataLst")
            if ref.owner is ref.presentation
            else _tag_container(root, shape_id)
        )
        for cust in [] if container is None else list(container):
            if cust.tag == f"{{{p_ns}}}custData" and cust.get(f"{{{r_ns}}}id") == operation.target:
                container.remove(cust)
        if not any(
            node.get(f"{{{r_ns}}}id") == operation.target
            for node in root.iter(f"{{{p_ns}}}custData")
        ):
            rels.remove(relationship)
        roots.detached_items.add(item)
        return
    if shared_relationship or _references_to(package, roots, item) > 1:
        # Copy on write: other owners keep the shared part unchanged.
        _, _, refs = _read_item_properties(package, item, roots, r_ns, read_only=False)
        data = operation.xml if operation.xml is not None else package.read(item)
        copied, _ = _next_item_names(package, roots)
        roots[copied] = parse_xml(data)
        _register_content_type(package, roots, copied, CUSTOM_XML_DATA_CONTENT_TYPE)
        _write_item_properties(
            package,
            roots,
            copied,
            r_ns,
            None,
            refs if operation.schema_refs is None else operation.schema_refs,
        )
        target = posixpath.relpath(copied, posixpath.dirname(source))
        if shared_relationship:
            rel_id = _add_relationship(rels, rel_type, target)
            container = _tag_container(root, shape_id)
            for node in container.findall(f"{{{p_ns}}}custData"):
                if node.get(f"{{{r_ns}}}id") == operation.target:
                    node.set(f"{{{r_ns}}}id", rel_id)
        else:
            relationship.set("Target", target)
        return
    if operation.xml is not None:
        roots[item] = parse_xml(operation.xml)
    if operation.schema_refs is not None:
        _write_item_properties(package, roots, item, r_ns, None, operation.schema_refs)


@dataclass
class _Entry:
    rel_id: str | None
    part_name: str | None
    xml: bytes
    item_id: str | None
    schema_refs: tuple[str, ...]
    operation: _CustomXmlOperation | None = None

    def public(self) -> CustomXmlPart:
        return CustomXmlPart(self.part_name, self.rel_id, self.xml, self.item_id, self.schema_refs)


class CustomXmlPartCollection:
    """Custom XML parts of the presentation, a slide or a shape.

    Reads reflect the package plus queued edits. Edits are staged with the
    presentation view lifecycle and written on the next save. Shapes added
    in this session must be saved before custom XML can be attached.
    """

    def __init__(self, presentation: Any, owner: Any) -> None:
        from .presentation_tags import OwnerRef

        OwnerRef.capture(presentation, owner)
        self._presentation = presentation
        self._owner = owner

    def _ref(self, *, mutating: bool = False) -> Any:
        from .presentation_tags import OwnerRef

        ref = OwnerRef.capture(self._presentation, self._owner)
        if mutating and ref.owner is not ref.part_owner and ref.shape_id is None:
            raise CustomPropertiesRefusal(
                "save the presentation before attaching custom XML to a new shape"
            )
        return ref

    def _stored(self, ref: Any) -> list[_Entry]:
        from .package_parts import R_NS, open_package_source
        from .presentation_tags import parse_xml
        from .xml_helpers import ooxml_namespace

        part = ref.source_part()
        if part is None:
            return []
        entries = []
        with open_package_source(self._presentation._source_path) as package:
            roots: dict = {}
            _datastore_ids(package, roots)
            root = parse_xml(package.read(part), read_only=True)
            r_ns = ooxml_namespace(root, R_NS)
            for rel_id, item in _owner_references(package, part, root, ref, roots):
                _, item_id, refs = _read_item_properties(package, item, roots, r_ns)
                entries.append(_Entry(rel_id, "/" + item, package.read(item), item_id, refs))
        return entries

    def _entries(self) -> list[_Entry]:
        ref = self._ref()
        entries = self._stored(ref)
        for operation in self._presentation.view_state.pending_operations():
            if not isinstance(operation, _CustomXmlOperation):
                continue
            if operation.ref.owner is not self._owner:
                continue
            if operation.kind in ("add", "bind"):
                entries.append(
                    _Entry(
                        None,
                        None if operation.kind == "add" else "/" + operation.target,
                        operation.xml,
                        operation.item_id,
                        operation.schema_refs or (),
                        operation,
                    )
                )
                continue
            entry = next(e for e in entries if e.rel_id == operation.target)
            if operation.kind == "remove":
                entries.remove(entry)
                continue
            if operation.xml is not None:
                entry.xml = operation.xml
            if operation.schema_refs is not None:
                entry.schema_refs = operation.schema_refs
        return entries

    def __len__(self) -> int:
        return len(self._entries())

    def __iter__(self) -> Iterator[CustomXmlPart]:
        return iter([entry.public() for entry in self._entries()])

    def __getitem__(self, index: int) -> CustomXmlPart:
        return self._entries()[index].public()

    def add(self, xml: Any, *, schema_refs: Any = (), item_id: str | None = None) -> CustomXmlPart:
        """Queue XML data, or bind a saved item from this deck to another owner."""
        ref = self._ref(mutating=True)
        if isinstance(xml, CustomXmlPart):
            if item_id is not None or schema_refs:
                raise CustomPropertiesRefusal("shared custom XML binding cannot redefine metadata")
            if xml.part_name is None:
                raise CustomPropertiesRefusal("save custom XML before binding it to another owner")
            from .package_parts import open_package_source

            item = xml.part_name.lstrip("/")
            with open_package_source(self._presentation._source_path) as package:
                roots: dict = {}
                ids = _datastore_ids(package, roots)
                if xml.item_id is None or ids.get(_item_id(xml.item_id)) != item:
                    raise CustomPropertiesRefusal(
                        "shared custom XML item does not belong to this deck"
                    )
                _, stored_id, refs = _read_item_properties(
                    package, item, roots, _custom_xml_namespace(package, roots, item)
                )
                if (package.read(item), stored_id, refs) != (xml.xml, xml.item_id, xml.schema_refs):
                    raise CustomPropertiesRefusal("shared custom XML item is stale or foreign")
            operation = _CustomXmlOperation(
                "bind", ref, item, xml.xml, xml.item_id, xml.schema_refs
            )
            self._presentation.view_state.stage_package_operation(operation)
            return CustomXmlPart(xml.part_name, None, xml.xml, xml.item_id, xml.schema_refs)
        normalized_id = _item_id(item_id)
        from .package_parts import open_package_source

        with open_package_source(self._presentation._source_path) as package:
            ids = _datastore_ids(package, {})
        pending_ids = {
            op.item_id
            for op in self._presentation.view_state.pending_operations()
            if isinstance(op, _CustomXmlOperation) and op.kind == "add"
        }
        if normalized_id in ids or normalized_id in pending_ids:
            raise CustomPropertiesRefusal(f"duplicate custom XML ds:itemID: {normalized_id}")
        operation = _CustomXmlOperation(
            "add",
            ref,
            xml=_xml_payload(xml),
            item_id=normalized_id,
            schema_refs=_schema_refs(schema_refs),
        )
        self._presentation.view_state.stage_package_operation(operation)
        return CustomXmlPart(None, None, operation.xml, operation.item_id, operation.schema_refs)

    def replace(self, index: int, xml: Any = None, *, schema_refs: Any = None) -> CustomXmlPart:
        """Replace the XML data and/or the schema references of one part."""
        if xml is None and schema_refs is None:
            raise TypeError("replace needs xml and/or schema_refs")
        payload = None if xml is None else _xml_payload(xml)
        refs = None if schema_refs is None else _schema_refs(schema_refs)
        entry = self._entries()[index]
        view = self._presentation.view_state
        if entry.operation is not None:
            pending = entry.operation
            view.replace_pending_operation(
                pending,
                _CustomXmlOperation(
                    "add",
                    pending.ref,
                    xml=pending.xml if payload is None else payload,
                    item_id=_item_id(None) if pending.kind == "bind" else pending.item_id,
                    schema_refs=pending.schema_refs if refs is None else refs,
                ),
            )
        else:
            view.stage_package_operation(
                _CustomXmlOperation(
                    "replace",
                    self._ref(mutating=True),
                    entry.rel_id,
                    xml=payload,
                    schema_refs=refs,
                )
            )
        return self[index]

    def remove(self, index: int) -> None:
        entry = self._entries()[index]
        view = self._presentation.view_state
        if entry.operation is not None:
            view.replace_pending_operation(entry.operation, None)
        else:
            view.stage_package_operation(
                _CustomXmlOperation("remove", self._ref(mutating=True), entry.rel_id)
            )

    def clear(self) -> None:
        for index in reversed(range(len(self))):
            self.remove(index)

    def __repr__(self) -> str:
        return f"<CustomXmlPartCollection count={len(self)}>"


def custom_xml_parts_for(presentation: Any, owner: Any = None) -> CustomXmlPartCollection:
    """Custom XML parts of ``owner`` (the presentation when omitted)."""
    if presentation._disposed:
        raise RuntimeError("presentation is disposed")
    return CustomXmlPartCollection(presentation, presentation if owner is None else owner)


__all__ = [
    "CUSTOM_PROPERTIES_CONTENT_TYPE",
    "CUSTOM_PROPERTIES_PARTNAME",
    "CUSTOM_PROPERTIES_REL_TYPE",
    "CUSTOM_PROPERTIES_REL_TYPES",
    "CUSTOM_PROPERTY_FMTID",
    "CUSTOM_XML_DATA_CONTENT_TYPE",
    "CUSTOM_XML_DS_NS",
    "CUSTOM_XML_PROPERTIES_CONTENT_TYPE",
    "CUSTPROPS_NS",
    "INT32_MAX",
    "INT32_MIN",
    "INT64_MAX",
    "INT64_MIN",
    "STRICT_CUSTOM_PROPERTIES_REL_TYPE",
    "STRICT_CUSTOM_XML_DS_NS",
    "STRICT_CUSTPROPS_NS",
    "STRICT_VTYPES_NS",
    "UINT64_MAX",
    "UINT64_MIN",
    "VTYPES_NS",
    "CustomProperties",
    "CustomPropertiesRefusal",
    "CustomPropertiesSnapshot",
    "CustomPropertyRecord",
    "CustomXmlPart",
    "CustomXmlPartCollection",
    "UntouchedVariant",
    "custom_xml_parts_for",
    "read_custom_properties",
    "read_custom_properties_profile",
    "serialize_custom_properties",
]
