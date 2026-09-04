"""XML navigation helpers for chart point facade objects."""

from __future__ import annotations

import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from .chart_edits import _chart_part_for_slide_shape
from .chart_xml import chart_container_element as _chart_container_element

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def chart_series_element(shape: Any, series_index: int) -> ET.Element:
    chart_element = _first_chart_plot_element(shape)
    if chart_element is None:
        return ET.Element(f"{{{C_NS}}}ser")
    for fallback_index, series in enumerate(chart_element.findall(f"{{{C_NS}}}ser")):
        raw_index = series.find(f"{{{C_NS}}}idx")
        if (
            raw_index is not None
            and int(raw_index.attrib.get("val", fallback_index)) == series_index
        ):
            return series
        if raw_index is None and fallback_index == series_index:
            return series
    return ET.Element(f"{{{C_NS}}}ser")


def chart_series_data_labels_text_default_run_properties(
    shape: Any,
    series_index: int,
) -> ET.Element | None:
    series = chart_series_element(shape, series_index)
    data_labels = series.find(f"{{{C_NS}}}dLbls")
    if data_labels is None:
        return None
    return data_labels.find(
        f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )


def _shape_chart_root(shape: Any) -> ET.Element:
    cached = shape._payload.get("_chart_root")
    if isinstance(cached, ET.Element):
        return cached
    chart_part = _shape_chart_part(shape)
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(chart_part))
    shape._payload["_chart_root"] = root
    return root


def _shape_chart_part(shape: Any) -> str:
    relationship_ids = [
        str(rel_id) for rel_id in shape._payload.get("relationship_ids") or []
    ]
    return _chart_part_for_slide_shape(
        shape._slide._presentation.path,
        shape._slide.partname,
        relationship_ids,
    )


def _first_chart_plot_element(shape: Any) -> ET.Element | None:
    root = _shape_chart_root(shape)
    chart = _chart_container_element(root)
    if chart is None:
        return None
    plot_area = chart.find(f"{{{C_NS}}}plotArea")
    if plot_area is None:
        return None
    for child in list(plot_area):
        if child.tag.endswith("Chart"):
            return child
    return None


def _chart_point_element(
    shape: Any,
    series_index: int,
    point_index: int,
    *,
    create: bool = False,
) -> ET.Element:
    series = chart_series_element(shape, series_index)
    for fallback_index, point in enumerate(series.findall(f"{{{C_NS}}}dPt")):
        raw_index = point.find(f"{{{C_NS}}}idx")
        if (
            raw_index is not None
            and int(raw_index.attrib.get("val", fallback_index)) == point_index
        ):
            return point
        if raw_index is None and fallback_index == point_index:
            return point
    point = ET.Element(f"{{{C_NS}}}dPt")
    ET.SubElement(point, f"{{{C_NS}}}idx", {"val": str(point_index)})
    if create:
        series.insert(_series_child_insert_index(series, "dPt"), point)
    return point


def _chart_point_data_label_element(
    shape: Any,
    series_index: int,
    point_index: int,
    *,
    create: bool = False,
) -> ET.Element:
    series = chart_series_element(shape, series_index)
    data_labels = series.find(f"{{{C_NS}}}dLbls")
    if data_labels is None:
        if not create:
            label = ET.Element(f"{{{C_NS}}}dLbl")
            ET.SubElement(label, f"{{{C_NS}}}idx", {"val": str(point_index)})
            return label
        data_labels = _chart_series_data_labels_element(series)
    for fallback_index, label in enumerate(data_labels.findall(f"{{{C_NS}}}dLbl")):
        raw_index = label.find(f"{{{C_NS}}}idx")
        if (
            raw_index is not None
            and int(raw_index.attrib.get("val", fallback_index)) == point_index
        ):
            return label
        if raw_index is None and fallback_index == point_index:
            return label
    label = _new_point_data_label(point_index)
    if create:
        data_labels.insert(_data_label_insert_index(data_labels, "dLbl"), label)
    return label


