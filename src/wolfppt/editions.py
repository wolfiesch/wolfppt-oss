"""Community and commercial edition boundary.

The Community wheel ships the editor: open, edit, and save PowerPoint packages.
Rendering, reporting refresh, deck assembly, and legacy or alternate formats
ship only in the commercial build. Community code reaches those modules through
:func:`commercial_module`, so a Community install refuses them with one typed
error instead of an ``ImportError`` from deep inside a call.

The commercial modules reach a Community install as the separate ``wolfppt-pro``
add-on, which installs the ``wolfppt_pro`` package beside the MIT ``wolfppt``
and no file under ``wolfppt/``. The private full build keeps the same modules
inside ``wolfppt`` itself, so both layouts resolve through the same call.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

# Import package of the ``wolfppt-pro`` add-on that carries the commercial modules.
PRO_PACKAGE = "wolfppt_pro"


class CommercialFeatureError(RuntimeError):
    """Raised when a feature needs a module that only the commercial build ships."""

    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(
            f"{feature} requires the WolfPPT commercial edition, "
            "which this installation does not include"
        )


def _import_if_present(qualified: str, *, roots: tuple[str, ...]) -> ModuleType | None:
    """Import ``qualified``, or return ``None`` when the module or its package is absent.

    ``roots`` lists the names whose absence means "not installed here". Any other
    ``ModuleNotFoundError`` comes from inside a present module and is re-raised.
    """
    try:
        return importlib.import_module(qualified)
    except ModuleNotFoundError as exc:
        if exc.name not in (qualified, *roots):
            raise
        return None


def commercial_module(name: str, feature: str) -> ModuleType:
    """Import a commercial module, refusing with :class:`CommercialFeatureError` if absent.

    ``wolfppt.<name>`` is tried first, which is where the private full build keeps
    the module. If that module is absent, ``wolfppt_pro.<name>`` from the
    ``wolfppt-pro`` add-on is tried. Only a module's own absence is translated. A
    missing dependency inside a present module still raises its original
    ``ModuleNotFoundError``.
    """
    module = _import_if_present(f"{__package__}.{name}", roots=())
    if module is None:
        module = _import_if_present(f"{PRO_PACKAGE}.{name}", roots=(PRO_PACKAGE,))
    if module is None:
        raise CommercialFeatureError(feature)
    return module


def assemble_main(argv: list[str] | None = None) -> int:
    """Console entry point for ``wolfppt-assemble`` in every edition.

    The command is installed everywhere so a Community install explains the
    missing feature instead of failing to resolve its entry point.
    """
    try:
        assembly = commercial_module("assembly", "Deck assembly")
    except CommercialFeatureError as error:
        print(error, file=sys.stderr)
        return 2
    return assembly.main(argv)
