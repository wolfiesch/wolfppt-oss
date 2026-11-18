"""XLSX chart data workbooks: deterministic authoring plus cell-level editing."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from copy import deepcopy
from datetime import date, datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

if TYPE_CHECKING:
    from .chart_data import ChartDataCell, ChartDataWorkbook, ChartDataWorksheet

_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_SS_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CORE_PROPS_REL_TYPE = (
    "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
)
_SHARED_STRINGS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"
)


def category_chart_workbook_blob(
    categories: list[str],
    series: list[dict[str, Any]],
    *,
    category_hierarchy: list[list[str]] | None = None,
    category_kind: str = "string",
) -> bytes:
    """Return a deterministic embedded XLSX workbook for category chart data."""
    shared_strings: list[str] = []
    shared_string_index: dict[str, int] = {}
    shared_string_refs = 0

    def intern(value: object) -> int:
        nonlocal shared_string_refs
        shared_string_refs += 1
        text = str(value)
        if text not in shared_string_index:
            shared_string_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_string_index[text]

    max_value_count = max(
        (len(item["values"]) for item in series),
        default=0,
    )
    category_column_count = _category_column_count(category_hierarchy)
    row_count = max(1, len(categories) + 1, max_value_count + 1)
    column_count = max(1, len(series) + category_column_count)
    rows: list[str] = []
    header_cells = [
        _shared_string_cell(
            _cell_ref(category_column_count + series_index + 1, 1),
            intern(item["name"]),
        )
        for series_index, item in enumerate(series)
    ]
    if header_cells:
        rows.append(f'<row r="1">{"".join(header_cells)}</row>')

    for row_index in range(2, row_count + 1):
        category_index = row_index - 2
        cells = []
        if category_index < len(categories):
            if category_hierarchy is None:
                if category_kind == "date":
                    cells.append(
                        _number_cell(
                            f"A{row_index}",
                            float(categories[category_index]),
                        )
                    )
                else:
                    cells.append(
                        _shared_string_cell(
                            f"A{row_index}",
                            intern(categories[category_index]),
                        )
                    )
            else:
                cells.extend(
                    _hierarchical_category_cells(
                        category_hierarchy,
                        category_index,
                        row_index,
                        intern,
                    )
                )
        for series_index, item in enumerate(series):
            values = item["values"]
            if category_index < len(values):
                cells.append(
                    _number_cell(
                        _cell_ref(category_column_count + series_index + 1, row_index),
                        float(values[category_index]),
                    )
                )
        if cells:
            rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    workbook = _workbook_xml()
    workbook_rels = _workbook_relationships_xml()
    worksheet = _worksheet_xml(row_count, column_count, rows)
    shared = _shared_strings_xml(shared_strings, shared_string_refs)
    styles = _styles_xml()
    content_types = _content_types_xml()
    root_rels = _root_relationships_xml()
    app_props = _app_properties_xml()
    core_props = _core_properties_xml()

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=1) as package:
        _write_part(package, "[Content_Types].xml", content_types)
        _write_part(package, "_rels/.rels", root_rels)
        _write_part(package, "docProps/app.xml", app_props)
        _write_part(package, "docProps/core.xml", core_props)
        _write_part(package, "xl/workbook.xml", workbook)
        _write_part(package, "xl/_rels/workbook.xml.rels", workbook_rels)
        _write_part(package, "xl/worksheets/sheet1.xml", worksheet)
        _write_part(package, "xl/styles.xml", styles)
        _write_part(package, "xl/sharedStrings.xml", shared)
    return buffer.getvalue()


def replace_category_chart_workbook_series(
    workbook_bytes: bytes,
    categories: list[str],
    series: list[dict[str, Any]],
    source_indexes: list[int],
) -> bytes:
    """Reorder existing business columns while preserving all non-sheet members."""
    if len(series) != len(source_indexes):
        raise ValueError("business-series source indexes must match replacement series")
    output = BytesIO()
    with (
        ZipFile(BytesIO(workbook_bytes)) as source,
        ZipFile(output, "w") as destination,
    ):
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                payload = _replace_category_chart_sheet(payload, categories, series, source_indexes)
            destination.writestr(info, payload)
    return output.getvalue()


def replace_category_chart_workbook_cardinality(
    workbook_bytes: bytes,
    categories: list[str],
    series: list[dict[str, Any]],
    source_category_count: int,
    source_series_count: int,
    style_source_indexes: list[int],
) -> bytes:
    """Resize a simple chart data rectangle without touching other XLSX members.

    Each result business column must name a source column whose formatting is
    approved for reuse. Formula-backed category and numeric business cells keep
    their formulas while their cached results and supported references update.
    Unsupported formula dependency graphs and worksheet layouts are refused.
    """
    if not categories or not series:
        raise ValueError("resizable category charts require categories and series")
    if len(series) != len(style_source_indexes):
        raise ValueError("each replacement business series requires a source style")
    if source_category_count < 1 or source_series_count < 1:
        raise ValueError("source chart must contain categories and business series")
    if any(index < 0 or index >= source_series_count for index in style_source_indexes):
        raise ValueError("business-series style source is outside the source chart")
    output = BytesIO()
    with (
        ZipFile(BytesIO(workbook_bytes)) as source,
        ZipFile(output, "w") as destination,
    ):
        shared_strings = _shared_string_values(source)
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                payload = _replace_category_chart_sheet_cardinality(
                    payload,
                    categories,
                    series,
                    source_category_count,
                    source_series_count,
                    style_source_indexes,
                    shared_strings,
                )
            destination.writestr(info, payload)
    return output.getvalue()


def _replace_category_chart_sheet_cardinality(
    sheet_bytes: bytes,
    categories: list[str],
    series: list[dict[str, Any]],
    source_category_count: int,
    source_series_count: int,
    style_source_indexes: list[int],
    shared_strings: list[str],
) -> bytes:
    root = ET.fromstring(sheet_bytes)
    dimension = root.find(f"{{{_SS_NS}}}dimension")
    expected_dimension = f"A1:{_cell_ref(source_series_count + 1, source_category_count + 1)}"
    if dimension is None or dimension.get("ref") != expected_dimension:
        raise ValueError("embedded workbook worksheet must contain only its chart data rectangle")
    sheet_data = root.find(f"{{{_SS_NS}}}sheetData")
    if sheet_data is None:
        raise ValueError("embedded workbook chart sheet data is unavailable")
    rows_by_number = {
        int(row.get("r", "0")): row
        for row in sheet_data.findall(f"{{{_SS_NS}}}row")
        if row.get("r", "").isdigit()
    }
    if set(rows_by_number) != set(range(1, source_category_count + 2)):
        raise ValueError("embedded workbook chart rows are not contiguous")
    cells = {
        cell.get("r"): cell
        for row in rows_by_number.values()
        for cell in row.findall(f"{{{_SS_NS}}}c")
        if cell.get("r") is not None
    }
    source_cells = {
        _cell_ref(column, row)
        for row in range(1, source_category_count + 2)
        for column in range(1, source_series_count + 2)
        if (column, row) != (1, 1)
    }
    if set(cells) != source_cells:
        raise ValueError(
            "embedded workbook chart sheet has unsupported cells outside the data rectangle"
        )
    _ensure_chart_data_cells_are_supported(cells, source_category_count, source_series_count)
    for row in list(sheet_data):
        sheet_data.remove(row)
    for row_index in range(1, len(categories) + 2):
        source_row_index = 1 if row_index == 1 else min(row_index, source_category_count + 1)
        row = deepcopy(rows_by_number[source_row_index])
        row.set("r", str(row_index))
        for cell in list(row):
            row.remove(cell)
        for column_index in range(1, len(series) + 2):
            if row_index == 1 and column_index == 1:
                continue
            source_column = 1 if column_index == 1 else style_source_indexes[column_index - 2] + 2
            source_ref = _cell_ref(source_column, source_row_index)
            source_cell = cells[_cell_ref(source_column, source_row_index)]
            cell = deepcopy(source_cell)
            cell.set("r", _cell_ref(column_index, row_index))
            _retarget_moved_chart_formula(
                cell,
                source_ref,
                _cell_ref(column_index, row_index),
                cells,
                source_category_count,
                source_series_count,
                len(categories),
                len(series),
            )
            if row_index == 1 and column_index > 1:
                if _shared_string_cell_value(source_cell, shared_strings) != str(
                    series[column_index - 2]["name"]
                ):
                    _set_inline_string(cell, str(series[column_index - 2]["name"]))
            elif row_index > 1 and column_index == 1:
                _set_inline_string(cell, categories[row_index - 2])
            elif row_index > 1:
                _set_numeric_cell(cell, float(series[column_index - 2]["values"][row_index - 2]))
            row.append(cell)
        sheet_data.append(row)
    dimension.set("ref", f"A1:{_cell_ref(len(series) + 1, len(categories) + 1)}")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _shared_string_values(workbook: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(item.itertext()) for item in root.findall(f"{{{_SS_NS}}}si")]


def _shared_string_cell_value(cell: ET.Element, values: list[str]) -> str:
    value = cell.findtext(f"{{{_SS_NS}}}v")
    if cell.get("t") != "s" or value is None or not value.isdigit():
        raise ValueError("embedded workbook chart header must be a shared string")
    try:
        return values[int(value)]
    except IndexError as exc:
        raise ValueError("embedded workbook chart header shared string is unavailable") from exc


_FORMULA_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_.])"
    r"(?:(?P<sheet>'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)?"
    r"(?P<column>\$?[A-Za-z]{1,3})(?P<row>\$?[1-9][0-9]*)"
    r"(?![A-Za-z0-9_.])"
)


def _ensure_chart_data_cells_are_supported(
    cells: dict[str, ET.Element], category_count: int, series_count: int
) -> None:
    for row_index in range(1, category_count + 2):
        for column_index in range(1, series_count + 2):
            if (column_index, row_index) == (1, 1):
                continue
            reference = _cell_ref(column_index, row_index)
            cell = cells.get(reference)
            if cell is None:
                raise ValueError("embedded workbook chart data cell is unavailable")
            formula = cell.find(f"{{{_SS_NS}}}f")
            if formula is not None:
                if row_index == 1:
                    raise ValueError("embedded workbook chart series-name formulas are unsupported")
                if cell.find(f"{{{_SS_NS}}}v") is None:
                    raise ValueError("embedded workbook formula cache is unavailable")
                _validate_chart_formula(
                    formula.text,
                    cells,
                    category_count,
                    series_count,
                )
            elif cell.find(f"{{{_SS_NS}}}v") is None and cell.find(f"{{{_SS_NS}}}is") is None:
                raise ValueError("embedded workbook chart data cell is unavailable")


def _formula_segments(formula: str) -> list[tuple[bool, str]]:
    segments: list[tuple[bool, str]] = []
    start = 0
    cursor = 0
    while cursor < len(formula):
        if formula[cursor] != '"':
            cursor += 1
            continue
        if start < cursor:
            segments.append((True, formula[start:cursor]))
        literal_start = cursor
        cursor += 1
        while cursor < len(formula):
            if formula[cursor] == '"':
                if cursor + 1 < len(formula) and formula[cursor + 1] == '"':
                    cursor += 2
                    continue
                cursor += 1
                break
            cursor += 1
        else:
            raise ValueError("embedded workbook formula has an unterminated string")
        segments.append((False, formula[literal_start:cursor]))
        start = cursor
    if start < len(formula):
        segments.append((True, formula[start:]))
    return segments


def _excel_column_index(column: str) -> int:
    result = 0
    for character in column.removeprefix("$").upper():
        result = result * 26 + ord(character) - ord("A") + 1
    return result


def _formula_sheet_name(sheet: str | None) -> str | None:
    if sheet is None:
        return None
    name = sheet[:-1]
    if name.startswith("'") and name.endswith("'"):
        name = name[1:-1].replace("''", "'")
    return name


def _formula_references(formula: str) -> list[re.Match[str]]:
    references: list[re.Match[str]] = []
    for code, segment in _formula_segments(formula):
        if code:
            references.extend(_FORMULA_REFERENCE.finditer(segment))
    return references


def _validate_chart_formula(
    formula: str | None,
    cells: dict[str, ET.Element],
    category_count: int,
    series_count: int,
) -> None:
    if formula is None or not formula.strip():
        raise ValueError("embedded workbook formula is unavailable")
    code = "".join(segment for is_code, segment in _formula_segments(formula) if is_code)
    if "[" in code or "]" in code:
        raise ValueError("embedded workbook external formula references are unsupported")
    references = _formula_references(formula)
    if not references:
        raise ValueError("embedded workbook formula has no cell references")
    for reference in references:
        sheet_name = _formula_sheet_name(reference["sheet"])
        if sheet_name is not None and sheet_name.casefold() != "sheet1":
            raise ValueError("embedded workbook cross-sheet formula references are unsupported")
        column_index = _excel_column_index(reference["column"])
        row_index = int(reference["row"].removeprefix("$"))
        if column_index > series_count + 1 or row_index > category_count + 1:
            raise ValueError("embedded workbook formula dependency is outside chart data")
        dependency = cells.get(_cell_ref(column_index, row_index))
        if dependency is None or dependency.find(f"{{{_SS_NS}}}f") is not None:
            raise ValueError("embedded workbook formula dependency graph is unsupported")
    remaining = _FORMULA_REFERENCE.sub("", code)
    for identifier in re.finditer(r"[A-Za-z_][A-Za-z0-9_.]*", remaining):
        token = identifier.group()
        if token.upper() in {"TRUE", "FALSE"}:
            continue
        if remaining[identifier.end() :].lstrip().startswith("("):
            continue
        raise ValueError("embedded workbook formula uses an unsupported name")
    if code.count("(") != code.count(")"):
        raise ValueError("embedded workbook formula has unbalanced parentheses")


def _retarget_moved_chart_formula(
    cell: ET.Element,
    source_ref: str,
    target_ref: str,
    cells: dict[str, ET.Element],
    source_category_count: int,
    source_series_count: int,
    target_category_count: int,
    target_series_count: int,
) -> None:
    formula = cell.find(f"{{{_SS_NS}}}f")
    if formula is None:
        return
    _validate_chart_formula(
        formula.text,
        cells,
        source_category_count,
        source_series_count,
    )
    source_column, source_row = _cell_reference_coordinates(source_ref)
    target_column, target_row = _cell_reference_coordinates(target_ref)

    def retarget(segment: str) -> str:
        def move(reference: re.Match[str]) -> str:
            column_text = reference["column"]
            row_text = reference["row"]
            column_index = _excel_column_index(column_text)
            row_index = int(row_text.removeprefix("$"))
            if not column_text.startswith("$"):
                column_index += target_column - source_column
            if not row_text.startswith("$"):
                row_index += target_row - source_row
            if (
                column_index < 1
                or row_index < 1
                or column_index > target_series_count + 1
                or row_index > target_category_count + 1
            ):
                raise ValueError("embedded workbook formula move produces #REF!")
            return (
                f"{reference['sheet'] or ''}"
                f"{'$' if column_text.startswith('$') else ''}"
                f"{_excel_column_name(column_index)}"
                f"{'$' if row_text.startswith('$') else ''}{row_index}"
            )

        return _FORMULA_REFERENCE.sub(move, segment)

    formula.text = "".join(
        retarget(segment) if is_code else segment
        for is_code, segment in _formula_segments(formula.text or "")
    )


def _cell_reference_coordinates(reference: str) -> tuple[int, int]:
    match = _FORMULA_REFERENCE.fullmatch(reference)
    if match is None:
        raise ValueError("embedded workbook cell reference is invalid")
    return _excel_column_index(match["column"]), int(match["row"].removeprefix("$"))


def _set_numeric_cell(cell: ET.Element, value: float) -> None:
    # Retain explicit numeric typing, including on caller-supplied formula caches.
    if cell.get("t") != "n":
        cell.attrib.pop("t", None)
    for child in list(cell):
        if child.tag in {f"{{{_SS_NS}}}is", f"{{{_SS_NS}}}v"}:
            cell.remove(child)
    ET.SubElement(cell, f"{{{_SS_NS}}}v").text = _number_text(value)


def _replace_category_chart_sheet(
    sheet_bytes: bytes,
    categories: list[str],
    series: list[dict[str, Any]],
    source_indexes: list[int],
) -> bytes:
    root = ET.fromstring(sheet_bytes)
    rows = root.findall(f".//{{{_SS_NS}}}sheetData/{{{_SS_NS}}}row")
    if len(rows) != len(categories) + 1:
        raise ValueError("embedded workbook category row count does not match request")
    cells: dict[str, tuple[ET.Element, int, ET.Element]] = {}
    for row in rows:
        for index, cell in enumerate(row.findall(f"{{{_SS_NS}}}c")):
            reference = cell.get("r")
            if reference is not None:
                cells[reference] = (row, index, cell)
    if any(index < 0 for index in source_indexes):
        raise ValueError("business-series source index is invalid")
    source_series_count = max(source_indexes, default=-1) + 1
    worksheet_cells = {reference: cell for reference, (_row, _index, cell) in cells.items()}
    _ensure_chart_data_cells_are_supported(worksheet_cells, len(categories), source_series_count)

    replacements: list[tuple[ET.Element, int, ET.Element]] = []
    for replacement_index, (series_payload, source_index) in enumerate(
        zip(series, source_indexes, strict=True)
    ):
        target_column = replacement_index + 2
        source_column = source_index + 2
        values = list(series_payload["values"])
        if len(values) != len(categories):
            raise ValueError("business-series value count does not match categories")
        for row_index in range(1, len(categories) + 2):
            source_ref = _cell_ref(source_column, row_index)
            target_ref = _cell_ref(target_column, row_index)
            source_cell = cells.get(source_ref)
            target_cell = cells.get(target_ref)
            if source_cell is None or target_cell is None:
                raise ValueError("embedded workbook business-series cell is unavailable")
            moved = deepcopy(source_cell[2])
            moved.set("r", target_ref)
            _retarget_moved_chart_formula(
                moved,
                source_ref,
                target_ref,
                worksheet_cells,
                len(categories),
                source_series_count,
                len(categories),
                len(series),
            )
            if row_index > 1:
                _set_numeric_cell(
                    moved,
                    float(values[row_index - 2]),
                )
            replacements.append((target_cell[0], target_cell[1], moved))

    for row_index, category in enumerate(categories, start=2):
        category_cell = cells.get(_cell_ref(1, row_index))
        if category_cell is None:
            raise ValueError("embedded workbook category cell is unavailable")
        _set_inline_string(category_cell[2], category)

    for row, index, replacement in replacements:
        row.remove(list(row)[index])
        row.insert(index, replacement)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _set_inline_string(cell: ET.Element, value: str) -> None:
    if cell.find(f"{{{_SS_NS}}}f") is not None:
        cell.attrib.pop("t", None)
        for child in (
            cell.find(f"{{{_SS_NS}}}v"),
            cell.find(f"{{{_SS_NS}}}is"),
        ):
            if child is not None:
                cell.remove(child)
        ET.SubElement(cell, f"{{{_SS_NS}}}v").text = value
        return
    cell.set("t", "inlineStr")
    for child in (
        cell.find(f"{{{_SS_NS}}}v"),
        cell.find(f"{{{_SS_NS}}}is"),
    ):
        if child is not None:
            cell.remove(child)
    inline_string = ET.SubElement(cell, f"{{{_SS_NS}}}is")
    text = ET.SubElement(inline_string, f"{{{_SS_NS}}}t")
    text.text = value


def _category_column_count(category_hierarchy: list[list[str]] | None) -> int:
    if category_hierarchy is None:
        return 1
    return max((len(path) for path in category_hierarchy), default=1)


def _hierarchical_category_cells(
    category_hierarchy: list[list[str]],
    category_index: int,
    row_index: int,
    intern: Any,
) -> list[str]:
    depth = _category_column_count(category_hierarchy)
    path = _padded_category_path(category_hierarchy[category_index], depth)
    previous_path = (
        None
        if category_index == 0
        else _padded_category_path(category_hierarchy[category_index - 1], depth)
    )
    cells: list[str] = []
    for level_index, label in enumerate(path):
        if not label:
            continue
        if (
            previous_path is not None
            and previous_path[: level_index + 1] == path[: level_index + 1]
        ):
            continue
        cells.append(
            _shared_string_cell(
                _cell_ref(level_index + 1, row_index),
                intern(label),
            )
        )
    return cells


def _padded_category_path(path: list[str], depth: int) -> list[str]:
    return [*([""] * (depth - len(path))), *path]


def xy_chart_workbook_blob(series: list[dict[str, Any]]) -> bytes:
    """Return a deterministic embedded XLSX workbook for XY chart data."""
    shared_strings: list[str] = []
    shared_string_index: dict[str, int] = {}
    shared_string_refs = 0

    def intern(value: object) -> int:
        nonlocal shared_string_refs
        shared_string_refs += 1
        text = str(value)
        if text not in shared_string_index:
            shared_string_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_string_index[text]

    rows: list[str] = []
    current_row = 1
    for item in series:
        x_values = [float(value) for value in item["x_values"]]
        y_values = [float(value) for value in item["values"]]
        item["name_formula"] = f"Sheet1!$B${current_row}"
        item["x_formula"] = f"Sheet1!$A${current_row + 1}:$A${current_row + len(x_values)}"
        item["y_formula"] = f"Sheet1!$B${current_row + 1}:$B${current_row + len(y_values)}"
        rows.append(
            f'<row r="{current_row}">'
            f"{_shared_string_cell(f'B{current_row}', intern(item['name']))}"
            "</row>"
        )
        for offset, (x_value, y_value) in enumerate(
            zip(x_values, y_values, strict=True),
            start=1,
        ):
            row_index = current_row + offset
            rows.append(
                f'<row r="{row_index}">'
                f"{_number_cell(f'A{row_index}', x_value)}"
                f"{_number_cell(f'B{row_index}', y_value)}"
                "</row>"
            )
        current_row += len(x_values) + 2

    row_count = max(1, current_row - 2)
    workbook = _workbook_xml()
    workbook_rels = _workbook_relationships_xml()
    worksheet = _worksheet_xml(row_count, 2, rows)
    shared = _shared_strings_xml(shared_strings, shared_string_refs)
    styles = _styles_xml()
    content_types = _content_types_xml()
    root_rels = _root_relationships_xml()
    app_props = _app_properties_xml()
    core_props = _core_properties_xml()

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=1) as package:
        _write_part(package, "[Content_Types].xml", content_types)
        _write_part(package, "_rels/.rels", root_rels)
        _write_part(package, "docProps/app.xml", app_props)
        _write_part(package, "docProps/core.xml", core_props)
        _write_part(package, "xl/workbook.xml", workbook)
        _write_part(package, "xl/_rels/workbook.xml.rels", workbook_rels)
        _write_part(package, "xl/worksheets/sheet1.xml", worksheet)
        _write_part(package, "xl/styles.xml", styles)
        _write_part(package, "xl/sharedStrings.xml", shared)
    return buffer.getvalue()


def bubble_chart_workbook_blob(series: list[dict[str, Any]]) -> bytes:
    """Return a deterministic embedded XLSX workbook for bubble chart data."""
    shared_strings: list[str] = []
    shared_string_index: dict[str, int] = {}
    shared_string_refs = 0

    def intern(value: object) -> int:
        nonlocal shared_string_refs
        shared_string_refs += 1
        text = str(value)
        if text not in shared_string_index:
            shared_string_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_string_index[text]

    rows: list[str] = []
    current_row = 1
    for item in series:
        x_values = [float(value) for value in item["x_values"]]
        y_values = [float(value) for value in item["values"]]
        bubble_sizes = [float(value) for value in item["bubble_sizes"]]
        item["name_formula"] = f"Sheet1!$B${current_row}"
        item["x_formula"] = f"Sheet1!$A${current_row + 1}:$A${current_row + len(x_values)}"
        item["y_formula"] = f"Sheet1!$B${current_row + 1}:$B${current_row + len(y_values)}"
        item["bubble_size_formula"] = (
            f"Sheet1!$C${current_row + 1}:$C${current_row + len(bubble_sizes)}"
        )
        rows.append(
            f'<row r="{current_row}">'
            f"{_shared_string_cell(f'B{current_row}', intern(item['name']))}"
            "</row>"
        )
        for offset, (x_value, y_value, bubble_size) in enumerate(
            zip(x_values, y_values, bubble_sizes, strict=True),
            start=1,
        ):
            row_index = current_row + offset
            rows.append(
                f'<row r="{row_index}">'
                f"{_number_cell(f'A{row_index}', x_value)}"
                f"{_number_cell(f'B{row_index}', y_value)}"
                f"{_number_cell(f'C{row_index}', bubble_size)}"
                "</row>"
            )
        current_row += len(x_values) + 2

    row_count = max(1, current_row - 2)
    workbook = _workbook_xml()
    workbook_rels = _workbook_relationships_xml()
    worksheet = _worksheet_xml(row_count, 3, rows)
    shared = _shared_strings_xml(shared_strings, shared_string_refs)
    styles = _styles_xml()
    content_types = _content_types_xml()
    root_rels = _root_relationships_xml()
    app_props = _app_properties_xml()
    core_props = _core_properties_xml()

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=1) as package:
        _write_part(package, "[Content_Types].xml", content_types)
        _write_part(package, "_rels/.rels", root_rels)
        _write_part(package, "docProps/app.xml", app_props)
        _write_part(package, "docProps/core.xml", core_props)
        _write_part(package, "xl/workbook.xml", workbook)
        _write_part(package, "xl/_rels/workbook.xml.rels", workbook_rels)
        _write_part(package, "xl/worksheets/sheet1.xml", worksheet)
        _write_part(package, "xl/styles.xml", styles)
        _write_part(package, "xl/sharedStrings.xml", shared)
    return buffer.getvalue()


def _write_part(package: ZipFile, name: str, payload: str) -> None:
    info = ZipInfo(name, date_time=_FIXED_ZIP_DATE)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    package.writestr(info, payload.encode("utf-8"), compresslevel=1)


def _worksheet_xml(row_count: int, column_count: int, rows: list[str]) -> str:
    last_ref = _cell_ref(column_count, row_count)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{_SS_NS}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="A1:{last_ref}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f"<sheetData>{''.join(rows)}</sheetData>"
        '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" '
        'header="0.3" footer="0.3"/>'
        "</worksheet>"
    )


def _shared_strings_xml(strings: list[str], refs: int) -> str:
    items = "".join(f"<si>{_text_element(text)}</si>" for text in strings)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="{_SS_NS}" count="{refs}" uniqueCount="{len(strings)}">'
        f"{items}</sst>"
    )


def _text_element(text: str) -> str:
    from xml.sax.saxutils import escape

    attrs = ' xml:space="preserve"' if text != text.strip() else ""
    return f"<t{attrs}>{escape(text)}</t>"


def _shared_string_cell(ref: str, index: int) -> str:
    return f'<c r="{ref}" t="s"><v>{index}</v></c>'


def _number_cell(ref: str, value: float) -> str:
    return f'<c r="{ref}"><v>{_number_text(value)}</v></c>'


def _number_text(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return format(value, ".15g")


def _cell_ref(column_index: int, row_index: int) -> str:
    return f"{_excel_column_name(column_index)}{row_index}"


def _excel_column_name(column_index: int) -> str:
    name = ""
    current = column_index
    while current:
        current, remainder = divmod(current - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def _workbook_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{_SS_NS}" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )


def _workbook_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_REL_NS}">'
        f'<Relationship Id="rId1" Type="{_DOC_REL_NS}/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        f'<Relationship Id="rId2" Type="{_DOC_REL_NS}/styles" Target="styles.xml"/>'
        f'<Relationship Id="rId3" Type="{_DOC_REL_NS}/sharedStrings" '
        'Target="sharedStrings.xml"/>'
        "</Relationships>"
    )


def _root_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_REL_NS}">'
        f'<Relationship Id="rId1" Type="{_DOC_REL_NS}/officeDocument" '
        'Target="xl/workbook.xml"/>'
        f'<Relationship Id="rId2" Type="{_DOC_REL_NS}/extended-properties" '
        'Target="docProps/app.xml"/>'
        f'<Relationship Id="rId3" Type="{_CORE_PROPS_REL_TYPE}" '
        'Target="docProps/core.xml"/>'
        "</Relationships>"
    )


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f'<Override PartName="/xl/sharedStrings.xml" '
        f'ContentType="{_SHARED_STRINGS_CONTENT_TYPE}"/>'
        "</Types>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{_SS_NS}">'
        '<fonts count="1"><font><sz val="11"/><color theme="1"/>'
        '<name val="Calibri"/><family val="2"/><scheme val="minor"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" '
        'fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" '
        'borderId="0" xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '<dxfs count="0"/><tableStyles count="0" defaultTableStyle="TableStyleMedium2" '
        'defaultPivotStyle="PivotStyleLight16"/></styleSheet>'
    )


def _app_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<Properties "
        'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        'extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>WolfPPT</Application></Properties>"
    )


def _core_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<cp:coreProperties "
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:creator>WolfPPT</dc:creator>"
        '<dcterms:created xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:modified>'
        "</cp:coreProperties>"
    )


# ---------------------------------------------------------------------------
# Cell-level editing of an existing chart data workbook.

_CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_OFFICE_DOCUMENT_REL_TYPE = f"{_DOC_REL_NS}/officeDocument"
_WORKSHEET_REL_TYPE = f"{_DOC_REL_NS}/worksheet"
_SHARED_STRINGS_REL_TYPE = f"{_DOC_REL_NS}/sharedStrings"
_STYLES_REL_TYPE = f"{_DOC_REL_NS}/styles"
_WORKSHEET_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)
_XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
_MAX_COLUMN = 16_384
_MAX_ROW = 1_048_576
_CELL_ADDRESS = re.compile(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)")
_PLAIN_SHEET_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_INVALID_SHEET_NAME_CHARACTERS = frozenset("[]:*?/\\")


class CellError(str):
    """An Excel error value (``#DIV/0!``, ``#VALUE!``...) held by a workbook cell."""

    __slots__ = ()

    def __repr__(self) -> str:
        return f"CellError({str(self)!r})"


CellValue = float | str | bool | CellError | date | datetime | None


class ChartCellValueRefusal(TypeError):
    """An unsupported chart-cell value, refused before creating or changing a cell."""


def _validated_date_value(value: date) -> date:
    """Accept calendar dates and naive date-times; Excel has no timezone semantics."""
    if isinstance(value, datetime) and value.utcoffset() is not None:
        raise ChartCellValueRefusal("cell date-time values must be timezone-naive")
    return value


def _read_date_value(raw: str) -> date | datetime:
    """Decode explicit SpreadsheetML ``t=d`` ISO values without guessing from styles."""
    try:
        return datetime.fromisoformat(raw) if "T" in raw or " " in raw else date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"worksheet date cell value {raw!r} is invalid") from exc


