"""Input normalization for the presentation facade."""

from __future__ import annotations

from importlib.resources import files
from io import BytesIO
from os import PathLike
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZipFile

from .editions import commercial_module
from .package_limits import (
    PPTX_PACKAGE_LIMITS,
    _xml_part_refusal,
    _zip_entries_refusal,
)
from .package_parts import InMemoryPackageSource, open_package_source
from .package_read_scope import release_shared_package
from .presentation_formats import has_cfbf_signature, is_odp_package
from .presentation_package_validation import (
    PresentationPackageError,
    validate_presentation_package,
)


def presentation_source_path(
    source: Any,
    *,
    no_disk: bool = False,
) -> tuple[Path | InMemoryPackageSource, TemporaryDirectory[str] | None]:
    """Normalize a presentation input.

    ``no_disk=True`` accepts a seekable binary stream, snapshots bytes from
    offset zero through EOF, then restores the caller's original position.
    The stream is never closed and the snapshot is retained only in memory.
    """
    if no_disk:
        if source is None or isinstance(source, (str, PathLike)):
            raise TypeError("no-disk presentation input must be a file-like object")
        package = InMemoryPackageSource(_read_no_disk_file_like_bytes(source))
        try:
            _validate_package_limits(package)
            validate_presentation_package(package)
        except Exception:
            package.dispose()
            raise
        return package, None
    if source is None:
        return _default_presentation_source_path()
    if isinstance(source, (str, PathLike)):
        return _normalized_path_source(Path(source))
    if not hasattr(source, "read"):
        raise TypeError("presentation input must be a path or file-like object")

    snapshot_dir = TemporaryDirectory(prefix="wolfppt-source-")
    snapshot_path = Path(snapshot_dir.name) / "presentation.pptx"
    try:
        snapshot_path.write_bytes(_read_file_like_bytes(source))
        return _normalized_path_source(snapshot_path, snapshot_dir)
    except Exception:
        release_shared_package(snapshot_path)
        snapshot_dir.cleanup()
        raise


def _normalized_path_source(
    path: Path,
    snapshot_dir: TemporaryDirectory[str] | None = None,
) -> tuple[Path, TemporaryDirectory[str] | None]:
    if not has_cfbf_signature(path):
        # ODP input is validated and converted by Presentation.__init__.
        # Keep that format-specific refusal path rather than treating ODP as OPC.
        if not is_odp_package(path):
            _validate_package_limits(path)
            validate_presentation_package(path)
        return path, snapshot_dir
    binary_ppt = commercial_module("binary_ppt", "Opening a binary .ppt presentation")
    workspace = snapshot_dir or TemporaryDirectory(prefix="wolfppt-binary-ppt-")
    converted = Path(workspace.name) / "presentation.pptx"
    try:
        binary_ppt.load_binary_ppt_as_pptx(path, converted)
        _validate_package_limits(converted)
        validate_presentation_package(converted)
    except Exception:
        if snapshot_dir is None:
            release_shared_package(converted)
            workspace.cleanup()
        raise
    return converted, workspace


def _validate_package_limits(source: Path | InMemoryPackageSource) -> None:
    """Refuse hostile package bounds before constructing any facade state."""
    limits = PPTX_PACKAGE_LIMITS
    size = source.stat().st_size if isinstance(source, Path) else len(source.read_bytes())
    if size > limits.max_archive_size:
        raise PresentationPackageError(
            f"archive_size_limit: requested {size}, "
            f"limit {limits.max_archive_size}. Shrink the presentation archive."
        )
    with open_package_source(source) as package:
        refusal = _zip_entries_refusal(package.infolist(), limits)
        if refusal is not None:
            # Keep established public ZIP-format error types for sibling callers.
            if refusal.code == "zip_encrypted":
                raise RuntimeError("ZIP member is encrypted")
            if refusal.code == "zip_compression_unsupported":
                raise NotImplementedError(refusal.recovery)
            raise PresentationPackageError(f"{refusal.code}: {refusal.recovery}")
        _validate_package_xml_limits(package)


def _validate_package_xml_limits(package: ZipFile) -> None:
    for info in package.infolist():
        if info.is_dir() or not info.filename.lower().endswith((".xml", ".rels")):
            continue
        with package.open(info) as member:
            refusal = _xml_part_refusal(member, PPTX_PACKAGE_LIMITS, size=info.file_size)
        if refusal is not None:
            raise PresentationPackageError(
                f"{refusal.code}: part {info.filename!r}: {refusal.recovery}"
            )


def _default_presentation_source_path() -> tuple[Path, TemporaryDirectory[str]]:
    snapshot_dir = TemporaryDirectory(prefix="wolfppt-default-")
    snapshot_path = Path(snapshot_dir.name) / "presentation.pptx"
    try:
        snapshot_path.write_bytes(files("wolfppt.templates").joinpath("blank.pptx").read_bytes())
        validate_presentation_package(snapshot_path)
    except Exception:
        release_shared_package(snapshot_path)
        snapshot_dir.cleanup()
        raise
    return snapshot_path, snapshot_dir


def release_input_snapshot(presentation: Any, previous_source_path: Path) -> None:
    snapshot_dir = getattr(presentation, "_source_tempdir", None)
    if snapshot_dir is None:
        return
    if presentation.path.resolve() == previous_source_path.resolve():
        return
    snapshot_dir.cleanup()
    presentation._source_tempdir = None


def _stream_position(file_like: Any) -> int | None:
    """Return the current offset of a seekable stream, or None if it cannot seek."""
    seekable = getattr(file_like, "seekable", None)
    if callable(seekable) and not seekable():
        return None
    if not callable(getattr(file_like, "seek", None)) or not callable(
        getattr(file_like, "tell", None)
    ):
        return None
    try:
        return file_like.tell()
    except (OSError, ValueError):
        return None


def _read_bounded_bytes(file_like: Any) -> bytes:
    limit = PPTX_PACKAGE_LIMITS.max_archive_size
    with BytesIO() as snapshot:
        size = 0
        while True:
            chunk = file_like.read(min(65536, limit + 1 - size))
            if not isinstance(chunk, bytes):
                raise TypeError("file-like read() must return bytes")
            size += len(chunk)
            if size > limit:
                raise PresentationPackageError(
                    f"archive_size_limit: requested at least {size}, "
                    f"limit {limit}. Shrink the presentation archive."
                )
            if not chunk:
                return snapshot.getvalue()
            snapshot.write(chunk)


def _read_from_start(file_like: Any, original_position: int) -> bytes:
    try:
        file_like.seek(0)
        return _read_bounded_bytes(file_like)
    finally:
        file_like.seek(original_position)


def _read_file_like_bytes(file_like: Any) -> bytes:
    original_position = _stream_position(file_like)
    if original_position is not None:
        return _read_from_start(file_like, original_position)
    return _read_bounded_bytes(file_like)


def _read_no_disk_file_like_bytes(file_like: Any) -> bytes:
    original_position = _stream_position(file_like)
    if original_position is None:
        raise TypeError("no-disk presentation input must be a seekable binary stream")
    return _read_from_start(file_like, original_position)
