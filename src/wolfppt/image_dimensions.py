"""Image dimension helpers for picture insertion."""

from __future__ import annotations

from typing import Any

from .image_inputs import image_input_bytes


def picture_dimensions(
    image_file: Any,
    width: Any,
    height: Any,
) -> tuple[int, int]:
    if width is not None and height is not None:
        return _coerce_emu(width, "width"), _coerce_emu(height, "height")
    native_width, native_height = image_native_size_emu(image_file)
    if width is None and height is None:
        return native_width, native_height
    if width is None:
        height_emu = _coerce_emu(height, "height")
        width_emu = int(round(height_emu * native_width / native_height))
        return width_emu, height_emu
    width_emu = _coerce_emu(width, "width")
    height_emu = int(round(width_emu * native_height / native_width))
    return width_emu, height_emu


def image_native_size_emu(image_file: Any) -> tuple[int, int]:
    data = image_input_bytes(image_file)
    pixel_width, pixel_height, dpi_x, dpi_y = image_size_and_dpi(data)
    width_emu = int(round(pixel_width * 914400 / dpi_x))
    height_emu = int(round(pixel_height * 914400 / dpi_y))
    if width_emu <= 0 or height_emu <= 0:
        raise ValueError("image native dimensions must be positive")
    return width_emu, height_emu


def image_size_and_dpi(data: bytes) -> tuple[int, int, float, float]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return _png_size_and_dpi(data)
    if data.startswith(b"\xff\xd8"):
        return _jpeg_size_and_dpi(data)
    if data.startswith((b"GIF87a", b"GIF89a")):
        width = int.from_bytes(data[6:8], "little")
        height = int.from_bytes(data[8:10], "little")
        return width, height, 72.0, 72.0
    if data.startswith(b"BM"):
        return _bmp_size_and_dpi(data)
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return _tiff_size_and_dpi(data)
    raise ValueError(
        "unsupported image format; expected PNG, JPEG, GIF, BMP, or TIFF"
    )


def _coerce_emu(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be an integer EMU value") from exc


def _png_size_and_dpi(data: bytes) -> tuple[int, int, float, float]:
    if len(data) < 33 or data[12:16] != b"IHDR":
        raise ValueError("invalid PNG image")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    dpi_x = dpi_y = 72.0
    offset = 8
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        if chunk_type == b"pHYs" and len(chunk_data) >= 9 and chunk_data[8] == 1:
            x_pixels_per_meter = int.from_bytes(chunk_data[0:4], "big")
            y_pixels_per_meter = int.from_bytes(chunk_data[4:8], "big")
            if x_pixels_per_meter > 0 and y_pixels_per_meter > 0:
                dpi_x = x_pixels_per_meter * 0.0254
                dpi_y = y_pixels_per_meter * 0.0254
        offset += 12 + length
    return width, height, dpi_x, dpi_y


def _jpeg_size_and_dpi(data: bytes) -> tuple[int, int, float, float]:
    dpi_x = dpi_y = 72.0
    width: int | None = None
    height: int | None = None
    offset = 2
    while offset + 4 <= len(data):
        while offset < len(data) and data[offset] != 0xFF:
            offset += 1
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset : offset + 2], "big")
        segment = data[offset + 2 : offset + length]
        if marker == 0xE0 and segment.startswith(b"JFIF\x00") and len(segment) >= 14:
            units = segment[7]
            x_density = int.from_bytes(segment[8:10], "big")
            y_density = int.from_bytes(segment[10:12], "big")
            if units == 1 and x_density > 0 and y_density > 0:
                dpi_x = float(x_density)
                dpi_y = float(y_density)
            elif units == 2 and x_density > 0 and y_density > 0:
                dpi_x = x_density * 2.54
                dpi_y = y_density * 2.54
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        } and len(segment) >= 7:
            height = int.from_bytes(segment[1:3], "big")
            width = int.from_bytes(segment[3:5], "big")
            break
        offset += length
    if width is None or height is None:
        raise ValueError("invalid JPEG image")
    return width, height, dpi_x, dpi_y


