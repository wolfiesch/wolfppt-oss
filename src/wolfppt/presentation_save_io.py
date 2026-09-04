"""Low-level output helpers for presentation saves."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Any

from .core_properties import (
    CORE_PROPERTIES_PARTNAME as _CORE_PROPERTIES_PARTNAME,
    serialize_core_properties as _serialize_core_properties,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)


def is_file_like_output(value: Any) -> bool:
    return not isinstance(value, (str, bytes, PathLike)) and hasattr(value, "write")


def write_path_to_file_like(source_path: Path, output: Any) -> None:
    output.write(source_path.read_bytes())


def apply_core_properties_edits(
    input_path: Path,
    output_path: Path,
    values: dict[str, Any],
) -> None:
    _copy_package_with_replacements(
        input_path,
        output_path,
        {_CORE_PROPERTIES_PARTNAME: _serialize_core_properties(values)},
    )
