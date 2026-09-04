"""WolfPPT compatibility harness."""

from __future__ import annotations

import sys

try:
    from . import wolfppt_native as _native  # type: ignore[attr-defined]
    sys.modules.setdefault("wolfppt_native", _native)
except ImportError:
    pass

from .extractor import extract_semantics
from .presentation import Presentation
__all__ = ["Presentation", "extract_semantics"]
