"""Editable financial chart authoring on the classic DrawingML chart machinery.

This module authors *real, editable* chart parts. Every output is a normal
OOXML chart part plus its embedded workbook, so PowerPoint, Excel, and
python-pptx keep showing the chart as an editable chart rather than a picture.

Two financial workflows are implemented:

``COMBO_COLUMN_LINE`` (plus stacked/100% column variants)
    A single ``c:plotArea`` holding a ``c:barChart`` plot bound to the primary
    value axis (``axPos="l"``) and a ``c:lineChart`` plot bound to a distinct
    secondary value axis (``axPos="r"``).  Both plots share one category axis.

``WATERFALL``
    A signed bridge rendered as a ``c:barChart`` with ``grouping="stacked"``
    and three explicit series roles: a hidden ``Base`` offset series, an
    ``Increase`` series holding the upward segment, and a ``Decrease`` series
    holding the downward segment.  Bars above zero, below zero, and crossing
    zero all resolve to a signed hidden offset plus one or both signed
    segments, and the increase/decrease/total roles carry distinct solid fills
    applied per data point.  Explicit total markers are authored as
    ``None`` phases that draw the running total at that category.

Representation boundary: this is an *editable OOXML stacked-bar bridge*, not
Microsoft's chartEx ``waterfall`` part type.  It is authored entirely from the
classic ``c:`` chart namespace, so PowerPoint and Excel reopen it as a normal
editable stacked chart with an embedded workbook.  No chartEx parity and no
PowerPoint layout parity is claimed; the marker extension records the exact
representation (``stacked-bar-bridge``) on the chart part.  Microsoft's chartEx
waterfall part type is *not* authored and is listed in
:data:`UNSUPPORTED_FINANCIAL_CHART_TYPES`.

The classic representation is deliberate: this repository's chart facade,
chart XML helpers, axis primitives, and reporting refresh gates all operate on
the ``c:`` chart namespace.

Publication contract: authoring and refreshing both bind the input deck to a
private snapshot, stage the edited package in a private directory beside the
destination, re-check the deck's digest, and publish atomically without
clobbering.  The input deck is never written, an existing or symlinked
destination is refused, and a failed run leaves the destination absent.
Publication is a hard link, so a destination filesystem that cannot hard-link is
refused rather than publishing a partially written deck.  Receipt
``source_sha256``/``output_sha256`` are raw file digests, so they can be compared
against the files on disk.
"""

from __future__ import annotations

import hashlib
import math
import os
import posixpath
import tempfile
import zipfile
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .chart_adds import (
    _FINANCIAL_TEMPLATE_NAME_TO_ID,
    A_NS,
    R_NS,
    _build_chart_template,
)
from .chart_axis_ids import chart_axis_ids_as_openxml_int32
from .chart_axis_xml import axis_title_element as _axis_title_element
from .chart_data_label_text_xml import set_chart_data_label_text
from .chart_point_xml import (
    _chart_point_data_label_element,
    _chart_series_data_labels_element,
    _set_chart_data_label_bool_child,
    set_chart_point_format_properties,
    set_chart_series_format_properties,
)
from .chart_title_text_xml import ensure_title_layout, set_title_text
from .chart_workbook import category_chart_workbook_blob
from .chart_xml import (
    _category_formula,
    _excel_column_name,
    _replace_chart_cache,
    _replace_chart_categories,
    _set_chart_series_identity,
)
from .chart_xml_utils import C_NS
from .chart_xml_utils import xml_local_name as _xml_local_name

COMBO_COLUMN_LINE = "COMBO_COLUMN_LINE"
COMBO_COLUMN_STACKED_LINE = "COMBO_COLUMN_STACKED_LINE"
COMBO_COLUMN_STACKED_100_LINE = "COMBO_COLUMN_STACKED_100_LINE"
WATERFALL = "WATERFALL"
TREEMAP = "TREEMAP"
SUNBURST = "SUNBURST"
CHARTEX_WATERFALL = "CHARTEX_WATERFALL"
FUNNEL = "FUNNEL"
BOX_WHISKER = "BOX_WHISKER"
HISTOGRAM = "HISTOGRAM"
PARETO = "PARETO"

CHARTEX_CHART_KINDS = (
    TREEMAP,
    SUNBURST,
    CHARTEX_WATERFALL,
    FUNNEL,
    BOX_WHISKER,
    HISTOGRAM,
    PARETO,
)

#: The concrete representation each kind authors, recorded in the receipt and
#: in the chart-part marker so a caller can tell exactly what was built.
FINANCIAL_CHART_REPRESENTATIONS = {
    COMBO_COLUMN_LINE: "bar-plot+line-plot-secondary-axis",
    COMBO_COLUMN_STACKED_LINE: "bar-plot-stacked+line-plot-secondary-axis",
    COMBO_COLUMN_STACKED_100_LINE: "bar-plot-percentStacked+line-plot-secondary-axis",
    WATERFALL: "stacked-bar-bridge",
    TREEMAP: "chartex-treemap",
    SUNBURST: "chartex-sunburst",
    CHARTEX_WATERFALL: "chartex-waterfall",
    FUNNEL: "chartex-funnel",
    BOX_WHISKER: "chartex-boxWhisker",
    HISTOGRAM: "chartex-histogram",
    PARETO: "chartex-pareto",
}

#: Default chart frame in EMU when a caller does not supply one.
DEFAULT_CHART_FRAME = {
    "x": 914400,
    "y": 914400,
    "cx": 5486400,
    "cy": 3200400,
}

FINANCIAL_CHART_KINDS = (
    COMBO_COLUMN_LINE,
    COMBO_COLUMN_STACKED_LINE,
    COMBO_COLUMN_STACKED_100_LINE,
    WATERFALL,
    *CHARTEX_CHART_KINDS,
)

#: Chart families a caller may reasonably ask for but that this module refuses
#: to author, with the exact reason returned to the caller.
UNSUPPORTED_FINANCIAL_CHART_TYPES: dict[str, str] = {
    "STOCK_HLCO": (
        "stock/high-low-close charts are not authored; no first-party template "
        "or series machinery exists for c:stockChart in this repository"
    ),
    "CANDLE": (
        "candlestick charts require c:stockChart with c:upDownBars tuning and "
        "are not authored"
    ),
    "SURFACE": "c:surfaceChart is not authored",
}

CHARTEX_NS = "http://schemas.microsoft.com/office/drawing/2014/chartex"

_FINANCIAL_EXT_NS = "urn:wolfppt:financial-chart"
_FINANCIAL_EXT_URI = "{7C9F4E2A-1D62-4B0C-9F0A-1C7E4B8D2A33}"
_FINANCIAL_EXT_TAG = f"{{{_FINANCIAL_EXT_NS}}}financialChart"

_COMBO_KIND_BY_GROUPING = {
    "clustered": COMBO_COLUMN_LINE,
    "stacked": COMBO_COLUMN_STACKED_LINE,
    "percentStacked": COMBO_COLUMN_STACKED_100_LINE,
}
_COMBO_COLUMN_TEMPLATE_ID = {
    grouping: _FINANCIAL_TEMPLATE_NAME_TO_ID[kind]
    for grouping, kind in _COMBO_KIND_BY_GROUPING.items()
}

_WATERFALL_SERIES_NAMES = ("Base", "Increase", "Decrease")
_DEFAULT_INCREASE_RGB = "2E7D32"
_DEFAULT_DECREASE_RGB = "C62828"
_DEFAULT_TOTAL_RGB = "1F4E79"
_DEFAULT_COLUMN_RGB = "1F4E79"
_DEFAULT_LINE_RGB = "C55A11"

_PARENT_CHILD_ORDER: dict[str, tuple[str, ...]] = {
    "chart": (
        "title",
        "autoTitleDeleted",
        "pivotFmts",
        "view3D",
        "floor",
        "sideWall",
        "backWall",
        "plotArea",
        "legend",
        "plotVisOnly",
        "dispBlanksAs",
        "showDLblsOverMax",
        "extLst",
    ),
    "catAx": (
        "axId",
        "scaling",
        "delete",
        "axPos",
        "majorGridlines",
        "minorGridlines",
        "title",
        "numFmt",
        "majorTickMark",
        "minorTickMark",
        "tickLblPos",
        "spPr",
        "txPr",
        "crossAx",
        "crosses",
        "crossesAt",
        "auto",
        "lblAlgn",
        "lblOffset",
        "tickLblSkip",
        "tickMarkSkip",
        "noMultiLvlLbl",
        "extLst",
    ),
    "valAx": (
        "axId",
        "scaling",
        "delete",
        "axPos",
        "majorGridlines",
        "minorGridlines",
        "title",
        "numFmt",
        "majorTickMark",
        "minorTickMark",
        "tickLblPos",
        "spPr",
        "txPr",
        "crossAx",
        "crosses",
        "crossesAt",
        "crossBetween",
        "majorUnit",
        "minorUnit",
        "dispUnits",
        "extLst",
    ),
}


