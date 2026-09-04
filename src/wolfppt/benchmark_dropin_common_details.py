"""Common drop-in benchmark result detail readers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .benchmark_cases import (
    MIXED_WORKLOAD_CHANGED_PARTS,
    MIXED_WORKLOAD_EXPECTED,
    SLIDE_BACKGROUND_EXPECTED_RGB,
    SLIDE_SIZE_EXPECTED_CX,
    SLIDE_SIZE_EXPECTED_CY,
    SLIDE_NAME_EXPECTED,
    TEMPLATE_BACKGROUND_EXPECTED_RGB,
)
from .benchmark_validation import _validate_output
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


def _dropin_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == [] and package_diff.removed_parts == []
    )
    if fixture_id == "text_basic/title_body_bullets":
        semantic_pass = summary.slides[0].shapes[1].paragraphs == [
            "Fast PPTX",
            "Benchmark paragraph",
        ]
    elif fixture_id in _MIXED_WORKLOAD_FIXTURES:
        semantic_pass = summary.slides[0].shapes[1].paragraphs == [
            "Benchmark paragraph"
        ]
    elif fixture_id == "tables/simple_table":
        semantic_pass = summary.slides[0].shapes[0].tables[0].rows[1][1] == "2"
    else:
        raise RuntimeError(
            f"drop-in edit benchmark does not support fixture {fixture_id}"
        )
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_mixed_workload_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _MIXED_WORKLOAD_FIXTURES:
        raise RuntimeError(
            f"drop-in mixed workload benchmark does not support fixture {fixture_id}"
        )
    expected = MIXED_WORKLOAD_EXPECTED
    summary = extract_semantics(output_path)
    chart = WolfPresentation(output_path).slides[2].shapes[1].chart
    chart_metadata = {
        "categories": list(chart.plots[0].categories),
        "series": [
            {"name": series.name, "values": [float(value) for value in series.values]}
            for series in chart.series
        ],
    }
    title_pass = summary.slides[0].shapes[0].text == expected["title"]
    table_pass = (
        summary.slides[1].shapes[1].tables[0].rows[1][3] == expected["table_revenue_q3"]
    )
    chart_pass = chart_metadata == {
        "categories": expected["chart_categories"],
        "series": expected["chart_series"],
    }
    risk_pass = summary.slides[3].shapes[1].text == expected["risk"]
    actions_pass = summary.slides[4].shapes[1].paragraphs == expected["actions"]
    notes_pass = summary.slides[4].notes == [expected["notes"]]
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == MIXED_WORKLOAD_CHANGED_PARTS
        and package_diff.removed_parts == []
    )
    semantic_pass = all(
        [title_pass, table_pass, chart_pass, risk_pass, actions_pass, notes_pass]
    )
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "title_pass": title_pass,
        "table_pass": table_pass,
        "chart_pass": chart_pass,
        "risk_pass": risk_pass,
        "actions_pass": actions_pass,
        "notes_pass": notes_pass,
        "chart_metadata": chart_metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


_MIXED_WORKLOAD_FIXTURES = {
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
}

_REAL_WORLD_SAFE_TEXT_FIXTURES = {
    "text_basic/title_body_bullets",
    *_MIXED_WORKLOAD_FIXTURES,
}


def _dropin_slide_layout_remove_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id != "slides/two_slide_text":
        raise RuntimeError(
            "drop-in slide-layout remove benchmark does not support fixture "
            f"{fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts
        == [
            "[Content_Types].xml",
            "ppt/slideMasters/_rels/slideMaster1.xml.rels",
            "ppt/slideMasters/slideMaster1.xml",
        ]
        and package_diff.removed_parts
        == [
            "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
            "ppt/slideLayouts/slideLayout1.xml",
        ]
    )
    source_prs = WolfPresentation(fixture_path)
    output_prs = WolfPresentation(output_path)
    layout_removed = output_prs.slide_layouts.get_by_name("Title Slide") is None
    slide_layouts_preserved = [
        slide.slide_layout.name for slide in output_prs.slides
    ] == [slide.slide_layout.name for slide in source_prs.slides]
    layout_count_pass = (
        len(output_prs.slide_layouts) == len(source_prs.slide_layouts) - 1
    )
    semantic_pass = layout_removed and slide_layouts_preserved and layout_count_pass
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "layout_removed": layout_removed,
        "layout_count": len(output_prs.slide_layouts),
        "source_layout_count": len(source_prs.slide_layouts),
        "slide_layouts_preserved": slide_layouts_preserved,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "removed_parts": package_diff.removed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_slide_name_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _REAL_WORLD_SAFE_TEXT_FIXTURES:
        raise RuntimeError(
            f"drop-in slide name benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    slide = WolfPresentation(output_path).slides[0]
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    name_xml = f'<p:cSld name="{SLIDE_NAME_EXPECTED}">' in slide_xml
    name_pass = slide.name == SLIDE_NAME_EXPECTED and name_xml
    ok = name_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": name_pass,
        "semantic_score": 1.0 if name_pass else 0.0,
        "name_pass": name_pass,
        "slide_name": slide.name,
        "name_xml": name_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_slide_background_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _REAL_WORLD_SAFE_TEXT_FIXTURES:
        raise RuntimeError(
            f"drop-in slide background benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    background = WolfPresentation(output_path).slides[0].background
    fill_type = background.fill.type
    fill_type_name = getattr(fill_type, "name", str(fill_type))
    rgb = background.fill.fore_color.rgb
    fill_pass = (
        fill_type_name == "SOLID" and str(rgb).upper() == SLIDE_BACKGROUND_EXPECTED_RGB
    )
    ok = fill_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": fill_pass,
        "semantic_score": 1.0 if fill_pass else 0.0,
        "fill_type": fill_type_name,
        "fill_rgb": None if rgb is None else str(rgb).upper(),
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_template_background_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _REAL_WORLD_SAFE_TEXT_FIXTURES:
        raise RuntimeError(
            "drop-in template background benchmark does not support fixture "
            f"{fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    expected_changed_parts = [
        "ppt/slideLayouts/slideLayout1.xml",
        "ppt/slideMasters/slideMaster1.xml",
    ]
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == expected_changed_parts
        and package_diff.removed_parts == []
    )
    prs = WolfPresentation(output_path)
    backgrounds = [
        prs.slide_layouts[0].background,
        prs.slide_master.background,
    ]
    observed = []
    for background in backgrounds:
        fill_type = background.fill.type
        rgb = background.fill.fore_color.rgb
        observed.append(
            {
                "fill_type": getattr(fill_type, "name", str(fill_type)),
                "fill_rgb": None if rgb is None else str(rgb).upper(),
            }
        )
    fill_pass = all(
        item["fill_type"] == "SOLID"
        and item["fill_rgb"] == TEMPLATE_BACKGROUND_EXPECTED_RGB
        for item in observed
    )
    ok = fill_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": fill_pass,
        "semantic_score": 1.0 if fill_pass else 0.0,
        "template_backgrounds": observed,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_slide_size_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _REAL_WORLD_SAFE_TEXT_FIXTURES:
        raise RuntimeError(
            f"drop-in slide size benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/presentation.xml"]
        and package_diff.removed_parts == []
    )
    prs = WolfPresentation(output_path)
    with ZipFile(output_path) as package:
        presentation_xml = package.read("ppt/presentation.xml")
    root = ET.fromstring(presentation_xml)
    slide_size = root.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz"
    )
    xml_pass = (
        slide_size is not None
        and slide_size.get("cx") == str(SLIDE_SIZE_EXPECTED_CX)
        and slide_size.get("cy") == str(SLIDE_SIZE_EXPECTED_CY)
    )
    size_pass = (
        prs.slide_width == SLIDE_SIZE_EXPECTED_CX
        and prs.slide_height == SLIDE_SIZE_EXPECTED_CY
        and xml_pass
    )
    ok = size_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": size_pass,
        "semantic_score": 1.0 if size_pass else 0.0,
        "size_pass": size_pass,
        "slide_width": prs.slide_width,
        "slide_height": prs.slide_height,
        "size_xml": xml_pass,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_core_properties_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in _REAL_WORLD_SAFE_TEXT_FIXTURES:
        raise RuntimeError(
            f"drop-in core properties benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["docProps/core.xml"]
        and package_diff.removed_parts == []
    )
    core = WolfPresentation(output_path).core_properties
    metadata = {
        "title": core.title,
        "subject": core.subject,
        "author": core.author,
        "keywords": core.keywords,
        "comments": core.comments,
        "last_modified_by": core.last_modified_by,
        "category": core.category,
        "content_status": core.content_status,
        "identifier": core.identifier,
        "language": core.language,
        "version": core.version,
        "revision": core.revision,
        "created": core.created.isoformat() if core.created is not None else None,
        "modified": core.modified.isoformat() if core.modified is not None else None,
        "last_printed": (
            core.last_printed.isoformat() if core.last_printed is not None else None
        ),
    }
    expected = {
        "title": "Quarterly Review",
        "subject": "Board",
        "author": "Wolf",
        "keywords": "qoe,deck",
        "comments": "Updated by WolfPPT",
        "last_modified_by": "Wolf",
        "category": "Finance",
        "content_status": "Draft",
        "identifier": "deck-001",
        "language": "en-US",
        "version": "v1",
        "revision": 7,
        "created": datetime(2020, 1, 2, 3, 4, 5).isoformat(),
        "modified": datetime(2020, 2, 3, 4, 5, 6).isoformat(),
        "last_printed": datetime(2020, 3, 4, 5, 6, 7).isoformat(),
    }
    with ZipFile(output_path) as package:
        core_xml = package.read("docProps/core.xml").decode("utf-8")
    xml_pass = (
        "<dc:title>Quarterly Review</dc:title>" in core_xml
        and "<cp:revision>7</cp:revision>" in core_xml
        and "2020-01-02T03:04:05Z" in core_xml
    )
    metadata_pass = metadata == expected and xml_pass
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "core_xml": xml_pass,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_multi_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == [] and package_diff.removed_parts == []
    )
    if fixture_id == "text_basic/title_body_bullets":
        semantic_pass = summary.slides[0].shapes[
            0
        ].text == "WolfPPT Native" and summary.slides[0].shapes[1].paragraphs == [
            "Fast PPTX",
            "Second",
        ]
    elif fixture_id == "tables/simple_table":
        semantic_pass = summary.slides[0].shapes[0].tables[0].rows[1] == ["Rows", "2"]
    elif fixture_id == "workloads/multi_edit_table":
        rows = summary.slides[0].shapes[0].tables[0].rows
        semantic_pass = rows[1] == [f"E1-{col_idx}" for col_idx in range(6)] and rows[
            5
        ] == [f"E5-{col_idx}" for col_idx in range(6)]
    else:
        raise RuntimeError(
            f"drop-in multi-edit benchmark does not support fixture {fixture_id}"
        )
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
