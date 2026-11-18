"""Editable Office 2016+ ChartEx facade: point levels and series layout options.

Treemap, sunburst, histogram, Pareto, box-and-whisker, waterfall and funnel
charts live in a ``cx:chartSpace`` part instead of a classic ``c:chartSpace``.
:class:`ExtendedChart` edits the hierarchical category levels of their points
and the series layout properties (``cx:layoutPr``): the treemap/sunburst parent
label layout, the box-and-whisker quartile method and the histogram binning.
Edits keep an in-memory ``cx:chartSpace`` and are written at save through the
chart data-replace queue, together with the embedded workbook when the
category levels change.
"""

from __future__ import annotations

import math
import re
import zipfile
from collections.abc import Iterator, Sequence
from typing import Any
from xml.etree import ElementTree as ET

from .chart_axis_facade import ChartCategories, ChartCategoryLevels
from .chart_facade_helpers import normalize_choice as _normalize_choice
from .chart_financial import (
    BOX_WHISKER,
    CHARTEX_CHART_KINDS,
    CHARTEX_WATERFALL,
    FUNNEL,
    HISTOGRAM,
    PARETO,
    SUNBURST,
    TREEMAP,
)
from .chart_workbook import category_chart_workbook_blob
from .package_parts import rels_part_for_package_part, resolve_package_target

CX_NS = "http://schemas.microsoft.com/office/drawing/2014/chartex"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CX = f"{{{CX_NS}}}"

#: ``ST_ParentLabelLayout`` tokens of a treemap or sunburst series.
PARENT_LABEL_LAYOUTS = ("none", "banner", "overlapping")
#: ``ST_QuartileMethod`` tokens of a box-and-whisker series.
QUARTILE_METHODS = ("inclusive", "exclusive")
#: Histogram bin aggregation: automatic bins, one bin per category, a fixed bin
#: width or a fixed number of bins.
BIN_AGGREGATIONS = ("automatic", "by_category", "bin_width", "bin_count")
#: Which side of a histogram bin interval is closed (``ST_IntervalClosedSide``).
BIN_INTERVAL_CLOSED_TOKENS = {"left": "l", "right": "r"}

_LAYOUT_KINDS = {
    "treemap": TREEMAP,
    "sunburst": SUNBURST,
    "boxWhisker": BOX_WHISKER,
    "waterfall": CHARTEX_WATERFALL,
    "funnel": FUNNEL,
}
#: ``CT_SeriesLayoutProperties`` child order.
_LAYOUT_PROPERTY_ORDER = (
    "parentLabelLayout",
    "regionLabelLayout",
    "visibility",
    "aggregation",
    "binning",
    "geography",
    "statistics",
    "subtotals",
    "extLst",
)
#: ``CT_Series`` children that follow ``cx:layoutPr``.
_LAYOUT_PROPERTIES_SUCCESSORS = frozenset({f"{_CX}axisId", f"{_CX}extLst"})
_SHEET1_REFERENCE = re.compile(r"^Sheet1!\$[A-Z]{1,3}\$\d+(:\$[A-Z]{1,3}\$\d+)?$")


def extended_chart_for_shape(shape: Any) -> ExtendedChart | None:
    """Return the ChartEx facade of a chart frame, ``None`` for a classic chart."""
    part = _chartex_part(shape)
    return None if part is None else ExtendedChart(shape, part)


