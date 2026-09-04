"""Runtime helpers for benchmark execution."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from time import perf_counter

try:  # pragma: no cover - Windows fallback
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]


def python_pptx_available() -> bool:
    return importlib.util.find_spec("pptx") is not None


def always_available() -> bool:
    return True


def elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


def max_rss_mb() -> float | None:
    if resource is None:
        return None
    usage = resource.getrusage(resource.RUSAGE_SELF)
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return round(usage.ru_maxrss / divisor, 3)


def stamp() -> str:
    return datetime.now(UTC).strftime("%H%M%S%f")
