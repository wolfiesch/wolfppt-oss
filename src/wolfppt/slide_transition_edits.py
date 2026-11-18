"""Slide XML transition edit applicator for presentation saves."""

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .slide_payloads import load_slide_payloads as _load_slide_payloads
from .slide_transition_xml import (
    apply_transition_package_edit as _apply_transition_package_edit,
)
from .slide_transition_xml import (
    register_transition_namespaces as _register_transition_namespaces,
)


@dataclass
class TransitionSpec:
    """Specification for slide transition mutations.

    Attributes:
        effect: Canonical Open XML element local name (e.g. 'fade', 'randomBar', 'push') or None.
        speed: 'slow', 'med', 'fast', or None.
        advance_on_click: True, False, or None.
        advance_after: Non-negative seconds (float/int), mapped to advTm attribute (ms), or None.
        duration: Non-negative integer milliseconds (0 to 4294967295), mapped to p14:dur attribute, or None.
        effect_options: Attributes for the effect child element (e.g. {'thruBlk': '1'}, {'dir': 'l'}).
        remove: If True, completely removes the <p:transition> element from the slide.
        effect_specified: Whether effect was explicitly set/modified by the caller.
        speed_specified: Whether speed was explicitly set/modified by the caller.
        advance_on_click_specified: Whether advance_on_click was explicitly set/modified by the caller.
        advance_after_specified: Whether advance_after was explicitly set/modified by the caller.
        duration_specified: Whether duration was explicitly set/modified by the caller.
    """

    effect: str | None = None
    speed: str | None = None
    advance_on_click: bool | None = None
    advance_after: float | None = None
    duration: int | None = None
    effect_options: dict[str, Any] = field(default_factory=dict)
    remove: bool = False
    effect_specified: bool = False
    speed_specified: bool = False
    advance_on_click_specified: bool = False
    advance_after_specified: bool = False
    duration_specified: bool = False


def _coerce_transition_spec(spec: Any) -> TransitionSpec:
    """Coerce input into a TransitionSpec."""
    if isinstance(spec, TransitionSpec):
        return spec
    if spec is None:
        return TransitionSpec(remove=True)
    if isinstance(spec, dict):
        return TransitionSpec(**spec)
    raise TypeError(f"expected TransitionSpec or dict, got {type(spec).__name__}")


def apply_slide_transition_edits(
    input_path: Path,
    output_path: Path,
    transition_edits: list[tuple[int | str, Any]] | dict[int | str, Any],
) -> None:
    """Apply queued slide transition edits to a presentation package.

    Consumes either a list of (slide_identifier, spec) pairs or a mapping.
    Slide identifiers may be 0-based integer indices or string part names
    (e.g. 'ppt/slides/slide1.xml').

    Preserves unsupported transitions untouched until an explicit replacement or removal.
    A newly embedded transition sound adds its WAV media part, slide audio
    relationship and content type; replaced sounds drop their stale relationship.
    Never touches, modifies, or loses p:timing or any other unrelated parts.
    """
    slides = _load_slide_payloads(input_path)

    items: list[tuple[int | str, Any]]
    if isinstance(transition_edits, dict):
        items = list(transition_edits.items())
    else:
        items = list(transition_edits)

    edits_by_part: dict[str, TransitionSpec] = {}
    for identifier, raw_spec in items:
        spec = _coerce_transition_spec(raw_spec)
        if isinstance(identifier, int):
            try:
                part = str(slides[identifier]["part"])
            except IndexError as exc:
                raise IndexError(
                    f"slide index {identifier} out of range (deck has {len(slides)} slides)"
                ) from exc
        elif isinstance(identifier, str):
            clean = identifier.strip().lstrip("/")
            if not clean:
                continue
            part = clean
            for s in slides:
                s_part = str(s.get("part", "")).lstrip("/")
                if s_part == clean or s_part.endswith(f"/{clean}"):
                    part = str(s["part"])
                    break
        else:
            raise TypeError(
                f"slide identifier must be int or str, got {type(identifier).__name__}"
            )
        edits_by_part[part] = spec

    if not edits_by_part:
        if input_path != output_path:
            shutil.copy2(input_path, output_path)
        return

    _register_transition_namespaces()
    replacements: dict[str, bytes] = {}

    with zipfile.ZipFile(input_path) as package:
        for slide_part, spec in edits_by_part.items():
            norm_part = slide_part.lstrip("/")
            try:
                xml_bytes = package.read(norm_part)
            except KeyError as exc:
                raise KeyError(
                    f"slide part {slide_part!r} not found in package"
                ) from exc
            root = ET.fromstring(xml_bytes)
            _apply_transition_package_edit(package, norm_part, root, spec, replacements)
            replacements[norm_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    _copy_package_with_replacements(input_path, output_path, replacements)