class ExtendedChart:
    """One Office 2016+ ChartEx chart part."""

    def __init__(self, shape: Any, part: str) -> None:
        self._shape = shape
        self._part = part

    @property
    def part_name(self) -> str:
        return self._part

    @property
    def kind(self) -> str:
        """The chart kind, named like :mod:`wolfppt.chart_financial` constants.

        Layouts without a constant (for example ``regionMap``) report their
        ``layoutId``.
        """
        layouts = [series.layout for series in self.series]
        if not layouts:
            raise ValueError("the extended chart has no series")
        if layouts[0] == "clusteredColumn":
            return PARETO if "paretoLine" in layouts else HISTOGRAM
        return _LAYOUT_KINDS.get(layouts[0], layouts[0])

    @property
    def series(self) -> ExtendedChartSeriesCollection:
        return ExtendedChartSeriesCollection(self)

    @property
    def categories(self) -> ExtendedChartCategories:
        """Category labels of the chart points with their per-level labels."""
        return ExtendedChartCategories(self)

    def _root(self) -> ET.Element:
        root = self._shape._payload.get("_chartex_root")
        if isinstance(root, ET.Element):
            return root
        with zipfile.ZipFile(self._shape._slide._presentation.path) as package:
            root = ET.fromstring(package.read(self._part))
        if root.tag != f"{_CX}chartSpace":
            raise ValueError(f"{self._part} is not a ChartEx chart part")
        self._shape._payload["_chartex_root"] = root
        return root

    def _series_elements(self) -> list[ET.Element]:
        return self._root().findall(f"{_CX}chart/{_CX}plotArea/{_CX}plotAreaRegion/{_CX}series")

    def _data_elements(self) -> dict[str, ET.Element]:
        return {
            str(data.get("id")): data for data in self._root().findall(f"{_CX}chartData/{_CX}data")
        }

    def _category_dimension(self) -> ET.Element | None:
        """The category ``cx:strDim`` of the first series' data.

        Office puts the categories and values in one ``cx:data``; wolfppt
        authoring stores the categories in their own ``cx:data``, so the first
        category dimension of the chart data is the fallback.
        """
        series = self._series_elements()
        data = self._data_elements()
        if series:
            data_id = series[0].find(f"{_CX}dataId")
            owner = None if data_id is None else data.get(str(data_id.get("val")))
            if owner is not None:
                dimension = owner.find(f"{_CX}strDim[@type='cat']")
                if dimension is not None:
                    return dimension
        return self._root().find(f"{_CX}chartData/{_CX}data/{_CX}strDim[@type='cat']")

    def _commit(self, workbook_blob: bytes | None = None) -> None:
        """Queue the in-memory part (and a rewritten workbook) for the next save."""
        payload = self._shape._payload
        if workbook_blob is not None:
            payload["_chartex_workbook"] = workbook_blob
        ET.register_namespace("cx", CX_NS)
        ET.register_namespace("r", R_NS)
        edit: dict[str, Any] = {
            "_chart_part": self._part,
            "_chart_xml": ET.tostring(self._root(), encoding="utf-8", xml_declaration=True),
        }
        if payload.get("_chartex_workbook") is not None:
            edit["xlsx_blob"] = payload["_chartex_workbook"]
        self._shape._slide._presentation._queue_chart_data_replace(
            self._shape._slide._index,
            self._shape._index,
            edit,
        )


class ExtendedChartSeriesCollection(Sequence["ExtendedChartSeries"]):
    def __init__(self, chart: ExtendedChart) -> None:
        self._chart = chart

    def __len__(self) -> int:
        return len(self._chart._series_elements())

    def __getitem__(self, index: int) -> ExtendedChartSeries:  # type: ignore[override]
        count = len(self)
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"series index must be an int, got {index!r}")
        if index < 0:
            index += count
        if not 0 <= index < count:
            raise IndexError("extended chart series index out of range")
        return ExtendedChartSeries(self._chart, index)

    def __iter__(self) -> Iterator[ExtendedChartSeries]:
        for index in range(len(self)):
            yield ExtendedChartSeries(self._chart, index)