def _chart_point_marker_element(
    shape: Any,
    series_index: int,
    point_index: int,
    *,
    create: bool = False,
) -> ET.Element:
    point = _chart_point_element(shape, series_index, point_index, create=create)
    marker = point.find(f"{{{C_NS}}}marker")
    if marker is not None:
        return marker
    marker = ET.Element(f"{{{C_NS}}}marker")
    if create:
        point.insert(_dpt_child_insert_index(point, "marker"), marker)
    return marker


def _chart_series_data_labels_element(series: ET.Element) -> ET.Element:
    data_labels = series.find(f"{{{C_NS}}}dLbls")
    if data_labels is not None:
        return data_labels
    data_labels = ET.Element(f"{{{C_NS}}}dLbls")
    _set_bool_child(data_labels, "showLegendKey", False)
    _set_bool_child(data_labels, "showVal", False)
    _set_bool_child(data_labels, "showCatName", False)
    _set_bool_child(data_labels, "showSerName", False)
    _set_bool_child(data_labels, "showPercent", False)
    _set_bool_child(data_labels, "showBubbleSize", False)
    _set_bool_child(data_labels, "showLeaderLines", True)
    series.insert(_series_child_insert_index(series, "dLbls"), data_labels)
    return data_labels


def _new_point_data_label(point_index: int) -> ET.Element:
    label = ET.Element(f"{{{C_NS}}}dLbl")
    ET.SubElement(label, f"{{{C_NS}}}idx", {"val": str(point_index)})
    _set_bool_child(label, "showLegendKey", False)
    _set_bool_child(label, "showVal", True)
    _set_bool_child(label, "showCatName", False)
    _set_bool_child(label, "showSerName", False)
    _set_bool_child(label, "showPercent", False)
    _set_bool_child(label, "showBubbleSize", False)
    return label


def _set_bool_child(element: ET.Element, local_name: str, enabled: bool) -> None:
    child = element.find(f"{{{C_NS}}}{local_name}")
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{local_name}")
        element.insert(_data_label_insert_index(element, local_name), child)
    child.set("val", "1" if enabled else "0")


def _series_child_insert_index(series: ET.Element, local_name: str) -> int:
    order = {
        "idx": 0,
        "order": 1,
        "tx": 2,
        "spPr": 3,
        "dPt": 4,
        "dLbls": 5,
        "cat": 6,
        "val": 7,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(series)
    for index, child in enumerate(list(series)):
        child_order = order.get(child.tag.rsplit("}", 1)[-1])
        if child_order is not None and child_order > target_order:
            return index
    return len(series)


def _dpt_child_insert_index(point: ET.Element, local_name: str) -> int:
    order = {
        "idx": 0,
        "invertIfNegative": 1,
        "marker": 2,
        "bubble3D": 3,
        "explosion": 4,
        "spPr": 5,
        "pictureOptions": 6,
        "extLst": 7,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(point)
    for index, child in enumerate(list(point)):
        child_order = order.get(child.tag.rsplit("}", 1)[-1])
        if child_order is not None and child_order > target_order:
            return index
    return len(point)


def _marker_child_insert_index(marker: ET.Element, local_name: str) -> int:
    order = {
        "symbol": 0,
        "size": 1,
        "spPr": 2,
        "extLst": 3,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(marker)
    for index, child in enumerate(list(marker)):
        child_order = order.get(child.tag.rsplit("}", 1)[-1])
        if child_order is not None and child_order > target_order:
            return index
    return len(marker)


def _data_label_insert_index(label: ET.Element, local_name: str) -> int:
    order = {
        "dLbl": 0,
        "idx": 1,
        "tx": 2,
        "numFmt": 3,
        "spPr": 4,
        "txPr": 5,
        "dLblPos": 6,
        "showLegendKey": 7,
        "showVal": 8,
        "showCatName": 9,
        "showSerName": 10,
        "showPercent": 11,
        "showBubbleSize": 12,
        "separator": 13,
        "showLeaderLines": 14,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(label)
    for index, child in enumerate(list(label)):
        child_order = order.get(child.tag.rsplit("}", 1)[-1])
        if child_order is not None and child_order > target_order:
            return index
    return len(label)