class FinancialChartRefusal(ValueError):
    """Raised when a requested financial chart cannot be authored as asked."""


@dataclass(frozen=True)
class ChartSeriesSpec:
    """One authored series of a combination chart.

    ``plot`` binds the series to the ``"column"`` (primary axis) or ``"line"``
    (secondary axis) plot of the authored ``c:plotArea``.
    """

    name: str
    values: tuple[float, ...]
    plot: str = "column"
    fill_rgb: str | None = None
    line_rgb: str | None = None
    marker_symbol: str | None = None

    def __post_init__(self) -> None:
        if self.plot not in {"column", "line"}:
            raise FinancialChartRefusal(
                f"combination chart series plot must be 'column' or 'line', "
                f"got {self.plot!r}"
            )
        if not self.name:
            raise FinancialChartRefusal("combination chart series need a name")
        if not self.values:
            raise FinancialChartRefusal(
                f"combination chart series {self.name!r} has no values"
            )


@dataclass(frozen=True)
class ComboChartSpec:
    """A column+line combination chart with secondary-axis line ownership."""

    categories: tuple[str, ...]
    series: tuple[ChartSeriesSpec, ...]
    column_grouping: str = "clustered"
    title: str | None = None
    legend: bool = True
    value_axis_title: str | None = None
    secondary_axis_title: str | None = None
    line_marker_symbol: str = "circle"
    line_smooth: bool = False

    def __post_init__(self) -> None:
        if self.column_grouping not in _COMBO_COLUMN_TEMPLATE_ID:
            raise FinancialChartRefusal(
                "combination chart column_grouping must be 'clustered', "
                f"'stacked', or 'percentStacked', got {self.column_grouping!r}"
            )
        if not self.categories:
            raise FinancialChartRefusal("combination chart needs categories")
        if not self.series:
            raise FinancialChartRefusal("combination chart needs at least one series")
        if not any(item.plot == "column" for item in self.series):
            raise FinancialChartRefusal(
                "combination chart needs at least one 'column' series"
            )
        if not any(item.plot == "line" for item in self.series):
            raise FinancialChartRefusal(
                "combination chart needs at least one 'line' series"
            )
        for item in self.series:
            if len(item.values) != len(self.categories):
                raise FinancialChartRefusal(
                    f"combination chart series {item.name!r} has "
                    f"{len(item.values)} values for {len(self.categories)} categories"
                )

    @property
    def kind(self) -> str:
        return _COMBO_KIND_BY_GROUPING[self.column_grouping]


@dataclass(frozen=True)
class WaterfallChartSpec:
    """A signed bridge chart with explicit running-total markers.

    ``phases`` holds one entry per category.  A float is a signed delta bar and
    ``None`` is an explicit total marker showing the running total at that
    category.  ``opening`` seeds the running total before the first phase.
    Running totals may be positive, negative, or cross zero: the bridge is
    authored as a signed stacked-bar construction rather than a ChartEx
    waterfall part.
    """

    categories: tuple[str, ...]
    phases: tuple[float | None, ...]
    opening: float = 0.0
    title: str | None = None
    legend: bool = False
    increase_rgb: str = _DEFAULT_INCREASE_RGB
    decrease_rgb: str = _DEFAULT_DECREASE_RGB
    total_rgb: str = _DEFAULT_TOTAL_RGB
    show_value_labels: bool = True
    gap_width: int = 60

    def __post_init__(self) -> None:
        if not self.categories:
            raise FinancialChartRefusal("waterfall chart needs categories")
        if len(self.phases) != len(self.categories):
            raise FinancialChartRefusal("waterfall chart needs one phase per category")
        if not any(phase is not None for phase in self.phases):
            raise FinancialChartRefusal(
                "waterfall chart needs at least one delta phase"
            )
        if self.gap_width < 0 or self.gap_width > 500:
            raise FinancialChartRefusal("waterfall gap_width must be in 0..500")

    @property
    def kind(self) -> str:
        return WATERFALL


@dataclass(frozen=True)
class ExtendedChartSpec:
    """One Office 2016+ ChartEx chart backed by one category/value series."""

    kind: str
    categories: tuple[str, ...]
    values: tuple[float, ...]
    title: str | None = None
    legend: bool = False
    bin_count: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in CHARTEX_CHART_KINDS:
            supported = ", ".join(CHARTEX_CHART_KINDS)
            raise FinancialChartRefusal(
                f"extended chart kind {self.kind!r} is not supported; supported kinds: {supported}"
            )
        if not self.categories or not self.values:
            raise FinancialChartRefusal("extended chart needs categories and values")
        if len(self.categories) != len(self.values):
            raise FinancialChartRefusal(
                "extended chart needs one value for every category"
            )
        if any(not math.isfinite(value) for value in self.values):
            raise FinancialChartRefusal("extended chart values must be finite")
        if self.bin_count is not None and self.bin_count <= 0:
            raise FinancialChartRefusal("extended chart bin_count must be positive")


@dataclass(frozen=True)
class WaterfallLayout:
    """Resolved signed rows for the stacked-bar bridge representation.

    ``bases`` holds the signed hidden offset that slides the stack to the bar's
    low edge.  ``increases`` holds the upward segment (never negative) and
    ``decreases`` the downward segment (never positive), so a bar that crosses
    zero is drawn as two segments meeting at the axis.  ``roles`` names the
    styling role of each category (``increase``/``decrease``/``total``/
    ``none``), ``label_slots`` says which segment carries the data label, and
    ``labels`` holds the authored label text: the signed phase delta for delta
    phases and the running total for explicit total markers.
    """

    bases: tuple[float, ...]
    increases: tuple[float, ...]
    decreases: tuple[float, ...]
    roles: tuple[str, ...]
    label_slots: tuple[str, ...]
    labels: tuple[str | None, ...]
    running_totals: tuple[float, ...]
    closing_total: float

    @property
    def minimum(self) -> float:
        """Lowest signed point the bridge draws, including total markers.

        A bar that crosses zero is drawn as two segments that each start at the
        hidden offset, so the drawn extremes come from the segment edges rather
        than from the algebraic sum of the delta.
        """
        return min(self._drawn_points())

    @property
    def maximum(self) -> float:
        """Highest signed point the bridge draws, including total markers."""
        return max(self._drawn_points())

    def _drawn_points(self) -> list[float]:
        points = [0.0]
        for base, increase, decrease in zip(
            self.bases,
            self.increases,
            self.decreases,
            strict=True,
        ):
            points.extend((base + increase, base + decrease))
        return points


@dataclass(frozen=True)
class FinancialChartReceipt:
    """Result of authoring one financial chart into a deck."""

    input_path: str
    output_path: str
    slide_index: int
    shape_name: str
    kind: str
    representation: str
    categories: list[str]
    series_names: list[str]
    chart_part: str
    workbook_part: str
    source_sha256: str
    output_sha256: str
    changed_parts: list[str]
    unchanged_part_count: int
    source_slide_count: int
    output_slide_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_path": self.input_path,
            "output_path": self.output_path,
            "slide_index": self.slide_index,
            "shape_name": self.shape_name,
            "kind": self.kind,
            "representation": self.representation,
            "categories": list(self.categories),
            "series_names": list(self.series_names),
            "chart_part": self.chart_part,
            "workbook_part": self.workbook_part,
            "source_sha256": self.source_sha256,
            "output_sha256": self.output_sha256,
            "changed_parts": list(self.changed_parts),
            "unchanged_part_count": self.unchanged_part_count,
            "source_slide_count": self.source_slide_count,
            "output_slide_count": self.output_slide_count,
        }


@dataclass(frozen=True)
class _FinancialChartStaging:
    """A private source snapshot plus the staged output awaiting publication."""

    source: Path
    destination: Path
    snapshot: Path
    staged: Path
    source_sha256: str


def _ensure_publishable_paths(source: Path, destination: Path) -> None:
    """Refuse paths that cannot honour the publication contract.

    The contract is the engine's reporting shape made strict: the source deck
    is read-only, the output must be a new regular file, and no path may name
    the source itself.
    """
    if not source.is_file():
        raise FinancialChartRefusal(f"input deck {source} does not exist")
    if destination.is_symlink():
        raise FinancialChartRefusal(
            f"output {destination} is a symbolic link; financial chart authoring "
            "publishes a new regular file and never follows a link"
        )
    if source.resolve() == destination.resolve():
        raise FinancialChartRefusal(
            f"output {destination} names the input deck; in-place financial "
            "chart editing would modify the source"
        )
    if destination.exists():
        raise FinancialChartRefusal(
            f"output {destination} already exists; financial chart authoring "
            "never overwrites a destination"
        )
    if not destination.parent.is_dir():
        raise FinancialChartRefusal(
            f"output directory {destination.parent} does not exist"
        )


