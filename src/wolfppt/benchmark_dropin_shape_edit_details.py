"""Shape edit drop-in benchmark result detail readers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    A_NS,
    ADD_SHAPE_EXPECTED_TRANSFORM,
    CONNECTOR_LINE_STYLE_EXPECTED,
    GROUP_CHILD_GEOMETRY_EXPECTED,
    PICTURE_CROP_EXPECTED,
    SHAPE_ADJUSTMENT_EXPECTED,
    SHAPE_ADJUSTMENT_EXPECTED_XML,
    SHAPE_GEOMETRY_EXPECTED,
)
from .benchmark_validation import _validate_output
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

PICTURE_CROP_FIXTURES = ("media/png_picture", "workloads/mixed_real_world_deck")
TOP_LEVEL_CREATION_FIXTURES = (
    "text_basic/title_body_bullets",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)
GROUP_SHAPE_TARGETS = {
    "shapes/grouped_shapes": (0, 0),
    "workloads/management_reporting_deck": (2, 1),
    "workloads/customer_success_review_pack": (4, 1),
}


def _dropin_shape_adjustment_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in shape adjustment benchmark does not support fixture {fixture_id}"
        )
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    shape_summary = summary.slides[0].shapes[-1]
    transform = None
    if shape_summary.transform is not None:
        transform = {
            "x": shape_summary.transform.x,
            "y": shape_summary.transform.y,
            "cx": shape_summary.transform.cx,
            "cy": shape_summary.transform.cy,
        }
    shape = WolfPresentation(output_path).slides[0].shapes[-1]
    adjustment_values = [
        shape.adjustments[index] for index in range(len(shape.adjustments))
    ]
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    adjustment_pass = (
        len(adjustment_values) == 1
        and math.isclose(
            adjustment_values[0],
            SHAPE_ADJUSTMENT_EXPECTED,
            rel_tol=0.0,
            abs_tol=0.00001,
        )
    )
    adjustment_xml_pass = (
        'name="adj"' in slide_xml
        and f'fmla="val {SHAPE_ADJUSTMENT_EXPECTED_XML}"' in slide_xml
    )
    semantic_pass = (
        shape_summary.kind == "shape"
        and transform == ADD_SHAPE_EXPECTED_TRANSFORM
        and adjustment_pass
    )
    ok = (
        semantic_pass
        and adjustment_xml_pass
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "adjustment_pass": adjustment_pass,
        "adjustment_xml_pass": adjustment_xml_pass,
        "adjustment_values": adjustment_values,
        "shape_transform": transform,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_geometry_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in shape geometry benchmark does not support fixture {fixture_id}"
        )
    changed_slide_part = "ppt/slides/slide1.xml"
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and changed_slide_part in package_diff.changed_parts
        and set(package_diff.changed_parts) <= {changed_slide_part, "[Content_Types].xml"}
        and package_diff.removed_parts == []
    )
    source_shape_names = [shape.name for shape in source_summary.slides[0].shapes]
    shape_names = [shape.name for shape in summary.slides[0].shapes]
    shape_names_preserved = shape_names == source_shape_names
    shape_summary = summary.slides[0].shapes[0]
    summary_transform = None
    if shape_summary.transform is not None:
        summary_transform = {
            "x": shape_summary.transform.x,
            "y": shape_summary.transform.y,
            "cx": shape_summary.transform.cx,
            "cy": shape_summary.transform.cy,
        }
    shape = WolfPresentation(output_path).slides[0].shapes[0]
    reopened_transform = {
        "x": int(shape.left),
        "y": int(shape.top),
        "cx": int(shape.width),
        "cy": int(shape.height),
    }
    geometry_pass = (
        summary_transform == SHAPE_GEOMETRY_EXPECTED
        and reopened_transform == SHAPE_GEOMETRY_EXPECTED
        and shape_names_preserved
    )
    ok = geometry_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": geometry_pass,
        "semantic_score": 1.0 if geometry_pass else 0.0,
        "geometry_pass": geometry_pass,
        "summary_transform": summary_transform,
        "reopened_transform": reopened_transform,
        "shape_names_preserved": shape_names_preserved,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_group_child_geometry_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            f"drop-in group child geometry benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    allowed_changed_parts = {changed_slide_part, "[Content_Types].xml"}
    changed_parts_ok = (
        package_diff.added_parts == []
        and changed_slide_part in package_diff.changed_parts
        and set(package_diff.changed_parts) <= allowed_changed_parts
        and package_diff.removed_parts == []
    )
    source_group = source_summary.slides[slide_index].shapes[group_index]
    group = summary.slides[slide_index].shapes[group_index]
    expected_child_names = [child.name for child in source_group.children]
    child_names = [child.name for child in group.children]
    child_names_preserved = child_names == expected_child_names
    child_summary = group.children[0]
    summary_transform = None
    if child_summary.transform is not None:
        summary_transform = {
            "x": child_summary.transform.x,
            "y": child_summary.transform.y,
            "cx": child_summary.transform.cx,
            "cy": child_summary.transform.cy,
        }
    child = WolfPresentation(output_path).slides[slide_index].shapes[group_index].shapes[0]
    reopened_transform = {
        "x": int(child.left),
        "y": int(child.top),
        "cx": int(child.width),
        "cy": int(child.height),
    }
    geometry_pass = (
        summary_transform == GROUP_CHILD_GEOMETRY_EXPECTED
        and reopened_transform == GROUP_CHILD_GEOMETRY_EXPECTED
        and child_names_preserved
    )
    ok = geometry_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": geometry_pass,
        "semantic_score": 1.0 if geometry_pass else 0.0,
        "geometry_pass": geometry_pass,
        "summary_transform": summary_transform,
        "reopened_transform": reopened_transform,
        "group_child_names_preserved": child_names_preserved,
        "group_child_names": child_names,
        "expected_group_child_names": expected_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_group_child_adjustment_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            f"drop-in group child adjustment benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
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
    parent_preserved = parent_child_names == expected_child_names
    child_summary = group.children[-1]
    summary_transform = None
    if child_summary.transform is not None:
        summary_transform = {
            "x": child_summary.transform.x,
            "y": child_summary.transform.y,
            "cx": child_summary.transform.cx,
            "cy": child_summary.transform.cy,
        }
    child = WolfPresentation(output_path).slides[slide_index].shapes[group_index].shapes[-1]
    adjustment_values = [
        child.adjustments[index] for index in range(len(child.adjustments))
    ]
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    adjustment_pass = (
        len(adjustment_values) == 1
        and math.isclose(
            adjustment_values[0],
            SHAPE_ADJUSTMENT_EXPECTED,
            rel_tol=0.0,
            abs_tol=0.00001,
        )
    )
    adjustment_xml_pass = (
        'name="adj"' in slide_xml
        and f'fmla="val {SHAPE_ADJUSTMENT_EXPECTED_XML}"' in slide_xml
    )
    semantic_pass = (
        child_summary.kind == "shape"
        and summary_transform == ADD_SHAPE_EXPECTED_TRANSFORM
        and adjustment_pass
        and parent_preserved
    )
    ok = (
        semantic_pass
        and adjustment_xml_pass
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "adjustment_pass": adjustment_pass,
        "adjustment_xml_pass": adjustment_xml_pass,
        "adjustment_values": adjustment_values,
        "shape_transform": summary_transform,
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_child_names,
        "expected_parent_child_names": expected_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_line_element_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in shape line element benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    shape = WolfPresentation(output_path).slides[0].shapes[0]
    line = shape.ln
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    line_pass = line is not None and line.tag == f"{{{A_NS}}}ln"
    line_xml_pass = "<a:ln" in slide_xml
    ok = line_pass and line_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": line_pass,
        "semantic_score": 1.0 if line_pass else 0.0,
        "line_pass": line_pass,
        "line_xml_pass": line_xml_pass,
        "line_tag": None if line is None else line.tag,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }



def _dropin_connector_line_style_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in connector line-style benchmark does not support fixture {fixture_id}"
        )
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    connector_summary = summary.slides[0].shapes[-1]
    connector = WolfPresentation(output_path).slides[0].shapes[-1]
    line_dash_style = getattr(
        connector.line.dash_style,
        "xml_value",
        connector.line.dash_style,
    )
    style = {
        "line_rgb": None if connector.line.color.rgb is None else str(connector.line.color.rgb),
        "line_width": int(connector.line.width),
        "line_dash_style": line_dash_style,
    }
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    connector_xml_pass = (
        "<p:cxnSp>" in slide_xml
        and CONNECTOR_LINE_STYLE_EXPECTED["line_rgb"] in slide_xml
        and f'w="{CONNECTOR_LINE_STYLE_EXPECTED["line_width"]}"' in slide_xml
        and '<a:prstDash val="dash"' in slide_xml
    )
    style_pass = (
        connector_summary.kind == "connector"
        and connector.shape_type is not None
        and style == CONNECTOR_LINE_STYLE_EXPECTED
    )
    ok = style_pass and connector_xml_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": style_pass,
        "semantic_score": 1.0 if style_pass else 0.0,
        "connector_line_style_pass": style_pass,
        "connector_xml_pass": connector_xml_pass,
        "connector_line_style": style,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_picture_crop_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in PICTURE_CROP_FIXTURES:
        raise RuntimeError(
            f"drop-in picture crop benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, picture = _first_picture_shape(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    crop = {
        "left": picture.crop_left,
        "right": picture.crop_right,
        "top": picture.crop_top,
        "bottom": picture.crop_bottom,
    }
    crop_pass = crop == PICTURE_CROP_EXPECTED
    ok = crop_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": crop_pass,
        "semantic_score": 1.0 if crop_pass else 0.0,
        "crop_pass": crop_pass,
        "crop": crop,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _first_picture_shape(prs: WolfPresentation) -> tuple[int, Any]:
    for slide_index, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if shape.has_picture:
                return slide_index, shape
    raise RuntimeError("output deck does not contain a picture shape")
