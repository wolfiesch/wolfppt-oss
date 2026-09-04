"""Internal chart facade payload and XML mutation helpers."""

from __future__ import annotations

import zipfile
from numbers import Integral
from typing import Any
from xml.etree import ElementTree as ET

from .chart_edits import _chart_part_for_slide_shape
from .chart_xml import (
    chart_axis_element as _chart_axis_element,
    chart_container_element as _chart_container_element,
    default_chart_axis_payload as _default_chart_axis_payload,
    default_chart_data_labels_payload as _default_chart_data_labels_payload,
    parse_chart_root as _parse_chart_root,
)
from .dml_fill import (
    no_fill_element as _no_fill_element,
    set_shape_pattern_fill as _set_shape_pattern_fill,
    solid_fill_element as _solid_fill_element,
)

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def normalize_tick_label_offset(value: Any) -> int:
    if not isinstance(value, Integral):
        raise TypeError(f"value must be an integral type, got {type(value)}")
    offset = int(value)
    if offset < 0 or offset > 1000:
        raise ValueError(f"value must be in range 0 to 1000 inclusive, got {offset}")
    return offset


def normalize_chart_plot_int(value: Any, *, minimum: int, maximum: int) -> int:
    if not isinstance(value, Integral):
        raise TypeError(f"value must be an integral type, got {type(value)}")
    normalized = int(value)
    if normalized < minimum or normalized > maximum:
        raise ValueError(
            f"value must be in range {minimum} to {maximum} inclusive, got {normalized}"
        )
    return normalized


def chart_payload(shape: Any) -> dict[str, Any]:
    cached = shape._payload.get("_chart_payload")
    if isinstance(cached, dict):
        return cached
    chart_part = shape_chart_part(shape)
    cached_root = shape._payload.get("_chart_root")
    if isinstance(cached_root, ET.Element):
        root = cached_root
    else:
        with zipfile.ZipFile(shape._slide._presentation.path) as package:
            chart_xml = package.read(chart_part)
        root = ET.fromstring(chart_xml)
        shape._payload["_chart_root"] = root
    payload = _parse_chart_root(root)
    payload["part"] = chart_part
    shape._payload["_chart_payload"] = payload
    return payload


def chart_axis_payload(shape: Any, axis: str) -> dict[str, Any]:
    payload = chart_payload(shape)
    axes = payload.setdefault("axes", {})
    if not isinstance(axes, dict):
        axes = {}
        payload["axes"] = axes
    axis_payload = axes.setdefault(
        axis,
        _default_chart_axis_payload(),
    )
    if not isinstance(axis_payload, dict):
        axis_payload = _default_chart_axis_payload()
        axes[axis] = axis_payload
    defaults = _default_chart_axis_payload()
    for key, value in defaults.items():
        axis_payload.setdefault(key, value)
    return axis_payload


def chart_data_labels_payload(shape: Any) -> dict[str, Any]:
    payload = chart_payload(shape)
    data_labels = payload.setdefault(
        "data_labels",
        _default_chart_data_labels_payload(),
    )
    if not isinstance(data_labels, dict):
        data_labels = _default_chart_data_labels_payload()
        payload["data_labels"] = data_labels
    defaults = _default_chart_data_labels_payload()
    for key, value in defaults.items():
        data_labels.setdefault(key, value)
    return data_labels


def chart_title_proxy_element(shape: Any, *, create: bool = False) -> ET.Element:
    root = shape_chart_root(shape)
    chart = _chart_container_element(root)
    if chart is None:
        raise AttributeError("chart element is unavailable")
    title = chart.find(f"{{{C_NS}}}title")
    if title is not None:
        return title
    if create:
        title = ET.Element(f"{{{C_NS}}}title")
        insert_at = len(chart)
        for index, child in enumerate(list(chart)):
            if child.tag in {f"{{{C_NS}}}autoTitleDeleted", f"{{{C_NS}}}plotArea"}:
                insert_at = index
                break
        chart.insert(insert_at, title)
        return title
    return ET.Element(f"{{{C_NS}}}title")


def shape_chart_root(shape: Any) -> ET.Element:
    cached = shape._payload.get("_chart_root")
    if isinstance(cached, ET.Element):
        return cached
    chart_part = shape_chart_part(shape)
    with zipfile.ZipFile(shape._slide._presentation.path) as package:
        root = ET.fromstring(package.read(chart_part))
    shape._payload["_chart_root"] = root
    return root


def chart_axis_proxy_element(shape: Any, axis: str) -> ET.Element:
    root = shape_chart_root(shape)
    chart = _chart_container_element(root)
    axis_element = None if chart is None else _chart_axis_element(chart, axis)
    if axis_element is None:
        tag = "catAx" if axis == "cat" else "valAx"
        return ET.Element(f"{{{C_NS}}}{tag}")
    return axis_element


