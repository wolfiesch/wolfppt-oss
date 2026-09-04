"""Movie and OLE result details for drop-in media benchmarks."""

from __future__ import annotations

import posixpath
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .benchmark_cases import (
    ADD_MOVIE_EXPECTED_TRANSFORM,
    ADD_OLE_OBJECT_EXPECTED_TRANSFORM,
)
from .benchmark_dropin_media_detail_helpers import (
    GROUP_OLE_OBJECT_TARGETS,
    TOP_LEVEL_MEDIA_FIXTURES,
    _dropin_expected_movie_bytes,
    _dropin_expected_ole_object_bytes,
    _dropin_expected_picture_bytes,
    _last_slide_picture_parts,
    _part_metadata,
)
from .benchmark_validation import _validate_output
from .extractor import extract_semantics
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


def _dropin_add_movie_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-movie benchmark does not support fixture {fixture_id}"
        )
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    poster_parts = [
        part
        for part in package_diff.added_parts
        if part.startswith("ppt/media/image") and part.endswith(".png")
    ]
    movie_parts = [
        part
        for part in package_diff.added_parts
        if part.startswith("ppt/media/media") and part.endswith(".mp4")
    ]
    required_changed = {
        "ppt/slides/_rels/slide1.xml.rels",
        "ppt/slides/slide1.xml",
    }
    allowed_changed = required_changed | {"[Content_Types].xml"}
    package_delta_ok = (
        len(poster_parts) <= 1
        and len(movie_parts) == 1
        and sorted(package_diff.added_parts) == sorted(poster_parts + movie_parts)
        and required_changed <= set(package_diff.changed_parts)
        and set(package_diff.changed_parts) <= allowed_changed
        and package_diff.removed_parts == []
    )
    source_summary = extract_semantics(fixture_path)
    summary = extract_semantics(output_path)
    source_media_targets = {
        rel.target
        for rel in source_summary.relationships
        if rel.source == "ppt/slides/slide1.xml"
        and (rel.type.endswith("/media") or rel.type.endswith("/video"))
    }
    media_targets = sorted(
        {
            rel.target
            for rel in summary.relationships
            if rel.source == "ppt/slides/slide1.xml"
            and (rel.type.endswith("/media") or rel.type.endswith("/video"))
        }
    )
    added_media_targets = sorted(set(media_targets) - source_media_targets)
    shape = WolfPresentation(output_path).slides[0].shapes[-1]
    transform = {
        "x": int(shape.left),
        "y": int(shape.top),
        "cx": int(shape.width),
        "cy": int(shape.height),
    }
    expected_added_media_targets = (
        [f"../media/{posixpath.basename(movie_parts[0])}"] if movie_parts else []
    )
    poster_part = (
        poster_parts[0]
        if poster_parts
        else _last_slide_picture_parts(output_path).media_part
    )
    semantic_pass = (
        str(shape.shape_type) == "MEDIA (16)"
        and transform == ADD_MOVIE_EXPECTED_TRANSFORM
        and added_media_targets == expected_added_media_targets
    )
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "movie_pass": semantic_pass,
        "shape_type": str(shape.shape_type),
        "shape_transform": transform,
        "media_targets": media_targets,
        "added_media_targets": added_media_targets,
        "expected_added_media_targets": expected_added_media_targets,
        "movie_part": movie_parts[0] if movie_parts else None,
        "poster_part": poster_part,
        "poster_part_added": poster_part in package_diff.added_parts,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_movie_file_like_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    details = _dropin_add_movie_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
    )
    with ZipFile(output_path) as package:
        media_blob = package.read(details["movie_part"])
        poster_blob = package.read(details["poster_part"])
    media_blob_pass = media_blob == _dropin_expected_movie_bytes()
    poster_blob_pass = poster_blob == _dropin_expected_picture_bytes(
        fixture_id,
        fixture_path,
    )
    semantic_pass = (
        bool(details["semantic_pass"]) and media_blob_pass and poster_blob_pass
    )
    details.update(
        {
            "ok": semantic_pass
            and bool(details["ok"])
            and details["openxml_valid"] is not False,
            "semantic_pass": semantic_pass,
            "semantic_score": 1.0 if semantic_pass else 0.0,
            "movie_pass": semantic_pass,
            "media_blob_pass": media_blob_pass,
            "media_blob_size": len(media_blob),
            "poster_blob_pass": poster_blob_pass,
            "poster_blob_size": len(poster_blob),
        }
    )
    return details