def _slide_at(presentation: Any, slide_index: int) -> Any:
    """Return the slide at ``slide_index``, refusing an unavailable index."""
    slides = presentation.slides
    if slide_index < 0 or slide_index >= len(slides):
        raise FinancialChartRefusal(
            f"slide index {slide_index} is unavailable; the deck has "
            f"{len(slides)} slide(s)"
        )
    return slides[slide_index]


@contextmanager
def _financial_chart_staging(
    source: Path,
    destination: Path,
    operation: str,
) -> Iterator[_FinancialChartStaging]:
    """Bind an operation to a private snapshot of ``source`` and stage its output.

    Both the snapshot and the staged package live in a private directory beside
    the destination, so publication is a same-filesystem operation and only this
    operation's own directory is ever cleaned up.  Every failure path leaves the
    destination absent: nothing is written outside the staging directory, and
    the directory itself is removed on exit.
    """
    _ensure_publishable_paths(source, destination)
    snapshot_bytes = source.read_bytes()
    with tempfile.TemporaryDirectory(
        prefix=f".wolfppt-{operation}-",
        dir=destination.parent,
    ) as directory:
        snapshot = Path(directory) / f"source{source.suffix or '.pptx'}"
        snapshot.write_bytes(snapshot_bytes)
        yield _FinancialChartStaging(
            source=source,
            destination=destination,
            snapshot=snapshot,
            staged=Path(directory) / destination.name,
            source_sha256=_sha256_bytes(snapshot_bytes),
        )


def _publish_staged_chart_output(staging: _FinancialChartStaging) -> str:
    """Publish the staged package and return the destination's raw file digest.

    The source snapshot is re-hashed immediately before publication, so a deck
    that changed while the edit was staged is refused instead of publishing a
    package derived from a base the caller no longer holds.  Publication itself
    is a same-filesystem atomic no-clobber link: it either creates the
    destination holding the staged package's complete bytes or fails, so a
    destination that appeared while the edit was staged is refused rather than
    overwritten, and a filesystem that cannot hard-link is refused rather than
    publishing non-atomically.
    """
    if _sha256_bytes(staging.source.read_bytes()) != staging.source_sha256:
        raise FinancialChartRefusal(
            f"input deck {staging.source} changed while the financial chart was "
            "being staged; nothing was published"
        )
    _link_staged_chart_output(staging.staged, staging.destination)
    try:
        staging.staged.unlink()
    except FileNotFoundError:
        pass
    return _sha256_bytes(staging.destination.read_bytes())


def _link_staged_chart_output(staged: Path, destination: Path) -> None:
    """Atomically publish ``staged`` as ``destination``, refusing to clobber.

    ``os.link`` is the only publication primitive used: it creates the
    destination name pointing at the staged package's already-complete bytes,
    and it fails with ``FileExistsError`` instead of replacing a destination
    that appeared meanwhile.  Any other failure is reported as a refusal, so an
    unsupported destination filesystem fails closed rather than exposing a
    partially written deck.
    """
    try:
        os.link(staged, destination)
    except FileExistsError as exc:
        raise FinancialChartRefusal(
            f"output {destination} already exists; financial chart authoring "
            "never overwrites a destination"
        ) from exc
    except OSError as exc:
        raise FinancialChartRefusal(
            f"output {destination} cannot be published atomically: this "
            "filesystem does not support hard-link publication "
            f"({exc.strerror or exc}); choose a destination on a filesystem "
            "that does"
        ) from exc


def waterfall_layout(spec: WaterfallChartSpec) -> WaterfallLayout:
    """Resolve bridge phases into the signed rows that get authored.

    Each category resolves to a signed hidden base plus an upward and/or
    downward segment, so a bar that stays above zero, stays below zero, or
    crosses zero is representable in the stacked-bar bridge construction:

    * a bar entirely above zero places its hidden base on the low edge
    * a bar entirely below zero places its hidden base on the high (less
      negative) edge and carries the remainder in the downward segment
    * a bar crossing zero uses no hidden base and splits into the upward
      segment above the axis and the downward segment below it
    """
    running = float(spec.opening)
    bases: list[float] = []
    increases: list[float] = []
    decreases: list[float] = []
    roles: list[str] = []
    label_slots: list[str] = []
    labels: list[str | None] = []
    running_totals: list[float] = []
    for phase in spec.phases:
        if phase is None:
            role = "total"
            low, high = min(running, 0.0), max(running, 0.0)
            label = _chart_number_text(running)
            prefer_up = running >= 0
        else:
            delta = float(phase)
            low, high = min(running, running + delta), max(running, running + delta)
            running += delta
            role = "increase" if delta > 0 else ("decrease" if delta < 0 else "none")
            label = _chart_number_text(delta) if delta else None
            prefer_up = delta > 0
        if high - low <= 0:
            base = 0.0
            increase = 0.0
            decrease = 0.0
        else:
            base = low if low >= 0 else (high if high <= 0 else 0.0)
            increase = high - max(low, 0.0) if high > 0 else 0.0
            decrease = (min(low, 0.0) - min(high, 0.0)) if low < 0 else 0.0
        # The label rides the segment actually drawn at this category, so a
        # delta that ends on the far side of the axis is still labelled.
        label_slot = _bridge_label_slot(prefer_up, increase, decrease)
        bases.append(base)
        increases.append(increase)
        decreases.append(decrease)
        roles.append(role)
        label_slots.append(label_slot)
        labels.append(label)
        running_totals.append(running)
    return WaterfallLayout(
        bases=tuple(bases),
        increases=tuple(increases),
        decreases=tuple(decreases),
        roles=tuple(roles),
        label_slots=tuple(label_slots),
        labels=tuple(labels),
        running_totals=tuple(running_totals),
        closing_total=running,
    )


def financial_chart_kind(spec: Any) -> str:
    kind = getattr(spec, "kind", None)
    if not isinstance(kind, str) or kind not in FINANCIAL_CHART_KINDS:
        raise FinancialChartRefusal(
            "financial chart spec must be ComboChartSpec, WaterfallChartSpec, "
            "or ExtendedChartSpec"
        )
    return kind


def financial_chart_payload(spec: Any) -> dict[str, Any]:
    """Return the normalized chart-data payload for one financial chart spec."""
    kind = financial_chart_kind(spec)
    if kind == WATERFALL:
        assert isinstance(spec, WaterfallChartSpec)
        layout = waterfall_layout(spec)
        names = list(_WATERFALL_SERIES_NAMES)
        values = [
            list(layout.bases),
            list(layout.increases),
            list(layout.decreases),
        ]
        chart_xml = _waterfall_chart_xml(spec, layout)
        workbook_evidence = _bridge_workbook_evidence(spec, layout)
    elif kind in CHARTEX_CHART_KINDS:
        assert isinstance(spec, ExtendedChartSpec)
        names = ["Series 1"]
        values = [list(spec.values)]
        chart_xml = _chartex_chart_xml(spec)
        workbook_evidence = []
    else:
        assert isinstance(spec, ComboChartSpec)
        names = [item.name for item in spec.series]
        values = [list(item.values) for item in spec.series]
        chart_xml = _combo_chart_xml(spec)
        workbook_evidence = []
    representation = FINANCIAL_CHART_REPRESENTATIONS[kind]
    categories = [str(category) for category in spec.categories]
    series_payloads = [
        {
            "name": name,
            "categories": list(categories),
            "values": list(row),
        }
        for name, row in zip(names, values, strict=True)
    ]
    payload: dict[str, Any] = {
        "data_kind": "category",
        "category_kind": "string",
        "categories": categories,
        "category_hierarchy": [],
        "series": series_payloads,
        "xlsx_blob": category_chart_workbook_blob(
            categories,
            series_payloads + workbook_evidence,
        ),
        "_financial_kind": kind,
        "_financial_representation": representation,
    }
    if kind in CHARTEX_CHART_KINDS:
        payload["_chartex_chart_xml"] = chart_xml
    else:
        payload["_precomputed_chart_xml"] = chart_xml
    return payload


