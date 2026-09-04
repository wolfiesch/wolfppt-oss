"""Helpers for path and file-like binary inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InMemoryFile:
    blob: bytes
    filename: str | None = None

    @property
    def display_filename(self) -> str:
        return Path(self.filename or "file.bin").name

    def materialize(self, directory: Path, stem: str | None = None) -> Path:
        if stem is None:
            target = directory / self.display_filename
        else:
            suffix = Path(self.display_filename).suffix or ".bin"
            target = directory / f"{stem}{suffix}"
        target.write_bytes(self.blob)
        return target


@dataclass(frozen=True)
class InMemoryImage(InMemoryFile):
    @property
    def display_filename(self) -> str:
        if self.filename:
            return Path(self.filename).name
        return f"image.{image_extension_from_blob(self.blob)}"


def image_source_for_queue(image_file: Any) -> str | Path | InMemoryImage:
    if isinstance(image_file, (str, Path)):
        return image_file
    return InMemoryImage(_read_file_like_bytes(image_file))


def binary_source_for_queue(
    binary_file: Any,
    default_filename: str,
) -> str | Path | InMemoryFile:
    if isinstance(binary_file, (str, Path)):
        return binary_file
    return InMemoryFile(_read_file_like_bytes(binary_file), default_filename)


def movie_source_for_queue(
    movie_file: Any,
    mime_type: str,
) -> str | Path | InMemoryFile:
    return binary_source_for_queue(movie_file, f"movie.{video_extension(mime_type)}")


def image_input_bytes(image_file: Any) -> bytes:
    if isinstance(image_file, InMemoryFile):
        return image_file.blob
    if isinstance(image_file, (str, Path)):
        return Path(image_file).read_bytes()
    return _read_file_like_bytes(image_file)


def image_input_filename(image_file: Any) -> str | None:
    if isinstance(image_file, InMemoryFile):
        return image_file.display_filename
    if isinstance(image_file, (str, Path)):
        return Path(image_file).name
    return None


def source_display_filename(source: Any) -> str:
    if isinstance(source, InMemoryFile):
        return source.display_filename
    return Path(source).name


def video_extension(mime_type: str | None) -> str:
    return {
        "video/x-ms-asf": "asf",
        "video/avi": "avi",
        "video/quicktime": "mov",
        "video/mp4": "mp4",
        "video/mpeg": "mpg",
        "video/msvideo": "avi",
        "application/x-shockwave-flash": "swf",
        "video/x-ms-wmv": "wmv",
        "video/x-msvideo": "avi",
    }.get(str(mime_type or "video/unknown"), "vid")


def image_extension_from_blob(blob: bytes) -> str:
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if blob.startswith(b"\xff\xd8"):
        return "jpg"
    if blob.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if blob.startswith(b"BM"):
        return "bmp"
    if blob.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    raise ValueError("unsupported image format")


def _read_file_like_bytes(file_like: Any) -> bytes:
    if not hasattr(file_like, "read"):
        raise TypeError("input must be a path or file-like object")
    if callable(getattr(file_like, "seek", None)):
        file_like.seek(0)
    blob = file_like.read()
    if not isinstance(blob, bytes):
        raise TypeError("file-like read() must return bytes")
    return blob
