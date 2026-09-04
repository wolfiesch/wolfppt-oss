"""Lightweight XLSX workbook generation for simple chart data."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_SS_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CORE_PROPS_REL_TYPE = (
    "http://schemas.openxmlformats.org/package/2006/relationships/"
    "metadata/core-properties"
)
_SHARED_STRINGS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml."
    "sharedStrings+xml"
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
            f'{_shared_string_cell(f"B{current_row}", intern(item["name"]))}'
            "</row>"
        )
        for offset, (x_value, y_value) in enumerate(
            zip(x_values, y_values, strict=True),
            start=1,
        ):
            row_index = current_row + offset
            rows.append(
                f'<row r="{row_index}">'
                f'{_number_cell(f"A{row_index}", x_value)}'
                f'{_number_cell(f"B{row_index}", y_value)}'
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
            f'{_shared_string_cell(f"B{current_row}", intern(item["name"]))}'
            "</row>"
        )
        for offset, (x_value, y_value, bubble_size) in enumerate(
            zip(x_values, y_values, bubble_sizes, strict=True),
            start=1,
        ):
            row_index = current_row + offset
            rows.append(
                f'<row r="{row_index}">'
                f'{_number_cell(f"A{row_index}", x_value)}'
                f'{_number_cell(f"B{row_index}", y_value)}'
                f'{_number_cell(f"C{row_index}", bubble_size)}'
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
        "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<sheetData>{"".join(rows)}</sheetData>'
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
        "<sheets><sheet name=\"Sheet1\" sheetId=\"1\" r:id=\"rId1\"/></sheets>"
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
        '<Properties '
        'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        'extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>WolfPPT</Application></Properties>"
    )


def _core_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties '
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
