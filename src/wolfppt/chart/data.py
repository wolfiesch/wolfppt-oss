"""Chart data containers importable like ``pptx.chart.data``.

These are the python-pptx construction objects: ``CategoryChartData`` with its
``Categories``/``Category`` hierarchy and ``CategorySeriesData`` points, plus the
XY and bubble equivalents. Pass them to ``shapes.add_chart`` or
``chart.replace_data``; WolfPPT builds the chart XML and the embedded workbook
in its own chart pipeline, so python-pptx's chart XML writer, workbook writer
and workbook range references (``categories_ref``, ``values_ref``,
``x_values_ref``, ``xlsx_blob`` ...) are not part of this module.
``BubbleChartData.bubble_sizes_ref`` is kept because it identifies bubble data.

For WolfPPT-specific workbook locales use :mod:`wolfppt.chart_data` instead.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import date, datetime
from numbers import Number
from typing import Any

__all__ = [
    "BubbleChartData",
    "BubbleDataPoint",
    "BubbleSeriesData",
    "Categories",
    "Category",
    "CategoryChartData",
    "CategoryDataPoint",
    "CategorySeriesData",
    "ChartData",
    "XyChartData",
    "XyDataPoint",
    "XySeriesData",
]

_DATE_FORMAT = r"yyyy\-mm\-dd"


class _BaseChartData(Sequence):
    """Ordered series of one chart, with the chart-wide default number format."""

    def __init__(self, number_format: Any = "General") -> None:
        self._number_format = number_format
        self._series: list[Any] = []

    def __getitem__(self, index):
        return self._series[index]

    def __len__(self) -> int:
        return len(self._series)

    def append(self, series: Any) -> None:
        self._series.append(series)

    @property
    def number_format(self) -> Any:
        """Default format of series values that set none of their own."""
        return self._number_format


class _BaseSeriesData(Sequence):
    """Ordered data points of one series."""

    def __init__(self, chart_data: Any, name: str | None, number_format: Any) -> None:
        self._chart_data = chart_data
        self._name = name
        self._number_format = number_format
        self._data_points: list[Any] = []

    def __getitem__(self, index):
        return self._data_points[index]

    def __len__(self) -> int:
        return len(self._data_points)

    def append(self, data_point: Any) -> None:
        self._data_points.append(data_point)

    @property
    def data_points(self) -> list[Any]:
        return list(self._data_points)

    @property
    def index(self) -> int:
        """Zero-based position of this series in its chart data."""
        return self._chart_data.index(self)

    @property
    def name(self) -> str:
        """Series name; an empty string when none was given."""
        return self._name or ""

    @property
    def number_format(self) -> Any:
        """Own format, else the chart data's format."""
        if self._number_format is None:
            return self._chart_data.number_format
        return self._number_format


class _BaseDataPoint:
    def __init__(self, series_data: Any, number_format: Any) -> None:
        self._series_data = series_data
        self._number_format = number_format

    @property
    def number_format(self) -> Any:
        """Own format, else the series format."""
        if self._number_format is None:
            return self._series_data.number_format
        return self._number_format


class CategoryChartData(_BaseChartData):
    """Data for category charts: bar, column, line, area, pie, doughnut and radar."""

    def __init__(self, number_format: Any = "General") -> None:
        super().__init__(number_format)
        self._categories: Categories | None = None

    def add_category(self, label: Any) -> Category:
        """Append a top-level category labelled *label* and return it."""
        return self.categories.add_category(label)

    def add_series(
        self, name: str | None, values: Iterable[Any] = (), number_format: Any = None
    ) -> CategorySeriesData:
        """Append a series named *name* holding *values*, one per category."""
        series = CategorySeriesData(self, name, number_format)
        self.append(series)
        for value in values:
            series.add_data_point(value)
        return series

    @property
    def categories(self) -> Categories:
        """The category hierarchy, created empty on first access."""
        if self._categories is None:
            self._categories = Categories()
        return self._categories

    @categories.setter
    def categories(self, category_labels: Iterable[Any]) -> None:
        categories = Categories()
        for label in category_labels:
            categories.add_category(label)
        self._categories = categories


