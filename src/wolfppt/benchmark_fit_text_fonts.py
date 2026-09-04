"""Font discovery helpers for fit_text benchmark lanes."""

from __future__ import annotations

from pathlib import Path

from .benchmark_cases import TEXT_FRAME_FIT_TEXT_FONT_FAMILIES

_FONT_FILE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "Arial": (
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    ),
    "DejaVu Sans": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/local/share/fonts/dejavu/DejaVuSans.ttf",
    ),
    "Liberation Sans": (
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ),
}


def find_fit_text_font() -> tuple[str, str]:
    """Return a font family and file path usable by python-pptx fit_text()."""
    fontfiles_error: Exception | None = None
    try:
        from pptx.text.fonts import FontFiles

        for family in TEXT_FRAME_FIT_TEXT_FONT_FAMILIES:
            try:
                return family, str(FontFiles.find(family, False, False))
            except Exception as exc:  # pragma: no cover - platform/font dependent.
                fontfiles_error = exc
    except Exception as exc:  # pragma: no cover - import/platform dependent.
        fontfiles_error = exc

    for family in TEXT_FRAME_FIT_TEXT_FONT_FAMILIES:
        for candidate in _FONT_FILE_CANDIDATES.get(family, ()):
            path = Path(candidate)
            if path.is_file():
                return family, str(path)

    detail = f": {fontfiles_error}" if fontfiles_error is not None else ""
    raise RuntimeError(
        "fit_text benchmark requires Arial, DejaVu Sans, or Liberation Sans"
        f" font file{detail}"
    )
