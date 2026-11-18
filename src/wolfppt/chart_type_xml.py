"""Chart type payload conversion helpers."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .chart_xml_utils import (
    A_NS,
    C_NS,
    child_val,
)
from .chart_xml_utils import (
    xml_local_name as _xml_local_name,
)
from .enum.chart import XL_CHART_TYPE


def chart_element_type(chart_element: ET.Element) -> dict[str, str | None]:
    kind = _xml_local_name(chart_element.tag)
    payload = {
        "kind": kind,
        "bar_dir": child_val(chart_element, "barDir"),
        "grouping": child_val(chart_element, "grouping"),
        "marker": (
            child_val(chart_element, "wireframe")
            if kind == "surface3DChart"
            else _first_series_marker(chart_element)
        ),
        "explosion": _first_child_value(chart_element, "explosion"),
        "radar_style": child_val(chart_element, "radarStyle"),
        "stock_type": (
            "ohlc" if chart_element.find(f"{{{C_NS}}}upDownBars") is not None else "hlc"
        )
        if kind == "stockChart"
        else None,
    }
    if payload["kind"] == "scatterChart":
        payload["scatter_style"] = child_val(chart_element, "scatterStyle")
        payload["line_no_fill"] = (
            "1" if _first_series_line_no_fill(chart_element) else None
        )
    if payload["kind"] == "bubbleChart":
        payload["bubble_3d"] = _first_child_value(chart_element, "bubble3D")
    return payload


def chart_type_value(payload: Any) -> Any:
    kind = str(payload.get("kind") if isinstance(payload, dict) else payload)
    bar_dir = payload.get("bar_dir") if isinstance(payload, dict) else None
    grouping = payload.get("grouping") if isinstance(payload, dict) else None
    marker = payload.get("marker") if isinstance(payload, dict) else None
    explosion = payload.get("explosion") if isinstance(payload, dict) else None
    radar_style = payload.get("radar_style") if isinstance(payload, dict) else None
    scatter_style = payload.get("scatter_style") if isinstance(payload, dict) else None
    line_no_fill = payload.get("line_no_fill") if isinstance(payload, dict) else None
    bubble_3d = payload.get("bubble_3d") if isinstance(payload, dict) else None
    stock_type = payload.get("stock_type") if isinstance(payload, dict) else None
    chart_name = _chart_type_name(
        kind,
        bar_dir,
        grouping,
        marker,
        explosion,
        radar_style,
        scatter_style,
        line_no_fill,
        bubble_3d,
        stock_type,
    )
    if chart_name is not None:
        return getattr(XL_CHART_TYPE, chart_name)
    return kind


def chart_type_payload_from_value(chart_type: Any) -> dict[str, str | None]:
    chart_name = getattr(chart_type, "name", None)
    try:
        chart_id = int(chart_type)
    except (TypeError, ValueError):
        chart_id = None
    chart_name = chart_name or _CHART_TYPE_NAME_BY_ID.get(chart_id)
    payload = _CHART_TYPE_PAYLOADS.get(chart_name or "")
    if payload is not None:
        return dict(payload)
    return {
        "kind": str(chart_type),
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "radar_style": None,
        "stock_type": None,
    }


_CHART_TYPE_NAME_BY_ID = {
    -4151: "RADAR",
    -4120: "DOUGHNUT",
    -4102: "THREE_D_PIE",
    -4101: "THREE_D_LINE",
    -4100: "THREE_D_COLUMN",
    -4098: "THREE_D_AREA",
    1: "AREA",
    4: "LINE",
    5: "PIE",
    15: "BUBBLE",
    51: "COLUMN_CLUSTERED",
    52: "COLUMN_STACKED",
    53: "COLUMN_STACKED_100",
    54: "THREE_D_COLUMN_CLUSTERED",
    55: "THREE_D_COLUMN_STACKED",
    56: "THREE_D_COLUMN_STACKED_100",
    57: "BAR_CLUSTERED",
    58: "BAR_STACKED",
    59: "BAR_STACKED_100",
    60: "THREE_D_BAR_CLUSTERED",
    61: "THREE_D_BAR_STACKED",
    62: "THREE_D_BAR_STACKED_100",
    63: "LINE_STACKED",
    64: "LINE_STACKED_100",
    65: "LINE_MARKERS",
    66: "LINE_MARKERS_STACKED",
    67: "LINE_MARKERS_STACKED_100",
    69: "PIE_EXPLODED",
    70: "THREE_D_PIE_EXPLODED",
    76: "AREA_STACKED",
    77: "AREA_STACKED_100",
    78: "THREE_D_AREA_STACKED",
    79: "THREE_D_AREA_STACKED_100",
    80: "DOUGHNUT_EXPLODED",
    81: "RADAR_MARKERS",
    82: "RADAR_FILLED",
    83: "SURFACE",
    84: "SURFACE_WIREFRAME",
    88: "STOCK_HLC",
    89: "STOCK_OHLC",
    -4169: "XY_SCATTER",
    72: "XY_SCATTER_SMOOTH",
    73: "XY_SCATTER_SMOOTH_NO_MARKERS",
    74: "XY_SCATTER_LINES",
    75: "XY_SCATTER_LINES_NO_MARKERS",
}

_CHART_TYPE_PAYLOADS = {
    "THREE_D_AREA": {
        "kind": "area3DChart",
        "bar_dir": None,
        "grouping": "standard",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_AREA_STACKED": {
        "kind": "area3DChart",
        "bar_dir": None,
        "grouping": "stacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_AREA_STACKED_100": {
        "kind": "area3DChart",
        "bar_dir": None,
        "grouping": "percentStacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_BAR_CLUSTERED": {
        "kind": "bar3DChart",
        "bar_dir": "bar",
        "grouping": "clustered",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_BAR_STACKED": {
        "kind": "bar3DChart",
        "bar_dir": "bar",
        "grouping": "stacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_BAR_STACKED_100": {
        "kind": "bar3DChart",
        "bar_dir": "bar",
        "grouping": "percentStacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_COLUMN": {
        "kind": "bar3DChart",
        "bar_dir": "col",
        "grouping": "clustered",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_COLUMN_CLUSTERED": {
        "kind": "bar3DChart",
        "bar_dir": "col",
        "grouping": "clustered",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_COLUMN_STACKED": {
        "kind": "bar3DChart",
        "bar_dir": "col",
        "grouping": "stacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_COLUMN_STACKED_100": {
        "kind": "bar3DChart",
        "bar_dir": "col",
        "grouping": "percentStacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_LINE": {
        "kind": "line3DChart",
        "bar_dir": None,
        "grouping": "standard",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_PIE": {
        "kind": "pie3DChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "THREE_D_PIE_EXPLODED": {
        "kind": "pie3DChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": "1",
        "radar_style": None,
    },
    "SURFACE": {
        "kind": "surface3DChart",
        "bar_dir": None,
        "grouping": None,
        "marker": "0",
        "explosion": None,
        "radar_style": None,
    },
    "SURFACE_WIREFRAME": {
        "kind": "surface3DChart",
        "bar_dir": None,
        "grouping": None,
        "marker": "1",
        "explosion": None,
        "radar_style": None,
    },
    "AREA": {
        "kind": "areaChart",
        "bar_dir": None,
        "grouping": "standard",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "AREA_STACKED": {
        "kind": "areaChart",
        "bar_dir": None,
        "grouping": "stacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "AREA_STACKED_100": {
        "kind": "areaChart",
        "bar_dir": None,
        "grouping": "percentStacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "BAR_CLUSTERED": {
        "kind": "barChart",
        "bar_dir": "bar",
        "grouping": "clustered",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "BAR_STACKED": {
        "kind": "barChart",
        "bar_dir": "bar",
        "grouping": "stacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "BAR_STACKED_100": {
        "kind": "barChart",
        "bar_dir": "bar",
        "grouping": "percentStacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "COLUMN_CLUSTERED": {
        "kind": "barChart",
        "bar_dir": "col",
        "grouping": "clustered",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "COLUMN_STACKED": {
        "kind": "barChart",
        "bar_dir": "col",
        "grouping": "stacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "COLUMN_STACKED_100": {
        "kind": "barChart",
        "bar_dir": "col",
        "grouping": "percentStacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "DOUGHNUT": {
        "kind": "doughnutChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "DOUGHNUT_EXPLODED": {
        "kind": "doughnutChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": "25",
        "radar_style": None,
    },
    "LINE": {
        "kind": "lineChart",
        "bar_dir": None,
        "grouping": "standard",
        "marker": "none",
        "explosion": None,
        "radar_style": None,
    },
    "LINE_MARKERS": {
        "kind": "lineChart",
        "bar_dir": None,
        "grouping": "standard",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "LINE_MARKERS_STACKED": {
        "kind": "lineChart",
        "bar_dir": None,
        "grouping": "stacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "LINE_MARKERS_STACKED_100": {
        "kind": "lineChart",
        "bar_dir": None,
        "grouping": "percentStacked",
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "LINE_STACKED": {
        "kind": "lineChart",
        "bar_dir": None,
        "grouping": "stacked",
        "marker": "none",
        "explosion": None,
        "radar_style": None,
    },
    "LINE_STACKED_100": {
        "kind": "lineChart",
        "bar_dir": None,
        "grouping": "percentStacked",
        "marker": "none",
        "explosion": None,
        "radar_style": None,
    },
    "PIE": {
        "kind": "pieChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
    },
    "PIE_EXPLODED": {
        "kind": "pieChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": "25",
        "radar_style": None,
    },
    "RADAR": {
        "kind": "radarChart",
        "bar_dir": None,
        "grouping": None,
        "marker": "none",
        "explosion": None,
        "radar_style": "marker",
    },
    "RADAR_FILLED": {
        "kind": "radarChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": "filled",
    },
    "RADAR_MARKERS": {
        "kind": "radarChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": "marker",
    },
    "XY_SCATTER": {
        "kind": "scatterChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
        "scatter_style": "lineMarker",
        "line_no_fill": "1",
    },
    "XY_SCATTER_LINES": {
        "kind": "scatterChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
        "scatter_style": "lineMarker",
        "line_no_fill": None,
    },
    "XY_SCATTER_LINES_NO_MARKERS": {
        "kind": "scatterChart",
        "bar_dir": None,
        "grouping": None,
        "marker": "none",
        "explosion": None,
        "radar_style": None,
        "scatter_style": "lineMarker",
        "line_no_fill": None,
    },
    "XY_SCATTER_SMOOTH": {
        "kind": "scatterChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
        "scatter_style": "smoothMarker",
        "line_no_fill": None,
    },
    "XY_SCATTER_SMOOTH_NO_MARKERS": {
        "kind": "scatterChart",
        "bar_dir": None,
        "grouping": None,
        "marker": "none",
        "explosion": None,
        "radar_style": None,
        "scatter_style": "smoothMarker",
        "line_no_fill": None,
    },
    "BUBBLE": {
        "kind": "bubbleChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
        "bubble_3d": "0",
    },
    "BUBBLE_THREE_D_EFFECT": {
        "kind": "bubbleChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
        "bubble_3d": "1",
    },
    "STOCK_HLC": {
        "kind": "stockChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
        "stock_type": "hlc",
    },
    "STOCK_OHLC": {
        "kind": "stockChart",
        "bar_dir": None,
        "grouping": None,
        "marker": None,
        "explosion": None,
        "radar_style": None,
        "stock_type": "ohlc",
    },
}


def _chart_type_name(
    kind: str,
    bar_dir: str | None,
    grouping: str | None,
    marker: str | None,
    explosion: str | None,
    radar_style: str | None,
    scatter_style: str | None = None,
    line_no_fill: str | None = None,
    bubble_3d: str | None = None,
    stock_type: str | None = None,
):
    if kind == "bar3DChart":
        return {
            ("col", "clustered"): "THREE_D_COLUMN_CLUSTERED",
            ("col", "stacked"): "THREE_D_COLUMN_STACKED",
            ("col", "percentStacked"): "THREE_D_COLUMN_STACKED_100",
            ("bar", "clustered"): "THREE_D_BAR_CLUSTERED",
            ("bar", "stacked"): "THREE_D_BAR_STACKED",
            ("bar", "percentStacked"): "THREE_D_BAR_STACKED_100",
        }.get((bar_dir, grouping))
    if kind == "area3DChart":
        return {
            "standard": "THREE_D_AREA",
            "stacked": "THREE_D_AREA_STACKED",
            "percentStacked": "THREE_D_AREA_STACKED_100",
        }.get(grouping)
    if kind == "line3DChart":
        return "THREE_D_LINE" if grouping == "standard" else None
    if kind == "pie3DChart":
        return "THREE_D_PIE_EXPLODED" if explosion is not None else "THREE_D_PIE"
    if kind == "surface3DChart":
        return "SURFACE_WIREFRAME" if marker == "1" else "SURFACE"
    if kind == "barChart":
        names = {
            ("col", "clustered"): "COLUMN_CLUSTERED",
            ("col", "stacked"): "COLUMN_STACKED",
            ("col", "percentStacked"): "COLUMN_STACKED_100",
            ("bar", "clustered"): "BAR_CLUSTERED",
            ("bar", "stacked"): "BAR_STACKED",
            ("bar", "percentStacked"): "BAR_STACKED_100",
        }
        return names.get((bar_dir, grouping))
    if kind == "areaChart":
        return {
            "standard": "AREA",
            "stacked": "AREA_STACKED",
            "percentStacked": "AREA_STACKED_100",
        }.get(grouping)
    if kind == "lineChart":
        if marker == "none":
            return {
                "standard": "LINE",
                "stacked": "LINE_STACKED",
                "percentStacked": "LINE_STACKED_100",
            }.get(grouping)
        return {
            "standard": "LINE_MARKERS",
            "stacked": "LINE_MARKERS_STACKED",
            "percentStacked": "LINE_MARKERS_STACKED_100",
        }.get(grouping)
    if kind == "pieChart":
        return "PIE_EXPLODED" if explosion is not None else "PIE"
    if kind == "doughnutChart":
        return "DOUGHNUT_EXPLODED" if explosion is not None else "DOUGHNUT"
    if kind == "radarChart":
        if radar_style == "filled":
            return "RADAR_FILLED"
        return "RADAR" if marker == "none" else "RADAR_MARKERS"
    if kind == "scatterChart":
        if scatter_style == "smoothMarker":
            return (
                "XY_SCATTER_SMOOTH_NO_MARKERS"
                if marker == "none"
                else "XY_SCATTER_SMOOTH"
            )
        if line_no_fill:
            return "XY_SCATTER"
        return "XY_SCATTER_LINES_NO_MARKERS" if marker == "none" else "XY_SCATTER_LINES"
    if kind == "bubbleChart":
        return "BUBBLE_THREE_D_EFFECT" if bubble_3d == "1" else "BUBBLE"
    if kind == "stockChart":
        return {"hlc": "STOCK_HLC", "ohlc": "STOCK_OHLC"}.get(stock_type)
    return None


def _first_series_marker(chart_element: ET.Element) -> str | None:
    first_series = chart_element.find(f"{{{C_NS}}}ser")
    if first_series is None:
        return None
    marker = first_series.find(f"{{{C_NS}}}marker/{{{C_NS}}}symbol")
    if marker is None:
        return None
    return marker.attrib.get("val")


def _first_series_line_no_fill(chart_element: ET.Element) -> bool:
    first_series = chart_element.find(f"{{{C_NS}}}ser")
    if first_series is None:
        return False
    return (
        first_series.find(f"{{{C_NS}}}spPr/{{{A_NS}}}ln/{{{A_NS}}}noFill") is not None
    )


def _first_child_value(chart_element: ET.Element, local_name: str) -> str | None:
    child = chart_element.find(f".//{{{C_NS}}}{local_name}")
    if child is None:
        return None
    return child.attrib.get("val", "")
