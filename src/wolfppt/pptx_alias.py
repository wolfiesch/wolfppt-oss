"""Opt in to the implemented python-pptx import surface for this process.

Call ``install()`` before importing ``pptx``. Unknown namespaces fail to import;
no python-pptx installation is consulted as a fallback. This is process-wide,
so use a separate process when comparing WolfPPT with python-pptx.
"""

from __future__ import annotations

import _imp
import importlib
import sys
from importlib.machinery import ModuleSpec
from types import ModuleType

from wolfppt import Presentation, __version__

_MODULES = {
    suffix: f"wolfppt.{suffix}"
    for suffix in (
        "util",
        "enum.base",
        "enum.action",
        "enum.chart",
        "enum.dml",
        "enum.lang",
        "enum.shapes",
        "enum.text",
        "dml.color",
        "chart.data",
    )
}
_MODULES["opc.packuri"] = "wolfppt.packuri"
_MODULES["table"] = "wolfppt.table_facade"
_MODULES["text.text"] = "wolfppt.text_text"
_installed: dict[str, ModuleType] | None = None


def _package(name: str) -> ModuleType:
    package = ModuleType(name)
    package.__package__ = name
    package.__path__ = []
    package.__spec__ = ModuleSpec(name, loader=None, is_package=True)
    return package


def install() -> ModuleType:
    """Make subsequent supported ``pptx`` imports use WolfPPT.

    Refuse an already-imported python-pptx (including any submodule) rather
    than leave a mixture of implementations. Repeated installation is safe
    while every installed alias remains intact. No existing module is replaced.
    """
    global _installed

    aliases = {
        name: _package(name)
        for name in ("pptx", "pptx.enum", "pptx.dml", "pptx.chart", "pptx.opc", "pptx.text")
    }
    aliases["pptx"].Presentation = Presentation
    aliases["pptx"].__version__ = __version__
    aliases["pptx"].__all__ = ["Presentation", "__version__"]
    # Resolve implementations before taking the global import lock: waiting
    # for another thread's module lock while holding it could deadlock.
    for suffix, implementation in _MODULES.items():
        aliases[f"pptx.{suffix}"] = importlib.import_module(implementation)
    for name, module in aliases.items():
        parent, _, attribute = name.rpartition(".")
        if parent:
            setattr(aliases[parent], attribute, module)

    # Serialize with Python's imports as well as concurrent install() calls.
    _imp.acquire_lock()
    try:
        if _installed is not None:
            if all(sys.modules.get(name) is module for name, module in _installed.items()):
                return _installed["pptx"]
            raise ImportError(
                "WolfPPT's pptx aliases changed after installation; start a new process"
            )
        conflicts = sorted(
            name for name in sys.modules if name == "pptx" or name.startswith("pptx.")
        )
        if conflicts:
            raise ImportError(
                "Install WolfPPT's pptx alias before importing pptx; "
                f"already imported: {', '.join(conflicts)}"
            )
        sys.modules.update(aliases)
        _installed = aliases
        return aliases["pptx"]
    finally:
        _imp.release_lock()
