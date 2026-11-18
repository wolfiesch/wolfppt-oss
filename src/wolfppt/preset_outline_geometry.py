"""DrawingML preset geometry outlines, shared by the editor and the renderer.

DrawingML preset geometry is a formula language.  This module traces the flat
presets whose OOXML formulas are unambiguous and refuses every other preset by
name, so a caller either gets exactly the outline a deck declares or a refusal
naming the preset.  Freeform ``a:custGeom`` geometry is handled separately,
which is how a deck expresses any other outline.  The editor converts these
outlines to ``a:custGeom`` for line sketch styles; the commercial renderer
reaches them through :mod:`wolfppt.render_presets`.

Coordinates are EMU relative to the shape's own box (origin at its top-left
corner, y downwards).  ``pin`` semantics for adjustments follow the OOXML
guide rules, including the ``ss`` (shortest side) base that several presets
use.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .render_refusals import RenderRefusal


class PresetRefusal(RenderRefusal):
    """Raised when a preset geometry is not part of the supported surface."""


@dataclass(frozen=True)
class PresetSegment:
    """One segment of a preset path: ``line``, ``quad``, or ``cubic``."""

    kind: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class PresetPath:
    """One closed or open path of a preset geometry."""

    start: tuple[float, float]
    segments: tuple[PresetSegment, ...]
    closed: bool = True
    filled: bool = True
    stroked: bool = True


@dataclass(frozen=True)
class PresetGeometry:
    """The paths a preset geometry resolves to for one shape box."""

    paths: tuple[PresetPath, ...]

    @property
    def is_line(self) -> bool:
        return all(not path.filled for path in self.paths)


def _line(points: list[tuple[float, float]]) -> tuple[PresetSegment, ...]:
    segments: list[PresetSegment] = []
    for index in range(1, len(points)):
        segments.append(PresetSegment("line", (points[index - 1], points[index])))
    return tuple(segments)


def _polygon(points: list[tuple[float, float]]) -> PresetPath:
    return PresetPath(
        start=points[0],
        segments=_line(points + [points[0]]),
        closed=True,
    )


def _pin(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def resolve_preset(
    preset: str,
    width: float,
    height: float,
    adjustments: Sequence[float] | Mapping[str, float] | Sequence[tuple[str, float]] = (),
) -> PresetGeometry:
    """Resolve one preset name into paths inside a ``width`` x ``height`` box."""
    builder = _PRESETS.get(preset)
    if builder is None:
        raise PresetRefusal(
            f"preset geometry {preset!r} is not supported; supported presets: "
            + ", ".join(sorted(_PRESETS))
        )
    if preset in {"line", "straightConnector1", "bentConnector3", "curvedConnector3"}:
        if width < 0 or height < 0 or (width == 0 and height == 0):
            raise PresetRefusal(
                f"line preset {preset!r} requires non-negative dimensions and non-zero length; "
                f"got {width}x{height}"
            )
    elif width <= 0 or height <= 0:
        raise PresetRefusal(
            f"preset geometry {preset!r} requires positive width and height; got {width}x{height}"
        )
    return builder(width, height, adjustments)


def _adjust(adjustments: tuple[float, ...], index: int, default: float) -> float:
    if index < len(adjustments):
        return adjustments[index]
    return default


def _rect(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    return PresetGeometry((_polygon([(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]),))


def _round_rect(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    radius = _pin(_adjust(adjustments, 0, 16667.0), 0.0, 50000.0)
    base = min(width, height) * radius / 100000.0
    if base <= 0:
        return _rect(width, height, adjustments)
    base = min(base, width / 2, height / 2)
    right = width
    bottom = height
    start = (base, 0.0)
    segments: tuple[PresetSegment, ...] = (
        PresetSegment("line", (start, (right - base, 0.0))),
        PresetSegment("quad", ((right, 0.0), (right, base))),
        PresetSegment("line", ((right, base), (right, bottom - base))),
        PresetSegment(
            "quad",
            ((right, bottom), (right - base, bottom)),
        ),
        PresetSegment("line", ((right - base, bottom), (base, bottom))),
        PresetSegment(
            "quad",
            ((0.0, bottom), (0.0, bottom - base)),
        ),
        PresetSegment("line", ((0.0, bottom - base), (0.0, base))),
        PresetSegment("quad", ((0.0, 0.0), (base, 0.0))),
        PresetSegment("line", ((base, 0.0), start)),
    )
    return PresetGeometry((PresetPath(start=start, segments=segments),))


def _ellipse(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    right = width
    bottom = height
    center_x = width / 2
    center_y = height / 2
    kappa = 0.5522847498307936
    control_x = center_x * kappa
    control_y = center_y * kappa
    start = (right, center_y)
    segments: tuple[PresetSegment, ...] = (
        PresetSegment(
            "cubic",
            (
                (right, center_y + control_y),
                (center_x + control_x, bottom),
                (center_x, bottom),
            ),
        ),
        PresetSegment(
            "cubic",
            (
                (center_x - control_x, bottom),
                (0.0, center_y + control_y),
                (0.0, center_y),
            ),
        ),
        PresetSegment(
            "cubic",
            (
                (0.0, center_y - control_y),
                (center_x - control_x, 0.0),
                (center_x, 0.0),
            ),
        ),
        PresetSegment(
            "cubic",
            (
                (center_x + control_x, 0.0),
                (right, center_y - control_y),
                (right, center_y),
            ),
        ),
    )
    return PresetGeometry((PresetPath(start=start, segments=segments),))


def _triangle(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    apex = _pin(_adjust(adjustments, 0, 50000.0), 0.0, 100000.0)
    return PresetGeometry(
        (_polygon([(width * apex / 100000.0, 0.0), (width, height), (0.0, height)]),)
    )


def _right_triangle(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    return PresetGeometry((_polygon([(0.0, 0.0), (0.0, height), (width, height)]),))


def _diamond(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    return PresetGeometry(
        (
            _polygon(
                [
                    (width / 2, 0.0),
                    (width, height / 2),
                    (width / 2, height),
                    (0.0, height / 2),
                ]
            ),
        )
    )


def _parallelogram(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    offset = _pin(_adjust(adjustments, 0, 25000.0), 0.0, 100000.0) / 100000.0
    left = width * offset
    return PresetGeometry(
        (
            _polygon(
                [
                    (left, 0.0),
                    (width, 0.0),
                    (width - left, height),
                    (0.0, height),
                ]
            ),
        )
    )


def _trapezoid(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    offset = _pin(_adjust(adjustments, 0, 25000.0), 0.0, 50000.0) / 100000.0
    inset = width * offset
    return PresetGeometry(
        (
            _polygon(
                [
                    (inset, 0.0),
                    (width - inset, 0.0),
                    (width, height),
                    (0.0, height),
                ]
            ),
        )
    )


def _hexagon(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    guide = _pin(_adjust(adjustments, 0, 25000.0), 0.0, 50000.0)
    inset = min(width, height) * guide / 100000.0
    return PresetGeometry(
        (
            _polygon(
                [
                    (inset, 0.0),
                    (width - inset, 0.0),
                    (width, height / 2),
                    (width - inset, height),
                    (inset, height),
                    (0.0, height / 2),
                ]
            ),
        )
    )


def _octagon(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    guide = _pin(_adjust(adjustments, 0, 29289.0), 0.0, 50000.0)
    size = min(width, height)
    inset_x = size * guide / 100000.0
    inset_y = size * guide / 100000.0
    return PresetGeometry(
        (
            _polygon(
                [
                    (inset_x, 0.0),
                    (width - inset_x, 0.0),
                    (width, inset_y),
                    (width, height - inset_y),
                    (width - inset_x, height),
                    (inset_x, height),
                    (0.0, height - inset_y),
                    (0.0, inset_y),
                ]
            ),
        )
    )


def _chevron(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    guide = _pin(_adjust(adjustments, 0, 50000.0), 0.0, 100000.0) / 100000.0
    inset = width * guide
    return PresetGeometry(
        (
            _polygon(
                [
                    (0.0, 0.0),
                    (width - inset, 0.0),
                    (width, height / 2),
                    (width - inset, height),
                    (0.0, height),
                    (inset, height / 2),
                ]
            ),
        )
    )


def _home_plate(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    guide = _pin(_adjust(adjustments, 0, 50000.0), 0.0, 100000.0) / 100000.0
    inset = width * guide
    return PresetGeometry(
        (
            _polygon(
                [
                    (0.0, 0.0),
                    (width - inset, 0.0),
                    (width, height / 2),
                    (width - inset, height),
                    (0.0, height),
                ]
            ),
        )
    )


def _plus(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    guide = _pin(_adjust(adjustments, 0, 25000.0), 0.0, 50000.0) / 100000.0
    inset_x = width * guide
    inset_y = height * guide
    return PresetGeometry(
        (
            _polygon(
                [
                    (inset_x, 0.0),
                    (width - inset_x, 0.0),
                    (width - inset_x, inset_y),
                    (width, inset_y),
                    (width, height - inset_y),
                    (width - inset_x, height - inset_y),
                    (width - inset_x, height),
                    (inset_x, height),
                    (inset_x, height - inset_y),
                    (0.0, height - inset_y),
                    (0.0, inset_y),
                    (inset_x, inset_y),
                ]
            ),
        )
    )


def _donut(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    guide = _pin(_adjust(adjustments, 0, 25000.0), 0.0, 50000.0) / 100000.0
    thickness = min(width, height) * guide
    if thickness <= 0:
        return _ellipse(width, height, adjustments)
    outer = _ellipse(width, height, ()).paths[0]
    inner_width = width - 2 * thickness
    inner_height = height - 2 * thickness
    if inner_width <= 0 or inner_height <= 0:
        return PresetGeometry((outer,))
    inner = _reverse_path(
        _ellipse(inner_width, inner_height, ()).paths[0],
        offset=(thickness, thickness),
    )
    return PresetGeometry((outer, inner))


def _reverse_path(path: PresetPath, offset: tuple[float, float]) -> PresetPath:
    """Return a path traversed in the opposite direction (a hole)."""
    dx, dy = offset
    points: list[tuple[float, float]] = []
    cursor = path.start
    points.append(cursor)
    for segment in path.segments:
        points.extend(segment.points)
    if points[0] != points[-1]:
        points.append(points[0])
    shifted = [(x + dx, y + dy) for x, y in reversed(points)]
    return PresetPath(
        start=shifted[0],
        segments=_line(shifted),
        closed=True,
    )


def _line_geometry(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    return PresetGeometry(
        (
            PresetPath(
                start=(0.0, 0.0),
                segments=(PresetSegment("line", ((0.0, 0.0), (width, height))),),
                closed=False,
                filled=False,
            ),
        )
    )


def _bent_connector_3(
    width: float, height: float, adjustments: tuple[float, ...]
) -> PresetGeometry:
    if len(adjustments) > 1:
        raise PresetRefusal(
            "preset 'bentConnector3' accepts at most 1 adjustment guide (adj1); "
            f"got {len(adjustments)}"
        )
    adj1 = _adjust(adjustments, 0, 50000.0)
    if not math.isfinite(adj1):
        raise PresetRefusal(f"preset 'bentConnector3' requires finite adj1; got {adj1}")
    x1 = (width * adj1) / 100000.0
    return PresetGeometry(
        (
            PresetPath(
                start=(0.0, 0.0),
                segments=(
                    PresetSegment("line", ((0.0, 0.0), (x1, 0.0))),
                    PresetSegment("line", ((x1, 0.0), (x1, height))),
                    PresetSegment("line", ((x1, height), (width, height))),
                ),
                closed=False,
                filled=False,
                stroked=True,
            ),
        )
    )


def _curved_connector_3(
    width: float, height: float, adjustments: tuple[float, ...]
) -> PresetGeometry:
    if len(adjustments) > 1:
        raise PresetRefusal(
            "preset 'curvedConnector3' accepts at most 1 adjustment guide (adj1); "
            f"got {len(adjustments)}"
        )
    adj1 = _adjust(adjustments, 0, 50000.0)
    if not math.isfinite(adj1):
        raise PresetRefusal(f"preset 'curvedConnector3' requires finite adj1; got {adj1}")
    x2 = (width * adj1) / 100000.0
    x1 = x2 / 2.0
    x3 = (width + x2) / 2.0
    hd4 = height / 4.0
    vc = height / 2.0
    y3 = height * 3.0 / 4.0
    return PresetGeometry(
        (
            PresetPath(
                start=(0.0, 0.0),
                segments=(
                    PresetSegment(
                        "cubic",
                        (
                            (x1, 0.0),
                            (x2, hd4),
                            (x2, vc),
                        ),
                    ),
                    PresetSegment(
                        "cubic",
                        (
                            (x2, y3),
                            (x3, height),
                            (width, height),
                        ),
                    ),
                ),
                closed=False,
                filled=False,
                stroked=True,
            ),
        )
    )


def _flow_storage(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    rect = _rect(width, height, adjustments).paths[0]
    cross = (
        PresetSegment("line", ((0.0, 0.0), (width, height))),
        PresetSegment("line", ((width, 0.0), (0.0, height))),
    )
    return PresetGeometry(
        (
            rect,
            PresetPath(
                start=(0.0, 0.0),
                segments=cross,
                closed=False,
                filled=False,
            ),
        )
    )


def _flow_manual_input(
    width: float, height: float, adjustments: tuple[float, ...]
) -> PresetGeometry:
    return PresetGeometry(
        (
            _polygon(
                [
                    (0.0, height / 5),
                    (width, 0.0),
                    (width, height),
                    (0.0, height),
                ]
            ),
        )
    )


def _flow_document(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    guide = height / 5
    bottom = height - guide
    start = (0.0, 0.0)
    segments: tuple[PresetSegment, ...] = (
        PresetSegment("line", ((0.0, 0.0), (width, 0.0))),
        PresetSegment("line", ((width, 0.0), (width, bottom))),
        PresetSegment(
            "cubic",
            (
                (width, bottom + guide * 0.6),
                (width * 0.75, bottom + guide * 0.6),
                (width * 0.5, bottom + guide * 0.4),
            ),
        ),
        PresetSegment(
            "cubic",
            (
                (width * 0.25, bottom + guide * 0.2),
                (0.0, bottom + guide * 0.6),
                (0.0, bottom),
            ),
        ),
        PresetSegment("line", ((0.0, bottom), start)),
    )
    return PresetGeometry((PresetPath(start=start, segments=segments),))


def _flow_merge(width: float, height: float, adjustments: tuple[float, ...]) -> PresetGeometry:
    return PresetGeometry((_polygon([(0.0, 0.0), (width, 0.0), (width / 2, height)]),))


def _parse_preset_adjustments(
    preset: str,
    adjustments: Any,
    allowed_guides: tuple[str, ...],
    defaults: dict[str, float],
) -> dict[str, float]:
    result = dict(defaults)
    if not adjustments:
        return result

    if isinstance(adjustments, Mapping):
        for k, v in adjustments.items():
            if k not in allowed_guides:
                raise PresetRefusal(
                    f"preset {preset!r} received unsupported adjustment guide {k!r}; "
                    f"supported guides: {', '.join(allowed_guides)}"
                )
            try:
                fv = float(v)
            except (ValueError, TypeError) as exc:
                raise PresetRefusal(
                    f"preset {preset!r} requires numeric adjustment for {k!r}; got {v!r}"
                ) from exc
            if not math.isfinite(fv):
                raise PresetRefusal(f"preset {preset!r} requires finite {k}; got {fv}")
            result[k] = fv
        return result

    if isinstance(adjustments, Sequence):
        if (
            len(adjustments) > 0
            and isinstance(adjustments[0], (tuple, list))
            and len(adjustments[0]) == 2
            and isinstance(adjustments[0][0], str)
        ):
            for k, v in adjustments:
                if k not in allowed_guides:
                    raise PresetRefusal(
                        f"preset {preset!r} received unsupported adjustment guide {k!r}; "
                        f"supported guides: {', '.join(allowed_guides)}"
                    )
                try:
                    fv = float(v)
                except (ValueError, TypeError) as exc:
                    raise PresetRefusal(
                        f"preset {preset!r} requires numeric adjustment for {k!r}; got {v!r}"
                    ) from exc
                if not math.isfinite(fv):
                    raise PresetRefusal(f"preset {preset!r} requires finite {k}; got {fv}")
                result[k] = fv
            return result

        if len(adjustments) > len(allowed_guides):
            guide_str = ", ".join(allowed_guides)
            s = "s" if len(allowed_guides) > 1 else ""
            raise PresetRefusal(
                f"preset {preset!r} accepts at most {len(allowed_guides)} adjustment "
                f"guide{s} ({guide_str}); got {len(adjustments)}"
            )
        for i, v in enumerate(adjustments):
            k = allowed_guides[i]
            try:
                fv = float(v)
            except (ValueError, TypeError) as exc:
                raise PresetRefusal(
                    f"preset {preset!r} requires numeric adjustment for {k!r}; got {v!r}"
                ) from exc
            if not math.isfinite(fv):
                raise PresetRefusal(f"preset {preset!r} requires finite {k}; got {fv}")
            result[k] = fv
        return result

    raise PresetRefusal(
        f"preset {preset!r} received unsupported adjustments type: {type(adjustments).__name__}"
    )


def _star_4(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments("star4", adjustments, ("adj",), {"adj": 12500.0})
    wd2 = width / 2.0
    hd2 = height / 2.0
    hc = width / 2.0
    vc = height / 2.0
    a = _pin(adjs["adj"], 0.0, 50000.0)
    iwd2 = (wd2 * a) / 50000.0
    ihd2 = (hd2 * a) / 50000.0
    ang_45 = math.pi / 4.0
    sdx = iwd2 * math.cos(ang_45)
    sdy = ihd2 * math.sin(ang_45)
    sx1 = hc - sdx
    sx2 = hc + sdx
    sy1 = vc - sdy
    sy2 = vc + sdy
    points = [
        (0.0, vc),
        (sx1, sy1),
        (hc, 0.0),
        (sx2, sy1),
        (width, vc),
        (sx2, sy2),
        (hc, height),
        (sx1, sy2),
    ]
    return PresetGeometry((_polygon(points),))


def _star_5(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments("star5", adjustments, ("adj",), {"adj": 19098.0})
    wd2 = width / 2.0
    hd2 = height / 2.0
    hc = width / 2.0
    vc = height / 2.0
    hf = 105146.0
    vf = 110557.0
    a = _pin(adjs["adj"], 0.0, 50000.0)
    swd2 = (wd2 * hf) / 100000.0
    shd2 = (hd2 * vf) / 100000.0
    svc = (vc * vf) / 100000.0

    ang_18 = (1080000.0 / 60000.0) * (math.pi / 180.0)
    ang_306 = (18360000.0 / 60000.0) * (math.pi / 180.0)
    dx1 = swd2 * math.cos(ang_18)
    dx2 = swd2 * math.cos(ang_306)
    dy1 = shd2 * math.sin(ang_18)
    dy2 = shd2 * math.sin(ang_306)

    x1 = hc - dx1
    x2 = hc - dx2
    x3 = hc + dx2
    x4 = hc + dx1
    y1 = svc - dy1
    y2 = svc - dy2

    iwd2 = (swd2 * a) / 50000.0
    ihd2 = (shd2 * a) / 50000.0

    ang_342 = (20520000.0 / 60000.0) * (math.pi / 180.0)
    ang_54 = (3240000.0 / 60000.0) * (math.pi / 180.0)
    sdx1 = iwd2 * math.cos(ang_342)
    sdx2 = iwd2 * math.cos(ang_54)
    sdy1 = ihd2 * math.sin(ang_54)
    sdy2 = ihd2 * math.sin(ang_342)

    sx1 = hc - sdx1
    sx2 = hc - sdx2
    sx3 = hc + sdx2
    sx4 = hc + sdx1

    sy1 = svc - sdy1
    sy2 = svc - sdy2
    sy3 = svc + ihd2

    points = [
        (x1, y1),
        (sx2, sy1),
        (hc, 0.0),
        (sx3, sy1),
        (x4, y1),
        (sx4, sy2),
        (x3, y2),
        (hc, sy3),
        (x2, y2),
        (sx1, sy2),
    ]
    return PresetGeometry((_polygon(points),))


def _star_6(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments("star6", adjustments, ("adj",), {"adj": 28868.0})
    wd2 = width / 2.0
    hd2 = height / 2.0
    hd4 = height / 4.0
    hc = width / 2.0
    vc = height / 2.0
    hf = 115470.0
    a = _pin(adjs["adj"], 0.0, 50000.0)
    swd2 = (wd2 * hf) / 100000.0

    ang_30 = (1800000.0 / 60000.0) * (math.pi / 180.0)
    dx1 = swd2 * math.cos(ang_30)
    x1 = hc - dx1
    x2 = hc + dx1
    y2 = vc + hd4

    iwd2 = (swd2 * a) / 50000.0
    ihd2 = (hd2 * a) / 50000.0

    sdx2 = iwd2 / 2.0
    sx1 = hc - iwd2
    sx2 = hc - sdx2
    sx3 = hc + sdx2
    sx4 = hc + iwd2

    ang_60 = (3600000.0 / 60000.0) * (math.pi / 180.0)
    sdy1 = ihd2 * math.sin(ang_60)
    sy1 = vc - sdy1
    sy2 = vc + sdy1

    points = [
        (x1, hd4),
        (sx2, sy1),
        (hc, 0.0),
        (sx3, sy1),
        (x2, hd4),
        (sx4, vc),
        (x2, y2),
        (sx3, sy2),
        (hc, height),
        (sx2, sy2),
        (x1, y2),
        (sx1, vc),
    ]
    return PresetGeometry((_polygon(points),))


def _right_arrow(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments(
        "rightArrow", adjustments, ("adj1", "adj2"), {"adj1": 50000.0, "adj2": 50000.0}
    )
    ss = min(width, height)
    vc = height / 2.0
    max_adj2 = (100000.0 * width) / ss
    a1 = _pin(adjs["adj1"], 0.0, 100000.0)
    a2 = _pin(adjs["adj2"], 0.0, max_adj2)
    dx1 = (ss * a2) / 100000.0
    x1 = width - dx1
    dy1 = (height * a1) / 200000.0
    y1 = vc - dy1
    y2 = vc + dy1
    points = [
        (0.0, y1),
        (x1, y1),
        (x1, 0.0),
        (width, vc),
        (x1, height),
        (x1, y2),
        (0.0, y2),
    ]
    return PresetGeometry((_polygon(points),))


def _left_arrow(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments(
        "leftArrow", adjustments, ("adj1", "adj2"), {"adj1": 50000.0, "adj2": 50000.0}
    )
    ss = min(width, height)
    vc = height / 2.0
    max_adj2 = (100000.0 * width) / ss
    a1 = _pin(adjs["adj1"], 0.0, 100000.0)
    a2 = _pin(adjs["adj2"], 0.0, max_adj2)
    dx2 = (ss * a2) / 100000.0
    x2 = dx2
    dy1 = (height * a1) / 200000.0
    y1 = vc - dy1
    y2 = vc + dy1
    points = [
        (0.0, vc),
        (x2, 0.0),
        (x2, y1),
        (width, y1),
        (width, y2),
        (x2, y2),
        (x2, height),
    ]
    return PresetGeometry((_polygon(points),))


def _up_arrow(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments(
        "upArrow", adjustments, ("adj1", "adj2"), {"adj1": 50000.0, "adj2": 50000.0}
    )
    ss = min(width, height)
    hc = width / 2.0
    max_adj2 = (100000.0 * height) / ss
    a1 = _pin(adjs["adj1"], 0.0, 100000.0)
    a2 = _pin(adjs["adj2"], 0.0, max_adj2)
    dy2 = (ss * a2) / 100000.0
    y2 = dy2
    dx1 = (width * a1) / 200000.0
    x1 = hc - dx1
    x2 = hc + dx1
    points = [
        (0.0, y2),
        (hc, 0.0),
        (width, y2),
        (x2, y2),
        (x2, height),
        (x1, height),
        (x1, y2),
    ]
    return PresetGeometry((_polygon(points),))


def _up_arrow_callout(width: float, height: float, adjustments: Any) -> PresetGeometry:
    # ECMA-376 presetShapeDefinitions.xml: shortest-side guides and coupled pins.
    adjs = _parse_preset_adjustments(
        "upArrowCallout",
        adjustments,
        ("adj1", "adj2", "adj3", "adj4"),
        {"adj1": 25000.0, "adj2": 25000.0, "adj3": 25000.0, "adj4": 64977.0},
    )
    ss = min(width, height)
    hc = width / 2.0
    a2 = _pin(adjs["adj2"], 0.0, 50000.0 * width / ss)
    a1 = _pin(adjs["adj1"], 0.0, a2 * 2.0)
    a3 = _pin(adjs["adj3"], 0.0, 100000.0 * height / ss)
    a4 = _pin(adjs["adj4"], 0.0, 100000.0 - a3 * ss / height)
    dx1 = ss * a2 / 100000.0
    dx2 = ss * a1 / 200000.0
    x1, x2 = hc - dx1, hc - dx2
    x3, x4 = hc + dx2, hc + dx1
    y1 = ss * a3 / 100000.0
    y2 = height - height * a4 / 100000.0
    points = [
        (0.0, y2),
        (x2, y2),
        (x2, y1),
        (x1, y1),
        (hc, 0.0),
        (x4, y1),
        (x3, y1),
        (x3, y2),
        (width, y2),
        (width, height),
        (0.0, height),
    ]
    return PresetGeometry((_polygon(points),))


def _down_arrow(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments(
        "downArrow", adjustments, ("adj1", "adj2"), {"adj1": 50000.0, "adj2": 50000.0}
    )
    ss = min(width, height)
    hc = width / 2.0
    max_adj2 = (100000.0 * height) / ss
    a1 = _pin(adjs["adj1"], 0.0, 100000.0)
    a2 = _pin(adjs["adj2"], 0.0, max_adj2)
    dy1 = (ss * a2) / 100000.0
    y1 = height - dy1
    dx1 = (width * a1) / 200000.0
    x1 = hc - dx1
    x2 = hc + dx1
    points = [
        (0.0, y1),
        (x1, y1),
        (x1, 0.0),
        (x2, 0.0),
        (x2, y1),
        (width, y1),
        (hc, height),
    ]
    return PresetGeometry((_polygon(points),))


def _wedge_rect_callout(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments(
        "wedgeRectCallout",
        adjustments,
        ("adj1", "adj2"),
        {"adj1": -20833.0, "adj2": 62500.0},
    )
    hc = width / 2.0
    vc = height / 2.0
    left = 0.0
    t = 0.0
    r = width
    b = height

    dx_pos = (width * adjs["adj1"]) / 100000.0
    dy_pos = (height * adjs["adj2"]) / 100000.0
    x_pos = hc + dx_pos
    y_pos = vc + dy_pos
    dq = (dx_pos * height) / width
    ady = abs(dy_pos)
    adq = abs(dq)
    dz = ady - adq

    xg1 = 7.0 if dx_pos > 0 else 2.0
    xg2 = 10.0 if dx_pos > 0 else 5.0
    x1 = (width * xg1) / 12.0
    x2 = (width * xg2) / 12.0

    yg1 = 7.0 if dy_pos > 0 else 2.0
    yg2 = 10.0 if dy_pos > 0 else 5.0
    y1 = (height * yg1) / 12.0
    y2 = (height * yg2) / 12.0

    t1 = left if dx_pos > 0 else x_pos
    xl = left if dz > 0 else t1

    t2 = x1 if dy_pos > 0 else x_pos
    xt = t2 if dz > 0 else x1

    t3 = x_pos if dx_pos > 0 else r
    xr = r if dz > 0 else t3

    t4 = x_pos if dy_pos > 0 else x1
    xb = t4 if dz > 0 else x1

    t5 = y1 if dx_pos > 0 else y_pos
    yl = y1 if dz > 0 else t5

    t6 = t if dy_pos > 0 else y_pos
    yt = t6 if dz > 0 else t

    t7 = y_pos if dx_pos > 0 else y1
    yr = y1 if dz > 0 else t7

    t8 = y_pos if dy_pos > 0 else b
    yb = t8 if dz > 0 else b

    points = [
        (left, t),
        (x1, t),
        (xt, yt),
        (x2, t),
        (r, t),
        (r, y1),
        (xr, yr),
        (r, y2),
        (r, b),
        (x2, b),
        (xb, yb),
        (x1, b),
        (left, b),
        (left, y2),
        (xl, yl),
        (left, y1),
    ]
    return PresetGeometry((_polygon(points),))


def _wedge_round_rect_callout(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments(
        "wedgeRoundRectCallout",
        adjustments,
        ("adj1", "adj2", "adj3"),
        {"adj1": -20833.0, "adj2": 62500.0, "adj3": 16667.0},
    )
    hc = width / 2.0
    vc = height / 2.0
    left = 0.0
    t = 0.0
    r = width
    b = height

    dx_pos = (width * adjs["adj1"]) / 100000.0
    dy_pos = (height * adjs["adj2"]) / 100000.0
    x_pos = hc + dx_pos
    y_pos = vc + dy_pos
    dq = (dx_pos * height) / width
    ady = abs(dy_pos)
    adq = abs(dq)
    dz = ady - adq

    xg1 = 7.0 if dx_pos > 0 else 2.0
    xg2 = 10.0 if dx_pos > 0 else 5.0
    x1 = (width * xg1) / 12.0
    x2 = (width * xg2) / 12.0

    yg1 = 7.0 if dy_pos > 0 else 2.0
    yg2 = 10.0 if dy_pos > 0 else 5.0
    y1 = (height * yg1) / 12.0
    y2 = (height * yg2) / 12.0

    t1 = left if dx_pos > 0 else x_pos
    xl = left if dz > 0 else t1

    t2 = x1 if dy_pos > 0 else x_pos
    xt = t2 if dz > 0 else x1

    t3 = x_pos if dx_pos > 0 else r
    xr = r if dz > 0 else t3

    t4 = x_pos if dy_pos > 0 else x1
    xb = t4 if dz > 0 else x1

    t5 = y1 if dx_pos > 0 else y_pos
    yl = y1 if dz > 0 else t5

    t6 = t if dy_pos > 0 else y_pos
    yt = t6 if dz > 0 else t

    t7 = y_pos if dx_pos > 0 else y1
    yr = y1 if dz > 0 else t7

    t8 = y_pos if dy_pos > 0 else b
    yb = t8 if dz > 0 else b

    ss = min(width, height)
    radius = _pin(adjs["adj3"], 0.0, 50000.0)
    base = min((ss * radius) / 100000.0, width / 2.0, height / 2.0)
    if base <= 0:
        return _wedge_rect_callout(width, height, {"adj1": adjs["adj1"], "adj2": adjs["adj2"]})
    u1 = base
    u2 = r - base
    v2 = b - base

    start = (left, u1)
    segments: tuple[PresetSegment, ...] = (
        PresetSegment("quad", ((left, t), (u1, t))),
        PresetSegment("line", ((u1, t), (x1, t))),
        PresetSegment("line", ((x1, t), (xt, yt))),
        PresetSegment("line", ((xt, yt), (x2, t))),
        PresetSegment("line", ((x2, t), (u2, t))),
        PresetSegment("quad", ((r, t), (r, u1))),
        PresetSegment("line", ((r, u1), (r, y1))),
        PresetSegment("line", ((r, y1), (xr, yr))),
        PresetSegment("line", ((xr, yr), (r, y2))),
        PresetSegment("line", ((r, y2), (r, v2))),
        PresetSegment("quad", ((r, b), (u2, b))),
        PresetSegment("line", ((u2, b), (x2, b))),
        PresetSegment("line", ((x2, b), (xb, yb))),
        PresetSegment("line", ((xb, yb), (x1, b))),
        PresetSegment("line", ((x1, b), (u1, b))),
        PresetSegment("quad", ((left, b), (left, v2))),
        PresetSegment("line", ((left, v2), (left, y2))),
        PresetSegment("line", ((left, y2), (xl, yl))),
        PresetSegment("line", ((xl, yl), (left, y1))),
        PresetSegment("line", ((left, y1), start)),
    )
    return PresetGeometry((PresetPath(start=start, segments=segments, closed=True),))


def _wedge_ellipse_callout(width: float, height: float, adjustments: Any) -> PresetGeometry:
    adjs = _parse_preset_adjustments(
        "wedgeEllipseCallout",
        adjustments,
        ("adj1", "adj2"),
        {"adj1": -20833.0, "adj2": 62500.0},
    )
    hc = width / 2.0
    vc = height / 2.0
    wd2 = width / 2.0
    hd2 = height / 2.0

    dx_pos = (width * adjs["adj1"]) / 100000.0
    dy_pos = (height * adjs["adj2"]) / 100000.0
    x_pos = hc + dx_pos
    y_pos = vc + dy_pos

    sdx = dx_pos * height
    sdy = dy_pos * width
    pang = math.atan2(sdy, sdx)

    ang_offset = (660000.0 / 60000.0) * (math.pi / 180.0)
    st_ang = pang + ang_offset
    en_ang = pang - ang_offset

    dx1 = wd2 * math.cos(st_ang)
    dy1 = hd2 * math.sin(st_ang)
    x1 = hc + dx1
    y1 = vc + dy1

    dx2 = wd2 * math.cos(en_ang)
    dy2 = hd2 * math.sin(en_ang)
    x2 = hc + dx2
    y2 = vc + dy2

    sw_ang = (en_ang - st_ang) % (2.0 * math.pi)
    if sw_ang <= 0.0:
        sw_ang += 2.0 * math.pi

    n = max(1, math.ceil(sw_ang / (math.pi / 2.0)))
    d_theta = sw_ang / n
    k = (4.0 / 3.0) * math.tan(d_theta / 4.0)

    segments: list[PresetSegment] = [
        PresetSegment("line", ((x_pos, y_pos), (x1, y1))),
    ]
    current_theta = st_ang
    for _ in range(n):
        next_theta = current_theta + d_theta
        cos0, sin0 = math.cos(current_theta), math.sin(current_theta)
        cos1, sin1 = math.cos(next_theta), math.sin(next_theta)

        p1 = (hc + wd2 * (cos0 - k * sin0), vc + hd2 * (sin0 + k * cos0))
        p2 = (hc + wd2 * (cos1 + k * sin1), vc + hd2 * (sin1 - k * cos1))
        p3 = (hc + wd2 * cos1, vc + hd2 * sin1)

        segments.append(PresetSegment("cubic", (p1, p2, p3)))
        current_theta = next_theta

    segments.append(PresetSegment("line", ((x2, y2), (x_pos, y_pos))))
    return PresetGeometry(
        (PresetPath(start=(x_pos, y_pos), segments=tuple(segments), closed=True),)
    )


_PRESETS = {
    "rect": _rect,
    "textBox": _rect,
    "flowChartProcess": _rect,
    "flowChartPredefinedProcess": _rect,
    "flowChartInternalStorage": _flow_storage,
    "flowChartManualInput": _flow_manual_input,
    "roundRect": _round_rect,
    "flowChartAlternateProcess": _round_rect,
    "ellipse": _ellipse,
    "oval": _ellipse,
    "flowChartConnector": _ellipse,
    "triangle": _triangle,
    "flowChartExtract": _triangle,
    "rtTriangle": _right_triangle,
    "diamond": _diamond,
    "flowChartDecision": _diamond,
    "parallelogram": _parallelogram,
    "flowChartData": _parallelogram,
    "trapezoid": _trapezoid,
    "hexagon": _hexagon,
    "flowChartPreparation": _hexagon,
    "octagon": _octagon,
    "chevron": _chevron,
    "homePlate": _home_plate,
    "plus": _plus,
    "donut": _donut,
    "line": _line_geometry,
    "straightConnector1": _line_geometry,
    "bentConnector3": _bent_connector_3,
    "curvedConnector3": _curved_connector_3,
    "flowChartDocument": _flow_document,
    "flowChartMerge": _flow_merge,
    "flowChartTerminator": _round_rect,
    "star4": _star_4,
    "star5": _star_5,
    "star6": _star_6,
    "rightArrow": _right_arrow,
    "leftArrow": _left_arrow,
    "upArrow": _up_arrow,
    "upArrowCallout": _up_arrow_callout,
    "downArrow": _down_arrow,
    "wedgeRectCallout": _wedge_rect_callout,
    "wedgeRoundRectCallout": _wedge_round_rect_callout,
    "wedgeEllipseCallout": _wedge_ellipse_callout,
}


def supported_presets() -> tuple[str, ...]:
    """Return the preset names :func:`resolve_preset` can trace."""
    return tuple(sorted(_PRESETS))
