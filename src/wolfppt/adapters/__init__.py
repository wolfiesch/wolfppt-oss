"""Optional external tool adapters."""

from __future__ import annotations

__all__ = ["ToolInfo", "available_tools"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    from .base import ToolInfo, available_tools

    return {"ToolInfo": ToolInfo, "available_tools": available_tools}[name]
