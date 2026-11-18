"""Text frame autofit scale model and validation helpers."""

import math
from dataclasses import dataclass
from typing import Any


def validate_font_scale(value: Any) -> float:
    if isinstance(value, bool):
        raise TypeError("font_scale cannot be a boolean")
    if not isinstance(value, (int, float)):
        raise TypeError(f"font_scale must be a number, got {type(value).__name__}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"font_scale must be a finite number, got {numeric}")
    # DrawingML ST_TextFontScalePercent range: 1000..100000 (1%..100%)
    if not (0.01 <= numeric <= 1.0):
        raise ValueError(f"font_scale must be between 0.01 and 1.0, got {numeric}")
    return numeric


def validate_line_spacing_reduction(value: Any) -> float:
    if isinstance(value, bool):
        raise TypeError("line_spacing_reduction cannot be a boolean")
    if not isinstance(value, (int, float)):
        raise TypeError(
            f"line_spacing_reduction must be a number, got {type(value).__name__}"
        )
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(
            f"line_spacing_reduction must be a finite number, got {numeric}"
        )
    # DrawingML ST_TextSpacingPercent range: 0..100000 (0%..100%)
    if not (0.0 <= numeric <= 1.0):
        raise ValueError(
            f"line_spacing_reduction must be between 0.0 and 1.0, got {numeric}"
        )
    return numeric


@dataclass(frozen=True)
class TextAutofitScale:
    font_scale: float
    line_spacing_reduction: float = 0.0

    def __post_init__(self) -> None:
        fs = validate_font_scale(self.font_scale)
        lsr = validate_line_spacing_reduction(self.line_spacing_reduction)
        object.__setattr__(self, "font_scale", fs)
        object.__setattr__(self, "line_spacing_reduction", lsr)


def font_scale_to_thousandths(font_scale: float) -> int:
    return round(validate_font_scale(font_scale) * 100000)


def line_spacing_reduction_to_thousandths(reduction: float) -> int:
    return round(validate_line_spacing_reduction(reduction) * 100000)


def parse_stored_scale(
    font_scale_attr: str | None,
    line_spacing_reduction_attr: str | None = None,
) -> TextAutofitScale | None:
    if font_scale_attr is None:
        return None
    try:
        raw_fs = int(font_scale_attr)
        font_scale = raw_fs / 100000.0
        line_spacing_reduction = 0.0
        if line_spacing_reduction_attr is not None:
            raw_lsr = int(line_spacing_reduction_attr)
            line_spacing_reduction = raw_lsr / 100000.0
        return TextAutofitScale(
            font_scale=font_scale,
            line_spacing_reduction=line_spacing_reduction,
        )
    except (TypeError, ValueError):
        return None


__all__ = [
    "TextAutofitScale",
    "font_scale_to_thousandths",
    "line_spacing_reduction_to_thousandths",
    "parse_stored_scale",
    "validate_font_scale",
    "validate_line_spacing_reduction",
]