def _excel_date_number(value: date, *, date1904: bool) -> float:
    """Chart/formula serial with the workbook epoch and Excel's fictitious leap day."""
    calendar_date = value.date() if isinstance(value, datetime) else value
    epoch = date(1904, 1, 1) if date1904 else date(1899, 12, 31)
    days = (calendar_date - epoch).days
    if not date1904 and calendar_date >= date(1900, 3, 1):
        days += 1
    if isinstance(value, datetime):
        seconds = value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6
        return days + seconds / 86400
    return float(days)


class UnsupportedFormulaError(ValueError):
    """Raised when a formula uses syntax or functions the evaluator lacks."""


def parse_cell_address(address: str) -> tuple[int, int]:
    """Return the one-based ``(row, column)`` of an A1 address such as ``$B$2``."""
    match = _CELL_ADDRESS.fullmatch(str(address).strip())
    if match is None:
        raise ValueError(f"cell address {address!r} is invalid")
    column = _excel_column_index(match[1])
    row = int(match[2])
    if column > _MAX_COLUMN or row > _MAX_ROW:
        raise ValueError(f"cell address {address!r} is outside the worksheet")
    return row, column


def cell_address(row: int, column: int, *, absolute: bool = False) -> str:
    """Return the A1 address for one-based ``row`` and ``column``."""
    if not 1 <= row <= _MAX_ROW or not 1 <= column <= _MAX_COLUMN:
        raise ValueError("cell coordinates are outside the worksheet")
    if absolute:
        return f"${_excel_column_name(column)}${row}"
    return _cell_ref(column, row)


