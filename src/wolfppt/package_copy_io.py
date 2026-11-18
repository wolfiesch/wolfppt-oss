"""Staged package output and lossless raw ZIP entry copying."""

from __future__ import annotations

import os
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from copy import copy
from pathlib import Path
from typing import BinaryIO


@contextmanager
def staged_package_output(output_path: Path) -> Iterator[BinaryIO]:
    """Publish a complete package atomically, removing staging on any failure."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, staged = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    try:
        with os.fdopen(descriptor, "w+b") as stream:
            yield stream
        os.replace(staged, output_path)
    finally:
        Path(staged).unlink(missing_ok=True)


def _raw_zip_entry_spans(source: zipfile.ZipFile) -> dict[int, int]:
    if source.fp is None:
        return {}
    try:
        central_directory_offset = source.start_dir
    except AttributeError:
        return {}
    infos = sorted(source.infolist(), key=lambda item: item.header_offset)
    spans: dict[int, int] = {}
    for index, item in enumerate(infos):
        next_offset = (
            infos[index + 1].header_offset
            if index + 1 < len(infos)
            else central_directory_offset
        )
        span = next_offset - item.header_offset
        if span > 0:
            spans[item.header_offset] = span
    return spans


def _copy_raw_zip_entry(
    source: zipfile.ZipFile,
    target: zipfile.ZipFile,
    item: zipfile.ZipInfo,
    raw_spans: dict[int, int],
) -> bool:
    span = raw_spans.get(item.header_offset)
    if span is None or source.fp is None or target.fp is None:
        return False

    copied = copy(item)

    target.fp.seek(target.start_dir)
    copied.header_offset = target.fp.tell()
    source.fp.seek(item.header_offset)
    remaining = span
    while remaining:
        chunk = source.fp.read(min(1024 * 1024, remaining))
        if not chunk:
            raise zipfile.BadZipFile(f"could not copy raw ZIP member {item.filename}")
        target.fp.write(chunk)
        remaining -= len(chunk)
    target.start_dir = target.fp.tell()
    target.filelist.append(copied)
    target.NameToInfo[copied.filename] = copied
    target._didModify = True
    return True
