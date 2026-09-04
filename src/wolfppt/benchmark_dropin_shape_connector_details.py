"""Connector shape-creation benchmark detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .benchmark_cases import CONNECTOR_EXPECTED_TRANSFORM
from .benchmark_validation import _validate_output
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
TOP_LEVEL_CONNECTOR_FIXTURES = (
    "text_basic/title_body_bullets",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)
GROUP_CONNECTOR_TARGETS = {
    "shapes/grouped_shapes": (0, 0),
    "workloads/management_reporting_deck": (2, 1),
    "workloads/customer_success_review_pack": (4, 1),
}


def _dropin_add_connector_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CONNECTOR_FIXTURES:
        raise RuntimeError(
            f"drop-in add-connector benchmark does not support fixture {fixture_id}"
        )
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    connector = summary.slides[0].shapes[-1]
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    transform = None
    if connector.transform is not None:
        transform = {
            "x": connector.transform.x,
            "y": connector.transform.y,
            "cx": connector.transform.cx,
            "cy": connector.transform.cy,
        }
    semantic_pass = (
        connector.kind == "connector"
        and connector.text == ""
        and transform == CONNECTOR_EXPECTED_TRANSFORM
    )
    connector_xml_pass = (
        "<p:cxnSp>" in slide_xml and '<a:prstGeom prst="line">' in slide_xml
    )
    ok = semantic_pass and connector_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "connector_pass": semantic_pass,
        "connector_xml_pass": connector_xml_pass,
        "connector_transform": transform,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_group_connector_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_CONNECTOR_TARGETS:
        raise RuntimeError(
            f"drop-in add-group-connector benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_CONNECTOR_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    summary = extract_semantics(output_path)
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
    group = summary.slides[slide_index].shapes[group_index]
    connector = group.children[-1] if group.children else None
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
        .shape_type
    )
    shape_type_pass = shape_type == "LINE (9)"
    ok = (
        semantic_pass
        and connector_xml_pass
        and shape_type_pass
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


def _dropin_add_nested_group_connector_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_CONNECTOR_TARGETS:
        raise RuntimeError(
            f"drop-in add-nested-group-connector benchmark does not support fixture {fixture_id}"
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
    connector = nested.children[-1] if nested is not None and nested.children else None
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


def _dropin_connector_connection_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_connector_connection_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
        begin_target_index=-3,
        end_target_index=-2,
        connector_index=-1,
        begin_connection_index=3,
        end_connection_index=1,
        label="connector connection",
    )


def _dropin_group_connector_connection_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_CONNECTOR_TARGETS:
        raise RuntimeError(
            "drop-in grouped connector connection benchmark does not "
            f"support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_CONNECTOR_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
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
    source_prs = WolfPresentation(fixture_path)
    prs = WolfPresentation(output_path)
    source_group = source_prs.slides[slide_index].shapes[group_index]
    group = prs.slides[slide_index].shapes[group_index]
    source_child_names = [child.name for child in source_group.shapes]
    child_names = [
        group.shapes[index].name for index in range(len(source_child_names))
    ]
    parent_preserved = child_names == source_child_names
    begin_target = group.shapes[-3]
    end_target = group.shapes[-2]
    connector = group.shapes[-1]
    expected_begin = _connector_connection_point(begin_target, 3)
    expected_end = _connector_connection_point(end_target, 1)
    with ZipFile(output_path) as package:
        slide_root = ET.fromstring(package.read(changed_slide_part))
    start_connections = slide_root.findall(f".//{{{A_NS}}}stCxn")
    end_connections = slide_root.findall(f".//{{{A_NS}}}endCxn")
    connection_xml_pass = (
        any(
            connection.attrib == {"id": str(begin_target.shape_id), "idx": "3"}
            for connection in start_connections
        )
        and any(
            connection.attrib == {"id": str(end_target.shape_id), "idx": "1"}
            for connection in end_connections
        )
    )
    endpoint_pass = (
        connector.begin_x == expected_begin[0]
        and connector.begin_y == expected_begin[1]
        and connector.end_x == expected_end[0]
        and connector.end_y == expected_end[1]
    )
    semantic_pass = (
        len(group.shapes) == len(source_group.shapes) + 3
        and int(connector.shape_type) == 9
        and endpoint_pass
        and parent_preserved
    )
    ok = semantic_pass and connection_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "connector_connection_pass": semantic_pass,
        "connector_endpoint_pass": endpoint_pass,
        "connector_connection_xml_pass": connection_xml_pass,
        "group_child_count": len(group.shapes),
        "expected_group_child_count": len(source_group.shapes) + 3,
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": child_names,
        "expected_parent_child_names": source_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "connector_begin": {"x": connector.begin_x, "y": connector.begin_y},
        "connector_end": {"x": connector.end_x, "y": connector.end_y},
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


def _dropin_existing_connector_connection_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_connector_connection_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
        begin_target_index=0,
        end_target_index=1,
        connector_index=-1,
        begin_connection_index=2,
        end_connection_index=0,
        label="existing-shape connector connection",
    )


def _dropin_connector_connection_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
    *,
    begin_target_index: int,
    end_target_index: int,
    connector_index: int,
    begin_connection_index: int,
    end_connection_index: int,
    label: str,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CONNECTOR_FIXTURES:
        raise RuntimeError(
            f"drop-in {label} benchmark does not support fixture {fixture_id}"
        )
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    prs = WolfPresentation(output_path)
    slide = prs.slides[0]
    begin_target = slide.shapes[begin_target_index]
    end_target = slide.shapes[end_target_index]
    connector = slide.shapes[connector_index]
    expected_begin = _connector_connection_point(begin_target, begin_connection_index)
    expected_end = _connector_connection_point(end_target, end_connection_index)
    expected_transform = {
        "x": min(expected_begin[0], expected_end[0]),
        "y": min(expected_begin[1], expected_end[1]),
        "cx": abs(expected_end[0] - expected_begin[0]),
        "cy": abs(expected_end[1] - expected_begin[1]),
    }
    semantic_connector = summary.slides[0].shapes[connector_index]
    transform = None
    if semantic_connector.transform is not None:
        transform = {
            "x": semantic_connector.transform.x,
            "y": semantic_connector.transform.y,
            "cx": semantic_connector.transform.cx,
            "cy": semantic_connector.transform.cy,
        }
    with ZipFile(output_path) as package:
        slide_root = ET.fromstring(package.read("ppt/slides/slide1.xml"))
    start_connection = slide_root.find(f".//{{{A_NS}}}stCxn")
    end_connection = slide_root.find(f".//{{{A_NS}}}endCxn")
    connection_xml_pass = (
        start_connection is not None
        and start_connection.attrib == {
            "id": str(begin_target.shape_id),
            "idx": str(begin_connection_index),
        }
        and end_connection is not None
        and end_connection.attrib == {
            "id": str(end_target.shape_id),
            "idx": str(end_connection_index),
        }
    )
    endpoint_pass = (
        connector.begin_x == expected_begin[0]
        and connector.begin_y == expected_begin[1]
        and connector.end_x == expected_end[0]
        and connector.end_y == expected_end[1]
    )
    semantic_pass = (
        semantic_connector.kind == "connector"
        and endpoint_pass
        and transform == expected_transform
    )
    ok = semantic_pass and connection_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "connector_connection_pass": semantic_pass,
        "connector_endpoint_pass": endpoint_pass,
        "connector_connection_xml_pass": connection_xml_pass,
        "connector_begin": {"x": connector.begin_x, "y": connector.begin_y},
        "connector_end": {"x": connector.end_x, "y": connector.end_y},
        "connector_transform": transform,
        "expected_transform": expected_transform,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _connector_connection_point(shape: Any, index: int) -> tuple[int, int]:
    points = {
        0: (shape.left + shape.width // 2, shape.top),
        1: (shape.left, shape.top + shape.height // 2),
        2: (shape.left + shape.width // 2, shape.top + shape.height),
        3: (shape.left + shape.width, shape.top + shape.height // 2),
    }
    return points[index]
