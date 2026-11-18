"""Ordered chart split, plot-layout and picture-fill XML/package mutations.

Schema source: ECMA-376 Part 1, DrawingML Charts (§21.2), dml-chart.xsd:
CT_OfPieChart, CT_CustSplit, CT_ManualLayout, CT_BarSer, CT_AreaSer,
CT_DPt and CT_PictureOptions. Schema transcriptions are available at
https://schemas.liquid-technologies.com/OfficeOpenXML/2006/ct_ofpiechart.html,
https://schemas.liquid-technologies.com/OfficeOpenXML/2006/ct_manuallayout.html,
https://schemas.liquid-technologies.com/OfficeOpenXML/2006/ct_pictureoptions.html
and https://schemas.liquid-technologies.com/OfficeOpenXML/2006/ct_dpt.html.
DrawingML a:blipFill uses CT_BlipFillProperties; image relationships and content
types follow ECMA-376 Part 2 (Open Packaging Conventions). Existing sibling
chart_trendline_xml series orders and background_edits package helpers are reused.
"""

from __future__ import annotations

import hashlib
import math
import numbers
import zipfile
from collections.abc import Mapping
from typing import Any
from xml.etree import ElementTree as ET

from .background_edits import _add_image_relationship, _ensure_content_type
from .chart_trendline_xml import _DEFAULT_SERIES_ORDER, _SERIES_CHILD_ORDERS
from .chart_xml_utils import C_NS
from .package_parts import rels_part_for_package_part

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SPLIT_TYPES = {
    "auto": "auto",
    "position": "pos",
    "value": "val",
    "percent": "percent",
    "custom": "cust",
}
PICTURE_TYPES = {
    "stretch": "stretch",
    "stack": "stack",
    "stack-and-scale": "stackScale",
}
OF_PIE_ORDER = (
    "ofPieType",
    "varyColors",
    "ser",
    "dLbls",
    "gapWidth",
    "splitType",
    "splitPos",
    "custSplit",
    "secondPieSize",
    "serLines",
    "extLst",
)
MANUAL_LAYOUT_ORDER = (
    "layoutTarget",
    "xMode",
    "yMode",
    "wMode",
    "hMode",
    "x",
    "y",
    "w",
    "h",
    "extLst",
)
POINT_ORDER = (
    "idx",
    "invertIfNegative",
    "marker",
    "bubble3D",
    "explosion",
    "spPr",
    "pictureOptions",
    "extLst",
)
PICTURE_OPTIONS_ORDER = (
    "applyToFront",
    "applyToSides",
    "applyToEnd",
    "pictureFormat",
    "pictureStackUnit",
)
_PICTURE_SERIES_FAMILIES = frozenset(
    {"barChart", "bar3DChart", "areaChart", "area3DChart"}
)


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def insert_ordered(
    parent: ET.Element, child: ET.Element, order: tuple[str, ...]
) -> None:
    rank = order.index(local_name(child))
    for index, sibling in enumerate(parent):
        name = local_name(sibling)
        if name in order and order.index(name) > rank:
            parent.insert(index, child)
            return
    parent.append(child)


def set_child(
    parent: ET.Element, name: str, value: Any, order: tuple[str, ...]
) -> None:
    child = parent.find(f"{{{C_NS}}}{name}")
    if child is None:
        child = ET.Element(f"{{{C_NS}}}{name}")
        insert_ordered(parent, child, order)
    child.set("val", str(value))


def plot_element(root: ET.Element, index: int) -> ET.Element:
    from .chart_xml import chart_plot_elements

    plots = chart_plot_elements(root)
    if index < 0 or index >= len(plots):
        raise IndexError("chart plot index out of range")
    return plots[index]


def finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a real number")
    try:
        normalized = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be a finite OOXML double") from exc
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def integer_in_range(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(f"{name} must be an integer")
    value = int(value)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be in range {minimum} to {maximum}")
    return value


def normalize_plot_property(name: str, value: Any) -> Any:
    if name == "split_type":
        if not isinstance(value, str) or value not in SPLIT_TYPES:
            raise ValueError(f"split_type must be one of {tuple(SPLIT_TYPES)}")
        return value
    if name == "split_value":
        return finite_number(value, name)
    if name == "second_plot_size":
        return integer_in_range(value, name, 5, 200)
    if name == "gap_width":
        return integer_in_range(value, name, 0, 500)
    if name == "split_custom_points":
        return sorted(
            {integer_in_range(index, "point index", 0, 4294967295) for index in value}
        )
    raise ValueError(f"unsupported chart plot property: {name!r}")


def set_plot_option(plot: ET.Element, name: str, value: Any) -> None:
    value = normalize_plot_property(name, value)
    if local_name(plot) != "ofPieChart":
        if name != "gap_width" or local_name(plot) not in {"barChart", "bar3DChart"}:
            raise AttributeError(f"{name} is only available on of-pie plots")
        from .chart_xml import _set_chart_plot_property

        _set_chart_plot_property(plot, name, value)
        return
    if name == "split_custom_points":
        custom = plot.find(f"{{{C_NS}}}custSplit")
        if custom is None:
            custom = ET.Element(f"{{{C_NS}}}custSplit")
            insert_ordered(plot, custom, OF_PIE_ORDER)
        for child in list(custom):
            if child.tag == f"{{{C_NS}}}secondPiePt":
                custom.remove(child)
        for index in value:
            ET.SubElement(custom, f"{{{C_NS}}}secondPiePt", {"val": str(index)})
        return
    xml_name = {
        "split_type": "splitType",
        "split_value": "splitPos",
        "second_plot_size": "secondPieSize",
        "gap_width": "gapWidth",
    }[name]
    set_child(
        plot,
        xml_name,
        SPLIT_TYPES[value] if name == "split_type" else value,
        OF_PIE_ORDER,
    )


def apply_plot_options(
    root: ET.Element, options: Mapping[str, Mapping[str, Any]]
) -> None:
    for index, properties in options.items():
        plot = plot_element(root, int(index))
        for name, value in properties.items():
            set_plot_option(plot, name, value)


def plot_area_element(root: ET.Element) -> ET.Element:
    plot_area = root.find(f".//{{{C_NS}}}plotArea")
    if plot_area is None:
        raise AttributeError("chart plot area is unavailable")
    return plot_area


def plot_area_layout(root: ET.Element) -> dict[str, Any]:
    manual = plot_area_element(root).find(f"{{{C_NS}}}layout/{{{C_NS}}}manualLayout")
    result: dict[str, Any] = {"layout_target": "outer", "manual_layout": {}}
    if manual is None:
        return result
    target = manual.find(f"{{{C_NS}}}layoutTarget")
    if target is not None:
        result["layout_target"] = target.get("val", "outer")
    for name in MANUAL_LAYOUT_ORDER[1:-1]:
        child = manual.find(f"{{{C_NS}}}{name}")
        if child is not None:
            value = child.get("val", "factor" if name.endswith("Mode") else "0")
            result["manual_layout"][name] = (
                value if name.endswith("Mode") else float(value)
            )
    return result


def normalize_manual_layout(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("manual_layout must be a mapping or None")
    normalized: dict[str, Any] = {}
    for name, item in value.items():
        if name not in MANUAL_LAYOUT_ORDER[1:-1]:
            raise ValueError(f"unsupported manual layout key: {name!r}")
        if name.endswith("Mode"):
            if not isinstance(item, str) or item not in {"factor", "edge"}:
                raise ValueError(f"{name} must be 'factor' or 'edge'")
            normalized[name] = item
        else:
            normalized[name] = finite_number(item, name)
    return normalized


def set_plot_area_layout(root: ET.Element, state: Mapping[str, Any]) -> None:
    target = state.get("layout_target", "outer")
    if target not in {"inner", "outer"}:
        raise ValueError("layout_target must be 'inner' or 'outer'")
    values = normalize_manual_layout(state.get("manual_layout"))
    area = plot_area_element(root)
    layout = area.find(f"{{{C_NS}}}layout")
    if layout is None:
        layout = ET.Element(f"{{{C_NS}}}layout")
        area.insert(0, layout)
    manual = layout.find(f"{{{C_NS}}}manualLayout")
    if manual is None:
        manual = ET.Element(f"{{{C_NS}}}manualLayout")
        layout.insert(0, manual)
    for child in list(manual):
        if local_name(child) in MANUAL_LAYOUT_ORDER[:-1]:
            manual.remove(child)
    set_child(manual, "layoutTarget", target, MANUAL_LAYOUT_ORDER)
    for name in MANUAL_LAYOUT_ORDER[1:-1]:
        if name in values:
            set_child(manual, name, values[name], MANUAL_LAYOUT_ORDER)


def series_and_plot(root: ET.Element, index: int) -> tuple[ET.Element, ET.Element]:
    from .chart_xml import chart_plot_elements

    fallback = 0
    for plot in chart_plot_elements(root):
        for series in plot.findall(f"{{{C_NS}}}ser"):
            idx = series.find(f"{{{C_NS}}}idx")
            actual = int(idx.get("val", str(fallback))) if idx is not None else fallback
            if actual == index:
                return series, plot
            fallback += 1
    raise IndexError("chart series index out of range")


def series_order(plot: ET.Element) -> tuple[str, ...]:
    family = local_name(plot)
    if family in {"pieChart", "pie3DChart", "doughnutChart", "ofPieChart"}:
        return (
            "idx",
            "order",
            "tx",
            "spPr",
            "explosion",
            "dPt",
            "dLbls",
            "cat",
            "val",
            "extLst",
        )
    return _SERIES_CHILD_ORDERS.get(
        family.replace("3DChart", "Chart"), _DEFAULT_SERIES_ORDER
    )


def picture_target(
    root: ET.Element,
    series_index: int,
    point_index: int | None,
    *,
    create: bool = False,
) -> tuple[ET.Element | None, ET.Element]:
    series, plot = series_and_plot(root, series_index)
    if point_index is None:
        return series, plot
    for point in series.findall(f"{{{C_NS}}}dPt"):
        idx = point.find(f"{{{C_NS}}}idx")
        if idx is not None and int(idx.get("val", "0")) == point_index:
            return point, plot
    if not create:
        return None, plot
    point = ET.Element(f"{{{C_NS}}}dPt")
    ET.SubElement(point, f"{{{C_NS}}}idx", {"val": str(point_index)})
    insert_ordered(series, point, series_order(plot))
    return point, plot


def validate_picture_options(
    plot: ET.Element, picture_type: str, point_index: int | None
) -> None:
    if not isinstance(picture_type, str) or picture_type not in PICTURE_TYPES:
        raise ValueError(f"picture_type must be one of {tuple(PICTURE_TYPES)}")
    if (
        point_index is None
        and picture_type != "stretch"
        and local_name(plot) not in _PICTURE_SERIES_FAMILIES
    ):
        raise ValueError(
            "series stack picture fills require a bar or area plot; use point_index for other plots"
        )


def set_picture_fill_xml(
    root: ET.Element, spec: Mapping[str, Any], relationship_id: str | None
) -> None:
    point_index = spec.get("point_index")
    target, plot = picture_target(
        root, int(spec["series_index"]), point_index, create=True
    )
    picture_type = spec["picture_type"]
    validate_picture_options(plot, picture_type, point_index)
    stack_unit = finite_number(spec["stack_unit"], "stack_unit")
    if stack_unit <= 0:
        raise ValueError("stack_unit must be greater than zero")
    order = POINT_ORDER if point_index is not None else series_order(plot)
    shape_properties = target.find(f"{{{C_NS}}}spPr")
    if shape_properties is None:
        shape_properties = ET.Element(f"{{{C_NS}}}spPr")
        insert_ordered(target, shape_properties, order)
    for child in list(shape_properties):
        if local_name(child) in {
            "noFill",
            "solidFill",
            "gradFill",
            "blipFill",
            "pattFill",
            "grpFill",
        }:
            shape_properties.remove(child)
    fill = ET.Element(f"{{{A_NS}}}blipFill", {"rotWithShape": "1"})
    blip = ET.SubElement(fill, f"{{{A_NS}}}blip")
    if relationship_id is not None:
        blip.set(f"{{{R_NS}}}embed", relationship_id)
    ET.SubElement(ET.SubElement(fill, f"{{{A_NS}}}stretch"), f"{{{A_NS}}}fillRect")
    # CT_ShapeProperties: geometry precedes fill, which precedes line/effects.
    insertion = len(shape_properties)
    for index, child in enumerate(shape_properties):
        if local_name(child) in {
            "ln",
            "effectLst",
            "effectDag",
            "scene3d",
            "sp3d",
            "extLst",
        }:
            insertion = index
            break
    shape_properties.insert(insertion, fill)
    if point_index is not None or local_name(plot) in _PICTURE_SERIES_FAMILIES:
        options = target.find(f"{{{C_NS}}}pictureOptions")
        if options is None:
            options = ET.Element(f"{{{C_NS}}}pictureOptions")
            insert_ordered(target, options, order)
        set_child(
            options, "pictureFormat", PICTURE_TYPES[picture_type], PICTURE_OPTIONS_ORDER
        )
        # CT_PictureStackUnit applies only to stackScale. PowerPoint refuses
        # pictureOptions carrying this child with stretch or stack.
        unit = options.find(f"{{{C_NS}}}pictureStackUnit")
        if picture_type == "stack-and-scale":
            set_child(options, "pictureStackUnit", stack_unit, PICTURE_OPTIONS_ORDER)
        elif unit is not None:
            options.remove(unit)


def picture_fill_descriptor(target: ET.Element | None) -> dict[str, Any] | None:
    if target is None:
        return None
    fill = target.find(f"{{{C_NS}}}spPr/{{{A_NS}}}blipFill")
    if fill is None:
        return None
    blip = fill.find(f"{{{A_NS}}}blip")
    options = target.find(f"{{{C_NS}}}pictureOptions")
    format_node = None if options is None else options.find(f"{{{C_NS}}}pictureFormat")
    unit_node = None if options is None else options.find(f"{{{C_NS}}}pictureStackUnit")
    token = "stretch" if format_node is None else format_node.get("val", "stretch")
    return {
        "picture_type": {token: name for name, token in PICTURE_TYPES.items()}.get(
            token, token
        ),
        "stack_unit": 1.0 if unit_node is None else float(unit_node.get("val", "1")),
        "relationship_id": None if blip is None else blip.get(f"{{{R_NS}}}embed"),
    }


def materialize_picture_fills(
    package: zipfile.ZipFile,
    replacements: dict[str, bytes],
    chart_part: str,
    chart_xml: bytes,
    specs: Mapping[str, Mapping[str, Any]],
) -> bytes:
    """Embed queued images without deleting unrelated parts or relationships."""
    root = ET.fromstring(chart_xml)
    names = set(package.namelist()) | set(replacements)
    for spec in specs.values():
        blob = spec["blob"]
        extension = spec["extension"]
        digest = hashlib.sha256(blob).hexdigest()
        base = f"ppt/media/chart-picture-{digest}"
        media_part = f"{base}.{extension}"
        counter = 1
        while media_part in names:
            existing = replacements.get(media_part)
            if existing is None:
                existing = package.read(media_part)
            if existing == blob:
                break
            media_part = f"{base}-{counter}.{extension}"
            counter += 1
        if media_part not in names:
            replacements[media_part] = blob
            names.add(media_part)
        _ensure_content_type(package, replacements, extension)
        rel_id = _add_image_relationship(
            package,
            replacements,
            rels_part_for_package_part(chart_part),
            media_part,
            chart_part,
        )
        set_picture_fill_xml(root, spec, rel_id)
    ET.register_namespace("c", C_NS)
    ET.register_namespace("a", A_NS)
    ET.register_namespace("r", R_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
