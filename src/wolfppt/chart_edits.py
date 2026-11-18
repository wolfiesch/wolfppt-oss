"""Chart package edit helpers for presentation saves."""
# ruff: noqa: F401

from __future__ import annotations

import warnings
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .chart_adds import (
    _apply_chart_add,
    _apply_chart_adds,
    _normalize_category_chart_data,
    _normalize_chart_add_data,
)
from .chart_xml import (
    ChartDataRefusal,
)
from .chart_xml import (
    replace_chart_root_title as _replace_chart_root_title,
)
from .chart_xml import (
    replace_chart_xml_axis_property_groups as _replace_chart_xml_axis_property_groups,
)
from .chart_xml import (
    replace_chart_xml_axis_title_groups as _replace_chart_xml_axis_title_groups,
)
from .chart_xml import (
    replace_chart_xml_data as _replace_chart_xml_data,
)
from .chart_xml import (
    replace_chart_xml_data_labels as _replace_chart_xml_data_labels,
)
from .chart_xml import (
    replace_chart_xml_font as _replace_chart_xml_font,
)
from .chart_xml import (
    replace_chart_xml_legend as _replace_chart_xml_legend,
)
from .chart_xml import (
    replace_chart_xml_plot_properties as _replace_chart_xml_plot_properties,
)
from .chart_xml import (
    replace_chart_xml_style as _replace_chart_xml_style,
)
from .chart_xml import (
    replace_chart_xml_title as _replace_chart_xml_title,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    rels_part_for_package_part as _rels_part_for_package_part,
)
from .package_parts import (
    resolve_package_target as _resolve_package_target,
)
from .slide_payloads import load_slide_payloads as _load_slide_payloads

PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"


class ChartWorkbookNotUpdatedWarning(UserWarning):
    """A chart cache was edited without updating an embedded workbook."""