class ExtendedChartSeries:
    """One ChartEx series and its layout properties (``cx:layoutPr``)."""

    def __init__(self, chart: ExtendedChart, index: int) -> None:
        self._chart = chart
        self._index = index

    @property
    def layout(self) -> str:
        """The series ``layoutId`` (``treemap``, ``clusteredColumn``, ...)."""
        return str(self._element().get("layoutId", ""))

    @property
    def name(self) -> str:
        return self._element().findtext(f"{_CX}tx/{_CX}txData/{_CX}v") or ""

    @property
    def values(self) -> list[float | None]:
        """The cached values of the series data, one per point."""
        dimension = self._value_dimension()
        if dimension is None:
            return []
        level = dimension.find(f"{_CX}lvl")
        if level is None:
            return []
        values: list[float | None] = [None] * _point_count(level)
        for index, text in _level_points(level):
            if index < len(values):
                values[index] = float(text)
        return values

    @property
    def points(self) -> ExtendedChartPoints:
        return ExtendedChartPoints(self)

    @property
    def parent_label_layout(self) -> str:
        """Treemap/sunburst parent labels: ``none``, ``banner`` or ``overlapping``."""
        self._require_layout("parent_label_layout", {"treemap", "sunburst"})
        element = self._layout_child("parentLabelLayout")
        return "overlapping" if element is None else element.get("val", "overlapping")

    @parent_label_layout.setter
    def parent_label_layout(self, value: Any) -> None:
        self._require_layout("parent_label_layout", {"treemap", "sunburst"})
        token = _normalize_choice(value, PARENT_LABEL_LAYOUTS, "parent_label_layout")
        self._ensure_layout_child("parentLabelLayout").set("val", token)
        self._chart._commit()

    @property
    def quartile_method(self) -> str:
        """Box-and-whisker quartile calculation: ``inclusive`` or ``exclusive``."""
        self._require_layout("quartile_method", {"boxWhisker"})
        element = self._layout_child("statistics")
        return "exclusive" if element is None else element.get("quartileMethod", "exclusive")

    @quartile_method.setter
    def quartile_method(self, value: Any) -> None:
        self._require_layout("quartile_method", {"boxWhisker"})
        token = _normalize_choice(value, QUARTILE_METHODS, "quartile_method")
        self._ensure_layout_child("statistics").set("quartileMethod", token)
        self._chart._commit()

    @property
    def bin_aggregation(self) -> str:
        """Histogram aggregation: ``automatic``, ``by_category``, ``bin_width``
        or ``bin_count``."""
        self._require_histogram("bin_aggregation")
        if self._layout_child("aggregation") is not None:
            return "by_category"
        binning = self._layout_child("binning")
        if binning is not None:
            if binning.find(f"{_CX}binSize") is not None:
                return "bin_width"
            if binning.find(f"{_CX}binCount") is not None:
                return "bin_count"
        return "automatic"

    @bin_aggregation.setter
    def bin_aggregation(self, value: Any) -> None:
        self._require_histogram("bin_aggregation")
        token = _normalize_choice(value, BIN_AGGREGATIONS, "bin_aggregation")
        if token in {"bin_width", "bin_count"}:
            if self.bin_aggregation != token:
                raise ValueError(f"assign {token} to aggregate by {token}")
            return
        self._remove_layout_child("aggregation")
        self._remove_layout_child("binning")
        if token == "by_category":
            self._ensure_layout_child("aggregation")
        self._chart._commit()

    @property
    def bin_width(self) -> float | None:
        """The fixed histogram bin width, ``None`` unless aggregating by width."""
        self._require_histogram("bin_width")
        binning = self._layout_child("binning")
        text = None if binning is None else binning.findtext(f"{_CX}binSize")
        return None if text is None else float(text)

    @bin_width.setter
    def bin_width(self, value: Any) -> None:
        self._require_histogram("bin_width")
        width = _positive_number(value, "bin_width")
        self._remove_layout_child("aggregation")
        self._set_bin_size_child("binSize", _number_text(width))
        self._chart._commit()

    @property
    def bin_count(self) -> int | None:
        """The fixed number of histogram bins, ``None`` unless aggregating by count."""
        self._require_histogram("bin_count")
        binning = self._layout_child("binning")
        text = None if binning is None else binning.findtext(f"{_CX}binCount")
        return None if text is None else int(text)

    @bin_count.setter
    def bin_count(self, value: Any) -> None:
        self._require_histogram("bin_count")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"bin_count must be a positive int, got {value!r}")
        self._remove_layout_child("aggregation")
        self._set_bin_size_child("binCount", str(value))
        self._chart._commit()

    @property
    def overflow_bin(self) -> float | str | None:
        """Overflow bin threshold: a number, ``"auto"`` or ``None`` (no bin)."""
        return self._bin_limit("overflow")

    @overflow_bin.setter
    def overflow_bin(self, value: Any) -> None:
        self._set_bin_limit("overflow", value)

    @property
    def underflow_bin(self) -> float | str | None:
        """Underflow bin threshold: a number, ``"auto"`` or ``None`` (no bin)."""
        return self._bin_limit("underflow")

    @underflow_bin.setter
    def underflow_bin(self, value: Any) -> None:
        self._set_bin_limit("underflow", value)

    @property
    def bin_interval_closed(self) -> str:
        """Closed side of each bin interval: ``right`` (default) or ``left``."""
        self._require_histogram("bin_interval_closed")
        binning = self._layout_child("binning")
        token = "r" if binning is None else binning.get("intervalClosed", "r")
        return "left" if token == "l" else "right"

    @bin_interval_closed.setter
    def bin_interval_closed(self, value: Any) -> None:
        self._require_histogram("bin_interval_closed")
        side = _normalize_choice(value, tuple(BIN_INTERVAL_CLOSED_TOKENS), "bin_interval_closed")
        self._binning_for_edit("bin_interval_closed").set(
            "intervalClosed", BIN_INTERVAL_CLOSED_TOKENS[side]
        )
        self._chart._commit()

    def _element(self) -> ET.Element:
        elements = self._chart._series_elements()
        if self._index >= len(elements):
            raise IndexError("extended chart series index out of range")
        return elements[self._index]

    def _value_dimension(self) -> ET.Element | None:
        data_id = self._element().find(f"{_CX}dataId")
        data = (
            None if data_id is None else self._chart._data_elements().get(str(data_id.get("val")))
        )
        return None if data is None else data.find(f"{_CX}numDim")

    def _require_layout(self, name: str, layouts: set[str]) -> None:
        if self.layout not in layouts:
            raise AttributeError(f"{name} is not available on a {self.layout or 'unknown'} series")

    def _require_histogram(self, name: str) -> None:
        self._require_layout(name, {"clusteredColumn"})

    def _layout_properties(self, *, create: bool = False) -> ET.Element | None:
        series = self._element()
        properties = series.find(f"{_CX}layoutPr")
        if properties is None and create:
            properties = ET.Element(f"{_CX}layoutPr")
            insert_at = len(series)
            for index, child in enumerate(list(series)):
                if child.tag in _LAYOUT_PROPERTIES_SUCCESSORS:
                    insert_at = index
                    break
            series.insert(insert_at, properties)
        return properties

    def _layout_child(self, local_name: str) -> ET.Element | None:
        properties = self._layout_properties()
        return None if properties is None else properties.find(f"{_CX}{local_name}")

    def _ensure_layout_child(self, local_name: str) -> ET.Element:
        properties = self._layout_properties(create=True)
        assert properties is not None
        child = properties.find(f"{_CX}{local_name}")
        if child is not None:
            return child
        child = ET.Element(f"{_CX}{local_name}")
        rank = _LAYOUT_PROPERTY_ORDER.index(local_name)
        insert_at = len(properties)
        for index, existing in enumerate(list(properties)):
            existing_name = existing.tag.rsplit("}", 1)[-1]
            if (
                existing_name in _LAYOUT_PROPERTY_ORDER
                and _LAYOUT_PROPERTY_ORDER.index(existing_name) > rank
            ):
                insert_at = index
                break
        properties.insert(insert_at, child)
        return child

    def _remove_layout_child(self, local_name: str) -> None:
        properties = self._layout_properties()
        child = None if properties is None else properties.find(f"{_CX}{local_name}")
        if properties is not None and child is not None:
            properties.remove(child)

    def _set_bin_size_child(self, local_name: str | None, text: str | None) -> None:
        """Replace the ``cx:binSize``/``cx:binCount`` choice of ``cx:binning``."""
        binning = self._ensure_layout_child("binning")
        for name in ("binSize", "binCount"):
            child = binning.find(f"{_CX}{name}")
            if child is not None:
                binning.remove(child)
        if local_name is not None:
            ET.SubElement(binning, f"{_CX}{local_name}").text = text

    def _binning_for_edit(self, name: str) -> ET.Element:
        binning = self._layout_child("binning")
        if binning is None:
            mode = (
                "aggregates by category"
                if self._layout_child("aggregation") is not None
                else "uses automatic bins; set bin_width or bin_count first"
            )
            raise ValueError(f"{name} applies to binned histograms; the series {mode}")
        return binning

    def _bin_limit(self, attribute: str) -> float | str | None:
        self._require_histogram(f"{attribute}_bin")
        binning = self._layout_child("binning")
        raw = None if binning is None else binning.get(attribute)
        if raw is None:
            return None
        return "auto" if raw == "auto" else float(raw)

    def _set_bin_limit(self, attribute: str, value: Any) -> None:
        name = f"{attribute}_bin"
        self._require_histogram(name)
        binning = self._binning_for_edit(name)
        if value is None:
            binning.attrib.pop(attribute, None)
        elif isinstance(value, str) and value.strip().lower() in {"auto", "automatic"}:
            binning.set(attribute, "auto")
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number, 'auto' or None, got {value!r}")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite, got {value!r}")
            binning.set(attribute, _number_text(float(value)))
        self._chart._commit()


