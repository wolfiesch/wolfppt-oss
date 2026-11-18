"""Lossless slide animation save edits, including in-place timing options."""

import copy
import math
import shutil
import zipfile
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from . import slide_animation_xml as _xml
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .slide_animation_behaviors import SlideAnimationRefusalError
from .slide_animation_sequences import (
    SequenceMove,
    apply_sequence_moves,
    preflight_sequence_moves,
)
from .slide_animation_xml import (
    register_animation_namespaces as _register_animation_namespaces,
)
from .slide_animation_xml import (
    set_slide_animation_xml as _set_slide_animation_xml,
)
from .slide_payloads import load_slide_payloads as _load_slide_payloads


@dataclass
class AnimationSpec:
    """Specification for slide animation mutations.

    Represents the full cumulative pending edit state for a slide's animations.
    ``timing_updates`` patches restart/autoRev/accel/decel/fill by timing ID,
    preserving all other markup. Easing update strings use OOXML's 100000
    scale; added effects use fractional acceleration/deceleration instead.
    Added property behaviours are immutable validated objects, serialized
    only when the presentation saves.
    """

    clear_supported: bool = False
    removed_timing_ids: list[int] = field(default_factory=list)
    added_effects: list[dict[str, Any]] = field(default_factory=list)
    # Final order of supported main-sequence effects by outer cTn timing ID.
    # ``None`` keeps the saved order and appends added effects at the end.
    effect_order: list[int] | None = None
    # Existing effects are patched in place so timing/build/behaviour fields
    # outside the editable model remain unchanged.
    timing_updates: dict[int, dict[str, str | None]] = field(default_factory=dict)
    # Paragraph build declarations patch only the matching p:bldP entry.
    build_updates: dict[int, str | None] = field(default_factory=dict)
    # Public units for persistent effect-property edits, applied before sequence moves.
    effect_updates: dict[int, dict[str, Any]] = field(default_factory=dict)
    # Move supported main effects into bounded explicit shape-click sequences.
    sequence_moves: list[SequenceMove] = field(default_factory=list)


def _coerce_animation_spec(spec: Any) -> AnimationSpec:
    """Coerce input into an AnimationSpec."""
    if isinstance(spec, AnimationSpec):
        return spec
    if spec is None:
        return AnimationSpec(clear_supported=True)
    if isinstance(spec, dict):
        return AnimationSpec(**spec)
    raise TypeError(f"expected AnimationSpec or dict, got {type(spec).__name__}")


def apply_animation_spec(slide_root: ET.Element, spec: Any) -> None:
    """Validate/edit private XML and commit only its timing subtree once valid.

    Main-sequence mutations retain their existing semantics. Sequence requests
    preflight against saved state, then move the resulting effect elements and
    their unchanged build pairs. Any refusal leaves the caller's tree untouched.
    """
    spec = _coerce_animation_spec(spec)
    private = copy.deepcopy(slide_root)
    moves = preflight_sequence_moves(private, spec)
    if moves and spec.effect_order is not None:
        spec = copy.copy(spec)
        moved_ids = [timing_id for move in moves for timing_id in move.timing_ids]
        spec.effect_order = [
            *spec.effect_order,
            *(timing_id for timing_id in moved_ids if timing_id not in spec.effect_order),
        ]
    _set_slide_animation_xml(private, spec)
    apply_effect_property_updates(
        private,
        spec.effect_updates,
        reserved_id=max((move.sequence_id for move in moves), default=0),
    )
    apply_sequence_moves(private, moves)
    namespace = slide_root.tag.split("}", 1)[0] + "}" if "}" in slide_root.tag else ""
    timing_tag = namespace + "timing"
    original_timing = slide_root.find(timing_tag)
    new_timing = private.find(timing_tag)
    if original_timing is not None:
        index = list(slide_root).index(original_timing)
        slide_root.remove(original_timing)
        if new_timing is not None:
            slide_root.insert(index, new_timing)
    elif new_timing is not None:
        slide_root.insert(list(private).index(new_timing), new_timing)