def quote_sheet_name(name: str) -> str:
    """Return ``name`` as it must appear before ``!`` in a formula reference."""
    if _PLAIN_SHEET_NAME.fullmatch(name) and not re.fullmatch(
        r"(?:[A-Za-z]{1,3}[0-9]+|[Rr][0-9]*(?:[Cc][0-9]*)?|[Cc][0-9]*|TRUE|FALSE)",
        name,
        flags=re.IGNORECASE,
    ):
        return name
    return "'" + name.replace("'", "''") + "'"


def parse_chart_reference(
    formula: str,
) -> list[tuple[str | None, int, int, int, int]]:
    """Split a chart ``c:f`` reference into ``(sheet, row1, col1, row2, col2)`` areas.

    Accepts ``Sheet1!$A$2:$A$4``, quoted sheet names and parenthesised unions
    such as ``(Sheet1!$B$2,Sheet1!$D$2)``. Areas are returned in formula order.
    """
    text = str(formula).strip()
    if text.startswith("="):
        text = text[1:].strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    areas: list[tuple[str | None, int, int, int, int]] = []
    for part in _split_reference_union(text):
        sheet: str | None = None
        body = part.strip()
        if "!" in body:
            raw_sheet, body = body.rsplit("!", 1)
            sheet = _formula_sheet_name(raw_sheet + "!")
            if sheet is None or not sheet or "[" in raw_sheet:
                raise ValueError(f"chart reference {formula!r} is unsupported")
        first, _, last = body.partition(":")
        row1, column1 = parse_cell_address(first)
        row2, column2 = parse_cell_address(last) if last else (row1, column1)
        areas.append(
            (
                sheet,
                min(row1, row2),
                min(column1, column2),
                max(row1, row2),
                max(column1, column2),
            )
        )
    if not areas:
        raise ValueError("chart reference is empty")
    return areas