class ExtendedChartPoints(Sequence["ExtendedChartPoint"]):
    def __init__(self, series: ExtendedChartSeries) -> None:
        self._series = series

    def __len__(self) -> int:
        return len(self._series.values)

    def __getitem__(self, index: int) -> ExtendedChartPoint:  # type: ignore[override]
        count = len(self)
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"point index must be an int, got {index!r}")
        if index < 0:
            index += count
        if not 0 <= index < count:
            raise IndexError("extended chart point index out of range")
        return ExtendedChartPoint(self._series, index)

    def __iter__(self) -> Iterator[ExtendedChartPoint]:
        for index in range(len(self)):
            yield ExtendedChartPoint(self._series, index)


class ExtendedChartPoint:
    """One ChartEx data point.

    ``levels`` edits the point's hierarchy labels (level 0 is the point's own
    category label).  The parent label layout, quartile method and bin
    aggregation are stored once per series, so assigning them through a point
    changes every point of its series.
    """

    def __init__(self, series: ExtendedChartSeries, index: int) -> None:
        self._series = series
        self._index = index

    @property
    def index(self) -> int:
        return self._index

    @property
    def series(self) -> ExtendedChartSeries:
        return self._series

    @property
    def value(self) -> float | None:
        return self._series.values[self._index]

    @property
    def label(self) -> str:
        return self.levels[0]

    @property
    def levels(self) -> ChartCategoryLevels:
        """The point's per-level labels: ``[0]`` its label, ``[1]`` its parent."""
        return ChartCategoryLevels(self._series._chart.categories, self._index)

    @property
    def parent_label_layout(self) -> str:
        return self._series.parent_label_layout

    @parent_label_layout.setter
    def parent_label_layout(self, value: Any) -> None:
        self._series.parent_label_layout = value

    @property
    def quartile_method(self) -> str:
        return self._series.quartile_method

    @quartile_method.setter
    def quartile_method(self, value: Any) -> None:
        self._series.quartile_method = value

    @property
    def bin_aggregation(self) -> str:
        return self._series.bin_aggregation

    @bin_aggregation.setter
    def bin_aggregation(self, value: Any) -> None:
        self._series.bin_aggregation = value


