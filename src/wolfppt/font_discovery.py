"""Find an installed font file for a family and style.

Geometric text fitting measures text with a real font file. A request may name
that file; when it does not, ``find_font_file`` picks the first installed face
whose name table reports exactly the requested family and style. Lookup order:
the ``WOLFPPT_FONT_DIRS`` directories (``os.pathsep`` separated), then the
platform's user and system font directories, each walked in sorted order. The
result therefore depends on the host's installed fonts; pass ``font_file`` to
pin one.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from functools import cache
from pathlib import Path

FONT_DIRS_ENV = "WOLFPPT_FONT_DIRS"
_FONT_SUFFIXES = frozenset({".ttf", ".otf", ".ttc"})
# Exact style names per (bold, italic), so a Light, Medium, or Semibold face never
# stands in for Regular or Bold.
_STYLE_NAMES = {
    (False, False): frozenset({"regular", "normal", "roman", "book"}),
    (True, False): frozenset({"bold"}),
    (False, True): frozenset({"italic", "oblique"}),
    (True, True): frozenset({"bolditalic", "boldoblique"}),
}


def find_font_file(family: str, bold: bool, italic: bool) -> str | None:
    """Return an installed font file for ``family`` in the given style, or None.

    Raises ImportError when Pillow, which reads font name tables, is missing.
    """
    from PIL import ImageFont  # noqa: F401  # fail loudly instead of "not found"

    return _find_font_file(_normalized(family), bold, italic, font_directories())


def font_directories() -> tuple[Path, ...]:
    """Return the directories searched for fonts, highest priority first."""
    configured = os.environ.get(FONT_DIRS_ENV, "")
    directories = [Path(item).expanduser() for item in configured.split(os.pathsep) if item]
    try:
        home: Path | None = Path.home()
    except RuntimeError:
        home = None
    if sys.platform == "darwin":
        if home is not None:
            directories.append(home / "Library" / "Fonts")
        directories += [
            Path("/Library/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/Network/Library/Fonts"),
        ]
    elif sys.platform == "win32":
        directories.append(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            directories.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    else:
        data_home = os.environ.get("XDG_DATA_HOME")
        if data_home:
            directories.append(Path(data_home) / "fonts")
        elif home is not None:
            directories.append(home / ".local" / "share" / "fonts")
        if home is not None:
            directories.append(home / ".fonts")
        data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
        directories += [Path(item) / "fonts" for item in data_dirs.split(":") if item]
    return tuple(dict.fromkeys(directories))


# Found files only: a long-running process sees a font installed after a refusal.
_FOUND: dict[tuple[str, bool, bool, tuple[Path, ...]], str] = {}


def _find_font_file(
    family: str, bold: bool, italic: bool, directories: tuple[Path, ...]
) -> str | None:
    key = (family, bold, italic, directories)
    if key in _FOUND:
        return _FOUND[key]
    styles = _STYLE_NAMES[(bold, italic)]
    for path in _font_files(directories):
        face = _face_name(path)
        if face is not None and _normalized(face[0]) == family and _normalized(face[1]) in styles:
            _FOUND[key] = str(path)
            return _FOUND[key]
    return None


def _font_files(directories: tuple[Path, ...]) -> Iterator[Path]:
    seen: set[Path] = set()
    for directory in directories:
        for root, dirnames, filenames in os.walk(directory):
            dirnames.sort()
            for filename in sorted(filenames):
                path = Path(root) / filename
                if path.suffix.lower() not in _FONT_SUFFIXES:
                    continue
                identity = path.resolve()
                if identity not in seen:
                    seen.add(identity)
                    yield path


@cache
def _face_name(path: Path) -> tuple[str, str] | None:
    """Return the (family, style) of the file's first face; measurement uses face 0."""
    from PIL import ImageFont

    try:
        family, style = ImageFont.truetype(str(path), 12).getname()
    except Exception:
        return None
    if not family or not style:
        return None
    return family, style


def _normalized(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())