def apply_slide_animation_edits(
    input_path: Path,
    output_path: Path,
    animation_edits: list[tuple[int | str, Any]] | dict[int | str, Any],
) -> None:
    """Apply queued slide animation edits to a presentation package.

    Consumes either a list of (slide_identifier, spec) pairs or a mapping.
    Slide identifiers may be 0-based integer indices or string part names
    (e.g. 'ppt/slides/slide1.xml').

    Preserves foreign animation groups and media timing under tmRoot.
    Never touches, modifies, or loses unrelated presentation parts.
    """
    slides = _load_slide_payloads(input_path)

    items: list[tuple[int | str, Any]]
    if isinstance(animation_edits, dict):
        items = list(animation_edits.items())
    else:
        items = list(animation_edits)

    edits_by_part: dict[str, AnimationSpec] = {}
    for identifier, raw_spec in items:
        spec = _coerce_animation_spec(raw_spec)
        if isinstance(identifier, int):
            try:
                part = str(slides[identifier]["part"])
            except IndexError:
                # If slide was deleted or out of range, skip
                continue
        elif isinstance(identifier, str):
            clean = identifier.strip().lstrip("/")
            part = clean
            for s in slides:
                s_part = str(s.get("part", "")).lstrip("/")
                if s_part == clean or s_part.endswith(clean):
                    part = str(s["part"])
                    break
        else:
            raise TypeError(f"slide identifier must be int or str, got {type(identifier).__name__}")
        edits_by_part[part] = spec

    if not edits_by_part:
        if input_path != output_path:
            shutil.copy2(input_path, output_path)
        return

    _register_animation_namespaces()
    replacements: dict[str, bytes] = {}

    with zipfile.ZipFile(input_path) as package:
        existing_parts = set(package.namelist())
        for slide_part, spec in edits_by_part.items():
            norm_part = slide_part.lstrip("/")
            if norm_part not in existing_parts:
                # Safely skip deleted or non-existent slide parts
                continue
            try:
                xml_bytes = package.read(norm_part)
            except KeyError:
                continue
            root = ET.fromstring(xml_bytes)
            apply_animation_spec(root, spec)
            replacements[norm_part] = ET.tostring(
                root,
                encoding="utf-8",
                xml_declaration=True,
            )

    _copy_package_with_replacements(input_path, output_path, replacements)


_EFFECT_PROPERTIES = frozenset(
    {
        "effect",
        "animation_class",
        "duration",
        "delay",
        "repeat_count",
        "rewind",
        "start",
        "text_build",
        "build_delay",
        "build_level",
        "preset_subtype",
        *_xml.PARAGRAPH_BUILD_OPTIONS,
    }
)
_P = f"{{{_xml.P_NS}}}"


