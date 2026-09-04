"""Shape formatting drop-in benchmark result detail readers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    SHAPE_HYPERLINK_EXPECTED_ADDRESS,
    SHAPE_NAME_EXPECTED,
    SHAPE_ROTATION_EXPECTED,
    SHAPE_ROTATION_EXPECTED_XML,
    SHAPE_SHADOW_EXPECTED_INHERIT,
    SHAPE_TARGET_SLIDE_EXPECTED_ADDRESS,
)
from .benchmark_validation import _validate_output
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation

TOP_LEVEL_CREATION_FIXTURES = (
    "text_basic/title_body_bullets",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)
TARGET_SLIDE_FIXTURES = (
    "slides/two_slide_text",
    "workloads/mixed_real_world_deck",
    "workloads/mixed_deal_review_deck",
)


def _output_shape_or_group_child(
    fixture_id: str,
    output_path: Path,
    operation: str,
) -> Any:
    prs = WolfPresentation(output_path)
    if fixture_id == "text_basic/title_body_bullets":
        return prs.slides[0].shapes[0]
    if fixture_id == "shapes/grouped_shapes":
        return prs.slides[0].shapes[0].shapes[0]
    raise RuntimeError(
        f"drop-in {operation} benchmark does not support fixture {fixture_id}"
    )


def _dropin_shape_style_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id == "text_basic/title_body_bullets":
        shape = WolfPresentation(output_path).slides[0].shapes[0]
    elif fixture_id == "shapes/grouped_shapes":
        shape = WolfPresentation(output_path).slides[0].shapes[0].shapes[0]
    else:
        raise RuntimeError(
            f"drop-in shape style benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    style_pass = (
        str(shape.fill.fore_color.rgb) == "123456"
        and str(shape.line.color.rgb) == "654321"
        and int(shape.line.width) == 28575
        and getattr(shape.line.dash_style, "xml_value", shape.line.dash_style) == "dash"
    )
    ok = style_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": style_pass,
        "semantic_score": 1.0 if style_pass else 0.0,
        "style_pass": style_pass,
        "fill_rgb": str(shape.fill.fore_color.rgb),
        "line_rgb": str(shape.line.color.rgb),
        "line_width": int(shape.line.width),
        "line_dash_style": getattr(shape.line.dash_style, "xml_value", shape.line.dash_style),
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_theme_color_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    shape = _output_shape_or_group_child(fixture_id, output_path, "shape theme color")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    fill_theme = getattr(
        shape.fill.fore_color.theme_color,
        "xml_value",
        shape.fill.fore_color.theme_color,
    )
    line_theme = getattr(
        shape.line.color.theme_color,
        "xml_value",
        shape.line.color.theme_color,
    )
    fill_brightness = shape.fill.fore_color.brightness
    line_brightness = shape.line.color.brightness
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    theme_xml_pass = (
        '<a:schemeClr val="accent2"><a:lumMod val="60000"/>'
        '<a:lumOff val="40000"/></a:schemeClr>' in slide_xml.replace(" />", "/>")
        and '<a:schemeClr val="accent3"><a:lumMod val="75000"/></a:schemeClr>'
        in slide_xml.replace(" />", "/>")
    )
    theme_pass = (
        fill_theme == "accent2"
        and line_theme == "accent3"
        and math.isclose(fill_brightness, 0.4)
        and math.isclose(line_brightness, -0.25)
        and theme_xml_pass
    )
    ok = theme_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": theme_pass,
        "semantic_score": 1.0 if theme_pass else 0.0,
        "theme_pass": theme_pass,
        "fill_theme_color": fill_theme,
        "line_theme_color": line_theme,
        "fill_brightness": fill_brightness,
        "line_brightness": line_brightness,
        "theme_xml_pass": theme_xml_pass,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_shadow_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id == "text_basic/title_body_bullets":
        shape = WolfPresentation(output_path).slides[0].shapes[0]
    elif fixture_id == "shapes/grouped_shapes":
        shape = WolfPresentation(output_path).slides[0].shapes[0].shapes[0]
    else:
        raise RuntimeError(
            f"drop-in shape shadow benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    shadow_inherit = bool(shape.shadow.inherit)
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
    shadow_xml = "<a:effectLst/>" in slide_xml.replace(" />", "/>")
    shadow_pass = (
        shadow_inherit is SHAPE_SHADOW_EXPECTED_INHERIT
        and shadow_xml is True
    )
    ok = shadow_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": shadow_pass,
        "semantic_score": 1.0 if shadow_pass else 0.0,
        "shadow_pass": shadow_pass,
        "shadow_inherit": shadow_inherit,
        "shadow_xml": shadow_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_hyperlink_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id == "text_basic/title_body_bullets":
        shape = WolfPresentation(output_path).slides[0].shapes[0]
    elif fixture_id == "shapes/grouped_shapes":
        shape = WolfPresentation(output_path).slides[0].shapes[0].shapes[0]
    else:
        raise RuntimeError(
            f"drop-in shape hyperlink benchmark does not support fixture {fixture_id}"
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
    action = shape.click_action.action
    action_name = getattr(action, "name", str(action).split(" ", 1)[0])
    address = shape.click_action.hyperlink.address
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
        rels_xml = package.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
    hyperlink_xml = "<a:hlinkClick" in slide_xml and SHAPE_HYPERLINK_EXPECTED_ADDRESS in rels_xml
    hyperlink_pass = (
        action_name == "HYPERLINK"
        and address == SHAPE_HYPERLINK_EXPECTED_ADDRESS
        and hyperlink_xml
    )
    ok = hyperlink_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": hyperlink_pass,
        "semantic_score": 1.0 if hyperlink_pass else 0.0,
        "hyperlink_pass": hyperlink_pass,
        "action": action_name,
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


def _dropin_shape_target_slide_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TARGET_SLIDE_FIXTURES:
        raise RuntimeError(
            f"drop-in shape target-slide benchmark does not support fixture {fixture_id}"
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
    prs = WolfPresentation(output_path)
    shape = prs.slides[0].shapes[0]
    action = shape.click_action.action
    action_name = getattr(action, "name", str(action).split(" ", 1)[0])
    target_slide = shape.click_action.target_slide
    address = shape.click_action.hyperlink.address
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
        rels_xml = package.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
    target_xml = (
        "ppaction://hlinksldjump" in slide_xml
        and f'Target="{SHAPE_TARGET_SLIDE_EXPECTED_ADDRESS}"' in rels_xml
        and "TargetMode" not in rels_xml
    )
    target_pass = (
        action_name == "NAMED_SLIDE"
        and target_slide == prs.slides[1]
        and address == SHAPE_TARGET_SLIDE_EXPECTED_ADDRESS
        and target_xml
    )
    ok = target_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": target_pass,
        "semantic_score": 1.0 if target_pass else 0.0,
        "target_slide_pass": target_pass,
        "action": action_name,
        "address": address,
        "target_xml": target_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_target_new_slide_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_CREATION_FIXTURES:
        raise RuntimeError(
            "drop-in shape target-new-slide benchmark does not support fixture "
            f"{fixture_id}"
        )
    source_slide_count = len(WolfPresentation(fixture_path).slides)
    target_slide_number = source_slide_count + 1
    target_slide_part = f"ppt/slides/slide{target_slide_number}.xml"
    target_slide_rels_part = f"ppt/slides/_rels/slide{target_slide_number}.xml.rels"
    target_address = f"slide{target_slide_number}.xml"
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == [target_slide_rels_part, target_slide_part]
        and package_diff.changed_parts
        == [
            "[Content_Types].xml",
            "ppt/_rels/presentation.xml.rels",
            "ppt/presentation.xml",
            "ppt/slides/_rels/slide1.xml.rels",
            "ppt/slides/slide1.xml",
        ]
        and package_diff.removed_parts == []
    )
    prs = WolfPresentation(output_path)
    shape = prs.slides[0].shapes[0]
    action = shape.click_action.action
    action_name = getattr(action, "name", str(action).split(" ", 1)[0])
    target_slide = shape.click_action.target_slide
    address = shape.click_action.hyperlink.address
    with ZipFile(output_path) as package:
        slide_xml = package.read("ppt/slides/slide1.xml").decode("utf-8")
        rels_xml = package.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
    target_xml = (
        "ppaction://hlinksldjump" in slide_xml
        and f'Target="{target_address}"' in rels_xml
        and "TargetMode" not in rels_xml
    )
    target_pass = (
        len(prs.slides) == target_slide_number
        and action_name == "NAMED_SLIDE"
        and target_slide == prs.slides[source_slide_count]
        and address == target_address
        and target_xml
    )
    ok = target_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": target_pass,
        "semantic_score": 1.0 if target_pass else 0.0,
        "target_pass": target_pass,
        "action": action_name,
        "target_slide_index": None if target_slide is None else target_slide._index,
        "address": address,
        "slide_count": len(prs.slides),
        "target_xml": target_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_fill_solid_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    shape = _output_shape_or_group_child(fixture_id, output_path, "shape solid-fill")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    fill_type = shape.fill.type
    fill_type_name = getattr(fill_type, "name", str(fill_type))
    style_pass = fill_type_name == "SOLID"
    ok = style_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": style_pass,
        "semantic_score": 1.0 if style_pass else 0.0,
        "style_pass": style_pass,
        "fill_type": fill_type_name,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_line_fill_background_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    shape = _output_shape_or_group_child(
        fixture_id,
        output_path,
        "shape line background-fill",
    )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    fill_type = shape.line.fill.type
    fill_type_name = getattr(fill_type, "name", str(fill_type))
    style_pass = (
        fill_type_name == "BACKGROUND"
        and int(shape.line.width) == 28575
        and shape.line.color.rgb is None
    )
    ok = style_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": style_pass,
        "semantic_score": 1.0 if style_pass else 0.0,
        "style_pass": style_pass,
        "line_fill_type": fill_type_name,
        "line_width": int(shape.line.width),
        "line_rgb": None if shape.line.color.rgb is None else str(shape.line.color.rgb),
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_patterned_fill_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    shape = _output_shape_or_group_child(fixture_id, output_path, "shape patterned-fill")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    fill_type = shape.fill.type
    fill_type_name = getattr(fill_type, "name", str(fill_type))
    fill_pattern = shape.fill.pattern
    fill_pattern_xml = getattr(fill_pattern, "xml_value", fill_pattern)
    fill_fore_rgb = str(shape.fill.fore_color.rgb)
    fill_back_rgb = str(shape.fill.back_color.rgb)
    line_fill_type = shape.line.fill.type
    line_fill_type_name = getattr(line_fill_type, "name", str(line_fill_type))
    line_pattern = shape.line.fill.pattern
    line_pattern_xml = getattr(line_pattern, "xml_value", line_pattern)
    line_fore_rgb = str(shape.line.fill.fore_color.rgb)
    line_back_rgb = str(shape.line.fill.back_color.rgb)
    style_pass = (
        fill_type_name == "PATTERNED"
        and fill_pattern_xml == "divot"
        and fill_fore_rgb == "123456"
        and fill_back_rgb == "654321"
        and line_fill_type_name == "PATTERNED"
        and line_pattern_xml == "wave"
        and line_fore_rgb == "ABCDEF"
        and line_back_rgb == "FEDCBA"
    )
    ok = style_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": style_pass,
        "semantic_score": 1.0 if style_pass else 0.0,
        "style_pass": style_pass,
        "fill_type": fill_type_name,
        "fill_pattern": fill_pattern_xml,
        "fill_fore_rgb": fill_fore_rgb,
        "fill_back_rgb": fill_back_rgb,
        "line_fill_type": line_fill_type_name,
        "line_pattern": line_pattern_xml,
        "line_fore_rgb": line_fore_rgb,
        "line_back_rgb": line_back_rgb,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_gradient_fill_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    shape = _output_shape_or_group_child(fixture_id, output_path, "shape gradient-fill")
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == ["ppt/slides/slide1.xml"]
        and package_diff.removed_parts == []
    )
    fill = shape.fill
    fill_type = fill.type
    fill_type_name = getattr(fill_type, "name", str(fill_type))
    first_stop = fill.gradient_stops[0]
    style_pass = (
        fill_type_name == "GRADIENT"
        and fill.gradient_angle == 45.0
        and len(fill.gradient_stops) == 2
        and first_stop.position == 0.25
        and str(first_stop.color.rgb) == "123456"
    )
    ok = style_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": style_pass,
        "semantic_score": 1.0 if style_pass else 0.0,
        "style_pass": style_pass,
        "fill_type": fill_type_name,
        "gradient_angle": fill.gradient_angle,
        "gradient_stop_count": len(fill.gradient_stops),
        "first_stop_position": first_stop.position,
        "first_stop_rgb": str(first_stop.color.rgb),
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_rotation_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id == "text_basic/title_body_bullets":
        shape = WolfPresentation(output_path).slides[0].shapes[0]
    elif fixture_id == "shapes/grouped_shapes":
        shape = WolfPresentation(output_path).slides[0].shapes[0].shapes[0]
    else:
        raise RuntimeError(
            f"drop-in shape rotation benchmark does not support fixture {fixture_id}"
        )
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
    rotation_pass = (
        math.isclose(shape.rotation, SHAPE_ROTATION_EXPECTED)
        and f'rot="{SHAPE_ROTATION_EXPECTED_XML}"' in slide_xml
    )
    ok = rotation_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": rotation_pass,
        "semantic_score": 1.0 if rotation_pass else 0.0,
        "rotation_pass": rotation_pass,
        "rotation": shape.rotation,
        "rotation_xml": SHAPE_ROTATION_EXPECTED_XML in slide_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_shape_name_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id == "text_basic/title_body_bullets":
        shape = WolfPresentation(output_path).slides[0].shapes[0]
    elif fixture_id == "shapes/grouped_shapes":
        shape = WolfPresentation(output_path).slides[0].shapes[0].shapes[0]
    else:
        raise RuntimeError(
            f"drop-in shape name benchmark does not support fixture {fixture_id}"
        )
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
    name_pass = shape.name == SHAPE_NAME_EXPECTED and f'name="{SHAPE_NAME_EXPECTED}"' in slide_xml
    ok = name_pass and changed_parts_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": name_pass,
        "semantic_score": 1.0 if name_pass else 0.0,
        "name_pass": name_pass,
        "shape_name": shape.name,
        "name_xml": f'name="{SHAPE_NAME_EXPECTED}"' in slide_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
