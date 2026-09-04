"""Chart drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    CHART_AXIS_PROPERTY_EXPECTED,
    CHART_AXIS_TITLE_EXPECTED,
    CHART_DATA_LABEL_EXPECTED,
    CHART_DATA_LABEL_REMOVAL_EXPECTED,
    CHART_FORMAT_EXPECTED,
    CHART_LEGEND_EXPECTED,
    CHART_POINT_DATA_LABEL_EXPECTED,
    CHART_PLOT_PROPERTY_EXPECTED,
    CHART_READ_EXPECTED_METADATA,
    CHART_STYLE_EXPECTED,
    CHART_TITLE_FORMAT_EXPECTED,
    CHART_TITLE_PARAGRAPH_FONT_EXPECTED,
    CHART_TITLE_PARAGRAPH_FORMAT_EXPECTED,
    CHART_TITLE_TEXT_FRAME_FLOW_EXPECTED,
    CHART_TITLE_TEXT_FRAME_EXPECTED,
    CHART_TITLE_EXPECTED_TEXT,
)
from .benchmark_dropin_actions import (
    _read_wolfppt_chart_format_metadata,
    _read_wolfppt_chart_axis_property_metadata,
    _read_wolfppt_chart_data_label_metadata,
    _read_wolfppt_chart_metadata,
    _read_wolfppt_chart_point_data_label_metadata,
    _read_wolfppt_chart_plot_property_metadata,
    _read_wolfppt_chart_style_metadata,
)
from .benchmark_dropin_chart_readers import CHART_EDIT_FIXTURES
from .benchmark_validation import _validate_output
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

def _dropin_chart_read_details(fixture_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    if fixture_id not in CHART_READ_EXPECTED_METADATA:
        raise RuntimeError(
            f"drop-in chart read benchmark does not support fixture {fixture_id}"
        )
    expected = CHART_READ_EXPECTED_METADATA[fixture_id]
    metadata_pass = metadata == expected
    return {
        "ok": metadata_pass,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
    }


def _dropin_chart_title_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart title benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_title_edit_pass(metadata)
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_legend_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart legend benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_legend_edit_pass(metadata)
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_title_remove_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart title removal benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_title_remove_pass(metadata)
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _chart_title_edit_pass(metadata: dict[str, Any]) -> bool:
    expected = {
        "has_title": True,
        "title_text": CHART_TITLE_EXPECTED_TEXT,
        "chart_title_has_text_frame": True,
        **CHART_TITLE_FORMAT_EXPECTED,
    }
    return all(metadata.get(key) == value for key, value in expected.items())


def _chart_title_remove_pass(metadata: dict[str, Any]) -> bool:
    expected = {
        "has_title": False,
        "title_text": "",
        "chart_title_has_text_frame": False,
    }
    return all(metadata.get(key) == value for key, value in expected.items())


def _chart_legend_edit_pass(metadata: dict[str, Any]) -> bool:
    return all(
        metadata.get(key) == value for key, value in CHART_LEGEND_EXPECTED.items()
    )


def _dropin_chart_axis_title_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart axis title benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_axis_title_edit_pass(metadata)
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_axis_title_remove_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            "drop-in chart axis-title removal benchmark does not support fixture "
            f"{fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_axis_title_remove_pass(metadata)
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _chart_axis_title_edit_pass(metadata: dict[str, Any]) -> bool:
    return all(
        metadata.get(key) == value for key, value in CHART_AXIS_TITLE_EXPECTED.items()
    )


def _chart_axis_title_remove_pass(metadata: dict[str, Any]) -> bool:
    expected = {
        "category_axis_has_title": False,
        "category_axis_title_text": "",
        "value_axis_has_title": False,
        "value_axis_title_text": "",
    }
    return all(metadata.get(key) == value for key, value in expected.items())


def _dropin_chart_title_text_frame_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            "drop-in chart title text-frame benchmark does not support fixture "
            f"{fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_title_text_frame_edit_pass(metadata)
    rich_text_xml_pass = _chart_title_text_frame_xml_pass(output_path, changed_chart_part)
    ok = metadata_pass and rich_text_xml_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass and rich_text_xml_pass,
        "semantic_score": 1.0 if metadata_pass and rich_text_xml_pass else 0.0,
        "metadata_pass": metadata_pass,
        "rich_text_xml_pass": rich_text_xml_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _chart_title_text_frame_edit_pass(metadata: dict[str, Any]) -> bool:
    expected = {
        "has_title": True,
        "title_text": CHART_TITLE_TEXT_FRAME_EXPECTED["text"],
        "chart_title_has_text_frame": True,
        "category_axis_has_title": True,
        "category_axis_title_text": CHART_TITLE_TEXT_FRAME_EXPECTED["text"],
    }
    return all(metadata.get(key) == value for key, value in expected.items())


def _dropin_chart_title_text_frame_flow_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            "drop-in chart title text-frame flow benchmark does not support fixture "
            f"{fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_title_text_frame_flow_edit_pass(metadata)
    flow_xml_pass = _chart_title_text_frame_flow_xml_pass(output_path, changed_chart_part)
    ok = metadata_pass and flow_xml_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass and flow_xml_pass,
        "semantic_score": 1.0 if metadata_pass and flow_xml_pass else 0.0,
        "metadata_pass": metadata_pass,
        "flow_xml_pass": flow_xml_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _chart_title_text_frame_flow_edit_pass(metadata: dict[str, Any]) -> bool:
    expected = {
        "has_title": True,
        "title_text": CHART_TITLE_TEXT_FRAME_FLOW_EXPECTED["text"],
        "chart_title_has_text_frame": True,
        "value_axis_has_title": True,
        "value_axis_title_text": CHART_TITLE_TEXT_FRAME_FLOW_EXPECTED["text"],
    }
    return all(metadata.get(key) == value for key, value in expected.items())


def _dropin_chart_title_paragraph_format_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            "drop-in chart title paragraph format benchmark does not support fixture "
            f"{fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_title_paragraph_format_edit_pass(metadata)
    paragraph_xml_pass = _chart_title_paragraph_format_xml_pass(
        output_path,
        changed_chart_part,
    )
    ok = metadata_pass and paragraph_xml_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass and paragraph_xml_pass,
        "semantic_score": 1.0 if metadata_pass and paragraph_xml_pass else 0.0,
        "metadata_pass": metadata_pass,
        "paragraph_xml_pass": paragraph_xml_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _chart_title_paragraph_format_edit_pass(metadata: dict[str, Any]) -> bool:
    expected = CHART_TITLE_PARAGRAPH_FORMAT_EXPECTED
    expected_metadata = {
        "has_title": True,
        "title_text": expected["text"],
        "chart_title_has_text_frame": True,
        "category_axis_has_title": True,
        "category_axis_title_text": expected["text"],
    }
    return all(metadata.get(key) == value for key, value in expected_metadata.items())


def _dropin_chart_title_paragraph_font_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            "drop-in chart title paragraph font benchmark does not support fixture "
            f"{fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_title_paragraph_font_edit_pass(metadata)
    paragraph_font_xml_pass = _chart_title_paragraph_font_xml_pass(
        output_path,
        changed_chart_part,
    )
    ok = metadata_pass and paragraph_font_xml_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass and paragraph_font_xml_pass,
        "semantic_score": 1.0 if metadata_pass and paragraph_font_xml_pass else 0.0,
        "metadata_pass": metadata_pass,
        "paragraph_font_xml_pass": paragraph_font_xml_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _chart_title_paragraph_font_edit_pass(metadata: dict[str, Any]) -> bool:
    expected = CHART_TITLE_PARAGRAPH_FONT_EXPECTED
    expected_metadata = {
        "has_title": True,
        "title_text": expected["text"],
        "chart_title_has_text_frame": True,
        "value_axis_has_title": True,
        "value_axis_title_text": expected["text"],
        "legend_font_fill_type": None,
    }
    return all(metadata.get(key) == value for key, value in expected_metadata.items())


def _chart_title_text_frame_xml_pass(output_path: Path, chart_part: str) -> bool:
    with ZipFile(output_path) as package:
        chart_xml = package.read(chart_part).decode("utf-8")
    expected = CHART_TITLE_TEXT_FRAME_EXPECTED
    snippets = (
        ">Revenue<",
        f">{expected['run_text']}<",
        ">Q4 outlook<",
        f"b=\"{expected['bold']}\"",
        f"i=\"{expected['italic']}\"",
        f"u=\"{expected['underline']}\"",
        f"sz=\"{expected['size']}\"",
        f"lang=\"{expected['language_id']}\"",
        expected["font_fill_xml"],
        f"srgbClr val=\"{expected['color_rgb']}\"",
        f"srgbClr val=\"{expected['back_color_rgb']}\"",
        f"latin typeface=\"{expected['font_name']}\"",
    )
    return all(snippet in chart_xml for snippet in snippets)


def _chart_title_paragraph_font_xml_pass(output_path: Path, chart_part: str) -> bool:
    with ZipFile(output_path) as package:
        chart_xml = package.read(chart_part).decode("utf-8")
    expected = CHART_TITLE_PARAGRAPH_FONT_EXPECTED
    snippets = (
        f">{expected['text']}<",
        f"b=\"{expected['bold']}\"",
        f"i=\"{expected['italic']}\"",
        f"u=\"{expected['underline']}\"",
        f"sz=\"{expected['size']}\"",
        f"lang=\"{expected['language_id']}\"",
        expected["font_fill_xml"],
        f"gs pos=\"{expected['gradient_first_stop_position']}\"",
        f"lin scaled=\"0\" ang=\"{expected['gradient_angle']}\"",
        f"srgbClr val=\"{expected['color_rgb']}\"",
        f"latin typeface=\"{expected['font_name']}\"",
    )
    return all(snippet in chart_xml for snippet in snippets)


def _chart_title_paragraph_format_xml_pass(output_path: Path, chart_part: str) -> bool:
    with ZipFile(output_path) as package:
        chart_xml = package.read(chart_part).decode("utf-8")
    expected = CHART_TITLE_PARAGRAPH_FORMAT_EXPECTED
    snippets = (
        f">{expected['text']}<",
        f"algn=\"{expected['alignment_xml']}\"",
        f"lvl=\"{expected['level']}\"",
        f"spcPct val=\"{expected['line_spacing_xml']}\"",
        f"spcPts val=\"{expected['space_before_xml']}\"",
        f"spcPts val=\"{expected['space_after_xml']}\"",
    )
    return all(snippet in chart_xml for snippet in snippets)


def _chart_title_text_frame_flow_xml_pass(output_path: Path, chart_part: str) -> bool:
    with ZipFile(output_path) as package:
        chart_xml = package.read(chart_part).decode("utf-8")
    expected = CHART_TITLE_TEXT_FRAME_FLOW_EXPECTED
    snippets = (
        ">Revenue<",
        ">Q4 outlook<",
        f"lIns=\"{expected['margin_left']}\"",
        f"rIns=\"{expected['margin_right']}\"",
        f"tIns=\"{expected['margin_top']}\"",
        f"bIns=\"{expected['margin_bottom']}\"",
        f"wrap=\"{expected['word_wrap_xml']}\"",
        f"anchor=\"{expected['vertical_anchor_xml']}\"",
        expected["auto_size_xml"],
    )
    return all(snippet in chart_xml for snippet in snippets)


def _dropin_chart_axis_property_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart axis property benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    chart_metadata = _read_wolfppt_chart_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    changed_chart_part = chart_metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_axis_property_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    metadata_pass = metadata == CHART_AXIS_PROPERTY_EXPECTED
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_plot_property_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart plot property benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    chart_metadata = _read_wolfppt_chart_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    changed_chart_part = chart_metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_plot_property_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    metadata_pass = metadata == CHART_PLOT_PROPERTY_EXPECTED
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_data_label_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart data-label benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    chart_metadata = _read_wolfppt_chart_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    changed_chart_part = chart_metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_data_label_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    metadata_pass = metadata == CHART_DATA_LABEL_EXPECTED
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_data_label_remove_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart data-label removal benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == []
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_data_label_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    metadata_pass = metadata == CHART_DATA_LABEL_REMOVAL_EXPECTED
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_point_data_label_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart point data-label benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    chart_metadata = _read_wolfppt_chart_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    changed_chart_part = chart_metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_point_data_label_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    metadata_pass = metadata == CHART_POINT_DATA_LABEL_EXPECTED
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_style_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart style benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    chart_metadata = _read_wolfppt_chart_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    changed_chart_part = chart_metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_style_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    metadata_pass = metadata == CHART_STYLE_EXPECTED
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_format_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in CHART_EDIT_FIXTURES:
        raise RuntimeError(
            f"drop-in chart format benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    chart_metadata = _read_wolfppt_chart_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    changed_chart_part = chart_metadata["chart_part"]["partname"].lstrip("/")
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part]
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_format_metadata(
        fixture_id,
        WolfPresentation(output_path),
    )
    metadata_pass = metadata == CHART_FORMAT_EXPECTED
    ok = metadata_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