def _replace_chart_xml_data_table(chart_xml: bytes, state: dict[str, Any]) -> bytes:
    root = ET.fromstring(chart_xml)
    chart = root.find(f"{{{C_NS}}}chart")
    if chart is None:
        raise AttributeError("chart element is unavailable")
    plot_area = chart.find(f"{{{C_NS}}}plotArea")
    if plot_area is None:
        raise AttributeError("chart plot area is unavailable")

    data_table = plot_area.find(f"{{{C_NS}}}dTable")
    if not bool(state.get("has_data_table")):
        if data_table is None:
            return chart_xml
        plot_area.remove(data_table)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    if data_table is None:
        data_table = ET.Element(f"{{{C_NS}}}dTable")
        insert_at = len(plot_area)
        for index, child in enumerate(plot_area):
            if child.tag in {
                f"{{{C_NS}}}spPr",
                f"{{{C_NS}}}extLst",
            }:
                insert_at = index
                break
        plot_area.insert(insert_at, data_table)

    for name in ("showHorzBorder", "showVertBorder", "showOutline", "showKeys"):
        element = data_table.find(f"{{{C_NS}}}{name}")
        if element is not None:
            data_table.remove(element)
    for index, (name, key) in enumerate(
        (
            ("showHorzBorder", "show_horz_border"),
            ("showVertBorder", "show_vert_border"),
            ("showOutline", "show_outline"),
            ("showKeys", "show_keys"),
        )
    ):
        data_table.insert(
            index,
            ET.Element(
                f"{{{C_NS}}}{name}",
                {"val": "1" if bool(state.get(key)) else "0"},
            ),
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _apply_chart_data_replace(
    input_path: Path,
    output_path: Path,
    slide_index: int,
    shape_index: int,
    chart_data: dict[str, Any],
    extra_replacements: dict[str, bytes] | None = None,
) -> None:
    replacements = _chart_data_replacements(
        input_path,
        slide_index,
        shape_index,
        chart_data,
    )
    if extra_replacements:
        replacements.update(extra_replacements)
    with zipfile.ZipFile(input_path) as package:
        replacements = _drop_unchanged_replacements(package, replacements)
    _copy_package_with_replacements(input_path, output_path, replacements)


def _chart_data_replacements(
    input_path: Path,
    slide_index: int,
    shape_index: int,
    chart_data: dict[str, Any],
) -> dict[str, bytes]:
    with zipfile.ZipFile(input_path) as package:
        return _chart_data_replacements_from_package(
            package,
            input_path,
            slide_index,
            shape_index,
            chart_data,
        )


def _chart_data_replacements_from_package(
    package: zipfile.ZipFile,
    input_path: Path,
    slide_index: int,
    shape_index: int,
    chart_data: dict[str, Any],
) -> dict[str, bytes]:
    chart_part = _chart_part_hint(chart_data)
    if chart_part is None:
        slide_payload, shape_payload = _chart_slide_and_shape_payload(
            input_path,
            slide_index,
            shape_index,
        )
        chart_part = _chart_part_for_shape_payload(package, slide_payload, shape_payload)
    replacement_chart_xml = chart_data.get("_chart_xml")
    if not isinstance(replacement_chart_xml, bytes):
        chart_xml = package.read(chart_part)
        replacement_chart_xml = _replace_chart_xml_data(chart_xml, chart_data)
    replacements = {chart_part: replacement_chart_xml}
    # Cache-only charts keep all relationships and externalData unchanged.
    workbook_blob = chart_data.get("xlsx_blob")
    if workbook_blob is not None:
        embedded_workbook_part = _chart_embedded_workbook_part_in_package(
            package,
            chart_part,
        )
        if embedded_workbook_part is not None:
            replacements[embedded_workbook_part] = workbook_blob
        elif not chart_data.get("_cache_only"):
            warnings.warn(
                f"{chart_part}: cache only; no embedded workbook was updated",
                ChartWorkbookNotUpdatedWarning,
                stacklevel=2,
            )
    return _drop_unchanged_replacements(package, replacements)


def _drop_unchanged_replacements(
    package: zipfile.ZipFile,
    replacements: dict[str, bytes],
) -> dict[str, bytes]:
    changed: dict[str, bytes] = {}
    for part_name, payload in replacements.items():
        try:
            existing_payload = package.read(part_name)
        except KeyError:
            changed[part_name] = payload
            continue
        if payload != existing_payload:
            changed[part_name] = payload
    return changed


def _apply_chart_title_edits(
    input_path: Path,
    output_path: Path,
    title_edits: list[tuple[tuple[int, int], dict[str, Any]]],
) -> None:
    slides: list[dict[str, Any]] | None = None
    replacements: dict[str, bytes] = {}
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index), title in title_edits:
            chart_part, slides = _chart_part_for_edit(
                input_path,
                package,
                slides,
                chart_part_cache,
                slide_index,
                shape_index,
                title,
            )
            chart_xml = replacements.get(chart_part)
            if chart_xml is None:
                chart_root = title.get("_chart_root")
                if isinstance(chart_root, ET.Element):
                    replacements[chart_part] = _replace_chart_root_title(
                        chart_root,
                        title,
                    )
                    continue
                chart_xml = package.read(chart_part)
            replacements[chart_part] = _replace_chart_xml_title(chart_xml, title)
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_chart_legend_edits(
    input_path: Path,
    output_path: Path,
    legend_edits: list[tuple[tuple[int, int], dict[str, Any]]],
) -> None:
    slides: list[dict[str, Any]] | None = None
    replacements: dict[str, bytes] = {}
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index), legend in legend_edits:
            chart_part, slides = _chart_part_for_edit(
                input_path,
                package,
                slides,
                chart_part_cache,
                slide_index,
                shape_index,
                legend,
            )
            chart_xml = replacements.get(chart_part)
            if chart_xml is None:
                chart_xml = package.read(chart_part)
            replacements[chart_part] = _replace_chart_xml_legend(chart_xml, legend)
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_chart_font_edits(
    input_path: Path,
    output_path: Path,
    font_edits: list[tuple[tuple[int, int], dict[str, Any]]],
) -> None:
    slides: list[dict[str, Any]] | None = None
    replacements: dict[str, bytes] = {}
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index), font in font_edits:
            chart_part, slides = _chart_part_for_edit(
                input_path,
                package,
                slides,
                chart_part_cache,
                slide_index,
                shape_index,
                font,
            )
            chart_xml = replacements.get(chart_part)
            if chart_xml is None:
                chart_xml = package.read(chart_part)
            replacements[chart_part] = _replace_chart_xml_font(chart_xml, font)
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_chart_data_label_edits(
    input_path: Path,
    output_path: Path,
    data_label_edits: list[tuple[tuple[int, int], dict[str, Any]]],
) -> None:
    slides: list[dict[str, Any]] | None = None
    replacements: dict[str, bytes] = {}
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index), data_labels in data_label_edits:
            chart_part, slides = _chart_part_for_edit(
                input_path,
                package,
                slides,
                chart_part_cache,
                slide_index,
                shape_index,
                data_labels,
            )
            chart_xml = replacements.get(chart_part)
            if chart_xml is None:
                chart_xml = package.read(chart_part)
            replacements[chart_part] = _replace_chart_xml_data_labels(
                chart_xml,
                data_labels,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_chart_plot_property_edits(
    input_path: Path,
    output_path: Path,
    plot_property_edits: list[tuple[tuple[int, int], dict[str, Any]]],
) -> None:
    from .chart_gap_xml import materialize_picture_fills

    slides: list[dict[str, Any]] | None = None
    replacements: dict[str, bytes] = {}
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index), properties in plot_property_edits:
            chart_part, slides = _chart_part_for_edit(
                input_path,
                package,
                slides,
                chart_part_cache,
                slide_index,
                shape_index,
                properties,
            )
            chart_xml = replacements.get(chart_part)
            if chart_xml is None:
                chart_xml = package.read(chart_part)
            data_table = properties.get("_data_table")
            regular_properties = {
                name: value
                for name, value in properties.items()
                if not name.startswith("_") and name != "picture_fills"
            }
            if regular_properties:
                chart_xml = _replace_chart_xml_plot_properties(chart_xml, regular_properties)
            if isinstance(data_table, dict):
                chart_xml = _replace_chart_xml_data_table(chart_xml, data_table)
            picture_fills = properties.get("picture_fills")
            if picture_fills:
                chart_xml = materialize_picture_fills(
                    package, replacements, chart_part, chart_xml, picture_fills
                )
            replacements[chart_part] = chart_xml
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_chart_axis_title_edits(
    input_path: Path,
    output_path: Path,
    axis_title_edits: list[tuple[tuple[int, int, str], dict[str, Any]]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    slides = slide_payloads if slide_payloads is not None else _load_slide_payloads(input_path)
    grouped_edits: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index, axis), title in axis_title_edits:
            try:
                slide_payload = slides[slide_index]
                shape_payload = slide_payload["shapes"][shape_index]
            except IndexError as exc:
                raise IndexError("chart shape index out of range") from exc
            slide_part = str(slide_payload["part"])
            relationship_ids = tuple(
                str(rel_id) for rel_id in shape_payload.get("relationship_ids") or []
            )
            cache_key = (slide_part, relationship_ids)
            chart_part = chart_part_cache.get(cache_key)
            if chart_part is None:
                chart_part = _chart_part_for_slide_shape_in_package(
                    package,
                    slide_part,
                    list(relationship_ids),
                )
                chart_part_cache[cache_key] = chart_part
            grouped_edits.setdefault(chart_part, []).append((axis, title))
        replacements = {
            chart_part: _replace_chart_xml_axis_title_groups(
                package.read(chart_part),
                edits,
            )
            for chart_part, edits in grouped_edits.items()
        }
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_chart_axis_property_edits(
    input_path: Path,
    output_path: Path,
    axis_property_edits: list[tuple[tuple[int, int, str], dict[str, Any]]],
) -> None:
    slides = _load_slide_payloads(input_path)
    grouped_edits: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index, axis), properties in axis_property_edits:
            try:
                slide_payload = slides[slide_index]
                shape_payload = slide_payload["shapes"][shape_index]
            except IndexError as exc:
                raise IndexError("chart shape index out of range") from exc
            slide_part = str(slide_payload["part"])
            relationship_ids = tuple(
                str(rel_id) for rel_id in shape_payload.get("relationship_ids") or []
            )
            cache_key = (slide_part, relationship_ids)
            chart_part = chart_part_cache.get(cache_key)
            if chart_part is None:
                chart_part = _chart_part_for_slide_shape_in_package(
                    package,
                    slide_part,
                    list(relationship_ids),
                )
                chart_part_cache[cache_key] = chart_part
            grouped_edits.setdefault(chart_part, []).append((axis, properties))
        replacements = {
            chart_part: _replace_chart_xml_axis_property_groups(
                package.read(chart_part),
                edits,
            )
            for chart_part, edits in grouped_edits.items()
        }
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_chart_style_edits(
    input_path: Path,
    output_path: Path,
    style_edits: list[tuple[tuple[int, int], int | None]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    slides = slide_payloads if slide_payloads is not None else _load_slide_payloads(input_path)
    replacements: dict[str, bytes] = {}
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] = {}
    with zipfile.ZipFile(input_path) as package:
        for (slide_index, shape_index), style in style_edits:
            try:
                slide_payload = slides[slide_index]
                shape_payload = slide_payload["shapes"][shape_index]
            except IndexError as exc:
                raise IndexError("chart shape index out of range") from exc
            chart_part = _chart_part_for_shape_payload(
                package,
                slide_payload,
                shape_payload,
                chart_part_cache,
            )
            chart_xml = replacements.get(chart_part)
            if chart_xml is None:
                chart_xml = package.read(chart_part)
            replacements[chart_part] = _replace_chart_xml_style(chart_xml, style)
    _copy_package_with_replacements(input_path, output_path, replacements)


def _chart_part_hint(edit: dict[str, Any]) -> str | None:
    value = edit.get("_chart_part")
    if isinstance(value, str) and value:
        return value
    return None


def _chart_slide_and_shape_payload(
    input_path: Path,
    slide_index: int,
    shape_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    slides = _load_slide_payloads(input_path)
    try:
        slide_payload = slides[slide_index]
        shape_payload = slide_payload["shapes"][shape_index]
    except IndexError as exc:
        raise IndexError("chart shape index out of range") from exc
    return slide_payload, shape_payload


def _chart_part_for_group_path(package: zipfile.ZipFile, slide_part: str, path: list[int]) -> str:
    from .chart_adds import _direct_group_child_group, _slide_group_shape

    root = ET.fromstring(package.read(slide_part))
    p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    tree = root.find(f"{{{p_ns}}}cSld/{{{p_ns}}}spTree")
    if tree is None or len(path) < 2:
        raise AttributeError("group chart ancestry is unavailable")
    group = _slide_group_shape(tree, path[0])
    for child_index in path[1:-1]:
        group = _direct_group_child_group(group, child_index)
    children = [
        child
        for child in group
        if child.tag.rsplit("}", 1)[-1] in {"sp", "pic", "graphicFrame", "cxnSp", "grpSp"}
    ]
    if path[-1] < 0 or path[-1] >= len(children):
        raise IndexError("group chart child index out of range")
    chart = children[path[-1]].find(f".//{{{C_NS}}}chart")
    if chart is None or not chart.get(f"{{{r_ns}}}id"):
        raise AttributeError("group child chart relationship is unavailable")
    return _chart_part_for_slide_shape_in_package(package, slide_part, [chart.get(f"{{{r_ns}}}id")])


def _chart_part_for_edit(
    input_path: Path,
    package: zipfile.ZipFile,
    slides: list[dict[str, Any]] | None,
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str],
    slide_index: int,
    shape_index: int,
    edit: dict[str, Any],
) -> tuple[str, list[dict[str, Any]] | None]:
    hinted_part = _chart_part_hint(edit)
    if hinted_part is not None:
        return hinted_part, slides
    if slides is None:
        slides = _load_slide_payloads(input_path)
    group_path = edit.get("_chart_group_path")
    if isinstance(group_path, list):
        try:
            slide_part = str(slides[slide_index]["part"])
        except IndexError as exc:
            raise IndexError("chart slide index out of range") from exc
        return _chart_part_for_group_path(package, slide_part, group_path), slides
    try:
        slide_payload = slides[slide_index]
        shape_payload = slide_payload["shapes"][shape_index]
    except IndexError as exc:
        raise IndexError("chart shape index out of range") from exc
    return (
        _chart_part_for_shape_payload(
            package,
            slide_payload,
            shape_payload,
            chart_part_cache,
        ),
        slides,
    )


def _chart_part_for_slide_shape(
    path: Path,
    slide_part: str,
    relationship_ids: list[str],
) -> str:
    with zipfile.ZipFile(path) as package:
        return _chart_part_for_slide_shape_in_package(
            package,
            slide_part,
            relationship_ids,
        )


def _chart_part_for_shape_payload(
    package: zipfile.ZipFile,
    slide_payload: dict[str, Any],
    shape_payload: dict[str, Any],
    chart_part_cache: dict[tuple[str, tuple[str, ...]], str] | None = None,
) -> str:
    slide_part = str(slide_payload["part"])
    relationship_ids = tuple(str(rel_id) for rel_id in shape_payload.get("relationship_ids") or [])
    cache_key = (slide_part, relationship_ids)
    if chart_part_cache is not None and cache_key in chart_part_cache:
        return chart_part_cache[cache_key]
    chart_part = _chart_part_for_slide_shape_in_package(
        package,
        slide_part,
        list(relationship_ids),
    )
    if chart_part_cache is not None:
        chart_part_cache[cache_key] = chart_part
    return chart_part


def _chart_part_for_slide_shape_in_package(
    package: zipfile.ZipFile,
    slide_part: str,
    relationship_ids: list[str],
) -> str:
    if not relationship_ids:
        raise AttributeError("shape chart relationship is unavailable")
    rels_part = slide_part.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    root = ET.fromstring(package.read(rels_part))
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Id") not in relationship_ids:
            continue
        if not rel.attrib.get("Type", "").endswith("/chart"):
            continue
        return _resolve_package_target(slide_part, rel.attrib.get("Target", ""))
    raise AttributeError("shape chart relationship is unavailable")


def _chart_embedded_workbook_part(path: Path, chart_part: str) -> str | None:
    with zipfile.ZipFile(path) as package:
        return _chart_embedded_workbook_part_in_package(package, chart_part)


def _chart_embedded_workbook_part_in_package(
    package: zipfile.ZipFile,
    chart_part: str,
) -> str | None:
    rels_part = _rels_part_for_package_part(chart_part)
    if rels_part not in package.namelist():
        return None
    root = ET.fromstring(package.read(rels_part))
    chart_root = ET.fromstring(package.read(chart_part))
    external_data = chart_root.find(f"{{{C_NS}}}externalData")
    workbook_id = (
        external_data.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if external_data is not None
        else None
    )
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if workbook_id is not None and rel.get("Id") != workbook_id:
            continue
        if not rel.get("Type", "").endswith("/package"):
            continue
        if rel.get("TargetMode") == "External":
            continue
        part = _resolve_package_target(chart_part, rel.get("Target", ""))
        if part not in package.namelist():
            raise ChartDataRefusal(f"{chart_part}: missing embedded workbook part {part}")
        return part
    return None