def author_financial_chart(
    input_path: str | Path,
    output_path: str | Path,
    *,
    spec: Any,
    slide_index: int = 0,
    x: int = 914400,
    y: int = 914400,
    cx: int = 5486400,
    cy: int = 3200400,
) -> FinancialChartReceipt:
    """Author one editable financial chart into a new deck at ``output_path``.

    The source deck is opened from a private snapshot, so it is never modified,
    and the result is staged beside the destination and published atomically
    without clobbering an existing path.  A refused or failed run leaves the
    source untouched and the destination absent.
    """
    from .presentation import Presentation

    source = Path(input_path)
    destination = Path(output_path)
    kind = financial_chart_kind(spec)
    payload = financial_chart_payload(spec)
    with _financial_chart_staging(source, destination, "author") as staging:
        # Snapshot the source package before saving so the changed-part list is
        # always measured against the snapshot that was actually edited.
        source_parts = _read_package_parts(staging.snapshot)
        presentation = Presentation(staging.snapshot)
        slide = _slide_at(presentation, slide_index)
        shape = slide.shapes.add_financial_chart(spec, x, y, cx, cy)
        presentation.save(staging.staged)
        output_sha256 = _publish_staged_chart_output(staging)
        return _financial_chart_receipt(
            source,
            destination,
            source_sha256=staging.source_sha256,
            output_sha256=output_sha256,
            source_parts=source_parts,
            slide_index=slide_index,
            shape_name=str(shape.name),
            kind=kind,
            representation=str(payload["_financial_representation"]),
            categories=list(payload["categories"]),
            series_names=[str(item["name"]) for item in payload["series"]],
        )


def author_extended_chart(
    input_path: str | Path,
    output_path: str | Path,
    *,
    spec: ExtendedChartSpec,
    slide_index: int = 0,
    x: int = 914400,
    y: int = 914400,
    cx: int = 5486400,
    cy: int = 3200400,
) -> FinancialChartReceipt:
    """Author one Office 2016+ ChartEx chart through the dedicated facade API."""
    from .presentation import Presentation

    source = Path(input_path)
    destination = Path(output_path)
    payload = financial_chart_payload(spec)
    with _financial_chart_staging(source, destination, "author-extended") as staging:
        source_parts = _read_package_parts(staging.snapshot)
        presentation = Presentation(staging.snapshot)
        slide = _slide_at(presentation, slide_index)
        shape = slide.shapes.add_extended_chart(spec, x, y, cx, cy)
        presentation.save(staging.staged)
        output_sha256 = _publish_staged_chart_output(staging)
        return _financial_chart_receipt(
            source,
            destination,
            source_sha256=staging.source_sha256,
            output_sha256=output_sha256,
            source_parts=source_parts,
            slide_index=slide_index,
            shape_name=str(shape.name),
            kind=spec.kind,
            representation=str(payload["_financial_representation"]),
            categories=list(payload["categories"]),
            series_names=[str(item["name"]) for item in payload["series"]],
        )


def refresh_financial_chart(
    input_path: str | Path,
    output_path: str | Path,
    *,
    spec: Any,
    slide_index: int = 0,
    shape_name: str | None = None,
) -> FinancialChartReceipt:
    """Refresh an authored financial chart's data into a new deck.

    The chart keeps its authored plot layout, series styling, and any unrelated
    deck content; only the chart part caches and its embedded workbook are
    replaced.  ``shape_name`` selects one chart when the slide holds several.
    The refresh refuses to change the authored financial kind, because the
    authored plot structure (grouping, plot membership, bridge roles) belongs
    to the kind that was originally authored.  Like authoring, the refresh
    edits a private snapshot of the input and publishes atomically without
    clobbering, so the input deck is never modified.
    """
    from .presentation import Presentation

    source = Path(input_path)
    destination = Path(output_path)
    kind = financial_chart_kind(spec)
    payload = financial_chart_payload(spec)
    with _financial_chart_staging(source, destination, "refresh") as staging:
        source_parts = _read_package_parts(staging.snapshot)
        presentation = Presentation(staging.snapshot)
        slide = _slide_at(presentation, slide_index)
        shape = _find_financial_chart_shape(slide, shape_name)
        authored_kind = shape.chart.financial_kind
        if authored_kind != kind:
            raise FinancialChartRefusal(
                f"chart shape {shape.name!r} holds a "
                f"{authored_kind or 'non-financial'} chart and cannot be refreshed "
                f"as {kind}; author a new chart instead"
            )
        from .chart_facade_helpers import shape_chart_part as _shape_chart_part

        chart_part = str(_shape_chart_part(shape))
        shape.chart.replace_financial_data(spec)
        presentation.save(staging.staged)
        output_sha256 = _publish_staged_chart_output(staging)
        return _financial_chart_receipt(
            source,
            destination,
            source_sha256=staging.source_sha256,
            output_sha256=output_sha256,
            source_parts=source_parts,
            slide_index=slide_index,
            shape_name=str(shape.name),
            kind=kind,
            chart_part=chart_part,
            representation=str(payload["_financial_representation"]),
            categories=list(payload["categories"]),
            series_names=[str(item["name"]) for item in payload["series"]],
        )


def _bridge_label_slot(prefer_up: bool, increase: float, decrease: float) -> str:
    """Pick the drawn segment that carries the category's data label."""
    if prefer_up:
        if increase != 0:
            return "up"
        return "down" if decrease != 0 else "none"
    if decrease != 0:
        return "down"
    return "up" if increase != 0 else "none"


def apply_financial_chart_formatting(chart_xml: bytes, spec: Any) -> bytes:
    """Reapply data-derived role formatting to an existing chart part.

    A bridge chart's per-point fills and data-label text are derived from the
    running total, so a data refresh must reapply them: a category that moves
    above or below zero changes role, and a stale label would state the wrong
    business value.  Combination charts keep their authored series styling and
    are returned unchanged.
    """
    if financial_chart_kind(spec) != WATERFALL:
        return chart_xml
    assert isinstance(spec, WaterfallChartSpec)
    layout = waterfall_layout(spec)
    root = ET.fromstring(chart_xml)
    chart = root.find(f"{{{C_NS}}}chart")
    if chart is None:
        raise FinancialChartRefusal("chart part has no chart element to format")
    plot_area = chart.find(f"{{{C_NS}}}plotArea")
    bar_plot = None if plot_area is None else plot_area.find(f"{{{C_NS}}}barChart")
    if bar_plot is None:
        raise FinancialChartRefusal(
            "chart part has no bar plot to format as a stacked-bar bridge"
        )
    _register_chart_namespaces()
    _apply_waterfall_series_formatting(
        bar_plot,
        spec,
        layout,
        show_labels=spec.show_value_labels,
    )
    return chart_axis_ids_as_openxml_int32(
        ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )


def _find_financial_chart_shape(slide: Any, shape_name: str | None) -> Any:
    chart_shapes = [shape for shape in slide.shapes if shape.has_chart]
    if shape_name is not None:
        for shape in chart_shapes:
            if str(shape.name) == shape_name:
                return shape
        raise FinancialChartRefusal(
            f"slide {slide._index} has no chart shape named {shape_name!r}"
        )
    authored = [
        shape for shape in chart_shapes if shape.chart.financial_kind is not None
    ]
    if not authored:
        raise FinancialChartRefusal(
            "slide has no authored financial chart to refresh; author one first"
        )
    if len(authored) > 1:
        raise FinancialChartRefusal(
            "slide holds more than one financial chart; pass shape_name to choose one"
        )
    return authored[0]


def financial_spec_from_request(document: dict[str, Any]) -> Any:
    """Build a typed spec from a full CLI/JSON request document.

    The document may carry the spec fields directly or nest them under
    ``chart``; ``kind`` may sit at either level.  Non-spec keys such as
    ``layout``, ``slide_index``, and ``shape_name`` are ignored here.
    """
    if not isinstance(document, dict):
        raise FinancialChartRefusal("financial chart request must be a JSON object")
    chart = document.get("chart")
    if chart is None:
        return request_spec_from_dict(document)
    if not isinstance(chart, dict):
        raise FinancialChartRefusal(
            "financial chart request 'chart' member must be an object"
        )
    kind = chart.get("kind") or document.get("kind")
    if not kind:
        raise FinancialChartRefusal("financial chart request needs a 'kind'")
    return request_spec_from_dict({**chart, "kind": kind})


