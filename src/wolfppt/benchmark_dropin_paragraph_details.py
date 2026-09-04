"""Paragraph drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .benchmark_cases import (
    APPENDED_PARAGRAPH_TEXT,
    PARAGRAPH_ALIGNMENT_EXPECTED,
    PARAGRAPH_CLEAR_EXPECTED,
    PARAGRAPH_FONT_EXPECTED,
    PARAGRAPH_LEVEL_EXPECTED,
    PARAGRAPH_LINE_BREAK_EXPECTED,
    PARAGRAPH_SPACING_EXPECTED,
)
from .benchmark_validation import _validate_output
from .benchmark_xml_inspection import (
    paragraph_alignment_for_text as _paragraph_alignment_for_text,
    paragraph_content_child_count as _paragraph_content_child_count,
    paragraph_font_for_text as _paragraph_font_for_text,
    paragraph_level_for_text as _paragraph_level_for_text,
    paragraph_line_break_count as _paragraph_line_break_count,
    paragraph_spacing_for_text as _paragraph_spacing_for_text,
)
from .extractor import extract_semantics
from .package_diff import diff_packages


def _paragraph_fixture_payload(
    summary: Any,
    fixture_id: str,
    operation: str,
) -> tuple[list[str], str, int]:
    if fixture_id == "text_basic/title_body_bullets":
        return summary.slides[0].shapes[1].paragraphs, "Fast PPTX", 1
    if fixture_id == "shapes/grouped_shapes":
        return summary.slides[0].shapes[0].children[0].paragraphs, "Grouped Text", 0
    raise RuntimeError(
        f"drop-in {operation} benchmark does not support fixture {fixture_id}"
    )


def _dropin_paragraph_format_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    paragraphs, target_text, _shape_index = _paragraph_fixture_payload(
        summary,
        fixture_id,
        "paragraph format",
    )
    semantic_pass = paragraphs == (
        ["Fast PPTX", "Lossless first"]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text"]
    )
    alignment = _paragraph_alignment_for_text(output_path, target_text)
    alignment_pass = alignment == PARAGRAPH_ALIGNMENT_EXPECTED
    ok = semantic_pass and alignment_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "paragraph_alignment_pass": alignment_pass,
        "paragraph_alignment": alignment,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_paragraph_level_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    paragraphs, target_text, _shape_index = _paragraph_fixture_payload(
        summary,
        fixture_id,
        "paragraph level",
    )
    semantic_pass = paragraphs == (
        ["Fast PPTX", "Lossless first"]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text"]
    )
    level = _paragraph_level_for_text(output_path, target_text)
    level_pass = level == PARAGRAPH_LEVEL_EXPECTED
    ok = semantic_pass and level_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "paragraph_level_pass": level_pass,
        "paragraph_level": level,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_paragraph_spacing_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    paragraphs, target_text, _shape_index = _paragraph_fixture_payload(
        summary,
        fixture_id,
        "paragraph spacing",
    )
    semantic_pass = paragraphs == (
        ["Fast PPTX", "Lossless first"]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text"]
    )
    spacing = _paragraph_spacing_for_text(output_path, target_text)
    spacing_pass = spacing == PARAGRAPH_SPACING_EXPECTED
    ok = semantic_pass and spacing_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "paragraph_spacing_pass": spacing_pass,
        "paragraph_spacing": spacing,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_paragraph_clear_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    paragraphs, _target_text, shape_index = _paragraph_fixture_payload(
        summary,
        fixture_id,
        "paragraph clear",
    )
    semantic_pass = paragraphs == (
        PARAGRAPH_CLEAR_EXPECTED
        if fixture_id == "text_basic/title_body_bullets"
        else [""]
    )
    content_child_count = _paragraph_content_child_count(
        output_path,
        shape_index=shape_index,
        paragraph_index=0,
    )
    paragraph_clear_pass = content_child_count == 0
    ok = semantic_pass and paragraph_clear_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "paragraph_clear_pass": paragraph_clear_pass,
        "paragraph_content_child_count": content_child_count,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_paragraph_line_break_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    paragraphs, _target_text, shape_index = _paragraph_fixture_payload(
        summary,
        fixture_id,
        "paragraph line-break",
    )
    semantic_pass = paragraphs == (
        PARAGRAPH_LINE_BREAK_EXPECTED
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text\vAfter"]
    )
    line_break_count = _paragraph_line_break_count(
        output_path,
        shape_index=shape_index,
        paragraph_index=0,
    )
    line_break_pass = line_break_count == 1
    ok = semantic_pass and line_break_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "paragraph_line_break_pass": line_break_pass,
        "paragraph_line_break_count": line_break_count,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_paragraph_font_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    paragraphs, target_text, _shape_index = _paragraph_fixture_payload(
        summary,
        fixture_id,
        "paragraph font",
    )
    semantic_pass = paragraphs == (
        ["Fast PPTX", "Lossless first"]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text"]
    )
    font = _paragraph_font_for_text(output_path, target_text)
    font_pass = font == PARAGRAPH_FONT_EXPECTED
    ok = semantic_pass and font_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "paragraph_font_pass": font_pass,
        "paragraph_font": font,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_paragraph_format_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    paragraphs, _target_text, _shape_index = _paragraph_fixture_payload(
        summary,
        fixture_id,
        "add-paragraph format",
    )
    semantic_pass = paragraphs == (
        ["Fast PPTX", "Lossless first", APPENDED_PARAGRAPH_TEXT]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text", APPENDED_PARAGRAPH_TEXT]
    )
    alignment = _paragraph_alignment_for_text(output_path, APPENDED_PARAGRAPH_TEXT)
    level = _paragraph_level_for_text(output_path, APPENDED_PARAGRAPH_TEXT)
    spacing = _paragraph_spacing_for_text(output_path, APPENDED_PARAGRAPH_TEXT)
    format_pass = (
        alignment == PARAGRAPH_ALIGNMENT_EXPECTED
        and level == PARAGRAPH_LEVEL_EXPECTED
        and spacing == PARAGRAPH_SPACING_EXPECTED
    )
    ok = semantic_pass and format_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "appended_paragraph_format_pass": format_pass,
        "paragraph_alignment": alignment,
        "paragraph_level": level,
        "paragraph_spacing": spacing,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