class ExtendedChartCategories(ChartCategories):
    """Point category labels of a ChartEx chart with their hierarchy levels.

    Level 0 is a point's own label and higher levels are its parents, as in
    the classic category levels manager.  Every level lists a label for each
    point.  Level edits rewrite the category cache, the data formulas and the
    embedded workbook, so the chart data stays editable in the host application.
    """

    def __init__(self, chart: ExtendedChart) -> None:
        self._chart = chart

    def _paths(self) -> list[list[str]]:
        dimension = self._chart._category_dimension()
        if dimension is None:
            return []
        levels = dimension.findall(f"{_CX}lvl")
        if not levels:
            return []
        count = max(_point_count(level) for level in levels)
        depth = len(levels)
        paths = [[""] * depth for _ in range(count)]
        for position, level in enumerate(levels):
            column = depth - 1 - position
            for index, text in _level_points(level):
                if index < count:
                    paths[index][column] = text
        return paths

    def _write(self, paths: list[list[str]]) -> None:
        chart = self._chart
        dimension = chart._category_dimension()
        if dimension is None or not paths:
            raise ValueError("the extended chart has no categories")
        count = len(paths)
        depth = len(paths[0])
        numeric = _numeric_dimensions(chart)
        workbook_series: list[dict[str, Any]] = []
        for data_id, numeric_dimension in numeric:
            level = numeric_dimension.find(f"{_CX}lvl")
            values: list[float | None] = [None] * count
            if level is not None:
                for index, text in _level_points(level):
                    if index < count:
                        values[index] = float(text)
            if any(value is None for value in values):
                raise ValueError(
                    "category levels cannot be rewritten while a series has blank values"
                )
            workbook_series.append(
                {
                    "name": _data_series_name(chart, data_id, len(workbook_series)),
                    "values": values,
                }
            )
        _require_sheet1_references(chart, dimension, numeric)
        for level in dimension.findall(f"{_CX}lvl"):
            dimension.remove(level)
        insert_at = len(dimension)
        for index, child in enumerate(list(dimension)):
            if child.tag == f"{_CX}extLst":
                insert_at = index
                break
        for position in range(depth):
            column = depth - 1 - position
            level = ET.Element(f"{_CX}lvl", {"ptCount": str(count)})
            for index, path in enumerate(paths):
                if path[column]:
                    ET.SubElement(level, f"{_CX}pt", {"idx": str(index)}).text = path[column]
            dimension.insert(insert_at + position, level)
        _set_formula(dimension, f"Sheet1!$A$2:${_column_name(depth)}${count + 1}")
        for offset, (data_id, numeric_dimension) in enumerate(numeric):
            column = _column_name(depth + offset + 1)
            _set_formula(numeric_dimension, f"Sheet1!${column}$2:${column}${count + 1}")
            for series in chart._series_elements():
                series_data = series.find(f"{_CX}dataId")
                formula = series.find(f"{_CX}tx/{_CX}txData/{_CX}f")
                if (
                    series_data is not None
                    and str(series_data.get("val")) == data_id
                    and formula is not None
                ):
                    formula.text = f"Sheet1!${column}$1"
        leaves = [path[-1] for path in paths]
        workbook = category_chart_workbook_blob(
            leaves,
            workbook_series,
            category_hierarchy=[list(path) for path in paths] if depth > 1 else None,
        )
        chart._commit(workbook)


