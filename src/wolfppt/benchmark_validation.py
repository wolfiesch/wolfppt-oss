"""Validation and round-trip detail helpers for benchmark runs."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from .compare import (
    DEFAULT_ROUNDTRIP_IGNORES,
    compare_semantics,
    semantic_mismatch_preview,
)
from .extractor import extract_semantics
from .package_diff import diff_packages

_OPENXML_VALIDATION_CACHE: dict[str, dict[str, Any]] = {}


def _roundtrip_details(
    fixture_id: str,
    fixture_path: Path,
    output_path: Path,
    validate_openxml: bool,
    *,
    require_package_clean: bool = False,
) -> dict[str, Any]:
    original_semantics = extract_semantics(fixture_path).to_dict()
    roundtrip_semantics = extract_semantics(output_path).to_dict()
    comparison = compare_semantics(
        fixture_id,
        original_semantics,
        roundtrip_semantics,
        ignore_paths=DEFAULT_ROUNDTRIP_IGNORES,
    )
    package_diff = diff_packages(fixture_path, output_path)
    validation = _validate_output(output_path) if validate_openxml else {"enabled": False}
    source_validation: dict[str, Any] | None = None
    source_invalid_preserved = False
    if validate_openxml and validation.get("valid") is False:
        source_validation = _validate_output(fixture_path)
        source_invalid_preserved = _source_invalid_preserved(source_validation, validation)
    openxml_ok = validation.get("valid") is not False or source_invalid_preserved
    ok = comparison.passed and openxml_ok and (package_diff.clean or not require_package_clean)
    return {
        "ok": ok,
        "semantic_pass": comparison.passed,
        "semantic_score": comparison.score,
        "mismatch_count": len(comparison.mismatches),
        "semantic_mismatches": semantic_mismatch_preview(comparison),
        "semantic_mismatch_preview_truncated": len(comparison.mismatches) > 3,
        "package_clean": package_diff.clean,
        "package_added_count": len(package_diff.added_parts),
        "package_changed_count": len(package_diff.changed_parts),
        "package_removed_count": len(package_diff.removed_parts),
        "openxml_valid": validation.get("valid"),
        "openxml_validation_accepted": openxml_ok,
        "openxml_source_invalid_preserved": source_invalid_preserved,
        "source_openxml_valid": source_validation.get("valid") if source_validation else None,
        "source_openxml_error_count": source_validation.get("error_count") if source_validation else None,
        "source_openxml_error_keys": _validation_error_keys(source_validation) if source_validation else [],
        "openxml_validation": validation,
    }


def _validate_output(output_path: Path) -> dict[str, Any]:
    from .adapters.openxml import validate as validate_openxml

    digest = _file_digest(output_path)
    cached = _OPENXML_VALIDATION_CACHE.get(digest)
    if cached is not None:
        validation = dict(cached)
        validation["path"] = str(output_path)
        validation["cache_hit"] = True
        return validation

    try:
        result = validate_openxml(output_path)
    except RuntimeError as exc:
        validation = {
            "enabled": True,
            "valid": None,
            "skipped": True,
            "reason": str(exc),
            "path": str(output_path),
        }
    else:
        validation = {"enabled": True, **result.to_dict()}
    validation["cache_hit"] = False
    _OPENXML_VALIDATION_CACHE[digest] = dict(validation)
    return validation


def _file_digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _source_invalid_preserved(source_validation: dict[str, Any], output_validation: dict[str, Any]) -> bool:
    if source_validation.get("valid") is not False or output_validation.get("valid") is not False:
        return False
    source_errors = _validation_error_keys(source_validation)
    output_errors = _validation_error_keys(output_validation)
    return bool(source_errors) and source_errors == output_errors


def _validation_error_keys(validation: dict[str, Any]) -> list[tuple[str | None, str | None]]:
    errors = validation.get("errors")
    if not isinstance(errors, list):
        return []
    keys: set[tuple[str | None, str | None]] = set()
    for error in errors:
        if not isinstance(error, dict):
            continue
        keys.add((error.get("part"), error.get("description")))
    return sorted(keys)
