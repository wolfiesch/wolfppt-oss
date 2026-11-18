"""Chart package-add helpers for presentation saves."""

from __future__ import annotations

import math
import posixpath
import re
import zipfile
from copy import deepcopy
from datetime import date, datetime
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .chart_axis_ids import (
    chart_axis_ids_as_openxml_int32 as _chart_axis_ids_as_openxml_int32,
)
from .chart_data import ChartDataWorkbook, ChartWorkbookLocale
from .chart_workbook import (
    bubble_chart_workbook_blob as _bubble_chart_workbook_blob,
)
from .chart_workbook import (
    category_chart_workbook_blob as _category_chart_workbook_blob,
)
from .chart_workbook import (
    xy_chart_workbook_blob as _xy_chart_workbook_blob,
)
from .chart_xml import (
    replace_chart_xml_data as _replace_chart_xml_data,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    natural_key as _natural_key,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .package_parts import (
    resolve_package_target as _resolve_package_target,
)
from .shape_xml import _next_relationship_id
from .xml_helpers import (
    content_types_xml as _content_types_xml,
)
from .xml_helpers import (
    xml_local_name as _xml_local_name,
)

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"

_CHART_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
_PACKAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package"
_CHART_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_XLSX_SHEET_PART = "xl/worksheets/sheet1.xml"
_XLSX_STYLES_PART = "xl/styles.xml"
#: SpreadsheetML reserves ids below 164 for built-in number formats.
_FIRST_CUSTOM_NUM_FMT_ID = 164
_GENERAL_NUMBER_FORMAT = "General"
_XLSX_CELL_XFS = re.compile(r'<cellXfs count="(?P<count>\d+)">(?P<body>.*?)</cellXfs>')
_XLSX_STYLE_SHEET_OPEN = re.compile(r"<styleSheet\b[^>]*>")
_XLSX_NUMBER_CELL = re.compile(r'<c r="(?P<ref>[A-Z]+[0-9]+)">')

CX_NS = "http://schemas.microsoft.com/office/drawing/2014/chartex"
_CHARTEX_REL_TYPE = "http://schemas.microsoft.com/office/2014/relationships/chartEx"
_CHARTEX_CONTENT_TYPE = "application/vnd.ms-office.chartex+xml"
_CHART_TEMPLATE_CACHE: dict[int, dict[str, Any]] = {}
_CHART_TEMPLATE_NAME_TO_ID = {
    "AREA": 1,
    "AREA_STACKED": 76,
    "AREA_STACKED_100": 77,
    "BAR_CLUSTERED": 57,
    "BAR_STACKED": 58,
    "BAR_STACKED_100": 59,
    "COLUMN_CLUSTERED": 51,
    "COLUMN_STACKED": 52,
    "COLUMN_STACKED_100": 53,
    "DOUGHNUT": -4120,
    "DOUGHNUT_EXPLODED": 80,
    "LINE": 4,
    "LINE_MARKERS": 65,
    "LINE_MARKERS_STACKED": 66,
    "LINE_MARKERS_STACKED_100": 67,
    "LINE_STACKED": 63,
    "LINE_STACKED_100": 64,
    "PIE": 5,
    "PIE_EXPLODED": 69,
    "RADAR": -4151,
    "RADAR_FILLED": 82,
    "RADAR_MARKERS": 81,
}
_STOCK_CHART_TEMPLATE_NAME_TO_ID = {
    "STOCK_HLC": 4,
    "STOCK_OHLC": 4,
}
_STOCK_CHART_NAMES_BY_ID = {
    88: "STOCK_HLC",
    89: "STOCK_OHLC",
}
_STOCK_SERIES_ROLES = {
    "STOCK_HLC": ("high", "low", "close"),
    "STOCK_OHLC": ("open", "high", "low", "close"),
}
#: Financial chart kinds authored by ``chart_financial`` reuse an existing
#: bar-chart template deck for the chart graphic frame and relationship shell
#: while supplying their own precomputed chart XML.  They are deliberately kept
#: out of ``_CHART_TEMPLATE_NAME_TO_ID`` so the python-pptx drop-in ``add_chart``
#: surface and its benchmark coverage stay exactly the python-pptx enum set.
_FINANCIAL_TEMPLATE_NAME_TO_ID = {
    "COMBO_COLUMN_LINE": 51,
    "COMBO_COLUMN_STACKED_LINE": 52,
    "COMBO_COLUMN_STACKED_100_LINE": 53,
    "WATERFALL": 52,
}
_XY_CHART_TEMPLATE_NAME_TO_ID = {
    "XY_SCATTER": -4169,
    "XY_SCATTER_LINES": 74,
    "XY_SCATTER_LINES_NO_MARKERS": 75,
    "XY_SCATTER_SMOOTH": 72,
    "XY_SCATTER_SMOOTH_NO_MARKERS": 73,
}
_BUBBLE_CHART_TEMPLATE_NAME_TO_ID = {
    "BUBBLE": 15,
    "BUBBLE_THREE_D_EFFECT": 87,
}

_THREE_D_CHART_SPECS = {
    "THREE_D_AREA": (1, "area3DChart"),
    "THREE_D_AREA_STACKED": (76, "area3DChart"),
    "THREE_D_AREA_STACKED_100": (77, "area3DChart"),
    "THREE_D_BAR_CLUSTERED": (57, "bar3DChart"),
    "THREE_D_BAR_STACKED": (58, "bar3DChart"),
    "THREE_D_BAR_STACKED_100": (59, "bar3DChart"),
    "THREE_D_COLUMN": (51, "bar3DChart"),
    "THREE_D_COLUMN_CLUSTERED": (51, "bar3DChart"),
    "THREE_D_COLUMN_STACKED": (52, "bar3DChart"),
    "THREE_D_COLUMN_STACKED_100": (53, "bar3DChart"),
    "THREE_D_LINE": (4, "line3DChart"),
    "THREE_D_PIE": (5, "pie3DChart"),
    "THREE_D_PIE_EXPLODED": (69, "pie3DChart"),
    "SURFACE": (1, "surface3DChart"),
    "SURFACE_WIREFRAME": (1, "surface3DChart"),
}
_THREE_D_NAMES_BY_ID = {
    -4102: "THREE_D_PIE",
    -4101: "THREE_D_LINE",
    -4100: "THREE_D_COLUMN",
    -4098: "THREE_D_AREA",
    54: "THREE_D_COLUMN_CLUSTERED",
    55: "THREE_D_COLUMN_STACKED",
    56: "THREE_D_COLUMN_STACKED_100",
    60: "THREE_D_BAR_CLUSTERED",
    61: "THREE_D_BAR_STACKED",
    62: "THREE_D_BAR_STACKED_100",
    70: "THREE_D_PIE_EXPLODED",
    78: "THREE_D_AREA_STACKED",
    79: "THREE_D_AREA_STACKED_100",
    83: "SURFACE",
    84: "SURFACE_WIREFRAME",
}
_CHART_TEMPLATE_IDS = frozenset(
    (
        *_CHART_TEMPLATE_NAME_TO_ID.values(),
        *_XY_CHART_TEMPLATE_NAME_TO_ID.values(),
        *_BUBBLE_CHART_TEMPLATE_NAME_TO_ID.values(),
    )
)
_ChartAdd = tuple[
    int,
    Any,
    Any,
    int,
    int,
    int,
    int,
    int | None,
    int | None,
    int | None,
    bool,
]


def _normalize_category_chart_data(
    chart_data: Any,
    series_items: list[Any] | None = None,
) -> dict[str, Any]:
    series_items = list(chart_data) if series_items is None else series_items
    category_hierarchy = _category_leaf_paths(chart_data.categories)
    raw_categories = [path[-1] for path in category_hierarchy]
    category_kind = "date" if _is_date_category_sequence(raw_categories) else "string"
    categories = [
        _excel_date_serial_text(category) if category_kind == "date" else str(category)
        for category in raw_categories
    ]
    has_hierarchy = any(len(path) > 1 for path in category_hierarchy)
    if series_items and not categories:
        raise ValueError("chart data contains no categories")
    series_payloads: list[dict[str, Any]] = []
    for series in series_items:
        values = [float(value) for value in series.values]
        series_payloads.append(
            {
                "name": str(series.name),
                "categories": categories,
                "values": values,
            }
        )
    xlsx_blob = _category_chart_workbook_blob(
        categories,
        series_payloads,
        category_hierarchy=category_hierarchy if has_hierarchy else None,
        category_kind=category_kind,
    )
    return {
        "data_kind": "category",
        "category_kind": category_kind,
        "categories": categories,
        "category_hierarchy": category_hierarchy if has_hierarchy else [],
        "series": series_payloads,
        "xlsx_blob": xlsx_blob,
    }


def _category_leaf_paths(categories: Any) -> list[list[Any]]:
    paths: list[list[Any]] = []

    def walk(category: Any, ancestors: list[Any]) -> None:
        label = getattr(category, "label", category)
        children = list(getattr(category, "sub_categories", []) or [])
        if not children:
            paths.append([*ancestors, label])
            return
        for child in children:
            walk(child, [*ancestors, label])

    for category in categories:
        walk(category, [])
    return paths


def _is_date_category_sequence(categories: list[Any]) -> bool:
    return bool(categories) and all(_is_date_category(category) for category in categories)


def _is_date_category(value: Any) -> bool:
    return isinstance(value, (date, datetime))


def _excel_date_serial_text(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise TypeError("date category must be a datetime.date or datetime.datetime")
    serial = float((value - date(1899, 12, 30)).days)
    return f"{serial:.1f}"


def _normalize_chart_add_data(chart_data: Any) -> dict[str, Any]:
    if isinstance(chart_data, dict) and "xlsx_blob" in chart_data:
        return chart_data
    # Validate before constructing any workbook or queuing a presentation edit.
    locale = ChartWorkbookLocale.validate(getattr(chart_data, "workbook_locale", None))
    series_items = list(chart_data)
    if hasattr(chart_data, "categories"):
        normalized = _normalize_category_chart_data(chart_data, series_items)
    elif _is_bubble_chart_data(chart_data, series_items):
        normalized = _normalize_bubble_chart_data(
            series_items, _chart_data_number_format(chart_data)
        )
    elif _is_xy_chart_data(chart_data, series_items):
        normalized = _normalize_xy_chart_data(series_items, _chart_data_number_format(chart_data))
    else:
        normalized = _normalize_category_chart_data(chart_data, series_items)
    if locale is not None:
        date_refs = (
            {f"A{row}" for row in range(2, len(normalized["categories"]) + 2)}
            if normalized.get("category_kind") == "date"
            else set()
        )
        normalized["xlsx_blob"] = _with_chart_workbook_locale(
            normalized["xlsx_blob"], locale, date_refs
        )
    return normalized


def _is_bubble_chart_data(chart_data: Any, series_items: list[Any]) -> bool:
    if hasattr(chart_data, "bubble_sizes_ref"):
        return True
    return bool(_looks_like_bubble_chart_data(series_items))


def _is_xy_chart_data(chart_data: Any, series_items: list[Any]) -> bool:
    if chart_data.__class__.__name__ == "XyChartData":
        return True
    return bool(_looks_like_xy_chart_data(series_items))


def _looks_like_bubble_chart_data(series_items: list[Any]) -> bool:
    if not series_items:
        return False
    first_series = series_items[0]
    if hasattr(first_series, "bubble_sizes"):
        return True
    try:
        points = list(first_series)
    except TypeError:
        return False
    return bool(points) and all(
        hasattr(point, "x") and hasattr(point, "y") and hasattr(point, "bubble_size")
        for point in points
    )


def _looks_like_xy_chart_data(series_items: list[Any]) -> bool:
    if not series_items:
        return False
    first_series = series_items[0]
    if hasattr(first_series, "x_values"):
        return True
    try:
        points = list(first_series)
    except TypeError:
        return False
    return bool(points) and all(hasattr(point, "x") and hasattr(point, "y") for point in points)


def _normalize_xy_chart_data(
    series_items: list[Any],
    chart_number_format: str = _GENERAL_NUMBER_FORMAT,
) -> dict[str, Any]:
    series_payloads: list[dict[str, Any]] = []
    for series in series_items:
        points = list(series)
        x_values = [float(point.x) for point in points]
        y_values = [float(point.y) for point in points]
        if len(x_values) != len(y_values):
            raise ValueError("XY chart x and y values must have the same length")
        series_payloads.append(
            {
                "name": str(series.name),
                "categories": [],
                "x_values": x_values,
                "values": y_values,
                "number_format": _series_number_format(series, chart_number_format),
            }
        )
    xlsx_blob = _with_xy_workbook_number_formats(
        _xy_chart_workbook_blob(series_payloads),
        series_payloads,
        chart_number_format,
        bubble=False,
    )
    return {
        "data_kind": "xy",
        "categories": [],
        "number_format": chart_number_format,
        "series": series_payloads,
        "xlsx_blob": xlsx_blob,
    }


def _normalize_bubble_chart_data(
    series_items: list[Any],
    chart_number_format: str = _GENERAL_NUMBER_FORMAT,
) -> dict[str, Any]:
    series_payloads: list[dict[str, Any]] = []
    for series in series_items:
        points = list(series)
        x_values = [float(point.x) for point in points]
        y_values = [float(point.y) for point in points]
        bubble_sizes = [float(point.bubble_size) for point in points]
        if len({len(x_values), len(y_values), len(bubble_sizes)}) != 1:
            raise ValueError("bubble chart x, y, and bubble-size values must have the same length")
        series_payloads.append(
            {
                "name": str(series.name),
                "categories": [],
                "x_values": x_values,
                "values": y_values,
                "bubble_sizes": bubble_sizes,
                "number_format": _series_number_format(series, chart_number_format),
            }
        )
    xlsx_blob = _with_xy_workbook_number_formats(
        _bubble_chart_workbook_blob(series_payloads),
        series_payloads,
        chart_number_format,
        bubble=True,
    )
    return {
        "data_kind": "bubble",
        "categories": [],
        "number_format": chart_number_format,
        "series": series_payloads,
        "xlsx_blob": xlsx_blob,
    }


def _chart_data_number_format(chart_data: Any) -> str:
    number_format = getattr(chart_data, "number_format", None)
    return _GENERAL_NUMBER_FORMAT if number_format is None else str(number_format)


def _series_number_format(series: Any, chart_number_format: str) -> str:
    """Series format as python-pptx resolves it: own format, else the chart's."""
    number_format = getattr(series, "number_format", None)
    return chart_number_format if number_format is None else str(number_format)


def _with_xy_workbook_number_formats(
    xlsx_blob: bytes,
    series_payloads: list[dict[str, Any]],
    chart_number_format: str,
    *,
    bubble: bool,
) -> bytes:
    """Style XY/bubble workbook cells the way python-pptx's workbook writers do.

    X values and bubble sizes carry the chart-level format; Y values carry the
    series format. Workbooks with only ``General`` cells are returned unchanged.
    """
    from xml.sax.saxutils import escape as _xml_escape

    cell_formats: dict[str, str] = {}
    for series in series_payloads:
        column_formats = [
            (series["x_formula"], chart_number_format),
            (series["y_formula"], series["number_format"]),
        ]
        if bubble:
            column_formats.append((series["bubble_size_formula"], chart_number_format))
        for formula, number_format in column_formats:
            if number_format == _GENERAL_NUMBER_FORMAT:
                continue
            for ref in _formula_cell_refs(formula):
                cell_formats[ref] = number_format
    if not cell_formats:
        return xlsx_blob

    with zipfile.ZipFile(BytesIO(xlsx_blob)) as workbook:
        infos = workbook.infolist()
        parts = {info.filename: workbook.read(info) for info in infos}
    # The generated workbook parts use a default SpreadsheetML namespace that
    # ElementTree cannot re-emit without a process-wide prefix registration,
    # so styles are spliced into the known generated markup instead.
    styles_xml = parts[_XLSX_STYLES_PART].decode("utf-8")
    cell_xfs = _XLSX_CELL_XFS.search(styles_xml)
    if cell_xfs is None or "<numFmts" in styles_xml:
        raise ValueError("chart workbook styles do not match the generated layout")
    first_style = int(cell_xfs.group("count"))
    style_index: dict[str, int] = {}
    for number_format in cell_formats.values():
        style_index.setdefault(number_format, first_style + len(style_index))
    num_fmts: list[str] = []
    xfs: list[str] = []
    for offset, number_format in enumerate(style_index):
        num_fmt_id = _FIRST_CUSTOM_NUM_FMT_ID + offset
        format_code = _xml_escape(number_format, {'"': "&quot;"})
        num_fmts.append(f'<numFmt numFmtId="{num_fmt_id}" formatCode="{format_code}"/>')
        xfs.append(
            f'<xf numFmtId="{num_fmt_id}" fontId="0" fillId="0" borderId="0" '
            'xfId="0" applyNumberFormat="1"/>'
        )
    styles_xml = (
        styles_xml[: cell_xfs.start()]
        + f'<cellXfs count="{first_style + len(xfs)}">'
        + cell_xfs.group("body")
        + "".join(xfs)
        + "</cellXfs>"
        + styles_xml[cell_xfs.end() :]
    )
    styles_xml, inserted = _XLSX_STYLE_SHEET_OPEN.subn(
        lambda match: (
            f'{match.group(0)}<numFmts count="{len(num_fmts)}">{"".join(num_fmts)}</numFmts>'
        ),
        styles_xml,
        count=1,
    )
    if inserted != 1:
        raise ValueError("chart workbook styles do not match the generated layout")
    parts[_XLSX_STYLES_PART] = styles_xml.encode("utf-8")

    styled_refs: set[str] = set()

    def style_cell(match: re.Match[str]) -> str:
        ref = match.group("ref")
        number_format = cell_formats.get(ref)
        if number_format is None:
            return match.group(0)
        styled_refs.add(ref)
        return f'<c r="{ref}" s="{style_index[number_format]}">'

    sheet_xml = _XLSX_NUMBER_CELL.sub(style_cell, parts[_XLSX_SHEET_PART].decode("utf-8"))
    if styled_refs != cell_formats.keys():
        raise ValueError("chart workbook cells do not match the series ranges")
    parts[_XLSX_SHEET_PART] = sheet_xml.encode("utf-8")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as workbook:
        for info in infos:
            workbook.writestr(info, parts[info.filename], compresslevel=1)
    return buffer.getvalue()


def _with_chart_workbook_locale(
    xlsx_blob: bytes, locale: ChartWorkbookLocale, date_refs: set[str]
) -> bytes:
    """Apply locale-specific formats to generated cells without changing values.

    SpreadsheetML numeric punctuation is invariant: swapping ``,`` and ``.``
    would change grouping/scaling semantics. Encode the selected locale with its
    language directive instead, and use explicit date order. Chart cache formats
    remain unchanged; this option affects only the embedded workbook.
    """
    from .chart_workbook import _SS_NS, serialize_xml_preserving_namespaces

    with zipfile.ZipFile(BytesIO(xlsx_blob)) as source:
        infos = source.infolist()
        parts = {info.filename: source.read(info) for info in infos}
    workbook = ChartDataWorkbook(xlsx_blob)
    sheet = ET.fromstring(parts[_XLSX_SHEET_PART])
    styles = ET.fromstring(parts[_XLSX_STYLES_PART])
    xfs = styles.find(f"{{{_SS_NS}}}cellXfs")
    assert xfs is not None
    num_fmts = styles.find(f"{{{_SS_NS}}}numFmts")
    if num_fmts is None:
        num_fmts = ET.Element(f"{{{_SS_NS}}}numFmts")
        styles.insert(0, num_fmts)
    next_id = (
        max([_FIRST_CUSTOM_NUM_FMT_ID - 1, *(int(item.get("numFmtId", "0")) for item in num_fmts)])
        + 1
    )
    format_ids: dict[str, int] = {}
    for item in num_fmts:
        code = _localized_workbook_format(item.get("formatCode", "General"), locale)
        item.set("formatCode", code)
        format_ids[code] = int(item.get("numFmtId", "0"))
    style_ids: dict[tuple[int, str], int] = {}
    for cell in sheet.iter(f"{{{_SS_NS}}}c"):
        if cell.get("t", "n") != "n":
            continue
        old_style = int(cell.get("s", "0"))
        code = workbook.get_cell(0, cell.get("r", "")).number_format
        if cell.get("r") in date_refs:
            code = locale.date_format
        elif code == _GENERAL_NUMBER_FORMAT:
            code = "#,##0.00"
        code = _localized_workbook_format(code, locale)
        if code not in format_ids:
            format_ids[code] = next_id
            next_id += 1
            ET.SubElement(
                num_fmts,
                f"{{{_SS_NS}}}numFmt",
                {"numFmtId": str(format_ids[code]), "formatCode": code},
            )
        key = (old_style, code)
        if key not in style_ids:
            style_ids[key] = len(xfs)
            xf = deepcopy(xfs[old_style])
            xf.set("numFmtId", str(format_ids[code]))
            xf.set("applyNumberFormat", "1")
            xfs.append(xf)
        cell.set("s", str(style_ids[key]))
    if not format_ids:
        # Empty generated series still retain the selected locale on reopen.
        ET.SubElement(
            num_fmts,
            f"{{{_SS_NS}}}numFmt",
            {"numFmtId": str(next_id), "formatCode": locale.format_prefix + "#,##0.00"},
        )
    num_fmts.set("count", str(len(num_fmts)))
    xfs.set("count", str(len(xfs)))
    for part, root in ((_XLSX_SHEET_PART, sheet), (_XLSX_STYLES_PART, styles)):
        parts[part] = serialize_xml_preserving_namespaces(root, parts[part])
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        for info in infos:
            output.writestr(info, parts[info.filename], compresslevel=1)
    return buffer.getvalue()


def _localized_workbook_format(code: str, locale: ChartWorkbookLocale) -> str:
    """Retain quoted/escaped separators and apply one directive per section."""
    sections = [""]
    has_directive = [False]
    directive = re.compile(r"\[\$([^\]]*?)-[0-9a-fA-F]+\]")
    for token in re.findall(r'"[^"]*"|\\.|[^;\\"]+|;', code):
        if token == ";":
            sections.append("")
            has_directive.append(False)
            continue
        if not token.startswith(('"', "\\")) and directive.search(token):
            # Retain currency text while updating its language, rather than
            # adding a second locale directive to the same section.
            token = directive.sub(
                lambda match: locale.format_prefix.replace("$-", f"${match[1]}-"), token
            )
            has_directive[-1] = True
        sections[-1] += token
    return ";".join(
        section if present or not section else locale.format_prefix + section
        for section, present in zip(sections, has_directive, strict=True)
    )


def _formula_cell_refs(formula: str) -> list[str]:
    """Cell refs of a single-column range such as ``Sheet1!$A$2:$A$4``."""
    start, _, end = formula.rpartition("!")[2].replace("$", "").partition(":")
    column = start.rstrip("0123456789")
    first_row = int(start[len(column) :])
    last_row = int((end or start)[len(column) :])
    return [f"{column}{row}" for row in range(first_row, last_row + 1)]


def _with_xy_cache_number_formats(
    chart_xml: bytes,
    series_payloads: list[dict[str, Any]],
) -> bytes:
    """Write each series format into its xVal/yVal/bubbleSize cache formatCode.

    python-pptx emits the resolved series format for every XY and bubble value
    cache; the generated templates already carry ``General`` there.
    """
    number_formats = [
        str(series.get("number_format", _GENERAL_NUMBER_FORMAT)) for series in series_payloads
    ]
    if all(fmt == _GENERAL_NUMBER_FORMAT for fmt in number_formats):
        return chart_xml
    root = ET.fromstring(chart_xml)
    series_elements = list(root.iter(f"{{{C_NS}}}ser"))
    for series_element, number_format in zip(series_elements, number_formats, strict=True):
        for tag in ("xVal", "yVal", "bubbleSize"):
            cache = series_element.find(f"{{{C_NS}}}{tag}/{{{C_NS}}}numRef/{{{C_NS}}}numCache")
            if cache is None:
                continue
            format_code = cache.find(f"{{{C_NS}}}formatCode")
            if format_code is None:
                format_code = ET.Element(f"{{{C_NS}}}formatCode")
                cache.insert(0, format_code)
            format_code.text = number_format
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _apply_chart_add(
    input_path: Path,
    output_path: Path,
    slide_index: int,
    chart_type: Any,
    chart_data: Any,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
    *,
    group_index: int | None = None,
    nested_group_child_index: int | None = None,
    deeper_group_child_index: int | None = None,
) -> None:
    _apply_chart_adds(
        input_path,
        output_path,
        [
            (
                slide_index,
                chart_type,
                chart_data,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                False,
            )
        ],
    )


def _apply_chart_adds(
    input_path: Path,
    output_path: Path,
    chart_adds: list[_ChartAdd],
) -> None:
    if not chart_adds:
        _copy_package_with_replacements(input_path, output_path, {})
        return

    with zipfile.ZipFile(input_path) as package:
        names = set(package.namelist())
        slide_parts = _presentation_slide_parts(package)
        content_types_root = ET.fromstring(package.read("[Content_Types].xml"))
        _ensure_content_type_default(content_types_root, "xlsx", _XLSX_CONTENT_TYPE)
        slide_states: dict[int, tuple[str, ET.Element, str, ET.Element]] = {}
        replacements: dict[str, bytes] = {}

        for add in chart_adds:
            (
                slide_index,
                chart_type,
                chart_data,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                create_nested_group,
            ) = add
            if slide_index not in slide_states:
                try:
                    slide_part = slide_parts[slide_index]
                except IndexError as exc:
                    raise IndexError("slide index out of range") from exc
                slide_rels_part = _rels_part_for_package_part(slide_part)
                slide_states[slide_index] = (
                    slide_part,
                    ET.fromstring(package.read(slide_part)),
                    slide_rels_part,
                    _relationships_root(package, slide_rels_part),
                )
            slide_part, slide_root, slide_rels_part, slide_rels_root = slide_states[slide_index]
            generated = _generated_chart_package_parts(
                chart_type,
                chart_data,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
            chart_part = _next_numbered_part(
                names,
                "ppt/charts/chartEx" if generated["is_chartex"] else "ppt/charts/chart",
                ".xml",
            )
            names.add(chart_part)
            chart_rels_part = _rels_part_for_package_part(chart_part)
            names.add(chart_rels_part)
            workbook_part = _next_numbered_part(
                names,
                "ppt/embeddings/Microsoft_Excel_Sheet",
                ".xlsx",
            )
            names.add(workbook_part)

            relationship_id = _next_relationship_id(slide_rels_root)
            shape_tree = _slide_shape_tree(slide_root)
            if group_index is None:
                target_tree = shape_tree
            else:
                target_tree = _slide_group_shape(shape_tree, group_index)
                if create_nested_group:
                    nested_shape_id = _next_shape_tree_id(shape_tree)
                    nested_group = _empty_group_shape(nested_shape_id)
                    _insert_shape_tree_child(target_tree, nested_group)
                    target_tree = nested_group
                elif nested_group_child_index is not None:
                    target_tree = _direct_group_child_group(
                        target_tree,
                        nested_group_child_index,
                    )
                    if deeper_group_child_index is not None:
                        target_tree = _direct_group_child_group(
                            target_tree,
                            deeper_group_child_index,
                        )
            shape_id = _next_shape_tree_id(shape_tree)
            chart_frame = generated["graphic_frame"]
            _set_chart_frame_identity(
                chart_frame,
                shape_id,
                _next_shape_tree_name(target_tree, "Chart")
                if group_index is None
                else f"Chart {shape_id - 1}",
                relationship_id,
            )
            if group_index is None:
                _insert_shape_tree_child(target_tree, chart_frame)
            else:
                _append_group_shape_child(target_tree, chart_frame)
            slide_rels_root.append(
                ET.Element(
                    f"{{{PKG_REL_NS}}}Relationship",
                    {
                        "Id": relationship_id,
                        "Type": (_CHARTEX_REL_TYPE if generated["is_chartex"] else _CHART_REL_TYPE),
                        "Target": _relative_package_target(slide_part, chart_part),
                    },
                )
            )

            chart_rels_root = generated["chart_rels"]
            _retarget_chart_relationships(chart_rels_root, chart_part, workbook_part)
            _ensure_content_type_override(
                content_types_root,
                chart_part,
                _CHARTEX_CONTENT_TYPE if generated["is_chartex"] else _CHART_CONTENT_TYPE,
            )
            replacements[chart_part] = generated["chart_xml"]
            replacements[chart_rels_part] = ET.tostring(
                chart_rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[workbook_part] = generated["workbook_blob"]

        for (
            slide_part,
            slide_root,
            slide_rels_part,
            slide_rels_root,
        ) in slide_states.values():
            replacements[slide_part] = ET.tostring(
                slide_root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[slide_rels_part] = ET.tostring(
                slide_rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
        replacements["[Content_Types].xml"] = _content_types_xml(content_types_root)

    _copy_package_with_replacements(input_path, output_path, replacements)


def _generated_chart_package_parts(
    chart_type: Any,
    chart_data: Any,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> dict[str, Any]:
    stock_name = _stock_chart_name(chart_type)
    normalized = (
        _normalize_stock_chart_add_data(chart_data, stock_name)
        if stock_name is not None
        else (
            chart_data
            if isinstance(chart_data, dict) and "xlsx_blob" in chart_data
            else _normalize_chart_add_data(chart_data)
        )
    )
    is_chartex = isinstance(normalized.get("_chartex_chart_xml"), bytes)
    template = _generated_chart_template(51 if is_chartex else chart_type)
    graphic_frame = deepcopy(template["graphic_frame"])
    _set_chart_frame_geometry(graphic_frame, x_emu, y_emu, cx_emu, cy_emu)
    if is_chartex:
        chart_xml = normalized["_chartex_chart_xml"]
        _as_chartex_graphic_frame(graphic_frame)
    else:
        precomputed = normalized.get("_precomputed_chart_xml")
        if isinstance(precomputed, bytes):
            chart_xml = precomputed
        else:
            chart_xml_data = dict(normalized)
            if (
                normalized.get("data_kind") in {"bubble", "category", "xy"}
                and not normalized["series"]
            ):
                chart_xml_data["_preserve_empty_chart_type"] = True
            chart_xml = _replace_chart_xml_data(template["chart_xml"], chart_xml_data)
            if normalized.get("data_kind") in {"bubble", "xy"}:
                chart_xml = _with_xy_cache_number_formats(chart_xml, normalized["series"])
        if stock_name is not None:
            chart_xml = _author_stock_chart_xml(chart_xml, stock_name)
        else:
            three_d_name = _three_d_chart_name(chart_type)
            if three_d_name is not None:
                chart_xml = _author_three_d_chart_xml(
                    chart_xml, _THREE_D_CHART_SPECS[three_d_name][1], three_d_name
                )
    return {
        "graphic_frame": graphic_frame,
        "chart_xml": chart_xml,
        "chart_rels": deepcopy(template["chart_rels"]),
        "workbook_blob": normalized["xlsx_blob"],
        "is_chartex": is_chartex,
    }


def _normalize_stock_chart_add_data(chart_data: Any, stock_name: str) -> dict[str, Any]:
    normalized = (
        dict(chart_data)
        if isinstance(chart_data, dict) and "xlsx_blob" in chart_data
        else _normalize_chart_add_data(chart_data)
    )
    _validate_stock_chart_data(normalized, stock_name)
    return normalized


def _validate_stock_chart_data(chart_data: dict[str, Any], stock_name: str) -> None:
    roles = _STOCK_SERIES_ROLES[stock_name]
    categories = list(chart_data.get("categories") or [])
    series = list(chart_data.get("series") or [])
    if not categories:
        raise ValueError(f"{stock_name} chart data contains no categories")
    if len(series) != len(roles):
        raise ValueError(
            f"{stock_name} requires exactly {len(roles)} series ordered " + ", ".join(roles)
        )
    values_by_role: dict[str, list[float]] = {}
    for role, series_data in zip(roles, series, strict=True):
        values = list(series_data.get("values") or [])
        if len(values) != len(categories):
            raise ValueError(f"{stock_name} {role} series value count must match categories")
        converted: list[float] = []
        for point_index, value in enumerate(values, start=1):
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{stock_name} {role} series point {point_index} is not numeric"
                ) from exc
            if not math.isfinite(number):
                raise ValueError(f"{stock_name} {role} series point {point_index} is not finite")
            converted.append(number)
        values_by_role[role] = converted
    for point_index in range(len(categories)):
        high = values_by_role["high"][point_index]
        low = values_by_role["low"][point_index]
        if high < low:
            raise ValueError(f"{stock_name} category {point_index + 1} high value is below low")
        for role in ("open", "close"):
            if role not in values_by_role:
                continue
            value = values_by_role[role][point_index]
            if value < low or value > high:
                raise ValueError(
                    f"{stock_name} category {point_index + 1} {role} value is outside "
                    "the high-low range"
                )


def _stock_chart_name(chart_type: Any) -> str | None:
    chart_name = getattr(chart_type, "name", None)
    if chart_name in _STOCK_CHART_TEMPLATE_NAME_TO_ID:
        return chart_name
    try:
        chart_id = int(chart_type)
    except (TypeError, ValueError):
        chart_id = None
    if chart_id in _STOCK_CHART_NAMES_BY_ID:
        return _STOCK_CHART_NAMES_BY_ID[chart_id]
    chart_text = str(chart_type).split(" ", 1)[0]
    return chart_text if chart_text in _STOCK_CHART_TEMPLATE_NAME_TO_ID else None


def _author_stock_chart_xml(chart_xml: bytes, stock_name: str) -> bytes:
    root = ET.fromstring(chart_xml)
    chart = root.find(f"{{{C_NS}}}chart")
    plot_area = None if chart is None else chart.find(f"{{{C_NS}}}plotArea")
    if plot_area is None:
        raise AttributeError("chart template has no plot area")
    plot = plot_area.find(f"{{{C_NS}}}lineChart")
    if plot is None:
        raise AttributeError("chart template has no line chart")
    expected_series = len(_STOCK_SERIES_ROLES[stock_name])
    series = plot.findall(f"{{{C_NS}}}ser")
    if len(series) != expected_series:
        raise ValueError(
            f"{stock_name} template data must contain exactly {expected_series} series"
        )
    plot.tag = f"{{{C_NS}}}stockChart"
    axis_ids = [child for child in list(plot) if _xml_local_name(child.tag) == "axId"]
    data_labels = [child for child in list(plot) if _xml_local_name(child.tag) == "dLbls"]
    for child in list(plot):
        plot.remove(child)
    for series_element in series:
        _set_stock_series_line_hidden(series_element)
        plot.append(series_element)
    for data_labels_element in data_labels:
        plot.append(data_labels_element)
    plot.append(_stock_hi_low_lines())
    if stock_name == "STOCK_OHLC":
        plot.append(_stock_up_down_bars())
    for axis_id in axis_ids:
        plot.append(axis_id)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _set_stock_series_line_hidden(series_element: ET.Element) -> None:
    sp_pr = series_element.find(f"{{{C_NS}}}spPr")
    if sp_pr is not None:
        series_element.remove(sp_pr)
    sp_pr = ET.Element(f"{{{C_NS}}}spPr")
    line = ET.SubElement(sp_pr, f"{{{A_NS}}}ln")
    ET.SubElement(line, f"{{{A_NS}}}noFill")
    insert_at = 0
    for child in list(series_element):
        if _xml_local_name(child.tag) in {"idx", "order", "tx"}:
            insert_at += 1
            continue
        break
    series_element.insert(insert_at, sp_pr)
    for child in list(series_element):
        if _xml_local_name(child.tag) in {"marker", "smooth"}:
            series_element.remove(child)


def _stock_hi_low_lines() -> ET.Element:
    lines = ET.Element(f"{{{C_NS}}}hiLowLines")
    lines.append(_stock_format_properties("808080"))
    return lines


def _stock_up_down_bars() -> ET.Element:
    bars = ET.Element(f"{{{C_NS}}}upDownBars")
    ET.SubElement(bars, f"{{{C_NS}}}gapWidth", {"val": "150"})
    up_bars = ET.SubElement(bars, f"{{{C_NS}}}upBars")
    up_bars.append(_stock_format_properties("2E7D32"))
    down_bars = ET.SubElement(bars, f"{{{C_NS}}}downBars")
    down_bars.append(_stock_format_properties("C62828"))
    return bars


def _stock_format_properties(color: str) -> ET.Element:
    sp_pr = ET.Element(f"{{{C_NS}}}spPr")
    solid_fill = ET.SubElement(sp_pr, f"{{{A_NS}}}solidFill")
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": color})
    line = ET.SubElement(sp_pr, f"{{{A_NS}}}ln", {"w": "12700"})
    line_fill = ET.SubElement(line, f"{{{A_NS}}}solidFill")
    ET.SubElement(line_fill, f"{{{A_NS}}}srgbClr", {"val": color})
    return sp_pr


def _three_d_chart_name(chart_type: Any) -> str | None:
    chart_name = getattr(chart_type, "name", None)
    if chart_name in _THREE_D_CHART_SPECS:
        return chart_name
    try:
        chart_id = int(chart_type)
    except (TypeError, ValueError):
        chart_id = None
    if chart_id in _THREE_D_NAMES_BY_ID:
        return _THREE_D_NAMES_BY_ID[chart_id]
    chart_text = str(chart_type).split(" ", 1)[0]
    return chart_text if chart_text in _THREE_D_CHART_SPECS else None


def _author_three_d_chart_xml(chart_xml: bytes, plot_tag: str, chart_name: str) -> bytes:
    """Turn a compatible category-chart template into a standard 3-D chart."""
    root = ET.fromstring(chart_xml)
    chart = root.find(f"{{{C_NS}}}chart")
    plot_area = None if chart is None else chart.find(f"{{{C_NS}}}plotArea")
    if chart is None or plot_area is None:
        raise ValueError("generated chart template has no plot area")
    source_plot = next(
        (
            child
            for child in plot_area
            if _xml_local_name(child.tag) in {"areaChart", "barChart", "lineChart", "pieChart"}
        ),
        None,
    )
    if source_plot is None:
        raise ValueError("generated chart template has no convertible plot")
    source_plot.tag = f"{{{C_NS}}}{plot_tag}"
    view = chart.find(f"{{{C_NS}}}view3D")
    if view is None:
        view = ET.Element(f"{{{C_NS}}}view3D")
        chart.insert(list(chart).index(plot_area), view)
    for child in list(view):
        view.remove(child)
    for local_name, value in (
        ("rotX", "20"),
        ("rotY", "30"),
        ("rAngAx", "0"),
        ("perspective", "30"),
    ):
        ET.SubElement(view, f"{{{C_NS}}}{local_name}", {"val": value})
    forbidden_plot_children = {
        # The source bar chart's overlap and serLines have no 3-D equivalents.
        "bar3DChart": {"overlap", "serLines"},
        # c:marker here belongs to c:lineChart itself. Markers nested in c:ser
        # remain valid c:LineChartSeries content in c:line3DChart.
        "line3DChart": {"hiLowLines", "upDownBars", "marker", "smooth"},
        # c:firstSliceAng is not admitted by c:pie3DChart.
        "pie3DChart": {"firstSliceAng"},
    }
    for child in list(source_plot):
        if _xml_local_name(child.tag) in forbidden_plot_children.get(plot_tag, ()):
            source_plot.remove(child)
    if (
        plot_tag in {"bar3DChart", "line3DChart", "area3DChart"}
        and source_plot.find(f"{{{C_NS}}}gapDepth") is None
    ):
        first_axis = next(
            (
                index
                for index, child in enumerate(list(source_plot))
                if _xml_local_name(child.tag) == "axId"
            ),
            len(source_plot),
        )
        source_plot.insert(first_axis, ET.Element(f"{{{C_NS}}}gapDepth", {"val": "100"}))
    if plot_tag == "bar3DChart" and source_plot.find(f"{{{C_NS}}}shape") is None:
        first_axis = next(
            (
                index
                for index, child in enumerate(list(source_plot))
                if _xml_local_name(child.tag) == "axId"
            ),
            len(source_plot),
        )
        source_plot.insert(first_axis, ET.Element(f"{{{C_NS}}}shape", {"val": "box"}))
    if plot_tag == "surface3DChart":
        for child in list(source_plot):
            if _xml_local_name(child.tag) in {
                "grouping",
                "varyColors",
                "dLbls",
                "dropLines",
                "gapDepth",
            }:
                source_plot.remove(child)
        source_plot.insert(
            0,
            ET.Element(
                f"{{{C_NS}}}wireframe",
                {"val": "1" if chart_name.endswith("WIREFRAME") else "0"},
            ),
        )
    if plot_tag in {"area3DChart", "bar3DChart", "line3DChart", "surface3DChart"}:
        _ensure_three_d_series_axis(plot_area, source_plot)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _ensure_three_d_series_axis(plot_area: ET.Element, plot: ET.Element) -> None:
    if any(_xml_local_name(axis.tag) == "serAx" for axis in plot_area):
        return
    category_axis = next(
        (axis for axis in plot_area if _xml_local_name(axis.tag) in {"catAx", "dateAx"}),
        None,
    )
    if category_axis is None:
        raise ValueError("3-D chart template has no category axis")
    category_id = category_axis.find(f"{{{C_NS}}}axId")
    if category_id is None or category_id.get("val") is None:
        raise ValueError("3-D chart category axis has no identifier")
    existing_ids = [
        int(axis_id.get("val", "0"))
        for axis_id in plot_area.findall(f".//{{{C_NS}}}axId")
        if axis_id.get("val", "").lstrip("-").isdigit()
    ]
    series_id = str(max(existing_ids, default=0) + 1)
    ET.SubElement(plot, f"{{{C_NS}}}axId", {"val": series_id})
    axis = ET.Element(f"{{{C_NS}}}serAx")
    ET.SubElement(axis, f"{{{C_NS}}}axId", {"val": series_id})
    scaling = ET.SubElement(axis, f"{{{C_NS}}}scaling")
    ET.SubElement(scaling, f"{{{C_NS}}}orientation", {"val": "minMax"})
    ET.SubElement(axis, f"{{{C_NS}}}delete", {"val": "0"})
    ET.SubElement(axis, f"{{{C_NS}}}axPos", {"val": "b"})
    ET.SubElement(axis, f"{{{C_NS}}}tickLblPos", {"val": "none"})
    ET.SubElement(axis, f"{{{C_NS}}}crossAx", {"val": category_id.get("val", "")})
    ET.SubElement(axis, f"{{{C_NS}}}crosses", {"val": "autoZero"})
    plot_area.append(axis)


def _generated_chart_template(chart_type: Any) -> dict[str, Any]:
    template_id = _chart_template_id(chart_type)
    if template_id not in _CHART_TEMPLATE_CACHE:
        _CHART_TEMPLATE_CACHE[template_id] = _build_chart_template(template_id)
    return _CHART_TEMPLATE_CACHE[template_id]


def _chart_template_id(chart_type: Any) -> int:
    stock_name = _stock_chart_name(chart_type)
    if stock_name is not None:
        return _STOCK_CHART_TEMPLATE_NAME_TO_ID[stock_name]
    three_d_name = _three_d_chart_name(chart_type)
    if three_d_name is not None:
        return _THREE_D_CHART_SPECS[three_d_name][0]
    chart_name = getattr(chart_type, "name", None)
    if chart_name in _CHART_TEMPLATE_NAME_TO_ID:
        return _CHART_TEMPLATE_NAME_TO_ID[chart_name]
    if chart_name in _XY_CHART_TEMPLATE_NAME_TO_ID:
        return _XY_CHART_TEMPLATE_NAME_TO_ID[chart_name]
    if chart_name in _BUBBLE_CHART_TEMPLATE_NAME_TO_ID:
        return _BUBBLE_CHART_TEMPLATE_NAME_TO_ID[chart_name]
    if chart_name in _FINANCIAL_TEMPLATE_NAME_TO_ID:
        return _FINANCIAL_TEMPLATE_NAME_TO_ID[chart_name]
    try:
        chart_id = int(chart_type)
    except (TypeError, ValueError):
        chart_id = None
    if chart_id in _CHART_TEMPLATE_IDS:
        return int(chart_id)
    chart_text = str(chart_type)
    chart_text_name = chart_text.split(" ", 1)[0]
    if chart_text_name in _CHART_TEMPLATE_NAME_TO_ID:
        return _CHART_TEMPLATE_NAME_TO_ID[chart_text_name]
    if chart_text_name in _XY_CHART_TEMPLATE_NAME_TO_ID:
        return _XY_CHART_TEMPLATE_NAME_TO_ID[chart_text_name]
    if chart_text_name in _BUBBLE_CHART_TEMPLATE_NAME_TO_ID:
        return _BUBBLE_CHART_TEMPLATE_NAME_TO_ID[chart_text_name]
    if chart_text_name in _FINANCIAL_TEMPLATE_NAME_TO_ID:
        return _FINANCIAL_TEMPLATE_NAME_TO_ID[chart_text_name]
    try:
        chart_id = int(chart_text)
    except ValueError:
        chart_id = None
    if chart_id in _CHART_TEMPLATE_IDS:
        return int(chart_id)
    supported = ", ".join(
        sorted(
            (
                *_CHART_TEMPLATE_NAME_TO_ID,
                *_XY_CHART_TEMPLATE_NAME_TO_ID,
                *_BUBBLE_CHART_TEMPLATE_NAME_TO_ID,
            )
        )
    )
    raise NotImplementedError(
        f"native add_chart template is unavailable for {chart_type!r}; "
        f"supported chart types: {supported}"
    )


def _build_chart_template(template_id: int) -> dict[str, Any]:
    template_name = f"chart_type_{template_id}.pptx"
    template_blob = files("wolfppt.templates.charts").joinpath(template_name).read_bytes()

    with zipfile.ZipFile(BytesIO(template_blob)) as package:
        slide_root = ET.fromstring(package.read("ppt/slides/slide1.xml"))
        graphic_frame = _first_chart_graphic_frame(slide_root)
        chart_xml = _sanitize_generated_chart_template_xml(
            _chart_axis_ids_as_openxml_int32(package.read("ppt/charts/chart1.xml"))
        )
        chart_rels = ET.fromstring(package.read("ppt/charts/_rels/chart1.xml.rels"))
    return {
        "graphic_frame": graphic_frame,
        "chart_xml": chart_xml,
        "chart_rels": chart_rels,
    }


def _sanitize_generated_chart_template_xml(chart_xml: bytes) -> bytes:
    root = ET.fromstring(chart_xml)
    _replace_alternate_content_with_fallback(root)
    _remove_radar_series_smooth_elements(root)
    _remove_smooth_scatter_template_smooth_elements(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _replace_alternate_content_with_fallback(root: ET.Element) -> None:
    for parent in root.iter():
        children = list(parent)
        for index, child in enumerate(children):
            if child.tag != f"{{{MC_NS}}}AlternateContent":
                continue
            fallback = child.find(f"{{{MC_NS}}}Fallback")
            if fallback is None:
                continue
            replacement = list(fallback)
            parent.remove(child)
            for offset, fallback_child in enumerate(replacement):
                parent.insert(index + offset, deepcopy(fallback_child))


def _remove_radar_series_smooth_elements(root: ET.Element) -> None:
    for radar_chart in root.findall(f".//{{{C_NS}}}radarChart"):
        for series in radar_chart.findall(f"{{{C_NS}}}ser"):
            for smooth in list(series.findall(f"{{{C_NS}}}smooth")):
                series.remove(smooth)


def _remove_smooth_scatter_template_smooth_elements(root: ET.Element) -> None:
    for scatter_chart in root.findall(f".//{{{C_NS}}}scatterChart"):
        style_el = scatter_chart.find(f"{{{C_NS}}}scatterStyle")
        if style_el is not None and style_el.attrib.get("val") in (
            "smooth",
            "smoothMarker",
        ):
            for smooth in list(scatter_chart.findall(f"{{{C_NS}}}smooth")):
                scatter_chart.remove(smooth)
            for series in scatter_chart.findall(f"{{{C_NS}}}ser"):
                for smooth in list(series.findall(f"{{{C_NS}}}smooth")):
                    series.remove(smooth)


def _set_chart_frame_geometry(
    chart_frame: ET.Element,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> None:
    transform = chart_frame.find(f"{{{P_NS}}}xfrm")
    if transform is None:
        raise AttributeError("chart frame transform is unavailable")
    offset = transform.find(f"{{{A_NS}}}off")
    extent = transform.find(f"{{{A_NS}}}ext")
    if offset is None or extent is None:
        raise AttributeError("chart frame transform bounds are unavailable")
    offset.set("x", str(x_emu))
    offset.set("y", str(y_emu))
    extent.set("cx", str(cx_emu))
    extent.set("cy", str(cy_emu))


def _first_chart_graphic_frame(root: ET.Element) -> ET.Element:
    for frame in root.findall(f".//{{{P_NS}}}graphicFrame"):
        if frame.find(f".//{{{C_NS}}}chart") is not None:
            return frame
    raise AttributeError("generated chart frame is unavailable")


def _presentation_slide_parts(package: zipfile.ZipFile) -> list[str]:
    presentation_part = _presentation_part(package)
    try:
        root = ET.fromstring(package.read(presentation_part))
    except (KeyError, ET.ParseError):
        return _fallback_slide_parts(package)
    relationships = _relationships_by_id(
        _relationships_root(package, _rels_part_for_package_part(presentation_part))
    )
    ordered: list[str] = []
    for slide_id in root.findall(f".//{{{P_NS}}}sldId"):
        relationship_id = slide_id.attrib.get(f"{{{R_NS}}}id")
        relationship = relationships.get(relationship_id or "")
        if relationship is None or not relationship.attrib.get("Type", "").endswith("/slide"):
            continue
        ordered.append(
            _resolve_package_target(
                presentation_part,
                relationship.attrib.get("Target", ""),
            )
        )
    return ordered or _fallback_slide_parts(package)


def _presentation_part(package: zipfile.ZipFile) -> str:
    try:
        root = ET.fromstring(package.read("_rels/.rels"))
    except (KeyError, ET.ParseError):
        return "ppt/presentation.xml"
    for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if relationship.attrib.get("Type", "").endswith("/officeDocument"):
            return _resolve_package_target("", relationship.attrib.get("Target", ""))
    return "ppt/presentation.xml"


def _relationships_by_id(root: ET.Element) -> dict[str, ET.Element]:
    return {
        relationship.attrib["Id"]: relationship
        for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship")
        if relationship.attrib.get("Id")
    }


def _fallback_slide_parts(package: zipfile.ZipFile) -> list[str]:
    return sorted(
        [
            name
            for name in package.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ],
        key=_natural_key,
    )


def _relationships_root(package: zipfile.ZipFile, rels_part: str) -> ET.Element:
    try:
        return ET.fromstring(package.read(rels_part))
    except KeyError:
        return ET.Element(f"{{{PKG_REL_NS}}}Relationships")


def _slide_shape_tree(slide_root: ET.Element) -> ET.Element:
    shape_tree = slide_root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
    if shape_tree is None:
        raise AttributeError("slide shape tree is unavailable")
    return shape_tree


def _slide_group_shape(shape_tree: ET.Element, group_index: int) -> ET.Element:
    ordinal = 0
    for child in list(shape_tree):
        if _xml_local_name(child.tag) != "grpSp":
            continue
        if ordinal == group_index:
            return child
        ordinal += 1
    raise IndexError("group shape index out of range")


def _direct_group_child_group(group_shape: ET.Element, child_index: int) -> ET.Element:
    ordinal = 0
    for child in list(group_shape):
        if _xml_local_name(child.tag) not in {
            "sp",
            "pic",
            "graphicFrame",
            "cxnSp",
            "grpSp",
        }:
            continue
        if ordinal == child_index:
            if _xml_local_name(child.tag) != "grpSp":
                raise IndexError("nested group child index does not reference a group")
            return child
        ordinal += 1
    raise IndexError("nested group child index out of range")


def _empty_group_shape(shape_id: int) -> ET.Element:
    group = ET.Element(f"{{{P_NS}}}grpSp")
    non_visual = ET.SubElement(group, f"{{{P_NS}}}nvGrpSpPr")
    ET.SubElement(
        non_visual,
        f"{{{P_NS}}}cNvPr",
        {"id": str(shape_id), "name": f"Group {shape_id - 1}"},
    )
    ET.SubElement(non_visual, f"{{{P_NS}}}cNvGrpSpPr")
    ET.SubElement(non_visual, f"{{{P_NS}}}nvPr")
    group_properties = ET.SubElement(group, f"{{{P_NS}}}grpSpPr")
    xfrm = ET.SubElement(group_properties, f"{{{A_NS}}}xfrm")
    ET.SubElement(xfrm, f"{{{A_NS}}}off", {"x": "0", "y": "0"})
    ET.SubElement(xfrm, f"{{{A_NS}}}ext", {"cx": "0", "cy": "0"})
    ET.SubElement(xfrm, f"{{{A_NS}}}chOff", {"x": "0", "y": "0"})
    ET.SubElement(xfrm, f"{{{A_NS}}}chExt", {"cx": "0", "cy": "0"})
    return group


def _next_shape_tree_id(shape_tree: ET.Element) -> int:
    max_id = 0
    for c_nv_pr in shape_tree.findall(f".//{{{P_NS}}}cNvPr"):
        raw_id = c_nv_pr.attrib.get("id", "0")
        try:
            max_id = max(max_id, int(raw_id))
        except ValueError:
            continue
    return max_id + 1


def _next_shape_tree_name(shape_tree: ET.Element, prefix: str) -> str:
    shape_count = sum(
        1
        for child in list(shape_tree)
        if _xml_local_name(child.tag) in {"sp", "pic", "graphicFrame", "cxnSp", "grpSp"}
    )
    return f"{prefix} {shape_count + 1}"


def _as_chartex_graphic_frame(graphic_frame: ET.Element) -> None:
    """Convert a classic chart frame template into a ChartEx relationship frame."""
    data = graphic_frame.find(f".//{{{A_NS}}}graphicData")
    if data is None:
        raise AttributeError("chart frame graphic data is unavailable")
    chart = data.find(f"{{{C_NS}}}chart")
    if chart is None:
        raise AttributeError("chart frame relationship is unavailable")
    data.remove(chart)
    data.set("uri", CX_NS)
    ET.SubElement(data, f"{{{CX_NS}}}chart")


def _set_chart_frame_identity(
    chart_frame: ET.Element,
    shape_id: int,
    name: str,
    relationship_id: str,
) -> None:
    non_visual_properties = chart_frame.find(f"{{{P_NS}}}nvGraphicFramePr/{{{P_NS}}}cNvPr")
    if non_visual_properties is None:
        raise AttributeError("chart frame non-visual properties are unavailable")
    non_visual_properties.set("id", str(shape_id))
    non_visual_properties.set("name", name)
    chart = chart_frame.find(f".//{{{C_NS}}}chart")
    if chart is None:
        chart = chart_frame.find(f".//{{{CX_NS}}}chart")
    if chart is None:
        raise AttributeError("chart frame relationship is unavailable")
    chart.set(f"{{{R_NS}}}id", relationship_id)


def _shape_bounds(shape: ET.Element) -> tuple[int, int, int, int]:
    tag = _xml_local_name(shape.tag)
    if tag == "grpSp":
        xfrm = shape.find(f"{{{P_NS}}}grpSpPr/{{{A_NS}}}xfrm")
    elif tag == "graphicFrame":
        xfrm = shape.find(f"{{{P_NS}}}xfrm")
    else:
        xfrm = shape.find(f"{{{P_NS}}}spPr/{{{A_NS}}}xfrm")
    if xfrm is None:
        raise ValueError("group child is missing transform")
    offset = xfrm.find(f"{{{A_NS}}}off")
    extent = xfrm.find(f"{{{A_NS}}}ext")
    if offset is None or extent is None:
        raise ValueError("group child is missing transform bounds")
    return (
        int(offset.attrib.get("x", "0")),
        int(offset.attrib.get("y", "0")),
        int(extent.attrib.get("cx", "0")),
        int(extent.attrib.get("cy", "0")),
    )


def _scaled_group_coordinate(value: int, extent: int, child_extent: int) -> int:
    product = value * extent
    if product < 0:
        return -((-product + child_extent // 2) // child_extent)
    return (product + child_extent // 2) // child_extent


def _append_group_shape_child(group_shape: ET.Element, child: ET.Element) -> None:
    group_xfrm = group_shape.find(f"{{{P_NS}}}grpSpPr/{{{A_NS}}}xfrm")
    if group_xfrm is None:
        raise ValueError("group shape is missing transform")
    offset = group_xfrm.find(f"{{{A_NS}}}off")
    extent = group_xfrm.find(f"{{{A_NS}}}ext")
    child_offset = group_xfrm.find(f"{{{A_NS}}}chOff")
    child_extent = group_xfrm.find(f"{{{A_NS}}}chExt")
    if offset is None or extent is None or child_offset is None or child_extent is None:
        raise ValueError("group shape transform is incomplete")

    off_x = int(offset.attrib.get("x", "0"))
    off_y = int(offset.attrib.get("y", "0"))
    ext_x = int(extent.attrib.get("cx", "0"))
    ext_y = int(extent.attrib.get("cy", "0"))
    ch_off_x = int(child_offset.attrib.get("x", "0"))
    ch_off_y = int(child_offset.attrib.get("y", "0"))
    ch_ext_x = int(child_extent.attrib.get("cx", "0"))
    ch_ext_y = int(child_extent.attrib.get("cy", "0"))
    child_x, child_y, child_cx, child_cy = _shape_bounds(child)
    initialized = ext_x > 0 and ext_y > 0 and ch_ext_x > 0 and ch_ext_y > 0

    if initialized:
        left = min(ch_off_x, child_x)
        top = min(ch_off_y, child_y)
        right = max(ch_off_x + ch_ext_x, child_x + child_cx)
        bottom = max(ch_off_y + ch_ext_y, child_y + child_cy)
        width = right - left
        height = bottom - top
        if group_xfrm.attrib.get("flipH") not in {None, "0", "false", "False"}:
            off_x += _scaled_group_coordinate(
                ch_off_x + ch_ext_x - left - width,
                ext_x,
                ch_ext_x,
            )
        else:
            off_x += _scaled_group_coordinate(left - ch_off_x, ext_x, ch_ext_x)
        if group_xfrm.attrib.get("flipV") not in {None, "0", "false", "False"}:
            off_y += _scaled_group_coordinate(
                ch_off_y + ch_ext_y - top - height,
                ext_y,
                ch_ext_y,
            )
        else:
            off_y += _scaled_group_coordinate(top - ch_off_y, ext_y, ch_ext_y)
        ext_x = _scaled_group_coordinate(width, ext_x, ch_ext_x)
        ext_y = _scaled_group_coordinate(height, ext_y, ch_ext_y)
    else:
        child_bounds = [
            _shape_bounds(existing)
            for existing in group_shape
            if _xml_local_name(existing.tag) in {"sp", "pic", "graphicFrame", "cxnSp", "grpSp"}
        ]
        child_bounds.append((child_x, child_y, child_cx, child_cy))
        left = min(x for x, _y, _cx, _cy in child_bounds)
        top = min(y for _x, y, _cx, _cy in child_bounds)
        right = max(x + cx for x, _y, cx, _cy in child_bounds)
        bottom = max(y + cy for _x, y, _cx, cy in child_bounds)
        width = right - left
        height = bottom - top
        off_x = left
        off_y = top
        ext_x = width
        ext_y = height

    offset.attrib.update({"x": str(off_x), "y": str(off_y)})
    extent.attrib.update({"cx": str(ext_x), "cy": str(ext_y)})
    child_offset.attrib.update({"x": str(left), "y": str(top)})
    child_extent.attrib.update({"cx": str(width), "cy": str(height)})
    _insert_shape_tree_child(group_shape, child)


def _insert_shape_tree_child(shape_tree: ET.Element, child: ET.Element) -> None:
    insert_at = len(shape_tree)
    for index, existing in enumerate(list(shape_tree)):
        if _xml_local_name(existing.tag) == "extLst":
            insert_at = index
            break
    shape_tree.insert(insert_at, child)


def _relative_package_target(source_part: str, target_part: str) -> str:
    return posixpath.relpath(target_part, posixpath.dirname(source_part))


def _retarget_chart_relationships(
    chart_rels_root: ET.Element,
    chart_part: str,
    workbook_part: str,
) -> None:
    for relationship in chart_rels_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if relationship.attrib.get("Type") == _PACKAGE_REL_TYPE:
            relationship.set(
                "Target",
                _relative_package_target(chart_part, workbook_part),
            )


def _ensure_content_type_default(
    root: ET.Element,
    extension: str,
    content_type: str,
) -> None:
    for default in root.findall(f"{{{CONTENT_TYPES_NS}}}Default"):
        if default.attrib.get("Extension", "").lower() == extension.lower():
            default.set("ContentType", content_type)
            return
    root.insert(
        _content_type_default_insert_index(root),
        ET.Element(
            f"{{{CONTENT_TYPES_NS}}}Default",
            {"Extension": extension, "ContentType": content_type},
        ),
    )


def _ensure_content_type_override(
    root: ET.Element,
    partname: str,
    content_type: str,
) -> None:
    normalized = f"/{partname.lstrip('/')}"
    for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == normalized:
            override.set("ContentType", content_type)
            return
    root.append(
        ET.Element(
            f"{{{CONTENT_TYPES_NS}}}Override",
            {"PartName": normalized, "ContentType": content_type},
        )
    )


def _content_type_default_insert_index(root: ET.Element) -> int:
    insert_at = 0
    for index, child in enumerate(list(root)):
        if _xml_local_name(child.tag) == "Default":
            insert_at = index + 1
    return insert_at


def _next_numbered_part(names: set[str], prefix: str, suffix: str) -> str:
    max_number = 0
    for name in names:
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        raw_number = name[len(prefix) : len(name) - len(suffix)]
        try:
            max_number = max(max_number, int(raw_number))
        except ValueError:
            continue
    return f"{prefix}{max_number + 1}{suffix}"
