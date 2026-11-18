"""Map authored text builds onto WolfPPT's retained glyph stream.

Fields contribute their saved ``a:t`` display text; tabs and wrapping spaces may
be absent from the drawable stream, but their laid-out positions are never
recomputed. Direct and body-list-style bullets contribute their exact rendered
characters and share the paragraph's first word/letter unit, rather than adding
a separate unit. Numbering uses the renderer's numbering rules.

The complete visible source stream must equal the retained stream before any
slice is returned. Membership never comes from geometry, a bullet-looking
character, or a primitive's position in the scene. Every slice preserves style,
effects, baseline and advance-derived glyph origins. Unavailable inherited
bullet sources and unmatched display text receive path-bearing refusals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any
from xml.etree import ElementTree as ET

from .bullet_numbering import AUTO_NUMBER_FORMATS, auto_number_text
from .render_model import TextPrimitive
from .slide_animation_emphasis import A_NS, P_NS, _build_entry

_BULLET_CHOICES = frozenset(
    f"{{{A_NS}}}{name}" for name in ("buNone", "buChar", "buAutoNum", "buBlip")
)


def _bullet_choice(
    body: ET.Element, paragraph: ET.Element, level: int, path: str
) -> tuple[ET.Element | None, str]:
    properties = paragraph.find(f"{{{A_NS}}}pPr")
    sources = [(properties, f"{path}/a:pPr")]
    style = body.find(f"{{{A_NS}}}lstStyle")
    if style is not None:
        inherited = style.find(f"{{{A_NS}}}lvl{level + 1}pPr")
        style_path = f"{path.rsplit('/a:p[', 1)[0]}/a:lstStyle/a:lvl{level + 1}pPr"
        if inherited is None and level == 0:
            inherited = style.find(f"{{{A_NS}}}defPPr")
            style_path = f"{path.rsplit('/a:p[', 1)[0]}/a:lstStyle/a:defPPr"
        sources.append((inherited, style_path))
    for source, source_path in sources:
        choices = (
            [] if source is None else [child for child in source if child.tag in _BULLET_CHOICES]
        )
        if len(choices) > 1:
            raise ValueError(f"ambiguous authored bullet choice at {source_path}")
        if choices:
            return choices[0], f"{source_path}/a:{choices[0].tag.rsplit('}', 1)[-1]}"
    return None, (
        f"{path}/a:pPr bullet choice; "
        f"p:txBody/a:lstStyle/a:lvl{level + 1}pPr; "
        f"layout/master placeholder p:txBody/a:lstStyle/a:lvl{level + 1}pPr; "
        f"master p:txStyles/*/a:lvl{level + 1}pPr; "
        f"presentation p:defaultTextStyle/a:lvl{level + 1}pPr; "
        f"theme a:objectDefaults/(a:txDef|a:spDef)/a:lstStyle/a:lvl{level + 1}pPr"
    )


def _bullet_text(choice: ET.Element | None, path: str, auto_number: int) -> str:
    if choice is None or choice.tag == f"{{{A_NS}}}buNone":
        return ""
    if choice.tag == f"{{{A_NS}}}buBlip":
        raise ValueError(f"picture bullet has no retained text-glyph mapping at {path}")
    if choice.tag == f"{{{A_NS}}}buChar":
        text = choice.get("char", "")
        if not text:
            raise ValueError(f"missing bullet display character at {path}/@char")
        return text
    kind = choice.get("type", "arabicPeriod")
    if kind not in AUTO_NUMBER_FORMATS:
        raise ValueError(f"unsupported automatic numbering {kind!r} at {path}/@type")
    raw_start = choice.get("startAt", "1")
    try:
        start = int(raw_start)
    except ValueError as exc:
        raise ValueError(f"invalid automatic numbering start at {path}/@startAt") from exc
    if start < 1:
        raise ValueError(f"automatic numbering starts below one at {path}/@startAt")
    return auto_number_text(kind, start + auto_number)


def _paragraph_text(paragraph: ET.Element, path: str) -> str:
    pieces: list[str] = []
    occurrences: dict[str, int] = {}
    for child in paragraph:
        tag = child.tag.rsplit("}", 1)[-1]
        occurrences[tag] = occurrences.get(tag, 0) + 1
        child_path = f"{path}/a:{tag}[{occurrences[tag]}]"
        if tag in ("r", "fld"):
            value = child.find(f"{{{A_NS}}}t")
            if value is None or (tag == "fld" and value.text is None):
                raise ValueError(f"missing saved display text at {child_path}/a:t")
            pieces.append(value.text or "")
        elif tag == "br":
            pieces.append("\n")
        elif tag == "tab":
            pieces.append("\t")
        elif tag not in ("pPr", "endParaRPr"):
            raise ValueError(f"unsupported authored text child at {child_path}")
    text = "".join(pieces)
    if any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise ValueError(f"text controls lack a retained glyph mapping at {path}")
    return text


def _source_build_labels(
    root: ET.Element, identifier: str, mode: str, level: int | None
) -> tuple[list[tuple[str, int, int]], list[str], str]:
    """Share authored unit/group membership with exact retained-glyph slicing."""
    bodies: list[ET.Element] = []
    for shape in root.iter(f"{{{P_NS}}}sp"):
        metadata = shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
        if metadata is not None and metadata.get("id") == identifier:
            body = shape.find(f"{{{P_NS}}}txBody")
            if body is not None:
                bodies.append(body)
    if len(bodies) != 1:
        raise ValueError("text build requires one unambiguous authored text body")
    if mode not in ("by_paragraph", "by_word", "by_letter"):
        raise ValueError(f"unsupported text build {mode!r}")
    if (mode == "by_paragraph" or level is not None) and (
        type(level) is not int or not 1 <= level <= 5
    ):
        raise ValueError("paragraph build level must be 1 through 5")
    body = bodies[0]
    body_path = f"p:sp[p:nvSpPr/p:cNvPr/@id={identifier!r}]/p:txBody"
    expected: list[tuple[str, int, int]] = []
    missing_sources: list[str] = []
    unit = -1
    auto_number = 0
    paragraph_group = -1
    for index, paragraph in enumerate(body.findall(f"{{{A_NS}}}p"), 1):
        path = f"{body_path}/a:p[{index}]"
        properties = paragraph.find(f"{{{A_NS}}}pPr")
        raw_level = "0" if properties is None else properties.get("lvl", "0")
        if not raw_level.isdigit() or not 0 <= int(raw_level) <= 8:
            raise ValueError(f"invalid authored paragraph level at {path}/a:pPr/@lvl")
        choice, bullet_path = _bullet_choice(body, paragraph, int(raw_level), path)
        bullet = _bullet_text(choice, bullet_path, auto_number)
        if choice is None:
            missing_sources.append(bullet_path)
        elif choice.tag == f"{{{A_NS}}}buAutoNum":
            auto_number += 1
        text = _paragraph_text(paragraph, path)
        if paragraph_group < 0 or int(raw_level) < (level or 1):
            paragraph_group += 1
        first_unit = unit + 1
        labels: list[int] = []
        if mode == "by_paragraph":
            if unit < 0 or int(raw_level) < level:
                unit += 1
            first_unit = unit
            labels = [unit] * len(text)
        else:
            in_word = False
            for c in text:
                if c.isspace():
                    in_word = False
                    # Authored whitespace belongs to the preceding unit within
                    # this paragraph, or its first unit for leading whitespace.
                    labels.append(max(unit, first_unit))
                else:
                    if mode == "by_letter" or not in_word:
                        unit += 1
                    in_word = True
                    labels.append(unit)
            if unit < first_unit and bullet:
                unit = first_unit
        expected.extend((c, first_unit, paragraph_group) for c in bullet)
        expected.extend((c, label, paragraph_group) for c, label in zip(text, labels, strict=True))
    return expected, missing_sources, body_path


def text_build_slices(
    root: ET.Element,
    identifier: str,
    primitive: TextPrimitive,
    mode: str,
    level: int | None,
) -> tuple[tuple[int, TextPrimitive], ...]:
    """Return source-ordered slices labelled by their proven staging unit.

    ``ValueError`` reports a mapping boundary before any raster operation.
    Paragraph groups share this same authored membership; layout is never rerun.
    """
    source, missing_sources, body_path = _source_build_labels(root, identifier, mode, level)
    expected = [(c, unit) for c, unit, _ in source]
    visible = [(c, label) for c, label in expected if not c.isspace()]
    actual = "".join(
        c
        for line in primitive.lines
        for segment in line.segments
        for c in segment.text
        if not c.isspace()
    )
    if not expected or actual != "".join(c for c, _ in visible):
        detail = (
            f"authored saved display text at {body_path} does not exactly match retained glyphs"
        )
        if missing_sources:
            detail += "; inherited bullet source proof is missing at " + "; ".join(missing_sources)
        raise ValueError(detail)
    slices: list[tuple[int, TextPrimitive]] = []
    cursor = 0
    for line in primitive.lines:
        for segment in line.segments:
            advances = segment.advances_emu
            if (
                advances is None
                or len(advances) != len(segment.text)
                or any(type(value) is not int for value in advances)
            ):
                raise ValueError(
                    "staged text requires one retained integer advance per character "
                    f"at {body_path}"
                )
            labels = []
            for c in segment.text:
                if c.isspace():
                    # Native layout omits tabs/spaces and preserves their gap
                    # in x_emu. If whitespace is retained, it must be proved
                    # by an authored character in this exact source interval.
                    end = cursor
                    while end < len(expected) and expected[end][0].isspace():
                        end += 1
                    candidates = [index for index in range(cursor, end) if expected[index][0] == c]
                    memberships = {expected[index][1] for index in candidates}
                    if len(memberships) != 1:
                        raise ValueError(
                            "retained whitespace has no unambiguous authored membership "
                            f"at {body_path}"
                        )
                    matched = candidates[0]
                    labels.append(expected[matched][1])
                    cursor = matched + 1
                else:
                    while cursor < len(expected) and expected[cursor][0].isspace():
                        cursor += 1
                    labels.append(expected[cursor][1])
                    cursor += 1
            start = 0
            offset = 0
            while start < len(labels):
                end = start + 1
                while end < len(labels) and labels[end] == labels[start]:
                    end += 1
                piece = replace(
                    segment,
                    x_emu=segment.x_emu + offset,
                    text=segment.text[start:end],
                    advances_emu=advances[start:end],
                )
                slices.append(
                    (labels[start], replace(primitive, lines=(replace(line, segments=(piece,)),)))
                )
                offset += sum(advances[start:end])
                start = end
    if not slices:
        raise ValueError(f"text build has no retained drawable glyphs at {body_path}")
    return tuple(slices)


def build_text_entry(
    key: tuple[str, str],
    build_attributes: dict[str, dict[str, str]],
    request: dict[str, Any] | None,
) -> ET.Element | None:
    """Author paragraph grouping alongside, rather than instead of, iteration."""
    options = request
    if (
        request is not None
        and request.get("text_build") in ("by_word", "by_letter")
        and request.get("build_level") is not None
        and "paragraph_build" not in request
    ):
        options = {**request, "paragraph_build": "p"}
    entry = _build_entry(key, build_attributes, options)
    if entry is not None and entry.tag == f"{{{P_NS}}}bldP" and entry.get("build") == "p":
        entry.set("bldLvl", str((options or {}).get("build_level") or 1))
    return entry


@dataclass(frozen=True, slots=True)
class TextBuildStage:
    """One disjoint text/background target and its absolute timeline start."""

    target: str
    unit: int | None
    paragraph_group: int | None
    indices: tuple[int, ...]
    start: float
    background: bool = False


def text_build_stages(
    root: ET.Element,
    identifier: str,
    units: tuple[tuple[str, int, tuple[int, ...]], ...],
    *,
    mode: str,
    level: int | None,
    delay_percent: float,
    start: float,
    cycle: float,
    span: float,
    paragraph_build: str | None,
    reverse_order: bool = False,
    animate_background: bool = False,
    target_indices: tuple[int, ...] = (),
) -> tuple[TextBuildStage, ...]:
    """Schedule already-proved slices without recomputing layout or glyphs.

    ``units`` is the existing retained-slice grouping: target ID, source unit
    ID, and primitive indices. With ``paragraph_build='p'``, groups advance
    serially only after the last unit's full ``span``; inside each group word/
    letter starts are ``cycle * delay_percent / 100`` apart. Reversal changes
    paragraph group order, never the direction of units inside a paragraph.
    Paragraph-only builds use one span per group. Other supported declarations
    keep flat iteration. Empty/ambiguous memberships refuse, never infer.

    ``target_indices`` must be the qualified original shape target. With
    ``animate_background`` its non-text remainder becomes one separate stage
    at ``start``. Without it the remainder stays static. Callers install all
    returned targets before playback; the helper never mutates the slide.
    """
    from .slide_animation_behaviors import AnimationFrameRefusal

    def refuse(reason: str) -> None:
        raise AnimationFrameRefusal(f"text_build {identifier!r}: {reason}")

    if paragraph_build not in (None, "allAtOnce", "whole", "p"):
        refuse(f"unsupported paragraph build {paragraph_build!r}")
    if type(reverse_order) is not bool or type(animate_background) is not bool:
        refuse("paragraph reversal/background flags must be booleans")
    grouped = mode == "by_paragraph" or paragraph_build == "p"
    if grouped and level is None:
        level = 1
    if reverse_order and not grouped:
        refuse("paragraph reversal requires a paragraph build")
    for name, value in (("start", start), ("cycle", cycle), ("span", span)):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            refuse(f"{name} must be finite and non-negative")
    if (
        type(delay_percent) not in (int, float)
        or not math.isfinite(delay_percent)
        or not 0 <= delay_percent <= 100
    ):
        refuse("word/letter delay must be a percentage through 100")
    try:
        source, _, path = _source_build_labels(root, identifier, mode, level)
    except ValueError as exc:
        refuse(str(exc))
    memberships: dict[int, set[int]] = {}
    for character, unit, group in source:
        if not character.isspace():
            memberships.setdefault(unit, set()).add(group)
    if not units:
        refuse(f"no proven retained text units at {path}")
    groups: dict[int, list[tuple[str, int, tuple[int, ...]]]] = {}
    text_indices: set[int] = set()
    seen_units: set[int] = set()
    seen_targets: set[str] = set()
    for target, unit, indices in units:
        if (
            not isinstance(target, str)
            or not target
            or target == identifier
            or target in seen_targets
            or type(unit) is not int
            or unit < 0
            or unit in seen_units
        ):
            refuse("retained slice targets and source units must be unique")
        if (
            not indices
            or any(type(index) is not int or index < 0 for index in indices)
            or len(set(indices)) != len(indices)
            or text_indices.intersection(indices)
        ):
            refuse("retained text targets must have disjoint primitive indices")
        membership = memberships.get(unit, set())
        if len(membership) != 1:
            refuse(f"unit {unit} has no unambiguous paragraph membership at {path}")
        group = next(iter(membership)) if grouped else 0
        groups.setdefault(group, []).append((target, unit, indices))
        seen_targets.add(target)
        seen_units.add(unit)
        text_indices.update(indices)
    if any(type(index) is not int or index < 0 for index in target_indices) or len(
        set(target_indices)
    ) != len(target_indices):
        refuse("shape target indices must be unique non-negative integers")
    if animate_background and not text_indices.issubset(target_indices):
        refuse("background staging requires the complete qualified shape target")
    result: list[TextBuildStage] = []
    background = tuple(index for index in target_indices if index not in text_indices)
    if animate_background and background:
        background_target = f"{identifier}:text:background"
        if background_target in seen_targets:
            refuse("background target conflicts with a retained text target")
        result.append(TextBuildStage(background_target, None, None, background, start, True))
    interval = span if mode == "by_paragraph" else cycle * delay_percent / 100
    group_start = start
    for group in sorted(groups, reverse=reverse_order):
        ordered = sorted(groups[group], key=lambda entry: entry[1])
        for ordinal, (target, unit, indices) in enumerate(ordered):
            unit_start = group_start + ordinal * interval
            if not math.isfinite(unit_start) or not math.isfinite(unit_start + span):
                refuse("staged timeline duration must be finite")
            result.append(
                TextBuildStage(target, unit, group if grouped else None, indices, unit_start)
            )
        group_start += (len(ordered) - 1) * interval + span
    return tuple(result)