def _chartex_part(shape: Any) -> str | None:
    payload = shape._payload
    cached = payload.get("_chartex_part")
    if cached is not None:
        return cached or None
    relationship_ids = {str(rel_id) for rel_id in payload.get("relationship_ids") or [] if rel_id}
    if not relationship_ids:
        chart_payload = payload.get("_chart_payload")
        chart_type = chart_payload.get("chart_type") if isinstance(chart_payload, dict) else None
        kind = chart_type.get("kind") if isinstance(chart_type, dict) else None
        if payload.get("_pending_shape") and kind in CHARTEX_CHART_KINDS:
            raise ValueError("save the presentation before editing a newly added extended chart")
        return None
    slide_part = str(shape._slide.partname)
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        try:
            rels = ET.fromstring(package.read(rels_part_for_package_part(slide_part)))
        except KeyError:
            rels = None
    part = ""
    if rels is not None:
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship"):
            if rel.get("Id") in relationship_ids and rel.get("Type", "").endswith("/chartEx"):
                part = resolve_package_target(slide_part, rel.get("Target", ""))
                break
    payload["_chartex_part"] = part
    return part or None


def _numeric_dimensions(chart: ExtendedChart) -> list[tuple[str, ET.Element]]:
    """The value dimensions referenced by the series, in first-use order."""
    data = chart._data_elements()
    result: list[tuple[str, ET.Element]] = []
    seen: set[str] = set()
    for series in chart._series_elements():
        data_id = series.find(f"{_CX}dataId")
        key = None if data_id is None else str(data_id.get("val"))
        if key is None or key in seen or key not in data:
            continue
        dimension = data[key].find(f"{_CX}numDim")
        if dimension is not None:
            seen.add(key)
            result.append((key, dimension))
    return result


def _data_series_name(chart: ExtendedChart, data_id: str, position: int) -> str:
    for series in chart._series_elements():
        series_data = series.find(f"{_CX}dataId")
        if series_data is not None and str(series_data.get("val")) == data_id:
            name = series.findtext(f"{_CX}tx/{_CX}txData/{_CX}v")
            if name:
                return name
    return f"Series {position + 1}"


def _require_sheet1_references(
    chart: ExtendedChart,
    category_dimension: ET.Element,
    numeric: list[tuple[str, ET.Element]],
) -> None:
    """Refuse level edits whose data formulas the rebuilt workbook cannot honour."""
    dimensions = [category_dimension, *(dimension for _, dimension in numeric)]
    formulas = [dimension.findtext(f"{_CX}f") for dimension in dimensions]
    formulas.extend(
        series.findtext(f"{_CX}tx/{_CX}txData/{_CX}f") for series in chart._series_elements()
    )
    for formula in formulas:
        if formula is not None and not _SHEET1_REFERENCE.match(formula.strip()):
            raise ValueError(
                "category levels can be rewritten only when the chart data uses "
                f"direct Sheet1 references, found {formula!r}"
            )


def _set_formula(dimension: ET.Element, text: str) -> None:
    formula = dimension.find(f"{_CX}f")
    if formula is None:
        formula = ET.Element(f"{_CX}f")
        dimension.insert(0, formula)
    formula.text = text


def _level_points(level: ET.Element) -> list[tuple[int, str]]:
    points: list[tuple[int, str]] = []
    for point in level.findall(f"{_CX}pt"):
        raw_index = point.get("idx", "")
        if raw_index.isdigit():
            points.append((int(raw_index), point.text or ""))
    return sorted(points)


def _point_count(level: ET.Element) -> int:
    raw = level.get("ptCount", "")
    if raw.isdigit():
        return int(raw)
    return max((index for index, _ in _level_points(level)), default=-1) + 1


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def _number_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a positive number, got {value!r}")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be a positive finite number, got {value!r}")
    return number
