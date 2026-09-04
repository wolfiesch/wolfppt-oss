"""Input normalization for the presentation facade."""

from __future__ import annotations

from importlib.resources import files
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


def presentation_source_path(source: Any) -> tuple[Path, TemporaryDirectory[str] | None]:
    if source is None:
        return _default_presentation_source_path()
    if isinstance(source, (str, PathLike)):
        return Path(source), None
    if not hasattr(source, "read"):
        raise TypeError("presentation input must be a path or file-like object")

    snapshot_dir = TemporaryDirectory(prefix="wolfppt-source-")
    snapshot_path = Path(snapshot_dir.name) / "presentation.pptx"
    snapshot_path.write_bytes(_read_file_like_bytes(source))
    return snapshot_path, snapshot_dir


def _default_presentation_source_path() -> tuple[Path, TemporaryDirectory[str]]:
    snapshot_dir = TemporaryDirectory(prefix="wolfppt-default-")
    snapshot_path = Path(snapshot_dir.name) / "presentation.pptx"
    snapshot_path.write_bytes(
        files("wolfppt.templates").joinpath("blank.pptx").read_bytes()
    )
    return snapshot_path, snapshot_dir


def release_input_snapshot(presentation: Any, previous_source_path: Path) -> None:
    snapshot_dir = getattr(presentation, "_source_tempdir", None)
    if snapshot_dir is None:
        return
    if presentation.path.resolve() == previous_source_path.resolve():
        return
    snapshot_dir.cleanup()
    presentation._source_tempdir = None


def _read_file_like_bytes(file_like: Any) -> bytes:
    if callable(getattr(file_like, "seek", None)):
        file_like.seek(0)
    blob = file_like.read()
    if not isinstance(blob, bytes):
        raise TypeError("file-like read() must return bytes")
    return blob
