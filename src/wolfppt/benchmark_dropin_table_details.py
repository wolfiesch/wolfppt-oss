"""Table drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    TABLE_CELL_PARAGRAPH_LINE_BREAK_EXPECTED,
    TABLE_CELL_PARAGRAPH_FONT_EXPECTED,
    TABLE_CELL_PARAGRAPH_RUNS_EXPECTED,
    TABLE_CELL_RUN_FONT_EXPECTED,
    TABLE_CELL_RUN_HYPERLINK_EXPECTED,
    TABLE_CELL_FILL_EXPECTED,
    TABLE_CELL_TEXT_FRAME_EXPECTED,
    TABLE_CELL_TEXT_FRAME_FLOW_EXPECTED,
    TABLE_DIMENSIONS_EXPECTED,
    TABLE_STYLE_FLAGS_EXPECTED,
)
from .benchmark_validation import _validate_output
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

TABLE_CELL_FIXTURES = (
    "tables/simple_table",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)


def _dropin_table_cell_text_frame_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            f"drop-in table-cell text-frame benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    cell = table.cell(0, 0)
    metadata = {
        "text": cell.text_frame.text,
        "cell_margins": {
            "margin_left": int(cell.margin_left),
            "margin_right": int(cell.margin_right),
            "margin_top": int(cell.margin_top),
            "margin_bottom": int(cell.margin_bottom),
        },
        "text_frame_margins": {
            "margin_left": int(cell.text_frame.margin_left),
            "margin_right": int(cell.text_frame.margin_right),
            "margin_top": int(cell.text_frame.margin_top),
            "margin_bottom": int(cell.text_frame.margin_bottom),
        },
        "cell_vertical_anchor": _anchor_metadata(cell.vertical_anchor),
        "text_frame_vertical_anchor": _anchor_metadata(
            cell.text_frame.vertical_anchor
        ),
    }
    semantic_pass = metadata == TABLE_CELL_TEXT_FRAME_EXPECTED
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_text_frame_pass": semantic_pass,
        "table_cell_text_frame": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _first_table(prs: WolfPresentation) -> tuple[int, Any]:
    for slide_index, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if shape.has_table:
                return slide_index, shape.table
    raise RuntimeError("output deck does not contain a table shape")


def _dropin_table_cell_text_frame_flow_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            f"drop-in table-cell text-frame flow benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    frame = table.cell(0, 0).text_frame
    auto_size = frame.auto_size
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    compact_xml = slide_xml.replace(" />", "/>")
    metadata = {
        "paragraphs": [paragraph.text for paragraph in frame.paragraphs],
        "text": frame.text,
        "word_wrap": frame.word_wrap,
        "word_wrap_xml": 'wrap="square"' in slide_xml,
        "auto_size": getattr(auto_size, "name", auto_size),
        "auto_size_xml": "<a:normAutofit/>" in slide_xml.replace(" />", "/>"),
    }
    semantic_pass = metadata == TABLE_CELL_TEXT_FRAME_FLOW_EXPECTED
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_text_frame_flow_pass": semantic_pass,
        "table_cell_text_frame_flow": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_table_cell_paragraph_runs_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            "drop-in table-cell paragraph-runs benchmark does not support "
            f"fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    paragraph = (
        table.cell(0, 0).text_frame.paragraphs[0]
    )
    metadata = {
        "text": paragraph.text,
        "runs": [run.text for run in paragraph.runs],
        "run_count": len(paragraph.runs),
    }
    semantic_pass = metadata == TABLE_CELL_PARAGRAPH_RUNS_EXPECTED
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_paragraph_runs_pass": semantic_pass,
        "table_cell_paragraph_runs": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_table_cell_paragraph_line_break_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            "drop-in table-cell paragraph-line-break benchmark does not support "
            f"fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    paragraph = (
        table.cell(0, 0).text_frame.paragraphs[0]
    )
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    compact_xml = slide_xml.replace(" />", "/>")
    metadata = {
        "text": paragraph.text,
        "runs": [run.text for run in paragraph.runs],
        "line_break_count": compact_xml.count("<a:br/>"),
    }
    semantic_pass = metadata == TABLE_CELL_PARAGRAPH_LINE_BREAK_EXPECTED
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_paragraph_line_break_pass": semantic_pass,
        "table_cell_paragraph_line_break": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_table_cell_run_font_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            "drop-in table-cell run-font benchmark does not support "
            f"fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    paragraph = (
        table.cell(0, 0).text_frame.paragraphs[0]
    )
    theme_run_font = paragraph.runs[0].font
    theme_run_fill_type = theme_run_font.fill.type
    theme_run_color = theme_run_font.color.theme_color
    font = paragraph.runs[1].font
    fill_type = font.fill.type
    color_rgb = font.color.rgb
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    compact_xml = slide_xml.replace(" />", "/>")
    metadata = {
        "text": paragraph.text,
        "runs": [run.text for run in paragraph.runs],
        "theme_run_fill_type": getattr(theme_run_fill_type, "name", theme_run_fill_type),
        "theme_run_color": getattr(theme_run_color, "name", theme_run_color),
        "bold": font.bold,
        "italic": font.italic,
        "underline": font.underline,
        "size": None if font.size is None else int(font.size),
        "language_id": getattr(font.language_id, "name", font.language_id),
        "font_name": font.name,
        "fill_type": getattr(fill_type, "name", fill_type),
        "color_rgb": None if color_rgb is None else str(color_rgb),
        "xml": {
            "bold": 'b="1"' in compact_xml,
            "italic": 'i="1"' in compact_xml,
            "underline": 'u="sng"' in compact_xml,
            "size": 'sz="1400"' in compact_xml,
            "language_id": 'lang="fr-FR"' in compact_xml,
            "font_name": '<a:latin typeface="Aptos"/>' in compact_xml,
            "theme_run_color": '<a:schemeClr val="accent2"/>' in compact_xml,
            "color_rgb": '<a:srgbClr val="123456"/>' in compact_xml,
        },
    }
    semantic_pass = metadata == TABLE_CELL_RUN_FONT_EXPECTED
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_run_font_pass": semantic_pass,
        "table_cell_run_font": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_table_cell_run_hyperlink_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            "drop-in table-cell run-hyperlink benchmark does not support "
            f"fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_rels_part = f"ppt/slides/_rels/slide{slide_index + 1}.xml.rels"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts
        == [changed_rels_part, changed_slide_part]
        and package_diff.removed_parts == []
    )
    paragraph = table.cell(0, 0).text_frame.paragraphs[0]
    run = paragraph.runs[1]
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
        rels_xml = package.read(changed_rels_part).decode("utf-8")
    metadata = {
        "text": paragraph.text,
        "runs": [run.text for run in paragraph.runs],
        "run_hyperlink_address": run.hyperlink.address,
        "hyperlink_xml": (
            "<a:hlinkClick" in slide_xml
            and TABLE_CELL_RUN_HYPERLINK_EXPECTED["run_hyperlink_address"] in rels_xml
        ),
    }
    semantic_pass = metadata == TABLE_CELL_RUN_HYPERLINK_EXPECTED
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_run_hyperlink_pass": semantic_pass,
        "table_cell_run_hyperlink": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "changed_rels_part": changed_rels_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_table_cell_paragraph_font_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            "drop-in table-cell paragraph-font benchmark does not support "
            f"fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    paragraph = (
        table.cell(0, 0).text_frame.paragraphs[0]
    )
    font = paragraph.font
    fill_type = font.fill.type
    color_rgb = font.color.rgb
    theme_color = font.color.theme_color
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
    compact_xml = slide_xml.replace(" />", "/>")
    metadata = {
        "text": paragraph.text,
        "bold": font.bold,
        "italic": font.italic,
        "underline": font.underline,
        "size": None if font.size is None else int(font.size),
        "language_id": getattr(font.language_id, "name", font.language_id),
        "font_name": font.name,
        "fill_type": getattr(fill_type, "name", fill_type),
        "theme_color": getattr(theme_color, "name", theme_color),
        "color_rgb": None if color_rgb is None else str(color_rgb),
        "xml": {
            "bold": 'b="1"' in compact_xml,
            "italic": 'i="1"' in compact_xml,
            "underline": 'u="sng"' in compact_xml,
            "size": 'sz="1400"' in compact_xml,
            "language_id": 'lang="fr-FR"' in compact_xml,
            "font_name": '<a:latin typeface="Aptos"/>' in compact_xml,
            "theme_color": '<a:schemeClr val="accent3"/>' in compact_xml,
        },
    }
    semantic_pass = metadata == TABLE_CELL_PARAGRAPH_FONT_EXPECTED
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_paragraph_font_pass": semantic_pass,
        "table_cell_paragraph_font": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_table_cell_fill_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            f"drop-in table-cell fill benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    solid_cell = table.cell(0, 0)
    theme_cell = table.cell(1, 0)
    gradient_cell = table.cell(0, 1)
    background_cell = table.cell(1, 1)
    solid_fill_type = solid_cell.fill.type
    theme_fill_type = theme_cell.fill.type
    gradient_fill_type = gradient_cell.fill.type
    background_fill_type = background_cell.fill.type
    gradient_stops = gradient_cell.fill.gradient_stops
    metadata = {
        "solid_cell": {
            "fill_type": getattr(solid_fill_type, "name", str(solid_fill_type)),
            "fill_rgb": (
                None
                if solid_cell.fill.fore_color.rgb is None
                else str(solid_cell.fill.fore_color.rgb)
            ),
        },
        "theme_cell": {
            "fill_type": getattr(theme_fill_type, "name", str(theme_fill_type)),
            "pattern": getattr(theme_cell.fill.pattern, "name", theme_cell.fill.pattern),
            "fore_type": getattr(
                theme_cell.fill.fore_color.type,
                "name",
                theme_cell.fill.fore_color.type,
            ),
            "fill_theme_color": getattr(
                theme_cell.fill.fore_color.theme_color,
                "name",
                theme_cell.fill.fore_color.theme_color,
            ),
            "back_type": getattr(
                theme_cell.fill.back_color.type,
                "name",
                theme_cell.fill.back_color.type,
            ),
            "back_theme_color": getattr(
                theme_cell.fill.back_color.theme_color,
                "name",
                theme_cell.fill.back_color.theme_color,
            ),
        },
        "gradient_cell": {
            "fill_type": getattr(
                gradient_fill_type,
                "name",
                str(gradient_fill_type),
            ),
            "gradient_angle": gradient_cell.fill.gradient_angle,
            "gradient_stop_count": len(gradient_stops),
            "first_stop_position": gradient_stops[0].position,
            "first_stop_rgb": str(gradient_stops[0].color.rgb),
        },
        "background_cell": {
            "fill_type": getattr(
                background_fill_type,
                "name",
                str(background_fill_type),
            ),
            "fill_rgb": (
                None
                if background_cell.fill.fore_color.rgb is None
                else str(background_cell.fill.fore_color.rgb)
            ),
        },
    }
    semantic_pass = metadata == TABLE_CELL_FILL_EXPECTED
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_fill_pass": semantic_pass,
        "table_cell_fill": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_table_cell_merge_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            f"drop-in table-cell merge benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    metadata = _table_cell_merge_metadata(table)
    semantic_pass = (
        metadata[0]["is_merge_origin"] is True
        and metadata[0]["is_spanned"] is False
        and metadata[0]["span_width"] == 2
        and metadata[0]["span_height"] == 2
        and metadata[1]["is_spanned"] is True
        and metadata[2]["is_spanned"] is True
        and metadata[3]["is_spanned"] is True
    )
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_cell_merge_pass": semantic_pass,
        "table_cell_merge": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _table_cell_merge_metadata(table: Any) -> list[dict[str, Any]]:
    return [
        {
            "cell": [row_idx, col_idx],
            "text": table.cell(row_idx, col_idx).text,
            "is_merge_origin": table.cell(row_idx, col_idx).is_merge_origin,
            "is_spanned": table.cell(row_idx, col_idx).is_spanned,
            "span_width": table.cell(row_idx, col_idx).span_width,
            "span_height": table.cell(row_idx, col_idx).span_height,
        }
        for row_idx in range(2)
        for col_idx in range(2)
    ]


def _dropin_table_dimensions_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            f"drop-in table dimensions benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    metadata = {
        "row_heights": [int(row.height) for row in table.rows],
        "column_widths": [int(column.width) for column in table.columns],
        "row_count": len(table.rows),
        "column_count": len(table.columns),
    }
    semantic_pass = (
        metadata["row_heights"][0] == TABLE_DIMENSIONS_EXPECTED["row_heights"][0]
        and metadata["column_widths"][0]
        == TABLE_DIMENSIONS_EXPECTED["column_widths"][0]
    )
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_dimensions_pass": semantic_pass,
        "table_dimensions": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _anchor_metadata(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        raw_value = int(value)
    except (TypeError, ValueError):
        raw_value = None
    return {
        "value": raw_value,
        "xml_value": getattr(value, "xml_value", None),
    }


def _dropin_table_style_flags_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TABLE_CELL_FIXTURES:
        raise RuntimeError(
            f"drop-in table-style flags benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    slide_index, table = _first_table(WolfPresentation(output_path))
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_slide_part]
        and package_diff.removed_parts == []
    )
    metadata = {
        "flags": {
            name: getattr(table, name)
            for name in TABLE_STYLE_FLAGS_EXPECTED["flags"]
        },
        "cells": [cell.text for cell in table.iter_cells()],
    }
    semantic_pass = metadata["flags"] == TABLE_STYLE_FLAGS_EXPECTED["flags"]
    ok = semantic_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "table_style_flags_pass": semantic_pass,
        "table_style_flags": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
