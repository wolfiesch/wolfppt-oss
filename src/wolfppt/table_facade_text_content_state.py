"""Text-content state helpers for table cell text frames."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from .table_facade import TableCell

from .shape_payloads import (
    _paragraph_runs_and_line_breaks,
    _paragraph_text_from_runs_and_line_breaks,
)
from .shape_xml import _text_paragraph_content
from .table_facade_cell_state import _table_cell_property_payload
from .table_facade_property_lists import (
    _fit_line_break_property_list,
    _fit_run_font_property_list,
    _fit_run_optional_string_property_list,
    _fit_run_property_list,
)
from .table_xml import _table_cell_xml_element
from .xml_helpers import xml_local_name as _xml_local_name

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Facade attribute -> direct ``a:pPr`` XML attribute. The values ride the table
# cell paragraph spacing queue, whose XML writer already serializes them.
_PARAGRAPH_XML_ATTRIBUTES = {
    "margin_left": "marL",
    "margin_right": "marR",
    "rtl": "rtl",
}


def _table_cell_text_frame_paragraph_attribute(
    cell: TableCell,
    paragraph_index: int,
    attr: str,
) -> int | bool | None:
    """Return a direct ``a:pPr`` attribute: pending edit, else saved XML."""
    if paragraph_index < 0 or paragraph_index >= len(
        _table_cell_text_frame_paragraph_texts(cell)
    ):
        raise IndexError("paragraph index out of range")
    presentation = cell._table._slide._presentation
    cell_key = (
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
    )
    pending = presentation._table_cell_text_frame_paragraph_spacing_edits.get(
        (*cell_key, paragraph_index),
        {},
    )
    if attr in pending:
        return pending[attr]
    if cell_key in presentation._table_cell_text_frame_content_edits:
        # Replaced paragraphs are written without paragraph properties.
        return None
    raw = _read_table_cell_text_frame_paragraph_attribute(
        cell,
        paragraph_index,
        _PARAGRAPH_XML_ATTRIBUTES[attr],
    )
    if raw is None:
        return None
    if attr == "rtl":
        if raw in ("1", "true"):
            return True
        if raw in ("0", "false"):
            return False
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _set_table_cell_text_frame_paragraph_attribute(
    cell: TableCell,
    paragraph_index: int,
    attr: str,
    value: int | bool | None,
) -> None:
    if _table_cell_text_frame_paragraph_attribute(cell, paragraph_index, attr) == value:
        return
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_spacing(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        attr,
        value,
    )


def _read_table_cell_text_frame_paragraph_attribute(
    cell: TableCell,
    paragraph_index: int,
    xml_attribute: str,
) -> str | None:
    slide_part = cell._table._slide.partname
    if not slide_part:
        return None
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
        return None
    if text_body is None:
        return None
    paragraphs = text_body.findall(f"{{{A_NS}}}p")
    if paragraph_index >= len(paragraphs):
        return None
    paragraph_properties = paragraphs[paragraph_index].find(f"{{{A_NS}}}pPr")
    if paragraph_properties is None:
        return None
    return paragraph_properties.get(xml_attribute)


def _hydrate_queued_table_text_content(cell: TableCell) -> None:
    """Project whole-cell/frame edits before falling back to saved run XML.

    The queue token changes only when whole content changes. Subsequent run
    setters retain their live cached values instead of hydrating the original
    whole-content value again during a read or find/replace dry run.
    """
    presentation = cell._table._slide._presentation
    key = (
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
    )
    if key in presentation._table_cell_text_frame_content_edits:
        paragraphs = presentation._table_cell_text_frame_content_edits[key]
        token = ("frame", tuple(paragraphs))
    elif key in presentation._table_cell_edits:
        text = presentation._table_cell_edits[key]
        paragraphs = text.split("\n") if text else [""]
        token = ("cell", tuple(paragraphs))
    else:
        return
    payload = _table_cell_property_payload(cell)
    properties = (
        "text_frame_paragraphs",
        "text_frame_paragraph_runs",
        "text_frame_paragraph_line_breaks",
    )
    if payload.get("_pending_text_frame_content_token") == token and all(
        name in payload for name in properties
    ):
        return
    parsed = [_paragraph_runs_and_line_breaks(str(text)) for text in paragraphs]
    payload["text_frame_paragraphs"] = list(paragraphs)
    payload["text_frame_paragraph_runs"] = [runs for runs, _ in parsed]
    payload["text_frame_paragraph_line_breaks"] = [breaks for _, breaks in parsed]
    payload["_pending_text_frame_content_token"] = token


def _table_cell_text_frame_paragraph_texts(cell: TableCell) -> list[str]:
    _hydrate_queued_table_text_content(cell)
    payload = _table_cell_property_payload(cell)
    paragraphs = payload.get("text_frame_paragraphs")
    if not isinstance(paragraphs, list):
        paragraphs = _read_table_cell_text_frame_paragraph_texts(cell)
        payload["text_frame_paragraphs"] = paragraphs
    return [str(paragraph) for paragraph in paragraphs] or [""]


def _read_table_cell_text_frame_paragraph_texts(cell: TableCell) -> list[str]:
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
            paragraphs = [
                _text_paragraph_content(paragraph)
                for paragraph in text_body.findall(f"{{{A_NS}}}p")
            ]
            if paragraphs:
                return paragraphs
    text = cell.text
    return text.split("\n") if text else [""]


def _table_cell_text_frame_paragraph_runs(
    cell: TableCell,
) -> list[list[str]]:
    _hydrate_queued_table_text_content(cell)
    payload = _table_cell_property_payload(cell)
    runs = payload.get("text_frame_paragraph_runs")
    if not isinstance(runs, list):
        runs = _read_table_cell_text_frame_paragraph_runs(cell)
        runs = _fit_run_property_list(
            runs,
            _table_cell_text_frame_paragraph_texts(cell),
        )
        payload["text_frame_paragraph_runs"] = runs
    return [
        [str(run) for run in paragraph_runs] if isinstance(paragraph_runs, list) else []
        for paragraph_runs in runs
    ]


def _table_cell_text_frame_paragraph_line_breaks(
    cell: TableCell,
) -> list[list[int]]:
    _hydrate_queued_table_text_content(cell)
    payload = _table_cell_property_payload(cell)
    line_breaks = payload.get("text_frame_paragraph_line_breaks")
    paragraph_runs = _table_cell_text_frame_paragraph_runs(cell)
    if not isinstance(line_breaks, list):
        line_breaks = _read_table_cell_text_frame_paragraph_line_breaks(cell)
        line_breaks = _fit_line_break_property_list(line_breaks, paragraph_runs)
        payload["text_frame_paragraph_line_breaks"] = line_breaks
    return [
        [int(slot) for slot in paragraph_line_breaks]
        if isinstance(paragraph_line_breaks, list)
        else []
        for paragraph_line_breaks in line_breaks
    ]


def _read_table_cell_text_frame_paragraph_runs(cell: TableCell) -> list[list[str]]:
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
            runs: list[list[str]] = []
            for paragraph in text_body.findall(f"{{{A_NS}}}p"):
                paragraph_runs: list[str] = []
                for run in paragraph.findall(f"{{{A_NS}}}r"):
                    text_node = run.find(f"{{{A_NS}}}t")
                    paragraph_runs.append(
                        "" if text_node is None else text_node.text or ""
                    )
                runs.append(paragraph_runs)
            if runs:
                return runs
    return [
        _paragraph_runs_and_line_breaks(paragraph)[0]
        for paragraph in _table_cell_text_frame_paragraph_texts(cell)
    ]


def _read_table_cell_text_frame_paragraph_line_breaks(
    cell: TableCell,
) -> list[list[int]]:
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
            line_breaks: list[list[int]] = []
            for paragraph in text_body.findall(f"{{{A_NS}}}p"):
                slots: list[int] = []
                run_slot = 0
                for child in paragraph:
                    local_name = _xml_local_name(child.tag)
                    if local_name == "br":
                        slots.append(run_slot)
                    elif local_name == "r":
                        run_slot += 1
                line_breaks.append(slots)
            if line_breaks:
                return line_breaks
    return [
        _paragraph_runs_and_line_breaks(paragraph)[1]
        for paragraph in _table_cell_text_frame_paragraph_texts(cell)
    ]


def _set_table_cell_text_frame_paragraph_runs(
    cell: TableCell,
    paragraph_index: int,
    runs: list[str],
) -> None:
    paragraph_runs = _table_cell_text_frame_paragraph_runs(cell)
    if paragraph_index < 0 or paragraph_index >= len(paragraph_runs):
        raise IndexError("paragraph index out of range")
    normalized = [str(run) for run in runs]
    if normalized == paragraph_runs[paragraph_index]:
        return
    paragraph_runs[paragraph_index] = normalized
    payload = _table_cell_property_payload(cell)
    payload["text_frame_paragraph_runs"] = paragraph_runs
    line_breaks = _fit_line_break_property_list(
        payload.get("text_frame_paragraph_line_breaks")
        if isinstance(payload.get("text_frame_paragraph_line_breaks"), list)
        else _table_cell_text_frame_paragraph_line_breaks(cell),
        paragraph_runs,
    )
    payload["text_frame_paragraph_line_breaks"] = line_breaks
    if isinstance(payload.get("text_frame_paragraph_run_fonts"), list):
        payload["text_frame_paragraph_run_fonts"] = _fit_run_font_property_list(
            payload["text_frame_paragraph_run_fonts"],
            paragraph_runs,
        )
    if isinstance(payload.get("text_frame_paragraph_run_hyperlinks"), list):
        payload["text_frame_paragraph_run_hyperlinks"] = (
            _fit_run_optional_string_property_list(
                payload["text_frame_paragraph_run_hyperlinks"],
                paragraph_runs,
            )
        )
    paragraphs = _table_cell_text_frame_paragraph_texts(cell)
    paragraphs[paragraph_index] = _paragraph_text_from_runs_and_line_breaks(
        normalized,
        line_breaks[paragraph_index],
    )
    payload["text_frame_paragraphs"] = paragraphs
    cell._table._rows[cell._row_idx][cell._col_idx] = "\n".join(paragraphs)
    cell._table._payload["rows"] = cell._table._rows
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_runs(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        normalized,
    )


def _set_table_cell_text_frame_paragraph_line_break(
    cell: TableCell,
    paragraph_index: int,
    run_slot: int,
) -> None:
    paragraph_runs = _table_cell_text_frame_paragraph_runs(cell)
    if paragraph_index < 0 or paragraph_index >= len(paragraph_runs):
        raise IndexError("paragraph index out of range")
    if run_slot < 0 or run_slot > len(paragraph_runs[paragraph_index]):
        raise IndexError("run slot out of range")
    line_breaks = _table_cell_text_frame_paragraph_line_breaks(cell)
    line_breaks[paragraph_index].append(run_slot)
    payload = _table_cell_property_payload(cell)
    payload["text_frame_paragraph_line_breaks"] = line_breaks
    paragraphs = _table_cell_text_frame_paragraph_texts(cell)
    paragraphs[paragraph_index] = _paragraph_text_from_runs_and_line_breaks(
        paragraph_runs[paragraph_index],
        line_breaks[paragraph_index],
    )
    payload["text_frame_paragraphs"] = paragraphs
    cell._table._rows[cell._row_idx][cell._col_idx] = "\n".join(paragraphs)
    cell._table._payload["rows"] = cell._table._rows
    cell._table._slide._presentation._queue_table_cell_text_frame_paragraph_line_break(
        cell._table._slide._index,
        cell._table._table_index,
        cell._row_idx,
        cell._col_idx,
        paragraph_index,
        run_slot,
    )
