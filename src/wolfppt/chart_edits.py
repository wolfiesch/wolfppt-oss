"""Chart package edit helpers for presentation saves."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .chart_adds import (
    _apply_chart_add,
    _apply_chart_adds,
    _normalize_chart_add_data,
    _normalize_category_chart_data,
)
from .chart_xml import (
    replace_chart_root_title as _replace_chart_root_title,
    replace_chart_xml_axis_property_groups as _replace_chart_xml_axis_property_groups,
    replace_chart_xml_axis_title_groups as _replace_chart_xml_axis_title_groups,
    replace_chart_xml_data as _replace_chart_xml_data,
    replace_chart_xml_data_labels as _replace_chart_xml_data_labels,
    replace_chart_xml_font as _replace_chart_xml_font,
    replace_chart_xml_legend as _replace_chart_xml_legend,
    replace_chart_xml_plot_properties as _replace_chart_xml_plot_properties,
    replace_chart_xml_style as _replace_chart_xml_style,
    replace_chart_xml_title as _replace_chart_xml_title,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
    rels_part_for_package_part as _rels_part_for_package_part,
    resolve_package_target as _resolve_package_target,
)
from .slide_payloads import load_slide_payloads as _load_slide_payloads

PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


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
    embedded_workbook_part = _chart_embedded_workbook_part_in_package(
        package,
        chart_part,
    )
    replacement_chart_xml = chart_data.get("_chart_xml")
    if not isinstance(replacement_chart_xml, bytes):
        chart_xml = package.read(chart_part)
        replacement_chart_xml = _replace_chart_xml_data(chart_xml, chart_data)
    replacements = {
        chart_part: replacement_chart_xml,
        embedded_workbook_part: chart_data["xlsx_blob"],
    }
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
            replacements[chart_part] = _replace_chart_xml_plot_properties(
                chart_xml,
                properties,
            )
    _copy_package_with_replacements(input_path, output_path, replacements)


def _apply_chart_axis_title_edits(
    input_path: Path,
    output_path: Path,
    axis_title_edits: list[tuple[tuple[int, int, str], dict[str, Any]]],
    *,
    slide_payloads: list[dict[str, Any]] | None = None,
) -> None:
    slides = (
        slide_payloads
        if slide_payloads is not None
        else _load_slide_payloads(input_path)
    )
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
    slides = (
        slide_payloads
        if slide_payloads is not None
        else _load_slide_payloads(input_path)
    )
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
    relationship_ids = tuple(
        str(rel_id) for rel_id in shape_payload.get("relationship_ids") or []
    )
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


def _chart_embedded_workbook_part(path: Path, chart_part: str) -> str:
    with zipfile.ZipFile(path) as package:
        return _chart_embedded_workbook_part_in_package(package, chart_part)


def _chart_embedded_workbook_part_in_package(
    package: zipfile.ZipFile,
    chart_part: str,
) -> str:
    rels_part = _rels_part_for_package_part(chart_part)
    root = ET.fromstring(package.read(rels_part))
    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if not rel.attrib.get("Type", "").endswith("/package"):
            continue
        return _resolve_package_target(chart_part, rel.attrib.get("Target", ""))
    raise AttributeError("chart embedded workbook relationship is unavailable")
