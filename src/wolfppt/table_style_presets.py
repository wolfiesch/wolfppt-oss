"""Built-in and package-defined table style presets, lookup, and normalization."""

from __future__ import annotations

import uuid
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .table_style_catalog import built_in_table_styles
from .table_xml import _table_xml_element

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def normalize_table_style_id(value: Any) -> str:
    """Normalize a GUID into uppercase canonical format with curly braces: ``{GUID}``.

    Raises ValueError if ``value`` is not a valid GUID.
    """
    if not isinstance(value, str):
        raise TypeError(f"table style id must be a str, got {type(value).__name__}")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("table style id cannot be empty")
    raw = cleaned.strip("{}").strip()
    try:
        parsed = uuid.UUID(raw)
        return f"{{{str(parsed).upper()}}}"
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"invalid table style GUID {value!r}") from exc


def package_table_styles(presentation_or_path: Any) -> dict[str, str]:
    """Read {style_id: style_name} for package-defined styles from ppt/tableStyles.xml."""
    if presentation_or_path is None:
        return {}
    if hasattr(presentation_or_path, "path"):
        path = presentation_or_path.path
    elif isinstance(presentation_or_path, (str, Path)):
        path = Path(presentation_or_path)
    else:
        return {}

    if not path or not Path(path).is_file():
        return {}

    styles: dict[str, str] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            target_name = None
            for name in archive.namelist():
                if name == "ppt/tableStyles.xml" or name.endswith("tableStyles.xml"):
                    target_name = name
                    break
            if target_name is None:
                return {}
            payload = archive.read(target_name)
            root = ET.fromstring(payload)
            for element in root:
                tag = element.tag.rsplit("}", 1)[-1]
                if tag != "tblStyle":
                    continue
                style_id = element.get("styleId")
                if not style_id:
                    continue
                style_name = element.get("styleName", "")
                try:
                    norm_id = normalize_table_style_id(style_id)
                    styles[norm_id] = style_name
                except ValueError:
                    styles[style_id.strip()] = style_name
    except (zipfile.BadZipFile, OSError, ET.ParseError, KeyError):
        return {}
    return styles


def available_table_styles(presentation: Any = None) -> dict[str, str]:
    """Return a mapping of {style_id: style_name} combining built-in and package styles."""
    styles = dict(built_in_table_styles())
    if presentation is not None:
        styles.update(package_table_styles(presentation))
    return styles


def lookup_table_style_name(
    style_id: str | None,
    presentation: Any = None,
) -> str | None:
    """Look up the human-readable style name for a given style ID."""
    if not style_id:
        return None
    try:
        norm_id = normalize_table_style_id(style_id)
    except ValueError:
        return None
    styles = available_table_styles(presentation)
    return styles.get(norm_id)


def lookup_table_style_id(
    style_name: str | None,
    presentation: Any = None,
) -> str | None:
    """Look up the canonical {GUID} style ID for a given style name (case-insensitive)."""
    if not style_name or not isinstance(style_name, str):
        return None
    target = style_name.strip().casefold()
    styles = available_table_styles(presentation)
    for sid, sname in styles.items():
        if sname.strip().casefold() == target:
            return sid
    return None


def validate_table_style_id(
    value: str | None,
    presentation: Any = None,
) -> str | None:
    """Validate a style ID against built-in and package styles, returning normalized ID."""
    if value is None:
        return None
    norm_id = normalize_table_style_id(value)
    styles = available_table_styles(presentation)
    if norm_id not in styles:
        raise ValueError(f"unknown table style id {value!r}")
    return norm_id


def read_table_style_id_from_properties(
    table_properties: ET.Element | None,
) -> str | None:
    """Read and normalize the tableStyleId child element text from a:tblPr if present."""
    if table_properties is None:
        return None
    elem = table_properties.find(f"{{{A_NS}}}tableStyleId")
    if elem is None or not elem.text or not elem.text.strip():
        return None
    try:
        return normalize_table_style_id(elem.text)
    except ValueError:
        return elem.text.strip()


def has_embedded_table_style(
    table_properties: ET.Element | None,
) -> bool:
    """Return True if a:tblPr has an embedded a:tableStyle child element."""
    if table_properties is None:
        return False
    return table_properties.find(f"{{{A_NS}}}tableStyle") is not None


def _read_table_style_id_and_conflict(table: Any) -> tuple[str | None, bool]:
    slide_part = getattr(table._slide, "partname", None)
    if not slide_part:
        return "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}", False
    try:
        presentation_path = getattr(table._slide._presentation, "path", None)
        if not presentation_path or not Path(presentation_path).is_file():
            return None, False
        with zipfile.ZipFile(presentation_path) as package:
            root = ET.fromstring(package.read(slide_part))
        table_element = _table_xml_element(root, table._table_index)
        table_properties = table_element.find(f"{{{A_NS}}}tblPr")
        has_embedded = has_embedded_table_style(table_properties)
        style_id = read_table_style_id_from_properties(table_properties)
        return style_id, has_embedded
    except (
        AttributeError,
        IndexError,
        KeyError,
        zipfile.BadZipFile,
        OSError,
        ET.ParseError,
    ):
        return None, False


def _table_style_id(table: Any) -> str | None:
    prs = getattr(table._slide, "_presentation", None)
    if prs is not None:
        edits = getattr(prs, "_table_style_edits", None)
        if edits is not None:
            table_edits = edits.get((table._slide._index, table._table_index))
            if table_edits is not None and "tableStyleId" in table_edits:
                return table_edits["tableStyleId"]

    if "_style_id" in table._payload:
        return table._payload["_style_id"]

    style_id, has_embedded = _read_table_style_id_and_conflict(table)
    table._payload["_style_id"] = style_id
    table._payload["_has_embedded_table_style"] = has_embedded
    return style_id


def _set_table_style_id(table: Any, value: Any) -> None:
    if value is not None and not isinstance(value, str):
        raise TypeError(
            f"table style id must be a string or None, got {type(value).__name__}"
        )

    norm_id = validate_table_style_id(
        value, getattr(table._slide, "_presentation", None)
    )

    if "_has_embedded_table_style" not in table._payload:
        _table_style_id(table)
    if norm_id is not None and table._payload.get("_has_embedded_table_style", False):
        raise ValueError(
            "cannot apply table style id: table has an embedded custom tableStyle"
        )

    if norm_id == _table_style_id(table):
        return

    table._payload["_style_id"] = norm_id
    prs = getattr(table._slide, "_presentation", None)
    if prs is not None and hasattr(prs, "_queue_table_style_id"):
        prs._queue_table_style_id(
            table._slide._index,
            table._table_index,
            norm_id,
        )


def _table_style_name(table: Any) -> str | None:
    sid = _table_style_id(table)
    if not sid:
        return None
    prs = getattr(table._slide, "_presentation", None)
    return lookup_table_style_name(sid, prs)


def _set_table_style_name(table: Any, value: Any) -> None:
    if value is None:
        _set_table_style_id(table, None)
        return
    if not isinstance(value, str):
        raise TypeError(
            f"table style name must be a string or None, got {type(value).__name__}"
        )
    prs = getattr(table._slide, "_presentation", None)
    sid = lookup_table_style_id(value, prs)
    if sid is None:
        raise ValueError(f"unknown table style name {value!r}")
    _set_table_style_id(table, sid)