def financial_chart_frame(
    document: dict[str, Any] | None = None,
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Resolve a chart frame from defaults, a request ``layout``, and overrides.

    The request may spell the frame as ``layout`` or ``frame``; explicit
    ``override`` entries (CLI flags) win over both.
    """
    frame = dict(DEFAULT_CHART_FRAME)
    document = {} if document is None else document
    layout = document.get("layout")
    if layout is None:
        layout = document.get("frame")
    if layout is not None:
        if not isinstance(layout, dict):
            raise FinancialChartRefusal(
                "financial chart request 'layout' member must be an object"
            )
        for key in frame:
            if layout.get(key) is not None:
                frame[key] = int(layout[key])
    for key, value in (override or {}).items():
        if value is not None:
            frame[key] = int(value)
    if frame["cx"] <= 0 or frame["cy"] <= 0:
        raise FinancialChartRefusal("financial chart frame must have positive extents")
    return frame


def request_spec_from_dict(payload: dict[str, Any]) -> Any:
    """Build a typed financial chart spec from a CLI/JSON request object."""
    if not isinstance(payload, dict):
        raise FinancialChartRefusal("financial chart request must be a JSON object")
    kind = str(payload.get("kind") or "").strip().upper()
    if kind in UNSUPPORTED_FINANCIAL_CHART_TYPES:
        raise FinancialChartRefusal(
            f"{kind} is not supported: {UNSUPPORTED_FINANCIAL_CHART_TYPES[kind]}"
        )
    categories = tuple(str(item) for item in _required_sequence(payload, "categories"))
    if kind in CHARTEX_CHART_KINDS:
        return ExtendedChartSpec(
            kind=kind,
            categories=categories,
            values=tuple(
                float(value) for value in _required_sequence(payload, "values")
            ),
            title=None if payload.get("title") is None else str(payload["title"]),
            legend=bool(payload.get("legend", False)),
            bin_count=(
                None if payload.get("bin_count") is None else int(payload["bin_count"])
            ),
        )
    if kind == WATERFALL:
        raw_phases = _required_sequence(payload, "phases")
        phases: list[float | None] = [
            None if phase is None else float(phase) for phase in raw_phases
        ]
        return WaterfallChartSpec(
            categories=categories,
            phases=tuple(phases),
            opening=float(payload.get("opening", 0.0)),
            title=None if payload.get("title") is None else str(payload["title"]),
            legend=bool(payload.get("legend", False)),
            increase_rgb=str(payload.get("increase_rgb") or _DEFAULT_INCREASE_RGB),
            decrease_rgb=str(payload.get("decrease_rgb") or _DEFAULT_DECREASE_RGB),
            total_rgb=str(payload.get("total_rgb") or _DEFAULT_TOTAL_RGB),
            show_value_labels=bool(payload.get("show_value_labels", True)),
            gap_width=int(payload.get("gap_width", 60)),
        )
    if kind not in {
        COMBO_COLUMN_LINE,
        COMBO_COLUMN_STACKED_LINE,
        COMBO_COLUMN_STACKED_100_LINE,
        "COMBO",
        "COMBO_COLUMN_LINE_CLUSTERED",
    }:
        supported = ", ".join(FINANCIAL_CHART_KINDS)
        raise FinancialChartRefusal(
            f"unsupported financial chart kind {kind!r}; supported kinds: {supported}"
        )
    grouping = {
        COMBO_COLUMN_LINE: "clustered",
        "COMBO": "clustered",
        "COMBO_COLUMN_LINE_CLUSTERED": "clustered",
        COMBO_COLUMN_STACKED_LINE: "stacked",
        COMBO_COLUMN_STACKED_100_LINE: "percentStacked",
    }[kind]
    series = tuple(
        ChartSeriesSpec(
            name=str(item["name"]),
            values=tuple(float(value) for value in _required_sequence(item, "values")),
            plot=str(item.get("plot") or "column"),
            fill_rgb=None if item.get("fill_rgb") is None else str(item["fill_rgb"]),
            line_rgb=None if item.get("line_rgb") is None else str(item["line_rgb"]),
            marker_symbol=(
                None
                if item.get("marker_symbol") is None
                else str(item["marker_symbol"])
            ),
        )
        for item in _required_sequence(payload, "series")
    )
    return ComboChartSpec(
        categories=categories,
        series=series,
        column_grouping=str(payload.get("column_grouping") or grouping),
        title=None if payload.get("title") is None else str(payload["title"]),
        legend=bool(payload.get("legend", True)),
        value_axis_title=(
            None
            if payload.get("value_axis_title") is None
            else str(payload["value_axis_title"])
        ),
        secondary_axis_title=(
            None
            if payload.get("secondary_axis_title") is None
            else str(payload["secondary_axis_title"])
        ),
        line_marker_symbol=str(payload.get("line_marker_symbol") or "circle"),
        line_smooth=bool(payload.get("line_smooth", False)),
    )


def _chartex_chart_xml(spec: ExtendedChartSpec) -> bytes:
    """Build a schema-valid Office 2016+ ChartEx part with cached source data."""
    ET.register_namespace("cx", CHARTEX_NS)
    ET.register_namespace("r", R_NS)
    cx = f"{{{CHARTEX_NS}}}"
    root = ET.Element(f"{cx}chartSpace", {"version": "1.0"})
    chart_data = ET.SubElement(root, f"{cx}chartData")
    ET.SubElement(chart_data, f"{cx}externalData", {f"{{{R_NS}}}id": "rId1"})
    _chartex_string_data(chart_data, 1, spec.categories, "Sheet1!$A$2")
    _chartex_numeric_data(chart_data, 2, spec.values, "Sheet1!$B$2")

    chart = ET.SubElement(root, f"{cx}chart")
    if spec.title:
        title = ET.SubElement(chart, f"{cx}title")
        text = ET.SubElement(title, f"{cx}tx")
        ET.SubElement(text, f"{cx}v").text = spec.title
    plot_area = ET.SubElement(chart, f"{cx}plotArea")
    region = ET.SubElement(plot_area, f"{cx}plotAreaRegion")
    layout = {
        TREEMAP: "treemap",
        SUNBURST: "sunburst",
        CHARTEX_WATERFALL: "waterfall",
        FUNNEL: "funnel",
        BOX_WHISKER: "boxWhisker",
        HISTOGRAM: "clusteredColumn",
        PARETO: "clusteredColumn",
    }[spec.kind]
    series = ET.SubElement(region, f"{cx}series", {"layoutId": layout})
    ET.SubElement(series, f"{cx}dataId", {"val": "2"})
    layout_properties = ET.SubElement(series, f"{cx}layoutPr")
    if spec.kind == HISTOGRAM:
        binning = ET.SubElement(layout_properties, f"{cx}binning")
        ET.SubElement(
            binning,
            f"{cx}binCount",
        ).text = str(spec.bin_count or max(1, round(len(spec.values) ** 0.5)))
    elif spec.kind == BOX_WHISKER:
        ET.SubElement(
            layout_properties, f"{cx}statistics", {"quartileMethod": "inclusive"}
        )
    elif spec.kind == TREEMAP:
        ET.SubElement(layout_properties, f"{cx}parentLabelLayout", {"val": "banner"})
    elif spec.kind == SUNBURST:
        ET.SubElement(
            layout_properties, f"{cx}parentLabelLayout", {"val": "overlapping"}
        )
    else:
        series.remove(layout_properties)
    if spec.kind == PARETO:
        pareto = ET.SubElement(region, f"{cx}series", {"layoutId": "paretoLine"})
        ET.SubElement(pareto, f"{cx}dataId", {"val": "2"})
    if spec.legend:
        ET.SubElement(chart, f"{cx}legend")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _chartex_string_data(
    parent: ET.Element,
    data_id: int,
    values: tuple[str, ...],
    formula_start: str,
) -> None:
    cx = f"{{{CHARTEX_NS}}}"
    data = ET.SubElement(parent, f"{cx}data", {"id": str(data_id)})
    dimension = ET.SubElement(data, f"{cx}strDim", {"type": "cat"})
    column = formula_start.split("$")[1]
    ET.SubElement(
        dimension, f"{cx}f"
    ).text = f"Sheet1!${column}$2:${column}${len(values) + 1}"
    level = ET.SubElement(dimension, f"{cx}lvl", {"ptCount": str(len(values))})
    for index, value in enumerate(values):
        ET.SubElement(level, f"{cx}pt", {"idx": str(index)}).text = str(value)


def _chartex_numeric_data(
    parent: ET.Element,
    data_id: int,
    values: tuple[float, ...],
    formula_start: str,
) -> None:
    cx = f"{{{CHARTEX_NS}}}"
    data = ET.SubElement(parent, f"{cx}data", {"id": str(data_id)})
    dimension = ET.SubElement(data, f"{cx}numDim", {"type": "val"})
    column = formula_start.split("$")[1]
    ET.SubElement(
        dimension, f"{cx}f"
    ).text = f"Sheet1!${column}$2:${column}${len(values) + 1}"
    level = ET.SubElement(dimension, f"{cx}lvl", {"ptCount": str(len(values))})
    for index, value in enumerate(values):
        ET.SubElement(level, f"{cx}pt", {"idx": str(index)}).text = _chart_number_text(
            value
        )


# --------------------------------------------------------------------------- #
# Chart XML construction
# --------------------------------------------------------------------------- #


def _combo_chart_xml(spec: ComboChartSpec) -> bytes:
    _register_chart_namespaces()
    base_template_id = _COMBO_COLUMN_TEMPLATE_ID[spec.column_grouping]
    bar_root = ET.fromstring(_build_chart_template(base_template_id)["chart_xml"])
    line_root = ET.fromstring(_build_chart_template(4)["chart_xml"])
    chart = bar_root.find(f"{{{C_NS}}}chart")
    if chart is None:
        raise FinancialChartRefusal("combination chart template has no chart element")
    plot_area = chart.find(f"{{{C_NS}}}plotArea")
    if plot_area is None:
        raise FinancialChartRefusal("combination chart template has no plot area")
    bar_plot = plot_area.find(f"{{{C_NS}}}barChart")
    line_template_plot = line_root.find(f".//{{{C_NS}}}lineChart")
    if bar_plot is None or line_template_plot is None:
        raise FinancialChartRefusal("combination chart templates are unavailable")
    line_plot = deepcopy(line_template_plot)

    cat_axis = _first_axis(plot_area, "catAx")
    value_axis = _first_axis(plot_area, "valAx")
    line_value_axis = _first_axis(line_root, "valAx")
    if cat_axis is None or value_axis is None or line_value_axis is None:
        raise FinancialChartRefusal("combination chart template axes are unavailable")

    category_axis_id = _axis_id(cat_axis, "category")
    primary_axis_id = _axis_id(value_axis, "primary value")
    secondary_axis_id = _next_axis_id((category_axis_id, primary_axis_id))
    secondary_axis = deepcopy(line_value_axis)
    _set_axis_id(secondary_axis, secondary_axis_id)
    _set_child(
        secondary_axis, "crossAx", category_axis_id, _PARENT_CHILD_ORDER["valAx"]
    )
    _set_child(secondary_axis, "axPos", "r", _PARENT_CHILD_ORDER["valAx"])
    _set_child(secondary_axis, "crosses", "max", _PARENT_CHILD_ORDER["valAx"])
    _set_child(secondary_axis, "delete", "0", _PARENT_CHILD_ORDER["valAx"])
    gridlines = secondary_axis.find(f"{{{C_NS}}}majorGridlines")
    if gridlines is not None:
        secondary_axis.remove(gridlines)

    _set_child(value_axis, "axPos", "l", _PARENT_CHILD_ORDER["valAx"])
    _set_child(value_axis, "delete", "0", _PARENT_CHILD_ORDER["valAx"])

    column_series = [item for item in spec.series if item.plot == "column"]
    line_series = [item for item in spec.series if item.plot == "line"]
    column_elements = _resize_plot_series(bar_plot, len(column_series))
    line_elements = _resize_plot_series(line_plot, len(line_series))

    # Both plots carry authored fills, so the automatic per-point colouring is
    # switched off explicitly instead of relying on the schema default.
    _set_child(bar_plot, "varyColors", "0", _bar_plot_order())
    _set_child(line_plot, "varyColors", "0", _line_plot_order())
    _set_plot_axis_ids(bar_plot, category_axis_id, primary_axis_id)
    _set_plot_axis_ids(line_plot, category_axis_id, secondary_axis_id)
    _set_child(line_plot, "grouping", "standard", _line_plot_order())
    _set_child(line_plot, "marker", "1", _line_plot_order())
    _set_child(line_plot, "smooth", "0", _line_plot_order())

    # Insert the line plot directly after the bar plot, then the secondary
    # value axis after the primary one, preserving the plotArea schema order.
    bar_index = list(plot_area).index(bar_plot)
    plot_area.insert(bar_index + 1, line_plot)
    value_index = list(plot_area).index(value_axis)
    plot_area.insert(value_index + 1, secondary_axis)

    all_series = [*column_elements, *line_elements]
    for series_index, series_element in enumerate(all_series):
        _set_chart_series_identity(series_element, series_index)
    categories = [str(category) for category in spec.categories]
    category_formula = _category_formula(len(categories), 1)
    for series_index, (series_element, series_spec) in enumerate(
        zip(all_series, spec.series, strict=True)
    ):
        value_column = _excel_column_name(series_index + 2)
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef"),
            [series_spec.name],
            f"Sheet1!${value_column}$1",
        )
        _replace_chart_categories(series_element, categories, [], category_formula)
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}val/{{{C_NS}}}numRef"),
            [_chart_number_text(float(value)) for value in series_spec.values],
            f"Sheet1!${value_column}$2:${value_column}${len(categories) + 1}",
        )
        if series_spec.plot == "line":
            _configure_line_series(
                series_element,
                series_spec,
                marker_symbol=series_spec.marker_symbol or spec.line_marker_symbol,
                smooth=spec.line_smooth,
            )

    _style_combo_series(bar_plot, line_plot, spec.series)
    if spec.title:
        _set_chart_title(chart, spec.title)
    if spec.value_axis_title:
        _set_axis_title(value_axis, spec.value_axis_title)
    if spec.secondary_axis_title:
        _set_axis_title(secondary_axis, spec.secondary_axis_title)
    if spec.legend:
        _set_chart_legend(chart, position="b")
    _append_financial_marker(
        bar_root,
        spec.kind,
        FINANCIAL_CHART_REPRESENTATIONS[spec.kind],
    )
    return chart_axis_ids_as_openxml_int32(
        ET.tostring(bar_root, encoding="utf-8", xml_declaration=True)
    )


def _bridge_workbook_evidence(
    spec: WaterfallChartSpec,
    layout: WaterfallLayout,
) -> list[dict[str, Any]]:
    """Extra workbook columns that state the bridge in business terms.

    The chart caches reference the hidden offset and segment columns, because
    that is what a stacked bar chart can plot.  The embedded workbook carries
    two further unreferenced columns so the authoring user can still read the
    phase deltas and the running total they supplied.
    """
    return [
        {
            "name": "Phase delta",
            "values": [0.0 if phase is None else float(phase) for phase in spec.phases],
        },
        {
            "name": "Running total",
            "values": list(layout.running_totals),
        },
    ]


def _waterfall_chart_xml(spec: WaterfallChartSpec, layout: WaterfallLayout) -> bytes:
    _register_chart_namespaces()
    template_id = _FINANCIAL_TEMPLATE_NAME_TO_ID[WATERFALL]
    root = ET.fromstring(_build_chart_template(template_id)["chart_xml"])
    chart = root.find(f"{{{C_NS}}}chart")
    if chart is None:
        raise FinancialChartRefusal("waterfall chart template has no chart element")
    plot_area = chart.find(f"{{{C_NS}}}plotArea")
    if plot_area is None:
        raise FinancialChartRefusal("waterfall chart template has no plot area")
    bar_plot = plot_area.find(f"{{{C_NS}}}barChart")
    if bar_plot is None:
        raise FinancialChartRefusal("waterfall chart template has no bar plot")
    _set_child(bar_plot, "varyColors", "0", _bar_plot_order())
    _set_child(bar_plot, "overlap", "100", _bar_plot_order())
    _set_child(bar_plot, "gapWidth", str(spec.gap_width), _bar_plot_order())

    rows = (
        layout.bases,
        layout.increases,
        layout.decreases,
    )
    series_elements = _resize_plot_series(bar_plot, len(_WATERFALL_SERIES_NAMES))
    categories = [str(category) for category in spec.categories]
    category_formula = _category_formula(len(categories), 1)
    for series_index, (series_element, name, values) in enumerate(
        zip(series_elements, _WATERFALL_SERIES_NAMES, rows, strict=True)
    ):
        _set_chart_series_identity(series_element, series_index)
        value_column = _excel_column_name(series_index + 2)
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef"),
            [name],
            f"Sheet1!${value_column}$1",
        )
        _replace_chart_categories(series_element, categories, [], category_formula)
        _replace_chart_cache(
            series_element.find(f"{{{C_NS}}}val/{{{C_NS}}}numRef"),
            [_chart_number_text(float(value)) for value in values],
            f"Sheet1!${value_column}$2:${value_column}${len(categories) + 1}",
        )

    _apply_waterfall_series_formatting(
        bar_plot,
        spec,
        layout,
        show_labels=spec.show_value_labels,
    )
    if spec.title:
        _set_chart_title(chart, spec.title)
    if spec.legend:
        _set_chart_legend(chart, position="b", hidden_series=(0,))
    _append_financial_marker(
        root,
        WATERFALL,
        FINANCIAL_CHART_REPRESENTATIONS[WATERFALL],
    )
    return chart_axis_ids_as_openxml_int32(
        ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )


def _resize_plot_series(plot: ET.Element, count: int) -> list[ET.Element]:
    series = plot.findall(f"{{{C_NS}}}ser")
    if not series:
        raise FinancialChartRefusal("chart series template is unavailable")
    if count < 1:
        raise FinancialChartRefusal("authored chart plots need at least one series")
    while len(series) > count:
        plot.remove(series.pop())
    if len(series) < count:
        insert_at = list(plot).index(series[-1]) + 1
        while len(series) < count:
            clone = deepcopy(series[-1])
            plot.insert(insert_at, clone)
            series.append(clone)
            insert_at += 1
    return series


def _style_combo_series(
    bar_plot: ET.Element,
    line_plot: ET.Element,
    series_specs: Sequence[ChartSeriesSpec],
) -> None:
    """Apply authored series styling to the real plot elements.

    Combination charts number series globally across plots, and the existing
    series-format helper resolves a series by its ``c:idx`` inside the given
    plot element, so the global index still selects exactly one series.
    """
    column_edits: list[dict[str, Any]] = []
    line_edits: list[dict[str, Any]] = []
    for series_index, item in enumerate(series_specs):
        if item.plot == "column":
            properties: dict[str, Any] = {
                "fill_type": "solid",
                "fill_rgb": item.fill_rgb or _DEFAULT_COLUMN_RGB,
            }
            if item.line_rgb:
                properties["line_rgb"] = item.line_rgb
            column_edits.append(
                {"series_index": series_index, "properties": properties}
            )
        else:
            line_edits.append(
                {
                    "series_index": series_index,
                    "properties": {
                        "fill_type": "solid",
                        "fill_rgb": item.fill_rgb or item.line_rgb or _DEFAULT_LINE_RGB,
                        "line_rgb": item.line_rgb or _DEFAULT_LINE_RGB,
                    },
                }
            )
    if column_edits:
        set_chart_series_format_properties(bar_plot, column_edits)
    if line_edits:
        set_chart_series_format_properties(line_plot, line_edits)


def _configure_line_series(
    series_element: ET.Element,
    series_spec: ChartSeriesSpec,
    *,
    marker_symbol: str,
    smooth: bool,
) -> None:
    marker = series_element.find(f"{{{C_NS}}}marker")
    if marker is None:
        marker = ET.Element(f"{{{C_NS}}}marker")
        series_element.insert(_series_child_index(series_element, "marker"), marker)
    _set_child(marker, "symbol", marker_symbol, ("symbol", "size"))
    _set_child(series_element, "smooth", "1" if smooth else "0", _line_series_order())


def _apply_waterfall_series_formatting(
    bar_plot: ET.Element,
    spec: WaterfallChartSpec,
    layout: WaterfallLayout,
    *,
    show_labels: bool,
) -> None:
    """Author role fills and data labels for the stacked-bar bridge.

    The hidden base series carries no fill, the up/down segment series carry the
    increase and decrease colors as their fallback series fill, and every drawn
    point then receives its own solid fill so explicit total markers render with
    the total color regardless of which segment direction they use.
    """
    set_chart_series_format_properties(
        bar_plot,
        [
            {
                "series_index": 0,
                "properties": {
                    "fill_type": "background",
                    "line_fill_type": "background",
                },
            },
            {
                "series_index": 1,
                "properties": {"fill_type": "solid", "fill_rgb": spec.increase_rgb},
            },
            {
                "series_index": 2,
                "properties": {"fill_type": "solid", "fill_rgb": spec.decrease_rgb},
            },
        ],
    )
    series_elements = bar_plot.findall(f"{{{C_NS}}}ser")
    if len(series_elements) != len(_WATERFALL_SERIES_NAMES):
        raise FinancialChartRefusal("waterfall chart series layout is unavailable")
    base_series, increase_series, decrease_series = series_elements
    # A refreshed bridge can move a category out of the drawn range, so stale
    # per-point fills are dropped instead of lingering on a zero-height bar.
    _prune_waterfall_point_fills(increase_series, layout.increases)
    _prune_waterfall_point_fills(decrease_series, layout.decreases)

    point_edits: list[dict[str, Any]] = []
    for point_index, role in enumerate(layout.roles):
        if role == "none":
            continue
        rgb = {
            "increase": spec.increase_rgb,
            "decrease": spec.decrease_rgb,
            "total": spec.total_rgb,
        }[role]
        if layout.increases[point_index] != 0:
            point_edits.append(
                {
                    "series_index": 1,
                    "point_index": point_index,
                    "properties": {"fill_type": "solid", "fill_rgb": rgb},
                }
            )
        if layout.decreases[point_index] != 0:
            point_edits.append(
                {
                    "series_index": 2,
                    "point_index": point_index,
                    "properties": {"fill_type": "solid", "fill_rgb": rgb},
                }
            )
    if point_edits:
        set_chart_point_format_properties(bar_plot, point_edits)

    point_count = len(layout.roles)
    _set_series_point_labels(base_series, [None] * point_count, enabled=False)
    _set_series_point_labels(
        increase_series,
        [
            layout.labels[index] if slot == "up" else None
            for index, slot in enumerate(layout.label_slots)
        ],
        enabled=show_labels,
    )
    _set_series_point_labels(
        decrease_series,
        [
            layout.labels[index] if slot == "down" else None
            for index, slot in enumerate(layout.label_slots)
        ],
        enabled=show_labels,
    )


def _prune_waterfall_point_fills(
    series_element: ET.Element,
    values: Sequence[float],
) -> None:
    """Remove per-point fills for categories the bridge no longer draws."""
    for point in series_element.findall(f"{{{C_NS}}}dPt"):
        index_element = point.find(f"{{{C_NS}}}idx")
        raw_index = None if index_element is None else index_element.get("val")
        if raw_index is None or not raw_index.lstrip("-").isdigit():
            series_element.remove(point)
            continue
        index = int(raw_index)
        if index >= len(values) or values[index] == 0:
            series_element.remove(point)


def _prune_chart_point_overrides(
    series_element: ET.Element,
    point_count: int,
) -> None:
    """Drop per-point overrides that address categories the refresh removed."""
    for point in series_element.findall(f"{{{C_NS}}}dPt"):
        if not _chart_point_index_in_range(point, point_count):
            series_element.remove(point)
    for data_labels in series_element.findall(f"{{{C_NS}}}dLbls"):
        for label in data_labels.findall(f"{{{C_NS}}}dLbl"):
            if not _chart_point_index_in_range(label, point_count):
                data_labels.remove(label)


def _chart_point_index_in_range(point: ET.Element, point_count: int) -> bool:
    index_element = point.find(f"{{{C_NS}}}idx")
    raw_index = None if index_element is None else index_element.get("val")
    if raw_index is None or not raw_index.lstrip("-").isdigit():
        return False
    return 0 <= int(raw_index) < point_count


def _set_series_point_labels(
    series_element: ET.Element,
    labels: Sequence[str | None],
    *,
    enabled: bool,
) -> None:
    """Author per-point data labels, including signed custom label text.

    The label text is the signed phase delta (or the running total at an
    explicit total marker), never the segment magnitude, so a delta that
    crosses zero still reads as the business value that was applied.  A point
    that carries no text loses its label override outright: a refresh can move
    a delta to the opposite segment, and a surviving label would keep stating
    the previous run's business value.
    """
    _prune_chart_point_overrides(series_element, len(labels))
    data_labels = _chart_series_data_labels_element(series_element)
    for local_name in (
        "showLegendKey",
        "showCatName",
        "showSerName",
        "showPercent",
        "showBubbleSize",
    ):
        _set_chart_data_label_bool_child(data_labels, local_name, False)
    _set_chart_data_label_bool_child(data_labels, "showVal", enabled)
    labelled: dict[int, str] = {}
    if enabled:
        for point_index, text in enumerate(labels):
            if text is not None:
                labelled[point_index] = text
    _prune_chart_point_labels(data_labels, set(labelled))
    for point_index, text in labelled.items():
        point_label = _chart_point_data_label_element(data_labels, point_index)
        set_chart_data_label_text(point_label, text)


def _prune_chart_point_labels(
    data_labels: ET.Element,
    labelled: set[int],
) -> None:
    """Drop per-point label overrides the current bridge no longer labels."""
    for fallback_index, point_label in enumerate(
        list(data_labels.findall(f"{{{C_NS}}}dLbl"))
    ):
        index_element = point_label.find(f"{{{C_NS}}}idx")
        raw_index = None if index_element is None else index_element.get("val")
        if raw_index is None:
            point_index: int | None = fallback_index
        elif raw_index.lstrip("-").isdigit():
            point_index = int(raw_index)
        else:
            point_index = None
        if point_index is None or point_index not in labelled:
            data_labels.remove(point_label)


def _set_chart_title(chart: ET.Element, title: str) -> None:
    existing = chart.find(f"{{{C_NS}}}title")
    if existing is not None:
        chart.remove(existing)
    title_element = ET.Element(f"{{{C_NS}}}title")
    chart.insert(0, title_element)
    set_title_text(title_element, title)
    ensure_title_layout(title_element)
    _set_child(chart, "autoTitleDeleted", "0", _PARENT_CHILD_ORDER["chart"])


def _set_axis_title(axis: ET.Element, text: str) -> None:
    title_element = _axis_title_element(axis)
    set_title_text(title_element, text)
    ensure_title_layout(title_element)


def _set_chart_legend(
    chart: ET.Element,
    *,
    position: str,
    hidden_series: Iterable[int] = (),
) -> None:
    legend = chart.find(f"{{{C_NS}}}legend")
    if legend is not None:
        chart.remove(legend)
    legend = ET.Element(f"{{{C_NS}}}legend")
    ET.SubElement(legend, f"{{{C_NS}}}legendPos", {"val": position})
    for series_index in hidden_series:
        entry = ET.SubElement(legend, f"{{{C_NS}}}legendEntry")
        ET.SubElement(entry, f"{{{C_NS}}}idx", {"val": str(series_index)})
        ET.SubElement(entry, f"{{{C_NS}}}delete", {"val": "1"})
    ET.SubElement(legend, f"{{{C_NS}}}overlay", {"val": "0"})
    _insert_ordered_element(chart, legend, _PARENT_CHILD_ORDER["chart"])


def _append_financial_marker(root: ET.Element, kind: str, representation: str) -> None:
    extensions = root.find(f"{{{C_NS}}}extLst")
    if extensions is None:
        extensions = ET.Element(f"{{{C_NS}}}extLst")
        root.append(extensions)
    extension = ET.SubElement(extensions, f"{{{C_NS}}}ext", {"uri": _FINANCIAL_EXT_URI})
    marker = ET.SubElement(extension, _FINANCIAL_EXT_TAG)
    marker.set("kind", kind)
    marker.set("representation", representation)
    marker.set("producer", "wolfppt")


def financial_marker_kind(chart_root: ET.Element) -> str | None:
    """Return the authored financial chart kind recorded in the chart part."""
    for extension in chart_root.findall(f"{{{C_NS}}}extLst/{{{C_NS}}}ext"):
        marker = extension.find(_FINANCIAL_EXT_TAG)
        if marker is None:
            continue
        kind = marker.get("kind")
        if kind:
            return kind
    return None


# --------------------------------------------------------------------------- #
# Small XML helpers
# --------------------------------------------------------------------------- #


def _register_chart_namespaces() -> None:
    """Pin the classic chart prefixes so serialized parts stay stable."""
    ET.register_namespace("a", A_NS)
    ET.register_namespace("c", C_NS)
    ET.register_namespace("r", R_NS)


def _first_axis(root: ET.Element, local_name: str) -> ET.Element | None:
    return root.find(f".//{{{C_NS}}}{local_name}")


def _axis_id(axis: ET.Element, label: str) -> str:
    ax_id = axis.find(f"{{{C_NS}}}axId")
    value = None if ax_id is None else ax_id.get("val")
    if not value or not value.lstrip("-").isdigit():
        raise FinancialChartRefusal(f"chart template has no {label} axis id")
    return value


def _set_axis_id(axis: ET.Element, value: str) -> None:
    _set_child(axis, "axId", value, _PARENT_CHILD_ORDER["valAx"])


def _next_axis_id(existing: Iterable[str]) -> str:
    numbers = [int(value) for value in existing if value.lstrip("-").isdigit()]
    return str(max(numbers, default=1000) + 1)


def _set_plot_axis_ids(plot: ET.Element, category_id: str, value_id: str) -> None:
    axis_ids = plot.findall(f"{{{C_NS}}}axId")
    if len(axis_ids) != 2:
        raise FinancialChartRefusal("chart plot template axis bindings are unavailable")
    axis_ids[0].set("val", category_id)
    axis_ids[1].set("val", value_id)


def _set_child(
    parent: ET.Element,
    local_name: str,
    value: str | None,
    order: Sequence[str],
    *,
    keep_value: bool = True,
) -> ET.Element:
    child = parent.find(f"{{{C_NS}}}{local_name}")
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        _insert_ordered_element(parent, child, order)
    if keep_value and value is not None:
        child.set("val", value)
    return child


def _insert_ordered_element(
    parent: ET.Element,
    element: ET.Element,
    order: Sequence[str],
) -> None:
    target = _xml_local_name(element.tag)
    try:
        target_index = order.index(target)
    except ValueError:
        parent.append(element)
        return
    for index, child in enumerate(list(parent)):
        child_index = (
            order.index(_xml_local_name(child.tag))
            if _xml_local_name(child.tag) in order
            else len(order)
        )
        if child_index > target_index:
            parent.insert(index, element)
            return
    parent.append(element)


def _bar_plot_order() -> tuple[str, ...]:
    return (
        "barDir",
        "grouping",
        "varyColors",
        "ser",
        "dLbls",
        "gapWidth",
        "overlap",
        "serLines",
        "axId",
        "extLst",
    )


def _line_plot_order() -> tuple[str, ...]:
    return (
        "grouping",
        "varyColors",
        "ser",
        "dLbls",
        "dropLines",
        "hiLowLines",
        "upDownBars",
        "marker",
        "smooth",
        "axId",
        "extLst",
    )


def _line_series_order() -> tuple[str, ...]:
    return (
        "idx",
        "order",
        "tx",
        "spPr",
        "marker",
        "dPt",
        "dLbls",
        "trendline",
        "errBars",
        "cat",
        "val",
        "smooth",
        "extLst",
    )


def _series_child_index(series_element: ET.Element, local_name: str) -> int:
    order = _line_series_order()
    target = order.index(local_name) if local_name in order else len(order)
    for index, child in enumerate(list(series_element)):
        name = _xml_local_name(child.tag)
        if name in order and order.index(name) > target:
            return index
    return len(series_element)


def _chart_number_text(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value)


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #


def _financial_chart_receipt(
    source: Path,
    destination: Path,
    *,
    source_sha256: str,
    output_sha256: str,
    source_parts: dict[str, bytes],
    slide_index: int,
    shape_name: str,
    kind: str,
    representation: str,
    categories: list[str],
    series_names: list[str],
    chart_part: str | None = None,
) -> FinancialChartReceipt:
    """Build the receipt for one published financial chart.

    ``source_sha256`` and ``output_sha256`` are the raw file digests of the
    input deck as snapshot and of the published output, so a caller can compare
    them against the files on disk directly.
    """
    output_parts = _read_package_parts(destination)
    changed = sorted(
        name
        for name in set(source_parts) | set(output_parts)
        if source_parts.get(name) != output_parts.get(name)
    )
    if chart_part is None:
        chart_part = _first_chart_part_created(source_parts, output_parts)
    workbook_part = _chart_workbook_part(output_parts, chart_part)
    return FinancialChartReceipt(
        input_path=str(source),
        output_path=str(destination),
        slide_index=slide_index,
        shape_name=shape_name,
        kind=kind,
        representation=representation,
        categories=list(categories),
        series_names=list(series_names),
        chart_part=chart_part,
        workbook_part=workbook_part,
        source_sha256=source_sha256,
        output_sha256=output_sha256,
        changed_parts=changed,
        unchanged_part_count=sum(
            1
            for name in source_parts
            if name in output_parts and source_parts[name] == output_parts[name]
        ),
        source_slide_count=_slide_part_count(source_parts),
        output_slide_count=_slide_part_count(output_parts),
    )


def _first_chart_part_created(
    source_parts: dict[str, bytes],
    output_parts: dict[str, bytes],
) -> str:
    created = sorted(
        name
        for name in output_parts
        if name.startswith("ppt/charts/")
        and name.endswith(".xml")
        and name not in source_parts
    )
    if not created:
        created = sorted(
            name
            for name in output_parts
            if name.startswith("ppt/charts/") and name.endswith(".xml")
        )
    if not created:
        raise FinancialChartRefusal("authored chart part is unavailable")
    return created[0]


def _chart_workbook_part(parts: dict[str, bytes], chart_part: str) -> str:
    parent, filename = chart_part.rsplit("/", 1)
    rels_part = f"{parent}/_rels/{filename}.rels"
    payload = parts.get(rels_part)
    if payload is None:
        raise FinancialChartRefusal("authored chart relationship part is unavailable")
    root = ET.fromstring(payload)
    for relationship in root:
        target = relationship.get("Target") or ""
        if target.endswith(".xlsx"):
            return _resolve_target(chart_part, target)
    raise FinancialChartRefusal("authored chart has no embedded workbook")


def _resolve_target(part_name: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(part_name), target))


def _read_package_parts(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as package:
        return {name: package.read(name) for name in package.namelist()}


def _slide_part_count(parts: dict[str, bytes]) -> int:
    return sum(
        1
        for name in parts
        if name.startswith("ppt/slides/slide") and name.endswith(".xml")
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _required_sequence(payload: Any, key: str) -> Sequence[Any]:
    if not isinstance(payload, dict):
        raise FinancialChartRefusal("financial chart request must be a JSON object")
    value = payload.get(key)
    if not isinstance(value, (list, tuple)) or not value:
        raise FinancialChartRefusal(
            f"financial chart request needs a non-empty {key!r}"
        )
    return value