class ChartData(CategoryChartData):
    """Deprecated python-pptx name for :class:`CategoryChartData`."""


class Categories(Sequence):
    """Top-level categories of a category chart; leaves are the plotted points."""

    def __init__(self) -> None:
        self._categories: list[Category] = []
        self._number_format: Any = None

    def __getitem__(self, index):
        return self._categories[index]

    def __len__(self) -> int:
        return len(self._categories)

    def add_category(self, label: Any) -> Category:
        category = Category(label, self)
        self._categories.append(category)
        return category

    @property
    def are_dates(self) -> bool:
        """True when single-level categories are labelled with dates."""
        if self.depth != 1:
            return False
        return isinstance(self._categories[0].label, (date, datetime))

    @property
    def are_numeric(self) -> bool:
        """True when the first category label is a number or a date."""
        if not self._categories:
            return False
        return isinstance(self._categories[0].label, (Number, date, datetime))

    @property
    def depth(self) -> int:
        """Number of category levels; 0 without categories."""
        if not self._categories:
            return 0
        depth = self._categories[0].depth
        if any(category.depth != depth for category in self._categories[1:]):
            raise ValueError("category depth not uniform")
        return depth

    def index(self, category: Category) -> int:
        """Offset of *category*'s first leaf among all leaves."""
        offset = 0
        for candidate in self._categories:
            if candidate is category:
                return offset
            offset += candidate.leaf_count
        raise ValueError("category not in top-level categories")

    @property
    def leaf_count(self) -> int:
        return sum(category.leaf_count for category in self._categories)

    @property
    def levels(self) -> Iterator[list[tuple[int, Any]]]:
        """``(idx, label)`` lists per level, leaf level first."""

        def walk(categories: list[Category]) -> Iterator[list[tuple[int, Any]]]:
            children = [child for category in categories for child in category.sub_categories]
            if children:
                yield from walk(children)
            yield [(category.idx, category.label) for category in categories]

        if self._categories:
            yield from walk(self._categories)

    @property
    def number_format(self) -> Any:
        """Category label format; a date format for single-level date labels."""
        if self._number_format is not None:
            return self._number_format
        return _DATE_FORMAT if self.depth == 1 and self.are_dates else "General"

    @number_format.setter
    def number_format(self, value: Any) -> None:
        self._number_format = value


class Category:
    """One category label, optionally parent of a nested category level."""

    def __init__(self, label: Any, parent: Categories | Category | None) -> None:
        self._label = label
        self._parent = parent
        self._sub_categories: list[Category] = []

    def add_sub_category(self, label: Any) -> Category:
        category = Category(label, self)
        self._sub_categories.append(category)
        return category

    @property
    def depth(self) -> int:
        """Levels at and below this category."""
        if not self._sub_categories:
            return 1
        depth = self._sub_categories[0].depth
        if any(child.depth != depth for child in self._sub_categories[1:]):
            raise ValueError("category depth not uniform")
        return depth + 1

    @property
    def idx(self) -> int:
        """Offset of this category's first leaf among all leaves."""
        return self._parent.index(self)

    def index(self, sub_category: Category) -> int:
        """Offset of *sub_category*'s first leaf among all leaves."""
        offset = self.idx
        for candidate in self._sub_categories:
            if candidate is sub_category:
                return offset
            offset += candidate.leaf_count
        raise ValueError("sub-category not in this category")

    @property
    def label(self) -> Any:
        """Label as given; an empty string when ``None``."""
        return "" if self._label is None else self._label

    @property
    def leaf_count(self) -> int:
        if not self._sub_categories:
            return 1
        return sum(child.leaf_count for child in self._sub_categories)

    def numeric_str_val(self, date_1904: bool = False) -> str:
        """Workbook text of the label; dates become an Excel serial such as ``42727.0``."""
        if isinstance(self._label, (date, datetime)):
            return f"{self._excel_date_number(date_1904):.1f}"
        return str(self._label)

    @property
    def sub_categories(self) -> list[Category]:
        return self._sub_categories

    def _excel_date_number(self, date_1904: bool) -> int:
        day = date(self._label.year, self._label.month, self._label.day)
        if date_1904:
            return (day - date(1904, 1, 1)).days
        serial = (day - date(1899, 12, 31)).days
        # Excel counts the nonexistent 1900-02-29 as day 60.
        return serial + 1 if serial > 59 else serial


