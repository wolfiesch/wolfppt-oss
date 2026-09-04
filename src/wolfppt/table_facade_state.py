"""State and XML helpers for the table facade."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .table_facade import Table, TableCell
from xml.etree import ElementTree as ET

from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
    centipoints_value as _centipoints_value,
    emu_to_centipoints as _emu_to_centipoints,
    paragraph_spacing_xml_tag as _paragraph_spacing_xml_tag,
)
from .slide_relationships import slide_relationship_target as _slide_relationship_target
from .table_facade_layout_state import (
    _set_table_column_width,
    _set_table_row_height,
    _set_table_style_flag,
    _table_column_widths,
    _table_row_heights,
    _table_style_flag,
)
from .table_facade_property_lists import (
    _fit_dict_property_list,
    _fit_paragraph_property_list,
    _fit_run_font_property_list,
    _fit_run_optional_string_property_list,
)
from .table_facade_text_content_state import (
    _set_table_cell_text_frame_paragraph_line_break,
    _set_table_cell_text_frame_paragraph_runs,
    _table_cell_text_frame_paragraph_runs,
    _table_cell_text_frame_paragraph_texts,
)
from .table_facade_cell_state import (
    _read_table_cell_properties_for_table,
    _set_table_cell_margin,
    _set_table_cell_text_frame_margin,
    _table_cell_fill_pattern,
    _table_cell_fill_type,
    _table_cell_gradient_fill_payload,
    _table_cell_margin,
    _table_cell_pattern_rgb,
    _table_cell_pattern_theme_color,
    _table_cell_property_payload,
    _table_cell_solid_rgb,
    _table_cell_solid_theme_color,
    _table_cell_span,
    _table_cell_text_frame_auto_size,
    _table_cell_text_frame_margin,
    _table_cell_text_frame_vertical_anchor,
    _table_cell_text_frame_word_wrap,
    _table_cell_vertical_anchor,
)
from .table_xml import _table_cell_xml_element

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _normalize_table_rows(payload: dict[str, Any]) -> list[list[str]]:
    rows = [list(row) for row in payload.get("rows", [])]
    payload["rows"] = rows
    return rows


def _table_cell_text_frame_paragraph_alignment(
    cell: TableCell,
    paragraph_index: int,
) -> str | None:
    alignments = _table_cell_text_frame_paragraph_alignments(cell)
    if paragraph_index < 0 or paragraph_index >= len(alignments):
        raise IndexError("paragraph index out of range")
    alignment = alignments[paragraph_index]
    return str(alignment) if alignment else None


def _table_cell_text_frame_paragraph_alignments(
    cell: TableCell,
) -> list[str | None]:
    payload = _table_cell_property_payload(cell)
    alignments = payload.get("text_frame_paragraph_alignments")
    if not isinstance(alignments, list):
        alignments = _read_table_cell_text_frame_paragraph_property(
            cell,
            "algn",
            None,
        )
        alignments = _fit_paragraph_property_list(
            alignments,
            len(_table_cell_text_frame_paragraph_texts(cell)),
            None,
        )
        payload["text_frame_paragraph_alignments"] = alignments
    return [str(value) if value else None for value in alignments]


def _set_table_cell_text_frame_paragraph_alignment(
    cell: TableCell,
    paragraph_index: int,
    alignment: str | None,
) -> None:
    alignments = _table_cell_text_frame_paragraph_alignments(cell)
    if paragraph_index < 0 or paragraph_index >= len(alignments):
        raise IndexError("paragraph index out of range")
    alignments[paragraph_index] = alignment
    _table_cell_property_payload(cell)["text_frame_paragraph_alignments"] = alignments
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_alignment(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        alignment,
    )


def _table_cell_text_frame_paragraph_level(
    cell: TableCell,
    paragraph_index: int,
) -> int:
    levels = _table_cell_text_frame_paragraph_levels(cell)
    if paragraph_index < 0 or paragraph_index >= len(levels):
        raise IndexError("paragraph index out of range")
    return int(levels[paragraph_index])


def _table_cell_text_frame_paragraph_levels(cell: TableCell) -> list[int]:
    payload = _table_cell_property_payload(cell)
    levels = payload.get("text_frame_paragraph_levels")
    if not isinstance(levels, list):
        raw_levels = _read_table_cell_text_frame_paragraph_property(cell, "lvl", "0")
        raw_levels = _fit_paragraph_property_list(
            raw_levels,
            len(_table_cell_text_frame_paragraph_texts(cell)),
            "0",
        )
        levels = []
        for raw_level in raw_levels:
            try:
                levels.append(int(raw_level or 0))
            except (TypeError, ValueError):
                levels.append(0)
        payload["text_frame_paragraph_levels"] = levels
    return [int(level) for level in levels]


def _set_table_cell_text_frame_paragraph_level(
    cell: TableCell,
    paragraph_index: int,
    level: int,
) -> None:
    levels = _table_cell_text_frame_paragraph_levels(cell)
    if paragraph_index < 0 or paragraph_index >= len(levels):
        raise IndexError("paragraph index out of range")
    levels[paragraph_index] = level
    _table_cell_property_payload(cell)["text_frame_paragraph_levels"] = levels
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_level(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        level,
    )


def _table_cell_text_frame_paragraph_spacing(
    cell: TableCell,
    paragraph_index: int,
    attr: str,
) -> Any:
    values = _table_cell_text_frame_paragraph_spacing_values(cell, attr)
    if paragraph_index < 0 or paragraph_index >= len(values):
        raise IndexError("paragraph index out of range")
    value = values[paragraph_index]
    if value is None:
        return None
    if attr == "line_spacing" and isinstance(value, float):
        return value
    return _centipoints_value(_emu_to_centipoints(int(value)))


def _table_cell_text_frame_paragraph_spacing_values(
    cell: TableCell,
    attr: str,
) -> list[int | float | None]:
    payload = _table_cell_property_payload(cell)
    key = f"text_frame_paragraph_{attr}"
    values = payload.get(key)
    if not isinstance(values, list):
        values = _read_table_cell_text_frame_paragraph_spacing(cell, attr)
        values = _fit_paragraph_property_list(
            values,
            len(_table_cell_text_frame_paragraph_texts(cell)),
            None,
        )
        payload[key] = values
    return list(values)


def _set_table_cell_text_frame_paragraph_spacing(
    cell: TableCell,
    paragraph_index: int,
    attr: str,
    value: int | float | None,
) -> None:
    values = _table_cell_text_frame_paragraph_spacing_values(cell, attr)
    if paragraph_index < 0 or paragraph_index >= len(values):
        raise IndexError("paragraph index out of range")
    if values[paragraph_index] == value:
        return
    values[paragraph_index] = value
    _table_cell_property_payload(cell)[f"text_frame_paragraph_{attr}"] = values
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_spacing(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        attr,
        value,
    )


def _table_cell_text_frame_paragraph_font_value(
    cell: TableCell,
    paragraph_index: int,
    attr: str,
) -> Any:
    fonts = _table_cell_text_frame_paragraph_fonts(cell)
    if paragraph_index < 0 or paragraph_index >= len(fonts):
        raise IndexError("paragraph index out of range")
    return fonts[paragraph_index].get(attr)


def _set_table_cell_text_frame_paragraph_font(
    cell: TableCell,
    paragraph_index: int,
    attr: str,
    value: Any,
) -> None:
    fonts = _table_cell_text_frame_paragraph_fonts(cell)
    if paragraph_index < 0 or paragraph_index >= len(fonts):
        raise IndexError("paragraph index out of range")
    font = dict(fonts[paragraph_index])
    current_fill_type = font.get("fill_type")
    current_value = font.get(attr)
    if attr == "color":
        font["fill_type"] = "solid"
        font["theme_color"] = None
    elif attr == "theme_color":
        font["fill_type"] = "solid"
        font["color"] = None
    if current_value == value and (
        attr not in {"color", "theme_color"} or current_fill_type == "solid"
    ):
        return
    font[attr] = value
    fonts[paragraph_index] = font
    _table_cell_property_payload(cell)["text_frame_paragraph_fonts"] = fonts
    queued = {attr: value}
    if attr == "color":
        queued["fill_type"] = "solid"
    elif attr == "theme_color":
        queued = {"color": {"type": "scheme", "value": value}, "fill_type": "solid"}
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_font(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        queued,
    )


def _table_cell_text_frame_paragraph_run_font_value(
    cell: TableCell,
    paragraph_index: int,
    run_index: int,
    attr: str,
) -> Any:
    fonts = _table_cell_text_frame_paragraph_run_fonts(cell)
    if paragraph_index < 0 or paragraph_index >= len(fonts):
        raise IndexError("paragraph index out of range")
    if run_index < 0 or run_index >= len(fonts[paragraph_index]):
        raise IndexError("run index out of range")
    return fonts[paragraph_index][run_index].get(attr)


def _set_table_cell_text_frame_paragraph_run_font(
    cell: TableCell,
    paragraph_index: int,
    run_index: int,
    attr: str,
    value: Any,
) -> None:
    fonts = _table_cell_text_frame_paragraph_run_fonts(cell)
    if paragraph_index < 0 or paragraph_index >= len(fonts):
        raise IndexError("paragraph index out of range")
    if run_index < 0 or run_index >= len(fonts[paragraph_index]):
        raise IndexError("run index out of range")
    font = dict(fonts[paragraph_index][run_index])
    current_fill_type = font.get("fill_type")
    current_value = font.get(attr)
    if attr == "color":
        font["fill_type"] = "solid"
        font["theme_color"] = None
    elif attr == "theme_color":
        font["fill_type"] = "solid"
        font["color"] = None
    if current_value == value and (
        attr not in {"color", "theme_color"} or current_fill_type == "solid"
    ):
        return
    font[attr] = value
    fonts[paragraph_index][run_index] = font
    _table_cell_property_payload(cell)["text_frame_paragraph_run_fonts"] = fonts
    queued = {attr: value}
    if attr == "color":
        queued["fill_type"] = "solid"
    elif attr == "theme_color":
        queued = {"color": {"type": "scheme", "value": value}, "fill_type": "solid"}
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_run_font(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        run_index,
        queued,
    )


def _table_cell_text_frame_paragraph_run_hyperlink_address(
    cell: TableCell,
    paragraph_index: int,
    run_index: int,
) -> str | None:
    hyperlinks = _table_cell_text_frame_paragraph_run_hyperlinks(cell)
    if paragraph_index < 0 or paragraph_index >= len(hyperlinks):
        raise IndexError("paragraph index out of range")
    if run_index < 0 or run_index >= len(hyperlinks[paragraph_index]):
        raise IndexError("run index out of range")
    address = hyperlinks[paragraph_index][run_index]
    return str(address) if address else None


def _set_table_cell_text_frame_paragraph_run_hyperlink_address(
    cell: TableCell,
    paragraph_index: int,
    run_index: int,
    address: str | None,
) -> None:
    hyperlinks = _table_cell_text_frame_paragraph_run_hyperlinks(cell)
    if paragraph_index < 0 or paragraph_index >= len(hyperlinks):
        raise IndexError("paragraph index out of range")
    if run_index < 0 or run_index >= len(hyperlinks[paragraph_index]):
        raise IndexError("run index out of range")
    normalized = str(address) if address else None
    if hyperlinks[paragraph_index][run_index] == normalized:
        return
    hyperlinks[paragraph_index][run_index] = normalized
    _table_cell_property_payload(cell)["text_frame_paragraph_run_hyperlinks"] = (
        hyperlinks
    )
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_run_hyperlink(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        run_index,
        normalized,
    )


def _table_cell_text_frame_paragraph_fonts(
    cell: TableCell,
) -> list[dict[str, Any]]:
    payload = _table_cell_property_payload(cell)
    fonts = payload.get("text_frame_paragraph_fonts")
    if not isinstance(fonts, list):
        fonts = _read_table_cell_text_frame_paragraph_fonts(cell)
        fonts = _fit_dict_property_list(
            fonts,
            len(_table_cell_text_frame_paragraph_texts(cell)),
        )
        payload["text_frame_paragraph_fonts"] = fonts
    return [dict(font) if isinstance(font, dict) else {} for font in fonts]


def _read_table_cell_text_frame_paragraph_fonts(
    cell: TableCell,
) -> list[dict[str, Any]]:
    slide_part = cell._table._slide.partname
    if slide_part:
        try:
            with zipfile.ZipFile(cell._table._slide._presentation.path) as package:
                root = ET.fromstring(package.read(slide_part))
            cell_element = _table_cell_xml_element(
                root,
                cell._table._table_index,
                cell._row_idx,
                cell._col_idx,
            )
            text_body = cell_element.find(f"{{{A_NS}}}txBody")
        except (
            AttributeError,
            FileNotFoundError,
            IndexError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            text_body = None
        if text_body is not None:
            fonts = [
                _paragraph_font_from_xml(paragraph)
                for paragraph in text_body.findall(f"{{{A_NS}}}p")
            ]
            if fonts:
                return fonts
    return [{} for _paragraph in _table_cell_text_frame_paragraph_texts(cell)]


def _paragraph_font_from_xml(paragraph: ET.Element) -> dict[str, Any]:
    paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return {}
    default_run_properties = paragraph_properties.find(f"{{{A_NS}}}defRPr")
    if default_run_properties is None:
        return {}
    return _font_from_run_properties(default_run_properties)


def _table_cell_text_frame_paragraph_run_fonts(
    cell: TableCell,
) -> list[list[dict[str, Any]]]:
    payload = _table_cell_property_payload(cell)
    fonts = payload.get("text_frame_paragraph_run_fonts")
    paragraph_runs = _table_cell_text_frame_paragraph_runs(cell)
    if not isinstance(fonts, list):
        fonts = _read_table_cell_text_frame_paragraph_run_fonts(cell)
        fonts = _fit_run_font_property_list(fonts, paragraph_runs)
        payload["text_frame_paragraph_run_fonts"] = fonts
    return [
        [dict(font) if isinstance(font, dict) else {} for font in paragraph_fonts]
        if isinstance(paragraph_fonts, list)
        else []
        for paragraph_fonts in fonts
    ]


def _table_cell_text_frame_paragraph_run_hyperlinks(
    cell: TableCell,
) -> list[list[str | None]]:
    payload = _table_cell_property_payload(cell)
    hyperlinks = payload.get("text_frame_paragraph_run_hyperlinks")
    paragraph_runs = _table_cell_text_frame_paragraph_runs(cell)
    if not isinstance(hyperlinks, list):
        hyperlinks = _read_table_cell_text_frame_paragraph_run_hyperlinks(cell)
        hyperlinks = _fit_run_optional_string_property_list(hyperlinks, paragraph_runs)
        payload["text_frame_paragraph_run_hyperlinks"] = hyperlinks
    return [
        [
            str(address) if address else None
            for address in paragraph_hyperlinks
        ]
        if isinstance(paragraph_hyperlinks, list)
        else []
        for paragraph_hyperlinks in hyperlinks
    ]


def _read_table_cell_text_frame_paragraph_run_hyperlinks(
    cell: TableCell,
) -> list[list[str | None]]:
    slide_part = cell._table._slide.partname
    if slide_part:
        try:
            with zipfile.ZipFile(cell._table._slide._presentation.path) as package:
                root = ET.fromstring(package.read(slide_part))
            cell_element = _table_cell_xml_element(
                root,
                cell._table._table_index,
                cell._row_idx,
                cell._col_idx,
            )
            text_body = cell_element.find(f"{{{A_NS}}}txBody")
        except (
            AttributeError,
            FileNotFoundError,
            IndexError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            text_body = None
        if text_body is not None:
            return [
                [
                    _run_hyperlink_address(cell, run)
                    for run in paragraph.findall(f"{{{A_NS}}}r")
                ]
                for paragraph in text_body.findall(f"{{{A_NS}}}p")
            ]
    return [
        [None for _run in paragraph_runs]
        for paragraph_runs in _table_cell_text_frame_paragraph_runs(cell)
    ]


def _run_hyperlink_address(cell: TableCell, run: ET.Element) -> str | None:
    run_properties = run.find(f"{{{A_NS}}}rPr")
    if run_properties is None:
        return None
    hyperlink = run_properties.find(f"{{{A_NS}}}hlinkClick")
    if hyperlink is None:
        return None
    relationship_id = hyperlink.attrib.get(f"{{{R_NS}}}id")
    if not relationship_id:
        return None
    return _slide_relationship_target(
        cell._table._slide._presentation.path,
        cell._table._slide.partname,
        relationship_id,
        "/hyperlink",
    )


def _read_table_cell_text_frame_paragraph_run_fonts(
    cell: TableCell,
) -> list[list[dict[str, Any]]]:
    slide_part = cell._table._slide.partname
    if slide_part:
        try:
            with zipfile.ZipFile(cell._table._slide._presentation.path) as package:
                root = ET.fromstring(package.read(slide_part))
            cell_element = _table_cell_xml_element(
                root,
                cell._table._table_index,
                cell._row_idx,
                cell._col_idx,
            )
            text_body = cell_element.find(f"{{{A_NS}}}txBody")
        except (
            AttributeError,
            FileNotFoundError,
            IndexError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            text_body = None
        if text_body is not None:
            return [
                [
                    _font_from_run_properties(run_properties)
                    if (run_properties := run.find(f"{{{A_NS}}}rPr")) is not None
                    else {}
                    for run in paragraph.findall(f"{{{A_NS}}}r")
                ]
                for paragraph in text_body.findall(f"{{{A_NS}}}p")
            ]
    return [
        [{} for _run in paragraph_runs]
        for paragraph_runs in _table_cell_text_frame_paragraph_runs(cell)
    ]


def _font_from_run_properties(run_properties: ET.Element) -> dict[str, Any]:
    font: dict[str, Any] = {}
    for attr, key in (("b", "bold"), ("i", "italic")):
        value = run_properties.attrib.get(attr)
        if value is not None:
            font[key] = value not in {"0", "false", "False"}
    underline = run_properties.attrib.get("u")
    if underline is not None:
        font["underline"] = underline != "none"
    size = run_properties.attrib.get("sz")
    if size is not None:
        try:
            font["size"] = _centipoints_to_emu(int(size))
        except ValueError:
            pass
    if run_properties.attrib.get("lang"):
        font["language_id"] = run_properties.attrib["lang"]
    latin = run_properties.find(f"{{{A_NS}}}latin")
    if latin is not None and latin.attrib.get("typeface"):
        font["name"] = latin.attrib["typeface"]
    rgb = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}srgbClr")
    if rgb is not None and rgb.attrib.get("val"):
        font["color"] = rgb.attrib["val"].upper()
    theme = run_properties.find(f"{{{A_NS}}}solidFill/{{{A_NS}}}schemeClr")
    if theme is not None and theme.attrib.get("val"):
        font["theme_color"] = theme.attrib["val"]
    fill_type = _paragraph_font_fill_type(run_properties)
    if fill_type is not None:
        font["fill_type"] = fill_type
    return font


def _paragraph_font_fill_type(run_properties: ET.Element) -> str | None:
    for child in run_properties:
        if child.tag == f"{{{A_NS}}}solidFill":
            return "solid"
        if child.tag == f"{{{A_NS}}}noFill":
            return "background"
        if child.tag == f"{{{A_NS}}}pattFill":
            return "patterned"
        if child.tag == f"{{{A_NS}}}gradFill":
            return "gradient"
        if child.tag == f"{{{A_NS}}}blipFill":
            return "picture"
        if child.tag == f"{{{A_NS}}}grpFill":
            return "group"
    return None


def _read_table_cell_text_frame_paragraph_spacing(
    cell: TableCell,
    attr: str,
) -> list[int | float | None]:
    slide_part = cell._table._slide.partname
    if slide_part:
        try:
            with zipfile.ZipFile(cell._table._slide._presentation.path) as package:
                root = ET.fromstring(package.read(slide_part))
            cell_element = _table_cell_xml_element(
                root,
                cell._table._table_index,
                cell._row_idx,
                cell._col_idx,
            )
            text_body = cell_element.find(f"{{{A_NS}}}txBody")
        except (
            AttributeError,
            FileNotFoundError,
            IndexError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            text_body = None
        if text_body is not None:
            values = [
                _paragraph_spacing_from_xml(paragraph, attr)
                for paragraph in text_body.findall(f"{{{A_NS}}}p")
            ]
            if values:
                return values
    return [None for _paragraph in _table_cell_text_frame_paragraph_texts(cell)]


def _paragraph_spacing_from_xml(
    paragraph: ET.Element,
    attr: str,
) -> int | float | None:
    paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return None
    spacing = paragraph_properties.find(f"{{{A_NS}}}{_paragraph_spacing_xml_tag(attr)}")
    if spacing is None:
        return None
    spacing_points = spacing.find(f"{{{A_NS}}}spcPts")
    if spacing_points is not None:
        try:
            return _centipoints_to_emu(int(spacing_points.attrib["val"]))
        except (KeyError, ValueError):
            return None
    if attr == "line_spacing":
        spacing_percent = spacing.find(f"{{{A_NS}}}spcPct")
        if spacing_percent is not None:
            try:
                return int(spacing_percent.attrib["val"]) / 100000
            except (KeyError, ValueError):
                return None
    return None


def _read_table_cell_text_frame_paragraph_property(
    cell: TableCell,
    attr: str,
    default: str | None,
) -> list[str | None]:
    slide_part = cell._table._slide.partname
    if slide_part:
        try:
            with zipfile.ZipFile(cell._table._slide._presentation.path) as package:
                root = ET.fromstring(package.read(slide_part))
            cell_element = _table_cell_xml_element(
                root,
                cell._table._table_index,
                cell._row_idx,
                cell._col_idx,
            )
            text_body = cell_element.find(f"{{{A_NS}}}txBody")
        except (
            AttributeError,
            FileNotFoundError,
            IndexError,
            KeyError,
            ET.ParseError,
            zipfile.BadZipFile,
        ):
            text_body = None
        if text_body is not None:
            values: list[str | None] = []
            for paragraph in text_body.findall(f"{{{A_NS}}}p"):
                paragraph_properties = paragraph.find(f"{{{A_NS}}}pPr")
                if paragraph_properties is None:
                    values.append(default)
                else:
                    values.append(paragraph_properties.attrib.get(attr, default))
            if values:
                return values
    return [default for _paragraph in _table_cell_text_frame_paragraph_texts(cell)]


def _set_table_cell_text_frame_text(cell: TableCell, text: str) -> None:
    _set_table_cell_text_frame_paragraphs(cell, text.split("\n") if text else [""])


def _set_table_cell_text_frame_paragraphs(
    cell: TableCell,
    paragraphs: list[str],
) -> None:
    normalized = [str(paragraph) for paragraph in paragraphs] or [""]
    if normalized == _table_cell_text_frame_paragraph_texts(cell):
        return
    payload = _table_cell_property_payload(cell)
    payload["text_frame_paragraphs"] = normalized
    payload.pop("text_frame_paragraph_alignments", None)
    payload.pop("text_frame_paragraph_levels", None)
    payload.pop("text_frame_paragraph_space_before", None)
    payload.pop("text_frame_paragraph_space_after", None)
    payload.pop("text_frame_paragraph_line_spacing", None)
    payload.pop("text_frame_paragraph_fonts", None)
    payload.pop("text_frame_paragraph_runs", None)
    payload.pop("text_frame_paragraph_line_breaks", None)
    payload.pop("text_frame_paragraph_run_fonts", None)
    payload.pop("text_frame_paragraph_run_hyperlinks", None)
    cell._table._rows[cell._row_idx][cell._col_idx] = "\n".join(normalized)
    cell._table._payload["rows"] = cell._table._rows
    cell._table._slide._presentation._queue_table_cell_text_frame_content(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        normalized,
    )


def _merge_table_cells(cell: TableCell, other_cell: TableCell) -> None:
    if (
        cell._table._slide._presentation is not other_cell._table._slide._presentation
        or cell._table._slide._index != other_cell._table._slide._index
        or cell._table._table_index != other_cell._table._table_index
    ):
        raise ValueError("other_cell from different table")
    row_min = min(cell._row_idx, other_cell._row_idx)
    row_max = max(cell._row_idx, other_cell._row_idx)
    col_min = min(cell._col_idx, other_cell._col_idx)
    col_max = max(cell._col_idx, other_cell._col_idx)
    rows = range(row_min, row_max + 1)
    cols = range(col_min, col_max + 1)
    table = cell._table
    selected = [table.cell(row_index, col_index) for row_index in rows for col_index in cols]
    if any(selected_cell.is_merge_origin or selected_cell.is_spanned for selected_cell in selected):
        raise ValueError("range contains one or more merged cells")

    paragraphs = [
        paragraph
        for selected_cell in selected
        for paragraph in _table_cell_text_frame_paragraph_texts(selected_cell)
        if paragraph
    ]
    if not paragraphs:
        paragraphs = [""]
    _set_table_cell_merge_state(
        table,
        row_min,
        row_max,
        col_min,
        col_max,
        paragraphs,
    )
    table._slide._presentation._queue_table_cell_merge_edit(
        {
            "kind": "merge",
            "slide_index": table._slide._index,
            "table_index": table._table_index,
            "row_min": row_min,
            "row_max": row_max,
            "col_min": col_min,
            "col_max": col_max,
            "paragraphs": paragraphs,
        }
    )


def _split_table_cell(cell: TableCell) -> None:
    if not cell.is_merge_origin:
        raise ValueError("not a merge-origin cell; only a merge-origin cell can be split")
    table = cell._table
    row_min = cell._row_idx
    col_min = cell._col_idx
    row_max = row_min + cell.span_height - 1
    col_max = col_min + cell.span_width - 1
    _set_table_cell_split_state(table, row_min, row_max, col_min, col_max)
    table._slide._presentation._queue_table_cell_merge_edit(
        {
            "kind": "split",
            "slide_index": table._slide._index,
            "table_index": table._table_index,
            "row_min": row_min,
            "row_max": row_max,
            "col_min": col_min,
            "col_max": col_max,
        }
    )


def _set_table_cell_merge_state(
    table: Table,
    row_min: int,
    row_max: int,
    col_min: int,
    col_max: int,
    paragraphs: list[str],
) -> None:
    row_count = row_max - row_min + 1
    col_count = col_max - col_min + 1
    for row_index in range(row_min, row_max + 1):
        for col_index in range(col_min, col_max + 1):
            cell = table.cell(row_index, col_index)
            payload = _table_cell_property_payload(cell)
            payload["row_span"] = row_count if row_index == row_min else 1
            payload["grid_span"] = col_count if col_index == col_min else 1
            payload["h_merge"] = col_index != col_min
            payload["v_merge"] = row_index != row_min
            _table_cell_property_payload(cell)["text_frame_paragraphs"] = (
                list(paragraphs) if (row_index, col_index) == (row_min, col_min) else [""]
            )
            table._rows[row_index][col_index] = (
                "\n".join(paragraphs) if (row_index, col_index) == (row_min, col_min) else ""
            )
    table._payload["rows"] = table._rows


def _set_table_cell_split_state(
    table: Table,
    row_min: int,
    row_max: int,
    col_min: int,
    col_max: int,
) -> None:
    for row_index in range(row_min, row_max + 1):
        for col_index in range(col_min, col_max + 1):
            cell = table.cell(row_index, col_index)
            payload = _table_cell_property_payload(cell)
            payload["row_span"] = 1
            payload["grid_span"] = 1
            payload["h_merge"] = False
            payload["v_merge"] = False


_CELL_EDIT_ATTRS = (
    "_table_cell_edits",
    "_table_cell_margin_edits",
    "_table_cell_vertical_anchor_edits",
    "_table_cell_text_frame_margin_edits",
    "_table_cell_text_frame_vertical_anchor_edits",
    "_table_cell_text_frame_content_edits",
    "_table_cell_text_frame_word_wrap_edits",
    "_table_cell_text_frame_auto_size_edits",
    "_table_cell_text_frame_fit_edits",
    "_table_cell_text_frame_paragraph_alignment_edits",
    "_table_cell_text_frame_paragraph_level_edits",
    "_table_cell_text_frame_paragraph_spacing_edits",
    "_table_cell_text_frame_paragraph_font_edits",
    "_table_cell_text_frame_paragraph_run_edits",
    "_table_cell_text_frame_paragraph_line_break_edits",
    "_table_cell_text_frame_paragraph_run_font_edits",
    "_table_cell_text_frame_paragraph_run_hyperlink_edits",
    "_table_cell_fill_solid_edits",
    "_table_cell_fill_background_edits",
    "_table_cell_fill_pattern_edits",
    "_table_cell_fill_pattern_fore_color_edits",
    "_table_cell_fill_pattern_back_color_edits",
    "_table_cell_fill_color_edits",
    "_table_cell_fill_gradient_edits",
)


def _shift_cell_container_row(
    container: Any, slide_idx: int, tbl_idx: int, index: int, insert: bool
) -> Any:
    if isinstance(container, dict):
        new_d = {}
        for key, val in container.items():
            if (
                isinstance(key, tuple)
                and len(key) >= 4
                and key[0] == slide_idx
                and key[1] == tbl_idx
            ):
                r = key[2]
                c = key[3]
                rest = key[4:]
                if insert:
                    new_r = r + 1 if r >= index else r
                    new_d[(slide_idx, tbl_idx, new_r, c, *rest)] = val
                else:
                    if r == index:
                        continue
                    new_r = r - 1 if r > index else r
                    new_d[(slide_idx, tbl_idx, new_r, c, *rest)] = val
            else:
                new_d[key] = val
        return new_d
    elif isinstance(container, set):
        new_st = set()
        for key in container:
            if (
                isinstance(key, tuple)
                and len(key) >= 4
                and key[0] == slide_idx
                and key[1] == tbl_idx
            ):
                r = key[2]
                c = key[3]
                rest = key[4:]
                if insert:
                    new_r = r + 1 if r >= index else r
                    new_st.add((slide_idx, tbl_idx, new_r, c, *rest))
                else:
                    if r == index:
                        continue
                    new_r = r - 1 if r > index else r
                    new_st.add((slide_idx, tbl_idx, new_r, c, *rest))
            else:
                new_st.add(key)
        return new_st
    elif isinstance(container, list):
        new_lst = []
        for item in container:
            if (
                isinstance(item, tuple)
                and len(item) >= 4
                and item[0] == slide_idx
                and item[1] == tbl_idx
            ):
                r = item[2]
                c = item[3]
                rest = item[4:]
                if insert:
                    new_r = r + 1 if r >= index else r
                    new_lst.append((slide_idx, tbl_idx, new_r, c, *rest))
                else:
                    if r == index:
                        continue
                    new_r = r - 1 if r > index else r
                    new_lst.append((slide_idx, tbl_idx, new_r, c, *rest))
            else:
                new_lst.append(item)
        return new_lst
    return container


def _shift_cell_container_col(
    container: Any, slide_idx: int, tbl_idx: int, index: int, insert: bool
) -> Any:
    if isinstance(container, dict):
        new_d = {}
        for key, val in container.items():
            if (
                isinstance(key, tuple)
                and len(key) >= 4
                and key[0] == slide_idx
                and key[1] == tbl_idx
            ):
                r = key[2]
                c = key[3]
                rest = key[4:]
                if insert:
                    new_c = c + 1 if c >= index else c
                    new_d[(slide_idx, tbl_idx, r, new_c, *rest)] = val
                else:
                    if c == index:
                        continue
                    new_c = c - 1 if c > index else c
                    new_d[(slide_idx, tbl_idx, r, new_c, *rest)] = val
            else:
                new_d[key] = val
        return new_d
    elif isinstance(container, set):
        new_st = set()
        for key in container:
            if (
                isinstance(key, tuple)
                and len(key) >= 4
                and key[0] == slide_idx
                and key[1] == tbl_idx
            ):
                r = key[2]
                c = key[3]
                rest = key[4:]
                if insert:
                    new_c = c + 1 if c >= index else c
                    new_st.add((slide_idx, tbl_idx, r, new_c, *rest))
                else:
                    if c == index:
                        continue
                    new_c = c - 1 if c > index else c
                    new_st.add((slide_idx, tbl_idx, r, new_c, *rest))
            else:
                new_st.add(key)
        return new_st
    elif isinstance(container, list):
        new_lst = []
        for item in container:
            if (
                isinstance(item, tuple)
                and len(item) >= 4
                and item[0] == slide_idx
                and item[1] == tbl_idx
            ):
                r = item[2]
                c = item[3]
                rest = item[4:]
                if insert:
                    new_c = c + 1 if c >= index else c
                    new_lst.append((slide_idx, tbl_idx, r, new_c, *rest))
                else:
                    if c == index:
                        continue
                    new_c = c - 1 if c > index else c
                    new_lst.append((slide_idx, tbl_idx, r, new_c, *rest))
            else:
                new_lst.append(item)
        return new_lst
    return container


def _ensure_table_cell_properties_loaded(table: Table) -> None:
    if not table._payload.get("_cell_properties_loaded") and table._slide.partname:
        cell_properties = table._payload.setdefault("_cell_properties", {})
        cell_properties.update(_read_table_cell_properties_for_table(table))
        table._payload["_cell_properties_loaded"] = True


def _row_has_merged_cells(table: Table, row_idx: int) -> bool:
    _ensure_table_cell_properties_loaded(table)
    cell_properties = table._payload.get("_cell_properties", {})
    col_count = len(table._rows[row_idx]) if row_idx < len(table._rows) else 0
    for col_idx in range(col_count):
        props = cell_properties.get(f"{row_idx}:{col_idx}", {})
        if (
            props.get("row_span", 1) > 1
            or props.get("grid_span", 1) > 1
            or props.get("h_merge")
            or props.get("v_merge")
        ):
            return True
    return False


def _col_has_merged_cells(table: Table, col_idx: int) -> bool:
    _ensure_table_cell_properties_loaded(table)
    cell_properties = table._payload.get("_cell_properties", {})
    for row_idx in range(len(table._rows)):
        props = cell_properties.get(f"{row_idx}:{col_idx}", {})
        if (
            props.get("row_span", 1) > 1
            or props.get("grid_span", 1) > 1
            or props.get("h_merge")
            or props.get("v_merge")
        ):
            return True
    return False

def _row_insert_intersects_merge(table: Table, row_idx: int) -> bool:
    _ensure_table_cell_properties_loaded(table)
    cell_properties = table._payload.get("_cell_properties", {})
    for key, props in cell_properties.items():
        if not isinstance(props, dict):
            continue
        parts = key.split(":", 1)
        if len(parts) != 2:
            continue
        try:
            origin_row = int(parts[0])
        except ValueError:
            continue
        row_span = props.get("row_span", 1)
        if row_span > 1 and origin_row < row_idx < origin_row + row_span:
            return True
        if origin_row == row_idx and props.get("v_merge"):
            return True
    return False


def _column_insert_intersects_merge(table: Table, col_idx: int) -> bool:
    _ensure_table_cell_properties_loaded(table)
    cell_properties = table._payload.get("_cell_properties", {})
    for key, props in cell_properties.items():
        if not isinstance(props, dict):
            continue
        parts = key.split(":", 1)
        if len(parts) != 2:
            continue
        try:
            origin_col = int(parts[1])
        except ValueError:
            continue
        grid_span = props.get("grid_span", 1)
        if grid_span > 1 and origin_col < col_idx < origin_col + grid_span:
            return True
        if origin_col == col_idx and props.get("h_merge"):
            return True
    return False


def _insert_table_row(table: Table, index: int) -> Any:
    if not isinstance(index, int) or isinstance(index, bool):
        raise TypeError("index must be an integer")
    row_count = len(table._rows)
    orig_index = index
    if index < 0:
        index += row_count
        if orig_index == -row_count - 1:
            index = 0
    if index < 0 or index > row_count:
        raise IndexError("table row index out of range")

    _ensure_table_cell_properties_loaded(table)
    if _row_insert_intersects_merge(table, index):
        raise ValueError(f"cannot insert row {index} through merged cells")
    col_count = len(table._rows[0]) if table._rows else 0
    new_row = ["" for _ in range(col_count)]
    table._rows.insert(index, new_row)
    table._payload["rows"] = table._rows

    heights = _table_row_heights(table)
    height = (
        heights[index - 1]
        if index > 0 and index - 1 < len(heights)
        else (heights[0] if heights else 370840)
    )
    heights.insert(index, height)
    table._payload["_row_heights"] = heights

    if "_cell_properties" in table._payload:
        old_props = table._payload["_cell_properties"]
        new_props = {}
        for key, val in old_props.items():
            r_str, c_str = key.split(":")
            r, c = int(r_str), int(c_str)
            if r >= index:
                new_props[f"{r + 1}:{c}"] = val
            else:
                new_props[key] = val
        table._payload["_cell_properties"] = new_props

    pres = table._slide._presentation
    slide_idx = table._slide._index
    tbl_idx = table._table_index

    for attr in _CELL_EDIT_ATTRS:
        if hasattr(pres, attr):
            setattr(
                pres,
                attr,
                _shift_cell_container_row(
                    getattr(pres, attr), slide_idx, tbl_idx, index, insert=True
                ),
            )

    new_height_edits = {}
    for (s, t, r), h in pres._table_row_height_edits.items():
        if s == slide_idx and t == tbl_idx:
            if r >= index:
                new_height_edits[(s, t, r + 1)] = h
            else:
                new_height_edits[(s, t, r)] = h
        else:
            new_height_edits[(s, t, r)] = h
    pres._table_row_height_edits = new_height_edits

    pres._queue_table_row_insert(slide_idx, tbl_idx, index)
    from .table_facade import TableRow

    return TableRow(table, index)


def _delete_table_row(table: Table, index: int) -> None:
    if not isinstance(index, int) or isinstance(index, bool):
        raise TypeError("index must be an integer")
    row_count = len(table._rows)
    if index < 0:
        index += row_count
    if index < 0 or index >= row_count:
        raise IndexError("table row index out of range")
    if row_count <= 1:
        raise ValueError("cannot delete the only row of a table")
    if _row_has_merged_cells(table, index):
        raise ValueError(f"cannot delete row {index} because it contains merged cells")

    _ensure_table_cell_properties_loaded(table)
    table._rows.pop(index)
    table._payload["rows"] = table._rows

    heights = _table_row_heights(table)
    if index < len(heights):
        heights.pop(index)
    table._payload["_row_heights"] = heights

    if "_cell_properties" in table._payload:
        old_props = table._payload["_cell_properties"]
        new_props = {}
        for key, val in old_props.items():
            r_str, c_str = key.split(":")
            r, c = int(r_str), int(c_str)
            if r == index:
                continue
            elif r > index:
                new_props[f"{r - 1}:{c}"] = val
            else:
                new_props[key] = val
        table._payload["_cell_properties"] = new_props

    pres = table._slide._presentation
    slide_idx = table._slide._index
    tbl_idx = table._table_index

    for attr in _CELL_EDIT_ATTRS:
        if hasattr(pres, attr):
            setattr(
                pres,
                attr,
                _shift_cell_container_row(
                    getattr(pres, attr), slide_idx, tbl_idx, index, insert=False
                ),
            )

    new_height_edits = {}
    for (s, t, r), h in pres._table_row_height_edits.items():
        if s == slide_idx and t == tbl_idx:
            if r == index:
                continue
            elif r > index:
                new_height_edits[(s, t, r - 1)] = h
            else:
                new_height_edits[(s, t, r)] = h
        else:
            new_height_edits[(s, t, r)] = h
    pres._table_row_height_edits = new_height_edits

    pres._queue_table_row_delete(slide_idx, tbl_idx, index)


def _insert_table_column(table: Table, index: int) -> Any:
    if not isinstance(index, int) or isinstance(index, bool):
        raise TypeError("index must be an integer")
    col_count = len(table._rows[0]) if table._rows else 0
    orig_index = index
    if index < 0:
        index += col_count
        if orig_index == -col_count - 1:
            index = 0
    if index < 0 or index > col_count:
        raise IndexError("table column index out of range")

    _ensure_table_cell_properties_loaded(table)
    if _column_insert_intersects_merge(table, index):
        raise ValueError(f"cannot insert column {index} through merged cells")
    for row in table._rows:
        row.insert(index, "")
    table._payload["rows"] = table._rows

    widths = _table_column_widths(table)
    width = (
        widths[index - 1]
        if index > 0 and index - 1 < len(widths)
        else (widths[0] if widths else 2743200)
    )
    widths.insert(index, width)
    table._payload["_column_widths"] = widths

    if "_cell_properties" in table._payload:
        old_props = table._payload["_cell_properties"]
        new_props = {}
        for key, val in old_props.items():
            r_str, c_str = key.split(":")
            r, c = int(r_str), int(c_str)
            if c >= index:
                new_props[f"{r}:{c + 1}"] = val
            else:
                new_props[key] = val
        table._payload["_cell_properties"] = new_props

    pres = table._slide._presentation
    slide_idx = table._slide._index
    tbl_idx = table._table_index

    for attr in _CELL_EDIT_ATTRS:
        if hasattr(pres, attr):
            setattr(
                pres,
                attr,
                _shift_cell_container_col(
                    getattr(pres, attr), slide_idx, tbl_idx, index, insert=True
                ),
            )

    new_width_edits = {}
    for (s, t, c), w in pres._table_column_width_edits.items():
        if s == slide_idx and t == tbl_idx:
            if c >= index:
                new_width_edits[(s, t, c + 1)] = w
            else:
                new_width_edits[(s, t, c)] = w
        else:
            new_width_edits[(s, t, c)] = w
    pres._table_column_width_edits = new_width_edits

    pres._queue_table_column_insert(slide_idx, tbl_idx, index)
    from .table_facade import TableColumn

    return TableColumn(table, index)


def _delete_table_column(table: Table, index: int) -> None:
    if not isinstance(index, int) or isinstance(index, bool):
        raise TypeError("index must be an integer")
    col_count = len(table._rows[0]) if table._rows else 0
    if index < 0:
        index += col_count
    if index < 0 or index >= col_count:
        raise IndexError("table column index out of range")
    if col_count <= 1:
        raise ValueError("cannot delete the only column of a table")
    if _col_has_merged_cells(table, index):
        raise ValueError(f"cannot delete column {index} because it contains merged cells")

    _ensure_table_cell_properties_loaded(table)
    for row in table._rows:
        if index < len(row):
            row.pop(index)
    table._payload["rows"] = table._rows

    widths = _table_column_widths(table)
    if index < len(widths):
        widths.pop(index)
    table._payload["_column_widths"] = widths

    if "_cell_properties" in table._payload:
        old_props = table._payload["_cell_properties"]
        new_props = {}
        for key, val in old_props.items():
            r_str, c_str = key.split(":")
            r, c = int(r_str), int(c_str)
            if c == index:
                continue
            elif c > index:
                new_props[f"{r}:{c - 1}"] = val
            else:
                new_props[key] = val
        table._payload["_cell_properties"] = new_props

    pres = table._slide._presentation
    slide_idx = table._slide._index
    tbl_idx = table._table_index

    for attr in _CELL_EDIT_ATTRS:
        if hasattr(pres, attr):
            setattr(
                pres,
                attr,
                _shift_cell_container_col(
                    getattr(pres, attr), slide_idx, tbl_idx, index, insert=False
                ),
            )

    new_width_edits = {}
    for (s, t, c), w in pres._table_column_width_edits.items():
        if s == slide_idx and t == tbl_idx:
            if c == index:
                continue
            elif c > index:
                new_width_edits[(s, t, c - 1)] = w
            else:
                new_width_edits[(s, t, c)] = w
        else:
            new_width_edits[(s, t, c)] = w
    pres._table_column_width_edits = new_width_edits

    pres._queue_table_column_delete(slide_idx, tbl_idx, index)
