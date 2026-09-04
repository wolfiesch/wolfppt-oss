"""Text-frame drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    TEXT_FRAME_AUTO_SIZE_EXPECTED,
    TEXT_FRAME_AUTO_SIZE_EXPECTED_NAME,
    TEXT_FRAME_FIT_TEXT_FONT_FAMILIES,
    TEXT_FRAME_FIT_TEXT_EXPECTED,
    TEXT_FRAME_MARGIN_EXPECTED,
    TEXT_FRAME_VERTICAL_ANCHOR_EXPECTED,
    TEXT_FRAME_VERTICAL_ANCHOR_EXPECTED_NAME,
    TEXT_FRAME_WORD_WRAP_EXPECTED,
)
from .benchmark_validation import _validate_output
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


def _output_text_frame_target(
    fixture_id: str,
    output_path: Path,
    operation: str,
) -> Any:
    prs = WolfPresentation(output_path)
    if fixture_id == "text_basic/title_body_bullets":
        return prs.slides[0].shapes[0].text_frame
    if fixture_id == "shapes/grouped_shapes":
        return prs.slides[0].shapes[0].shapes[0].text_frame
    raise RuntimeError(
        f"drop-in text frame {operation} benchmark does not support fixture {fixture_id}"
    )


def _dropin_text_frame_margin_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    text_frame = _output_text_frame_target(fixture_id, output_path, "margin")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    margins = {
        "margin_left": int(text_frame.margin_left),
        "margin_right": int(text_frame.margin_right),
        "margin_top": int(text_frame.margin_top),
        "margin_bottom": int(text_frame.margin_bottom),
    }
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    margin_xml = all(
        f'{attr}="{value}"' in slide_xml
        for attr, value in {
            "lIns": TEXT_FRAME_MARGIN_EXPECTED["margin_left"],
            "rIns": TEXT_FRAME_MARGIN_EXPECTED["margin_right"],
            "tIns": TEXT_FRAME_MARGIN_EXPECTED["margin_top"],
            "bIns": TEXT_FRAME_MARGIN_EXPECTED["margin_bottom"],
        }.items()
    )
    margin_pass = margins == TEXT_FRAME_MARGIN_EXPECTED and margin_xml
    ok = margin_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": margin_pass,
        "semantic_score": 1.0 if margin_pass else 0.0,
        "margin_pass": margin_pass,
        "margins": margins,
        "margin_xml": margin_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_text_frame_word_wrap_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    text_frame = _output_text_frame_target(fixture_id, output_path, "word-wrap")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    word_wrap_xml = 'wrap="square"' in slide_xml
    word_wrap_pass = (
        text_frame.word_wrap is TEXT_FRAME_WORD_WRAP_EXPECTED
        and word_wrap_xml
    )
    ok = word_wrap_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": word_wrap_pass,
        "semantic_score": 1.0 if word_wrap_pass else 0.0,
        "word_wrap_pass": word_wrap_pass,
        "word_wrap": text_frame.word_wrap,
        "word_wrap_xml": word_wrap_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_text_frame_vertical_anchor_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    text_frame = _output_text_frame_target(fixture_id, output_path, "vertical-anchor")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    vertical_anchor = text_frame.vertical_anchor
    vertical_anchor_name = getattr(vertical_anchor, "name", vertical_anchor)
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    vertical_anchor_xml = f'anchor="{TEXT_FRAME_VERTICAL_ANCHOR_EXPECTED}"' in slide_xml
    vertical_anchor_pass = (
        vertical_anchor_name == TEXT_FRAME_VERTICAL_ANCHOR_EXPECTED_NAME
        and vertical_anchor_xml
    )
    ok = vertical_anchor_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": vertical_anchor_pass,
        "semantic_score": 1.0 if vertical_anchor_pass else 0.0,
        "vertical_anchor_pass": vertical_anchor_pass,
        "vertical_anchor": vertical_anchor_name,
        "vertical_anchor_xml": vertical_anchor_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_text_frame_auto_size_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    text_frame = _output_text_frame_target(fixture_id, output_path, "auto-size")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    auto_size = text_frame.auto_size
    auto_size_name = getattr(auto_size, "name", auto_size)
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    auto_size_xml = (
        f"<a:{TEXT_FRAME_AUTO_SIZE_EXPECTED}/>" in slide_xml.replace(" />", "/>")
    )
    auto_size_pass = (
        auto_size_name == TEXT_FRAME_AUTO_SIZE_EXPECTED_NAME
        and auto_size_xml
    )
    ok = auto_size_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": auto_size_pass,
        "semantic_score": 1.0 if auto_size_pass else 0.0,
        "auto_size_pass": auto_size_pass,
        "auto_size": auto_size_name,
        "auto_size_xml": auto_size_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_text_frame_fit_text_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    text_frame = _output_text_frame_target(fixture_id, output_path, "fit-text")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    run = text_frame.paragraphs[0].runs[0]
    auto_size = text_frame.auto_size
    auto_size_name = getattr(auto_size, "name", auto_size)
    font = {
        "font_family": run.font.name,
        "size": None if run.font.size is None else int(run.font.size),
        "bold": run.font.bold,
        "italic": run.font.italic,
    }
    font_family = font["font_family"]
    font_family_ok = font_family in TEXT_FRAME_FIT_TEXT_FONT_FAMILIES
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    compact_xml = slide_xml.replace(" />", "/>")
    fit_text_xml = (
        'wrap="square"' in slide_xml
        and "<a:noAutofit/>" in compact_xml
        and f'sz="{TEXT_FRAME_FIT_TEXT_EXPECTED["size_xml"]}"' in slide_xml
        and 'b="1"' in slide_xml
        and 'i="1"' in slide_xml
        and font_family is not None
        and f'<a:latin typeface="{font_family}"/>' in compact_xml
    )
    fit_text_pass = (
        text_frame.word_wrap is True
        and auto_size_name == "NONE"
        and font_family_ok
        and font == {
            "font_family": font_family,
            "size": TEXT_FRAME_FIT_TEXT_EXPECTED["size"],
            "bold": TEXT_FRAME_FIT_TEXT_EXPECTED["bold"],
            "italic": TEXT_FRAME_FIT_TEXT_EXPECTED["italic"],
        }
        and fit_text_xml
    )
    ok = fit_text_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": fit_text_pass,
        "semantic_score": 1.0 if fit_text_pass else 0.0,
        "fit_text_pass": fit_text_pass,
        "word_wrap": text_frame.word_wrap,
        "auto_size": auto_size_name,
        "font": font,
        "font_family_ok": font_family_ok,
        "fit_text_xml": fit_text_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
