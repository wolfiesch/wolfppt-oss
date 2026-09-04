"""Private deck discovery for opt-in benchmark lanes."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any
from typing import Final

from .deck_complexity import DECK_COMPLEXITY_FEATURES
from .deck_complexity import DECK_COMPLEXITY_TOTAL_FIELDS
from .deck_complexity import deck_complexity_counts


PRIVATE_DECKS_ENV: Final = "WOLFPPT_PRIVATE_DECKS_DIR"
PRIVATE_DECKS_SENTINEL: Final = "private:*"
PRIVATE_DECK_EXTENSIONS: Final = {".pptx", ".pptm"}
PRIVATE_REPORT_TEXT_EXTENSIONS: Final = {".json", ".jsonl", ".md", ".txt"}
PRIVATE_COMPLEXITY_FEATURES: Final = DECK_COMPLEXITY_FEATURES
PRIVATE_COMPLEXITY_TOTAL_FIELDS: Final = DECK_COMPLEXITY_TOTAL_FIELDS
PRIVATE_FEATURE_DECK_FEATURES: Final = (
    "tables",
    "charts",
    "media",
    "embedded_objects",
)
PRIVATE_COMPLEXITY_LABELS: Final = {
    "slides": "total private deck slide(s)",
    "shapes": "total private deck shape(s)",
    "tables": "total private deck table(s)",
    "charts": "total private deck chart(s)",
    "media": "total private deck media part(s)",
    "embedded_objects": "total private deck embedded object part(s)",
}
PRIVATE_MIN_COMPLEXITY_LABELS: Final = {
    "slides": "slide(s) in the smallest private deck",
    "shapes": "shape(s) in the smallest private deck",
}
PRIVATE_FEATURE_DECK_LABELS: Final = {
    "tables": "private deck(s) with table(s)",
    "charts": "private deck(s) with chart(s)",
    "media": "private deck(s) with media part(s)",
    "embedded_objects": "private deck(s) with embedded object part(s)",
}


def discover_private_decks() -> list[dict[str, object]]:
    root_value = os.environ.get(PRIVATE_DECKS_ENV)
    if not root_value:
        raise ValueError(
            f"{PRIVATE_DECKS_ENV} is not set; point it at a private .pptx/.pptm corpus"
        )

    root = Path(root_value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"{PRIVATE_DECKS_ENV} does not point to a directory")

    decks = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and _is_private_deck(path)
    ]
    if not decks:
        raise ValueError(f"{PRIVATE_DECKS_ENV} contains no .pptx or .pptm files")

    seen_digests: dict[str, int] = {}
    return [_private_deck_item(path, seen_digests) for path in decks]


def private_deck_inventory() -> dict[str, object]:
    """Return a redacted inventory for the opt-in private deck corpus."""

    items = discover_private_decks()
    extensions = Counter(
        Path(str(item["report_path"])).suffix.lower()
        for item in items
    )
    distinct_content_count = len({str(item["content_digest"]) for item in items})
    complexity_counts: Counter[str] = Counter()
    for item in items:
        complexity_counts.update(
            {
                feature: int(dict(item["complexity_counts"])[feature])
                for feature in PRIVATE_COMPLEXITY_FEATURES
            }
        )
    complexity_payload = {
        feature: int(complexity_counts[feature])
        for feature in PRIVATE_COMPLEXITY_FEATURES
    }
    minimum_complexity_payload = {
        feature: min(
            int(dict(item["complexity_counts"])[feature])
            for item in items
        )
        for feature in PRIVATE_COMPLEXITY_FEATURES
    }
    feature_deck_count_payload = {
        feature: sum(
            1
            for item in items
            if int(dict(item["complexity_counts"])[feature]) > 0
        )
        for feature in PRIVATE_FEATURE_DECK_FEATURES
    }
    distinct_feature_deck_count_payload = {
        feature: len(
            {
                str(item["content_digest"])
                for item in items
                if int(dict(item["complexity_counts"])[feature]) > 0
            }
        )
        for feature in PRIVATE_FEATURE_DECK_FEATURES
    }
    total_fields = {
        total_field: complexity_payload[feature]
        for feature, total_field in PRIVATE_COMPLEXITY_TOTAL_FIELDS.items()
    }
    return {
        "env": PRIVATE_DECKS_ENV,
        "deck_count": len(items),
        "distinct_content_count": distinct_content_count,
        "duplicate_content_count": len(items) - distinct_content_count,
        **total_fields,
        "complexity_counts": complexity_payload,
        "minimum_complexity_counts": minimum_complexity_payload,
        "feature_deck_counts": feature_deck_count_payload,
        "distinct_feature_deck_counts": distinct_feature_deck_count_payload,
        "extension_counts": dict(sorted(extensions.items())),
        "decks": [
            {
                "id": str(item["id"]),
                "extension": Path(str(item["report_path"])).suffix.lower(),
                "slide_count": int(item["slide_count"]),
                "complexity_counts": dict(item["complexity_counts"]),
                "tags": list(item.get("tags", [])),
            }
            for item in items
        ],
    }


def verify_private_report_redaction(report_path: Path) -> dict[str, Any]:
    """Check report files for raw private deck names or paths."""

    target = report_path.expanduser().resolve()
    if not target.exists():
        raise ValueError("report path does not exist")
    files = _private_report_files(target)
    terms = sorted(_private_deck_redaction_terms(), key=len, reverse=True)
    leaks: list[dict[str, object]] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        match_count = sum(1 for term in terms if term in text)
        if match_count:
            leaks.append(
                {
                    "file": _report_file_label(file_path, target),
                    "match_count": match_count,
                }
            )
    return {
        "status": "pass" if not leaks else "fail",
        "checked_files": len(files),
        "forbidden_terms": len(terms),
        "leak_count": len(leaks),
        "leaks": leaks,
    }


def write_private_report_redaction_check(report_path: Path) -> dict[str, Any]:
    """Write and enforce a redaction check for a private benchmark report."""

    result = verify_private_report_redaction(report_path)
    check_path = (
        report_path / "redaction-check.json"
        if report_path.is_dir()
        else report_path.with_suffix(f"{report_path.suffix}.redaction-check.json")
    )
    check_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if result["status"] != "pass":
        raise ValueError("private report redaction check failed")
    return result


def has_private_fixture_ids(fixture_ids: list[str] | tuple[str, ...]) -> bool:
    return any(fixture_id.startswith("private/") for fixture_id in fixture_ids)


def private_complexity_total(inventory: dict[str, object], feature: str) -> int:
    try:
        field = PRIVATE_COMPLEXITY_TOTAL_FIELDS[feature]
    except KeyError as exc:
        known = ", ".join(PRIVATE_COMPLEXITY_FEATURES)
        raise ValueError(f"unknown private complexity feature {feature!r}; known: {known}") from exc
    return int(inventory[field])


def private_complexity_gate_message(
    inventory: dict[str, object],
    feature: str,
    minimum: int,
) -> str:
    value = private_complexity_total(inventory, feature)
    return (
        f"{inventory['env']} contains {value} {PRIVATE_COMPLEXITY_LABELS[feature]}; "
        f"at least {minimum} required"
    )


def private_min_complexity(inventory: dict[str, object], feature: str) -> int:
    if feature not in PRIVATE_MIN_COMPLEXITY_LABELS:
        known = ", ".join(PRIVATE_MIN_COMPLEXITY_LABELS)
        raise ValueError(
            f"unknown private minimum complexity feature {feature!r}; known: {known}"
        )
    counts = inventory.get("minimum_complexity_counts")
    if not isinstance(counts, dict):
        return 0
    return int(counts.get(feature, 0))


def private_min_complexity_gate_message(
    inventory: dict[str, object],
    feature: str,
    minimum: int,
) -> str:
    value = private_min_complexity(inventory, feature)
    return (
        f"{inventory['env']} contains {value} "
        f"{PRIVATE_MIN_COMPLEXITY_LABELS[feature]}; at least {minimum} required"
    )


def private_feature_deck_count(inventory: dict[str, object], feature: str) -> int:
    if feature not in PRIVATE_FEATURE_DECK_LABELS:
        known = ", ".join(PRIVATE_FEATURE_DECK_LABELS)
        raise ValueError(
            f"unknown private feature-deck feature {feature!r}; known: {known}"
        )
    counts = inventory.get("feature_deck_counts")
    if not isinstance(counts, dict):
        return 0
    return int(counts.get(feature, 0))


def private_feature_deck_gate_message(
    inventory: dict[str, object],
    feature: str,
    minimum: int,
) -> str:
    value = private_feature_deck_count(inventory, feature)
    return (
        f"{inventory['env']} contains {value} "
        f"{PRIVATE_FEATURE_DECK_LABELS[feature]}; at least {minimum} required"
    )


def private_distinct_feature_deck_count(
    inventory: dict[str, object],
    feature: str,
) -> int:
    if feature not in PRIVATE_FEATURE_DECK_LABELS:
        known = ", ".join(PRIVATE_FEATURE_DECK_LABELS)
        raise ValueError(
            f"unknown private distinct feature-deck feature {feature!r}; known: {known}"
        )
    counts = inventory.get("distinct_feature_deck_counts")
    if not isinstance(counts, dict):
        return 0
    return int(counts.get(feature, 0))


def private_distinct_feature_deck_gate_message(
    inventory: dict[str, object],
    feature: str,
    minimum: int,
) -> str:
    value = private_distinct_feature_deck_count(inventory, feature)
    return (
        f"{inventory['env']} contains {value} distinct-content "
        f"{PRIVATE_FEATURE_DECK_LABELS[feature]}; at least {minimum} required"
    )


def _is_private_deck(path: Path) -> bool:
    return path.suffix.lower() in PRIVATE_DECK_EXTENSIONS and not path.name.startswith("~$")


def _private_deck_item(
    path: Path,
    seen_digests: dict[str, int],
) -> dict[str, object]:
    content_digest = _private_deck_digest(path)
    seen_digests[content_digest] = seen_digests.get(content_digest, 0) + 1
    report_digest = content_digest
    if seen_digests[content_digest] > 1:
        report_digest = f"{content_digest}-{seen_digests[content_digest]}"
    private_id = f"private/deck-{report_digest}"
    complexity_counts = _private_deck_complexity_counts(path)
    return {
        "id": private_id,
        "content_digest": content_digest,
        "slide_count": complexity_counts["slides"],
        "complexity_counts": complexity_counts,
        "path": f"<private>/deck-{report_digest}{path.suffix.lower()}",
        "actual_path": str(path),
        "report_path": f"<private>/deck-{report_digest}{path.suffix.lower()}",
        "description": "Private user-supplied benchmark deck",
        "tags": ["private", "real-world"],
    }


def _private_deck_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:12]


def _private_deck_complexity_counts(path: Path) -> dict[str, int]:
    try:
        return deck_complexity_counts(path)
    except ValueError as exc:
        message = str(exc).replace("deck", "private deck", 1)
        raise ValueError(message) from exc


def _private_report_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in PRIVATE_REPORT_TEXT_EXTENSIONS else []
    return [
        item
        for item in sorted(path.rglob("*"))
        if item.is_file() and item.suffix.lower() in PRIVATE_REPORT_TEXT_EXTENSIONS
    ]


def _private_deck_redaction_terms() -> set[str]:
    root_value = os.environ.get(PRIVATE_DECKS_ENV)
    if not root_value:
        raise ValueError(
            f"{PRIVATE_DECKS_ENV} is not set; point it at a private .pptx/.pptm corpus"
        )
    root = Path(root_value).expanduser().resolve()
    items = discover_private_decks()
    terms = {root_value, str(root), root.name, Path(root_value).name}
    for item in items:
        actual_path = Path(str(item["actual_path"])).resolve()
        terms.update({str(actual_path), actual_path.name, actual_path.stem})
        try:
            relative_path = actual_path.relative_to(root)
        except ValueError:
            relative_path = Path(actual_path.name)
        terms.add(str(relative_path))
        for part in relative_path.parts:
            part_path = Path(part)
            terms.add(part)
            terms.add(part_path.stem)
    return {term for term in terms if len(term) >= 4 and not term.startswith("<private>")}


def _report_file_label(file_path: Path, target: Path) -> str:
    if target.is_file():
        return target.name
    try:
        return str(file_path.relative_to(target))
    except ValueError:
        return file_path.name