def _seconds_ms(value: Any, name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SlideAnimationRefusalError(f"{name} must be a finite non-negative number")
    try:
        milliseconds = float(value) * 1000
        if value < 0 or not math.isfinite(milliseconds):
            raise ValueError
        return str(round(milliseconds))
    except (ValueError, OverflowError) as exc:
        raise SlideAnimationRefusalError(
            f"{name} must be a finite non-negative number of seconds"
        ) from exc


def _property_values(info: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Normalize public values without interpreting saved repeatDur as seconds."""
    values = dict(info)
    for name, value in updates.items():
        if name in {"effect", "animation_class", "start", "text_build"}:
            if not isinstance(value, str):
                raise SlideAnimationRefusalError(f"Invalid {name}: {value!r}")
            value = value.strip().lower()
        elif name in {"duration", "delay"}:
            _seconds_ms(value, name)
        elif name == "repeat_count":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise SlideAnimationRefusalError("repeat_count must be a positive integer")
        elif name == "rewind" and not isinstance(value, bool):
            raise SlideAnimationRefusalError("rewind must be a boolean")
        elif name == "preset_subtype":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SlideAnimationRefusalError("preset_subtype must be a supported integer")
        values[name] = value
    if values["animation_class"] not in _xml._PRESET_CLASS_BY_ANIMATION:
        raise SlideAnimationRefusalError("Unsupported animation_class")
    if values["start"] not in _xml.START_TO_NODE_TYPE:
        raise SlideAnimationRefusalError("Unsupported start condition")
    if values["text_build"] not in _xml.TEXT_BUILDS:
        raise SlideAnimationRefusalError("Unsupported text_build")
    if values["effect"] != info["effect"]:
        values.update(amount=None, color=None, color_target=None, direction=None)
        if "preset_subtype" not in updates:
            values["preset_subtype"] = int(
                "2"
                if values["effect"] == "color_change"
                else _xml.EFFECT_PRESET_SUBTYPES.get(values["effect"], "0")
            )
    if values["text_build"] not in _xml._ITERATE_TYPES and "build_delay" not in updates:
        values["build_delay"] = None
    if values["text_build"] == "as_one" and "build_level" not in updates:
        values["build_level"] = None
    if "preset_subtype" in updates:
        subtype = str(values["preset_subtype"])
        effect = values["effect"]
        if effect in {"fly", "wipe"}:
            subtypes = (
                _xml._FLY_DIRECTION_SUBTYPES if effect == "fly" else _xml._WIPE_DIRECTION_SUBTYPES
            )
            values["direction"] = next(
                (name for name, number in subtypes.items() if number == subtype), None
            )
            valid = values["direction"] is not None
        elif effect == "wheel":
            valid = values["preset_subtype"] in {1, 2, 3, 4, 8}
        else:
            valid = subtype == ("2" if effect == "color_change" else "0")
        if not valid or effect in {"custom", "motion_path"}:
            raise SlideAnimationRefusalError("Unsupported preset_subtype for this effect")
    options = _xml.coerce_effect_options(
        values["effect"], values["animation_class"], values, values.get("_target_kind")
    )
    values.update(options)
    return values


def _preset_template(info: dict[str, Any], alloc_id: Any) -> ET.Element:
    payload = {
        key: value
        for key, value in info.items()
        if key
        not in {
            "timing_markup",
            "build_markup",
            "repeat_duration",
            "behaviors",
            "paragraph_build",
        }
    }
    if info["effect"] in {"custom", "motion_path"}:
        payload["behaviors"] = info["behaviors"]
    group, _options = _xml._build_animation_group(payload, alloc_id, 0)
    node = group.find(f"{_P}cTn")
    if info["preset_subtype"] is not None:
        node.set("presetSubtype", str(info["preset_subtype"]))
    if info["effect"] == "wheel":
        node.find(f"{_P}childTnLst/{_P}animEffect").set(
            "filter", f"wheel({info['preset_subtype'] or 8})"
        )
    return node


def _behavior_key(node: ET.Element) -> tuple[str, tuple[str | None, ...]]:
    return node.tag, tuple(
        attr.text for attr in node.findall(f"{_P}cBhvr/{_P}attrNameLst/{_P}attrName")
    )


def _merge_behavior(target: ET.Element, before: ET.Element, after: ET.Element) -> None:
    """Patch modelled differences, retaining IDs, extra attributes and extensions."""
    for name in before.attrib.keys() | after.attrib.keys():
        if name == "id" or before.get(name) == after.get(name):
            continue
        if name in after.attrib:
            target.set(name, after.get(name))
        else:
            target.attrib.pop(name, None)
    if before.text != after.text:
        target.text = after.text
    old_children = list(before)
    new_children = list(after)
    remaining = list(target)
    for old in old_children:
        match = next((child for child in new_children if child.tag == old.tag), None)
        actual = next((child for child in remaining if child.tag == old.tag), None)
        if actual is not None:
            remaining.remove(actual)
            if match is None:
                target.remove(actual)
            else:
                _merge_behavior(actual, old, match)
        elif match is not None:
            target.append(copy.deepcopy(match))
        if match is not None:
            new_children.remove(match)
    for child in new_children:
        target.append(copy.deepcopy(child))


def _replace_preset_behaviors(node: ET.Element, before: ET.Element, after: ET.Element) -> None:
    children = node.find(f"{_P}childTnLst")
    old = list(before.find(f"{_P}childTnLst"))
    new = list(after.find(f"{_P}childTnLst"))
    legacy_motion = children.find(f"{_P}animMotion")
    if before.get("presetID") == "2" and legacy_motion is not None:
        old = [child for child in old if child.tag != f"{_P}anim"]
        old.append(copy.deepcopy(legacy_motion))
    remaining = list(children)
    insertion = 0
    retired_ids: list[str] = []
    for template in old:
        key = _behavior_key(template)
        actual = next((child for child in remaining if _behavior_key(child) == key), None)
        replacement = next((child for child in new if _behavior_key(child) == key), None)
        if actual is None:
            raise SlideAnimationRefusalError("Saved preset behavior cannot be edited losslessly")
        remaining.remove(actual)
        insertion = list(children).index(actual)
        if replacement is None:
            # Extensions on a retired behavior have no equivalent owner in the new preset.
            if actual.find(f".//{_P}extLst") is not None:
                raise SlideAnimationRefusalError("Cannot replace an extended preset behavior")
            retired_ids.extend(
                timing.get("id")
                for timing in actual.iter(f"{_P}cTn")
                if timing.get("id") is not None
            )
            children.remove(actual)
        else:
            _merge_behavior(actual, template, replacement)
            new.remove(replacement)
            insertion += 1
    for replacement in new:
        for timing in replacement.iter(f"{_P}cTn"):
            if retired_ids:
                timing.set("id", retired_ids.pop(0))
        children.insert(insertion, replacement)
        insertion += 1


def _patch_duration(
    node: ET.Element, info: dict[str, Any], values: dict[str, Any], alloc_id: Any
) -> None:
    duration = _seconds_ms(values["duration"], "duration")
    children = node.find(f"{_P}childTnLst")
    if info["effect"] == "custom":
        old_duration = round(info["duration"] * 1000)
        for child in children:
            timing = child.find(f"{_P}cBhvr/{_P}cTn")
            if timing is not None and (raw := timing.get("dur", "")).isdigit():
                timing.set(
                    "dur",
                    str(round(Fraction(int(raw) * int(duration), old_duration)))
                    if old_duration
                    else duration,
                )
    else:
        before = _preset_template(info, alloc_id).find(f"{_P}childTnLst")
        after = _preset_template(values, alloc_id).find(f"{_P}childTnLst")
        legacy_motion = children.find(f"{_P}animMotion")
        if info["effect"] == "fly" and legacy_motion is not None:
            for template, span in ((before, info["duration"]), (after, values["duration"])):
                for child in list(template):
                    if child.tag == f"{_P}anim":
                        template.remove(child)
                motion = copy.deepcopy(legacy_motion)
                motion.find(f"{_P}cBhvr/{_P}cTn").set("dur", _seconds_ms(span, "duration"))
                template.append(motion)
        remaining = list(children)
        for old, new in zip(before, after, strict=True):
            actual = next(
                (child for child in remaining if _behavior_key(child) == _behavior_key(old)), None
            )
            if actual is None:
                raise SlideAnimationRefusalError(
                    "Saved preset duration cannot be edited losslessly"
                )
            remaining.remove(actual)
            old_timing = old.find(f"{_P}cBhvr/{_P}cTn")
            new_timing = new.find(f"{_P}cBhvr/{_P}cTn")
            timing = actual.find(f"{_P}cBhvr/{_P}cTn")
            if timing is not None and old_timing is not None and new_timing is not None:
                _merge_behavior(timing, old_timing, new_timing)
    node.set("dur", duration)


def _patch_text_build(
    root: ET.Element, node: ET.Element, values: dict[str, Any], updates: dict[str, Any]
) -> None:
    iterate = node.find(f"{_P}iterate")
    mode = values["text_build"]
    if mode in _xml._ITERATE_TYPES:
        if iterate is None:
            iterate = ET.Element(f"{_P}iterate")
            node.insert(list(node).index(node.find(f"{_P}childTnLst")), iterate)
        iterate.set("type", _xml._ITERATE_TYPES[mode])
        percent = iterate.find(f"{_P}tmPct")
        if percent is None:
            percent = ET.SubElement(iterate, f"{_P}tmPct")
        percent.set("val", str(round(values["build_delay"] * 1000)))
    elif iterate is not None:
        node.remove(iterate)
    if not {"text_build", "build_level"} & updates.keys():
        return
    key = _xml._effect_build_key(node)
    timing = root.find(f"{_P}timing")
    builds = timing.find(f"{_P}bldLst")
    entries = (
        [entry for entry in builds if (entry.get("spid"), entry.get("grpId")) == key]
        if builds is not None
        else []
    )
    if key is None or len(entries) > 1 or any(entry.tag != f"{_P}bldP" for entry in entries):
        raise SlideAnimationRefusalError("Text build needs an unambiguous paragraph build entry")
    if not entries:
        if values["_target_kind"] != "text":
            if mode == "as_one":
                return
            raise SlideAnimationRefusalError("Text builds need a shape with text")
        if builds is None:
            builds = ET.SubElement(timing, f"{_P}bldLst")
        entry = ET.SubElement(builds, f"{_P}bldP", {"spid": key[0], "grpId": key[1]})
    else:
        entry = entries[0]
    if mode == "by_paragraph" or values["build_level"] is not None:
        entry.set("build", "p")
        entry.set("bldLvl", str(values["build_level"] or 1))
    else:
        entry.set("build", "allAtOnce")
        entry.attrib.pop("bldLvl", None)


def _click_group_spans(root: ET.Element) -> dict[ET.Element, list[int]]:
    spans = {}
    for main in root.iter(f"{_P}cTn"):
        if main.get("nodeType") == "mainSeq":
            for group in main.findall(f"{_P}childTnLst/{_P}par"):
                layout = _xml._click_group_layout(group)
                if layout is not None:
                    spans[group] = [
                        max(_xml._effect_span_ms(effect.find(f"{_P}cTn")) for effect in sub)
                        for sub in layout
                    ]
    return spans


def _refresh_click_layout(
    root: ET.Element, previous_spans: dict[ET.Element, list[int]], alloc_id: Any
) -> None:
    for main in root.iter(f"{_P}cTn"):
        if main.get("nodeType") != "mainSeq":
            continue
        children = main.find(f"{_P}childTnLst")
        if children is None:
            continue
        units = _xml._sequence_units(children)
        _xml._write_main_sequence(children, units, main.get("id"), alloc_id)
        for group in children:
            # Newly partitioned groups already have freshly computed offsets.
            # Reused groups keep authored spacing; shift only dependent starts.
            if group not in previous_spans:
                continue
            layout = _xml._click_group_layout(group)
            wrappers = group.find(f"{_P}cTn/{_P}childTnLst")
            delta = 0
            for wrapper, effects, old_span in zip(
                wrappers, layout, previous_spans[group], strict=True
            ):
                if delta:
                    condition = wrapper.find(f"{_P}cTn/{_P}stCondLst/{_P}cond")
                    raw = condition.get("delay", "") if condition is not None else ""
                    if not raw.isdigit() or int(raw) + delta < 0:
                        raise SlideAnimationRefusalError("Cannot update opaque click-group timing")
                    condition.set("delay", str(int(raw) + delta))
                delta += (
                    max(_xml._effect_span_ms(effect.find(f"{_P}cTn")) for effect in effects)
                    - old_span
                )


def _patch_paragraph_options(root: ET.Element, node: ET.Element, updates: dict[str, Any]) -> None:
    """Patch one effect/shape build pair without regenerating its timing."""
    key = _xml._effect_build_key(node)
    entries = [
        entry
        for entry in root.findall(f"{_P}timing/{_P}bldLst/{_P}bldP")
        if (entry.get("spid"), entry.get("grpId")) == key
    ]
    if len(entries) != 1:
        raise SlideAnimationRefusalError("Paragraph options need one matching p:bldP entry")
    for name, attribute in _xml.PARAGRAPH_BUILD_OPTIONS.items():
        if name not in updates:
            continue
        value = updates[name]
        if value is None:
            entries[0].attrib.pop(attribute, None)
        elif isinstance(value, bool):
            entries[0].set(attribute, "1" if value else "0")
        else:
            raise SlideAnimationRefusalError(
                f"Invalid {name}: {value!r} (must be a boolean or None)"
            )


def apply_effect_property_updates(
    root: ET.Element, updates: dict[int, dict[str, Any]], *, reserved_id: int = 0
) -> None:
    """Apply public property changes on the transaction's private Transitional tree."""
    if not isinstance(updates, dict):
        raise SlideAnimationRefusalError("effect_updates must be a mapping")
    if not updates:
        return
    if root.find(f"{{{_xml.STRICT_P_NS}}}timing") is not None:
        raise SlideAnimationRefusalError(
            "Cannot edit Strict animation timing; inspection is read-only"
        )
    effects = {
        info["timing_id"]: info for info in _xml.read_slide_animation_xml(root)["supported_effects"]
    }
    next_id = max(_xml.max_timing_id(root), reserved_id)

    def alloc_id() -> int:
        nonlocal next_id
        next_id += 1
        return next_id

    regroup: set[int] = set()
    previous_spans = _click_group_spans(root)
    for timing_id, changes in updates.items():
        if (
            isinstance(timing_id, bool)
            or not isinstance(timing_id, int)
            or timing_id not in effects
        ):
            raise SlideAnimationRefusalError("Cannot edit unsupported/foreign animation timing ID")
        if not isinstance(changes, dict) or not changes.keys() <= _EFFECT_PROPERTIES:
            raise SlideAnimationRefusalError("Unsupported animation property update")
        info = effects[timing_id]
        info["_target_kind"] = _xml.shape_build_kind(root, info["shape_id"])
        values = _property_values(info, changes)
        node = info["group_element"].find(f"{_P}cTn")
        replacement = bool({"effect", "animation_class", "preset_subtype"} & changes.keys())
        if replacement:
            before = _preset_template(info, alloc_id)
            after = _preset_template(values, alloc_id)
            _replace_preset_behaviors(node, before, after)
            for attr in ("presetClass", "presetID", "presetSubtype"):
                node.set(attr, after.get(attr))
        if "duration" in changes:
            _patch_duration(node, values if replacement else info, values, alloc_id)
        if "delay" in changes:
            conditions = node.find(f"{_P}stCondLst")
            if conditions is None:
                conditions = ET.Element(f"{_P}stCondLst")
                node.insert(0, conditions)
            condition = conditions.find(f"{_P}cond")
            if condition is None:
                condition = ET.SubElement(conditions, f"{_P}cond")
            condition.set("delay", _seconds_ms(values["delay"], "delay"))
        if "repeat_count" in changes:
            node.attrib.pop("repeatCount", None)
            if values["repeat_count"] != 1:
                node.set("repeatCount", str(values["repeat_count"] * 1000))
        if "rewind" in changes:
            node.attrib.pop("fill", None)
            if values["rewind"]:
                node.set("fill", "remove")
        if "start" in changes:
            node.set("nodeType", _xml.START_TO_NODE_TYPE[values["start"]])
        if {"text_build", "build_delay", "build_level"} & changes.keys():
            _patch_text_build(root, node, values, changes)
        if _xml.PARAGRAPH_BUILD_OPTIONS.keys() & changes.keys():
            if info["_target_kind"] != "text":
                raise SlideAnimationRefusalError("Paragraph options need a shape with text")
            _patch_paragraph_options(root, node, changes)
        if not _xml._inspect_effect_group(info["group_element"])[0]:
            raise SlideAnimationRefusalError("Property update would produce an unsupported effect")
        if {"start", "duration", "delay", "repeat_count"} & changes.keys():
            regroup.add(timing_id)
    if regroup:
        _refresh_click_layout(root, previous_spans, alloc_id)
