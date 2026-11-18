"""Import JSON and PNG pages as an image-only deck, without reading PDF bytes.

Contract: WolfSuite docs/pdf-to-office-decision.md sections 5, 6 and 7.3.
``pages_to_pptx(manifest, output)`` resolves images relative to the manifest,
validates every page before authoring, and returns a JSON-ready tier-a receipt.
The first page sets the deck size; different aspect ratios are centered and
reported as ``page_size_mismatch`` omissions. Extreme ratios that cannot fit
both OOXML side limits under uniform scaling are refused.

Admission bounds: 8 MiB JSON, 512 pages, 64 MiB per PNG, 100 million pixels
per PNG, and 128 MiB combined PNG bytes. Images are embedded unrecompressed.
Existing output files are never overwritten; publication is atomic.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from .image_dimensions import image_size_and_dpi

EMU_PER_POINT = 12_700
MIN_SIDE_EMU = 914_400
MAX_SIDE_EMU = 51_206_400
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_PAGES = 512
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000
MAX_TOTAL_IMAGE_BYTES = 128 * 1024 * 1024
_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


class PageImportRefusal(ValueError):
    """A typed refusal, with a stable code and optional source page number."""

    def __init__(self, code: str, message: str, *, page: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.page = page

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": type(self).__name__,
            "code": self.code,
            "message": str(self),
            "page": self.page,
        }


@dataclass(frozen=True)
class _Page:
    number: int
    width: Fraction
    height: Fraction
    image: bytes


def _bounded_read(path: Path, limit: int, *, code: str, page: int | None = None) -> bytes:
    try:
        with path.open("rb") as handle:
            payload = handle.read(limit + 1)
    except OSError as exc:
        raise PageImportRefusal(code, "input file is missing or unreadable", page=page) from exc
    if len(payload) > limit:
        raise PageImportRefusal("input_limit", "input exceeds its byte limit", page=page)
    return payload


def _points(value: Any) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PageImportRefusal(
            "manifest_invalid", "page dimensions must be positive finite numbers"
        )
    if value <= 0 or (isinstance(value, float) and not math.isfinite(value)):
        raise PageImportRefusal(
            "manifest_invalid", "page dimensions must be positive finite numbers"
        )
    return Fraction(str(value))


def _validate_png(payload: bytes, page: int) -> None:
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PageImportRefusal("image_not_png", "page image must be PNG", page=page)
    try:
        width, height, _, _ = image_size_and_dpi(payload)
    except ValueError as exc:
        raise PageImportRefusal("image_invalid", "invalid PNG header", page=page) from exc
    if width <= 0 or height <= 0:
        raise PageImportRefusal("image_invalid", "PNG dimensions must be positive", page=page)
    if width * height > MAX_IMAGE_PIXELS:
        raise PageImportRefusal("input_limit", "PNG exceeds the pixel limit", page=page)
    # Check the whole container, not only its signature: truncated or corrupt
    # rasterizer output must never become an unreadable picture in a valid deck.
    offset = 8
    has_data = False
    while offset + 12 <= len(payload):
        length = int.from_bytes(payload[offset : offset + 4], "big")
        end = offset + 12 + length
        kind = payload[offset + 4 : offset + 8]
        if end > len(payload) or zlib.crc32(payload[offset + 4 : end - 4]) != int.from_bytes(
            payload[end - 4 : end], "big"
        ):
            break
        if offset == 8 and (kind != b"IHDR" or length != 13):
            break
        has_data |= kind == b"IDAT"
        if kind == b"IEND":
            if length == 0 and end == len(payload) and has_data:
                return
            break
        offset = end
    raise PageImportRefusal(
        "image_invalid", "PNG has a truncated or corrupt chunk stream", page=page
    )


def _load_pages(manifest: Path) -> tuple[str, list[_Page]]:
    raw = _bounded_read(manifest, MAX_MANIFEST_BYTES, code="manifest_unreadable")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PageImportRefusal("manifest_invalid", "manifest is not valid JSON") from exc
    if not isinstance(data, dict) or data.get("schema") != "wolfsuite.pdf-pages.v1":
        raise PageImportRefusal("manifest_invalid", "expected wolfsuite.pdf-pages.v1")
    digest = data.get("source_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise PageImportRefusal(
            "manifest_invalid", "source_sha256 must be a lowercase SHA-256 digest"
        )
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        raise PageImportRefusal("manifest_invalid", "manifest must contain at least one page")
    if len(pages) > MAX_PAGES:
        raise PageImportRefusal("input_limit", "manifest exceeds the page limit")
    result = []
    previous = 0
    total = 0
    for page in pages:
        if not isinstance(page, dict):
            raise PageImportRefusal("manifest_invalid", "each page must be an object")
        number = page.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number <= previous:
            raise PageImportRefusal(
                "manifest_invalid",
                "page numbers must be positive and strictly increasing",
            )
        previous = number
        width, height = _points(page.get("width_pt")), _points(page.get("height_pt"))
        image = page.get("image")
        if not isinstance(image, str) or not image or "\x00" in image:
            raise PageImportRefusal(
                "manifest_invalid", "image must be a non-empty file path", page=number
            )
        payload = _bounded_read(
            manifest.parent / image,
            MAX_IMAGE_BYTES,
            code="image_unreadable",
            page=number,
        )
        _validate_png(payload, number)
        total += len(payload)
        if total > MAX_TOTAL_IMAGE_BYTES:
            raise PageImportRefusal(
                "input_limit", "pages exceed the combined image byte limit", page=number
            )
        result.append(_Page(number, width, height, payload))
    return digest, result


def _deck_size(page: _Page) -> tuple[int, int]:
    width, height = page.width * EMU_PER_POINT, page.height * EMU_PER_POINT
    lower = max(MIN_SIDE_EMU / width, MIN_SIDE_EMU / height)
    upper = min(MAX_SIDE_EMU / width, MAX_SIDE_EMU / height)
    if lower > upper:
        raise PageImportRefusal(
            "page_size_unrepresentable",
            "page aspect ratio cannot fit OOXML slide limits",
            page=page.number,
        )
    scale = min(max(Fraction(1), lower), upper)
    return round(width * scale), round(height * scale)


def pages_to_pptx(manifest: str | Path, output: str | Path) -> dict[str, Any]:
    """Write one picture slide per manifest page and return its import receipt."""
    from .presentation import Presentation

    manifest, output = Path(manifest), Path(output)
    source_sha256, pages = _load_pages(manifest)
    width, height = _deck_size(pages[0])
    if output.exists() or output.is_symlink():
        raise PageImportRefusal("output_exists", "output already exists")
    if not output.parent.is_dir():
        raise PageImportRefusal("output_unwritable", "output directory does not exist")
    omissions = []
    # Use native authoring and private snapshots; no image is reopened after
    # validation, and a later-page refusal never leaves a partial output.
    with tempfile.TemporaryDirectory(prefix="wolfppt-pages-") as workspace:
        authored = Path(workspace) / "authored.pptx"
        presentation = Presentation()
        try:
            presentation.slide_width = width
            presentation.slide_height = height
            for index, page in enumerate(pages):
                scale = min(width / page.width, height / page.height)
                cx, cy = (
                    max(1, round(page.width * scale)),
                    max(1, round(page.height * scale)),
                )
                slide = presentation.slides.add_slide(presentation.slide_layouts[6])
                slide.shapes.add_picture(
                    io.BytesIO(page.image),
                    (width - cx) // 2,
                    (height - cy) // 2,
                    cx,
                    cy,
                )
                if page.width * pages[0].height != pages[0].width * page.height:
                    omissions.append(
                        {
                            "kind": "page_size_mismatch",
                            "page": page.number,
                            "slide": index + 1,
                        }
                    )
            presentation.save(authored)
        finally:
            presentation.dispose()
        with tempfile.TemporaryDirectory(prefix=".wolfppt-pages-", dir=output.parent) as staging:
            staged = Path(staging) / "deck.pptx"
            with (
                zipfile.ZipFile(authored) as source,
                zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as target,
            ):
                for name in sorted(source.namelist()):
                    payload = source.read(name)
                    match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name)
                    if match:
                        page = pages[int(match[1]) - 1]
                        root = ET.fromstring(payload)
                        props = root.find(
                            f"{{{_P_NS}}}cSld/{{{_P_NS}}}spTree/{{{_P_NS}}}pic/{{{_P_NS}}}nvPicPr/{{{_P_NS}}}cNvPr"
                        )
                        if props is None:
                            raise PageImportRefusal(
                                "authoring_failed",
                                "native authoring omitted the page picture",
                                page=page.number,
                            )
                        props.set("descr", f"Source page {page.number}")
                        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                    entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    target.writestr(entry, payload)
            try:
                os.link(staged, output)
            except FileExistsError as exc:
                raise PageImportRefusal("output_exists", "output already exists") from exc
            except OSError as exc:
                raise PageImportRefusal("output_unwritable", "could not publish output") from exc
    return {
        "status": "ok",
        "output": str(output),
        "source_sha256": source_sha256,
        "tier": "a",
        "image_only": True,
        "slide_count": len(pages),
        "slide_size_emu": {"width": width, "height": height},
        "omissions": omissions,
    }
