"""Timed GIF assets and immutable, time-selected raster scenes.

``AnimatedRaster.from_blob(blob)`` validates and decodes every GIF frame before
returning metadata. ``durations_ms`` retains each positive authored delay;
``duration`` is one complete cycle in seconds. ``loop_count`` is ``None`` for a
single pass, ``0`` for infinite looping, or the number of repeats after the
first pass. ``frame_at(seconds)`` returns an independent, composited RGBA Pillow
image. Intervals are half-open: an exact frame boundary selects the next frame,
an exact looping cycle boundary selects the first, and a completed finite
animation holds its last frame. GIF disposal 0/1/2 is supported; disposal 3,
reserved disposal values, missing/nonpositive animated timing, corrupt frames,
and animated codecs other than GIF raise ``AnimatedRasterRefusal``.

``raster_animation(blob)`` returns that metadata for a multi-frame GIF, or
``None`` for a validated static raster. ``select_image_frames(slide, time)``
returns an immutable scene whose animated pictures, picture fills, background
paint, and fill overlays contain selected PNG bytes. Source assets and all
placement/crop/paint metadata remain untouched. Rendering starts each image's
clock at slide time zero, independently of shape-effect activation. The input
scene and saved image bytes are never rewritten or re-encoded by selection.
"""

from __future__ import annotations

import bisect
import io
import math
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any

from .render_model import PicturePrimitive, Primitive, SlideScene, TiledPicturePaint
from .render_refusals import RenderRefusal

__all__ = ["AnimatedRaster", "AnimatedRasterRefusal", "raster_animation", "select_image_frames"]


class AnimatedRasterRefusal(RenderRefusal):
    """A raster cannot be decoded or played without losing its timed semantics."""


