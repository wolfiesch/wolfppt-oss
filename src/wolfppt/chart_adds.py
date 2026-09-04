"""Chart package-add helpers for presentation saves."""

from __future__ import annotations

import posixpath
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
from .chart_xml import (
    replace_chart_xml_data as _replace_chart_xml_data,
)
from .chart_workbook import (
    bubble_chart_workbook_blob as _bubble_chart_workbook_blob,
    category_chart_workbook_blob as _category_chart_workbook_blob,
    xy_chart_workbook_blob as _xy_chart_workbook_blob,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
    natural_key as _natural_key,
    rels_part_for_package_part as _rels_part_for_package_part,
    resolve_package_target as _resolve_package_target,
)
from .shape_xml import _next_relationship_id
from .xml_helpers import xml_local_name as _xml_local_name

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"

_CHART_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
)
_PACKAGE_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package"
)
_CHART_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
)
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
    series_items = list(chart_data)
    if hasattr(chart_data, "categories"):
        return _normalize_category_chart_data(chart_data, series_items)
    if _is_bubble_chart_data(chart_data, series_items):
        return _normalize_bubble_chart_data(series_items)
    if _is_xy_chart_data(chart_data, series_items):
        return _normalize_xy_chart_data(series_items)
    return _normalize_category_chart_data(chart_data, series_items)


def _is_bubble_chart_data(chart_data: Any, series_items: list[Any]) -> bool:
    if hasattr(chart_data, "bubble_sizes_ref"):
        return True
    if _looks_like_bubble_chart_data(series_items):
        return True
    return False


def _is_xy_chart_data(chart_data: Any, series_items: list[Any]) -> bool:
    if chart_data.__class__.__name__ == "XyChartData":
        return True
    if _looks_like_xy_chart_data(series_items):
        return True
    return False


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
    return bool(points) and all(
        hasattr(point, "x") and hasattr(point, "y") for point in points
    )


def _normalize_xy_chart_data(series_items: list[Any]) -> dict[str, Any]:
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
            }
        )
    xlsx_blob = _xy_chart_workbook_blob(series_payloads)
    return {
        "data_kind": "xy",
        "categories": [],
        "series": series_payloads,
        "xlsx_blob": xlsx_blob,
    }


def _normalize_bubble_chart_data(series_items: list[Any]) -> dict[str, Any]:
    series_payloads: list[dict[str, Any]] = []
    for series in series_items:
        points = list(series)
        x_values = [float(point.x) for point in points]
        y_values = [float(point.y) for point in points]
        bubble_sizes = [float(point.bubble_size) for point in points]
        if len({len(x_values), len(y_values), len(bubble_sizes)}) != 1:
            raise ValueError(
                "bubble chart x, y, and bubble-size values must have the same length"
            )
        series_payloads.append(
            {
                "name": str(series.name),
                "categories": [],
                "x_values": x_values,
                "values": y_values,
                "bubble_sizes": bubble_sizes,
            }
        )
    xlsx_blob = _bubble_chart_workbook_blob(series_payloads)
    return {
        "data_kind": "bubble",
        "categories": [],
        "series": series_payloads,
        "xlsx_blob": xlsx_blob,
    }


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
            slide_part, slide_root, slide_rels_part, slide_rels_root = slide_states[
                slide_index
            ]
            generated = _generated_chart_package_parts(
                chart_type,
                chart_data,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            )
            chart_part = _next_numbered_part(names, "ppt/charts/chart", ".xml")
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
            _insert_shape_tree_child(target_tree, chart_frame)
            slide_rels_root.append(
                ET.Element(
                    f"{{{PKG_REL_NS}}}Relationship",
                    {
                        "Id": relationship_id,
                        "Type": _CHART_REL_TYPE,
                        "Target": _relative_package_target(slide_part, chart_part),
                    },
                )
            )

            chart_rels_root = generated["chart_rels"]
            _retarget_chart_relationships(chart_rels_root, chart_part, workbook_part)
            _ensure_content_type_override(
                content_types_root,
                chart_part,
                _CHART_CONTENT_TYPE,
            )
            replacements[chart_part] = generated["chart_xml"]
            replacements[chart_rels_part] = ET.tostring(
                chart_rels_root,
                encoding="utf-8",
                xml_declaration=True,
            )
            replacements[workbook_part] = generated["workbook_blob"]

        for slide_part, slide_root, slide_rels_part, slide_rels_root in (
            slide_states.values()
        ):
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
    normalized = (
        chart_data
        if isinstance(chart_data, dict) and "xlsx_blob" in chart_data
        else _normalize_chart_add_data(chart_data)
    )
    template = _generated_chart_template(chart_type)
    graphic_frame = deepcopy(template["graphic_frame"])
    _set_chart_frame_geometry(graphic_frame, x_emu, y_emu, cx_emu, cy_emu)
    chart_xml_data = dict(normalized)
    if (
        normalized.get("data_kind") in {"bubble", "category", "xy"}
        and not normalized["series"]
    ):
        chart_xml_data["_preserve_empty_chart_type"] = True
    return {
        "graphic_frame": graphic_frame,
        "chart_xml": _replace_chart_xml_data(template["chart_xml"], chart_xml_data),
        "chart_rels": deepcopy(template["chart_rels"]),
        "workbook_blob": normalized["xlsx_blob"],
    }