def _bmp_size_and_dpi(data: bytes) -> tuple[int, int, float, float]:
    if len(data) < 26:
        raise ValueError("invalid BMP image")
    header_size = int.from_bytes(data[14:18], "little")
    dpi_x = dpi_y = 72.0
    if header_size == 12:
        width = int.from_bytes(data[18:20], "little")
        height = int.from_bytes(data[20:22], "little")
    elif header_size >= 40 and len(data) >= 54:
        width = int.from_bytes(data[18:22], "little", signed=True)
        height = abs(int.from_bytes(data[22:26], "little", signed=True))
        x_pixels_per_meter = int.from_bytes(data[38:42], "little", signed=True)
        y_pixels_per_meter = int.from_bytes(data[42:46], "little", signed=True)
        if x_pixels_per_meter > 0 and y_pixels_per_meter > 0:
            dpi_x = float(round(x_pixels_per_meter * 0.0254))
            dpi_y = float(round(y_pixels_per_meter * 0.0254))
    else:
        raise ValueError("invalid BMP image")
    if width <= 0 or height <= 0:
        raise ValueError("invalid BMP image")
    return width, height, dpi_x, dpi_y


def _tiff_size_and_dpi(data: bytes) -> tuple[int, int, float, float]:
    if data.startswith(b"II*\x00"):
        byte_order = "little"
    elif data.startswith(b"MM\x00*"):
        byte_order = "big"
    else:
        raise ValueError("invalid TIFF image")
    if len(data) < 10:
        raise ValueError("invalid TIFF image")
    ifd_offset = int.from_bytes(data[4:8], byte_order)
    entries = _tiff_ifd_entries(data, ifd_offset, byte_order)
    width = _tiff_scalar_value(data, entries, 256, byte_order)
    height = _tiff_scalar_value(data, entries, 257, byte_order)
    if width is None or height is None or width <= 0 or height <= 0:
        raise ValueError("invalid TIFF image")
    dpi_x = _tiff_resolution(data, entries, 282, byte_order)
    dpi_y = _tiff_resolution(data, entries, 283, byte_order)
    if dpi_x is None or dpi_y is None:
        dpi_x = dpi_y = 1.0
    else:
        unit = _tiff_scalar_value(data, entries, 296, byte_order) or 2
        if unit == 3:
            dpi_x *= 2.54
            dpi_y *= 2.54
    return width, height, dpi_x, dpi_y


def _tiff_ifd_entries(
    data: bytes,
    offset: int,
    byte_order: str,
) -> dict[int, tuple[int, int, int]]:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError("invalid TIFF image")
    count = int.from_bytes(data[offset : offset + 2], byte_order)
    entries: dict[int, tuple[int, int, int]] = {}
    cursor = offset + 2
    for _ in range(count):
        if cursor + 12 > len(data):
            raise ValueError("invalid TIFF image")
        tag = int.from_bytes(data[cursor : cursor + 2], byte_order)
        value_type = int.from_bytes(data[cursor + 2 : cursor + 4], byte_order)
        value_count = int.from_bytes(data[cursor + 4 : cursor + 8], byte_order)
        value_or_offset = int.from_bytes(data[cursor + 8 : cursor + 12], byte_order)
        entries[tag] = (value_type, value_count, value_or_offset)
        cursor += 12
    return entries


def _tiff_scalar_value(
    data: bytes,
    entries: dict[int, tuple[int, int, int]],
    tag: int,
    byte_order: str,
) -> int | None:
    entry = entries.get(tag)
    if entry is None:
        return None
    value_type, value_count, value_or_offset = entry
    if value_count != 1:
        return None
    if value_type == 3:
        if byte_order == "little":
            return value_or_offset & 0xFFFF
        return value_or_offset >> 16
    if value_type == 4:
        return value_or_offset
    return None


def _tiff_resolution(
    data: bytes,
    entries: dict[int, tuple[int, int, int]],
    tag: int,
    byte_order: str,
) -> float | None:
    entry = entries.get(tag)
    if entry is None:
        return None
    value_type, value_count, value_offset = entry
    if value_type != 5 or value_count != 1 or value_offset + 8 > len(data):
        return None
    numerator = int.from_bytes(data[value_offset : value_offset + 4], byte_order)
    denominator = int.from_bytes(data[value_offset + 4 : value_offset + 8], byte_order)
    if numerator <= 0 or denominator <= 0:
        return None
    return numerator / denominator