def _dropin_add_ole_object_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in TOP_LEVEL_MEDIA_FIXTURES:
        raise RuntimeError(
            f"drop-in add-ole-object benchmark does not support fixture {fixture_id}"
        )
    return _dropin_add_ole_object_details_for_location(
        fixture_path,
        output_path,
        validate_openxml,
        shape_location="slide",
    )


def _dropin_add_group_ole_object_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_OLE_OBJECT_TARGETS:
        raise RuntimeError(
            f"drop-in add-group-ole-object benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_OLE_OBJECT_TARGETS[fixture_id]
    return _dropin_add_ole_object_details_for_location(
        fixture_path,
        output_path,
        validate_openxml,
        shape_location="group",
        slide_index=slide_index,
        group_index=group_index,
    )


def _dropin_add_nested_group_ole_object_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_OLE_OBJECT_TARGETS:
        raise RuntimeError(
            f"drop-in add-nested-group-ole-object benchmark does not support fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_OLE_OBJECT_TARGETS[fixture_id]
    return _dropin_add_ole_object_details_for_location(
        fixture_path,
        output_path,
        validate_openxml,
        shape_location="nested_group",
        slide_index=slide_index,
        group_index=group_index,
    )


def _dropin_add_deeper_nested_group_ole_object_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    if fixture_id not in GROUP_OLE_OBJECT_TARGETS:
        raise RuntimeError(
            "drop-in add-deeper-nested-group-ole-object benchmark does not support "
            f"fixture {fixture_id}"
        )
    slide_index, group_index = GROUP_OLE_OBJECT_TARGETS[fixture_id]
    details = _dropin_add_ole_object_details_for_location(
        fixture_path,
        output_path,
        validate_openxml,
        shape_location="deeper_nested_group",
        slide_index=slide_index,
        group_index=group_index,
    )
    details["deeper_group_ole_object_pass"] = bool(details["ole_object_pass"])
    return details


def _dropin_add_ole_object_details_for_location(
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
    *,
    shape_location: str,
    slide_index: int = 0,
    group_index: int = 0,
) -> dict[str, Any]:
    changed_slide_part = f"ppt/slides/slide{slide_index + 1}.xml"
    changed_rels_part = f"ppt/slides/_rels/slide{slide_index + 1}.xml.rels"
    package_diff = diff_packages(fixture_path, output_path)
    validation = (
        _validate_output(output_path) if validate_openxml else {"enabled": False}
    )
    openxml_ok = validation.get("valid") is not False
    icon_parts = [
        part
        for part in package_diff.added_parts
        if part.startswith("ppt/media/image") and part.endswith(".png")
    ]
    ole_parts = [
        part
        for part in package_diff.added_parts
        if part.startswith("ppt/embeddings/oleObject") and part.endswith(".bin")
    ]
    required_changed = {changed_rels_part, changed_slide_part}
    allowed_changed = required_changed | {"[Content_Types].xml"}
    package_delta_ok = (
        len(icon_parts) <= 1
        and len(ole_parts) == 1
        and sorted(package_diff.added_parts) == sorted(icon_parts + ole_parts)
        and required_changed <= set(package_diff.changed_parts)
        and set(package_diff.changed_parts) <= allowed_changed
        and package_diff.removed_parts == []
    )
    source_summary = extract_semantics(fixture_path)
    summary = extract_semantics(output_path)
    source_ole_targets = {
        rel.target
        for rel in source_summary.relationships
        if rel.source == changed_slide_part and rel.type.endswith("/oleObject")
    }
    ole_targets = sorted(
        {
            rel.target
            for rel in summary.relationships
            if rel.source == changed_slide_part and rel.type.endswith("/oleObject")
        }
    )
    added_ole_targets = sorted(set(ole_targets) - source_ole_targets)
    parent_child_names: list[str] = []
    expected_parent_child_names: list[str] = []
    parent_preserved = True
    slide_shapes = WolfPresentation(output_path).slides[slide_index].shapes
    if shape_location != "slide":
        source_group = source_summary.slides[slide_index].shapes[group_index]
        output_group = summary.slides[slide_index].shapes[group_index]
        expected_parent_child_names = [child.name for child in source_group.children]
        parent_child_names = [
            child.name
            for child in output_group.children[: len(expected_parent_child_names)]
        ]
        parent_preserved = parent_child_names == expected_parent_child_names
    if shape_location == "slide":
        shape = slide_shapes[-1]
    elif shape_location == "group":
        shape = slide_shapes[group_index].shapes[-1]
    elif shape_location == "nested_group":
        shape = slide_shapes[group_index].shapes[-1].shapes[-1]
    elif shape_location == "deeper_nested_group":
        shape = slide_shapes[group_index].shapes[-1].shapes[-1].shapes[-1]
    else:  # pragma: no cover - defensive guard for future callers.
        raise RuntimeError(f"unsupported OLE shape location {shape_location!r}")
    ole_format = shape.ole_format
    transform = {
        "x": int(shape.left),
        "y": int(shape.top),
        "cx": int(shape.width),
        "cy": int(shape.height),
    }
    ole_format_metadata = {
        "prog_id": ole_format.prog_id,
        "show_as_icon": ole_format.show_as_icon,
        "blob_size": len(ole_format.blob),
        "blob_pass": ole_format.blob == _dropin_expected_ole_object_bytes(),
        "part": _part_metadata(ole_format),
        "element_tag": ole_format.element.tag,
        "element_child_count": len(ole_format.element),
    }
    expected_added_ole_targets = (
        [f"../embeddings/{posixpath.basename(ole_parts[0])}"] if ole_parts else []
    )
    icon_part = (
        icon_parts[0]
        if icon_parts
        else _last_slide_picture_parts(output_path, slide_index=slide_index).media_part
    )
    semantic_pass = (
        str(shape.shape_type) == "EMBEDDED_OLE_OBJECT (7)"
        and transform == ADD_OLE_OBJECT_EXPECTED_TRANSFORM
        and added_ole_targets == expected_added_ole_targets
        and ole_format_metadata["prog_id"] == "Package"
        and ole_format_metadata["show_as_icon"] is True
        and ole_format_metadata["blob_pass"] is True
        and parent_preserved
    )
    ok = semantic_pass and package_delta_ok and openxml_ok
    return {
        "ok": ok,
        "semantic_pass": semantic_pass,
        "semantic_score": 1.0 if semantic_pass else 0.0,
        "ole_object_pass": semantic_pass,
        "shape_type": str(shape.shape_type),
        "shape_transform": transform,
        "ole_targets": ole_targets,
        "added_ole_targets": added_ole_targets,
        "expected_added_ole_targets": expected_added_ole_targets,
        "ole_part": ole_parts[0] if ole_parts else None,
        "icon_part": icon_part,
        "icon_part_added": icon_part in package_diff.added_parts,
        "parent_group_child_preserved": parent_preserved,
        "parent_child_names": parent_child_names,
        "expected_parent_child_names": expected_parent_child_names,
        "target_slide_index": slide_index,
        "target_group_index": group_index,
        "ole_format": ole_format_metadata,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "added_parts": package_diff.added_parts,
        "changed_parts": package_diff.changed_parts,
        "changed_slide_part": changed_slide_part,
        "changed_rels_part": changed_rels_part,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_add_ole_object_file_like_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    details = _dropin_add_ole_object_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
    )
    with ZipFile(output_path) as package:
        embedded_blob = package.read(details["ole_part"])
        icon_blob = package.read(details["icon_part"])
    embedded_blob_pass = embedded_blob == _dropin_expected_ole_object_bytes()
    icon_blob_pass = icon_blob == _dropin_expected_picture_bytes(
        fixture_id,
        fixture_path,
    )
    semantic_pass = (
        bool(details["semantic_pass"]) and embedded_blob_pass and icon_blob_pass
    )
    details.update(
        {
            "ok": semantic_pass
            and bool(details["ok"])
            and details["openxml_valid"] is not False,
            "semantic_pass": semantic_pass,
            "semantic_score": 1.0 if semantic_pass else 0.0,
            "ole_object_pass": semantic_pass,
            "embedded_blob_pass": embedded_blob_pass,
            "embedded_blob_size": len(embedded_blob),
            "icon_blob_pass": icon_blob_pass,
            "icon_blob_size": len(icon_blob),
        }
    )
    return details
