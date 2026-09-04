"""Shared native binding constants."""

from __future__ import annotations

NATIVE_INSTALL_HINT = "wolfppt_native is not installed; run uv run maturin develop --manifest-path crates/wolfppt-py/Cargo.toml"

try:
    import wolfppt_native  # type: ignore[import-not-found]  # noqa: F401
except ImportError:
    try:
        from wolfppt import wolfppt_native as _native  # type: ignore[attr-defined]
        import sys
        sys.modules.setdefault("wolfppt_native", _native)
    except ImportError:
        pass