def _generated_chart_template(chart_type: Any) -> dict[str, Any]:
    template_id = _chart_template_id(chart_type)
    if template_id not in _CHART_TEMPLATE_CACHE:
        _CHART_TEMPLATE_CACHE[template_id] = _build_chart_template(template_id)
    return _CHART_TEMPLATE_CACHE[template_id]


def _chart_template_id(chart_type: Any) -> int:
    chart_name = getattr(chart_type, "name", None)
    if chart_name in _CHART_TEMPLATE_NAME_TO_ID:
        return _CHART_TEMPLATE_NAME_TO_ID[chart_name]
    if chart_name in _XY_CHART_TEMPLATE_NAME_TO_ID:
        return _XY_CHART_TEMPLATE_NAME_TO_ID[chart_name]
    if chart_name in _BUBBLE_CHART_TEMPLATE_NAME_TO_ID:
        return _BUBBLE_CHART_TEMPLATE_NAME_TO_ID[chart_name]
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
    template_blob = (
        files("wolfppt.templates.charts")
        .joinpath(template_name)
        .read_bytes()
    )

    with zipfile.ZipFile(BytesIO(template_blob)) as package:
        slide_root = ET.fromstring(package.read("ppt/slides/slide1.xml"))
        graphic_frame = _first_chart_graphic_frame(slide_root)
        chart_xml = _sanitize_generated_chart_template_xml(
            _chart_axis_ids_as_openxml_int32(package.read("ppt/charts/chart1.xml"))
        )
        chart_rels = ET.fromstring(
            package.read("ppt/charts/_rels/chart1.xml.rels")
        )
    return {
        "graphic_frame": graphic_frame,
        "chart_xml": chart_xml,
        "chart_rels": chart_rels,
    }


def _sanitize_generated_chart_template_xml(chart_xml: bytes) -> bytes:
    root = ET.fromstring(chart_xml)
    _replace_alternate_content_with_fallback(root)
    _remove_radar_series_smooth_elements(root)
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


def _set_chart_frame_identity(
    chart_frame: ET.Element,
    shape_id: int,
    name: str,
    relationship_id: str,
) -> None:
    non_visual_properties = chart_frame.find(
        f"{{{P_NS}}}nvGraphicFramePr/{{{P_NS}}}cNvPr"
    )
    if non_visual_properties is None:
        raise AttributeError("chart frame non-visual properties are unavailable")
    non_visual_properties.set("id", str(shape_id))
    non_visual_properties.set("name", name)
    chart = chart_frame.find(f".//{{{C_NS}}}chart")
    if chart is None:
        raise AttributeError("chart frame relationship is unavailable")
    chart.set(f"{{{R_NS}}}id", relationship_id)


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


def _content_types_xml(root: ET.Element) -> bytes:
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return payload.replace(b"xmlns:ns0=", b"xmlns=").replace(b"ns0:", b"")


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
