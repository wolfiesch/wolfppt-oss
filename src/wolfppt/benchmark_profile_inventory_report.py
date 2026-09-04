"""Inventory report helpers for benchmark profile markdown."""

from __future__ import annotations

from typing import Any


def private_inventory_markdown(
    inventory: dict[str, Any],
    gates: dict[str, int],
) -> list[str]:
    counts = inventory.get("complexity_counts", {})
    feature_deck_counts = inventory.get("feature_deck_counts", {})
    distinct_feature_deck_counts = inventory.get("distinct_feature_deck_counts", {})
    lines = [
        "",
        "## Private Corpus",
        "",
        "| metric | observed | required |",
        "|---|---:|---:|",
        f"| decks | {inventory.get('deck_count')} | {_fmt_count(gates.get('deck_count'))} |",
        (
            "| distinct deck contents | "
            f"{inventory.get('distinct_content_count')} | "
            f"{_fmt_count(gates.get('distinct_content_count'))} |"
        ),
        f"| duplicate deck contents | {inventory.get('duplicate_content_count')} | n/a |",
        f"| slides | {counts.get('slides', inventory.get('total_slide_count'))} | {_fmt_count(gates.get('slides'))} |",
        f"| shapes | {counts.get('shapes', inventory.get('total_shape_count'))} | {_fmt_count(gates.get('shapes'))} |",
        (
            "| smallest deck slides | "
            f"{_min_complexity_count(inventory, 'slides')} | "
            f"{_fmt_count(gates.get('min_slides_per_deck'))} |"
        ),
        (
            "| smallest deck shapes | "
            f"{_min_complexity_count(inventory, 'shapes')} | "
            f"{_fmt_count(gates.get('min_shapes_per_deck'))} |"
        ),
        f"| tables | {counts.get('tables', inventory.get('total_table_count'))} | {_fmt_count(gates.get('tables'))} |",
        f"| charts | {counts.get('charts', inventory.get('total_chart_count'))} | {_fmt_count(gates.get('charts'))} |",
        f"| media parts | {counts.get('media', inventory.get('total_media_count'))} | {_fmt_count(gates.get('media'))} |",
        (
            "| embedded object parts | "
            f"{counts.get('embedded_objects', inventory.get('total_embedded_object_count'))} | "
            f"{_fmt_count(gates.get('embedded_objects'))} |"
        ),
        (
            "| decks with tables | "
            f"{dict(feature_deck_counts).get('tables')} | "
            f"{_fmt_count(gates.get('decks_with_tables'))} |"
        ),
        (
            "| distinct decks with tables | "
            f"{dict(distinct_feature_deck_counts).get('tables')} | "
            f"{_fmt_count(gates.get('distinct_decks_with_tables'))} |"
        ),
        (
            "| decks with charts | "
            f"{dict(feature_deck_counts).get('charts')} | "
            f"{_fmt_count(gates.get('decks_with_charts'))} |"
        ),
        (
            "| distinct decks with charts | "
            f"{dict(distinct_feature_deck_counts).get('charts')} | "
            f"{_fmt_count(gates.get('distinct_decks_with_charts'))} |"
        ),
        (
            "| decks with media | "
            f"{dict(feature_deck_counts).get('media')} | "
            f"{_fmt_count(gates.get('decks_with_media'))} |"
        ),
        (
            "| distinct decks with media | "
            f"{dict(distinct_feature_deck_counts).get('media')} | "
            f"{_fmt_count(gates.get('distinct_decks_with_media'))} |"
        ),
        (
            "| decks with embedded objects | "
            f"{dict(feature_deck_counts).get('embedded_objects')} | "
            f"{_fmt_count(gates.get('decks_with_embedded_objects'))} |"
        ),
        (
            "| distinct decks with embedded objects | "
            f"{dict(distinct_feature_deck_counts).get('embedded_objects')} | "
            f"{_fmt_count(gates.get('distinct_decks_with_embedded_objects'))} |"
        ),
        "",
        "| deck | extension | slides | shapes | tables | charts | media | embedded objects |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for deck in inventory.get("decks", []):
        deck_counts = deck.get("complexity_counts", {})
        lines.append(
            f"| `{deck.get('id')}` | {deck.get('extension')} | "
            f"{deck_counts.get('slides', deck.get('slide_count'))} | "
            f"{deck_counts.get('shapes')} | {deck_counts.get('tables')} | "
            f"{deck_counts.get('charts')} | {deck_counts.get('media')} | "
            f"{deck_counts.get('embedded_objects')} |"
        )
    return lines


def fixture_inventory_markdown(
    inventory: dict[str, Any],
    gates: dict[str, int],
) -> list[str]:
    counts = inventory.get("complexity_counts", {})
    feature_fixture_counts = inventory.get("feature_fixture_counts", {})
    lines = [
        "",
        "## Fixture Corpus",
        "",
        "| metric | observed | required |",
        "|---|---:|---:|",
        f"| fixtures | {inventory.get('fixture_count')} | n/a |",
        f"| slides | {counts.get('slides', inventory.get('total_slide_count'))} | {_fmt_count(gates.get('slides'))} |",
        f"| shapes | {counts.get('shapes', inventory.get('total_shape_count'))} | {_fmt_count(gates.get('shapes'))} |",
        f"| tables | {counts.get('tables', inventory.get('total_table_count'))} | {_fmt_count(gates.get('tables'))} |",
        f"| charts | {counts.get('charts', inventory.get('total_chart_count'))} | {_fmt_count(gates.get('charts'))} |",
        (
            "| fixtures with charts | "
            f"{dict(feature_fixture_counts).get('charts')} | "
            f"{_fmt_count(gates.get('fixtures_with_charts'))} |"
        ),
        f"| media parts | {counts.get('media', inventory.get('total_media_count'))} | {_fmt_count(gates.get('media'))} |",
        (
            "| fixtures with media | "
            f"{dict(feature_fixture_counts).get('media')} | "
            f"{_fmt_count(gates.get('fixtures_with_media'))} |"
        ),
        (
            "| embedded object parts | "
            f"{counts.get('embedded_objects', inventory.get('total_embedded_object_count'))} | "
            f"{_fmt_count(gates.get('embedded_objects'))} |"
        ),
        (
            "| fixtures with tables | "
            f"{dict(feature_fixture_counts).get('tables')} | "
            f"{_fmt_count(gates.get('fixtures_with_tables'))} |"
        ),
        (
            "| fixtures with embedded objects | "
            f"{dict(feature_fixture_counts).get('embedded_objects')} | "
            f"{_fmt_count(gates.get('fixtures_with_embedded_objects'))} |"
        ),
        "",
        "| fixture | slides | shapes | tables | charts | media | embedded objects |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for fixture in inventory.get("fixtures", []):
        fixture_counts = fixture.get("complexity_counts", {})
        lines.append(
            f"| `{fixture.get('id')}` | "
            f"{fixture_counts.get('slides')} | {fixture_counts.get('shapes')} | "
            f"{fixture_counts.get('tables')} | {fixture_counts.get('charts')} | "
            f"{fixture_counts.get('media')} | {fixture_counts.get('embedded_objects')} |"
        )
    return lines


def fixture_gate_observed(
    inventory: dict[str, Any],
    feature: str,
) -> int:
    if feature.startswith("fixtures_with_"):
        feature_name = feature.removeprefix("fixtures_with_")
        return int(dict(inventory.get("feature_fixture_counts", {})).get(feature_name, 0))
    return int(dict(inventory.get("complexity_counts", {})).get(feature, 0))


def _min_complexity_count(inventory: dict[str, Any], feature: str) -> Any:
    counts = inventory.get("minimum_complexity_counts")
    if isinstance(counts, dict):
        return counts.get(feature)
    deck_counts = [
        dict(deck.get("complexity_counts", {})).get(feature)
        for deck in inventory.get("decks", [])
        if isinstance(deck, dict)
    ]
    deck_counts = [count for count in deck_counts if count is not None]
    return min(deck_counts) if deck_counts else None


def _fmt_count(value: int | None) -> str:
    return "n/a" if value is None else str(value)
