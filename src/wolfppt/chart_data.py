"""First-party chart data: authoring containers and editable chart data sources.

Besides the authoring containers, this module exposes a chart's embedded
workbook as worksheets and cells (:class:`ChartDataWorkbook`) and the chart's
series sources (:class:`EditableChartData`) inside a :class:`ChartDataPackage`.
Chart, slide and embedded-workbook parts are read in either ECMA-376 profile:
Strict parts are queried in Transitional form and edited parts serialize back
to the profile they were read in.

Author with ``CategoryChartData(workbook_locale="de-DE")`` (also available on
XY/bubble data), then read ``ChartDataPackage(path).slide_chart_data(0).workbook``.
Read ``workbook.workbook_locale`` and ``workbook.get_cell(0, "B2").number_format``
after saving. With a locale, General numeric cells use grouped, two-decimal
formats; date categories use that locale's date order. Custom precision is kept.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Iterable, Iterator, Sequence
from contextlib import suppress
from copy import copy, deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .chart_workbook import (
    _CONTENT_TYPES_NS,
    _DOC_REL_NS,
    _FIXED_ZIP_DATE,
    _INVALID_SHEET_NAME_CHARACTERS,
    _OFFICE_DOCUMENT_REL_TYPE,
    _REL_NS,
    _SHARED_STRINGS_REL_TYPE,
    _SS_NS,
    _STYLES_REL_TYPE,
    _UNSUPPORTED,
    _WORKSHEET_CONTENT_TYPE,
    _WORKSHEET_REL_TYPE,
    _XML_DECLARATION,
    _XML_NS,
    CellError,
    CellValue,
    ChartCellValueRefusal,
    UnsupportedFormulaError,
    _excel_date_number,
    _expand_shared_formulas,
    _FormulaEvaluator,
    _number_text,
    _parse_formula,
    _read_date_value,
    _validated_date_value,
    cell_address,
    chart_reference_for_cells,
    parse_cell_address,
    parse_chart_reference,
    serialize_xml_preserving_namespaces,
)
from .package_parts import copy_package_with_replacements
from .xml_helpers import STRICT_P_NS, STRICT_R_NS

__all__ = [
    "BubbleChartData",
    "BubbleDataPoint",
    "BubbleSeries",
    "CategoryChartData",
    "CategorySeries",
    "CellError",
    "ChartCellValueRefusal",
    "ChartDataCell",
    "ChartDataWorkbook",
    "ChartDataWorksheet",
    "ChartDataWorksheetCollection",
    "ChartWorkbookLocale",
    "ChartWorkbookLocaleRefusal",
    "UnsupportedFormulaError",
    "XyChartData",
    "XyDataPoint",
    "XySeries",
]


class ChartWorkbookLocaleRefusal(ValueError):
    """Unsupported locale for a generated chart data workbook."""


class ChartWorkbookLocale(StrEnum):
    """Supported workbook locales, encoded by SpreadsheetML locale directives.

    Numeric format syntax remains invariant (``#,##0.00``); the locale directive
    selects the decimal/grouping convention. Date formats use explicit order.
    No locale means the existing, locale-neutral workbook output.
    """

    EN_US = "en-US"
    DE_DE = "de-DE"

    @classmethod
    def validate(cls, value: str | None) -> ChartWorkbookLocale | None:
        if value is None:
            return None
        try:
            return cls(value)
        except (ValueError, TypeError):
            raise ChartWorkbookLocaleRefusal(
                f"unsupported chart workbook locale {value!r}; supported: en-US, de-DE"
            ) from None

    @property
    def format_prefix(self) -> str:
        return "[$-409]" if self is self.EN_US else "[$-407]"

    @property
    def decimal_separator(self) -> str:
        return "." if self is self.EN_US else ","

    @property
    def grouping_separator(self) -> str:
        return "," if self is self.EN_US else "."

    @property
    def date_format(self) -> str:
        return "mm/dd/yyyy" if self is self.EN_US else "dd.mm.yyyy"


class XyDataPoint:
    """One numeric coordinate point (x, y) in an XY scatter series."""

    def __init__(
        self,
        x: float,
        y: float,
        number_format: str | None = None,
        *,
        series: XySeries | None = None,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self._number_format = number_format
        self._series = series

    @property
    def number_format(self) -> str:
        """Point format, inherited from the series when not set."""
        if self._number_format is not None:
            return self._number_format
        return self._series.number_format if self._series is not None else "General"

    def __repr__(self) -> str:
        return f"XyDataPoint(x={self.x!r}, y={self.y!r})"


class XySeries:
    """One series of numeric coordinates in an XY scatter chart."""

    def __init__(
        self,
        name: str = "",
        number_format: str | None = None,
        *,
        chart_data: XyChartData | None = None,
    ) -> None:
        self.name = str(name)
        self._chart_data = chart_data
        self._number_format = number_format
        self._points: list[XyDataPoint] = []

    def add_data_point(self, x: float, y: float, number_format: str | None = None) -> XyDataPoint:
        point = XyDataPoint(x, y, number_format, series=self)
        self._points.append(point)
        return point

    def __iter__(self) -> Iterator[XyDataPoint]:
        return iter(self._points)

    def __len__(self) -> int:
        return len(self._points)

    def __repr__(self) -> str:
        return f"XySeries(name={self.name!r}, points={len(self._points)})"

    @property
    def number_format(self) -> str:
        """Series format, inherited from the chart data when not set."""
        if self._number_format is not None:
            return self._number_format
        if self._chart_data is None:
            return "General"
        return self._chart_data.number_format

    @property
    def x_values(self) -> list[float]:
        return [point.x for point in self._points]

    @property
    def values(self) -> list[float]:
        return [point.y for point in self._points]


class XyChartData:
    """First-party XY data; use ``workbook_locale`` for generated cell formats."""

    def __init__(
        self, number_format: str = "General", *, workbook_locale: str | None = None
    ) -> None:
        self.workbook_locale = ChartWorkbookLocale.validate(workbook_locale)
        self.number_format = number_format
        self._series: list[XySeries] = []

    def add_series(self, name: str = "", number_format: str | None = None) -> XySeries:
        series = XySeries(name, number_format, chart_data=self)
        self._series.append(series)
        return series

    def __iter__(self) -> Iterator[XySeries]:
        return iter(self._series)

    def __len__(self) -> int:
        return len(self._series)

    def __repr__(self) -> str:
        return f"XyChartData(series={len(self._series)})"


class BubbleDataPoint(XyDataPoint):
    """One numeric (x, y, bubble size) point in a bubble chart series."""

    def __init__(
        self,
        x: float,
        y: float,
        size: float,
        number_format: str | None = None,
        *,
        series: BubbleSeries | None = None,
    ) -> None:
        super().__init__(x, y, number_format, series=series)
        self.bubble_size = float(size)

    def __repr__(self) -> str:
        return f"BubbleDataPoint(x={self.x!r}, y={self.y!r}, bubble_size={self.bubble_size!r})"


class BubbleSeries(XySeries):
    """One series of (x, y, bubble size) points in a bubble chart."""

    def __init__(
        self,
        chart_data: BubbleChartData,
        name: str = "",
        number_format: str | None = None,
    ) -> None:
        super().__init__(name, number_format, chart_data=chart_data)
        self._chart_data: BubbleChartData = chart_data
        self._points: list[BubbleDataPoint] = []

    def add_data_point(  # type: ignore[override]
        self,
        x: float,
        y: float,
        size: float,
        number_format: str | None = None,
    ) -> BubbleDataPoint:
        point = BubbleDataPoint(x, y, size, number_format, series=self)
        self._points.append(point)
        return point

    def __iter__(self) -> Iterator[BubbleDataPoint]:
        return iter(self._points)

    def __getitem__(self, index: int) -> BubbleDataPoint:
        return self._points[index]

    def __repr__(self) -> str:
        return f"BubbleSeries(name={self.name!r}, points={len(self._points)})"

    @property
    def points(self) -> list[BubbleDataPoint]:
        return list(self._points)

    @property
    def y_values(self) -> list[float]:
        return self.values

    @property
    def bubble_sizes(self) -> list[float]:
        return [point.bubble_size for point in self._points]

    @property
    def bubble_sizes_ref(self) -> str:
        return self._chart_data.bubble_sizes_ref(self)


class BubbleChartData(XyChartData):
    """First-party data container for bubble charts (XY plus bubble size)."""

    def __init__(
        self, number_format: str = "General", *, workbook_locale: str | None = None
    ) -> None:
        super().__init__(number_format, workbook_locale=workbook_locale)
        self._series: list[BubbleSeries] = []  # type: ignore[assignment]

    def add_series(  # type: ignore[override]
        self, name: str = "", number_format: str | None = None
    ) -> BubbleSeries:
        series = BubbleSeries(self, name, number_format)
        self._series.append(series)
        return series

    def __iter__(self) -> Iterator[BubbleSeries]:
        return iter(self._series)

    def __getitem__(self, index: int) -> BubbleSeries:
        return self._series[index]

    def bubble_sizes_ref(self, series: BubbleSeries) -> str:
        """Embedded-worksheet range holding *series* bubble sizes.

        Each series table is a name row followed by one row per point, with
        one spacer row between tables, matching the add_chart workbook layout.
        """
        top_row = 2
        for candidate in self._series:
            if candidate is series:
                bottom_row = top_row + len(series) - 1
                return f"Sheet1!$C${top_row}:$C${bottom_row}"
            top_row += len(candidate) + 2
        raise ValueError("series not in chart data object")

    def __repr__(self) -> str:
        return f"BubbleChartData(series={len(self._series)})"


class CategorySeries:
    """One series of values in a category-based chart."""

    def __init__(self, name: str = "", values: Iterable[float | None] = ()) -> None:
        self.name = str(name)
        self.values = [float(v) if v is not None else None for v in values]

    def __repr__(self) -> str:
        return f"CategorySeries(name={self.name!r}, values={len(self.values)})"


class CategoryChartData:
    """Category data; use ``workbook_locale`` for numeric and date cell formats."""

    def __init__(self, *, workbook_locale: str | None = None) -> None:
        self.workbook_locale = ChartWorkbookLocale.validate(workbook_locale)
        self.categories: list[str] = []
        self._series: list[CategorySeries] = []

    def add_series(self, name: str = "", values: Iterable[float | None] = ()) -> CategorySeries:
        series = CategorySeries(name, values)
        self._series.append(series)
        return series

    def __iter__(self) -> Iterator[CategorySeries]:
        return iter(self._series)

    def __len__(self) -> int:
        return len(self._series)

    def __repr__(self) -> str:
        return f"CategoryChartData(categories={len(self.categories)}, series={len(self._series)})"


_UNSET: Any = object()
_UNSET: Any = object()
_BUILTIN_NUMBER_FORMATS = {
    0: "General",
    1: "0",
    2: "0.00",
    3: "#,##0",
    4: "#,##0.00",
    9: "0%",
    10: "0.00%",
    11: "0.00E+00",
    12: "# ?/?",
    13: "# ??/??",
    14: "m/d/yyyy",
    15: "d-mmm-yy",
    16: "d-mmm",
    17: "mmm-yy",
    18: "h:mm AM/PM",
    19: "h:mm:ss AM/PM",
    20: "h:mm",
    21: "h:mm:ss",
    22: "m/d/yyyy h:mm",
    37: "#,##0 ;(#,##0)",
    38: "#,##0 ;[Red](#,##0)",
    39: "#,##0.00;(#,##0.00)",
    40: "#,##0.00;[Red](#,##0.00)",
    45: "mm:ss",
    46: "[h]:mm:ss",
    47: "mmss.0",
    48: "##0.0E+0",
    49: "@",
}


class ChartDataCell:
    """One addressable cell of a chart data worksheet."""

    __slots__ = ("_worksheet", "column", "row")

    def __init__(self, worksheet: ChartDataWorksheet, row: int, column: int) -> None:
        cell_address(row, column)
        self._worksheet = worksheet
        self.row = row
        self.column = column

    @property
    def worksheet(self) -> ChartDataWorksheet:
        return self._worksheet

    @property
    def address(self) -> str:
        """Relative A1 address such as ``B2``."""
        return cell_address(self.row, self.column)

    @property
    def absolute_address(self) -> str:
        """Absolute A1 address such as ``$B$2``."""
        return cell_address(self.row, self.column, absolute=True)

    @property
    def reference(self) -> str:
        """Sheet-qualified absolute reference such as ``Sheet1!$B$2``."""
        return chart_reference_for_cells([self])

    @property
    def value(self) -> CellValue:
        """Cell value; for formula cells the calculated result.

        Invalid assignments leave the existing value and formula unchanged.
        Dates and naive date-times use explicit SpreadsheetML ISO ``t=d`` values,
        retaining their Python type and microseconds on readback. Unsupported
        types and timezone-aware date-times raise :class:`ChartCellValueRefusal`.
        Non-finite numbers retain their existing ``ValueError`` refusal.
        """
        workbook = self._worksheet.workbook
        element = self._worksheet._cell_element(self.row, self.column, create=False)
        if element is None:
            return None
        if element.find(f"{{{_SS_NS}}}f") is not None and workbook._needs_calculation:
            workbook.calculate_formulas()
        return workbook._element_value(element)

    @value.setter
    def value(self, value: CellValue | int) -> None:
        value = _validated_cell_value(value)
        element = self._worksheet._cell_element(self.row, self.column, create=True)
        assert element is not None
        _write_cell_value(element, value, keep_formula=False)
        self._worksheet._touch()

    @property
    def formula(self) -> str | None:
        """Formula text without the leading ``=``, or ``None`` for a value cell."""
        element = self._worksheet._cell_element(self.row, self.column, create=False)
        if element is None:
            return None
        formula = element.find(f"{{{_SS_NS}}}f")
        return None if formula is None else formula.text or ""

    @formula.setter
    def formula(self, formula: str | None) -> None:
        if formula is None:
            current = self.value
            self.value = current
            return
        text = str(formula).strip().removeprefix("=").strip()
        if not text:
            raise ValueError("formula text is empty")
        _parse_formula(text)
        element = self._worksheet._cell_element(self.row, self.column, create=True)
        assert element is not None
        _write_cell_value(element, None, keep_formula=False)
        formula_element = ET.Element(f"{{{_SS_NS}}}f")
        formula_element.text = text
        element.insert(0, formula_element)
        self._worksheet._touch()

    @property
    def number_format(self) -> str:
        """Number format code applied through the cell style."""
        element = self._worksheet._cell_element(self.row, self.column, create=False)
        style = 0 if element is None else int(element.get("s") or 0)
        number_format = self._worksheet.workbook._number_format(style)
        if number_format == "General" and element is not None and element.get("t") == "d":
            value = self._worksheet.workbook._element_value(element)
            return "yyyy-mm-dd hh:mm:ss" if isinstance(value, datetime) else "yyyy-mm-dd"
        return number_format

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ChartDataCell)
            and other._worksheet is self._worksheet
            and other.row == self.row
            and other.column == self.column
        )

    def __hash__(self) -> int:
        return hash((id(self._worksheet), self.row, self.column))

    def __repr__(self) -> str:
        return f"ChartDataCell({self.reference!r})"


class ChartDataWorksheet:
    """One worksheet of a chart data workbook."""

    def __init__(self, workbook: ChartDataWorkbook, name: str, part: str) -> None:
        self._workbook = workbook
        self._name = name
        self._part = part
        self._root: ET.Element | None = None
        self._rows: dict[int, ET.Element] = {}
        self._cells: dict[tuple[int, int], ET.Element] = {}
        self._strict = False

    @property
    def workbook(self) -> ChartDataWorkbook:
        return self._workbook

    @property
    def name(self) -> str:
        return self._name

    @property
    def index(self) -> int:
        return self._workbook._worksheets.index(self)

    @property
    def part_name(self) -> str:
        return self._part

    def cell(self, address: str | tuple[int, int]) -> ChartDataCell:
        """Return the cell at an A1 ``address`` or one-based ``(row, column)``."""
        if isinstance(address, tuple):
            row, column = address
        else:
            row, column = parse_cell_address(address)
        return ChartDataCell(self, int(row), int(column))

    def get_cell(self, address: str, value: Any = _UNSET) -> ChartDataCell:
        """Return the cell at ``address``, first writing ``value`` when given."""
        cell = self.cell(address)
        if value is not _UNSET:
            cell.value = value
        return cell

    def cells(self, area: str) -> list[ChartDataCell]:
        """Return the cells of an A1 area such as ``B2:B4`` in row-major order."""
        first, _, last = area.partition(":")
        row1, column1 = parse_cell_address(first)
        row2, column2 = parse_cell_address(last) if last else (row1, column1)
        return [
            ChartDataCell(self, row, column)
            for row in range(min(row1, row2), max(row1, row2) + 1)
            for column in range(min(column1, column2), max(column1, column2) + 1)
        ]

    @property
    def used_range(self) -> str | None:
        """A1 area spanning every cell holding a value or formula."""
        self._load()
        used = [key for key, element in self._cells.items() if _has_content(element)]
        if not used:
            return None
        rows = [row for row, _column in used]
        columns = [column for _row, column in used]
        first = cell_address(min(rows), min(columns))
        last = cell_address(max(rows), max(columns))
        return first if first == last else f"{first}:{last}"

    def __repr__(self) -> str:
        return f"ChartDataWorksheet(name={self._name!r})"

    def _touch(self) -> None:
        self._workbook._dirty_parts.add(self._part)
        self._workbook._needs_calculation = True

    def _load(self) -> ET.Element:
        if self._root is not None:
            return self._root
        payload = self._workbook._members.get(self._part)
        if payload is None:
            raise ValueError(f"worksheet part {self._part!r} is unavailable")
        root, self._strict = _parse_part(payload)
        sheet_data = root.find(f"{{{_SS_NS}}}sheetData")
        if sheet_data is None:
            raise ValueError("worksheet has no sheetData element")
        previous_row = 0
        for row in sheet_data.findall(f"{{{_SS_NS}}}row"):
            row_index = int(row.get("r") or previous_row + 1)
            row.set("r", str(row_index))
            previous_row = row_index
            self._rows[row_index] = row
            previous_column = 0
            for element in row.findall(f"{{{_SS_NS}}}c"):
                reference = element.get("r")
                if reference:
                    cell_row, column = parse_cell_address(reference)
                    if cell_row != row_index:
                        raise ValueError("worksheet cell lies outside its row")
                else:
                    column = previous_column + 1
                    element.set("r", cell_address(row_index, column))
                previous_column = column
                self._cells[(row_index, column)] = element
        self._root = root
        _expand_shared_formulas(self._cells)
        return root

    def _cell_element(self, row: int, column: int, *, create: bool) -> ET.Element | None:
        root = self._load()
        element = self._cells.get((row, column))
        if element is not None or not create:
            return element
        row_element = self._rows.get(row)
        if row_element is None:
            sheet_data = root.find(f"{{{_SS_NS}}}sheetData")
            assert sheet_data is not None
            row_element = ET.Element(f"{{{_SS_NS}}}row", {"r": str(row)})
            following = [index for index in self._rows if index > row]
            if following:
                position = list(sheet_data).index(self._rows[min(following)])
                sheet_data.insert(position, row_element)
            else:
                sheet_data.append(row_element)
            self._rows[row] = row_element
        row_element.attrib.pop("spans", None)
        element = ET.Element(f"{{{_SS_NS}}}c", {"r": cell_address(row, column)})
        later = [
            self._cells[(row, other)]
            for other in sorted(c for r, c in self._cells if r == row and c > column)
        ]
        if later:
            row_element.insert(list(row_element).index(later[0]), element)
        else:
            row_element.append(element)
        self._cells[(row, column)] = element
        return element

    def _formula_cells(self) -> list[tuple[int, int, ET.Element]]:
        self._load()
        return [
            (row, column, element)
            for (row, column), element in sorted(self._cells.items())
            if element.find(f"{{{_SS_NS}}}f") is not None
        ]

    def _serialize(self) -> bytes:
        root = self._load()
        dimension = root.find(f"{{{_SS_NS}}}dimension")
        if dimension is None:
            dimension = ET.Element(f"{{{_SS_NS}}}dimension")
            sheet_properties = root.find(f"{{{_SS_NS}}}sheetPr")
            root.insert(0 if sheet_properties is None else 1, dimension)
        dimension.set("ref", self.used_range or "A1")
        return _serialize_part(root, self._workbook._members[self._part], strict=self._strict)


class ChartDataWorksheetCollection(Sequence[ChartDataWorksheet]):
    """Ordered worksheets of a chart data workbook, indexable by position or name."""

    def __init__(self, workbook: ChartDataWorkbook) -> None:
        self._workbook = workbook

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            return self._workbook.worksheet(key)
        return self._workbook._worksheets[key]

    def __iter__(self) -> Iterator[ChartDataWorksheet]:
        return iter(list(self._workbook._worksheets))

    def __len__(self) -> int:
        return len(self._workbook._worksheets)

    def add(self, name: str) -> ChartDataWorksheet:
        return self._workbook.add_worksheet(name)


class ChartDataWorkbook:
    """Editable view of a chart's embedded XLSX workbook.

    Only parts that were actually edited are re-serialized by :meth:`to_bytes`;
    every other workbook member is copied unchanged.
    """

    def __init__(self, payload: bytes) -> None:
        with ZipFile(BytesIO(payload)) as package:
            self._infos = package.infolist()
            self._members = {info.filename: package.read(info.filename) for info in self._infos}
        self._source = payload
        self._dirty_parts: set[str] = set()
        self._needs_calculation = False
        self._uncalculated: list[ChartDataCell] = []
        self._workbook_part = self._main_part()
        self._workbook_rels_part = _rels_part(self._workbook_part)
        self._workbook_root, self._strict = _parse_part(self._members[self._workbook_part])
        properties = self._workbook_root.find(f"{{{_SS_NS}}}workbookPr")
        self._date1904 = properties is not None and properties.get("date1904") in {"1", "true"}
        self._rels_root = ET.fromstring(
            self._members.get(
                self._workbook_rels_part, f'<Relationships xmlns="{_REL_NS}"/>'.encode()
            )
        )
        self._shared_strings = self._read_shared_strings()
        self._number_formats: list[str] | None = None
        self._worksheets: list[ChartDataWorksheet] = []
        targets = {
            relationship.get("Id"): relationship
            for relationship in self._rels_root.findall(f"{{{_REL_NS}}}Relationship")
        }
        sheets = self._workbook_root.find(f"{{{_SS_NS}}}sheets")
        for sheet in [] if sheets is None else sheets.findall(f"{{{_SS_NS}}}sheet"):
            relationship = targets.get(sheet.get(f"{{{_DOC_REL_NS}}}id"))
            if relationship is None or _rel_type(relationship) != _WORKSHEET_REL_TYPE:
                continue
            part = _resolve_part(self._workbook_part, relationship.get("Target") or "")
            self._worksheets.append(ChartDataWorksheet(self, sheet.get("name") or "", part))
        if not self._worksheets:
            raise ValueError("chart data workbook has no worksheets")

    @classmethod
    def from_bytes(cls, payload: bytes) -> ChartDataWorkbook:
        return cls(payload)

    @property
    def workbook_locale(self) -> ChartWorkbookLocale | None:
        """Locale encoded in saved custom formats; ``None`` for neutral/mixed data."""
        part = self._related_part(_STYLES_REL_TYPE)
        if part is None:
            return None
        root = _parse_part(self._members[part])[0]
        codes = [
            item.get("formatCode", "")
            for item in root.iterfind(f"{{{_SS_NS}}}numFmts/{{{_SS_NS}}}numFmt")
        ]
        locale_ids = [
            [
                value
                for value in re.findall(r'"[^"]*"|\\.|\[\$[^\]]*-([0-9a-fA-F]+)\]', code)
                if value
            ]
            for code in codes
        ]
        for locale in ChartWorkbookLocale:
            expected = int(locale.format_prefix[3:-1], 16)
            if locale_ids and all(
                ids and all(int(value, 16) == expected for value in ids) for ids in locale_ids
            ):
                return locale
        return None

    @property
    def worksheets(self) -> ChartDataWorksheetCollection:
        return ChartDataWorksheetCollection(self)

    @property
    def modified(self) -> bool:
        return bool(self._dirty_parts) or self._needs_calculation

    @property
    def uncalculated_cells(self) -> list[ChartDataCell]:
        """Formula cells the last calculation could not evaluate (cache kept)."""
        return list(self._uncalculated)

    def worksheet(self, key: int | str) -> ChartDataWorksheet:
        """Return a worksheet by zero-based index or case-insensitive name."""
        if isinstance(key, int):
            return self._worksheets[key]
        for worksheet in self._worksheets:
            if worksheet.name.casefold() == str(key).casefold():
                return worksheet
        raise KeyError(f"worksheet {key!r} is not in the chart data workbook")

    def get_cell(self, worksheet: int | str, address: str, value: Any = _UNSET) -> ChartDataCell:
        """Return a cell by worksheet index or name, optionally writing ``value``."""
        return self.worksheet(worksheet).get_cell(address, value)

    def cells(self, reference: str) -> list[ChartDataCell]:
        """Resolve a sheet-qualified reference (``Sheet1!$A$2:$A$4``) to its cells."""
        cells: list[ChartDataCell] = []
        for sheet, row1, column1, row2, column2 in parse_chart_reference(reference):
            worksheet = self._worksheets[0] if sheet is None else self.worksheet(sheet)
            cells.extend(
                ChartDataCell(worksheet, row, column)
                for row in range(row1, row2 + 1)
                for column in range(column1, column2 + 1)
            )
        return cells

    def add_worksheet(self, name: str) -> ChartDataWorksheet:
        """Append an empty worksheet named ``name`` and return it."""
        name = _validated_sheet_name(name)
        if any(item.name.casefold() == name.casefold() for item in self._worksheets):
            raise ValueError(f"worksheet {name!r} already exists")
        index = 1
        while f"xl/worksheets/sheet{index}.xml" in self._members:
            index += 1
        part = f"xl/worksheets/sheet{index}.xml"
        spreadsheet_ns = _STRICT_SS_NS if self._strict else _SS_NS
        relationships_ns = STRICT_R_NS if self._strict else _DOC_REL_NS
        self._members[part] = (
            _XML_DECLARATION + f'<worksheet xmlns="{spreadsheet_ns}" xmlns:r="{relationships_ns}">'
            '<dimension ref="A1"/><sheetViews><sheetView workbookViewId="0"/>'
            '</sheetViews><sheetFormatPr defaultRowHeight="15"/><sheetData/>'
            '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" '
            'header="0.3" footer="0.3"/></worksheet>'
        ).encode("utf-8")
        relationship_ids = {
            item.get("Id") for item in self._rels_root.findall(f"{{{_REL_NS}}}Relationship")
        }
        relationship_index = 1
        while f"rId{relationship_index}" in relationship_ids:
            relationship_index += 1
        relationship_id = f"rId{relationship_index}"
        ET.SubElement(
            self._rels_root,
            f"{{{_REL_NS}}}Relationship",
            {
                "Id": relationship_id,
                "Type": _profile_rel_type(_WORKSHEET_REL_TYPE, strict=self._strict),
                "Target": _relative_target(self._workbook_part, part),
            },
        )
        sheets = self._workbook_root.find(f"{{{_SS_NS}}}sheets")
        if sheets is None:
            raise ValueError("chart data workbook has no sheets element")
        sheet_ids = [int(item.get("sheetId") or 0) for item in sheets]
        ET.SubElement(
            sheets,
            f"{{{_SS_NS}}}sheet",
            {
                "name": name,
                "sheetId": str(max(sheet_ids, default=0) + 1),
                f"{{{_DOC_REL_NS}}}id": relationship_id,
            },
        )
        content_types = ET.fromstring(self._members["[Content_Types].xml"])
        ET.SubElement(
            content_types,
            f"{{{_CONTENT_TYPES_NS}}}Override",
            {"PartName": f"/{part}", "ContentType": _WORKSHEET_CONTENT_TYPE},
        )
        self._members["[Content_Types].xml"] = serialize_xml_preserving_namespaces(
            content_types, self._members["[Content_Types].xml"]
        )
        self._dirty_parts.update({self._workbook_part, self._workbook_rels_part})
        self._dirty_parts.add("[Content_Types].xml")
        worksheet = ChartDataWorksheet(self, name, part)
        self._worksheets.append(worksheet)
        return worksheet

    def calculate_formulas(self, *, strict: bool = False) -> None:
        """Recalculate every formula cell and store the results as cached values.

        Formulas the evaluator cannot handle keep their stored cache, are listed
        in :attr:`uncalculated_cells`, and make Excel recalculate on open; with
        ``strict=True`` they raise :class:`UnsupportedFormulaError` instead.
        """
        evaluator = _FormulaEvaluator(self, strict=strict)
        for worksheet in self._worksheets:
            for row, column, element in worksheet._formula_cells():
                result = evaluator.cell_result(worksheet, row, column)
                if result is _UNSUPPORTED:
                    continue
                before = ET.tostring(element)
                _write_cell_value(element, result, keep_formula=True)
                if ET.tostring(element) != before:
                    self._dirty_parts.add(worksheet._part)
        self._uncalculated = [
            ChartDataCell(worksheet, row, column)
            for worksheet, row, column in evaluator.unsupported
        ]
        self._needs_calculation = False
        if self._uncalculated:
            self._request_full_calculation_on_load()

    def to_bytes(self) -> bytes:
        """Return the workbook package with every edit applied."""
        if self._needs_calculation:
            self.calculate_formulas()
        if not self._dirty_parts:
            return self._source
        payloads = dict(self._members)
        for worksheet in self._worksheets:
            if worksheet._part in self._dirty_parts:
                payloads[worksheet._part] = worksheet._serialize()
        if self._workbook_part in self._dirty_parts:
            payloads[self._workbook_part] = _serialize_part(
                self._workbook_root,
                self._members[self._workbook_part],
                strict=self._strict,
            )
        if self._workbook_rels_part in self._dirty_parts:
            payloads[self._workbook_rels_part] = serialize_xml_preserving_namespaces(
                self._rels_root,
                self._members.get(
                    self._workbook_rels_part,
                    f'<Relationships xmlns="{_REL_NS}"/>'.encode(),
                ),
            )
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=1) as package:
            written = set()
            for info in self._infos:
                item = copy(info)
                item.compress_type = ZIP_DEFLATED
                package.writestr(item, payloads[info.filename], compresslevel=1)
                written.add(info.filename)
            for name, payload in payloads.items():
                if name not in written:
                    info = ZipInfo(name, date_time=_FIXED_ZIP_DATE)
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o600 << 16
                    package.writestr(info, payload, compresslevel=1)
        return buffer.getvalue()

    def _main_part(self) -> str:
        root_rels = self._members.get("_rels/.rels")
        if root_rels is not None:
            for relationship in ET.fromstring(root_rels):
                if _rel_type(relationship) == _OFFICE_DOCUMENT_REL_TYPE:
                    return _resolve_part("", relationship.get("Target") or "")
        if "xl/workbook.xml" in self._members:
            return "xl/workbook.xml"
        raise ValueError("chart data workbook has no workbook part")

    def _related_part(self, relationship_type: str) -> str | None:
        for relationship in self._rels_root.findall(f"{{{_REL_NS}}}Relationship"):
            if _rel_type(relationship) == relationship_type:
                return _resolve_part(self._workbook_part, relationship.get("Target") or "")
        return None

    def _read_shared_strings(self) -> list[str]:
        part = self._related_part(_SHARED_STRINGS_REL_TYPE)
        if part is None or part not in self._members:
            return []
        root = _parse_part(self._members[part])[0]
        values = []
        for item in root.findall(f"{{{_SS_NS}}}si"):
            texts = item.findall(f"{{{_SS_NS}}}t") + item.findall(f"{{{_SS_NS}}}r/{{{_SS_NS}}}t")
            values.append("".join(text.text or "" for text in texts))
        return values

    def _number_format(self, style_index: int) -> str:
        if self._number_formats is None:
            self._number_formats = []
            part = self._related_part(_STYLES_REL_TYPE)
            if part is not None and part in self._members:
                root = _parse_part(self._members[part])[0]
                custom = {
                    int(item.get("numFmtId") or 0): item.get("formatCode") or "General"
                    for item in root.iterfind(f"{{{_SS_NS}}}numFmts/{{{_SS_NS}}}numFmt")
                }
                for xf in root.iterfind(f"{{{_SS_NS}}}cellXfs/{{{_SS_NS}}}xf"):
                    format_id = int(xf.get("numFmtId") or 0)
                    self._number_formats.append(
                        custom.get(format_id, _BUILTIN_NUMBER_FORMATS.get(format_id, "General"))
                    )
        if 0 <= style_index < len(self._number_formats):
            return self._number_formats[style_index]
        return "General"

    def _element_value(self, element: ET.Element) -> CellValue:
        kind = element.get("t") or "n"
        if kind == "inlineStr":
            inline = element.find(f"{{{_SS_NS}}}is")
            if inline is None:
                return ""
            texts = inline.findall(f"{{{_SS_NS}}}t") + inline.findall(
                f"{{{_SS_NS}}}r/{{{_SS_NS}}}t"
            )
            return "".join(text.text or "" for text in texts)
        raw = element.findtext(f"{{{_SS_NS}}}v")
        if raw is None:
            return None
        if kind == "s":
            try:
                return self._shared_strings[int(raw)]
            except (ValueError, IndexError) as exc:
                raise ValueError("worksheet shared string is unavailable") from exc
        if kind == "d":
            return _read_date_value(raw)
        if kind == "str":
            return raw
        if kind == "b":
            return raw.strip() in {"1", "true"}
        if kind == "e":
            return CellError(raw)
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"worksheet numeric cell value {raw!r} is invalid") from exc

    def _request_full_calculation_on_load(self) -> None:
        calculation = self._workbook_root.find(f"{{{_SS_NS}}}calcPr")
        if calculation is None:
            calculation = ET.Element(f"{{{_SS_NS}}}calcPr")
            followers = {
                "oleSize",
                "customWorkbookViews",
                "pivotCaches",
                "smartTagPr",
                "smartTagTypes",
                "webPublishing",
                "fileRecoveryPr",
                "webPublishObjects",
                "extLst",
            }
            position = len(self._workbook_root)
            for index, child in enumerate(self._workbook_root):
                if child.tag.rsplit("}", 1)[-1] in followers:
                    position = index
                    break
            self._workbook_root.insert(position, calculation)
        if calculation.get("fullCalcOnLoad") != "1":
            calculation.set("fullCalcOnLoad", "1")
            self._dirty_parts.add(self._workbook_part)


def _rels_part(part: str) -> str:
    directory, _, name = part.rpartition("/")
    return f"{directory}/_rels/{name}.rels" if directory else f"_rels/{name}.rels"


def _resolve_part(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    directory = source_part.rpartition("/")[0]
    parts: list[str] = [item for item in directory.split("/") if item]
    for item in target.split("/"):
        if item == "..":
            if parts:
                parts.pop()
        elif item and item != ".":
            parts.append(item)
    return "/".join(parts)


def _relative_target(source_part: str, target_part: str) -> str:
    directory = source_part.rpartition("/")[0]
    if directory and target_part.startswith(directory + "/"):
        return target_part[len(directory) + 1 :]
    return "/" + target_part


def _validated_sheet_name(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("worksheet name must be str")
    if not 1 <= len(name) <= 31:
        raise ValueError("worksheet name must be 1 to 31 characters")
    if any(character in _INVALID_SHEET_NAME_CHARACTERS for character in name):
        raise ValueError("worksheet name contains a character Excel forbids")
    if name.startswith("'") or name.endswith("'"):
        raise ValueError("worksheet name cannot start or end with an apostrophe")
    return name


def _has_content(element: ET.Element) -> bool:
    return any(element.find(f"{{{_SS_NS}}}{name}") is not None for name in ("v", "f", "is"))


def _finite_number(value: int | float, message: str) -> float:
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(message) from exc
    if not math.isfinite(number):
        raise ValueError(message)
    return number


def _validated_cell_value(value: Any) -> CellValue:
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, date):
        return _validated_date_value(value)
    if isinstance(value, int | float):
        return _finite_number(value, "cell numbers must be finite")
    raise ChartCellValueRefusal(
        f"cell values must be str, int, float, bool, date, datetime or None, "
        f"not {type(value).__name__}"
    )


def _write_cell_value(element: ET.Element, value: Any, *, keep_formula: bool) -> None:
    value = _validated_cell_value(value)
    for child in list(element):
        local = child.tag.rsplit("}", 1)[-1]
        if local in {"v", "is"} or (local == "f" and not keep_formula):
            element.remove(child)
    element.attrib.pop("t", None)
    if value is None:
        return
    if isinstance(value, CellError):
        element.set("t", "e")
        ET.SubElement(element, f"{{{_SS_NS}}}v").text = str(value)
    elif isinstance(value, bool):
        element.set("t", "b")
        ET.SubElement(element, f"{{{_SS_NS}}}v").text = "1" if value else "0"
    elif isinstance(value, float):
        ET.SubElement(element, f"{{{_SS_NS}}}v").text = _number_text(value)
    elif isinstance(value, date):
        element.set("t", "d")
        ET.SubElement(element, f"{{{_SS_NS}}}v").text = value.isoformat()
    elif isinstance(value, str):
        if keep_formula:
            element.set("t", "str")
            text = ET.SubElement(element, f"{{{_SS_NS}}}v")
        else:
            element.set("t", "inlineStr")
            inline = ET.SubElement(element, f"{{{_SS_NS}}}is")
            text = ET.SubElement(inline, f"{{{_SS_NS}}}t")
        text.text = value
        if value != value.strip():
            text.set(f"{{{_XML_NS}}}space", "preserve")


# ---------------------------------------------------------------------------
# Chart-side data sources: series names, categories and values.

_C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_PACKAGE_REL_TYPE = f"{_DOC_REL_NS}/package"
_OLE_OBJECT_REL_TYPE = f"{_DOC_REL_NS}/oleObject"
_SLIDE_REL_TYPE = f"{_DOC_REL_NS}/slide"
_EMPTY_RELATIONSHIPS = f'<Relationships xmlns="{_REL_NS}"/>'.encode()
_SERIES_ROLES = {
    "name": "tx",
    "categories": "cat",
    "values": "val",
    "x_values": "xVal",
    "y_values": "yVal",
    "bubble_sizes": "bubbleSize",
}
_ROLE_FOLLOWERS = {
    "cat": {"val", "shape", "smooth", "extLst"},
    "val": {"shape", "smooth", "extLst"},
    "xVal": {"yVal", "bubbleSize", "smooth", "bubble3D", "extLst"},
    "yVal": {"bubbleSize", "smooth", "bubble3D", "extLst"},
    "bubbleSize": {"bubble3D", "extLst"},
}
_XY_PLOTS = {"scatterChart", "bubbleChart"}
_CHART_SPACE_FOLLOWERS = {"printSettings", "userShapes", "extLst"}
# ECMA-376 Strict renames these namespaces and the relationship-type base URI.
# Parts are queried in Transitional form; edited parts serialize back to the
# profile they were read in, and unedited parts are copied byte for byte.
_STRICT_C_NS = "http://purl.oclc.org/ooxml/drawingml/chart"
_STRICT_SS_NS = "http://purl.oclc.org/ooxml/spreadsheetml/main"
_STRICT_MARKER = b"http://purl.oclc.org/ooxml/"
_TO_TRANSITIONAL = {
    f"{{{strict}}}": f"{{{transitional}}}"
    for strict, transitional in (
        (_STRICT_C_NS, _C_NS),
        (_STRICT_SS_NS, _SS_NS),
        (STRICT_P_NS, _P_NS),
        (STRICT_R_NS, _DOC_REL_NS),
    )
}
_TO_STRICT = {transitional: strict for strict, transitional in _TO_TRANSITIONAL.items()}


class ChartDataSourceType(StrEnum):
    """Where a chart's data lives."""

    EMBEDDED_WORKBOOK = "embedded_workbook"
    EXTERNAL_WORKBOOK = "external_workbook"
    LITERAL = "literal"


@dataclass(frozen=True)
class ChartValueSource:
    """The source of one series name, category set or value set.

    ``source_type`` is ``"cells"`` (``formula`` names the workbook cells and
    ``cells`` resolves them for embedded workbooks), ``"literal"`` (values are
    stored in the chart itself) or ``"none"``. ``values`` holds the chart's
    cached or literal points, index-aligned with ``None`` for gaps.
    """

    source_type: str
    formula: str | None
    values: tuple[CellValue, ...]
    cells: tuple[ChartDataCell, ...] = ()

    @property
    def is_cells(self) -> bool:
        return self.source_type == "cells"

    @property
    def is_literal(self) -> bool:
        return self.source_type == "literal"


class ChartSeriesData:
    """Data sources of one chart series.

    Assign a :class:`ChartDataCell`, a sequence of cells (one or many, contiguous
    or not), a literal value, or a sequence of literal values to ``name``,
    ``categories``, ``values``, ``x_values``, ``y_values`` or ``bubble_sizes``.
    Invalid assignments preserve the existing source.
    """

    def __init__(self, chart_data: EditableChartData, element: ET.Element, plot: str):
        object.__setattr__(self, "_chart_data", chart_data)
        object.__setattr__(self, "_element", element)
        object.__setattr__(self, "_plot", plot)

    @property
    def chart_type(self) -> str:
        """Local name of the plot holding the series, such as ``barChart``."""
        return self._plot

    @property
    def index(self) -> int:
        return int(self._element.find(f"{{{_C_NS}}}idx").get("val") or 0)  # type: ignore[union-attr]

    def __getattr__(self, name: str) -> ChartValueSource:
        role = _SERIES_ROLES.get(name)
        if role is None:
            raise AttributeError(name)
        return self._chart_data._read_source(self._element, self._role(role))

    def __setattr__(self, name: str, value: Any) -> None:
        role = _SERIES_ROLES.get(name)
        if role is None:
            raise AttributeError(f"series data has no settable {name!r}")
        self._chart_data._write_source(self._element, self._role(role), value)

    def _role(self, role: str) -> str:
        xy = self._plot in _XY_PLOTS
        if xy and role in {"cat", "val"}:
            raise AttributeError(f"{self._plot} series use x_values and y_values")
        if not xy and role in {"xVal", "yVal", "bubbleSize"}:
            raise AttributeError(f"{self._plot} series use categories and values")
        if role == "bubbleSize" and self._plot != "bubbleChart":
            raise AttributeError("only bubble series have bubble sizes")
        return role

    def __repr__(self) -> str:
        return f"ChartSeriesData(chart_type={self._plot!r}, index={self.index})"


class EditableChartData:
    """Data source, linked workbook and series sources of one chart part."""

    def __init__(self, package: ChartDataPackage, chart_part: str) -> None:
        self._package = package
        self._chart_part = chart_part
        self._source = package._read(chart_part)
        self._root, self._strict = _parse_part(self._source)
        self._rels_part = _rels_part(chart_part)
        self._rels_source = package._read_optional(self._rels_part)
        self._rels_root = ET.fromstring(self._rels_source or _EMPTY_RELATIONSHIPS)
        self._workbook: ChartDataWorkbook | None = None
        self._removed_parts: set[str] = set()
        self._dirty = False
        self._rels_dirty = False

    @property
    def chart_part(self) -> str:
        return self._chart_part

    @property
    def data_source_type(self) -> ChartDataSourceType:
        relationship = self._external_relationship()
        if relationship is None:
            return ChartDataSourceType.LITERAL
        if relationship.get("TargetMode") == "External":
            return ChartDataSourceType.EXTERNAL_WORKBOOK
        return ChartDataSourceType.EMBEDDED_WORKBOOK

    @property
    def workbook_part(self) -> str | None:
        """Package part of the embedded workbook, or ``None``."""
        if self.data_source_type is not ChartDataSourceType.EMBEDDED_WORKBOOK:
            return None
        relationship = self._external_relationship()
        assert relationship is not None
        return _resolve_part(self._chart_part, relationship.get("Target") or "")

    @property
    def external_workbook_target(self) -> str | None:
        """Raw relationship target of the linked workbook, or ``None``."""
        if self.data_source_type is not ChartDataSourceType.EXTERNAL_WORKBOOK:
            return None
        relationship = self._external_relationship()
        assert relationship is not None
        return relationship.get("Target") or ""

    @property
    def external_workbook_path(self) -> str | None:
        """File path of the linked workbook, read without opening the workbook."""
        target = self.external_workbook_target
        return None if target is None else _decode_external_target(target)

    def set_external_workbook(self, path: str | os.PathLike[str]) -> None:
        """Link the chart to the workbook at ``path`` without loading it.

        A linked chart is retargeted; an embedded workbook is detached and
        dropped from the package when nothing else uses it; a literal chart
        gains a link. Series formulas and caches are kept as they are. Retargeting
        discards a loaded external workbook; persist its bytes before retargeting.
        """
        target = _encode_external_target(path)
        relationship = self._external_relationship()
        if relationship is None:
            relationship = ET.SubElement(
                self._rels_root,
                f"{{{_REL_NS}}}Relationship",
                {"Id": _next_relationship_id(self._rels_root)},
            )
            external = ET.Element(
                f"{{{_C_NS}}}externalData",
                {f"{{{_DOC_REL_NS}}}id": relationship.get("Id") or ""},
            )
            ET.SubElement(external, f"{{{_C_NS}}}autoUpdate", {"val": "0"})
            _insert_before(self._root, external, _CHART_SPACE_FOLLOWERS)
            self._dirty = True
        elif relationship.get("TargetMode") != "External":
            embedded_part = self.workbook_part
            assert embedded_part is not None
            self._removed_parts.add(embedded_part)
        self._workbook = None
        relationship.set("Type", _profile_rel_type(_OLE_OBJECT_REL_TYPE, strict=self._strict))
        relationship.set("Target", target)
        relationship.set("TargetMode", "External")
        self._rels_dirty = True

    def load_external_workbook(self, payload: bytes) -> ChartDataWorkbook:
        """Edit explicitly supplied XLSX bytes for the current linked workbook.

        No relationship target is opened or fetched. Save workbook edits through
        ``workbook.to_bytes()`` separately; presentation save refreshes the chart
        caches while retaining the external link. Invalid loads preserve the
        currently loaded workbook and chart.
        """
        if self.data_source_type is not ChartDataSourceType.EXTERNAL_WORKBOOK:
            raise ValueError("chart must link to an external workbook before loading bytes")
        if not isinstance(payload, bytes):
            raise TypeError("external workbook payload must be bytes")
        workbook = ChartDataWorkbook(payload)
        self._workbook = workbook
        return workbook

    @property
    def workbook(self) -> ChartDataWorkbook:
        """The embedded workbook, or linked workbook loaded explicitly from bytes."""
        if self._workbook is None:
            source_type = self.data_source_type
            if source_type is not ChartDataSourceType.EMBEDDED_WORKBOOK:
                raise ValueError(
                    f"chart data source is {source_type.value}; "
                    "only embedded workbooks are editable as cells until external bytes "
                    "are loaded with load_external_workbook()"
                )
            part = self.workbook_part
            assert part is not None
            payload = self._package._read(part)
            if not payload.startswith(b"PK"):
                raise ValueError("embedded chart workbook is not an XLSX package")
            self._workbook = ChartDataWorkbook(payload)
        return self._workbook

    @property
    def series(self) -> list[ChartSeriesData]:
        plot_area = self._root.find(f"{{{_C_NS}}}chart/{{{_C_NS}}}plotArea")
        if plot_area is None:
            return []
        result = []
        for plot in plot_area:
            for element in plot.findall(f"{{{_C_NS}}}ser"):
                result.append(ChartSeriesData(self, element, _local(plot.tag)))
        return result

    @property
    def categories(self) -> ChartValueSource:
        """Categories of the first category series."""
        for series in self.series:
            if series.chart_type not in _XY_PLOTS:
                return series.categories
        raise AttributeError("chart has no category series")

    @categories.setter
    def categories(self, value: Any) -> None:
        targets = [item for item in self.series if item.chart_type not in _XY_PLOTS]
        if not targets:
            raise AttributeError("chart has no category series")
        replacement = self._prepare_source("cat", value)
        for series in targets:
            self._set_source(series._element, "cat", deepcopy(replacement))

    def refresh(self) -> None:
        """Recalculate the loaded workbook and rewrite every chart cache from it."""
        if self.data_source_type is ChartDataSourceType.LITERAL:
            return
        if self.data_source_type is ChartDataSourceType.EXTERNAL_WORKBOOK:
            if self._workbook is None:
                return
            workbook = self._workbook
        else:
            workbook = self.workbook
        workbook.calculate_formulas()
        for reference in self._root.iter():
            kind = _local(reference.tag)
            if kind not in {"strRef", "numRef", "multiLvlStrRef"}:
                continue
            formula = reference.findtext(f"{{{_C_NS}}}f")
            if not formula:
                continue
            try:
                areas = parse_chart_reference(formula)
                cells = workbook.cells(formula)
            except (KeyError, ValueError):
                continue
            _fill_reference_cache(reference, cells, areas, joined=False)
        for series in self.series:
            tx = series._element.find(f"{{{_C_NS}}}tx/{{{_C_NS}}}strRef")
            if tx is not None:
                with suppress(KeyError, ValueError):
                    cells = workbook.cells(tx.findtext(f"{{{_C_NS}}}f") or "")
                    _fill_reference_cache(tx, cells, [], joined=True)
        self._dirty = True

    def _external_relationship(self) -> ET.Element | None:
        external = self._root.find(f"{{{_C_NS}}}externalData")
        if external is None:
            return None
        relationship_id = external.get(f"{{{_DOC_REL_NS}}}id")
        for relationship in self._rels_root.findall(f"{{{_REL_NS}}}Relationship"):
            if relationship.get("Id") == relationship_id:
                return relationship
        raise ValueError("chart externalData relationship is unavailable")

    def _read_source(self, series: ET.Element, role: str) -> ChartValueSource:
        element = series.find(f"{{{_C_NS}}}{role}")
        if element is None or len(element) == 0:
            return ChartValueSource("none", None, ())
        content = element[0]
        kind = _local(content.tag)
        if kind == "v":
            return ChartValueSource("literal", None, (content.text or "",))
        if kind in {"strLit", "numLit"}:
            return ChartValueSource("literal", None, _cache_points(content))
        formula = content.findtext(f"{{{_C_NS}}}f")
        cache = next((child for child in content if _local(child.tag).endswith("Cache")), None)
        values: tuple[CellValue, ...] = ()
        if cache is not None:
            if _local(cache.tag) == "multiLvlStrCache":
                levels = cache.findall(f"{{{_C_NS}}}lvl")
                values = _cache_points(levels[0]) if levels else ()
                values = values + (None,) * (_point_count(cache) - len(values))
            else:
                values = _cache_points(cache)
        cells: tuple[ChartDataCell, ...] = ()
        if formula and (
            self.data_source_type is ChartDataSourceType.EMBEDDED_WORKBOOK
            or self._workbook is not None
        ):
            with suppress(KeyError, ValueError):
                cells = tuple(self.workbook.cells(formula))
        return ChartValueSource("cells", formula, values, cells)

    def _prepare_source(self, role: str, value: Any) -> ET.Element:
        cells, literals = _coerce_source(value)
        replacement = ET.Element(f"{{{_C_NS}}}{role}")
        if cells is not None:
            workbook = self.workbook
            if any(cell.worksheet.workbook is not workbook for cell in cells):
                raise ValueError("cells must belong to this chart's workbook")
            _write_cell_source(replacement, role, cells)
        else:
            _write_literal_source(replacement, role, literals)
        return replacement

    def _write_source(self, series: ET.Element, role: str, value: Any) -> None:
        self._set_source(series, role, self._prepare_source(role, value))

    def _set_source(self, series: ET.Element, role: str, replacement: ET.Element) -> None:
        element = series.find(f"{{{_C_NS}}}{role}")
        if element is None:
            element = ET.Element(f"{{{_C_NS}}}{role}")
            if role == "tx":
                position = sum(1 for child in series if _local(child.tag) in {"idx", "order"})
                series.insert(position, element)
            else:
                _insert_before(series, element, _ROLE_FOLLOWERS[role])
        for child in list(element):
            element.remove(child)
        element.extend(replacement)
        self._dirty = True

    def _replacements(self) -> dict[str, bytes]:
        replacements: dict[str, bytes] = {}
        if self._workbook is not None and (
            self._workbook.modified
            or self.data_source_type is ChartDataSourceType.EXTERNAL_WORKBOOK
        ):
            self.refresh()
            if self.data_source_type is ChartDataSourceType.EMBEDDED_WORKBOOK:
                part = self.workbook_part
                assert part is not None
                replacements[part] = self._workbook.to_bytes()
        if self._dirty:
            replacements[self._chart_part] = _serialize_part(
                self._root, self._source, strict=self._strict
            )
        if self._rels_dirty:
            replacements[self._rels_part] = serialize_xml_preserving_namespaces(
                self._rels_root, self._rels_source or _EMPTY_RELATIONSHIPS
            )
        return replacements


class ChartDataPackage:
    """Edit chart data sources of a presentation file, then :meth:`save` it.

    >>> package = ChartDataPackage("deck.pptx")
    >>> data = package.slide_chart_data(0)
    >>> data.workbook.get_cell(0, "B2", 42)
    >>> package.save("edited.pptx")
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        with ZipFile(self._path) as package:
            self._names = set(package.namelist())
        self._charts: dict[str, EditableChartData] = {}

    @property
    def chart_parts(self) -> list[str]:
        """Every chart part in the package, in natural order."""
        return sorted(
            (
                name
                for name in self._names
                if name.startswith("ppt/charts/") and name.count("/") == 2 and name.endswith(".xml")
            ),
            key=lambda name: [
                int(part) if part.isdigit() else part for part in re.split(r"([0-9]+)", name)
            ],
        )

    def chart_data(self, chart: Any) -> EditableChartData:
        """Return the editable data of a chart part name or a ``Chart`` facade."""
        part = getattr(getattr(chart, "part", None), "partname", chart)
        part = str(part).lstrip("/")
        if part not in self._names:
            raise KeyError(f"chart part {part!r} is not in the package")
        if part not in self._charts:
            self._charts[part] = EditableChartData(self, part)
        return self._charts[part]

    def slide_chart_data(self, slide_index: int, chart_index: int = 0) -> EditableChartData:
        """Return the ``chart_index``-th chart (document order) on a slide."""
        slide_part = self._slide_parts()[slide_index]
        relationships = {
            item.get("Id"): item
            for item in ET.fromstring(
                self._read_optional(_rels_part(slide_part)) or _EMPTY_RELATIONSHIPS
            )
        }
        charts = []
        for frame_chart in _parse_part(self._read(slide_part))[0].iter(f"{{{_C_NS}}}chart"):
            relationship = relationships.get(frame_chart.get(f"{{{_DOC_REL_NS}}}id"))
            if relationship is not None:
                charts.append(_resolve_part(slide_part, relationship.get("Target") or ""))
        return self.chart_data(charts[chart_index])

    def save(self, path: str | os.PathLike[str]) -> None:
        """Write the presentation with every chart data edit applied."""
        replacements: dict[str, bytes] = {}
        removals: set[str] = set()
        for chart in self._charts.values():
            replacements.update(chart._replacements())
            removals.update(chart._removed_parts)
        removals = {part for part in removals if not self._part_still_referenced(part)}
        if removals:
            content_types = self._read("[Content_Types].xml")
            root = ET.fromstring(content_types)
            for override in root.findall(f"{{{_CONTENT_TYPES_NS}}}Override"):
                if (override.get("PartName") or "").lstrip("/") in removals:
                    root.remove(override)
            replacements["[Content_Types].xml"] = serialize_xml_preserving_namespaces(
                root, content_types
            )
        copy_package_with_replacements(self._path, Path(path), replacements, removals)

    def _read(self, part: str) -> bytes:
        payload = self._read_optional(part)
        if payload is None:
            raise KeyError(f"package part {part!r} is unavailable")
        return payload

    def _read_optional(self, part: str) -> bytes | None:
        if part not in self._names:
            return None
        with ZipFile(self._path) as package:
            return package.read(part)

    def _slide_parts(self) -> list[str]:
        presentation = "ppt/presentation.xml"
        relationships = {
            item.get("Id"): item.get("Target") or ""
            for item in ET.fromstring(self._read(_rels_part(presentation)))
            if _rel_type(item) == _SLIDE_REL_TYPE
        }
        root = _parse_part(self._read(presentation))[0]
        return [
            _resolve_part(presentation, relationships[slide.get(f"{{{_DOC_REL_NS}}}id")])
            for slide in root.iterfind(f"{{{_P_NS}}}sldIdLst/{{{_P_NS}}}sldId")
            if slide.get(f"{{{_DOC_REL_NS}}}id") in relationships
        ]

    def _part_still_referenced(self, part: str) -> bool:
        for name in self._names:
            if not name.endswith(".rels"):
                continue
            source = _rels_source_part(name)
            chart = self._charts.get(source)
            root = chart._rels_root if chart is not None else ET.fromstring(self._read(name))
            for relationship in root:
                if relationship.get("TargetMode") == "External":
                    continue
                if _resolve_part(source, relationship.get("Target") or "") == part:
                    return True
        return False


def _rels_source_part(rels_part: str) -> str:
    directory, _, name = rels_part.rpartition("/")
    parent = directory.rpartition("/")[0] if directory.endswith("_rels") else directory
    if directory == "_rels":
        parent = ""
    source = name.removesuffix(".rels")
    return f"{parent}/{source}" if parent else source


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_part(payload: bytes) -> tuple[ET.Element, bool]:
    """Parse an XML part in Transitional form and report whether it was Strict."""
    root = ET.fromstring(payload)
    strict = _STRICT_MARKER in payload and _rename_namespaces(root, _TO_TRANSITIONAL)
    return root, strict


def _serialize_part(root: ET.Element, source: bytes, *, strict: bool) -> bytes:
    """Serialize a part parsed by :func:`_parse_part` in its original profile."""
    if not strict:
        return serialize_xml_preserving_namespaces(root, source)
    _rename_namespaces(root, _TO_STRICT)
    try:
        return serialize_xml_preserving_namespaces(root, source)
    finally:
        _rename_namespaces(root, _TO_TRANSITIONAL)


def _rename_namespaces(root: ET.Element, prefixes: dict[str, str]) -> bool:
    renamed = False
    for element in root.iter():
        if isinstance(element.tag, str):
            tag = _renamed(element.tag, prefixes)
            if tag != element.tag:
                element.tag = tag
                renamed = True
        if any(_renamed(name, prefixes) != name for name in element.attrib):
            items = [(_renamed(name, prefixes), value) for name, value in element.attrib.items()]
            element.attrib.clear()
            element.attrib.update(items)
            renamed = True
    return renamed


def _renamed(name: str, prefixes: dict[str, str]) -> str:
    if name.startswith("{"):
        end = name.find("}") + 1
        prefix = prefixes.get(name[:end])
        if prefix is not None:
            return prefix + name[end:]
    return name


def _rel_type(relationship: ET.Element) -> str | None:
    """Relationship type in Transitional form; Strict types use another base URI."""
    value = relationship.get("Type")
    if value is not None and value.startswith(f"{STRICT_R_NS}/"):
        return _DOC_REL_NS + value[len(STRICT_R_NS) :]
    return value


def _profile_rel_type(relationship_type: str, *, strict: bool) -> str:
    if strict and relationship_type.startswith(f"{_DOC_REL_NS}/"):
        return STRICT_R_NS + relationship_type[len(_DOC_REL_NS) :]
    return relationship_type


def _insert_before(parent: ET.Element, element: ET.Element, followers: set[str]) -> None:
    for index, child in enumerate(parent):
        if _local(child.tag) in followers:
            parent.insert(index, element)
            return
    parent.append(element)


def _next_relationship_id(root: ET.Element) -> str:
    used = {item.get("Id") for item in root}
    index = 1
    while f"rId{index}" in used:
        index += 1
    return f"rId{index}"


def _decode_external_target(target: str) -> str:
    if target[:5].lower() == "file:":
        rest = target[5:]
        if rest.startswith("///"):
            rest = rest[3:]
            decoded = unquote(rest)
            if re.match(r"[A-Za-z]:", decoded):
                return decoded.replace("/", "\\")
            return "/" + decoded
        if rest.startswith("//"):
            return "//" + unquote(rest[2:])
        return unquote(rest)
    return unquote(target)


def _encode_external_target(path: str | os.PathLike[str]) -> str:
    text = os.fspath(path)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("external workbook path must be a non-empty string")
    if re.match(r"[A-Za-z]:[\\/]", text):
        return "file:///" + quote(text.replace("\\", "/"), safe="/:")
    if text.startswith(("\\\\", "//")):
        return "file:" + quote(text.replace("\\", "/"), safe="/:")
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", text):
        return text
    if text.startswith("/"):
        return "file://" + quote(text, safe="/")
    return quote(text.replace("\\", "/"), safe="/")


def _coerce_source(value: Any) -> tuple[list[ChartDataCell] | None, list[Any]]:
    if isinstance(value, ChartValueSource):
        if value.is_cells:
            if not value.cells:
                raise ValueError("source cells are unavailable")
            return list(value.cells), []
        return None, list(value.values)
    if isinstance(value, ChartDataCell):
        return [value], []
    if isinstance(value, str | int | float | bool) or value is None:
        return None, [value]
    items = list(value)
    if not items:
        raise ValueError("a chart data source needs at least one cell or value")
    if all(isinstance(item, ChartDataCell) for item in items):
        return items, []
    if any(isinstance(item, ChartDataCell) for item in items):
        raise TypeError("chart data sources cannot mix cells and literal values")
    return None, items


def _cell_text(value: CellValue) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return _number_text(value)
    return str(value)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _write_cell_source(element: ET.Element, role: str, cells: list[ChartDataCell]) -> None:
    formula = chart_reference_for_cells(cells)
    areas = parse_chart_reference(formula)
    workbook = cells[0].worksheet.workbook
    # Preview pending calculations without writing caches: a later invalid
    # source cell must not change formulas or discard earlier workbook edits.
    evaluator = _FormulaEvaluator(workbook, strict=False) if workbook._needs_calculation else None
    values: list[CellValue] = []
    for cell in cells:
        value = _UNSUPPORTED
        if evaluator is not None:
            value = evaluator.cell_result(cell.worksheet, cell.row, cell.column)
        if value is _UNSUPPORTED:
            cell_element = cell.worksheet._cell_element(cell.row, cell.column, create=False)
            value = None if cell_element is None else workbook._element_value(cell_element)
        if _is_number(value):
            _finite_number(value, "chart source cell numbers must be finite")
        values.append(value)
    if role == "tx":
        kind = "strRef"
    elif role in {"val", "yVal", "bubbleSize"}:
        kind = "numRef"
    elif role == "cat" and len(areas) == 1 and _area_is_table(areas[0]):
        kind = "multiLvlStrRef"
    elif any(item is not None for item in values) and all(
        _is_number(item) or isinstance(item, date) for item in values if item is not None
    ):
        kind = "numRef"
    else:
        kind = "strRef"
    reference = ET.SubElement(element, f"{{{_C_NS}}}{kind}")
    ET.SubElement(reference, f"{{{_C_NS}}}f").text = formula
    _fill_reference_cache(reference, cells, areas, joined=role == "tx", values=values)


def _area_is_table(area: tuple[str | None, int, int, int, int]) -> bool:
    _sheet, row1, column1, row2, column2 = area
    return row2 > row1 and column2 > column1


def _fill_reference_cache(
    reference: ET.Element,
    cells: list[ChartDataCell],
    areas: list[tuple[str | None, int, int, int, int]],
    *,
    joined: bool,
    values: list[CellValue] | None = None,
) -> None:
    kind = _local(reference.tag)
    if values is None:
        values = [cell.value for cell in cells]
    for child in list(reference):
        if _local(child.tag).endswith("Cache"):
            reference.remove(child)
    if kind == "multiLvlStrRef":
        cache = _multi_level_cache(cells, areas, values)
    elif kind == "numRef":
        cache = _number_cache(cells, values)
    else:
        cache = ET.Element(f"{{{_C_NS}}}strCache")
        texts = [_cell_text(value) for value in values]
        if joined:
            texts = [" ".join(text for text in texts if text is not None)]
        ET.SubElement(cache, f"{{{_C_NS}}}ptCount", {"val": str(len(texts))})
        _append_points(cache, texts)
    reference.insert(1, cache)


def _number_cache(cells: list[ChartDataCell], values: list[CellValue]) -> ET.Element:
    cache = ET.Element(f"{{{_C_NS}}}numCache")
    numeric = [
        (
            cell,
            _excel_date_number(value, date1904=cell.worksheet.workbook._date1904)
            if isinstance(value, date)
            else value,
        )
        for cell, value in zip(cells, values, strict=True)
    ]
    formats = [cell.number_format for cell, value in numeric if _is_number(value)]
    series_format = formats[0] if formats else "General"
    ET.SubElement(cache, f"{{{_C_NS}}}formatCode").text = series_format
    ET.SubElement(cache, f"{{{_C_NS}}}ptCount", {"val": str(len(cells))})
    for index, (cell, value) in enumerate(numeric):
        if not _is_number(value):
            continue
        point = ET.SubElement(cache, f"{{{_C_NS}}}pt", {"idx": str(index)})
        if cell.number_format != series_format:
            point.set("formatCode", cell.number_format)
        ET.SubElement(point, f"{{{_C_NS}}}v").text = _number_text(float(value))
    return cache


def _multi_level_cache(
    cells: list[ChartDataCell],
    areas: list[tuple[str | None, int, int, int, int]],
    values: list[CellValue],
) -> ET.Element:
    _sheet, row1, column1, row2, column2 = areas[0]
    by_position = {
        (cell.row, cell.column): value for cell, value in zip(cells, values, strict=True)
    }
    down_rows = (row2 - row1) >= (column2 - column1)
    points = range(row1, row2 + 1) if down_rows else range(column1, column2 + 1)
    levels = range(column2, column1 - 1, -1) if down_rows else range(row2, row1 - 1, -1)
    cache = ET.Element(f"{{{_C_NS}}}multiLvlStrCache")
    ET.SubElement(cache, f"{{{_C_NS}}}ptCount", {"val": str(len(points))})
    for level in levels:
        level_element = ET.SubElement(cache, f"{{{_C_NS}}}lvl")
        texts = []
        for point in points:
            position = (point, level) if down_rows else (level, point)
            texts.append(_cell_text(by_position[position]))
        _append_points(level_element, texts)
    return cache


def _append_points(parent: ET.Element, texts: list[str | None]) -> None:
    for index, text in enumerate(texts):
        if text is None:
            continue
        point = ET.SubElement(parent, f"{{{_C_NS}}}pt", {"idx": str(index)})
        ET.SubElement(point, f"{{{_C_NS}}}v").text = text


def _write_literal_source(element: ET.Element, role: str, literals: list[Any]) -> None:
    if role == "tx":
        if len(literals) != 1 or not isinstance(literals[0], str):
            raise TypeError("a literal series name must be one string")
        ET.SubElement(element, f"{{{_C_NS}}}v").text = literals[0]
        return
    numeric = all(_is_number(item) for item in literals if item is not None)
    if role in {"val", "yVal", "bubbleSize"} and not numeric:
        raise TypeError("literal series values must be numbers or None")
    if numeric and any(item is not None for item in literals):
        numbers = [
            None if item is None else _finite_number(item, "literal chart values must be finite")
            for item in literals
        ]
        texts = [None if item is None else _number_text(item) for item in numbers]
        literal = ET.SubElement(element, f"{{{_C_NS}}}numLit")
        ET.SubElement(literal, f"{{{_C_NS}}}formatCode").text = "General"
    else:
        for item in literals:
            if _is_number(item):
                _finite_number(item, "literal chart values must be finite")
        literal = ET.SubElement(element, f"{{{_C_NS}}}strLit")
        texts = [_cell_text(item) for item in literals]
    ET.SubElement(literal, f"{{{_C_NS}}}ptCount", {"val": str(len(literals))})
    _append_points(literal, texts)


def _point_count(cache: ET.Element) -> int:
    count = cache.find(f"{{{_C_NS}}}ptCount")
    return int(count.get("val") or 0) if count is not None else 0


def _cache_points(cache: ET.Element) -> tuple[CellValue, ...]:
    numeric = _local(cache.tag) in {"numCache", "numLit"}
    points = {
        int(point.get("idx") or 0): point.findtext(f"{{{_C_NS}}}v")
        for point in cache.findall(f"{{{_C_NS}}}pt")
    }
    count = max(_point_count(cache), max(points, default=-1) + 1)
    values: list[CellValue] = []
    for index in range(count):
        text = points.get(index)
        if text is None:
            values.append(None)
        elif numeric:
            try:
                values.append(float(text))
            except ValueError:
                values.append(text)
        else:
            values.append(text)
    return tuple(values)