def _seconds(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnimatedRasterRefusal("image time must be a finite non-negative number")
    try:
        seconds = float(value)
    except OverflowError as exc:
        raise AnimatedRasterRefusal("image time must be finite") from exc
    if not math.isfinite(seconds) or seconds < 0:
        raise AnimatedRasterRefusal("image time must be a finite non-negative number")
    return seconds


@dataclass(frozen=True)
class AnimatedRaster:
    """Fully decoded GIF metadata; ``duration`` measures one cycle, not repeats."""

    durations_ms: tuple[int, ...]
    loop_count: int | None
    _frames: tuple[Any, ...] = field(repr=False, compare=False)
    _ends_ms: tuple[int, ...] = field(repr=False)

    @classmethod
    def from_blob(cls, blob: bytes) -> AnimatedRaster:
        """Decode a timed multi-frame GIF, refusing static or unsupported assets."""
        animation = raster_animation(blob)
        if animation is None:
            raise AnimatedRasterRefusal("animated raster metadata requires a timed multi-frame GIF")
        return animation

    @property
    def duration(self) -> float:
        return self._ends_ms[-1] / 1000.0

    def _frame_index(self, seconds: float) -> int:
        cycles = 1 if self.loop_count is None else self.loop_count + 1
        milliseconds = seconds * 1000.0
        if math.isfinite(milliseconds):
            nearest = round(milliseconds)
            if abs(milliseconds - nearest) <= math.ulp(milliseconds):
                milliseconds = float(nearest)
        if self.loop_count != 0 and milliseconds >= self._ends_ms[-1] * cycles:
            return len(self._frames) - 1
        # Work in authored integer milliseconds: 0.3 seconds is the exact
        # boundary of a 100/200-ms GIF, not a floating-point remainder of 0.3.
        if math.isfinite(milliseconds):
            milliseconds %= self._ends_ms[-1]
        else:
            milliseconds = math.fmod(seconds, self.duration) * 1000.0
        return min(bisect.bisect_right(self._ends_ms, milliseconds), len(self._frames) - 1)

    def frame_at(self, seconds: float) -> Any:
        """Return independent RGBA pixels at non-negative finite slide seconds."""
        return self._frames[self._frame_index(_seconds(seconds))].copy()


def _gif_metadata(blob: bytes) -> tuple[tuple[int | None, ...], tuple[int, ...], int | None]:
    """Read per-image controls, without Pillow's inherited duration/disposal state."""
    offset = 0

    def take(count: int) -> bytes:
        nonlocal offset
        end = offset + count
        if end > len(blob):
            raise AnimatedRasterRefusal("corrupt GIF: truncated frame or extension")
        result = blob[offset:end]
        offset = end
        return result

    def blocks(*, collect: bool = False) -> tuple[bytes, ...]:
        result = []
        while count := take(1)[0]:
            payload = take(count)
            if collect:
                result.append(payload)
        return tuple(result)

    header = take(13)
    if header[:6] not in (b"GIF87a", b"GIF89a"):
        raise AnimatedRasterRefusal("animated raster playback supports GIF only")
    width = int.from_bytes(header[6:8], "little")
    height = int.from_bytes(header[8:10], "little")
    if not width or not height:
        raise AnimatedRasterRefusal("corrupt GIF: empty logical screen")
    if header[10] & 0x80:
        take(3 * (1 << ((header[10] & 7) + 1)))
    delays: list[int | None] = []
    disposals: list[int] = []
    delay: int | None = None
    disposal = 0
    loop_count: int | None = None
    while True:
        marker = take(1)[0]
        if marker == 0x3B:
            if not delays:
                raise AnimatedRasterRefusal("corrupt GIF: no image frames")
            return tuple(delays), tuple(disposals), loop_count
        if marker == 0x21:
            label = take(1)[0]
            if label == 0xF9:
                control = take(6)
                if control[0] != 4 or control[-1] != 0:
                    raise AnimatedRasterRefusal("corrupt GIF: invalid graphic control extension")
                disposal = (control[1] >> 2) & 7
                if disposal not in (0, 1, 2):
                    raise AnimatedRasterRefusal(f"animated GIF disposal {disposal} is unsupported")
                delay = int.from_bytes(control[2:4], "little") * 10
            elif label == 0xFF:
                application = take(take(1)[0])
                payloads = blocks(collect=True)
                if application in (b"NETSCAPE2.0", b"ANIMEXTS1.0"):
                    if len(payloads) != 1 or len(payloads[0]) != 3 or payloads[0][0] != 1:
                        raise AnimatedRasterRefusal("corrupt GIF: invalid loop extension")
                    repeats = int.from_bytes(payloads[0][1:], "little")
                    if loop_count is not None and loop_count != repeats:
                        raise AnimatedRasterRefusal("animated GIF has conflicting loop extensions")
                    loop_count = repeats
            elif label == 0x01:
                raise AnimatedRasterRefusal("animated GIF plain-text graphics are unsupported")
            else:
                blocks()
            continue
        if marker != 0x2C:
            raise AnimatedRasterRefusal("corrupt GIF: invalid frame block")
        descriptor = take(9)
        x = int.from_bytes(descriptor[:2], "little")
        y = int.from_bytes(descriptor[2:4], "little")
        frame_width = int.from_bytes(descriptor[4:6], "little")
        frame_height = int.from_bytes(descriptor[6:8], "little")
        if (
            not frame_width
            or not frame_height
            or x + frame_width > width
            or y + frame_height > height
        ):
            raise AnimatedRasterRefusal("corrupt GIF: frame exceeds the logical screen")
        if descriptor[8] & 0x80:
            take(3 * (1 << ((descriptor[8] & 7) + 1)))
        if not 2 <= take(1)[0] <= 8:
            raise AnimatedRasterRefusal("corrupt GIF: unsupported LZW code size")
        blocks()
        delays.append(delay)
        disposals.append(disposal)
        delay, disposal = None, 0


def raster_animation(blob: bytes) -> AnimatedRaster | None:
    """Validate all raster frames; return GIF metadata or ``None`` if static."""
    if not isinstance(blob, bytes):
        raise AnimatedRasterRefusal("raster metadata requires exact bytes")
    return _decode_raster(blob)


@lru_cache(maxsize=8)
def _decode_raster(blob: bytes) -> AnimatedRaster | None:
    from PIL import Image

    try:
        metadata = _gif_metadata(blob) if blob.startswith((b"GIF87a", b"GIF89a")) else None
        with Image.open(io.BytesIO(blob)) as decoded:
            if metadata is None:
                if getattr(decoded, "n_frames", 1) != 1:
                    raise AnimatedRasterRefusal(
                        f"animated raster codec {decoded.format!r} is unsupported; use a timed GIF"
                    )
                decoded.load()
                return None
            delays, disposals, loop_count = metadata
            animated = len(delays) > 1
            if animated and decoded.width * decoded.height * len(delays) > 80_000_000:
                raise AnimatedRasterRefusal(
                    "animated GIF exceeds the 80 million decoded pixel limit; "
                    "reduce image dimensions or frame count"
                )
            if animated and any(delay is None or delay <= 0 for delay in delays):
                raise AnimatedRasterRefusal(
                    "animated GIF requires a positive duration for every frame"
                )
            durations = tuple(delay for delay in delays if delay is not None)
            frames = []
            ends = []
            elapsed = 0
            for index, disposal in enumerate(disposals):
                # Pillow retains the preceding nonzero disposal when the next
                # control says zero. Reset it before seek so zero means retain,
                # while the previous frame's stored disposal is still applied.
                decoded.disposal_method = disposal
                decoded.seek(index)
                decoded.load()
                if animated:
                    frames.append(decoded.convert("RGBA"))
                    elapsed += durations[index]
                    ends.append(elapsed)
            if not animated:
                return None
            return AnimatedRaster(durations, loop_count, tuple(frames), tuple(ends))
    except AnimatedRasterRefusal:
        raise
    except (
        ValueError,
        OSError,
        EOFError,
        SyntaxError,
        IndexError,
        Image.DecompressionBombError,
    ) as exc:
        raise AnimatedRasterRefusal("unsupported or corrupt raster image or GIF frame") from exc


def _image_consumers(value: Any) -> Iterator[PicturePrimitive | TiledPicturePaint]:
    if isinstance(value, (PicturePrimitive, TiledPicturePaint)):
        yield value
    if isinstance(value, Primitive):
        fill = getattr(value, "fill", None)
        if isinstance(fill, TiledPicturePaint):
            yield fill
        if value.fill_overlay is not None and isinstance(
            value.fill_overlay.color, TiledPicturePaint
        ):
            yield value.fill_overlay.color


def scene_image_timing(slide: SlideScene) -> tuple[float, frozenset[int], bool]:
    """Return sampling lifetime, animated primitive indices and background flag.

    Infinite GIFs contribute one cycle; finite GIFs contribute every pass.
    Unsupported animated content is refused even when a shape starts hidden.
    """
    duration = 0.0
    indices = set()
    background = False
    for index, value in enumerate((slide.background, *slide.primitives), start=-1):
        for consumer in _image_consumers(value):
            animation = raster_animation(consumer.data)
            if animation is None:
                continue
            if index == -1:
                background = True
            else:
                indices.add(index)
            cycles = 1 if animation.loop_count in (None, 0) else animation.loop_count + 1
            duration = max(duration, animation._ends_ms[-1] * cycles / 1000.0)
    return duration, frozenset(indices), background


@lru_cache(maxsize=64)
def _frame_png(blob: bytes, index: int) -> bytes:
    animation = AnimatedRaster.from_blob(blob)
    stream = io.BytesIO()
    animation._frames[index].save(stream, format="PNG")
    return stream.getvalue()


def _select_value(value: Any, seconds: float) -> Any:
    changes = {}
    if isinstance(value, (PicturePrimitive, TiledPicturePaint)):
        animation = raster_animation(value.data)
        if animation is not None:
            index = animation._frame_index(seconds)
            changes.update(
                data=_frame_png(value.data, index),
                image_format="png",
                pixel_width=animation._frames[index].width,
                pixel_height=animation._frames[index].height,
            )
    if isinstance(value, Primitive):
        fill = getattr(value, "fill", None)
        selected = _select_value(fill, seconds)
        if selected is not fill:
            changes["fill"] = selected
        if value.fill_overlay is not None:
            selected = _select_value(value.fill_overlay.color, seconds)
            if selected is not value.fill_overlay.color:
                changes["fill_overlay"] = replace(value.fill_overlay, color=selected)
    return replace(value, **changes) if changes else value


def select_image_frames(slide: SlideScene, time: float) -> SlideScene:
    """Select GIF pixels at ``time`` seconds without changing the source scene."""
    seconds = _seconds(time)
    background = _select_value(slide.background, seconds)
    primitives = tuple(_select_value(primitive, seconds) for primitive in slide.primitives)
    if background is slide.background and all(
        selected is original
        for selected, original in zip(primitives, slide.primitives, strict=True)
    ):
        return slide
    return replace(slide, background=background, primitives=primitives)
