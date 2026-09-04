"""Deeper nested freeform drop-in benchmark result details."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import ADD_FREEFORM_EXPECTED_TEXT, ADD_FREEFORM_EXPECTED_TRANSFORM
from .benchmark_dropin_shape_freeform_details import GROUP_FREEFORM_TARGETS
from .benchmark_validation import _validate_output
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


def _dropin_build_deeper_nested_group_freeform_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_FREEFORM_TARGETS:
        raise RuntimeError(
            "drop-in build-deeper-nested-group-freeform benchmark does not "
            f"support fixture {fixture_id}"
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
    deeper_group = (
        nested_group.children[-1]
        if nested_group is not None and nested_group.children
        else None
    )
    shape_summary = (
        deeper_group.children[-1]
        if deeper_group is not None and deeper_group.children
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
        and deeper_group is not None
        and deeper_group.kind == "group"
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
