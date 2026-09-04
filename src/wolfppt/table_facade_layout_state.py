"""Row, column, and style state helpers for the table facade."""

from __future__ import annotations

import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from .facade_values import coerce_emu as _coerce_emu
from .table_xml import _table_xml_element
from .xml_helpers import (
    xml_bool_attr as _xml_bool_attr,
    xml_int_attr as _xml_int_attr,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

_TABLE_STYLE_FLAG_ATTRS = {
    "first_col": "firstCol",
    "first_row": "firstRow",
    "horz_banding": "bandRow",
    "last_col": "lastCol",
    "last_row": "lastRow",
    "vert_banding": "bandCol",
}


def _table_row_heights(table: Table) -> list[int]:
    heights = table._payload.get("_row_heights")
    if not isinstance(heights, list):
        heights = _read_table_row_heights(table)
        table._payload["_row_heights"] = heights
    return [int(height) for height in heights]


def _read_table_row_heights(table: Table) -> list[int]:
    slide_part = table._slide.partname
    fallback = [0 for _row in table._rows]
    if not slide_part:
        return fallback
    try:
        with zipfile.ZipFile(table._slide._presentation.path) as package:
            root = ET.fromstring(package.read(slide_part))
        table_element = _table_xml_element(root, table._table_index)
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return fallback
    heights: list[int] = []
    for row in table_element.findall(f"{{{A_NS}}}tr"):
        heights.append(_xml_int_attr(row, "h", 0))
    return heights or fallback


def _set_table_row_height(row: TableRow, value: Any) -> None:
    height = _coerce_emu(value, "height")
    heights = _table_row_heights(row._table)
    if row._index >= len(heights):
        heights.extend([0] * (row._index - len(heights) + 1))
    if heights[row._index] == height:
        return
    heights[row._index] = height
    row._table._payload["_row_heights"] = heights
    row._table._slide._presentation._queue_table_row_height(
        row._table._slide._index,
        row._table._table_index,
        row._index,
        height,
    )


def _table_column_widths(table: Table) -> list[int]:
    widths = table._payload.get("_column_widths")
    if not isinstance(widths, list):
        widths = _read_table_column_widths(table)
        table._payload["_column_widths"] = widths
    return [int(width) for width in widths]


def _read_table_column_widths(table: Table) -> list[int]:
    slide_part = table._slide.partname
    fallback = [0 for _col in range(max((len(row) for row in table._rows), default=0))]
    if not slide_part:
        return fallback
    try:
        with zipfile.ZipFile(table._slide._presentation.path) as package:
            root = ET.fromstring(package.read(slide_part))
        table_element = _table_xml_element(root, table._table_index)
    except (
        AttributeError,
        FileNotFoundError,
        IndexError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return fallback
    grid = table_element.find(f"{{{A_NS}}}tblGrid")
    if grid is None:
        return fallback
    widths = [
        _xml_int_attr(column, "w", 0)
        for column in grid.findall(f"{{{A_NS}}}gridCol")
    ]
    return widths or fallback


def _set_table_column_width(column: TableColumn, value: Any) -> None:
    width = _coerce_emu(value, "width")
    widths = _table_column_widths(column._table)
    if column._index >= len(widths):
        widths.extend([0] * (column._index - len(widths) + 1))
    if widths[column._index] == width:
        return
    widths[column._index] = width
    column._table._payload["_column_widths"] = widths
    column._table._slide._presentation._queue_table_column_width(
        column._table._slide._index,
        column._table._table_index,
        column._index,
        width,
    )


def _table_style_payload(table: Table) -> dict[str, bool]:
    style = table._payload.get("_style_flags")
    if not isinstance(style, dict):
        style = _read_table_style_flags(table)
        table._payload["_style_flags"] = style
    return style


def _read_table_style_flags(table: Table) -> dict[str, bool]:
    style = {name: False for name in _TABLE_STYLE_FLAG_ATTRS}
    slide_part = table._slide.partname
    if slide_part:
        try:
            with zipfile.ZipFile(table._slide._presentation.path) as package:
                root = ET.fromstring(package.read(slide_part))
            table_element = _table_xml_element(root, table._table_index)
            table_properties = table_element.find(f"{{{A_NS}}}tblPr")
        except (AttributeError, IndexError, KeyError, zipfile.BadZipFile):
            table_properties = None
        if table_properties is not None:
            for name, attr in _TABLE_STYLE_FLAG_ATTRS.items():
                style[name] = _xml_bool_attr(table_properties, attr)
    else:
        style["first_row"] = True
        style["horz_banding"] = True
    return style


def _table_style_flag(table: Table, name: str) -> bool:
    return bool(_table_style_payload(table).get(name, False))


def _set_table_style_flag(table: Table, name: str, value: Any) -> None:
    if value not in (True, False):
        raise ValueError(f"assigned value must be True or False, got {value}")
    flag = bool(value)
    if flag == _table_style_flag(table, name):
        return
    _table_style_payload(table)[name] = flag
    table._slide._presentation._queue_table_style_flag(
        table._slide._index,
        table._table_index,
        _TABLE_STYLE_FLAG_ATTRS[name],
        flag,
    )