def _split_reference_union(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    for character in text:
        if character == "'":
            quoted = not quoted
        if character == "," and not quoted:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))
    return [part for part in parts if part.strip()]


def chart_reference_for_cells(cells: Sequence[ChartDataCell]) -> str:
    """Return the absolute ``c:f`` reference addressing ``cells`` in order.

    Consecutive cells along one row or column collapse into a range; anything
    else becomes a parenthesised union of areas.
    """
    if not cells:
        raise ValueError("a chart reference needs at least one cell")
    areas: list[tuple[ChartDataCell, ChartDataCell]] = []
    for cell in cells:
        if areas:
            start, end = areas[-1]
            if _extends_run(start, end, cell):
                areas[-1] = (start, cell)
                continue
        areas.append((cell, cell))
    texts = []
    for start, end in areas:
        prefix = quote_sheet_name(start.worksheet.name) + "!"
        if start is end:
            texts.append(prefix + start.absolute_address)
        else:
            texts.append(f"{prefix}{start.absolute_address}:{end.absolute_address}")
    if len(texts) == 1:
        return texts[0]
    return "(" + ",".join(texts) + ")"


def _extends_run(start: ChartDataCell, end: ChartDataCell, cell: ChartDataCell) -> bool:
    if cell.worksheet is not start.worksheet:
        return False
    if start.row == end.row == cell.row and start.column <= end.column:
        return cell.column == end.column + 1
    if start.column == end.column == cell.column and start.row <= end.row:
        return cell.row == end.row + 1
    return False


