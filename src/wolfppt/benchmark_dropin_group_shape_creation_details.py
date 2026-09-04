"""Grouped-shape creation drop-in benchmark detail readers."""
# ruff: noqa: F401

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    ADD_SHAPE_EXPECTED_PRESET,
    ADD_SHAPE_EXPECTED_TEXT,
    ADD_SHAPE_EXPECTED_TRANSFORM,
    ADD_TEXTBOX_EXPECTED_TEXT,
    ADD_TEXTBOX_EXPECTED_TRANSFORM,
)
from .benchmark_validation import _validate_output
from .benchmark_dropin_group_shape_child_details import (
    _dropin_add_group_auto_shape_details,
    _dropin_add_group_textbox_details,
)
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

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


def _dropin_add_group_shape_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in add-group-shape benchmark does not support fixture {fixture_id}"
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
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    group_xml_pass = "<p:grpSp>" in slide_xml
    semantic_pass = (
        shape_summary.kind == "group"
        and shape_summary.children == []
        and transform == {"x": 0, "y": 0, "cx": 0, "cy": 0}
    )
    ok = semantic_pass and group_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "group_xml_pass": group_xml_pass,
        "group_name": shape_summary.name,
        "shape_transform": transform,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }

def _dropin_group_existing_shapes_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            "drop-in group-existing-shapes benchmark does not support fixture "
            f"{fixture_id}"
        )
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
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
    expected_child_names = [
        source_summary.slides[0].shapes[1].name,
        source_summary.slides[0].shapes[0].name,
    ]
    groups = [shape for shape in summary.slides[0].shapes if shape.kind == "group"]
    matching_groups = [
        shape
        for shape in groups
        if [child.name for child in shape.children] == expected_child_names
    ]
    group = matching_groups[0] if matching_groups else (groups[0] if groups else None)
    child_names = [child.name for child in group.children] if group else []
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    group_xml_pass = "<p:grpSp>" in slide_xml
    semantic_pass = (
        group is not None
        and group.kind == "group"
        and child_names == expected_child_names
    )
    ok = semantic_pass and group_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "group_xml_pass": group_xml_pass,
        "group_name": None if group is None else group.name,
        "group_child_names": child_names,
        "expected_group_child_names": expected_child_names,
        "group_child_count": len(child_names),
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_nested_group_shape_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            f"drop-in add-nested-group-shape benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
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
    nested = group.children[-1] if group.children else None
    transform = None
    if nested is not None and nested.transform is not None:
        transform = {
            "x": nested.transform.x,
            "y": nested.transform.y,
            "cx": nested.transform.cx,
            "cy": nested.transform.cy,
        }
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    group_xml_pass = "<p:grpSp>" in slide_xml
    semantic_pass = (
        nested is not None
        and nested.kind == "group"
        and nested.children == []
        and transform == {"x": 0, "y": 0, "cx": 0, "cy": 0}
        and parent_preserved
    )
    ok = semantic_pass and group_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "group_xml_pass": group_xml_pass,
        "shape_transform": transform,
        "group_name": None if nested is None else nested.name,
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


def _dropin_add_deeper_nested_group_shape_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-shape benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
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
    nested = group.children[-1] if group.children else None
    deeper = nested.children[-1] if nested is not None and nested.children else None
    transform = None
    if deeper is not None and deeper.transform is not None:
        transform = {
            "x": deeper.transform.x,
            "y": deeper.transform.y,
            "cx": deeper.transform.cx,
            "cy": deeper.transform.cy,
        }
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    group_xml_pass = "<p:grpSp>" in slide_xml
    semantic_pass = (
        nested is not None
        and nested.kind == "group"
        and deeper is not None
        and deeper.kind == "group"
        and deeper.children == []
        and transform == {"x": 0, "y": 0, "cx": 0, "cy": 0}
        and parent_preserved
    )
    ok = semantic_pass and group_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "group_xml_pass": group_xml_pass,
        "shape_transform": transform,
        "group_name": None if deeper is None else deeper.name,
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


