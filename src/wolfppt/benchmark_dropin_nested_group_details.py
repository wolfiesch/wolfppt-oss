"""Nested-group drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_validation import _validate_output
from .benchmark_dropin_nested_group_actions import GROUP_EXISTING_CHILD_TARGETS
from .extractor import extract_semantics
from .package_diff import diff_packages


def _dropin_group_existing_nested_children_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_EXISTING_CHILD_TARGETS:
        raise RuntimeError(
            "drop-in group-existing-nested-children benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_EXISTING_CHILD_TARGETS[fixture_id]
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
    expected_parent_names = [child.name for child in source_group.children]
    parent_names = [
        child.name for child in group.children[: len(expected_parent_names)]
    ]
    parent_preserved = parent_names == expected_parent_names
    nested = group.children[-1]
    grouped = nested.children[-1] if nested.children else None
    nested_child_count = len(nested.children)
    grouped_child_text = [child.text for child in grouped.children] if grouped else []
    transform = None
    if grouped is not None and grouped.transform is not None:
        transform = {
            "x": grouped.transform.x,
            "y": grouped.transform.y,
            "cx": grouped.transform.cx,
            "cy": grouped.transform.cy,
        }
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    group_xml_pass = "<p:grpSp>" in slide_xml
    semantic_pass = (
        nested.kind == "group"
        and nested_child_count == 1
        and grouped is not None
        and grouped.kind == "group"
        and grouped_child_text == ["Second", "First"]
        and parent_preserved
    )
    ok = semantic_pass and group_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "group_xml_pass": group_xml_pass,
        "nested_child_count": nested_child_count,
        "grouped_name": None if grouped is None else grouped.name,
        "grouped_child_text": grouped_child_text,
        "grouped_transform": transform,
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_names,
        "expected_parent_child_names": expected_parent_names,
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


def _dropin_group_existing_deeper_nested_children_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_EXISTING_CHILD_TARGETS:
        raise RuntimeError(
            "drop-in group-existing-deeper-nested-children benchmark does not "
            f"support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_EXISTING_CHILD_TARGETS[fixture_id]
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
    expected_parent_names = [child.name for child in source_group.children]
    parent_names = [
        child.name for child in group.children[: len(expected_parent_names)]
    ]
    parent_preserved = parent_names == expected_parent_names
    nested = group.children[-1]
    deeper = nested.children[-1] if nested.children else None
    grouped = deeper.children[-1] if deeper.children else None
    grouped_child_text = [child.text for child in grouped.children] if grouped else []
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    group_xml_pass = "<p:grpSp>" in slide_xml
    semantic_pass = (
        nested.kind == "group"
        and deeper is not None
        and deeper.kind == "group"
        and len(deeper.children) == 1
        and grouped is not None
        and grouped.kind == "group"
        and grouped_child_text == ["Second", "First"]
        and parent_preserved
    )
    ok = semantic_pass and group_xml_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "group_xml_pass": group_xml_pass,
        "nested_child_count": len(nested.children),
        "deeper_child_count": 0 if deeper is None else len(deeper.children),
        "grouped_name": None if grouped is None else grouped.name,
        "grouped_child_text": grouped_child_text,
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_names,
        "expected_parent_child_names": expected_parent_names,
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
