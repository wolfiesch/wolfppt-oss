"""Notes drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .benchmark_cases import (
    CREATE_NOTES_SLIDE_EXPECTED,
    NOTES_BACKGROUND_EXPECTED_RGB,
    NOTES_PARAGRAPH_RUN_EXPECTED,
    NOTES_PLACEHOLDER_HYPERLINK_EXPECTED_ADDRESS,
    NOTES_PLACEHOLDER_CLONE_EXPECTED,
    NOTES_RUN_HYPERLINK_EXPECTED_ADDRESS,
    NOTES_TEXT_EXPECTED,
    NOTES_TEXT_FRAME_FLOW_EXPECTED,
)
from .benchmark_validation import _validate_output
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


_MIXED_WORKLOAD_FIXTURES = {
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
}

_NOTES_EDIT_FIXTURES = {
    "notes/speaker_notes",
    *_MIXED_WORKLOAD_FIXTURES,
}


def _dropin_notes_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
    expected_notes_text: str,
    operation_label: str,
) -> dict[str, Any]:
    if fixture_id not in _NOTES_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in {operation_label} benchmark does not support fixture {fixture_id}"
        )
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_notes_part = _first_slide_notes_part(output_path)
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_notes_part]
        and package_diff.removed_parts == []
    )
    notes_pass = summary.slides[0].notes == expected_notes_text.splitlines()
    visible_slide_preserved = summary.slides[0].texts == source_summary.slides[
        0
    ].texts and [shape.text for shape in summary.slides[0].shapes] == [
        shape.text for shape in source_summary.slides[0].shapes
    ]
    semantic_pass = notes_pass and visible_slide_preserved
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "notes_pass": notes_pass,
        "visible_slide_preserved": visible_slide_preserved,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_notes_part": changed_notes_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_notes_text_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_notes_edit_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
        NOTES_TEXT_EXPECTED,
        "notes text",
    )


def _dropin_notes_text_frame_flow_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _NOTES_EDIT_FIXTURES:
        raise RuntimeError(
            "drop-in notes text-frame flow benchmark does not support fixture "
            f"{fixture_id}"
        )
    output_prs = WolfPresentation(output_path)
    source_summary = extract_semantics(fixture_path)
    output_summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    changed_notes_part = _first_slide_notes_part(output_path)
    frame = output_prs.slides[0].notes_slide.notes_text_frame
    auto_size = frame.auto_size
    vertical_anchor = frame.vertical_anchor
    details = {
        "margin_left": int(frame.margin_left),
        "margin_right": int(frame.margin_right),
        "margin_top": int(frame.margin_top),
        "margin_bottom": int(frame.margin_bottom),
        "word_wrap": frame.word_wrap,
        "vertical_anchor": getattr(vertical_anchor, "name", vertical_anchor),
        "auto_size": getattr(auto_size, "name", auto_size),
    }
    with ZipFile(output_path) as package:
        notes_xml = package.read(changed_notes_part).decode("utf-8")
    expected = NOTES_TEXT_FRAME_FLOW_EXPECTED
    margin_pass = all(
        details[key] == expected[key]
        for key in ("margin_left", "margin_right", "margin_top", "margin_bottom")
    )
    flow_pass = (
        details["word_wrap"] is expected["word_wrap"]
        and details["vertical_anchor"] == expected["vertical_anchor"]
        and details["auto_size"] == expected["auto_size"]
    )
    xml_pass = all(
        marker in notes_xml
        for marker in (
            f'lIns="{expected["margin_left"]}"',
            f'rIns="{expected["margin_right"]}"',
            f'tIns="{expected["margin_top"]}"',
            f'bIns="{expected["margin_bottom"]}"',
            f'wrap="{expected["word_wrap_xml"]}"',
            f'anchor="{expected["vertical_anchor_xml"]}"',
            f"<a:{expected['auto_size_xml']}",
        )
    )
    visible_slide_preserved = output_summary.slides[0].texts == source_summary.slides[
        0
    ].texts and [shape.text for shape in output_summary.slides[0].shapes] == [
        shape.text for shape in source_summary.slides[0].shapes
    ]
    notes_text_preserved = (
        output_summary.slides[0].notes == source_summary.slides[0].notes
    )
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_notes_part]
        and package_diff.removed_parts == []
    )
    semantic_pass = (
        margin_pass
        and flow_pass
        and xml_pass
        and visible_slide_preserved
        and notes_text_preserved
    )
    ok = semantic_pass and changed_parts_ok and validation.get("valid") is not False
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "notes_text_frame_flow_pass": margin_pass and flow_pass and xml_pass,
        "notes_text_preserved": notes_text_preserved,
        "visible_slide_preserved": visible_slide_preserved,
        "margin_pass": margin_pass,
        "flow_pass": flow_pass,
        "xml_pass": xml_pass,
        "text_frame": details,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_notes_part": changed_notes_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_notes_background_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _NOTES_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in notes background benchmark does not support fixture {fixture_id}"
        )
    output_prs = WolfPresentation(output_path)
    source_summary = extract_semantics(fixture_path)
    output_summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    changed_notes_part = _first_slide_notes_part(output_path)
    background = output_prs.slides[0].notes_slide.background
    fill_type = background.fill.type
    fill_type_name = getattr(fill_type, "name", str(fill_type))
    rgb = background.fill.fore_color.rgb
    fill_pass = (
        fill_type_name == "SOLID" and str(rgb).upper() == NOTES_BACKGROUND_EXPECTED_RGB
    )
    visible_slide_preserved = output_summary.slides[0].texts == source_summary.slides[
        0
    ].texts and [shape.text for shape in output_summary.slides[0].shapes] == [
        shape.text for shape in source_summary.slides[0].shapes
    ]
    notes_text_preserved = (
        output_summary.slides[0].notes == source_summary.slides[0].notes
    )
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_notes_part]
        and package_diff.removed_parts == []
    )
    semantic_pass = fill_pass and visible_slide_preserved and notes_text_preserved
    ok = semantic_pass and changed_parts_ok and validation.get("valid") is not False
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "notes_background_pass": fill_pass,
        "notes_text_preserved": notes_text_preserved,
        "visible_slide_preserved": visible_slide_preserved,
        "fill_type": fill_type_name,
        "fill_rgb": None if rgb is None else str(rgb).upper(),
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_notes_part": changed_notes_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_create_notes_slide_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id != "text_basic/title_body_bullets":
        raise RuntimeError(
            "drop-in create notes-slide benchmark does not support fixture "
            f"{fixture_id}"
        )
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts
        == [
            "ppt/notesMasters/_rels/notesMaster1.xml.rels",
            "ppt/notesMasters/notesMaster1.xml",
            "ppt/notesSlides/_rels/notesSlide1.xml.rels",
            "ppt/notesSlides/notesSlide1.xml",
            "ppt/theme/theme2.xml",
        ]
        and package_diff.changed_parts
        == [
            "[Content_Types].xml",
            "ppt/_rels/presentation.xml.rels",
            "ppt/slides/_rels/slide1.xml.rels",
        ]
        and package_diff.removed_parts == []
    )
    notes_pass = summary.slides[0].notes == [CREATE_NOTES_SLIDE_EXPECTED]
    visible_slide_preserved = summary.slides[0].texts == source_summary.slides[
        0
    ].texts and [shape.text for shape in summary.slides[0].shapes] == [
        shape.text for shape in source_summary.slides[0].shapes
    ]
    semantic_pass = notes_pass and visible_slide_preserved
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "notes_pass": notes_pass,
        "visible_slide_preserved": visible_slide_preserved,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_notes_paragraph_run_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    details = _dropin_notes_edit_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
        NOTES_PARAGRAPH_RUN_EXPECTED,
        "notes paragraph/run",
    )
    changed_notes_part = details["changed_notes_part"]
    layout_pass = _notes_paragraph_layout_pass(output_path, changed_notes_part)
    run_font_pass = _notes_run_font_pass(output_path, changed_notes_part)
    paragraph_font_pass = _notes_paragraph_font_pass(output_path, changed_notes_part)
    details["notes_paragraph_layout_pass"] = layout_pass
    details["notes_run_font_pass"] = run_font_pass
    details["notes_paragraph_font_pass"] = paragraph_font_pass
    details["semantic_pass"] = bool(
        details["semantic_pass"]
        and layout_pass
        and run_font_pass
        and paragraph_font_pass
    )
    details["semantic_score"] = 1.0 if details["semantic_pass"] else 0.0
    details["ok"] = bool(
        details["semantic_pass"]
        and details["package_added_count"] == 0
        and details["changed_parts"] == [details["changed_notes_part"]]
        and details["package_removed_count"] == 0
        and details["openxml_valid"] is not False
    )
    return details


def _dropin_notes_hyperlink_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _NOTES_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in notes hyperlink benchmark does not support fixture {fixture_id}"
        )
    output_prs = WolfPresentation(output_path)
    notes = output_prs.slides[0].notes_slide
    placeholder_address = notes.notes_placeholder.click_action.hyperlink.address
    run_address = notes.notes_text_frame.paragraphs[0].runs[0].hyperlink.address
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_notes_part = _first_slide_notes_part(output_path)
    changed_notes_rels_part = _part_rels_name(changed_notes_part)
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_notes_rels_part, changed_notes_part]
        and package_diff.removed_parts == []
    )
    with ZipFile(output_path) as package:
        notes_xml = package.read(changed_notes_part).decode("utf-8")
        notes_rels_xml = package.read(changed_notes_rels_part).decode("utf-8")
        slide_rels_xml = package.read("ppt/slides/_rels/slide1.xml.rels").decode(
            "utf-8"
        )
    placeholder_pass = (
        placeholder_address == NOTES_PLACEHOLDER_HYPERLINK_EXPECTED_ADDRESS
        and NOTES_PLACEHOLDER_HYPERLINK_EXPECTED_ADDRESS in notes_rels_xml
    )
    run_pass = (
        run_address == NOTES_RUN_HYPERLINK_EXPECTED_ADDRESS
        and NOTES_RUN_HYPERLINK_EXPECTED_ADDRESS in notes_rels_xml
    )
    notes_xml_pass = notes_xml.count("<a:hlinkClick") >= 2
    slide_rels_preserved = (
        NOTES_PLACEHOLDER_HYPERLINK_EXPECTED_ADDRESS not in slide_rels_xml
        and NOTES_RUN_HYPERLINK_EXPECTED_ADDRESS not in slide_rels_xml
    )
    visible_slide_preserved = summary.slides[0].texts == source_summary.slides[
        0
    ].texts and [shape.text for shape in summary.slides[0].shapes] == [
        shape.text for shape in source_summary.slides[0].shapes
    ]
    semantic_pass = (
        placeholder_pass
        and run_pass
        and notes_xml_pass
        and slide_rels_preserved
        and visible_slide_preserved
    )
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "placeholder_hyperlink_pass": placeholder_pass,
        "run_hyperlink_pass": run_pass,
        "notes_xml_pass": notes_xml_pass,
        "slide_rels_preserved": slide_rels_preserved,
        "visible_slide_preserved": visible_slide_preserved,
        "placeholder_address": placeholder_address,
        "run_address": run_address,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_notes_part": changed_notes_part,
        "changed_notes_rels_part": changed_notes_rels_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _first_slide_notes_part(path: Path) -> str:
    return WolfPresentation(path).slides[0].notes_slide.part.partname.lstrip("/")


def _part_rels_name(part_name: str) -> str:
    prefix, name = part_name.rsplit("/", 1)
    return f"{prefix}/_rels/{name}.rels"


def _notes_paragraph_layout_pass(path: Path, notes_part: str) -> bool:
    with ZipFile(path) as package:
        notes_xml = package.read(notes_part).decode("utf-8")
    return all(
        marker in notes_xml
        for marker in [
            'algn="ctr"',
            'lvl="1"',
            '<a:spcBef><a:spcPts val="1200"',
            '<a:spcAft><a:spcPts val="600"',
            '<a:lnSpc><a:spcPct val="125000"',
        ]
    )


def _notes_run_font_pass(path: Path, notes_part: str) -> bool:
    with ZipFile(path) as package:
        notes_xml = package.read(notes_part).decode("utf-8")
    return all(
        marker in notes_xml
        for marker in [
            'b="1"',
            'i="1"',
            'u="sng"',
            'sz="1800"',
            'lang="de-DE"',
            '<a:latin typeface="Aptos"',
            '<a:srgbClr val="123456"',
        ]
    )


def _notes_paragraph_font_pass(path: Path, notes_part: str) -> bool:
    with ZipFile(path) as package:
        notes_xml = package.read(notes_part)
    root = ET.fromstring(notes_xml)
    for default_run_properties in root.findall(
        ".//{http://schemas.openxmlformats.org/drawingml/2006/main}pPr/"
        "{http://schemas.openxmlformats.org/drawingml/2006/main}defRPr"
    ):
        latin = default_run_properties.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}latin"
        )
        srgb_color = default_run_properties.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill/"
            "{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr"
        )
        if (
            default_run_properties.attrib.get("b") == "1"
            and default_run_properties.attrib.get("i") == "1"
            and default_run_properties.attrib.get("u") == "sng"
            and default_run_properties.attrib.get("sz") == "1800"
            and default_run_properties.attrib.get("lang") == "de-DE"
            and latin is not None
            and latin.attrib.get("typeface") == "Aptos"
            and srgb_color is not None
            and srgb_color.attrib.get("val") == "123456"
        ):
            return True
    return False


def _notes_placeholder_metadata(path: Path) -> list[dict[str, Any]]:
    notes = WolfPresentation(path).slides[0].notes_slide
    return [
        {
            "name": shape.name,
            "text": shape.text,
            "placeholder_idx": shape.placeholder_format.idx,
            "placeholder_type": str(shape.placeholder_format.type),
        }
        for shape in notes.shapes
        if shape.is_placeholder
    ]


def _dropin_notes_placeholder_clone_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _NOTES_EDIT_FIXTURES:
        raise RuntimeError(
            "drop-in notes placeholder clone benchmark does not support fixture "
            f"{fixture_id}"
        )
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_notes_part = _first_slide_notes_part(output_path)
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_notes_part]
        and package_diff.removed_parts == []
    )
    placeholder_metadata = _notes_placeholder_metadata(output_path)
    placeholder_clone_pass = _notes_placeholder_clone_pass(placeholder_metadata)
    output_notes_text = (
        WolfPresentation(output_path).slides[0].notes_slide.notes_text_frame.text
    )
    source_notes_text = (
        WolfPresentation(fixture_path).slides[0].notes_slide.notes_text_frame.text
    )
    notes_text_preserved = output_notes_text == source_notes_text
    visible_slide_preserved = summary.slides[0].texts == source_summary.slides[
        0
    ].texts and [shape.text for shape in summary.slides[0].shapes] == [
        shape.text for shape in source_summary.slides[0].shapes
    ]
    semantic_pass = (
        placeholder_clone_pass and notes_text_preserved and visible_slide_preserved
    )
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "placeholder_clone_pass": placeholder_clone_pass,
        "placeholder_metadata": placeholder_metadata,
        "notes_text_preserved": notes_text_preserved,
        "visible_slide_preserved": visible_slide_preserved,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_notes_part": changed_notes_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _notes_placeholder_clone_pass(metadata: list[dict[str, Any]]) -> bool:
    return [
        {
            "placeholder_idx": item["placeholder_idx"],
            "placeholder_type": item["placeholder_type"],
        }
        for item in metadata
    ] == [
        {
            "placeholder_idx": item["placeholder_idx"],
            "placeholder_type": item["placeholder_type"],
        }
        for item in NOTES_PLACEHOLDER_CLONE_EXPECTED
    ]
