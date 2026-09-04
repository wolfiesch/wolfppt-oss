"""Fixture source helpers for media drop-in benchmarks."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from .benchmark_runtime import stamp as _stamp


def _dropin_add_picture_source_image(
    fixture_id: str,
    fixture_path: Path,
    tmp_path: Path,
) -> Path:
    image_path = tmp_path / f"dropin-picture-{_stamp()}.png"
    fixture_root = fixture_path
    for _ in Path(fixture_id).parts:
        fixture_root = fixture_root.parent
    with ZipFile(fixture_root / "media" / "png_picture.pptx") as package:
        image_path.write_bytes(package.read("ppt/media/image1.png"))
    return image_path


def _dropin_replace_picture_source_image(
    fixture_id: str,
    fixture_path: Path,
    tmp_path: Path,
) -> Path:
    image_path = _dropin_add_picture_source_image(fixture_id, fixture_path, tmp_path)
    image_path.write_bytes(image_path.read_bytes() + b"replacement")
    return image_path


def _dropin_add_movie_sources(
    fixture_id: str,
    fixture_path: Path,
    tmp_path: Path,
) -> tuple[Path, Path]:
    movie_path = tmp_path / f"dropin-movie-{_stamp()}.mp4"
    movie_path.write_bytes(b"wolfppt benchmark movie bytes")
    poster_path = _dropin_add_picture_source_image(fixture_id, fixture_path, tmp_path)
    return movie_path, poster_path


def _dropin_add_ole_object_sources(
    fixture_id: str,
    fixture_path: Path,
    tmp_path: Path,
) -> tuple[Path, Path]:
    embedded_path = tmp_path / f"dropin-object-{_stamp()}.bin"
    embedded_path.write_bytes(b"wolfppt benchmark embedded object bytes")
    icon_path = _dropin_add_picture_source_image(fixture_id, fixture_path, tmp_path)
    return embedded_path, icon_path
