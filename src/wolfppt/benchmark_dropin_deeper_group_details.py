"""Deeper grouped-shape drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    ADD_CHART_EXPECTED,
    ADD_CHART_EXPECTED_TRANSFORM,
    CONNECTOR_EXPECTED_TRANSFORM,
)
from .benchmark_validation import _validate_output
from .benchmark_dropin_shape_connector_actions import GROUP_CONNECTOR_TARGETS
from .benchmark_dropin_shape_connector_chart_details import (
    GROUP_CHART_TARGETS,
    _top_level_chart_package_delta_ok,
)
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


def _dropin_add_deeper_nested_group_connector_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_CONNECTOR_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-connector benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_CONNECTOR_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    allowed_changed_parts = {changed_slide_part, "[Content_Types].xml"}
    package_delta_ok = (
        package_diff.added_parts == []
        and changed_slide_part in package_diff.changed_parts
        and set(package_diff.changed_parts) <= allowed_changed_parts
        and package_diff.removed_parts == []
    )
    source_group = source_summary.slides[slide_index].shapes[group_index]
    group = summary.slides[slide_index].shapes[group_index]
    expected_child_names = [child.name for child in source_group.children]
    parent_child_names = [
        child.name for child in group.children[: len(expected_child_names)]
    ]
    nested = group.children[-1] if group.children else None
    deeper = nested.children[-1] if nested is not None and nested.children else None
    connector = deeper.children[-1] if deeper is not None and deeper.children else None
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    transform = None
    if connector is not None and connector.transform is not None:
        transform = {
            "x": connector.transform.x,
            "y": connector.transform.y,
            "cx": connector.transform.cx,
            "cy": connector.transform.cy,
        }
    semantic_pass = (
        group.kind == "group"
        and nested is not None
        and nested.kind == "group"
        and deeper is not None
        and deeper.kind == "group"
        and connector is not None
        and connector.kind == "connector"
        and connector.text == ""
        and transform == CONNECTOR_EXPECTED_TRANSFORM
    )
    connector_xml_pass = (
        "<p:grpSp>" in slide_xml
        and "<p:cxnSp>" in slide_xml
        and '<a:prstGeom prst="line">' in slide_xml
    )
    shape_type = str(
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
        .shapes[-1]
        .shapes[-1]
        .shape_type
    )
    shape_type_pass = shape_type == "LINE (9)"
    parent_preserved = parent_child_names == expected_child_names
    ok = (
        semantic_pass
        and connector_xml_pass
        and shape_type_pass
        and parent_preserved
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "connector_pass": semantic_pass,
        "connector_xml_pass": connector_xml_pass,
        "connector_shape_type_pass": shape_type_pass,
        "connector_shape_type": shape_type,
        "connector_transform": transform,
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_child_names,
        "expected_parent_child_names": expected_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_deeper_nested_group_chart_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_CHART_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-chart benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_CHART_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_rels_part = f"ppt/slides/_rels/slide{slide_index + 1}.xml.rels"
    shape = (
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
        .shapes[-1]
        .shapes[-1]
    )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = _top_level_chart_package_delta_ok(
        fixture_id,
        package_diff.added_parts,
        package_diff.changed_parts,
        package_diff.removed_parts,
        slide_index=slide_index,
    )
    source_summary = extract_semantics(fixture_path)
    output_summary = extract_semantics(output_path)
    source_group = source_summary.slides[slide_index].shapes[group_index]
    output_group = output_summary.slides[slide_index].shapes[group_index]
    expected_child_names = [child.name for child in source_group.children]
    parent_child_names = [
        child.name for child in output_group.children[: len(expected_child_names)]
    ]
    parent_preserved = parent_child_names == expected_child_names
    chart = shape.chart
    transform = {
        "x": int(shape.left),
        "y": int(shape.top),
        "cx": int(shape.width),
        "cy": int(shape.height),
    }
    chart_metadata = {
        "chart_type": str(chart.chart_type),
        "categories": chart.categories,
        "series": [
            {"name": series.name, "values": list(series.values)}
            for series in chart.series
        ],
    }
    expected_chart_metadata = {
        **ADD_CHART_EXPECTED,
        "chart_type": "COLUMN_CLUSTERED (51)",
    }
    semantic_pass = (
        shape.has_chart is True
        and transform == ADD_CHART_EXPECTED_TRANSFORM
        and chart_metadata == expected_chart_metadata
        and parent_preserved
    )
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "chart_pass": semantic_pass,
        "deeper_group_chart_pass": bool(shape.has_chart),
        "chart_metadata": chart_metadata,
        "expected_chart_metadata": expected_chart_metadata,
        "chart_transform": transform,
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_child_names,
        "expected_parent_child_names": expected_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "changed_rels_part": changed_rels_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