def _dropin_group_existing_children_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id != "workloads/customer_success_review_pack":
        raise RuntimeError(
            "drop-in group-existing-children benchmark does not support fixture "
            f"{fixture_id}"
        )
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    expected_changed_parts = ["ppt/slides/slide5.xml"]
    python_pptx_changed_parts = ["[Content_Types].xml", "ppt/slides/slide5.xml"]
    package_delta_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts
        in (expected_changed_parts, python_pptx_changed_parts)
        and package_diff.removed_parts == []
    )
    parent = summary.slides[4].shapes[1]
    nested = parent.children[-1] if parent.children else None
    parent_child_names = [child.name for child in parent.children]
    nested_child_names = [child.name for child in nested.children] if nested else []
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide5.xml").decode("utf-8")
    group_xml_pass = "<p:grpSp>" in slide_xml and 'name="Group 7"' in slide_xml
    semantic_pass = (
        nested is not None
        and nested.kind == "group"
        and nested.name == "Group 7"
        and parent_child_names == [
            "Rounded Rectangle 5",
            "Rounded Rectangle 6",
            "Group 7",
        ]
        and nested_child_names == ["Rounded Rectangle 4", "Rounded Rectangle 3"]
    )
    ok = semantic_pass and group_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "group_xml_pass": group_xml_pass,
        "parent_child_names": parent_child_names,
        "nested_child_names": nested_child_names,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "package_slide_only": package_diff.changed_parts == expected_changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_nested_group_auto_shape_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            f"drop-in add-nested-group-auto-shape benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
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
    shape_summary = (
        nested.children[-1] if nested is not None and nested.children else None
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
    auto_shape_type = shape.auto_shape_type
    auto_shape_type_payload = {
        "value": int(auto_shape_type),
        "xml_value": getattr(auto_shape_type, "xml_value", None),
        "label": str(auto_shape_type),
    }
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    auto_shape_type_pass = (
        auto_shape_type_payload["xml_value"] == ADD_SHAPE_EXPECTED_PRESET
    )
    shape_xml_pass = f'<a:prstGeom prst="{ADD_SHAPE_EXPECTED_PRESET}">' in slide_xml
    parent_preserved = parent_child_names == expected_child_names
    semantic_pass = (
        group.kind == "group"
        and nested is not None
        and nested.kind == "group"
        and shape_summary is not None
        and shape_summary.kind == "shape"
        and shape_summary.text == ADD_SHAPE_EXPECTED_TEXT
        and transform == ADD_SHAPE_EXPECTED_TRANSFORM
    )
    ok = (
        semantic_pass
        and auto_shape_type_pass
        and shape_xml_pass
        and parent_preserved
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "auto_shape_pass": semantic_pass,
        "auto_shape_type_pass": auto_shape_type_pass,
        "shape_xml_pass": shape_xml_pass,
        "auto_shape_type": auto_shape_type_payload,
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


def _dropin_add_nested_group_textbox_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            f"drop-in add-nested-group-textbox benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
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
    textbox = nested.children[-1] if nested is not None and nested.children else None
    transform = None
    if textbox is not None and textbox.transform is not None:
        transform = {
            "x": textbox.transform.x,
            "y": textbox.transform.y,
            "cx": textbox.transform.cx,
            "cy": textbox.transform.cy,
        }
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    shape = (
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
        .shapes[-1]
    )
    shape_type = str(shape.shape_type)
    shape_type_pass = shape_type == "TEXT_BOX (17)"
    semantic_pass = (
        group.kind == "group"
        and nested is not None
        and nested.kind == "group"
        and textbox is not None
        and textbox.kind == "shape"
        and textbox.text == ADD_TEXTBOX_EXPECTED_TEXT
        and transform == ADD_TEXTBOX_EXPECTED_TRANSFORM
    )
    textbox_xml_pass = (
        "<p:grpSp>" in slide_xml
        and "<p:sp>" in slide_xml
        and "<a:spAutoFit/>" in slide_xml
    )
    parent_preserved = parent_child_names == expected_child_names
    ok = (
        semantic_pass
        and textbox_xml_pass
        and shape_type_pass
        and parent_preserved
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "textbox_pass": semantic_pass,
        "textbox_xml_pass": textbox_xml_pass,
        "textbox_shape_type_pass": shape_type_pass,
        "textbox_shape_type": shape_type,
        "textbox_text": None if textbox is None else textbox.text,
        "textbox_transform": transform,
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


def _dropin_add_deeper_nested_group_textbox_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-textbox benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
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
    textbox = deeper.children[-1] if deeper is not None and deeper.children else None
    transform = None
    if textbox is not None and textbox.transform is not None:
        transform = {
            "x": textbox.transform.x,
            "y": textbox.transform.y,
            "cx": textbox.transform.cx,
            "cy": textbox.transform.cy,
        }
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    shape = (
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
        .shapes[-1]
        .shapes[-1]
    )
    shape_type = str(shape.shape_type)
    shape_type_pass = shape_type == "TEXT_BOX (17)"
    semantic_pass = (
        group.kind == "group"
        and nested is not None
        and nested.kind == "group"
        and deeper is not None
        and deeper.kind == "group"
        and textbox is not None
        and textbox.kind == "shape"
        and textbox.text == ADD_TEXTBOX_EXPECTED_TEXT
        and transform == ADD_TEXTBOX_EXPECTED_TRANSFORM
    )
    textbox_xml_pass = (
        "<p:grpSp>" in slide_xml
        and "<p:sp>" in slide_xml
        and "<a:spAutoFit/>" in slide_xml
    )
    parent_preserved = parent_child_names == expected_child_names
    ok = (
        semantic_pass
        and textbox_xml_pass
        and shape_type_pass
        and parent_preserved
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "textbox_pass": semantic_pass,
        "textbox_xml_pass": textbox_xml_pass,
        "textbox_shape_type_pass": shape_type_pass,
        "textbox_shape_type": shape_type,
        "textbox_text": None if textbox is None else textbox.text,
        "textbox_transform": transform,
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


def _dropin_add_deeper_nested_group_auto_shape_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-auto-shape benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
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
    shape_summary = (
        deeper.children[-1] if deeper is not None and deeper.children else None
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
        .shapes[-1]
    )
    auto_shape_type = shape.auto_shape_type
    auto_shape_type_payload = {
        "value": int(auto_shape_type),
        "xml_value": getattr(auto_shape_type, "xml_value", None),
        "label": str(auto_shape_type),
    }
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    auto_shape_type_pass = (
        auto_shape_type_payload["xml_value"] == ADD_SHAPE_EXPECTED_PRESET
    )
    shape_xml_pass = f'<a:prstGeom prst="{ADD_SHAPE_EXPECTED_PRESET}">' in slide_xml
    parent_preserved = parent_child_names == expected_child_names
    semantic_pass = (
        group.kind == "group"
        and nested is not None
        and nested.kind == "group"
        and deeper is not None
        and deeper.kind == "group"
        and shape_summary is not None
        and shape_summary.kind == "shape"
        and shape_summary.text == ADD_SHAPE_EXPECTED_TEXT
        and transform == ADD_SHAPE_EXPECTED_TRANSFORM
    )
    ok = (
        semantic_pass
        and auto_shape_type_pass
        and shape_xml_pass
        and parent_preserved
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "auto_shape_pass": semantic_pass,
        "auto_shape_type_pass": auto_shape_type_pass,
        "shape_xml_pass": shape_xml_pass,
        "auto_shape_type": auto_shape_type_payload,
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
