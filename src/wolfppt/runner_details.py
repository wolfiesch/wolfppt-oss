"""Detail builders shared by corpus runner lanes."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .adapters.openxml import validate as validate_openxml
from .corpus import FIXTURE_ROOT
from .extractor import extract_semantics
from .package_diff import diff_packages

SHAPE_TEXT_REPLACEMENT = "WolfPPT Shape\nSecond Line"
PARAGRAPH_TEXT_REPLACEMENT = "WolfPPT Paragraph"


def _write_sample_png(tmp_path: Path) -> Path:
    image = tmp_path / "wolfppt-sample.png"
    with ZipFile(FIXTURE_ROOT / "media/png_picture.pptx") as package:
        image.write_bytes(package.read("ppt/media/image1.png"))
    return image


def _slide_add_details(
    input_path: Path,
    output_path: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    original = extract_semantics(input_path)
    added = extract_semantics(output_path)
    package_diff = diff_packages(input_path, output_path)
    try:
        validation_details = validate_openxml(output_path).to_dict()
        validation_ok = bool(validation_details["valid"])
    except RuntimeError as exc:
        validation_details = {"valid": None, "skipped": True, "reason": str(exc)}
        validation_ok = True
    slide_part = str(result["slide_part"])
    slide_prefix, slide_name = slide_part.rsplit("/", 1)
    expected_added_parts = {
        slide_part,
        f"{slide_prefix}/_rels/{slide_name}.rels",
    }
    allowed_changed_parts = {
        "[Content_Types].xml",
        "ppt/presentation.xml",
        "ppt/_rels/presentation.xml.rels",
    }
    original_slide_count = len(original.slides)
    new_slide_count = len(added.slides)
    ok = (
        new_slide_count == original_slide_count + 1
        and result["slide_count"] == new_slide_count
        and set(package_diff.added_parts) == expected_added_parts
        and not package_diff.removed_parts
        and set(package_diff.changed_parts).issubset(allowed_changed_parts)
        and validation_ok
    )
    return {
        "ok": ok,
        "result": result,
        "original_slide_count": original_slide_count,
        "new_slide_count": new_slide_count,
        "package_diff": package_diff.to_dict(),
        "openxml_validation": validation_details,
    }


def _text_run_replace_details(
    input_path: Path,
    output_path: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    original = extract_semantics(input_path)
    replaced = extract_semantics(output_path)
    package_diff = diff_packages(input_path, output_path)
    try:
        validation_details = validate_openxml(output_path).to_dict()
        validation_ok = bool(validation_details["valid"])
    except RuntimeError as exc:
        validation_details = {"valid": None, "skipped": True, "reason": str(exc)}
        validation_ok = True
    slide_part = replaced.slides[int(result["slide_index"])].part
    replaced_texts = _slide_text_values(replaced.slides[int(result["slide_index"])])
    ok = (
        result["replacements"] == 1
        and any("WolfPPT Run" in text for text in replaced_texts)
        and len(replaced.slides) == len(original.slides)
        and not package_diff.added_parts
        and not package_diff.removed_parts
        and set(package_diff.changed_parts).issubset({slide_part})
        and validation_ok
    )
    return {
        "ok": ok,
        "result": result,
        "package_diff": package_diff.to_dict(),
        "openxml_validation": validation_details,
    }


def _shape_text_set_details(
    input_path: Path,
    output_path: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    original = extract_semantics(input_path)
    replaced = extract_semantics(output_path)
    package_diff = diff_packages(input_path, output_path)
    try:
        validation_details = validate_openxml(output_path).to_dict()
        validation_ok = bool(validation_details["valid"])
    except RuntimeError as exc:
        validation_details = {"valid": None, "skipped": True, "reason": str(exc)}
        validation_ok = True
    slide_index = int(result["slide_index"])
    shape_index = int(result["shape_index"])
    slide_part = replaced.slides[slide_index].part
    original_shape_count = len(original.slides[slide_index].shapes)
    replaced_shape = replaced.slides[slide_index].shapes[shape_index]
    ok = (
        result["replacements"] >= 1
        and replaced_shape.text == SHAPE_TEXT_REPLACEMENT
        and len(replaced.slides) == len(original.slides)
        and len(replaced.slides[slide_index].shapes) == original_shape_count
        and not package_diff.added_parts
        and not package_diff.removed_parts
        and set(package_diff.changed_parts).issubset({slide_part})
        and validation_ok
    )
    return {
        "ok": ok,
        "result": result,
        "package_diff": package_diff.to_dict(),
        "openxml_validation": validation_details,
    }


def _paragraph_text_set_details(
    input_path: Path,
    output_path: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    original = extract_semantics(input_path)
    replaced = extract_semantics(output_path)
    package_diff = diff_packages(input_path, output_path)
    try:
        validation_details = validate_openxml(output_path).to_dict()
        validation_ok = bool(validation_details["valid"])
    except RuntimeError as exc:
        validation_details = {"valid": None, "skipped": True, "reason": str(exc)}
        validation_ok = True
    slide_index = int(result["slide_index"])
    shape_index = int(result["shape_index"])
    paragraph_index = int(result["paragraph_index"])
    slide_part = replaced.slides[slide_index].part
    original_shape_count = len(original.slides[slide_index].shapes)
    replaced_shape = replaced.slides[slide_index].shapes[shape_index]
    ok = (
        result["replacements"] >= 1
        and replaced_shape.paragraphs[paragraph_index] == PARAGRAPH_TEXT_REPLACEMENT
        and len(replaced.slides) == len(original.slides)
        and len(replaced.slides[slide_index].shapes) == original_shape_count
        and not package_diff.added_parts
        and not package_diff.removed_parts
        and set(package_diff.changed_parts).issubset({slide_part})
        and validation_ok
    )
    return {
        "ok": ok,
        "result": result,
        "package_diff": package_diff.to_dict(),
        "openxml_validation": validation_details,
    }


def _first_text_shape_target(path: Path) -> tuple[int, int] | None:
    semantics = extract_semantics(path)
    for slide_index, slide in enumerate(semantics.slides):
        for shape_index, shape in enumerate(slide.shapes):
            if shape.paragraphs and not shape.tables:
                return slide_index, shape_index
    return None


def _first_text_paragraph_target(path: Path) -> tuple[int, int, int] | None:
    semantics = extract_semantics(path)
    for slide_index, slide in enumerate(semantics.slides):
        for shape_index, shape in enumerate(slide.shapes):
            if shape.paragraphs and not shape.tables:
                return slide_index, shape_index, 0
    return None


def _slide_text_values(slide: Any) -> list[str]:
    values = list(slide.texts)
    for shape in slide.shapes:
        values.extend(shape.paragraphs)
        for table in shape.tables:
            values.extend(cell for row in table.rows for cell in row)
    return values


def _image_add_details(
    input_path: Path,
    output_path: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    original = extract_semantics(input_path)
    added = extract_semantics(output_path)
    package_diff = diff_packages(input_path, output_path)
    try:
        validation_details = validate_openxml(output_path).to_dict()
        validation_ok = bool(validation_details["valid"])
    except RuntimeError as exc:
        validation_details = {"valid": None, "skipped": True, "reason": str(exc)}
        validation_ok = True
    slide_part = str(result["slide_part"])
    rels_part = slide_part.replace("ppt/slides/", "ppt/slides/_rels/") + ".rels"
    image_part = str(result["image_part"])
    original_image_relationships = [
        rel for rel in original.relationships if rel.source == slide_part and rel.type.endswith("/image")
    ]
    added_image_relationships = [
        rel for rel in added.relationships if rel.source == slide_part and rel.type.endswith("/image")
    ]
    allowed_changed_parts = {
        "[Content_Types].xml",
        slide_part,
        rels_part,
    }
    allowed_added_parts = {
        image_part,
        rels_part,
    }
    ok = (
        len(added.slides) == len(original.slides)
        and len(added_image_relationships) == len(original_image_relationships) + 1
        and image_part in package_diff.added_parts
        and set(package_diff.added_parts).issubset(allowed_added_parts)
        and not package_diff.removed_parts
        and set(package_diff.changed_parts).issubset(allowed_changed_parts)
        and validation_ok
    )
    return {
        "ok": ok,
        "result": result,
        "original_image_relationship_count": len(original_image_relationships),
        "new_image_relationship_count": len(added_image_relationships),
        "package_diff": package_diff.to_dict(),
        "openxml_validation": validation_details,
    }


def _table_add_details(
    input_path: Path,
    output_path: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    original = extract_semantics(input_path)
    added = extract_semantics(output_path)
    package_diff = diff_packages(input_path, output_path)
    try:
        validation_details = validate_openxml(output_path).to_dict()
        validation_ok = bool(validation_details["valid"])
    except RuntimeError as exc:
        validation_details = {"valid": None, "skipped": True, "reason": str(exc)}
        validation_ok = True
    slide_part = str(result["slide_part"])
    original_slide = original.slides[int(result["slide_index"])]
    added_slide = added.slides[int(result["slide_index"])]
    original_tables = [table for shape in original_slide.shapes for table in shape.tables]
    added_tables = [table for shape in added_slide.shapes for table in shape.tables]
    added_table = added_tables[int(result["table_index"])]
    ok = (
        len(added.slides) == len(original.slides)
        and len(added_slide.shapes) == len(original_slide.shapes) + 1
        and len(added_tables) == len(original_tables) + 1
        and added_table.row_count == int(result["rows"])
        and added_table.col_count == int(result["cols"])
        and not package_diff.added_parts
        and not package_diff.removed_parts
        and set(package_diff.changed_parts).issubset({slide_part})
        and validation_ok
    )
    return {
        "ok": ok,
        "result": result,
        "original_shape_count": len(original_slide.shapes),
        "new_shape_count": len(added_slide.shapes),
        "package_diff": package_diff.to_dict(),
        "openxml_validation": validation_details,
    }