class CategorySeriesData(_BaseSeriesData):
    """One named series of a :class:`CategoryChartData`."""

    def add_data_point(self, value: Any, number_format: Any = None) -> CategoryDataPoint:
        data_point = CategoryDataPoint(self, value, number_format)
        self.append(data_point)
        return data_point

    @property
    def categories(self) -> Categories:
        return self._chart_data.categories

    @property
    def values(self) -> list[Any]:
        """Point values in category order; ``None`` marks a missing point."""
        return [data_point.value for data_point in self._data_points]


class CategoryDataPoint(_BaseDataPoint):
    def __init__(self, series_data: Any, value: Any, number_format: Any) -> None:
        super().__init__(series_data, number_format)
        self._value = value

    @property
    def value(self) -> Any:
        return self._value


class XyChartData(_BaseChartData):
    """Data for XY (scatter) charts."""

    def add_series(self, name: str | None, number_format: Any = None) -> XySeriesData:
        series = XySeriesData(self, name, number_format)
        self.append(series)
        return series


class BubbleChartData(XyChartData):
    """Data for bubble charts: XY points with a bubble size."""

    def add_series(  # type: ignore[override]
        self, name: str | None, number_format: Any = None
    ) -> BubbleSeriesData:
        series = BubbleSeriesData(self, name, number_format)
        self.append(series)
        return series

    def bubble_sizes_ref(self, series: BubbleSeriesData) -> str:
        """Worksheet range of *series* bubble sizes in the embedded workbook.

        Series tables stack in column order A (x), B (y), C (size): a name row
        plus one row per point, with one spacer row between tables.
        """
        top_row = 2
        for candidate in self._series:
            if candidate is series:
                return f"Sheet1!$C${top_row}:$C${top_row + len(series) - 1}"
            top_row += len(candidate) + 2
        raise ValueError("series not in chart data object")


class XySeriesData(_BaseSeriesData):
    """One named series of x/y points."""

    def add_data_point(self, x: Any, y: Any, number_format: Any = None) -> XyDataPoint:
        data_point = XyDataPoint(self, x, y, number_format)
        self.append(data_point)
        return data_point

    @property
    def x_values(self) -> list[Any]:
        return [data_point.x for data_point in self._data_points]

    @property
    def y_values(self) -> list[Any]:
        return [data_point.y for data_point in self._data_points]


class BubbleSeriesData(XySeriesData):
    """One named series of x/y points with bubble sizes."""

    def add_data_point(  # type: ignore[override]
        self, x: Any, y: Any, size: Any, number_format: Any = None
    ) -> BubbleDataPoint:
        data_point = BubbleDataPoint(self, x, y, size, number_format)
        self.append(data_point)
        return data_point

    @property
    def bubble_sizes(self) -> list[Any]:
        return [data_point.bubble_size for data_point in self._data_points]


class XyDataPoint(_BaseDataPoint):
    def __init__(self, series_data: Any, x: Any, y: Any, number_format: Any) -> None:
        super().__init__(series_data, number_format)
        self._x = x
        self._y = y

    @property
    def x(self) -> Any:
        return self._x

    @property
    def y(self) -> Any:
        return self._y


class BubbleDataPoint(XyDataPoint):
    def __init__(self, series_data: Any, x: Any, y: Any, size: Any, number_format: Any) -> None:
        super().__init__(series_data, x, y, number_format)
        self._size = size

    @property
    def bubble_size(self) -> Any:
        return self._size
