"""Media-oriented drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM,
    ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM,
)
from .benchmark_dropin_media_detail_helpers import (
    GROUP_PICTURE_TARGETS,
    PICTURE_IMAGE_INSPECTION_FIXTURES,
    PICTURE_REPLACE_FIXTURES,
    TOP_LEVEL_PICTURE_FIXTURES,
    _dropin_expected_picture_bytes,
    _dropin_expected_replacement_picture_bytes,
    _expected_picture_image_metadata,
    _first_slide_picture_parts,
    _last_slide_picture_parts,
)
from .benchmark_dropin_media_embedded_details import (
    _dropin_add_deeper_nested_group_ole_object_details as _dropin_add_deeper_nested_group_ole_object_details,
    _dropin_add_group_ole_object_details as _dropin_add_group_ole_object_details,
    _dropin_add_movie_details as _dropin_add_movie_details,
    _dropin_add_movie_file_like_details as _dropin_add_movie_file_like_details,
    _dropin_add_nested_group_ole_object_details as _dropin_add_nested_group_ole_object_details,
    _dropin_add_ole_object_details as _dropin_add_ole_object_details,
    _dropin_add_ole_object_file_like_details as _dropin_add_ole_object_file_like_details,
)
from .benchmark_validation import _validate_output
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


def _top_level_picture_package_delta_ok(
    fixture_id: str,
    added_parts: list[str],
    changed_parts: list[str],
    removed_parts: list[str],
    *,
    slide_index: int = 0,
) -> bool:
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_rels_part = f"ppt/slides/_rels/slide{slide_index + 1}.xml.rels"
    if fixture_id == "text_basic/title_body_bullets" and slide_index == 0:
        return (
            added_parts == ["ppt/media/image1.png"]
            and changed_parts
            == [
                "[Content_Types].xml",
                "ppt/slides/_rels/slide1.xml.rels",
                "ppt/slides/slide1.xml",
            ]
            and removed_parts == []
        )
    added_media = [
        part
        for part in added_parts
        if part.startswith("ppt/media/image") and part.endswith(".png")
    ]
    required_new_media_changed = {changed_rels_part, changed_slide_part}
    allowed_changed = required_new_media_changed | {"[Content_Types].xml"}
    reused_existing_media = (
        added_parts == []
        and changed_slide_part in changed_parts
        and set(changed_parts) <= allowed_changed
    )
    added_new_media = (
        len(added_media) == 1
        and added_parts == added_media
        and required_new_media_changed <= set(changed_parts)
        and set(changed_parts) <= allowed_changed
        and removed_parts == []
    )
    return (reused_existing_media or added_new_media) and removed_parts == []


def _dropin_add_picture_auto_size_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture auto-size benchmark does not support fixture {fixture_id}"
        )
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = _top_level_picture_package_delta_ok(
        fixture_id,
        package_diff.added_parts,
        package_diff.changed_parts,
        package_diff.removed_parts,
    )
    picture = summary.slides[0].shapes[-1]
    transform = None
    if picture.transform is not None:
        transform = {
            "x": picture.transform.x,
            "y": picture.transform.y,
            "cx": picture.transform.cx,
            "cy": picture.transform.cy,
        }
    semantic_pass = (
        picture.has_picture is True
        and transform == ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM
    )
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "picture_pass": semantic_pass,
        "picture_transform": transform,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }

def _dropin_add_picture_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture benchmark does not support fixture {fixture_id}"
        )
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = _top_level_picture_package_delta_ok(
        fixture_id,
        package_diff.added_parts,
        package_diff.changed_parts,
        package_diff.removed_parts,
    )
    picture = summary.slides[0].shapes[-1]
    transform = None
    if picture.transform is not None:
        transform = {
            "x": picture.transform.x,
            "y": picture.transform.y,
            "cx": picture.transform.cx,
            "cy": picture.transform.cy,
        }
    semantic_pass = (
        picture.has_picture is True
        and transform == ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM
    )
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "picture_pass": semantic_pass,
        "picture_transform": transform,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_picture_image_inspection_details(
    fixture_id: str,
    fixture_path: Path,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if fixture_id not in PICTURE_IMAGE_INSPECTION_FIXTURES:
        raise RuntimeError(
            "drop-in picture image inspection benchmark does not support fixture "
            f"{fixture_id}"
        )
    expected = _expected_picture_image_metadata(fixture_id, fixture_path)
    metadata_pass = metadata == expected
    return {
        "ok": metadata_pass,
        "semantic_pass": metadata_pass,
        "semantic_score": 1.0 if metadata_pass else 0.0,
        "metadata_pass": metadata_pass,
        "metadata": metadata,
    }


def _dropin_replace_picture_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in PICTURE_REPLACE_FIXTURES:
        raise RuntimeError(
            f"drop-in replace-picture benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    picture_parts = _first_slide_picture_parts(fixture_path)
    package_delta_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [picture_parts.media_part]
        and package_diff.removed_parts == []
    )
    with ZipFile(output_path) as package:
        replaced_blob = package.read(picture_parts.media_part)
        slide_xml = package.read(picture_parts.slide_part)
        rels_xml = package.read(picture_parts.rels_part)
    with ZipFile(fixture_path) as package:
        original_slide_xml = package.read(picture_parts.slide_part)
        original_rels_xml = package.read(picture_parts.rels_part)
    blob_pass = replaced_blob == _dropin_expected_replacement_picture_bytes(
        fixture_id,
        fixture_path,
    )
    relationship_pass = rels_xml == original_rels_xml
    slide_xml_pass = slide_xml == original_slide_xml
    semantic_pass = blob_pass and relationship_pass and slide_xml_pass
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "picture_pass": blob_pass,
        "relationship_pass": relationship_pass,
        "slide_xml_pass": slide_xml_pass,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "removed_parts": package_diff.removed_parts,
        "replaced_media_part": picture_parts.media_part,
        "picture_slide_part": picture_parts.slide_part,
        "picture_rels_part": picture_parts.rels_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_group_picture_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_PICTURE_TARGETS:
        raise RuntimeError(
            f"drop-in add-group-picture benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_PICTURE_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_rels_part = f"ppt/slides/_rels/slide{slide_index + 1}.xml.rels"
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = _top_level_picture_package_delta_ok(
        fixture_id,
        package_diff.added_parts,
        package_diff.changed_parts,
        package_diff.removed_parts,
        slide_index=slide_index,
    )
    source_group = source_summary.slides[slide_index].shapes[group_index]
    group = summary.slides[slide_index].shapes[group_index]
    expected_child_names = [child.name for child in source_group.children]
    parent_child_names = [
        child.name for child in group.children[: len(expected_child_names)]
    ]
    parent_preserved = parent_child_names == expected_child_names
    picture = group.children[-1] if group.children else None
    transform = None
    if picture is not None and picture.transform is not None:
        transform = {
            "x": picture.transform.x,
            "y": picture.transform.y,
            "cx": picture.transform.cx,
            "cy": picture.transform.cy,
        }
    picture_parts = _last_slide_picture_parts(output_path, slide_index=slide_index)
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
        media_blob = package.read(picture_parts.media_part)
    media_blob_pass = media_blob == _dropin_expected_picture_bytes(
        fixture_id,
        fixture_path,
    )
    shape = (
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
    )
    shape_type = str(shape.shape_type)
    shape_type_pass = shape_type == "PICTURE (13)"
    semantic_pass = (
        group.kind == "group"
        and picture is not None
        and picture.has_picture is True
        and transform == ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM
        and media_blob_pass
        and parent_preserved
    )
    picture_xml_pass = "<p:grpSp>" in slide_xml and "<p:pic>" in slide_xml
    ok = (
        semantic_pass
        and picture_xml_pass
        and shape_type_pass
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "picture_pass": semantic_pass,
        "picture_xml_pass": picture_xml_pass,
        "picture_shape_type_pass": shape_type_pass,
        "picture_shape_type": shape_type,
        "picture_transform": transform,
        "media_blob_pass": media_blob_pass,
        "media_blob_size": len(media_blob),
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_child_names,
        "expected_parent_child_names": expected_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "changed_rels_part": changed_rels_part,
        "picture_media_part": picture_parts.media_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_nested_group_picture_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_PICTURE_TARGETS:
        raise RuntimeError(
            f"drop-in add-nested-group-picture benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_PICTURE_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_rels_part = f"ppt/slides/_rels/slide{slide_index + 1}.xml.rels"
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = _top_level_picture_package_delta_ok(
        fixture_id,
        package_diff.added_parts,
        package_diff.changed_parts,
        package_diff.removed_parts,
        slide_index=slide_index,
    )
    source_group = source_summary.slides[slide_index].shapes[group_index]
    group = summary.slides[slide_index].shapes[group_index]
    expected_child_names = [child.name for child in source_group.children]
    parent_child_names = [
        child.name for child in group.children[: len(expected_child_names)]
    ]
    parent_preserved = parent_child_names == expected_child_names
    nested = group.children[-1] if group.children else None
    picture = nested.children[-1] if nested is not None and nested.children else None
    transform = None
    if picture is not None and picture.transform is not None:
        transform = {
            "x": picture.transform.x,
            "y": picture.transform.y,
            "cx": picture.transform.cx,
            "cy": picture.transform.cy,
        }
    picture_parts = _last_slide_picture_parts(output_path, slide_index=slide_index)
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
        media_blob = package.read(picture_parts.media_part)
    media_blob_pass = media_blob == _dropin_expected_picture_bytes(
        fixture_id,
        fixture_path,
    )
    shape = (
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
        .shapes[-1]
    )
    shape_type = str(shape.shape_type)
    shape_type_pass = shape_type == "PICTURE (13)"
    semantic_pass = (
        group.kind == "group"
        and nested is not None
        and nested.kind == "group"
        and picture is not None
        and picture.has_picture is True
        and transform == ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM
        and media_blob_pass
        and parent_preserved
    )
    picture_xml_pass = "<p:grpSp>" in slide_xml and "<p:pic>" in slide_xml
    ok = (
        semantic_pass
        and picture_xml_pass
        and shape_type_pass
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "picture_pass": semantic_pass,
        "picture_xml_pass": picture_xml_pass,
        "picture_shape_type_pass": shape_type_pass,
        "picture_shape_type": shape_type,
        "picture_transform": transform,
        "media_blob_pass": media_blob_pass,
        "media_blob_size": len(media_blob),
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_child_names,
        "expected_parent_child_names": expected_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "changed_rels_part": changed_rels_part,
        "picture_media_part": picture_parts.media_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_deeper_nested_group_picture_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_PICTURE_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-picture benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_PICTURE_TARGETS[fixture_id]
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_rels_part = f"ppt/slides/_rels/slide{slide_index + 1}.xml.rels"
    summary = extract_semantics(output_path)
    source_summary = extract_semantics(fixture_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = _top_level_picture_package_delta_ok(
        fixture_id,
        package_diff.added_parts,
        package_diff.changed_parts,
        package_diff.removed_parts,
        slide_index=slide_index,
    )
    source_group = source_summary.slides[slide_index].shapes[group_index]
    group = summary.slides[slide_index].shapes[group_index]
    expected_child_names = [child.name for child in source_group.children]
    parent_child_names = [
        child.name for child in group.children[: len(expected_child_names)]
    ]
    parent_preserved = parent_child_names == expected_child_names
    nested = group.children[-1] if group.children else None
    deeper = nested.children[-1] if nested is not None and nested.children else None
    picture = deeper.children[-1] if deeper is not None and deeper.children else None
    transform = None
    if picture is not None and picture.transform is not None:
        transform = {
            "x": picture.transform.x,
            "y": picture.transform.y,
            "cx": picture.transform.cx,
            "cy": picture.transform.cy,
        }
    picture_parts = _last_slide_picture_parts(output_path, slide_index=slide_index)
    with ZipFile(output_path) as package:
        slide_xml = package.read(changed_slide_part).decode("utf-8")
        media_blob = package.read(picture_parts.media_part)
    media_blob_pass = media_blob == _dropin_expected_picture_bytes(
        fixture_id,
        fixture_path,
    )
    shape = (
        WolfPresentation(output_path)
        .slides[slide_index]
        .shapes[group_index]
        .shapes[-1]
        .shapes[-1]
        .shapes[-1]
    )
    shape_type = str(shape.shape_type)
    shape_type_pass = shape_type == "PICTURE (13)"
    semantic_pass = (
        group.kind == "group"
        and nested is not None
        and nested.kind == "group"
        and deeper is not None
        and deeper.kind == "group"
        and picture is not None
        and picture.has_picture is True
        and transform == ADD_PICTURE_EXPLICIT_EXPECTED_TRANSFORM
        and media_blob_pass
        and parent_preserved
    )
    picture_xml_pass = "<p:grpSp>" in slide_xml and "<p:pic>" in slide_xml
    ok = (
        semantic_pass
        and picture_xml_pass
        and shape_type_pass
        and package_delta_ok
        and openxml_ok
    )
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "picture_pass": semantic_pass,
        "deeper_group_picture_pass": bool(picture is not None and picture.has_picture),
        "picture_xml_pass": picture_xml_pass,
        "picture_shape_type_pass": shape_type_pass,
        "picture_shape_type": shape_type,
        "picture_transform": transform,
        "media_blob_pass": media_blob_pass,
        "media_blob_size": len(media_blob),
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_child_names,
        "expected_parent_child_names": expected_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "changed_rels_part": changed_rels_part,
        "picture_media_part": picture_parts.media_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_picture_file_like_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_PICTURE_FIXTURES:
        raise RuntimeError(
            f"drop-in add-picture file-like benchmark does not support fixture {fixture_id}"
        )
    summary = extract_semantics(output_path)
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    package_delta_ok = _top_level_picture_package_delta_ok(
        fixture_id,
        package_diff.added_parts,
        package_diff.changed_parts,
        package_diff.removed_parts,
    )
    picture = summary.slides[0].shapes[-1]
    transform = None
    if picture.transform is not None:
        transform = {
            "x": picture.transform.x,
            "y": picture.transform.y,
            "cx": picture.transform.cx,
            "cy": picture.transform.cy,
        }
    picture_parts = _last_slide_picture_parts(output_path)
    with ZipFile(output_path) as package:
        media_blob = package.read(picture_parts.media_part)
    media_blob_pass = media_blob == _dropin_expected_picture_bytes(
        fixture_id,
        fixture_path,
    )
    semantic_pass = (
        picture.has_picture is True
        and transform == ADD_PICTURE_NATIVE_EXPECTED_TRANSFORM
        and media_blob_pass
    )
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "picture_pass": semantic_pass,
        "picture_transform": transform,
        "media_blob_pass": media_blob_pass,
        "media_blob_size": len(media_blob),
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "picture_media_part": picture_parts.media_part,
        "picture_slide_part": picture_parts.slide_part,
        "picture_rels_part": picture_parts.rels_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }
