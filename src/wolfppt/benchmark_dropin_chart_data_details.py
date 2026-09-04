"""Chart data drop-in benchmark result detail readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .benchmark_cases import C_NS
from .benchmark_dropin_actions import (
    _chart_bubble_data_edit_case,
    _chart_data_edit_case,
    _chart_empty_bubble_data_edit_case,
    _chart_empty_category_data_edit_case,
    _chart_empty_xy_data_edit_case,
    _chart_hierarchical_category_data_edit_case,
    _chart_sparse_category_data_edit_case,
    _chart_xy_data_edit_case,
    _read_wolfppt_chart_bubble_data_metadata,
    _read_wolfppt_chart_metadata,
    _read_wolfppt_chart_xy_data_metadata,
)
from .benchmark_dropin_chart_readers import _first_chart_shape
from .benchmark_validation import _validate_output
from .package_diff import diff_packages
from .presentation import Presentation as WolfPresentation


def _dropin_chart_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_category_chart_data_edit_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
        _chart_data_edit_case(fixture_id),
    )


def _dropin_chart_sparse_category_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_category_chart_data_edit_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
        _chart_sparse_category_data_edit_case(fixture_id),
    )


def _dropin_chart_hierarchical_category_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_category_chart_data_edit_details(
        fixture_id,
        fixture_path,
        output_path,
        validate_openxml,
        _chart_hierarchical_category_data_edit_case(fixture_id),
    )


def _dropin_chart_empty_category_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_empty_chart_data_edit_details(
        fixture_path,
        output_path,
        validate_openxml,
        _chart_empty_category_data_edit_case(fixture_id),
    )


def _dropin_category_chart_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
    case: dict[str, Any],
) -> dict[str, Any]:
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    metadata = _read_wolfppt_chart_metadata(fixture_id, WolfPresentation(output_path))
    changed_chart_part = metadata["chart_part"]["partname"].lstrip("/")
    changed_workbook_parts = _changed_workbook_parts(package_diff.changed_parts)
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part, *changed_workbook_parts]
        and len(changed_workbook_parts) == 1
        and package_diff.removed_parts == []
    )
    metadata_pass = _chart_data_edit_pass(metadata, case)
    hierarchy_xml = _chart_hierarchy_xml_details(output_path, changed_chart_part)
    hierarchy_xml_pass = _chart_hierarchy_xml_pass(hierarchy_xml, case)
    date_category_xml = _chart_date_category_xml_details(output_path, changed_chart_part)
    date_category_xml_pass = _chart_date_category_xml_pass(date_category_xml, case)
    ok = (
        metadata_pass
        and changed_parts_ok
        and openxml_ok
        and hierarchy_xml_pass
        and date_category_xml_pass
    )
    return {
        "ok": ok,
        "semantic_pass": metadata_pass and hierarchy_xml_pass and date_category_xml_pass,
        "semantic_score": (
            1.0 if metadata_pass and hierarchy_xml_pass and date_category_xml_pass else 0.0
        ),
        "metadata_pass": metadata_pass,
        "metadata": metadata,
        "hierarchy_xml_pass": hierarchy_xml_pass,
        "hierarchy_xml": hierarchy_xml,
        "date_category_xml_pass": date_category_xml_pass,
        "date_category_xml": date_category_xml,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "changed_parts": package_diff.changed_parts,
        "changed_chart_part": changed_chart_part,
        "changed_workbook_parts": changed_workbook_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
        "sparse_variant": case.get("sparse_variant"),
        "category_variant": case.get("category_variant"),
    }


def _chart_data_edit_pass(metadata: dict[str, Any], case: dict[str, Any]) -> bool:
    return metadata.get("categories") == case["categories"] and metadata.get(
        "series"
    ) == case["series"]


def _chart_hierarchy_xml_details(
    output_path: Path,
    changed_chart_part: str,
) -> dict[str, Any]:
    with ZipFile(output_path) as package:
        root = ET.fromstring(package.read(changed_chart_part))
    reference = root.find(f".//{{{C_NS}}}ser/{{{C_NS}}}cat/{{{C_NS}}}multiLvlStrRef")
    cache = None if reference is None else reference.find(f"{{{C_NS}}}multiLvlStrCache")
    point_count = None if cache is None else cache.find(f"{{{C_NS}}}ptCount")
    formula = None if reference is None else reference.find(f"{{{C_NS}}}f")
    return {
        "has_multi_level_ref": reference is not None,
        "has_multi_level_cache": cache is not None,
        "formula": None if formula is None else formula.text,
        "level_count": 0 if cache is None else len(cache.findall(f"{{{C_NS}}}lvl")),
        "point_count": None if point_count is None else point_count.get("val"),
    }


def _chart_hierarchy_xml_pass(
    hierarchy_xml: dict[str, Any],
    case: dict[str, Any],
) -> bool:
    if "hierarchy" not in case:
        return (
            hierarchy_xml["has_multi_level_ref"] is False
            and hierarchy_xml["has_multi_level_cache"] is False
        )
    return (
        hierarchy_xml["has_multi_level_ref"] is True
        and hierarchy_xml["has_multi_level_cache"] is True
        and hierarchy_xml["level_count"] == _hierarchy_depth(case["hierarchy"])
        and hierarchy_xml["point_count"] == str(len(case["categories"]))
    )


def _hierarchy_depth(categories: list[dict[str, Any]]) -> int:
    return max(_category_depth(category) for category in categories)


def _category_depth(category: dict[str, Any]) -> int:
    children = category.get("children", [])
    nested_children = [child for child in children if isinstance(child, dict)]
    if not nested_children:
        return 1 + int(bool(children))
    return 1 + max(_category_depth(child) for child in nested_children)


def _chart_date_category_xml_details(
    output_path: Path,
    changed_chart_part: str,
) -> dict[str, Any]:
    with ZipFile(output_path) as package:
        root = ET.fromstring(package.read(changed_chart_part))
    cat = root.find(f".//{{{C_NS}}}ser/{{{C_NS}}}cat")
    num_ref = None if cat is None else cat.find(f"{{{C_NS}}}numRef")
    str_ref = None if cat is None else cat.find(f"{{{C_NS}}}strRef")
    cache = None if num_ref is None else num_ref.find(f"{{{C_NS}}}numCache")
    format_code = None if cache is None else cache.find(f"{{{C_NS}}}formatCode")
    point_count = None if cache is None else cache.find(f"{{{C_NS}}}ptCount")
    return {
        "has_num_ref": num_ref is not None,
        "has_str_ref": str_ref is not None,
        "format_code": None if format_code is None else format_code.text,
        "point_count": None if point_count is None else point_count.get("val"),
    }


def _chart_date_category_xml_pass(
    date_category_xml: dict[str, Any],
    case: dict[str, Any],
) -> bool:
    if case.get("category_kind") != "date":
        return True
    return (
        date_category_xml["has_num_ref"] is True
        and date_category_xml["has_str_ref"] is False
        and date_category_xml["format_code"] == r"yyyy\-mm\-dd"
        and date_category_xml["point_count"] == str(len(case["categories"]))
    )


def _dropin_chart_empty_xy_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_empty_chart_data_edit_details(
        fixture_path,
        output_path,
        validate_openxml,
        _chart_empty_xy_data_edit_case(fixture_id),
    )


def _dropin_chart_xy_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    case = _chart_xy_data_edit_case(fixture_id)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    prs = WolfPresentation(output_path)
    changed_chart_part = _first_chart_shape(prs).chart_part.partname.lstrip("/")
    changed_workbook_parts = _changed_workbook_parts(package_diff.changed_parts)
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part, *changed_workbook_parts]
        and len(changed_workbook_parts) == 1
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_xy_data_metadata(
        fixture_id,
        prs,
    )
    expected_metadata = {
        "chart_type": "XY_SCATTER (-4169)",
        "categories": case["categories"],
        "series": case["series"],
    }
    metadata_pass = metadata == expected_metadata
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
        "changed_workbook_parts": changed_workbook_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_bubble_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    case = _chart_bubble_data_edit_case(fixture_id)
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    prs = WolfPresentation(output_path)
    changed_chart_part = _first_chart_shape(prs).chart_part.partname.lstrip("/")
    changed_workbook_parts = _changed_workbook_parts(package_diff.changed_parts)
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part, *changed_workbook_parts]
        and len(changed_workbook_parts) == 1
        and package_diff.removed_parts == []
    )
    metadata = _read_wolfppt_chart_bubble_data_metadata(
        fixture_id,
        prs,
    )
    expected_metadata = {
        "chart_type": "BUBBLE (15)",
        "categories": case["categories"],
        "series": case["series"],
    }
    metadata_pass = metadata == expected_metadata
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
        "changed_workbook_parts": changed_workbook_parts,
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _dropin_chart_empty_bubble_data_edit_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
) -> dict[str, Any]:
    return _dropin_empty_chart_data_edit_details(
        fixture_path,
        output_path,
        validate_openxml,
        _chart_empty_bubble_data_edit_case(fixture_id),
    )


def _dropin_empty_chart_data_edit_details(
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
    case: dict[str, Any],
) -> dict[str, Any]:
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    openxml_ok = validation.get("valid") is not False
    prs = WolfPresentation(output_path)
    shape = _first_chart_shape(prs)
    chart = shape.chart
    changed_chart_part = shape.chart_part.partname.lstrip("/")
    changed_workbook_parts = _changed_workbook_parts(package_diff.changed_parts)
    changed_parts_ok = (
        package_diff.added_parts == []
        and package_diff.changed_parts == [changed_chart_part, *changed_workbook_parts]
        and len(changed_workbook_parts) == 1
        and package_diff.removed_parts == []
    )
    metadata = {
        "chart_type": str(chart.chart_type),
        "plot_count": len(chart.plots),
        "categories": list(chart.categories),
        "series": [
            {
                "name": series.name,
                "values": series.values,
            }
            for series in chart.series
        ],
    }
    expected_metadata = {
        "chart_type": case["chart_type"],
        "plot_count": case["plot_count"],
        "categories": case["categories"],
        "series": case["series"],
    }
    metadata_pass = metadata == expected_metadata
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
        "changed_workbook_parts": changed_workbook_parts,
        "empty_variant": case["empty_variant"],
        "openxml_valid": validation.get("valid"),
        "openxml_validation": validation,
    }


def _changed_workbook_parts(changed_parts: list[str]) -> list[str]:
    return [
        part
        for part in changed_parts
        if part.startswith("ppt/embeddings/") and part.endswith(".xlsx")
    ]
