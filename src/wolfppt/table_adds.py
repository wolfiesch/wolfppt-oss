"""Fast package-level table insertion for presentation saves."""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
    natural_key as _natural_key,
    resolve_package_target as _resolve_package_target,
)

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_CNVPR_ID_RE = re.compile(r"<p:cNvPr\b[^>]*\bid=\"([0-9]+)\"")


def apply_table_add(
    input_path: Path,
    output_path: Path,
    slide_index: int,
    rows: int,
    cols: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    cell_texts: list[tuple[int, int, str]] | None = None,
) -> None:
    if rows <= 0 or cols <= 0:
        raise ValueError("table rows and columns must be greater than zero")
    normalized_cell_texts = cell_texts or []
    for row_index, col_index, _text in normalized_cell_texts:
        if row_index >= rows or col_index >= cols:
            raise ValueError(
                f"table cell {row_index},{col_index} is outside {rows}x{cols} table"
            )

    with zipfile.ZipFile(input_path) as package:
        slide_parts = _presentation_slide_parts(package)
        try:
            slide_part = slide_parts[slide_index]
        except IndexError as exc:
            raise IndexError("slide index out of range") from exc
        slide_xml = package.read(slide_part).decode("utf-8")
        shape_id = _next_shape_id(slide_xml)
        updated_xml = _add_table_to_slide_xml(
            slide_xml,
            shape_id,
            rows,
            cols,
            x_emu,
            y_emu,
            cx_emu,
            cy_emu,
            normalized_cell_texts,
        )
        _copy_package_with_replacements(
            input_path,
            output_path,
            {slide_part: updated_xml.encode("utf-8")},
        )


def _presentation_slide_parts(package: zipfile.ZipFile) -> list[str]:
    try:
        presentation = ET.fromstring(package.read("ppt/presentation.xml"))
        relationships = ET.fromstring(package.read("ppt/_rels/presentation.xml.rels"))
    except KeyError:
        return _fallback_slide_parts(package)
    targets_by_id = {
        relationship.attrib.get("Id"): relationship.attrib.get("Target", "")
        for relationship in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    slide_parts: list[str] = []
    for slide_id in presentation.findall(f".//{{{P_NS}}}sldId"):
        rel_id = slide_id.attrib.get(f"{{{R_NS}}}id")
        target = targets_by_id.get(rel_id)
        if target:
            slide_parts.append(_resolve_package_target("ppt/presentation.xml", target))
    return slide_parts or _fallback_slide_parts(package)


def _fallback_slide_parts(package: zipfile.ZipFile) -> list[str]:
    return sorted(
        [
            name
            for name in package.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ],
        key=_natural_key,
    )


def _next_shape_id(slide_xml: str) -> int:
    ids = [int(match.group(1)) for match in _CNVPR_ID_RE.finditer(slide_xml)]
    if not ids:
        try:
            root = ET.fromstring(slide_xml)
        except ET.ParseError:
            return 1
        for element in root.iter():
            if not (element.tag == "cNvPr" or element.tag.endswith("}cNvPr")):
                continue
            try:
                ids.append(int(element.attrib.get("id", "0")))
            except ValueError:
                continue
    return max(ids, default=0) + 1


def _add_table_to_slide_xml(
    slide_xml: str,
    shape_id: int,
    rows: int,
    cols: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    cell_texts: list[tuple[int, int, str]],
) -> str:
    insert_at = slide_xml.rfind("</p:spTree>")
    if insert_at == -1:
        raise AttributeError("slide XML is missing </p:spTree>")
    table_xml = _table_shape_xml(
        shape_id,
        rows,
        cols,
        x_emu,
        y_emu,
        cx_emu,
        cy_emu,
        cell_texts,
    )
    return f"{slide_xml[:insert_at]}{table_xml}{slide_xml[insert_at:]}"


def _table_shape_xml(
    shape_id: int,
    rows: int,
    cols: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    cell_texts: list[tuple[int, int, str]],
) -> str:
    col_width = cx_emu // cols
    row_height = cy_emu // rows
    text_by_cell = {
        (row_index, col_index): text
        for row_index, col_index, text in cell_texts
    }
    grid_cols = "".join(f'<a:gridCol w="{col_width}"/>' for _ in range(cols))
    table_rows = []
    for row_index in range(rows):
        cells = []
        for col_index in range(cols):
            text = text_by_cell.get((row_index, col_index))
            paragraph_xml = (
                _replacement_paragraphs_xml(text)
                if text is not None
                else "<a:p><a:r><a:t></a:t></a:r></a:p>"
            )
            cells.append(
                "<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>"
                f"{paragraph_xml}</a:txBody><a:tcPr/></a:tc>"
            )
        table_rows.append(f'<a:tr h="{row_height}">{"".join(cells)}</a:tr>')
    return (
        f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" '
        f'name="Table {shape_id}"/><p:cNvGraphicFramePr>'
        '<a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/>'
        f'</p:nvGraphicFramePr><p:xfrm><a:off x="{x_emu}" y="{y_emu}"/>'
        f'<a:ext cx="{cx_emu}" cy="{cy_emu}"/></p:xfrm><a:graphic>'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
        '<a:tbl><a:tblPr firstRow="1" bandRow="1">'
        "<a:tableStyleId>{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}</a:tableStyleId>"
        f"</a:tblPr><a:tblGrid>{grid_cols}</a:tblGrid>"
        f'{"".join(table_rows)}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>'
    )


def _replacement_paragraphs_xml(text: str) -> str:
    return "".join(
        f"<a:p><a:r><a:t>{html.escape(line, quote=False)}</a:t></a:r></a:p>"
        for line in text.split("\n")
    )
