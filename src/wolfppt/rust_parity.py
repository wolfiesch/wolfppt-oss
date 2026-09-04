"""Compare Rust typed summaries against Python semantic oracles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .compare import SemanticComparison, compare_semantics
from .native import summarize as native_summarize


def compare_native_summary(fixture_id: str, fixture_path: Path, expected: dict[str, Any]) -> SemanticComparison:
    """Compare the native Rust summary against normalized oracle facts."""

    actual = native_summarize(fixture_path).to_dict()
    return compare_semantics(
        fixture_id,
        normalize_python_oracle(expected),
        normalize_rust_summary(actual),
    )


def normalize_python_oracle(oracle: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_vba": oracle["has_vba"],
        "slide_count": len(oracle["slides"]),
        "slides": [_normalize_python_slide(oracle, slide) for slide in oracle["slides"]],
    }


def normalize_rust_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_vba": summary["has_vba"],
        "slide_count": summary["slide_count"],
        "slides": [
            {
                "part": slide["part"],
                "text_runs": _text_runs(slide),
                "shapes": [_normalize_shape(shape) for shape in slide.get("shapes", [])],
                "tables": slide["tables"],
                "notes": slide["notes"],
                "image_relationships": _normalize_rust_relationships(slide["image_relationships"]),
                "chart_relationships": _normalize_rust_relationships(slide["chart_relationships"]),
                "comment_relationships": _normalize_rust_relationships(slide["comment_relationships"]),
                "media_relationships": _normalize_rust_relationships(slide["media_relationships"]),
                "ole_relationships": _normalize_rust_relationships(slide["ole_relationships"]),
                "has_transition": slide["has_transition"],
                "has_timing": slide["has_timing"],
                "relationships": _normalize_rust_relationships(slide["relationships"]),
            }
            for slide in summary["slides"]
        ],
    }


def _normalize_python_slide(oracle: dict[str, Any], slide: dict[str, Any]) -> dict[str, Any]:
    return {
        "part": slide["part"],
        "text_runs": _text_runs(slide),
        "shapes": [_normalize_shape(shape) for shape in slide["shapes"]],
        "tables": _tables(slide),
        "notes": slide["notes"],
        "image_relationships": _typed_relationships(oracle, slide["part"], "/image"),
        "chart_relationships": _typed_relationships(oracle, slide["part"], "/chart"),
        "comment_relationships": _typed_relationships(oracle, slide["part"], "/comments", "/comment"),
        "media_relationships": _typed_relationships(oracle, slide["part"], "/audio", "/media", "/video"),
        "ole_relationships": _typed_relationships(oracle, slide["part"], "/oleObject", "/package"),
        "has_transition": slide["has_transition"],
        "has_timing": slide["has_timing"],
        "relationships": _slide_relationships(oracle, slide["part"]),
    }


def _normalize_shape(shape: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": shape.get("id"),
        "name": shape.get("name"),
        "kind": shape["kind"],
        "text": shape["text"],
        "paragraphs": shape["paragraphs"],
        "tables": shape["tables"],
        "relationship_ids": shape["relationship_ids"],
        "has_chart": shape["has_chart"],
        "has_picture": shape["has_picture"],
        "has_group": shape["has_group"],
        "transform": shape.get("transform"),
        "effective_transform": shape.get("effective_transform"),
        "children": [_normalize_shape(child) for child in shape.get("children", [])],
    }


def _text_runs(slide: dict[str, Any]) -> list[str]:
    runs: list[str] = []
    for shape in slide["shapes"]:
        runs.extend(shape["paragraphs"])
    return runs


def _tables(slide: dict[str, Any]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for shape in slide["shapes"]:
        tables.extend(shape["tables"])
    return tables


def _slide_relationships(oracle: dict[str, Any], part: str) -> list[dict[str, Any]]:
    rels = [
        {
            "id": rel["id"],
            "type": rel["type"],
            "target": rel["target"],
            "target_mode": rel.get("target_mode"),
        }
        for rel in oracle["relationships"]
        if rel["source"] == part
    ]
    return sorted(rels, key=lambda rel: (rel["id"], rel["target"], rel["type"]))


def _typed_relationships(oracle: dict[str, Any], part: str, *suffixes: str) -> list[dict[str, Any]]:
    return [
        rel
        for rel in _slide_relationships(oracle, part)
        if any(rel["type"].endswith(suffix) for suffix in suffixes)
    ]


def _normalize_rust_relationships(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "id": rel["id"],
                "type": rel["relationship_type"],
                "target": rel["target"],
                "target_mode": rel.get("target_mode"),
            }
            for rel in relationships
        ],
        key=lambda rel: (rel["id"], rel["target"], rel["type"]),
    )
