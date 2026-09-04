"""Shape creation drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    ADD_SHAPE_EXPECTED_PRESET,
    ADD_SHAPE_EXPECTED_TEXT,
    ADD_SHAPE_EXPECTED_TRANSFORM,
    ADD_SLIDE_EXPECTED_CHANGED_PARTS,
    ADD_TABLE_EXPECTED_ROWS,
    ADD_TABLE_EXPECTED_TRANSFORM,
    ADD_TEXTBOX_EXPECTED_TEXT,
    ADD_TEXTBOX_EXPECTED_TRANSFORM,
    ADD_TITLE_SLIDE_EXPECTED_TEXTS,
)
from .benchmark_validation import _validate_output
from .benchmark_dropin_shape_connector_chart_details import (
    _dropin_add_chart_details,
    _dropin_add_chart_template_family_details,
    _dropin_add_connector_details,
    _dropin_add_group_chart_details,
    _dropin_add_group_connector_details,
    _dropin_add_nested_group_chart_details,
    _dropin_add_nested_group_connector_details,
    _dropin_add_xy_scatter_template_family_details,
    _dropin_connector_connection_edit_details,
    _dropin_existing_connector_connection_edit_details,
    _dropin_group_connector_connection_edit_details,
)
from .benchmark_dropin_shape_freeform_details import (
    _dropin_build_freeform_details,
    _dropin_build_group_freeform_details,
    _dropin_build_nested_group_freeform_details,
    _dropin_clone_layout_placeholders_details,
)
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

TOP_LEVEL_CREATION_FIXTURES = (
    "text_basic/title_body_bullets",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)


def _dropin_add_shape_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in add-shape benchmark does not support fixture {fixture_id}"
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
    auto_shape_type = shape.auto_shape_type
    auto_shape_type_payload = {
        "value": int(auto_shape_type),
        "xml_value": getattr(auto_shape_type, "xml_value", None),
        "label": str(auto_shape_type),
    }
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    auto_shape_type_pass = (
        auto_shape_type_payload["xml_value"] == ADD_SHAPE_EXPECTED_PRESET
    )
    shape_xml_pass = f'<a:prstGeom prst="{ADD_SHAPE_EXPECTED_PRESET}">' in slide_xml
    semantic_pass = (
        shape_summary.kind == "shape"
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
        "auto_shape_type_pass": auto_shape_type_pass,
        "shape_xml_pass": shape_xml_pass,
        "auto_shape_type": auto_shape_type_payload,
        "shape_transform": transform,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
def _dropin_add_textbox_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in add-textbox benchmark does not support fixture {fixture_id}"
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
    shape_type = str(WolfPresentation(output_path).slides[0].shapes[-1].shape_type)
    shape_type_pass = shape_type == "TEXT_BOX (17)"
    semantic_pass = (
        shape_summary.kind == "shape"
        and shape_summary.text == ADD_TEXTBOX_EXPECTED_TEXT
        and transform == ADD_TEXTBOX_EXPECTED_TRANSFORM
    )
    ok = semantic_pass and shape_type_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "text_box_pass": shape_type_pass,
        "textbox_text": shape_summary.text,
        "textbox_transform": transform,
        "textbox_shape_type": shape_type,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_table_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in add-table benchmark does not support fixture {fixture_id}"
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
    table_rows = shape_summary.tables[0].rows if shape_summary.tables else []
    transform = None
    if shape_summary.transform is not None:
        transform = {
            "x": shape_summary.transform.x,
            "y": shape_summary.transform.y,
            "cx": shape_summary.transform.cx,
            "cy": shape_summary.transform.cy,
        }
    shape_type = str(WolfPresentation(output_path).slides[0].shapes[-1].shape_type)
    shape_type_pass = shape_type == "TABLE (19)"
    semantic_pass = (
        shape_summary.kind == "graphic_frame"
        and table_rows == ADD_TABLE_EXPECTED_ROWS
        and transform == ADD_TABLE_EXPECTED_TRANSFORM
    )
    ok = semantic_pass and shape_type_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_pass": semantic_pass,
        "table_rows": table_rows,
        "table_transform": transform,
        "table_shape_type": shape_type,
        "table_shape_type_pass": shape_type_pass,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_slide_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in add-slide benchmark does not support fixture {fixture_id}"
        )
    source_summary = extract_semantics(fixture_path)
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    added_slide_index = len(source_summary.slides)
    added_slide_number = added_slide_index + 1
    expected_added_parts = [
        f"ppt/slides/_rels/slide{added_slide_number}.xml.rels",
        f"ppt/slides/slide{added_slide_number}.xml",
    ]
    package_delta_ok = (
        package_diff.added_parts == expected_added_parts
        and package_diff.changed_parts == ADD_SLIDE_EXPECTED_CHANGED_PARTS
        and package_diff.removed_parts == []
    )
    added_slide_texts = (
        summary.slides[added_slide_index].texts
        if len(summary.slides) > added_slide_index
        else None
    )
    semantic_pass = (
        len(summary.slides) == len(source_summary.slides) + 1
        and added_slide_texts == []
    )
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "slide_pass": semantic_pass,
        "slide_count": len(summary.slides),
        "source_slide_count": len(source_summary.slides),
        "added_slide_texts": added_slide_texts,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_title_slide_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            f"drop-in add-title-slide benchmark does not support fixture {fixture_id}"
        )
    source_summary = extract_semantics(fixture_path)
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    added_slide_index = len(source_summary.slides)
    added_slide_number = added_slide_index + 1
    expected_added_parts = [
        f"ppt/slides/_rels/slide{added_slide_number}.xml.rels",
        f"ppt/slides/slide{added_slide_number}.xml",
    ]
    package_delta_ok = (
        package_diff.added_parts == expected_added_parts
        and package_diff.changed_parts == ADD_SLIDE_EXPECTED_CHANGED_PARTS
        and package_diff.removed_parts == []
    )
    added_slide_texts = (
        summary.slides[added_slide_index].texts
        if len(summary.slides) > added_slide_index
        else None
    )
    output_prs = WolfPresentation(output_path)
    placeholders = (
        [
            {
                "name": placeholder.name,
                "text": placeholder.text,
                "placeholder_idx": placeholder.placeholder_format.idx,
                "placeholder_type": str(placeholder.placeholder_format.type),
            }
            for placeholder in output_prs.slides[added_slide_index].placeholders
        ]
        if len(summary.slides) > added_slide_index
        else []
    )
    placeholder_texts = [placeholder["text"] for placeholder in placeholders]
    semantic_pass = (
        len(summary.slides) == len(source_summary.slides) + 1
        and added_slide_texts == ADD_TITLE_SLIDE_EXPECTED_TEXTS
        and placeholder_texts == ADD_TITLE_SLIDE_EXPECTED_TEXTS
    )
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "slide_pass": semantic_pass,
        "slide_count": len(summary.slides),
        "source_slide_count": len(source_summary.slides),
        "added_slide_texts": added_slide_texts,
        "placeholder_count": len(placeholders),
        "placeholder_texts": placeholder_texts,
        "placeholders": placeholders,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