def serialize_xml_preserving_namespaces(root: ET.Element, source: bytes) -> bytes:
    """Serialize ``root`` keeping the source document's namespace prefixes.

    Markup-compatibility ``Ignorable`` prefixes are re-declared on the root
    even when no element uses them, so Office does not reject the part.
    """
    from xml.sax.saxutils import escape

    declarations = [value for _event, value in ET.iterparse(BytesIO(source), events=("start-ns",))]
    default_namespace = next((uri for prefix, uri in declarations if not prefix), None)
    namespace_map: dict[str, str] = ET._namespace_map  # type: ignore[attr-defined]
    saved = dict(namespace_map)
    placeholder = "wolfpptdefaultns"
    try:
        for prefix, uri in declarations:
            if prefix and not re.fullmatch(r"ns[0-9]+", prefix):
                ET.register_namespace(prefix, uri)
        if default_namespace is not None:
            ET.register_namespace(placeholder, default_namespace)
        text = ET.tostring(root, encoding="unicode")
    finally:
        namespace_map.clear()
        namespace_map.update(saved)
    if default_namespace is not None and f"xmlns:{placeholder}=" in text:
        text = text.replace(f"<{placeholder}:", "<").replace(f"</{placeholder}:", "</")
        if f"{placeholder}:" in text.replace(f"xmlns:{placeholder}=", ""):
            head_end = text.index(">")
            if text[head_end - 1] == "/":
                head_end -= 1
            text = text[:head_end] + f' xmlns="{escape(default_namespace)}"' + text[head_end:]
        else:
            text = text.replace(f"xmlns:{placeholder}=", "xmlns=", 1)
    ignorable = root.get(f"{{{_MC_NS}}}Ignorable")
    if ignorable:
        mapping = {prefix: uri for prefix, uri in declarations if prefix}
        head_end = text.index(">")
        if text[head_end - 1] == "/":
            head_end -= 1
        head = text[:head_end]
        missing = [
            f' xmlns:{prefix}="{escape(mapping[prefix])}"'
            for prefix in ignorable.split()
            if prefix in mapping and f"xmlns:{prefix}=" not in head
        ]
        text = head + "".join(missing) + text[head_end:]
    return (_XML_DECLARATION + text).encode("utf-8")


