"""Table-cell property loading and accessors for the table facade."""

from __future__ import annotations

import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from .dml_fill import (
    gradient_payload_from_fill_parent as _gradient_payload_from_fill_parent,
)
from .facade_values import (
    coerce_emu as _coerce_emu,
    text_frame_auto_size_value as _text_frame_auto_size_value,
)
from .table_xml import _table_cell_xml_element, _table_xml_element
from .xml_helpers import (
    xml_bool_attr as _xml_bool_attr,
    xml_int_attr as _xml_int_attr,
    xml_local_name as _xml_local_name,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

_TEXT_FRAME_MARGIN_ATTRS = {
    "margin_left": "lIns",
    "margin_right": "rIns",
    "margin_top": "tIns",
    "margin_bottom": "bIns",
}
_TEXT_FRAME_MARGIN_DEFAULTS = {
    "lIns": 91440,
    "rIns": 91440,
    "tIns": 45720,
    "bIns": 45720,
}
_TEXT_FRAME_AUTO_SIZE_TAGS = {"noAutofit", "spAutoFit", "normAutofit"}
_TABLE_CELL_MARGIN_ATTRS = {
    "margin_left": "marL",
    "margin_right": "marR",
    "margin_top": "marT",
    "margin_bottom": "marB",
}
_TABLE_CELL_MARGIN_DEFAULTS = {
    "marL": 91440,
    "marR": 91440,
    "marT": 45720,
    "marB": 45720,
}


def _text_frame_margin_name(attr: str) -> str:
    for name, xml_attr in _TEXT_FRAME_MARGIN_ATTRS.items():
        if xml_attr == attr:
            return name
    return attr


def _table_cell_property_payload(cell: TableCell) -> dict[str, Any]:
    cell_properties = cell._table._payload.setdefault("_cell_properties", {})
    key = f"{cell._row_idx}:{cell._col_idx}"
    payload = cell_properties.get(key)
    if not isinstance(payload, dict):
        if not cell._table._payload.get("_cell_properties_loaded"):
            cell_properties.update(_read_table_cell_properties_for_table(cell._table))
            cell._table._payload["_cell_properties_loaded"] = True
            payload = cell_properties.get(key)
        if not isinstance(payload, dict):
            payload = _read_table_cell_properties(cell)
        cell_properties[key] = payload
    return payload


def _read_table_cell_properties_for_table(table: Table) -> dict[str, dict[str, Any]]:
    slide_part = table._slide.partname
    if not slide_part:
        return {}
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
        return {}

    payloads: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(table_element.findall(f"{{{A_NS}}}tr")):
        for col_index, cell_element in enumerate(row.findall(f"{{{A_NS}}}tc")):
            payloads[f"{row_index}:{col_index}"] = _table_cell_properties_from_xml(
                cell_element
            )
    return payloads


def _read_table_cell_properties(cell: TableCell) -> dict[str, Any]:
    slide_part = cell._table._slide.partname
    if slide_part:
        try:
            with zipfile.ZipFile(cell._table._slide._presentation.path) as package:
                root = ET.fromstring(package.read(slide_part))
            return _table_cell_properties_from_xml(
                _table_cell_xml_element(
                    root,
                    cell._table._table_index,
                    cell._row_idx,
                    cell._col_idx,
                )
            )
        except (
            AttributeError,
            FileNotFoundError,
            IndexError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            pass
    return _table_cell_properties_from_xml(None)


def _table_cell_properties_from_xml(cell_element: ET.Element | None) -> dict[str, Any]:
    margins = dict(_TABLE_CELL_MARGIN_DEFAULTS)
    text_frame_margins = dict(_TEXT_FRAME_MARGIN_DEFAULTS)
    vertical_anchor = None
    text_frame_vertical_anchor = None
    text_frame_word_wrap = None
    text_frame_auto_size = None
    fill_type = None
    fill_rgb = None
    fill_theme_color = None
    fill_pattern = None
    fill_pattern_fore_rgb = None
    fill_pattern_back_rgb = None
    fill_pattern_fore_theme_color = None
    fill_pattern_back_theme_color = None
    fill_gradient = None
    grid_span = 1
    row_span = 1
    h_merge = False
    v_merge = False
    if cell_element is not None:
        cell_properties = cell_element.find(f"{{{A_NS}}}tcPr")
        body_properties = cell_element.find(f"{{{A_NS}}}txBody/{{{A_NS}}}bodyPr")
        grid_span = _xml_int_attr(cell_element, "gridSpan", 1)
        row_span = _xml_int_attr(cell_element, "rowSpan", 1)
        h_merge = _xml_bool_attr(cell_element, "hMerge")
        v_merge = _xml_bool_attr(cell_element, "vMerge")
        if cell_properties is not None:
            for attr in _TABLE_CELL_MARGIN_DEFAULTS:
                raw = cell_properties.attrib.get(attr)
                if raw is None:
                    continue
                try:
                    margins[attr] = int(raw)
                except ValueError:
                    continue
            vertical_anchor = cell_properties.attrib.get("anchor")
            (
                fill_type,
                fill_rgb,
                fill_theme_color,
                fill_pattern,
                fill_pattern_fore_rgb,
                fill_pattern_back_rgb,
                fill_pattern_fore_theme_color,
                fill_pattern_back_theme_color,
            ) = _table_cell_fill_payload(cell_properties)
            fill_gradient = _gradient_payload_from_fill_parent(cell_properties)
        if body_properties is not None:
            for attr in _TEXT_FRAME_MARGIN_DEFAULTS:
                raw = body_properties.attrib.get(attr)
                if raw is None:
                    continue
                try:
                    text_frame_margins[attr] = int(raw)
                except ValueError:
                    continue
            text_frame_vertical_anchor = body_properties.attrib.get("anchor")
            raw_wrap = body_properties.attrib.get("wrap")
            if raw_wrap == "square":
                text_frame_word_wrap = True
            elif raw_wrap == "none":
                text_frame_word_wrap = False
            for child in body_properties:
                local_name = _xml_local_name(child.tag)
                if local_name in _TEXT_FRAME_AUTO_SIZE_TAGS:
                    text_frame_auto_size = local_name
                    break
    return {
        "margins": margins,
        "text_frame_margins": text_frame_margins,
        "vertical_anchor": vertical_anchor,
        "text_frame_vertical_anchor": text_frame_vertical_anchor,
        "text_frame_word_wrap": text_frame_word_wrap,
        "text_frame_auto_size": text_frame_auto_size,
        "fill_type": fill_type,
        "fill_rgb": fill_rgb,
        "fill_theme_color": fill_theme_color,
        "fill_pattern": fill_pattern,
        "fill_pattern_fore_rgb": fill_pattern_fore_rgb,
        "fill_pattern_back_rgb": fill_pattern_back_rgb,
        "fill_pattern_fore_theme_color": fill_pattern_fore_theme_color,
        "fill_pattern_back_theme_color": fill_pattern_back_theme_color,
        "fill_gradient": fill_gradient,
        "grid_span": grid_span,
        "row_span": row_span,
        "h_merge": h_merge,
        "v_merge": v_merge,
    }


def _table_cell_margin(cell: TableCell, attr: str) -> int:
    margins = _table_cell_property_payload(cell).setdefault(
        "margins",
        dict(_TABLE_CELL_MARGIN_DEFAULTS),
    )
    return int(margins.get(attr, _TABLE_CELL_MARGIN_DEFAULTS[attr]))


def _set_table_cell_margin(cell: TableCell, attr: str, value: Any) -> None:
    margin = _coerce_emu(value, _table_cell_margin_name(attr))
    if margin == _table_cell_margin(cell, attr):
        return
    margins = _table_cell_property_payload(cell).setdefault(
        "margins",
        dict(_TABLE_CELL_MARGIN_DEFAULTS),
    )
    margins[attr] = margin
    cell._table._slide._presentation._queue_table_cell_margin(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        attr,
        margin,
    )


def _table_cell_margin_name(attr: str) -> str:
    for name, margin_attr in _TABLE_CELL_MARGIN_ATTRS.items():
        if margin_attr == attr:
            return name
    return attr


def _table_cell_vertical_anchor(cell: TableCell) -> str | None:
    value = _table_cell_property_payload(cell).get("vertical_anchor")
    return str(value) if value else None


def _table_cell_text_frame_margin(cell: TableCell, attr: str) -> int:
    margins = _table_cell_property_payload(cell).setdefault(
        "text_frame_margins",
        dict(_TEXT_FRAME_MARGIN_DEFAULTS),
    )
    return int(margins.get(attr, _TEXT_FRAME_MARGIN_DEFAULTS[attr]))


def _set_table_cell_text_frame_margin(cell: TableCell, attr: str, value: Any) -> None:
    margin = _coerce_emu(value, _text_frame_margin_name(attr))
    if margin == _table_cell_text_frame_margin(cell, attr):
        return
    margins = _table_cell_property_payload(cell).setdefault(
        "text_frame_margins",
        dict(_TEXT_FRAME_MARGIN_DEFAULTS),
    )
    margins[attr] = margin
    cell._table._slide._presentation._queue_table_cell_text_frame_margin(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        attr,
        margin,
    )


def _table_cell_text_frame_vertical_anchor(cell: TableCell) -> str | None:
    value = _table_cell_property_payload(cell).get("text_frame_vertical_anchor")
    return str(value) if value else None


def _table_cell_text_frame_word_wrap(cell: TableCell) -> bool | None:
    value = _table_cell_property_payload(cell).get("text_frame_word_wrap")
    return None if value is None else bool(value)


def _table_cell_text_frame_auto_size(cell: TableCell) -> Any:
    return _text_frame_auto_size_value(
        _table_cell_property_payload(cell).get("text_frame_auto_size")
    )


def _table_cell_fill_payload(
    cell_properties: ET.Element,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
]:
    for child in cell_properties:
        if child.tag == f"{{{A_NS}}}solidFill":
            rgb_color = child.find(f"{{{A_NS}}}srgbClr")
            theme_color = child.find(f"{{{A_NS}}}schemeClr")
            rgb = None if rgb_color is None else rgb_color.attrib.get("val")
            theme = (
                None if theme_color is None else theme_color.attrib.get("val")
            )
            return (
                "solid",
                rgb.upper() if rgb else None,
                theme,
                None,
                None,
                None,
                None,
                None,
            )
        if child.tag == f"{{{A_NS}}}noFill":
            return ("background", None, None, None, None, None, None, None)
        if child.tag == f"{{{A_NS}}}pattFill":
            pattern = child.attrib.get("prst") or None
            fore = child.find(f"{{{A_NS}}}fgClr/{{{A_NS}}}srgbClr")
            back = child.find(f"{{{A_NS}}}bgClr/{{{A_NS}}}srgbClr")
            fore_theme = child.find(f"{{{A_NS}}}fgClr/{{{A_NS}}}schemeClr")
            back_theme = child.find(f"{{{A_NS}}}bgClr/{{{A_NS}}}schemeClr")
            fore_rgb = None if fore is None else fore.attrib.get("val")
            back_rgb = None if back is None else back.attrib.get("val")
            fore_theme_value = (
                None if fore_theme is None else fore_theme.attrib.get("val")
            )
            back_theme_value = (
                None if back_theme is None else back_theme.attrib.get("val")
            )
            return (
                "patterned",
                None,
                None,
                pattern,
                fore_rgb.upper() if fore_rgb else None,
                back_rgb.upper() if back_rgb else None,
                fore_theme_value,
                back_theme_value,
            )
        if child.tag == f"{{{A_NS}}}gradFill":
            return ("gradient", None, None, None, None, None, None, None)
        if child.tag == f"{{{A_NS}}}blipFill":
            return ("picture", None, None, None, None, None, None, None)
        if child.tag == f"{{{A_NS}}}grpFill":
            return ("group", None, None, None, None, None, None, None)
    return (None, None, None, None, None, None, None, None)


def _table_cell_fill_type(cell: TableCell) -> str | None:
    value = _table_cell_property_payload(cell).get("fill_type")
    return str(value) if value else None


def _table_cell_gradient_fill_payload(cell: TableCell) -> dict[str, Any] | None:
    value = _table_cell_property_payload(cell).get("fill_gradient")
    return dict(value) if isinstance(value, dict) else None


def _table_cell_span(cell: TableCell, key: str) -> int:
    value = _table_cell_property_payload(cell).get(key, 1)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _table_cell_solid_rgb(cell: TableCell) -> str | None:
    value = _table_cell_property_payload(cell).get("fill_rgb")
    return str(value).upper() if value else None


def _table_cell_solid_theme_color(cell: TableCell) -> str | None:
    value = _table_cell_property_payload(cell).get("fill_theme_color")
    return str(value) if value else None


def _table_cell_fill_pattern(cell: TableCell) -> str | None:
    value = _table_cell_property_payload(cell).get("fill_pattern")
    return str(value) if value else None


def _table_cell_pattern_rgb(cell: TableCell, role: str, default: str) -> str:
    key = f"fill_pattern_{role}_rgb"
    value = _table_cell_property_payload(cell).get(key)
    return str(value).upper() if value else default


def _table_cell_pattern_theme_color(cell: TableCell, role: str) -> str | None:
    key = f"fill_pattern_{role}_theme_color"
    value = _table_cell_property_payload(cell).get(key)
    return str(value) if value else None
