"""Internal chart facade payload and XML mutation helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from numbers import Integral
from typing import Any
from xml.etree import ElementTree as ET

from .chart_edits import _chart_part_for_slide_shape_in_package
from .chart_xml import (
    chart_axis_element as _chart_axis_element,
)
from .chart_xml import (
    chart_container_element as _chart_container_element,
)
from .chart_xml import (
    default_chart_axis_payload as _default_chart_axis_payload,
)
from .chart_xml import (
    default_chart_data_labels_payload as _default_chart_data_labels_payload,
)
from .chart_xml import (
    parse_chart_root as _parse_chart_root,
)
from .package_parts import open_package_source

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
# ECMA-376 Part 1 Strict renames these namespaces and keeps the chart vocabulary.
_STRICT_CHART_NS = "http://purl.oclc.org/ooxml/drawingml/chart"
_TRANSITIONAL_PREFIXES = {
    f"{{{_STRICT_CHART_NS}}}": f"{{{C_NS}}}",
    "{http://purl.oclc.org/ooxml/drawingml/main}": f"{{{A_NS}}}",
    "{http://purl.oclc.org/ooxml/officeDocument/relationships}": f"{{{R_NS}}}",
}


def _transitional_name(name: str) -> str:
    if name.startswith("{"):
        prefix = name[: name.find("}") + 1]
        replacement = _TRANSITIONAL_PREFIXES.get(prefix)
        if replacement is not None:
            return replacement + name[len(prefix) :]
    return name


def transitional_chart_root(root: ET.Element) -> ET.Element:
    """Rename a Strict chartSpace's chart, DrawingML and relationship names in place.

    Chart facade readers address Transitional names; a Strict root is read as its
    Transitional equivalent. Transitional roots are returned unchanged.
    """
    if not root.tag.startswith(f"{{{_STRICT_CHART_NS}}}"):
        return root
    for element in root.iter():
        if isinstance(element.tag, str):
            element.tag = _transitional_name(element.tag)
        if any(name.startswith("{") for name in element.attrib):
            attributes = {_transitional_name(name): value for name, value in element.attrib.items()}
            element.attrib.clear()
            element.attrib.update(attributes)
    return root


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


def normalize_choice(value: Any, choices: Sequence[str], name: str) -> str:
    """Normalize a string or enum member (by name) to one of ``choices``.

    Matching ignores case and treats spaces, hyphens and underscores alike, so
    ``"By Category"`` and an enum member named ``BY_CATEGORY`` both select
    ``"by_category"``.
    """
    raw = getattr(value, "name", value)
    if isinstance(raw, str):
        compact = re.sub(r"[\s_-]", "", raw).lower()
        for choice in choices:
            if choice.replace("_", "").lower() == compact:
                return choice
    raise ValueError(f"unsupported {name} value {value!r}; expected one of {', '.join(choices)}")


def chart_payload(shape: Any) -> dict[str, Any]:
    cached = shape._payload.get("_chart_payload")
    if isinstance(cached, dict):
        return cached
    chart_part = shape_chart_part(shape)
    cached_root = shape._payload.get("_chart_root")
    if isinstance(cached_root, ET.Element):
        root = transitional_chart_root(cached_root)
    else:
        with open_package_source(shape._slide._presentation._source_path) as package:
            chart_xml = package.read(chart_part)
        root = transitional_chart_root(ET.fromstring(chart_xml))
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
        return transitional_chart_root(cached)

    # Check if this is an unsaved chart (no chart part and no relationship IDs)
    hinted_part = shape._payload.get("_chart_part")
    relationship_ids = shape._payload.get("relationship_ids") or []

    if not hinted_part and not relationship_ids:
        # Chart hasn't been saved yet - generate from staged payload
        chart_payload = shape._payload.get("_chart_payload")
        if not chart_payload:
            raise AttributeError("chart payload is unavailable")

        # Generate chart XML from the payload
        from .chart_adds import _generated_chart_template
        from .chart_type_xml import chart_type_value
        from .chart_xml import replace_chart_xml_data

        chart_type_payload = chart_payload.get("chart_type")
        if chart_type_payload is None:
            raise AttributeError("chart type is unavailable in payload")

        chart_type = chart_type_value(chart_type_payload)
        template = _generated_chart_template(chart_type)
        chart_data = {
            "series": chart_payload.get("series", []),
            "categories": (
                chart_payload["series"][0].get("categories", [])
                if chart_payload.get("series")
                else []
            ),
        }
        chart_xml = replace_chart_xml_data(template["chart_xml"], chart_data)
        root = ET.fromstring(chart_xml)
        shape._payload["_chart_root"] = root
        return root

    # Saved chart - read from package
    chart_part = shape_chart_part(shape)
    with open_package_source(shape._slide._presentation._source_path) as package:
        root = transitional_chart_root(ET.fromstring(package.read(chart_part)))
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


def chart_axis_gridlines_element(
    shape: Any,
    axis: str,
    kind: str,
    *,
    create: bool = False,
) -> ET.Element:
    """The axis ``c:majorGridlines`` or ``c:minorGridlines`` (``kind`` major or minor)."""
    local_name = f"{kind}Gridlines"
    axis_element = chart_axis_proxy_element(shape, axis)
    gridlines = axis_element.find(f"{{{C_NS}}}{local_name}")
    if gridlines is not None:
        return gridlines
    gridlines = ET.Element(f"{{{C_NS}}}{local_name}")
    if create:
        axis_element.insert(_chart_axis_insert_index(axis_element, local_name), gridlines)
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
    return text_properties.find(f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr")


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
    return axis_element.find(f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr")


def chart_data_labels_text_default_run_properties(shape: Any) -> ET.Element | None:
    chart_element = first_chart_plot_element(shape)
    if chart_element is None:
        return None
    data_labels = chart_element.find(f"{{{C_NS}}}dLbls")
    if data_labels is None:
        return None
    return data_labels.find(f"{{{C_NS}}}txPr/{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr")


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
    return text_properties.find(f"{{{A_NS}}}p/{{{A_NS}}}pPr/{{{A_NS}}}defRPr")


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


def chart_series_child_insert_index(series_element: ET.Element, local_name: str) -> int:
    order = {
        "idx": 0,
        "order": 1,
        "tx": 2,
        "spPr": 3,
        "invertIfNegative": 4,
        "pictureOptions": 5,
        "marker": 6,
        "dPt": 7,
        "dLbls": 8,
        "trendline": 9,
        "errBars": 10,
        "cat": 11,
        "xVal": 12,
        "val": 13,
        "yVal": 14,
        "bubbleSize": 15,
        "bubble3D": 16,
        "smooth": 17,
        "shape": 18,
        "extLst": 19,
    }
    target_order = order.get(local_name)
    if target_order is None:
        return len(series_element)
    for index, child in enumerate(list(series_element)):
        child_order = order.get(child.tag.rsplit("}", 1)[-1])
        if child_order is not None and child_order > target_order:
            return index
    return len(series_element)


def set_chart_series_invert_if_negative(series_element: ET.Element, value: bool) -> None:
    child = series_element.find(f"{{{C_NS}}}invertIfNegative")
    val_str = "1" if value else "0"
    if child is None:
        child = ET.Element(f"{{{C_NS}}}invertIfNegative")
        child.set("val", val_str)
        insert_idx = chart_series_child_insert_index(series_element, "invertIfNegative")
        series_element.insert(insert_idx, child)
    else:
        child.set("val", val_str)


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


def chart_category_paths(shape: Any) -> tuple[list[list[str]], bool]:
    """Return each category's label path and whether the labels are strings.

    A path lists the outermost grouping level first and the leaf label last.
    Multi-level caches store a higher-level label only at the first point of its
    span, so every later point in the span inherits it.  Numeric and date
    categories report ``False`` because they cannot carry grouping levels.
    """
    plot = first_chart_plot_element(shape)
    series = None if plot is None else plot.find(f"{{{C_NS}}}ser")
    category = None if series is None else series.find(f"{{{C_NS}}}cat")
    if category is None:
        return [], True
    cache = category.find(f"{{{C_NS}}}multiLvlStrRef/{{{C_NS}}}multiLvlStrCache")
    if cache is not None:
        return _multi_level_category_paths(cache), True
    for path, is_string in (
        (f"{{{C_NS}}}strRef/{{{C_NS}}}strCache", True),
        (f"{{{C_NS}}}numRef/{{{C_NS}}}numCache", False),
        (f"{{{C_NS}}}strLit", True),
        (f"{{{C_NS}}}numLit", False),
    ):
        cache = category.find(path)
        if cache is not None:
            points = _category_cache_points(cache)
            labels = [""] * _category_point_count(cache, points)
            for index, text in points:
                labels[index] = text
            return [[label] for label in labels], is_string
    return [], True


def _multi_level_category_paths(cache: ET.Element) -> list[list[str]]:
    levels = cache.findall(f"{{{C_NS}}}lvl")
    level_points = [_category_cache_points(level) for level in levels]
    count = _category_point_count(cache, [point for points in level_points for point in points])
    depth = max(1, len(levels))
    paths = [[""] * depth for _ in range(count)]
    for level_position, points in enumerate(level_points):
        column = depth - 1 - level_position
        if level_position == 0:
            for index, text in points:
                if index < count:
                    paths[index][column] = text
            continue
        for position, (index, text) in enumerate(points):
            end = points[position + 1][0] if position + 1 < len(points) else count
            for point_index in range(index, min(end, count)):
                paths[point_index][column] = text
    return paths


def _category_cache_points(container: ET.Element) -> list[tuple[int, str]]:
    points: list[tuple[int, str]] = []
    for point in container.findall(f"{{{C_NS}}}pt"):
        raw_index = point.get("idx", "")
        if raw_index.isdigit():
            points.append((int(raw_index), point.findtext(f"{{{C_NS}}}v") or ""))
    return sorted(points)


def _category_point_count(cache: ET.Element, points: list[tuple[int, str]]) -> int:
    declared = cache.find(f"{{{C_NS}}}ptCount")
    raw_count = None if declared is None else declared.get("val", "")
    if raw_count is not None and raw_count.isdigit():
        return int(raw_count)
    return max((index for index, _ in points), default=-1) + 1


def prepare_chart_category_levels(
    root: ET.Element,
    series_elements: list[ET.Element],
    depth: int,
) -> None:
    """Align series-name formulas and level display with a category depth.

    The embedded workbook places ``depth`` category columns before the series
    columns, so each series name moves to the column after them.  Category
    axes that suppress multi-level labels are switched to show every level.
    """
    for series_index, series_element in enumerate(series_elements):
        formula = series_element.find(f"{{{C_NS}}}tx/{{{C_NS}}}strRef/{{{C_NS}}}f")
        if formula is not None:
            column = _spreadsheet_column_name(depth + series_index + 1)
            formula.text = f"Sheet1!${column}$1"
    if depth < 2:
        return
    for suppress in root.iter(f"{{{C_NS}}}noMultiLvlLbl"):
        suppress.set("val", "0")


def _spreadsheet_column_name(index: int) -> str:
    """Return the spreadsheet column name for a one-based column number."""
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def shape_chart_part(shape: Any) -> str:
    hinted_part = shape._payload.get("_chart_part")
    if hinted_part:
        return str(hinted_part)
    relationship_ids = [str(rel_id) for rel_id in shape._payload.get("relationship_ids") or []]
    with open_package_source(shape._slide._presentation._source_path) as package:
        return _chart_part_for_slide_shape_in_package(
            package,
            shape._slide.partname,
            relationship_ids,
        )
