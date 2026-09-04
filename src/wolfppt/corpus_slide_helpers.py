"""Shared helpers for synthetic corpus slide builders."""

from __future__ import annotations

from io import BytesIO


def add_textbox(slide, text: str, left, top, width, height):
    shape = slide.shapes.add_textbox(left, top, width, height)
    shape.text = text
    return shape


def png_1x1() -> bytes:
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6360000002000100ffff03000006000557bfab00000000"
        "49454e44ae426082"
    )


def jpeg_2x3() -> bytes:
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (2, 3), (180, 30, 30)).save(output, "JPEG")
    return output.getvalue()


def bmp_2x3() -> bytes:
    width = 2
    height = 3
    row_stride = ((width * 3 + 3) // 4) * 4
    row = (b"\x1e\x78\xdc" * width).ljust(row_stride, b"\x00")
    pixels = row * height
    pixel_offset = 14 + 40
    file_size = pixel_offset + len(pixels)
    return (
        b"BM"
        + file_size.to_bytes(4, "little")
        + b"\x00\x00\x00\x00"
        + pixel_offset.to_bytes(4, "little")
        + (40).to_bytes(4, "little")
        + width.to_bytes(4, "little", signed=True)
        + height.to_bytes(4, "little", signed=True)
        + (1).to_bytes(2, "little")
        + (24).to_bytes(2, "little")
        + (0).to_bytes(4, "little")
        + len(pixels).to_bytes(4, "little")
        + (3780).to_bytes(4, "little", signed=True)
        + (3780).to_bytes(4, "little", signed=True)
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + pixels
    )


def tiff_2x3() -> bytes:
    width = 2
    height = 3
    ifd_offset = 8
    entry_count = 10
    bits_offset = ifd_offset + 2 + entry_count * 12 + 4
    image_offset = bits_offset + 6
    pixels = (b"\xdc\x78\x1e" * width) * height
    entries = [
        (256, 4, 1, width),
        (257, 4, 1, height),
        (258, 3, 3, bits_offset),
        (259, 3, 1, 1),
        (262, 3, 1, 2),
        (273, 4, 1, image_offset),
        (277, 3, 1, 3),
        (278, 4, 1, height),
        (279, 4, 1, len(pixels)),
        (284, 3, 1, 1),
    ]
    payload = bytearray(b"II*\x00" + ifd_offset.to_bytes(4, "little"))
    payload += entry_count.to_bytes(2, "little")
    for tag, value_type, value_count, value in entries:
        if value_type == 3 and value_count == 1:
            raw_value = value.to_bytes(2, "little") + b"\x00\x00"
        else:
            raw_value = value.to_bytes(4, "little")
        payload += (
            tag.to_bytes(2, "little")
            + value_type.to_bytes(2, "little")
            + value_count.to_bytes(4, "little")
            + raw_value
        )
    payload += (0).to_bytes(4, "little")
    payload += (8).to_bytes(2, "little") * 3
    payload += pixels
    return bytes(payload)