def _expand_shared_formulas(cells: dict[tuple[int, int], ET.Element]) -> None:
    masters: dict[str, tuple[int, int, str]] = {}
    dependents: list[tuple[int, int, ET.Element, str]] = []
    for (row, column), element in cells.items():
        formula = element.find(f"{{{_SS_NS}}}f")
        if formula is None or formula.get("t") != "shared":
            continue
        index = formula.get("si") or ""
        if formula.text:
            masters[index] = (row, column, formula.text)
        dependents.append((row, column, formula, index))
    for row, column, formula, index in dependents:
        master = masters.get(index)
        if master is None:
            raise ValueError("worksheet shared formula has no master cell")
        master_row, master_column, text = master
        formula.text = _shift_formula(text, row - master_row, column - master_column)
        for attribute in ("t", "si", "ref"):
            formula.attrib.pop(attribute, None)


_TOKEN = re.compile(
    r"""
    (?P<space>\s+)
    | (?P<string>"(?:[^"]|"")*")
    | (?P<error>\#(?:DIV/0!|N/A|NAME\?|NULL!|NUM!|REF!|VALUE!))
    | (?P<ref>
        (?P<sheet>(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)?
        (?P<first>\$?[A-Za-z]{1,3}\$?[0-9]+)
        (?::(?P<last>\$?[A-Za-z]{1,3}\$?[0-9]+))?
      )(?![A-Za-z0-9_(.])
    | (?P<number>(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)
    | (?P<function>[A-Za-z_][A-Za-z0-9_.]*)\s*\(
    | (?P<boolean>TRUE|FALSE)(?![A-Za-z0-9_(.])
    | (?P<operator><=|>=|<>|[-+*/^&=<>%(),])
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _tokens(formula: str) -> list[tuple[str, re.Match[str]]]:
    tokens: list[tuple[str, re.Match[str]]] = []
    position = 0
    while position < len(formula):
        match = _TOKEN.match(formula, position)
        if match is None:
            raise UnsupportedFormulaError(
                f"formula {formula!r} has unsupported syntax at {formula[position:]!r}"
            )
        kind = match.lastgroup or ""
        if kind in {"sheet", "first", "last"}:
            kind = "ref"
        if kind != "space":
            tokens.append((kind, match))
        position = match.end()
    return tokens


def _shift_formula(formula: str, row_offset: int, column_offset: int) -> str:
    pieces: list[str] = []
    position = 0
    for kind, match in _tokens(formula):
        if kind != "ref":
            continue
        pieces.append(formula[position : match.start()])
        shifted = [
            _shift_address(match[group], row_offset, column_offset)
            for group in ("first", "last")
            if match[group]
        ]
        pieces.append((match["sheet"] or "") + ":".join(shifted))
        position = match.end()
    pieces.append(formula[position:])
    return "".join(pieces)


def _shift_address(address: str, row_offset: int, column_offset: int) -> str:
    match = re.fullmatch(r"(\$?)([A-Za-z]{1,3})(\$?)([0-9]+)", address)
    assert match is not None
    column = _excel_column_index(match[2])
    row = int(match[4])
    if not match[1]:
        column += column_offset
    if not match[3]:
        row += row_offset
    if column < 1 or row < 1:
        raise ValueError("shared formula reference moves outside the worksheet")
    return f"{match[1]}{_excel_column_name(column)}{match[3]}{row}"


_UNSUPPORTED: Any = object()
_BINARY_PRECEDENCE = {
    "=": 1,
    "<>": 1,
    "<": 1,
    ">": 1,
    "<=": 1,
    ">=": 1,
    "&": 2,
    "+": 3,
    "-": 3,
    "*": 4,
    "/": 4,
    "^": 5,
}
_FUNCTIONS = frozenset(
    {
        "SUM",
        "AVERAGE",
        "MIN",
        "MAX",
        "COUNT",
        "COUNTA",
        "PRODUCT",
        "ABS",
        "ROUND",
        "IF",
        "AND",
        "OR",
        "NOT",
        "CONCATENATE",
    }
)


def _parse_formula(formula: str) -> tuple[Any, ...]:
    """Parse a formula into a small expression tree, rejecting unsupported syntax."""
    tokens = _tokens(formula)
    position = 0

    def peek() -> tuple[str, str] | None:
        if position >= len(tokens):
            return None
        kind, match = tokens[position]
        return kind, match.group(0)

    def take() -> tuple[str, re.Match[str]]:
        nonlocal position
        if position >= len(tokens):
            raise UnsupportedFormulaError(f"formula {formula!r} ends unexpectedly")
        token = tokens[position]
        position += 1
        return token

    def expect(text: str) -> None:
        kind, match = take()
        if kind != "operator" or match.group(0) != text:
            raise UnsupportedFormulaError(f"formula {formula!r} expected {text!r}")

    def expression(minimum: int) -> tuple[Any, ...]:
        left = unary()
        while True:
            token = peek()
            if token is None or token[0] != "operator":
                return left
            precedence = _BINARY_PRECEDENCE.get(token[1])
            if precedence is None or precedence < minimum:
                return left
            take()
            right = expression(precedence + (0 if token[1] == "^" else 1))
            left = ("binary", token[1], left, right)

    def unary() -> tuple[Any, ...]:
        token = peek()
        if token is not None and token[0] == "operator" and token[1] in "+-":
            take()
            return ("unary", token[1], unary())
        node = primary()
        while (token := peek()) is not None and token == ("operator", "%"):
            take()
            node = ("percent", node)
        return node

    def primary() -> tuple[Any, ...]:
        kind, match = take()
        text = match.group(0)
        if kind == "number":
            return ("value", float(text))
        if kind == "string":
            return ("value", text[1:-1].replace('""', '"'))
        if kind == "boolean":
            return ("value", text.upper() == "TRUE")
        if kind == "error":
            return ("value", CellError(text.upper()))
        if kind == "ref":
            sheet = _formula_sheet_name(match["sheet"])
            row1, column1 = parse_cell_address(match["first"])
            if match["last"]:
                row2, column2 = parse_cell_address(match["last"])
                return (
                    "range",
                    sheet,
                    min(row1, row2),
                    min(column1, column2),
                    max(row1, row2),
                    max(column1, column2),
                )
            return ("ref", sheet, row1, column1)
        if kind == "function":
            name = match["function"].upper()
            if name not in _FUNCTIONS:
                raise UnsupportedFormulaError(f"formula function {name} is unsupported")
            arguments: list[tuple[Any, ...]] = []
            if peek() != ("operator", ")"):
                arguments.append(expression(1))
                while peek() == ("operator", ","):
                    take()
                    arguments.append(expression(1))
            expect(")")
            return ("call", name, tuple(arguments))
        if kind == "operator" and text == "(":
            node = expression(1)
            expect(")")
            return node
        raise UnsupportedFormulaError(f"formula {formula!r} has unexpected {text!r}")

    tree = expression(1)
    if position != len(tokens):
        raise UnsupportedFormulaError(
            f"formula {formula!r} has trailing {tokens[position][1].group(0)!r}"
        )
    return tree


class _FormulaEvaluator:
    """Evaluate workbook formulas; results are memoized per calculation pass."""

    def __init__(self, workbook: ChartDataWorkbook, *, strict: bool) -> None:
        self._workbook = workbook
        self._strict = strict
        self._results: dict[tuple[int, int, int], Any] = {}
        self._active: set[tuple[int, int, int]] = set()
        self.unsupported: list[tuple[ChartDataWorksheet, int, int]] = []

    def cell_result(self, worksheet: ChartDataWorksheet, row: int, column: int) -> Any:
        key = (id(worksheet), row, column)
        if key in self._results:
            return self._results[key]
        element = worksheet._cell_element(row, column, create=False)
        formula = None if element is None else element.find(f"{{{_SS_NS}}}f")
        if element is None:
            return None
        if formula is None:
            return self._workbook._element_value(element)
        if key in self._active:
            raise UnsupportedFormulaError(
                f"circular reference at {worksheet.name}!{cell_address(row, column)}"
            )
        self._active.add(key)
        try:
            tree = _parse_formula(formula.text or "")
            result = self._scalar(self._evaluate(tree, worksheet))
        except UnsupportedFormulaError:
            if self._strict:
                raise
            self.unsupported.append((worksheet, row, column))
            result = _UNSUPPORTED
        finally:
            self._active.discard(key)
        self._results[key] = result
        return result

    def _cell_value(self, worksheet: ChartDataWorksheet, row: int, column: int) -> Any:
        result = self.cell_result(worksheet, row, column)
        if result is _UNSUPPORTED:
            raise UnsupportedFormulaError("formula depends on an unsupported formula")
        if isinstance(result, date):
            return _excel_date_number(result, date1904=self._workbook._date1904)
        return result

    def _sheet(self, name: str | None, current: ChartDataWorksheet) -> ChartDataWorksheet:
        if name is None:
            return current
        try:
            return self._workbook.worksheet(name)
        except KeyError as exc:
            raise UnsupportedFormulaError(f"formula sheet {name!r} is unavailable") from exc

    def _evaluate(self, node: tuple[Any, ...], sheet: ChartDataWorksheet) -> Any:
        kind = node[0]
        if kind == "value":
            return node[1]
        if kind == "ref":
            return self._cell_value(self._sheet(node[1], sheet), node[2], node[3])
        if kind == "range":
            target = self._sheet(node[1], sheet)
            return [
                self._cell_value(target, row, column)
                for row in range(node[2], node[4] + 1)
                for column in range(node[3], node[5] + 1)
            ]
        if kind == "unary":
            operand = _number(self._scalar(self._evaluate(node[2], sheet)))
            if isinstance(operand, CellError):
                return operand
            return -operand if node[1] == "-" else operand
        if kind == "percent":
            operand = _number(self._scalar(self._evaluate(node[1], sheet)))
            return operand if isinstance(operand, CellError) else operand / 100
        if kind == "binary":
            left = self._scalar(self._evaluate(node[2], sheet))
            right = self._scalar(self._evaluate(node[3], sheet))
            return _binary(node[1], left, right)
        if kind == "call":
            return self._call(node[1], node[2], sheet)
        raise UnsupportedFormulaError(f"formula node {kind!r} is unsupported")

    def _scalar(self, value: Any) -> Any:
        if isinstance(value, list):
            if len(value) != 1:
                return CellError("#VALUE!")
            return value[0]
        return value

    def _call(
        self,
        name: str,
        arguments: tuple[tuple[Any, ...], ...],
        sheet: ChartDataWorksheet,
    ) -> Any:
        if name == "IF":
            if not 1 < len(arguments) < 4:
                return CellError("#VALUE!")
            condition = _truth(self._scalar(self._evaluate(arguments[0], sheet)))
            if isinstance(condition, CellError):
                return condition
            if condition:
                return self._scalar(self._evaluate(arguments[1], sheet))
            if len(arguments) == 3:
                return self._scalar(self._evaluate(arguments[2], sheet))
            return False
        values = [self._evaluate(argument, sheet) for argument in arguments]
        if name in {"SUM", "AVERAGE", "MIN", "MAX", "COUNT", "PRODUCT"}:
            numbers: list[float] = []
            for value in values:
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, CellError) and name != "COUNT":
                            return item
                        if isinstance(item, float):
                            numbers.append(item)
                    continue
                number = _number(value)
                if isinstance(number, CellError):
                    if name == "COUNT":
                        continue
                    return number
                numbers.append(number)
            if name == "SUM":
                return math.fsum(numbers)
            if name == "COUNT":
                return float(len(numbers))
            if name == "PRODUCT":
                return math.prod(numbers) if numbers else 0.0
            if name == "AVERAGE":
                return math.fsum(numbers) / len(numbers) if numbers else CellError("#DIV/0!")
            if not numbers:
                return 0.0
            return min(numbers) if name == "MIN" else max(numbers)
        if name == "COUNTA":
            flat = [
                item for value in values for item in (value if isinstance(value, list) else [value])
            ]
            return float(sum(1 for item in flat if item is not None))
        scalars = [self._scalar(value) for value in values]
        if name == "ABS":
            if len(scalars) != 1:
                return CellError("#VALUE!")
            number = _number(scalars[0])
            return number if isinstance(number, CellError) else abs(number)
        if name == "ROUND":
            if len(scalars) != 2:
                return CellError("#VALUE!")
            number, digits = _number(scalars[0]), _number(scalars[1])
            for item in (number, digits):
                if isinstance(item, CellError):
                    return item
            factor = 10 ** int(digits)
            return math.copysign(math.floor(abs(number) * factor + 0.5) / factor, number)
        if name in {"AND", "OR"}:
            truths = []
            for value in values:
                for item in value if isinstance(value, list) else [value]:
                    if item is None or isinstance(item, str) and isinstance(value, list):
                        continue
                    truth = _truth(item)
                    if isinstance(truth, CellError):
                        return truth
                    truths.append(truth)
            if not truths:
                return CellError("#VALUE!")
            return all(truths) if name == "AND" else any(truths)
        if name == "NOT":
            if len(scalars) != 1:
                return CellError("#VALUE!")
            truth = _truth(scalars[0])
            return truth if isinstance(truth, CellError) else not truth
        if name == "CONCATENATE":
            texts = []
            for item in scalars:
                if isinstance(item, CellError):
                    return item
                texts.append(_text(item))
            return "".join(texts)
        raise UnsupportedFormulaError(f"formula function {name} is unsupported")


def _number(value: Any) -> float | CellError:
    if isinstance(value, CellError):
        return value
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, float | int):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return CellError("#VALUE!")


def _truth(value: Any) -> bool | CellError:
    if isinstance(value, CellError):
        return value
    if isinstance(value, str):
        if value.upper() in {"TRUE", "FALSE"}:
            return value.upper() == "TRUE"
        return CellError("#VALUE!")
    number = _number(value)
    return number if isinstance(number, CellError) else number != 0


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return _number_text(value)
    return str(value)


def _binary(operator: str, left: Any, right: Any) -> Any:
    for value in (left, right):
        if isinstance(value, CellError):
            return value
    if operator == "&":
        return _text(left) + _text(right)
    if operator in {"=", "<>", "<", ">", "<=", ">="}:
        return _compare(operator, left, right)
    first, second = _number(left), _number(right)
    for value in (first, second):
        if isinstance(value, CellError):
            return value
    if operator == "+":
        return first + second
    if operator == "-":
        return first - second
    if operator == "*":
        return first * second
    if operator == "/":
        return CellError("#DIV/0!") if second == 0 else first / second
    try:
        result = first**second
    except (OverflowError, ZeroDivisionError):
        return CellError("#NUM!")
    if isinstance(result, complex) or not math.isfinite(result):
        return CellError("#NUM!")
    return result


def _compare(operator: str, left: Any, right: Any) -> bool:
    def rank(value: Any) -> tuple[int, Any]:
        if value is None:
            return (0, 0.0)
        if isinstance(value, bool):
            return (2, value)
        if isinstance(value, str):
            return (1, value.casefold())
        return (0, float(value))

    if left is None and isinstance(right, str):
        left = ""
    if right is None and isinstance(left, str):
        right = ""
    first, second = rank(left), rank(right)
    return {
        "=": first == second,
        "<>": first != second,
        "<": first < second,
        ">": first > second,
        "<=": first <= second,
        ">=": first >= second,
    }[operator]