def chart_axis_major_gridlines_element(
    shape: Any,
    axis: str,
    *,
    create: bool = False,
) -> ET.Element:
    axis_element = chart_axis_proxy_element(shape, axis)
    gridlines = axis_element.find(f"{{{C_NS}}}majorGridlines")
    if gridlines is not None:
        return gridlines
    gridlines = ET.Element(f"{{{C_NS}}}majorGridlines")
    if create:
        axis_element.insert(
            _chart_axis_insert_index(axis_element, "majorGridlines"),
            gridlines,
        )
    return gridlines


def _chart_axis_insert_index(axis_element: ET.Element, local_name: str) -> int:
    order = {
        "axId": 0,
        "scaling": 1,
        "delete": 2,
        "axPos": 3,
        "majorGridlines": 4,
        "minorGridlines": 5,
        "title": 6,
        "numFmt": 7,
        "majorTickMark": 8,
        "minorTickMark": 9,
        "tickLblPos": 10,
        "spPr": 11,
        "txPr": 12,
        "crossAx": 13,
        "crosses": 14,
        "crossesAt": 15,
        "crossBetween": 16,
        "auto": 17,
        "lblAlgn": 18,
        "lblOffset": 19,
        "tickLblSkip": 20,
        "tickMarkSkip": 21,
        "noMultiLvlLbl": 22,
        "majorUnit": 23,
        "minorUnit": 24,
        "dispUnits": 25,
        "extLst": 26,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(axis_element)
    for index, child in enumerate(list(axis_element)):
        child_local_name = child.tag.rsplit("}", 1)[-1]
        child_order = order.get(child_local_name)
        if child_order is not None and child_order > target_order:
            return index
    return len(axis_element)


def chart_text_default_run_properties(
    shape: Any,
    *,
    create: bool = False,
) -> ET.Element | None:
    root = shape_chart_root(shape)
    text_properties = root.find(f"{{{C_NS}}}txPr")
    if text_properties is None:
        if not create:
            return None
        text_properties = ET.Element(f"{{{C_NS}}}txPr")
        text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
        text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
        paragraph = ET.Element(f"{{{A_NS}}}p")
        paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
        text_properties.append(paragraph)
        root.insert(_chart_space_txpr_insert_index(root), text_properties)
    return text_properties.find(
        f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )


def _chart_space_txpr_insert_index(root: ET.Element) -> int:
    for index, child in enumerate(list(root)):
        if child.tag in {
            f"{{{C_NS}}}externalData",
            f"{{{C_NS}}}printSettings",
            f"{{{C_NS}}}userShapes",
            f"{{{C_NS}}}extLst",
        }:
            return index
    return len(root)


def chart_axis_text_default_run_properties(
    shape: Any,
    axis: str,
) -> ET.Element | None:
    axis_element = chart_axis_proxy_element(shape, axis)
    return axis_element.find(
        f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )


def chart_data_labels_text_default_run_properties(shape: Any) -> ET.Element | None:
    chart_element = first_chart_plot_element(shape)
    if chart_element is None:
        return None
    data_labels = chart_element.find(f"{{{C_NS}}}dLbls")
    if data_labels is None:
        return None
    return data_labels.find(
        f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )


def chart_legend_text_default_run_properties(
    shape: Any,
    *,
    create: bool = False,
) -> ET.Element | None:
    root = shape_chart_root(shape)
    chart = _chart_container_element(root)
    if chart is None:
        return None
    legend = chart.find(f"{{{C_NS}}}legend")
    if legend is None:
        if not create:
            return None
        legend = ET.Element(f"{{{C_NS}}}legend")
        chart.insert(_chart_legend_insert_index(chart), legend)
    text_properties = legend.find(f"{{{C_NS}}}txPr")
    if text_properties is None:
        if not create:
            return None
        text_properties = ET.Element(f"{{{C_NS}}}txPr")
        text_properties.append(ET.Element(f"{{{A_NS}}}bodyPr"))
        text_properties.append(ET.Element(f"{{{A_NS}}}lstStyle"))
        paragraph = ET.Element(f"{{{A_NS}}}p")
        paragraph_properties = ET.SubElement(paragraph, f"{{{A_NS}}}pPr")
        ET.SubElement(paragraph_properties, f"{{{A_NS}}}defRPr")
        text_properties.append(paragraph)
        legend.insert(_chart_legend_txpr_insert_index(legend), text_properties)
    return text_properties.find(
        f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr"
    )


def _chart_legend_insert_index(chart: ET.Element) -> int:
    insert_at = len(chart)
    for index, child in enumerate(list(chart)):
        if child.tag in {
            f"{{{C_NS}}}dispBlanksAs",
            f"{{{C_NS}}}plotVisOnly",
            f"{{{C_NS}}}showDLblsOverMax",
            f"{{{C_NS}}}extLst",
        }:
            return index
    plot_area = chart.find(f"{{{C_NS}}}plotArea")
    if plot_area is not None:
        insert_at = list(chart).index(plot_area) + 1
    return insert_at


def _chart_legend_txpr_insert_index(legend: ET.Element) -> int:
    for index, child in enumerate(list(legend)):
        if child.tag == f"{{{C_NS}}}extLst":
            return index
    return len(legend)


def set_chart_element_solid_fill(element: ET.Element) -> None:
    shape_properties = chart_element_shape_properties(element)
    for child in list(shape_properties):
        if child.tag in {
            f"{{{A_NS}}}noFill",
            f"{{{A_NS}}}solidFill",
            f"{{{A_NS}}}gradFill",
            f"{{{A_NS}}}blipFill",
            f"{{{A_NS}}}pattFill",
            f"{{{A_NS}}}grpFill",
        }:
            shape_properties.remove(child)
    shape_properties.insert(0, ET.Element(f"{{{A_NS}}}solidFill"))


def set_chart_element_fill_rgb(element: ET.Element, rgb: str) -> None:
    shape_properties = chart_element_shape_properties(element)
    solid_fill = shape_properties.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        set_chart_element_solid_fill(element)
        solid_fill = shape_properties.find(f"{{{A_NS}}}solidFill")
    assert solid_fill is not None
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def set_chart_element_line_rgb(element: ET.Element, rgb: str) -> None:
    shape_properties = chart_element_shape_properties(element)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    solid_fill = line.find(f"{{{A_NS}}}solidFill")
    if solid_fill is None:
        solid_fill = ET.Element(f"{{{A_NS}}}solidFill")
        line.insert(0, solid_fill)
    for child in list(solid_fill):
        solid_fill.remove(child)
    ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": rgb})


def set_chart_element_line_width(element: ET.Element, width: int) -> None:
    shape_properties = chart_element_shape_properties(element)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    line.set("w", str(width))


def set_chart_element_line_dash(element: ET.Element, dash_style: Any) -> None:
    shape_properties = chart_element_shape_properties(element)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    preset_dash = line.find(f"{{{A_NS}}}prstDash")
    if dash_style is None:
        if preset_dash is not None:
            line.remove(preset_dash)
        return
    if preset_dash is None:
        preset_dash = ET.Element(f"{{{A_NS}}}prstDash")
        line.append(preset_dash)
    preset_dash.set("val", str(dash_style))


def set_chart_element_line_fill_type(element: ET.Element, fill_type: str) -> None:
    shape_properties = chart_element_shape_properties(element)
    line = shape_properties.find(f"{{{A_NS}}}ln")
    if line is None:
        line = ET.Element(f"{{{A_NS}}}ln")
        shape_properties.append(line)
    if fill_type == "solid":
        _solid_fill_element(line)
        return
    if fill_type == "background":
        _no_fill_element(line)
        return
    if fill_type == "patterned":
        _set_shape_pattern_fill(line, None)
        return
    raise ValueError(f"unsupported chart line fill type: {fill_type!r}")


def chart_element_shape_properties(element: ET.Element) -> ET.Element:
    shape_properties = element.find(f"{{{C_NS}}}spPr")
    if shape_properties is not None:
        return shape_properties
    shape_properties = ET.Element(f"{{{C_NS}}}spPr")
    element.insert(chart_series_child_insert_index(element, "spPr"), shape_properties)
    return shape_properties


def chart_series_child_insert_index(series_element: ET.Element, local_name: str) -> int:
    order = {
        "idx": 0,
        "order": 1,
        "tx": 2,
        "spPr": 3,
        "invertIfNegative": 4,
        "dPt": 5,
        "dLbls": 6,
        "cat": 7,
        "val": 8,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(series_element)
    for index, child in enumerate(list(series_element)):
        child_order = order.get(child.tag.rsplit("}", 1)[-1])
        if child_order is not None and child_order > target_order:
            return index
    return len(series_element)


def first_chart_plot_element(shape: Any) -> ET.Element | None:
    root = shape_chart_root(shape)
    chart = _chart_container_element(root)
    if chart is None:
        return None
    plot_area = chart.find(f"{{{C_NS}}}plotArea")
    if plot_area is None:
        return None
    chart_element = None
    for child in list(plot_area):
        if child.tag.endswith("Chart"):
            chart_element = child
            break
    return chart_element


def shape_chart_part(shape: Any) -> str:
    hinted_part = shape._payload.get("_chart_part")
    if hinted_part:
        return str(hinted_part)
    relationship_ids = [
        str(rel_id) for rel_id in shape._payload.get("relationship_ids") or []
    ]
    return _chart_part_for_slide_shape(
        shape._slide._presentation.path,
        shape._slide.partname,
        relationship_ids,
    )
