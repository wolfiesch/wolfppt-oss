"""Non-nested group child benchmark detail readers."""

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
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

GROUP_SHAPE_TARGETS = {
    "shapes/grouped_shapes": (0, 0),
    "workloads/management_reporting_deck": (2, 1),
    "workloads/customer_success_review_pack": (4, 1),
}


def _dropin_add_group_textbox_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            f"drop-in add-group-textbox benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
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
    textbox = group.children[-1] if group.children else None
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
    )
    shape_type = str(shape.shape_type)
    shape_type_pass = shape_type == "TEXT_BOX (17)"
    semantic_pass = (
        group.kind == "group"
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
    ok = (
        semantic_pass
        and textbox_xml_pass
        and shape_type_pass
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


def _dropin_add_group_auto_shape_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_SHAPE_TARGETS:
        raise RuntimeError(
            f"drop-in add-group-auto-shape benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_SHAPE_TARGETS[fixture_id]
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
    semantic_pass = (
        group.kind == "group"
        and shape_summary is not None
        and shape_summary.kind == "shape"
        and shape_summary.text == ADD_SHAPE_EXPECTED_TEXT
        and transform == ADD_SHAPE_EXPECTED_TRANSFORM
    )
    ok = (
        semantic_pass
        and auto_shape_type_pass
        and shape_xml_pass
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
