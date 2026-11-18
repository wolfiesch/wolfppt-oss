"""The refusal type every built-in renderer module raises.

The renderer never approximates: an unsupported shape, an unresolved font, a
colour it cannot resolve, text that does not fit, or a package asset it cannot
read is refused with an explicit reason before any output is published.  A
caller that wants one ``except`` clause catches :class:`RenderRefusal`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from .results import (
    LoadSaveWarning,
    LoadSaveWarningRefusal,
    WarningCategory,
    observe_warnings,
)


class RenderRefusal(ValueError):
    """Raised when the built-in renderer refuses a deck or a render request."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.diagnostic = LoadSaveWarning("render", "unsupported_feature", message)


def render_with_diagnostics(options: Any, operation: Any, refusal_type: Any) -> Any:
    """Retain named hard refusals even when a caller approves the diagnostic."""
    callback = options.diagnostic_callback
    if callback is not None and not callable(callback):
        raise LoadSaveWarningRefusal("callback_unsupported", "diagnostic_callback must be callable")
    try:
        return operation(options)
    except RenderRefusal as exc:
        observe_warnings([exc.diagnostic], callback, require_decision=False)
        if isinstance(exc, refusal_type):
            raise
        raise refusal_type(str(exc)) from exc


class RenderDiagnostics:
    """Collect typed receipts alongside the existing string warning observer."""

    def __init__(self, options: Any) -> None:
        self.options = options
        self.messages: list[str] = []
        self.warnings: list[LoadSaveWarning] = []

    def font_warning(self, message: str) -> None:
        self._add(message, WarningCategory.FONT_SUBSTITUTION, "font_substitution", None)

    def omission(self, message: str, part: str) -> None:
        self._add(message, WarningCategory.UNSUPPORTED_FEATURE, "unsupported_feature", part)

    def _add(self, message: str, category: WarningCategory, code: str, part: str | None) -> None:
        warning = LoadSaveWarning("render", code, message, part, category)
        if warning in self.warnings:
            return
        self.warnings.append(warning)
        observe_warnings(
            self.warnings[-1:], self.options.diagnostic_callback, require_decision=False
        )
        if message not in self.messages:
            self.messages.append(message)
            callback = getattr(self.options, "warning_callback", None)
            if callback is not None:
                callback(message)

    def receipt(self, receipt: dict[str, Any]) -> None:
        if self.warnings:
            receipt["diagnostics"] = [warning.row() for warning in self.warnings]


class MissingFontRefusal(RenderRefusal):
    """Raised when text requires a font that was not admitted.

    ``RefusalLog`` records these separately so a diagnostic caller can report
    every missing font as a finding instead of refusing the whole deck.
    """

    def __init__(
        self,
        message: str = "",
        *,
        family: str = "",
        bold: bool = False,
        italic: bool = False,
        style: str = "regular",
    ) -> None:
        super().__init__(message)
        self.family = family
        self.bold = bold
        self.italic = italic
        self.style = style


@dataclass(frozen=True)
class MissingFontEvent:
    """One occurrence where text required a font asset that was not admitted."""

    family: str
    bold: bool
    italic: bool
    style: str
    message: str


def _find_missing_font(exc: BaseException | None) -> MissingFontRefusal | None:
    if exc is None:
        return None
    visited: set[int] = set()
    stack = [exc]
    while stack:
        current = stack.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, MissingFontRefusal):
            return current
        if current.__cause__ is not None:
            stack.append(current.__cause__)
        if current.__context__ is not None:
            stack.append(current.__context__)
    return None


class RefusalLog:
    """Collects refusal reasons so one render reports every problem at once.

    The renderer refuses rather than omits, but it refuses after inspecting the
    whole deck: a caller sees every unsupported object before deciding what to
    do, instead of fixing one problem to discover the next.
    """

    def __init__(self, limit: int = 20) -> None:
        self._entries: list[str] = []
        self._limit = limit
        self._count = 0
        self._missing_fonts: list[MissingFontEvent] = []
        self._all_entry_messages: list[str] = []

    def add(self, message: str) -> None:
        exc = sys.exc_info()[1]
        missing = _find_missing_font(exc)
        if missing is not None:
            self._missing_fonts.append(
                MissingFontEvent(
                    family=missing.family,
                    bold=missing.bold,
                    italic=missing.italic,
                    style=missing.style,
                    message=message,
                )
            )
            if len(self._all_entry_messages) < self._limit:
                self._all_entry_messages.append(message)
            return
        self._count += 1
        if len(self._entries) < self._limit:
            self._entries.append(message)
        if len(self._all_entry_messages) < self._limit:
            self._all_entry_messages.append(message)

    @property
    def count(self) -> int:
        return self._count

    @property
    def missing_fonts(self) -> tuple[MissingFontEvent, ...]:
        return tuple(self._missing_fonts)

    def entries(self) -> tuple[str, ...]:
        return tuple(self._entries)

    def __bool__(self) -> bool:
        return self._count > 0 or bool(self._missing_fonts)

    def raise_if_any(self, *, tolerate_missing_fonts: bool = False) -> None:
        """Raise one refusal describing every problem this log collected."""
        if tolerate_missing_fonts:
            if not self._count:
                return
            lines = list(self._entries)
            if self._count > len(lines):
                lines.append(f"... and {self._count - len(lines)} more")
            raise RenderRefusal(
                "the built-in renderer cannot render this deck exactly:\n  " + "\n  ".join(lines)
            )
        total = self._count + len(self._missing_fonts)
        if not total:
            return
        lines = list(self._all_entry_messages)
        if total > len(lines):
            lines.append(f"... and {total - len(lines)} more")
        raise RenderRefusal(
            "the built-in renderer cannot render this deck exactly:\n  " + "\n  ".join(lines)
        )
