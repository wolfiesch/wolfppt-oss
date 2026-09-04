"""Text-run drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    APPENDED_PARAGRAPH_TEXT,
    FONT_FILL_EXPECTED,
    FONT_LANGUAGE_EXPECTED,
    MULTI_FORMAT_RUN_COUNT,
    REPLACED_PARAGRAPH_TEXT,
    RICH_FORMATTING_EXPECTED,
    TEXT_RUN_HYPERLINK_EXPECTED_ADDRESS,
)
from .benchmark_validation import _validate_output
from .benchmark_xml_inspection import (
    run_fill_for_text as _run_fill_for_text,
    run_formatting_by_texts as _run_formatting_by_texts,
    run_formatting_for_text as _run_formatting_for_text,
    run_language_for_text as _run_language_for_text,
)
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


def _text_fixture_paragraphs(summary: Any, fixture_id: str, operation: str) -> list[str]:
    if fixture_id == "text_basic/title_body_bullets":
        return summary.slides[0].shapes[1].paragraphs
    if fixture_id == "shapes/grouped_shapes":
        return summary.slides[0].shapes[0].children[0].paragraphs
    raise RuntimeError(
        f"drop-in {operation} benchmark does not support fixture {fixture_id}"
    )


def _text_fixture_first_text(fixture_id: str, operation: str) -> str:
    if fixture_id == "text_basic/title_body_bullets":
        return "Fast PPTX"
    if fixture_id == "shapes/grouped_shapes":
        return "Grouped Text"
    raise RuntimeError(
        f"drop-in {operation} benchmark does not support fixture {fixture_id}"
    )


def _dropin_formatting_edit_details(
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
    if fixture_id == "text_basic/title_body_bullets":
        semantic_pass = summary.slides[0].shapes[1].paragraphs == [
            "Fast PPTX",
            "Lossless first",
        ]
        run_formatting: dict[str, Any] = _run_formatting_for_text(output_path, "Fast PPTX")
        formatting_pass = run_formatting == RICH_FORMATTING_EXPECTED
    elif fixture_id == "workloads/multi_format_runs":
        expected_texts = _multi_format_texts()
        semantic_pass = summary.slides[0].shapes[0].paragraphs == ["".join(expected_texts)]
        found_formatting = _run_formatting_by_texts(output_path, expected_texts)
        failures = [
            text
            for text in expected_texts
            if found_formatting.get(text) != RICH_FORMATTING_EXPECTED
        ]
        formatting_pass = not failures
        run_formatting = {
            "checked_count": len(expected_texts),
            "failure_count": len(failures),
            "failures": failures[:5],
            "failures_truncated": len(failures) > 5,
        }
    elif fixture_id == "shapes/grouped_shapes":
        semantic_pass = summary.slides[0].shapes[0].children[0].text == "Grouped Text"
        run_formatting = _run_formatting_for_text(output_path, "Grouped Text")
        formatting_pass = run_formatting == RICH_FORMATTING_EXPECTED
    else:
        raise RuntimeError(f"drop-in formatting benchmark does not support fixture {fixture_id}")
    ok = semantic_pass and formatting_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "run_formatting_pass": formatting_pass,
        "run_formatting": run_formatting,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_font_language_edit_details(
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
    paragraphs = _text_fixture_paragraphs(summary, fixture_id, "font language")
    target_text = _text_fixture_first_text(fixture_id, "font language")
    expected_paragraphs = (
        ["Fast PPTX", "Lossless first"]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text"]
    )
    semantic_pass = paragraphs == expected_paragraphs
    language_id = _run_language_for_text(output_path, target_text)
    language_pass = language_id == FONT_LANGUAGE_EXPECTED
    ok = semantic_pass and language_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "language_pass": language_pass,
        "language_id": language_id,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_font_fill_edit_details(
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
    paragraphs = _text_fixture_paragraphs(summary, fixture_id, "font fill")
    target_text = _text_fixture_first_text(fixture_id, "font fill")
    expected_paragraphs = (
        ["Fast PPTX", "Lossless first"]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text"]
    )
    semantic_pass = paragraphs == expected_paragraphs
    font_fill = _run_fill_for_text(output_path, target_text)
    fill_pass = font_fill == FONT_FILL_EXPECTED
    ok = semantic_pass and fill_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "font_fill_pass": fill_pass,
        "font_fill": font_fill,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_run_formatting_edit_details(
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
    paragraphs = _text_fixture_paragraphs(summary, fixture_id, "add-run formatting")
    semantic_pass = paragraphs == (
        ["Fast PPTX Decks", "Lossless first"]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text Decks"]
    )
    run_formatting = _run_formatting_for_text(output_path, " Decks")
    formatting_pass = run_formatting == RICH_FORMATTING_EXPECTED
    ok = semantic_pass and formatting_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "run_formatting_pass": formatting_pass,
        "run_formatting": run_formatting,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_paragraph_run_formatting_edit_details(
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
    paragraphs = _text_fixture_paragraphs(
        summary,
        fixture_id,
        "add-paragraph run formatting",
    )
    semantic_pass = paragraphs == (
        ["Fast PPTX", "Lossless first", APPENDED_PARAGRAPH_TEXT]
        if fixture_id == "text_basic/title_body_bullets"
        else ["Grouped Text", APPENDED_PARAGRAPH_TEXT]
    )
    run_formatting = _run_formatting_for_text(output_path, APPENDED_PARAGRAPH_TEXT)
    formatting_pass = run_formatting == RICH_FORMATTING_EXPECTED
    ok = semantic_pass and formatting_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "run_formatting_pass": formatting_pass,
        "run_formatting": run_formatting,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_replace_run_formatting_edit_details(
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
    paragraphs = _text_fixture_paragraphs(summary, fixture_id, "replace-run formatting")
    semantic_pass = paragraphs == (
        ["Fast PPTX", REPLACED_PARAGRAPH_TEXT]
        if fixture_id == "text_basic/title_body_bullets"
        else [REPLACED_PARAGRAPH_TEXT]
    )
    run_formatting = _run_formatting_for_text(output_path, REPLACED_PARAGRAPH_TEXT)
    formatting_pass = run_formatting == RICH_FORMATTING_EXPECTED
    ok = semantic_pass and formatting_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "run_formatting_pass": formatting_pass,
        "run_formatting": run_formatting,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }

def _dropin_text_run_hyperlink_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id == "text_basic/title_body_bullets":
        run = (
            WolfPresentation(output_path)
            .slides[0]
            .shapes[1]
            .text_frame.paragraphs[0]
            .runs[0]
        )
        expected_text = "Fast PPTX"
    elif fixture_id == "shapes/grouped_shapes":
        run = (
            WolfPresentation(output_path)
            .slides[0]
            .shapes[0]
            .shapes[0]
            .text_frame.paragraphs[0]
            .runs[0]
        )
        expected_text = "Grouped Text"
    else:
        raise RuntimeError(
            f"drop-in text run hyperlink benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts
        == ["ppt/slides/_rels/slide1.xml.rels", "ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    address = run.hyperlink.address
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
        rels_xml = package.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
    hyperlink_xml = (
        "<a:hlinkClick" in slide_xml
        and TEXT_RUN_HYPERLINK_EXPECTED_ADDRESS in rels_xml
        and expected_text in slide_xml
    )
    hyperlink_pass = address == TEXT_RUN_HYPERLINK_EXPECTED_ADDRESS and hyperlink_xml
    ok = hyperlink_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": hyperlink_pass,
        "semantic_score": 1.0 if hyperlink_pass else 0.0,
        "hyperlink_pass": hyperlink_pass,
        "address": address,
        "hyperlink_xml": hyperlink_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }

def _multi_format_texts() -> list[str]:
    return [f"Run {run_idx:02d} " for run_idx in range(MULTI_FORMAT_RUN_COUNT)]
