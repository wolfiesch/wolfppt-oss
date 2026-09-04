"""Load the compatibility spec from docs without making docs a package."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "docs" / "compatibility" / "_compat_spec.py"


def load_spec_module(path: Path = SPEC_PATH) -> ModuleType:
    spec = importlib.util.spec_from_file_location("wolfppt_compat_spec", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load compatibility spec from {path}")
    module = importlib.util.module_from_spec(spec)
    spec_dir = str(path.resolve().parent)
    sys.path.insert(0, spec_dir)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(spec_dir)
    return module


def load_entries() -> list[dict[str, Any]]:
    module = load_spec_module()
    return list(module.ENTRIES)


def load_categories() -> list[dict[str, str]]:
    module = load_spec_module()
    return list(module.CATEGORIES)
