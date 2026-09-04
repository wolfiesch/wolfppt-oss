"""Freeform shape creation benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    ADD_FREEFORM_EXPECTED_TEXT,
    ADD_FREEFORM_EXPECTED_TRANSFORM,
)
from .benchmark_validation import _validate_output
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

TOP_LEVEL_CREATION_FIXTURES = (
    "text_basic/title_body_bullets",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)
GROUP_FREEFORM_TARGETS = {
    "shapes/grouped_shapes": (0, 0),
    "workloads/management_reporting_deck": (2, 1),
    "workloads/customer_success_review_pack": (4, 1),
}


def _dropin_build_freeform_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in build-freeform benchmark does not support fixture {fixture_id}"
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
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    freeform_type_pass = str(shape.shape_type) == "FREEFORM (5)"
    custom_geometry_pass = "<a:custGeom>" in slide_xml and "<a:close/>" in slide_xml
    semantic_pass = (
        shape_summary.kind == "shape"
        and shape_summary.text == ADD_FREEFORM_EXPECTED_TEXT
        and transform == ADD_FREEFORM_EXPECTED_TRANSFORM
    )
    ok = (
        semantic_pass
        and freeform_type_pass
        and custom_geometry_pass
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "freeform_type_pass": freeform_type_pass,
        "custom_geometry_pass": custom_geometry_pass,
        "shape_type": str(shape.shape_type),
        "shape_transform": transform,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_build_group_freeform_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_FREEFORM_TARGETS:
        raise RuntimeError(
            f"drop-in build-group-freeform benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_FREEFORM_TARGETS[fixture_id]
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
    shape_summary = group.children[-1] if group.children else None
    transform = None
    if shape_summary is not None and shape_summary.transform is not None:
        transform = {
            "x": shape_summary.transform.x,
            "y": shape_summary.transform.y,
            "cx": shape_summary.transform.cx,
            "cy": shape_summary.transform.cy,
        }
    shape = (
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
    )
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    freeform_type_pass = str(shape.shape_type) == "FREEFORM (5)"
    custom_geometry_pass = (
        "<p:grpSp>" in slide_xml
        and "<a:custGeom>" in slide_xml
        and "<a:close/>" in slide_xml
    )
    semantic_pass = (
        group.kind == "group"
        and shape_summary is not None
        and shape_summary.kind == "shape"
        and shape_summary.text == ADD_FREEFORM_EXPECTED_TEXT
        and transform == ADD_FREEFORM_EXPECTED_TRANSFORM
    )
    ok = (
        semantic_pass
        and freeform_type_pass
        and custom_geometry_pass
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "freeform_type_pass": freeform_type_pass,
        "custom_geometry_pass": custom_geometry_pass,
        "shape_type": str(shape.shape_type),
        "shape_text": None if shape_summary is None else shape_summary.text,
        "shape_transform": transform,
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


def _dropin_build_nested_group_freeform_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_FREEFORM_TARGETS:
        raise RuntimeError(
            f"drop-in build-nested-group-freeform benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_FREEFORM_TARGETS[fixture_id]
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
    parent_preserved = parent_child_names == expected_child_names
    nested_group = group.children[-1] if group.children else None
    shape_summary = (
        nested_group.children[-1]
        if nested_group is not None and nested_group.children
        else None
    )
    transform = None
    if shape_summary is not None and shape_summary.transform is not None:
        transform = {
            "x": shape_summary.transform.x,
            "y": shape_summary.transform.y,
            "cx": shape_summary.transform.cx,
            "cy": shape_summary.transform.cy,
        }
    shape = (
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
        .shapes[-1]
    )
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    freeform_type_pass = str(shape.shape_type) == "FREEFORM (5)"
    custom_geometry_pass = (
        "<p:grpSp>" in slide_xml
        and "<a:custGeom>" in slide_xml
        and "<a:close/>" in slide_xml
    )
    semantic_pass = (
        group.kind == "group"
        and nested_group is not None
        and nested_group.kind == "group"
        and shape_summary is not None
        and shape_summary.kind == "shape"
        and shape_summary.text == ADD_FREEFORM_EXPECTED_TEXT
        and transform == ADD_FREEFORM_EXPECTED_TRANSFORM
        and parent_preserved
    )
    ok = (
        semantic_pass
        and freeform_type_pass
        and custom_geometry_pass
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "freeform_type_pass": freeform_type_pass,
        "custom_geometry_pass": custom_geometry_pass,
        "shape_type": str(shape.shape_type),
        "shape_text": None if shape_summary is None else shape_summary.text,
        "shape_transform": transform,
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


def _dropin_clone_layout_placeholders_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id != "text_basic/title_body_bullets":
        raise RuntimeError(
            f"drop-in clone-layout-placeholders benchmark does not support fixture {fixture_id}"
        )
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
    placeholders = list(WolfPresentation(output_path).slides[0].placeholders)
    placeholder_descriptors = [
        {
            "name": placeholder.name,
            "idx": placeholder.placeholder_format.idx,
            "type": str(placeholder.placeholder_format.type),
            "text": placeholder.text,
        }
        for placeholder in placeholders[-2:]
    ]
    semantic_pass = placeholder_descriptors == [
        {"name": "Title 3", "idx": 0, "type": "TITLE (1)", "text": ""},
        {
            "name": "Content Placeholder 4",
            "idx": 1,
            "type": "OBJECT (7)",
            "text": "",
        },
    ]
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "placeholder_count": len(placeholders),
        "placeholder_descriptors": placeholder_descriptors,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
