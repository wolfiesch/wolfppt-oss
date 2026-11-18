"""Open XML animation inspection and lossless property/restart authoring.

Property keyframes use the shared behaviour parser and serializer. Saved
restart/auto-reverse edits patch only their timing attributes; behaviour
replacements retain unrelated outer timing options and build markup.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

from .slide_animation_behaviors import (
    BehaviorFactory,
    MotionBehavior,
    MotionPath,
    RawBehavior,
    SlideAnimationRefusalError,
    append_behavior,
    coerce_acceleration_deceleration,
    coerce_behaviors,
    coerce_fill,
    coerce_restart,
    is_authorable,
    parse_behaviors,
)
from .slide_animation_emphasis import (
    _CHART_BUILD_BY_STEP,
    _DEFAULT_OPTIONS,
    _ITERATE_TYPES,
    _SCHEME_COLORS,
    AFTER_ANIMATIONS,
    CHART_BUILDS,
    COLOR_CHANGE_PRESET_IDS,
    EMPHASIS_DEFAULT_AMOUNTS,
    EMPHASIS_DEFAULT_DURATIONS,
    EMPHASIS_EFFECTS,
    EMPHASIS_PRESET_IDS,
    PARAGRAPH_BUILD_TYPES,
    TEXT_BUILDS,
    AnimationKeyframe,  # noqa: F401
    PropertyAnimation,  # noqa: F401
    _append_after_animation,
    _append_emphasis,
    _inspect_emphasis,
    _inspect_text_and_after,
    _property_animations,
    _shape_build_attributes,
)
from .slide_animation_text_builds import build_text_entry as _build_entry
from .xml_helpers import STRICT_A_NS, STRICT_P_NS, find_ooxml, xml_bool_value

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

START_TO_NODE_TYPE = {
    "on_click": "clickEffect",
    "with_previous": "withEffect",
    "after_previous": "afterEffect",
}

NODE_TYPE_TO_START = {
    "clickEffect": "on_click",
    "withEffect": "with_previous",
    "afterEffect": "after_previous",
}

EFFECT_PRESET_IDS = {
    "appear": 1,
    "fly": 2,
    "dissolve": 9,
    "fade": 10,
    "wheel": 21,
    "wipe": 22,
    "zoom": 23,
    "bounce": 26,
}
PRESET_ID_TO_EFFECT = {str(value): key for key, value in EFFECT_PRESET_IDS.items()}
EFFECT_FILTERS = {
    "dissolve": "dissolve",
    "fade": "fade",
    "wheel": "wheel(8)",
    "wipe": "wipe(down)",
}
EFFECT_PRESET_SUBTYPES = {
    "fly": "4",
    "wipe": "4",
    "wheel": "8",
}
# Fly names identify the off-slide edge; wipe names identify the filter sweep.
_FLY_DIRECTION_SUBTYPES = {"up": "1", "right": "2", "down": "4", "left": "8"}
_WIPE_DIRECTION_SUBTYPES = {"up": "4", "right": "8", "down": "1", "left": "2"}


def coerce_direction(effect: str, direction: Any) -> str | None:
    """Validate cardinal options without guessing semantics for other presets."""
    if direction is None:
        return None
    if effect not in {"fly", "wipe"}:
        raise SlideAnimationRefusalError("direction applies only to fly/wipe presets")
    if not isinstance(direction, str) or direction not in _FLY_DIRECTION_SUBTYPES:
        raise SlideAnimationRefusalError("Invalid direction: use left, right, up, or down")
    return direction


def coerce_repeat_duration(value: Any) -> str | None:
    """Convert bounded public seconds to OOXML milliseconds (or indefinite)."""
    if value is None or (isinstance(value, str) and value == "indefinite"):
        return value
    seconds = _coerce_number(value, "repeat_duration", 0.0, 2147483.647)
    return str(round(seconds * 1000))


def _read_easing(
    node: ET.Element, updates: dict[str, str | None] | None = None
) -> tuple[float | None, float | None]:
    values = []
    for name in ("accel", "decel"):
        raw = (updates or {}).get(name, node.get(name))
        if raw is not None and (
            not isinstance(raw, str) or not raw.isdigit() or not 0 <= int(raw) <= 100000
        ):
            raise SlideAnimationRefusalError(f"Unsupported animation {name}: {raw!r}")
        values.append(None if raw is None else int(raw) / 100000)
    return coerce_acceleration_deceleration(*values)


# Chart element index meaning "every series" / "every category" in a build step.
_CHART_ALL_INDEX = -3
_CHART_URI = "http://schemas.openxmlformats.org/drawingml/2006/chart"
MAX_BUILD_LEVEL = 5
# PowerPoint groups main-sequence effects as click group > sub-group > effect.
_CLICK_GROUP_NODE_TYPES = frozenset({None, "clickPar"})
_SUB_GROUP_NODE_TYPES = frozenset({None, "withGroup", "afterGroup"})
_GROUP_TIMING_CHILDREN = frozenset({"stCondLst", "childTnLst"})
_BUILD_ENTRY_TAGS = frozenset({"bldP", "bldDgm", "bldOleChart", "bldGraphic"})
_SHAPE_TAGS = frozenset({"sp", "pic", "graphicFrame", "grpSp", "cxnSp"})
# Custom effects (presetID 0) built only from modelled behaviours, by class.
CUSTOM_PRESET_CLASSES = {
    "entr": "entrance",
    "exit": "exit",
    "emph": "emphasis",
    "path": "motion_path",
}
_PRESET_CLASS_BY_ANIMATION = {value: key for key, value in CUSTOM_PRESET_CLASSES.items()}


def _xml_local_name(tag: str) -> str:
    """Return local name without XML namespace prefix."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def register_animation_namespaces() -> None:
    """Register PresentationML and DrawingML namespaces for ElementTree."""
    ET.register_namespace("p", P_NS)
    ET.register_namespace("a", A_NS)


def _find_tm_root(tn_lst: ET.Element) -> tuple[ET.Element | None, ET.Element | None]:
    """Locate the <p:par> and <p:cTn nodeType='tmRoot'> within <p:tnLst>.

    Searches across all children of tnLst so a non-first tmRoot is discovered.
    Falls back to a root par whose cTn has dur='indefinite' and restart='never'
    (the corpus_injections/simple_timing pattern), but never relabels foreign nodes.
    """
    for child in tn_lst:
        if _xml_local_name(child.tag) == "par":
            for ctn in child.findall(f"{{{P_NS}}}cTn"):
                if ctn.get("nodeType") == "tmRoot":
                    return child, ctn

    for child in tn_lst:
        if _xml_local_name(child.tag) == "par":
            ctn = child.find(f"{{{P_NS}}}cTn")
            if ctn is not None and ctn.get("dur") == "indefinite" and ctn.get("restart") == "never":
                return child, ctn

    return None, None


def _find_main_seq(
    child_tn_lst: ET.Element,
) -> tuple[ET.Element | None, ET.Element | None]:
    """Locate <p:seq> and its <p:cTn nodeType='mainSeq'> within childTnLst."""
    for child in child_tn_lst:
        if _xml_local_name(child.tag) == "seq":
            for ctn in child.findall(f"{{{P_NS}}}cTn"):
                if ctn.get("nodeType") == "mainSeq":
                    return child, ctn
    return None, None


def _can_remove_timing(timing_el: ET.Element) -> bool:
    """Determine whether <p:timing> is completely empty of animation/media/build content."""
    if timing_el.find(f"{{{P_NS}}}extLst") is not None:
        return False

    bld_lst = timing_el.find(f"{{{P_NS}}}bldLst")
    if bld_lst is not None and len(bld_lst) > 0:
        return False

    for child in timing_el:
        local = _xml_local_name(child.tag)
        if local not in {"tnLst", "bldLst"}:
            return False

    tn_lst = timing_el.find(f"{{{P_NS}}}tnLst")
    if tn_lst is None or len(tn_lst) == 0:
        return True

    if len(tn_lst) > 1:
        return False

    par = tn_lst[0]
    if _xml_local_name(par.tag) != "par" or len(par) > 1:
        return False
    if len(par) == 0:
        return True

    c_tn = par[0]
    if _xml_local_name(c_tn.tag) != "cTn":
        return False

    for child in c_tn:
        local = _xml_local_name(child.tag)
        if local == "childTnLst":
            if len(child) > 0:
                return False
        else:
            return False

    return True


def max_timing_id(slide_root: ET.Element) -> int:
    """Return highest integer id among all <p:cTn> elements in slide XML root."""
    highest = 0
    for ctn in slide_root.iter(f"{{{P_NS}}}cTn"):
        raw = ctn.get("id")
        if raw is not None and raw.isdigit():
            highest = max(highest, int(raw))
    return highest


def _parse_motion_path(path: str | None) -> tuple[tuple[float, float], ...] | None:
    if not path:
        return None
    tokens = path.split()
    if len(tokens) < 6 or tokens[0] != "M" or tokens[-1] != "E":
        return None
    points: list[tuple[float, float]] = []
    index = 0
    try:
        while index < len(tokens) - 1:
            if tokens[index] not in {"M", "L"}:
                return None
            x = float(tokens[index + 1])
            y = float(tokens[index + 2])
            if not (float("-inf") < x < float("inf") and float("-inf") < y < float("inf")):
                return None
            points.append((x, y))
            index += 3
    except (IndexError, ValueError):
        return None
    return tuple(points) if len(points) >= 2 else None


def _is_motion_path(behaviors: tuple[Any, ...]) -> bool:
    """A single modelled animMotion with a path: an editable motion path effect."""
    return (
        len(behaviors) == 1
        and isinstance(behaviors[0], MotionBehavior)
        and behaviors[0].path is not None
    )


def _inspect_effect_group(group_el: ET.Element) -> tuple[bool, dict[str, Any]]:
    """Classify one effect par (flat or nested in a click group) as editable or foreign."""
    if _xml_local_name(group_el.tag) != "par":
        return False, {
            "timing_id": None,
            "preset_class": None,
            "preset_id": None,
            "node_type": None,
            "shape_id": None,
            "name": _xml_local_name(group_el.tag),
            "raw_element": group_el,
        }

    c_tn = group_el.find(f"{{{P_NS}}}cTn")
    if c_tn is None:
        return False, {
            "timing_id": None,
            "preset_class": None,
            "preset_id": None,
            "node_type": None,
            "shape_id": None,
            "name": "par_without_cTn",
            "raw_element": group_el,
        }

    raw_id = c_tn.get("id")
    timing_id = int(raw_id) if raw_id and raw_id.isdigit() else None
    preset_class = c_tn.get("presetClass")
    preset_id = c_tn.get("presetID")
    node_type = c_tn.get("nodeType")
    spids = [
        target.get("spid")
        for target in group_el.findall(f".//{{{P_NS}}}spTgt")
        if target.get("spid") is not None
    ]
    unique_spids = sorted(set(spids))
    target_shape_id = unique_spids[0] if len(unique_spids) == 1 else None
    child_tn_lst = c_tn.find(f"{{{P_NS}}}childTnLst")
    behaviors = parse_behaviors(child_tn_lst)

    effect: str | None = None
    animation_class: str | None = None
    path: tuple[tuple[float, float], ...] | None = None
    direction: str | None = None
    is_supported = (
        timing_id is not None
        and node_type in NODE_TYPE_TO_START
        and target_shape_id is not None
        and child_tn_lst is not None
    )
    if is_supported and preset_class == "path" and preset_id == "0":
        motion = child_tn_lst.find(f"{{{P_NS}}}animMotion")
        path = _parse_motion_path(motion.get("path") if motion is not None else None)
        if (
            path is not None and motion is not None and motion.get("origin") == "layout"
        ) or _is_motion_path(behaviors):
            effect = "motion_path"
            animation_class = "motion_path"
        elif is_authorable(behaviors):
            effect = "custom"
            animation_class = "motion_path"
        else:
            is_supported = False
    elif (
        is_supported
        and preset_id == "0"
        and preset_class in CUSTOM_PRESET_CLASSES
        and is_authorable(behaviors)
    ):
        effect = "custom"
        animation_class = CUSTOM_PRESET_CLASSES[preset_class]
    elif is_supported and preset_class in {"entr", "exit"}:
        effect = PRESET_ID_TO_EFFECT.get(preset_id or "")
        animation_class = "entrance" if preset_class == "entr" else "exit"
        if effect is None or (effect == "appear" and animation_class != "entrance"):
            is_supported = False
        elif effect == "appear":
            set_el = child_tn_lst.find(f"{{{P_NS}}}set")
            attr = set_el.find(f".//{{{P_NS}}}attrName") if set_el is not None else None
            is_supported = attr is not None and attr.text == "style.visibility"
        elif effect in EFFECT_FILTERS:
            anim = child_tn_lst.find(f"{{{P_NS}}}animEffect")
            transition = "in" if animation_class == "entrance" else "out"
            filter_name = anim.get("filter") if anim is not None else None
            if effect == "wipe" and filter_name in {
                f"wipe({value})" for value in _FLY_DIRECTION_SUBTYPES
            }:
                direction = filter_name[5:-1]
            is_supported = (
                anim is not None
                and anim.get("transition") == transition
                and (
                    direction is not None
                    if effect == "wipe"
                    else filter_name in {f"wheel({spokes})" for spokes in (1, 2, 3, 4, 8)}
                    if effect == "wheel"
                    else filter_name == EFFECT_FILTERS[effect]
                )
            )
        elif effect == "zoom":
            is_supported = child_tn_lst.find(f"{{{P_NS}}}animScale") is not None
        elif effect == "fly":
            # PowerPoint's ppt_x/ppt_y anim pair; older WolfPPT saves used animMotion.
            is_supported = child_tn_lst.find(
                f"{{{P_NS}}}animMotion"
            ) is not None or _fly_anim_attributes(child_tn_lst) == ["ppt_x", "ppt_y"]
            direction = next(
                (
                    name
                    for name, subtype in _FLY_DIRECTION_SUBTYPES.items()
                    if subtype == c_tn.get("presetSubtype")
                ),
                None,
            )
        elif effect == "bounce":
            is_supported = child_tn_lst.find(f"{{{P_NS}}}animMotion") is not None
        else:
            is_supported = False
    elif is_supported and preset_class == "emph":
        emphasis = _inspect_emphasis(preset_id, child_tn_lst)
        if emphasis is None:
            is_supported = False
        else:
            effect = emphasis[0]
            animation_class = "emphasis"
    else:
        is_supported = False

    options: dict[str, Any] = {}
    if is_supported and effect is not None:
        text_and_after = _inspect_text_and_after(c_tn)
        if text_and_after is None:
            is_supported = False
        else:
            options = {**_DEFAULT_OPTIONS, **text_and_after}
            emphasis = (
                _inspect_emphasis(preset_id, child_tn_lst)
                if animation_class == "emphasis"
                else None
            )
            if emphasis is not None:
                options.update(emphasis[1])

    if effect == "fly" and child_tn_lst is not None:
        # Keep the established read-only fly inspection contract. Custom
        # expression-valued property animations remain editable.
        behaviors = tuple(
            RawBehavior("anim", _markup(child))
            if _xml_local_name(child.tag) == "anim"
            else behavior
            for child, behavior in zip(child_tn_lst, behaviors, strict=True)
        )
    if is_supported and effect is not None and animation_class is not None:
        delay = 0.0
        cond = c_tn.find(f"{{{P_NS}}}stCondLst/{{{P_NS}}}cond")
        if cond is not None and (delay_raw := cond.get("delay")) and delay_raw.isdigit():
            delay = float(delay_raw) / 1000.0
        duration = 0.0 if effect == "appear" else 0.5
        duration_raw = c_tn.get("dur")
        if duration_raw is None:
            inner = child_tn_lst.find(f".//{{{P_NS}}}cTn")
            duration_raw = inner.get("dur") if inner is not None else None
        if duration_raw and duration_raw.isdigit():
            duration = float(duration_raw) / 1000.0
        repeat_count = 1
        repeat_raw = c_tn.get("repeatCount")
        if repeat_raw and repeat_raw.isdigit() and int(repeat_raw) >= 1000:
            if int(repeat_raw) % 1000 == 0:
                repeat_count = int(repeat_raw) // 1000
            else:
                is_supported = False
        auto_reverse = False
        if (auto_reverse_raw := c_tn.get("autoRev")) is not None:
            if auto_reverse_raw.casefold() in {"1", "true"}:
                auto_reverse = True
            elif auto_reverse_raw.casefold() not in {"0", "false"}:
                is_supported = False
        try:
            acceleration, deceleration = _read_easing(c_tn)
        except SlideAnimationRefusalError:
            is_supported = False
        if is_supported:
            return True, {
                "timing_id": timing_id,
                "shape_id": int(target_shape_id) if target_shape_id.isdigit() else target_shape_id,
                "effect": effect,
                "animation_class": animation_class,
                "start": NODE_TYPE_TO_START[node_type],
                "delay": delay,
                "duration": duration,
                "repeat_count": repeat_count,
                "rewind": c_tn.get("fill") == "remove",
                "auto_reverse": auto_reverse,
                "path": path,
                "preset_subtype": int(c_tn.get("presetSubtype"))
                if (c_tn.get("presetSubtype") or "").isdigit()
                else None,
                "repeat_duration": c_tn.get("repeatDur"),
                "acceleration": acceleration,
                "deceleration": deceleration,
                "direction": direction,
                "restart": c_tn.get("restart"),
                "fill": c_tn.get("fill"),
                **options,
                "behaviors": behaviors,
                "group_element": group_el,
            }

    desc = f"{preset_class or 'custom'}_{preset_id or 'unknown'}"
    if node_type:
        desc = f"{node_type}_{desc}"
    return False, {
        "timing_id": timing_id,
        "preset_class": preset_class,
        "preset_id": preset_id,
        "node_type": node_type,
        "shape_id": int(target_shape_id)
        if (target_shape_id and target_shape_id.isdigit())
        else target_shape_id,
        "name": desc,
        "raw_element": group_el,
    }


def _is_effect_par(element: ET.Element) -> bool:
    """True for a <p:par> whose cTn is a click, with, or after effect node."""
    if _xml_local_name(element.tag) != "par":
        return False
    c_tn = element.find(f"{{{P_NS}}}cTn")
    return c_tn is not None and c_tn.get("nodeType") in NODE_TYPE_TO_START


def _group_timing_children(
    element: ET.Element, node_types: frozenset[str | None]
) -> list[ET.Element] | None:
    """Children of a PowerPoint grouping <p:par>, or None if it is not one."""
    if _xml_local_name(element.tag) != "par" or len(element) != 1:
        return None
    c_tn = element[0]
    if (
        _xml_local_name(c_tn.tag) != "cTn"
        or c_tn.get("presetClass") is not None
        or c_tn.get("nodeType") not in node_types
        or any(_xml_local_name(child.tag) not in _GROUP_TIMING_CHILDREN for child in c_tn)
    ):
        return None
    child_tn_lst = c_tn.find(f"{{{P_NS}}}childTnLst")
    if child_tn_lst is None or len(child_tn_lst) == 0:
        return None
    return list(child_tn_lst)


def _click_group_layout(element: ET.Element) -> list[list[ET.Element]] | None:
    """Effect pars per sub-group when ``element`` is a PowerPoint click group."""
    sub_groups = _group_timing_children(element, _CLICK_GROUP_NODE_TYPES)
    if sub_groups is None:
        return None
    conditions = element[0].findall(f"{{{P_NS}}}stCondLst/{{{P_NS}}}cond")
    if not any(cond.get("delay") == "indefinite" for cond in conditions):
        return None
    layout: list[list[ET.Element]] = []
    for sub_group in sub_groups:
        effects = _group_timing_children(sub_group, _SUB_GROUP_NODE_TYPES)
        if effects is None or not all(_is_effect_par(effect) for effect in effects):
            return None
        layout.append(effects)
    return layout


def _is_auto_start_group(click_group: ET.Element) -> bool:
    return any(
        cond.get("evt") == "onBegin"
        for cond in click_group[0].findall(f"{{{P_NS}}}stCondLst/{{{P_NS}}}cond")
    )


@dataclass
class _SequenceUnit:
    """One main-sequence entry: an effect par, or an opaque foreign node.

    Effect units remember the PowerPoint click group they were loaded from and
    that group's partition, so an unchanged group is written back as-is.
    """

    element: ET.Element
    is_effect: bool
    supported: bool
    info: dict[str, Any] = field(default_factory=dict)
    click_group: ET.Element | None = None
    layout: tuple[tuple[int, ...], ...] | None = None
    build_request: dict[str, Any] | None = None

    @property
    def node_type(self) -> str | None:
        c_tn = self.element.find(f"{{{P_NS}}}cTn")
        return c_tn.get("nodeType") if c_tn is not None else None


def _sequence_units(main_child_tn_lst: ET.Element) -> list[_SequenceUnit]:
    """Flatten the main sequence into effect units in playback order.

    PowerPoint click groups contribute each nested effect par. A legacy flat
    effect par is an effect unit when supported; any other node (including a
    flat foreign effect or an unrecognized group) stays an opaque unit.
    """
    units: list[_SequenceUnit] = []
    for child in main_child_tn_lst:
        layout = _click_group_layout(child)
        if layout is not None:
            key = tuple(tuple(id(effect) for effect in sub) for sub in layout)
            for sub in layout:
                for effect_par in sub:
                    supported, info = _inspect_effect_group(effect_par)
                    units.append(_SequenceUnit(effect_par, True, supported, info, child, key))
            continue
        supported, info = _inspect_effect_group(child)
        units.append(_SequenceUnit(child, supported, supported, info))
    return units


def _read_strict_animation_xml(timing: ET.Element) -> dict[str, Any]:
    """Inspect a private timing copy; retain original Strict elements and markup.

    The shared behaviour and emphasis parsers consume Transitional names. Adapt
    only the two standard namespace pairs on a copy, never the package tree or
    foreign namespaces. Public raw markup remains in its authored profile.
    """
    normalized = copy.deepcopy(timing)
    originals = dict(zip(normalized.iter(), timing.iter(), strict=True))
    namespaces = {STRICT_P_NS: P_NS, STRICT_A_NS: A_NS}
    for element in normalized.iter():
        for strict, transitional in namespaces.items():
            prefix = f"{{{strict}}}"
            if element.tag.startswith(prefix):
                element.tag = f"{{{transitional}}}" + element.tag[len(prefix) :]
            for attribute in list(element.attrib):
                if attribute.startswith(prefix):
                    element.set(
                        f"{{{transitional}}}" + attribute[len(prefix) :],
                        element.attrib.pop(attribute),
                    )
    root = ET.Element(f"{{{P_NS}}}sld")
    root.append(normalized)
    result = read_slide_animation_xml(root)
    builds = normalized.find(f"{{{P_NS}}}bldLst")
    entries: dict[tuple[str | None, str | None], ET.Element] = {}
    for entry in builds if builds is not None else ():
        if _xml_local_name(entry.tag) in _BUILD_ENTRY_TAGS:
            entries.setdefault((entry.get("spid"), entry.get("grpId")), entry)
    for info in result["supported_effects"] + result["unsupported_effects"]:
        key = "group_element" if "group_element" in info else "raw_element"
        group = info[key]
        info[key] = originals[group]
        children = group.find(f"{{{P_NS}}}cTn/{{{P_NS}}}childTnLst")
        info["behaviors"] = tuple(
            RawBehavior(behavior.tag, _markup(originals[child]))
            if isinstance(behavior, RawBehavior)
            else behavior
            for behavior, child in zip(
                info["behaviors"], children if children is not None else (), strict=True
            )
        )
        if key == "group_element":
            info["timing_markup"] = _markup(originals[group])
            entry = entries.get(_effect_build_key(group.find(f"{{{P_NS}}}cTn")))
            info["build_markup"] = _markup(originals[entry]) if entry is not None else None
    return result


def read_slide_animation_xml(slide_root: ET.Element) -> dict[str, Any]:
    """Inspect and extract animation properties and effect groups from a slide XML root."""
    timing_el = find_ooxml(slide_root, f"{{{P_NS}}}timing")
    if timing_el is not None and timing_el.tag == f"{{{STRICT_P_NS}}}timing":
        return _read_strict_animation_xml(timing_el)
    if timing_el is None:
        return {
            "has_timing": False,
            "has_tm_root": False,
            "has_main_seq": False,
            "has_animations": False,
            "supported_effects": [],
            "unsupported_effects": [],
            "media_node_count": 0,
            "max_timing_id": 0,
        }

    max_id = max_timing_id(slide_root)
    tn_lst = timing_el.find(f"{{{P_NS}}}tnLst")
    if tn_lst is None:
        return {
            "has_timing": True,
            "has_tm_root": False,
            "has_main_seq": False,
            "has_animations": False,
            "supported_effects": [],
            "unsupported_effects": [],
            "media_node_count": 0,
            "max_timing_id": max_id,
        }

    _par_root, c_tn_root = _find_tm_root(tn_lst)
    if c_tn_root is None:
        return {
            "has_timing": True,
            "has_tm_root": False,
            "has_main_seq": False,
            "has_animations": False,
            "supported_effects": [],
            "unsupported_effects": [],
            "media_node_count": 0,
            "max_timing_id": max_id,
        }

    child_tn_lst = c_tn_root.find(f"{{{P_NS}}}childTnLst")
    if child_tn_lst is None:
        # tmRoot without childTnLst (e.g. simple_timing.pptx fixture)
        return {
            "has_timing": True,
            "has_tm_root": True,
            "has_main_seq": False,
            "has_animations": False,
            "supported_effects": [],
            "unsupported_effects": [],
            "media_node_count": 0,
            "max_timing_id": max_id,
        }

    media_nodes: list[ET.Element] = []
    media_nodes = [c for c in child_tn_lst if _xml_local_name(c.tag) in {"video", "audio"}]
    seq_el, main_c_tn = _find_main_seq(child_tn_lst)
    if seq_el is None or main_c_tn is None:
        return {
            "has_timing": True,
            "has_tm_root": True,
            "has_main_seq": False,
            "has_animations": False,
            "supported_effects": [],
            "unsupported_effects": [],
            "media_node_count": len(media_nodes),
            "max_timing_id": max_id,
        }

    main_child_tn_lst = main_c_tn.find(f"{{{P_NS}}}childTnLst")
    if main_child_tn_lst is None:
        return {
            "has_timing": True,
            "has_tm_root": True,
            "has_main_seq": True,
            "has_animations": False,
            "supported_effects": [],
            "unsupported_effects": [],
            "media_node_count": len(media_nodes),
            "max_timing_id": max_id,
        }

    supported_effects: list[dict[str, Any]] = []
    unsupported_effects: list[dict[str, Any]] = []

    for unit in _sequence_units(main_child_tn_lst):
        if unit.supported:
            supported_effects.append(unit.info)
        else:
            unsupported_effects.append(unit.info)
    _attach_listing(timing_el, supported_effects, unsupported_effects)

    return {
        "has_timing": True,
        "has_tm_root": True,
        "has_main_seq": True,
        "has_animations": bool(supported_effects or unsupported_effects),
        "supported_effects": supported_effects,
        "unsupported_effects": unsupported_effects,
        "media_node_count": len(media_nodes),
        "max_timing_id": max_id,
    }


def _insert_slide_timing_element(slide_root: ET.Element, timing_element: ET.Element) -> None:
    """Insert <p:timing> in PresentationML schema-compliant order.

    CT_Slide sequence:
      1. cSld (required)
      2. EG_SlideLifeCycleAdditions (optional)
      3. clrMapOvr (optional)
      4. transition (optional)
      5. timing (optional)
      6. extLst (optional)

    <p:timing> must be placed after <p:transition> and before <p:extLst>.
    """
    children = list(slide_root)
    insert_at = len(children)
    for index, child in enumerate(children):
        local_name = _xml_local_name(child.tag)
        if local_name == "extLst":
            insert_at = index
            break
    slide_root.insert(insert_at, timing_element)


def _coerce_motion_coordinates(value: Any) -> tuple[tuple[float, float], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise SlideAnimationRefusalError(
            "Motion path coordinates must be a sequence of coordinate pairs"
        )
    points: list[tuple[float, float]] = []
    for coordinate in value:
        if (
            isinstance(coordinate, (str, bytes))
            or not isinstance(coordinate, (list, tuple))
            or len(coordinate) != 2
        ):
            raise SlideAnimationRefusalError(
                "Motion path coordinates must contain two-item coordinate pairs"
            )
        x, y = coordinate
        if isinstance(x, bool) or isinstance(y, bool):
            raise SlideAnimationRefusalError("Motion path coordinates must be numeric")
        try:
            x_value, y_value = float(x), float(y)
        except (TypeError, ValueError) as exc:
            raise SlideAnimationRefusalError("Motion path coordinates must be numeric") from exc
        if not (float("-inf") < x_value < float("inf") and float("-inf") < y_value < float("inf")):
            raise SlideAnimationRefusalError("Motion path coordinates must be finite numbers")
        points.append((x_value, y_value))
    if len(points) < 2:
        raise SlideAnimationRefusalError("Motion path coordinates must contain at least two pairs")
    return tuple(points)


def _append_common_behavior(
    parent: ET.Element,
    shape_id: str,
    duration_ms: str,
    alloc_id: Any,
    *,
    attr_names: tuple[str, ...] = (),
) -> None:
    behavior = ET.SubElement(parent, f"{{{P_NS}}}cBhvr")
    ET.SubElement(
        behavior,
        f"{{{P_NS}}}cTn",
        {"id": str(alloc_id()), "dur": duration_ms, "fill": "hold"},
    )
    target = ET.SubElement(behavior, f"{{{P_NS}}}tgtEl")
    ET.SubElement(target, f"{{{P_NS}}}spTgt", {"spid": shape_id})
    if attr_names:
        attr_list = ET.SubElement(behavior, f"{{{P_NS}}}attrNameLst")
        for attr_name in attr_names:
            ET.SubElement(attr_list, f"{{{P_NS}}}attrName").text = attr_name


def _append_visibility_set(
    parent: ET.Element,
    shape_id: str,
    value: str,
    delay_ms: str,
    alloc_id: Any,
) -> None:
    set_el = ET.SubElement(parent, f"{{{P_NS}}}set")
    behavior = ET.SubElement(set_el, f"{{{P_NS}}}cBhvr")
    inner = ET.SubElement(
        behavior,
        f"{{{P_NS}}}cTn",
        {"id": str(alloc_id()), "dur": "1", "fill": "hold"},
    )
    conditions = ET.SubElement(inner, f"{{{P_NS}}}stCondLst")
    ET.SubElement(conditions, f"{{{P_NS}}}cond", {"delay": delay_ms})
    target = ET.SubElement(behavior, f"{{{P_NS}}}tgtEl")
    ET.SubElement(target, f"{{{P_NS}}}spTgt", {"spid": shape_id})
    attr_list = ET.SubElement(behavior, f"{{{P_NS}}}attrNameLst")
    ET.SubElement(attr_list, f"{{{P_NS}}}attrName").text = "style.visibility"
    to_el = ET.SubElement(set_el, f"{{{P_NS}}}to")
    ET.SubElement(to_el, f"{{{P_NS}}}strVal", {"val": value})


def _append_motion(
    parent: ET.Element,
    shape_id: str,
    duration_ms: str,
    points: tuple[tuple[float, float], ...],
    alloc_id: Any,
) -> None:
    """Layout-relative animMotion with PowerPoint's rotation angle and center."""
    path = MotionPath().move_to(*points[0])
    for x, y in points[1:]:
        path = path.line_to(x, y)
    append_behavior(parent, BehaviorFactory().create_motion(path), shape_id, duration_ms, alloc_id)


def _fly_anim_attributes(child_tn_lst: ET.Element) -> list[str]:
    """Animated attribute names of the direct <p:anim> behaviors, in order."""
    return [
        attr.text or ""
        for anim in child_tn_lst.findall(f"{{{P_NS}}}anim")
        for attr in anim.findall(f"{{{P_NS}}}cBhvr/{{{P_NS}}}attrNameLst/{{{P_NS}}}attrName")
    ]


def _append_fly(
    parent: ET.Element,
    shape_id: str,
    duration_ms: str,
    entrance: bool,
    alloc_id: Any,
    direction: str = "down",
) -> None:
    """Fly from/to a cardinal slide edge using ppt_x/ppt_y property keys.

    As an animMotion path, fly draws a path guide past the slide edge, and
    PowerPoint for Mac keeps redrawing the editing view while such a guide is
    shown. PowerPoint's own ppt_x/ppt_y property animations draw no guide.
    """
    prefix = "#" if entrance else ""
    x, y, w, h = (f"{prefix}ppt_{name}" for name in "xywh")
    outside = {
        "down": (x, f"1+{h}/2"),
        "up": (x, f"-{h}/2"),
        "left": (f"-{w}/2", y),
        "right": (f"1+{w}/2", y),
    }[direction]
    values = tuple(
        (f"ppt_{name}", edge if entrance else base, base if entrance else edge)
        for name, base, edge in zip("xy", (x, y), outside, strict=True)
    )
    for attr_name, start_value, end_value in values:
        anim = ET.SubElement(parent, f"{{{P_NS}}}anim", {"calcmode": "lin", "valueType": "num"})
        behavior = ET.SubElement(anim, f"{{{P_NS}}}cBhvr", {"additive": "base"})
        timing = {"id": str(alloc_id()), "dur": duration_ms}
        if entrance:
            timing["fill"] = "hold"
        ET.SubElement(behavior, f"{{{P_NS}}}cTn", timing)
        target = ET.SubElement(behavior, f"{{{P_NS}}}tgtEl")
        ET.SubElement(target, f"{{{P_NS}}}spTgt", {"spid": shape_id})
        attr_list = ET.SubElement(behavior, f"{{{P_NS}}}attrNameLst")
        ET.SubElement(attr_list, f"{{{P_NS}}}attrName").text = attr_name
        values_el = ET.SubElement(anim, f"{{{P_NS}}}tavLst")
        for tm, value in (("0", start_value), ("100000", end_value)):
            tav = ET.SubElement(values_el, f"{{{P_NS}}}tav", {"tm": tm})
            val = ET.SubElement(tav, f"{{{P_NS}}}val")
            ET.SubElement(val, f"{{{P_NS}}}strVal", {"val": value})


def _attach_listing(
    timing_el: ET.Element,
    supported: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
) -> None:
    """Add markup, build options, and property animations to effect listings."""
    entries: dict[tuple[str | None, str | None], ET.Element] = {}
    bld_lst = timing_el.find(f"{{{P_NS}}}bldLst")
    for entry in bld_lst if bld_lst is not None else ():
        if _xml_local_name(entry.tag) in _BUILD_ENTRY_TAGS:
            entries.setdefault((entry.get("spid"), entry.get("grpId")), entry)
    for info in supported:
        group = info["group_element"]
        key = _effect_build_key(group.find(f"{{{P_NS}}}cTn"))
        entry = entries.get(key) if key is not None else None
        info["timing_markup"] = _markup(group)
        info["build_markup"] = _markup(entry) if entry is not None else None
        info["property_animations"] = _property_animations(group)
        if entry is None:
            continue
        tag = _xml_local_name(entry.tag)
        if tag == "bldP":
            info["paragraph_build"] = entry.get("build")
            info["animate_background"] = xml_bool_value(entry.get("animBg"), False)
            info["reverse_order"] = xml_bool_value(entry.get("rev"), False)
            info["auto_update_background"] = xml_bool_value(entry.get("autoUpdateAnimBg"), True)
        if tag == "bldP" and entry.get("build") == "p":
            level = entry.get("bldLvl", "1")
            info["build_level"] = int(level) if level.isdigit() else 1
            if info.get("text_build") == "as_one":
                info["text_build"] = "by_paragraph"
        chart = entry.find(f"{{{P_NS}}}bldSub/{{{A_NS}}}bldChart")
        if tag == "bldGraphic" and chart is not None:
            info["chart_build"] = _CHART_BUILD_BY_STEP.get(chart.get("bld", ""), "as_one")
    for info in unsupported:
        raw = info["raw_element"]
        info["property_animations"] = _property_animations(raw)
        info["behaviors"] = parse_behaviors(raw.find(f"{{{P_NS}}}cTn/{{{P_NS}}}childTnLst"))


def _markup(element: ET.Element) -> str:
    """Serialized element without its tail text."""
    clone = copy.copy(element)
    clone.tail = None
    return ET.tostring(clone, encoding="unicode")


def shape_build_kind(slide_root: ET.Element, shape_id: Any) -> str | None:
    """``text`` for a text-bearing p:sp, ``chart`` for a chart frame, else other."""
    target = str(shape_id)
    for element in slide_root.iter():
        name = _xml_local_name(element.tag)
        if name not in _SHAPE_TAGS or len(element) == 0:
            continue
        c_nv_pr = element[0].find(f"{{{P_NS}}}cNvPr")
        if c_nv_pr is None or c_nv_pr.get("id") != target:
            continue
        if name == "sp" and element.find(f"{{{P_NS}}}txBody") is not None:
            return "text"
        data = element.find(f"{{{A_NS}}}graphic/{{{A_NS}}}graphicData")
        if name == "graphicFrame" and data is not None and data.get("uri") == _CHART_URI:
            return "chart"
        return "other"
    return None


def _coerce_color(value: Any, name: str) -> str:
    if isinstance(value, str):
        clean = value.strip().removeprefix("#")
        if clean in _SCHEME_COLORS:
            return clean
        if len(clean) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in clean):
            return clean.upper()
    raise SlideAnimationRefusalError(
        f"Invalid {name}: {value!r} (use RRGGBB hex or a scheme colour name such as 'accent2')"
    )


def _coerce_number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise SlideAnimationRefusalError(
            f"Invalid {name}: {value!r} (must be a number from {low:g} to {high:g})"
        )
    return float(value)


PARAGRAPH_BUILD_OPTIONS = {
    "animate_background": "animBg",
    "reverse_order": "rev",
    "auto_update_background": "autoUpdateAnimBg",
}


def coerce_effect_options(
    effect: str,
    animation_class: str,
    options: dict[str, Any],
    target_kind: str | None = None,
) -> dict[str, Any]:
    """Validate emphasis, text build, after-animation, and chart build options.

    ``target_kind`` (from :func:`shape_build_kind`) refuses a text build on a
    shape without text and a chart build on a shape that is not a chart.
    """
    text_build = options.get("text_build") or "as_one"
    if text_build not in TEXT_BUILDS:
        raise SlideAnimationRefusalError(
            f"Invalid text_build: {text_build!r} (use one of {', '.join(TEXT_BUILDS)})"
        )
    build_level = options.get("build_level")
    if text_build == "by_paragraph" or (text_build in _ITERATE_TYPES and build_level is not None):
        build_level = 1 if build_level is None else build_level
        if (
            isinstance(build_level, bool)
            or not isinstance(build_level, int)
            or not 1 <= build_level <= MAX_BUILD_LEVEL
        ):
            raise SlideAnimationRefusalError(
                f"Invalid build_level: {build_level!r} (must be 1 to {MAX_BUILD_LEVEL})"
            )
    elif build_level is not None:
        raise SlideAnimationRefusalError("build_level applies only to paragraph/word/letter builds")
    build_delay = options.get("build_delay")
    if text_build in _ITERATE_TYPES:
        build_delay = _coerce_number(
            10.0 if build_delay is None else build_delay, "build_delay", 0.0, 100.0
        )
    elif build_delay is not None:
        raise SlideAnimationRefusalError("build_delay applies only to by_word/by_letter")
    after = options.get("after_animation") or "none"
    if after not in AFTER_ANIMATIONS:
        raise SlideAnimationRefusalError(
            f"Invalid after_animation: {after!r} (use one of {', '.join(AFTER_ANIMATIONS)})"
        )
    dim_color = options.get("dim_color")
    if after == "dim":
        dim_color = _coerce_color(dim_color, "dim_color")
    elif dim_color is not None:
        raise SlideAnimationRefusalError("dim_color applies only to after_animation='dim'")
    chart_build = options.get("chart_build") or "as_one"
    if chart_build not in CHART_BUILDS:
        raise SlideAnimationRefusalError(
            f"Invalid chart_build: {chart_build!r} (use one of {', '.join(CHART_BUILDS)})"
        )
    if animation_class == "motion_path" and (text_build != "as_one" or chart_build != "as_one"):
        raise SlideAnimationRefusalError("Motion paths do not take text or chart builds")
    if text_build != "as_one" and target_kind not in {None, "text"}:
        raise SlideAnimationRefusalError(f"text_build {text_build!r} needs a shape with text")
    if chart_build != "as_one" and target_kind not in {None, "chart"}:
        raise SlideAnimationRefusalError(f"chart_build {chart_build!r} needs a chart graphic frame")
    paragraph_options = {}
    for name in PARAGRAPH_BUILD_OPTIONS:
        value = options.get(name)
        if value is None:
            continue
        if not isinstance(value, bool):
            raise SlideAnimationRefusalError(
                f"Invalid {name}: {value!r} (must be a boolean or None)"
            )
        if target_kind not in {None, "text"}:
            raise SlideAnimationRefusalError(f"{name} needs a shape with text")
        paragraph_options[name] = value
    amount = options.get("amount")
    color = options.get("color")
    color_target = options.get("color_target")
    direction = coerce_direction(effect, options.get("direction"))
    if animation_class == "emphasis" and effect in EMPHASIS_DEFAULT_AMOUNTS:
        amount = EMPHASIS_DEFAULT_AMOUNTS[effect] if amount is None else amount
        low, high = {
            "spin": (-36000.0, 36000.0),
            "grow_shrink": (1.0, 10000.0),
            "transparency": (0.0, 100.0),
        }[effect]
        amount = _coerce_number(amount, "amount", low, high)
    elif amount is not None:
        raise SlideAnimationRefusalError(
            "amount applies only to spin, grow_shrink, and transparency"
        )
    if animation_class == "emphasis" and effect == "color_change":
        color = _coerce_color(color, "color")
        color_target = color_target or "fill"
        if color_target not in COLOR_CHANGE_PRESET_IDS:
            raise SlideAnimationRefusalError(
                f"Invalid color_target: {color_target!r} (use 'fill', 'font', or 'line')"
            )
    elif color is not None or color_target is not None:
        raise SlideAnimationRefusalError("color applies only to color_change")
    return {
        "text_build": text_build,
        "build_level": build_level,
        "build_delay": build_delay,
        "chart_build": chart_build,
        "after_animation": after,
        "dim_color": dim_color,
        "amount": amount,
        "color": color,
        "color_target": color_target,
        "direction": direction,
        **paragraph_options,
    }


def _build_animation_group(
    effect_data: dict[str, Any],
    alloc_id: Any,
    grp_id: int,
    slide_root: ET.Element | None = None,
) -> tuple[ET.Element, dict[str, Any]]:
    effect = effect_data["effect"]
    animation_class = effect_data.get("animation_class", "entrance")
    if animation_class not in {"entrance", "exit", "motion_path", "emphasis"}:
        raise SlideAnimationRefusalError(f"Unsupported animation class: {animation_class!r}")
    shape_id = str(effect_data["shape_id"])
    options = coerce_effect_options(
        effect,
        animation_class,
        effect_data,
        shape_build_kind(slide_root, shape_id) if slide_root is not None else None,
    )
    behaviors = effect_data.get("behaviors")
    if behaviors is not None:
        if effect not in {"custom", "motion_path"}:
            raise SlideAnimationRefusalError(
                "Behaviours are authored on custom and motion path effects"
            )
        behaviors = coerce_behaviors(behaviors)
    if effect == "custom":
        if behaviors is None:
            raise SlideAnimationRefusalError("A custom effect needs behaviours")
        preset_class, preset_id = _PRESET_CLASS_BY_ANIMATION[animation_class], "0"
    elif animation_class == "motion_path":
        if effect != "motion_path":
            raise SlideAnimationRefusalError("Motion paths must use effect 'motion_path'")
        if behaviors is not None and not _is_motion_path(behaviors):
            raise SlideAnimationRefusalError(
                "A motion path effect takes one MotionBehavior with a path"
            )
        preset_class, preset_id = "path", "0"
    elif animation_class == "emphasis":
        if effect not in EMPHASIS_EFFECTS:
            raise SlideAnimationRefusalError(f"Unsupported emphasis animation effect: {effect!r}")
        preset_class = "emph"
        preset_id = str(
            COLOR_CHANGE_PRESET_IDS[options["color_target"]]
            if effect == "color_change"
            else EMPHASIS_PRESET_IDS[effect]
        )
    else:
        if effect not in EFFECT_PRESET_IDS or (animation_class == "exit" and effect == "appear"):
            raise SlideAnimationRefusalError(
                f"Unsupported {animation_class} animation effect: {effect!r}"
            )
        preset_class, preset_id = (
            "entr" if animation_class == "entrance" else "exit",
            str(EFFECT_PRESET_IDS[effect]),
        )

    start = effect_data.get("start", "on_click")
    if start not in START_TO_NODE_TYPE:
        raise SlideAnimationRefusalError(f"Unsupported start condition: {start!r}")
    repeat_count = effect_data.get("repeat_count", 1)
    if isinstance(repeat_count, bool) or not isinstance(repeat_count, int) or repeat_count < 1:
        raise SlideAnimationRefusalError("repeat_count must be a positive integer")
    rewind = effect_data.get("rewind", False)
    if not isinstance(rewind, bool):
        raise SlideAnimationRefusalError("rewind must be a boolean")
    auto_reverse = effect_data.get("auto_reverse", False)
    if not isinstance(auto_reverse, bool):
        raise SlideAnimationRefusalError("auto_reverse must be a boolean")
    restart = coerce_restart(effect_data.get("restart"))
    fill = coerce_fill(effect_data.get("fill", "remove" if rewind else "hold"))
    acceleration, deceleration = coerce_acceleration_deceleration(
        effect_data.get("acceleration"), effect_data.get("deceleration")
    )
    default_duration = (
        EMPHASIS_DEFAULT_DURATIONS.get(effect, 0.5) if animation_class == "emphasis" else 0.5
    )
    try:
        delay_sec = float(effect_data.get("delay", 0.0))
        duration_sec = float(effect_data.get("duration", default_duration))
    except (TypeError, ValueError) as exc:
        raise SlideAnimationRefusalError("Animation delay and duration must be numeric") from exc
    if not (0.0 <= delay_sec < float("inf") and 0.0 <= duration_sec < float("inf")):
        raise SlideAnimationRefusalError(
            "Animation delay and duration must be finite non-negative numbers"
        )
    delay_ms = str(round(delay_sec * 1000.0))
    duration_ms = str(round(duration_sec * 1000.0))
    outer_id = effect_data.get("timing_id")
    if outer_id is None:
        outer_id = alloc_id()
    if isinstance(outer_id, bool) or not isinstance(outer_id, int) or outer_id < 1:
        raise SlideAnimationRefusalError("Animation timing_id must be a positive integer")

    outer_attrs = {
        "id": str(outer_id),
        "presetID": preset_id,
        "presetClass": preset_class,
        "presetSubtype": "2"
        if effect == "color_change"
        else EFFECT_PRESET_SUBTYPES.get(effect, "0"),
        "grpId": str(grp_id),
        "nodeType": START_TO_NODE_TYPE[start],
    }
    if options["direction"] is not None:
        subtypes = _FLY_DIRECTION_SUBTYPES if effect == "fly" else _WIPE_DIRECTION_SUBTYPES
        outer_attrs["presetSubtype"] = subtypes[options["direction"]]
    if effect != "appear":
        outer_attrs["dur"] = duration_ms
    elif repeat_count != 1 or rewind:
        outer_attrs["dur"] = "1"
    if repeat_count != 1:
        outer_attrs["repeatCount"] = str(repeat_count * 1000)
    if fill is not None:
        outer_attrs["fill"] = fill
    if auto_reverse:
        outer_attrs["autoRev"] = "1"
    saved_markup = effect_data.get("timing_markup")
    if saved_markup is not None:
        try:
            saved_outer = ET.fromstring(saved_markup).find(f"{{{P_NS}}}cTn")
        except (ET.ParseError, TypeError) as exc:
            raise SlideAnimationRefusalError("Invalid saved animation timing markup") from exc
        if saved_outer is None:
            raise SlideAnimationRefusalError("Saved animation timing markup has no cTn")
        replaced = {
            "id",
            "presetID",
            "presetClass",
            "grpId",
            "nodeType",
            "dur",
            "fill",
            "repeatCount",
            "autoRev",
            "restart",
            "accel",
            "decel",
        }
        if "repeat_duration" in effect_data:
            replaced.add("repeatDur")
        if not effect_data.get("preserve_preset_subtype", True):
            replaced.add("presetSubtype")
        outer_attrs.update(
            {key: value for key, value in saved_outer.attrib.items() if key not in replaced}
        )
    repeat_duration = coerce_repeat_duration(effect_data.get("repeat_duration"))
    if repeat_duration is not None:
        outer_attrs["repeatDur"] = repeat_duration
    if restart is not None:
        outer_attrs["restart"] = restart
    for name, value in (("accel", acceleration), ("decel", deceleration)):
        if value is not None:
            outer_attrs[name] = str(round(value * 100000))
    build_markup = effect_data.get("build_markup")
    if build_markup is not None:
        try:
            saved_build = ET.fromstring(build_markup)
        except (ET.ParseError, TypeError) as exc:
            raise SlideAnimationRefusalError("Invalid saved animation build markup") from exc
        if _xml_local_name(saved_build.tag) not in _BUILD_ENTRY_TAGS:
            raise SlideAnimationRefusalError("Unsupported saved animation build markup")
        options["_build_markup"] = build_markup
    if "paragraph_build" in effect_data:
        value = effect_data["paragraph_build"]
        if value is not None and value not in PARAGRAPH_BUILD_TYPES:
            raise SlideAnimationRefusalError(f"Invalid paragraph_build: {value!r}")
        options["paragraph_build"] = value

    group = ET.Element(f"{{{P_NS}}}par")
    outer = ET.SubElement(group, f"{{{P_NS}}}cTn", outer_attrs)
    conditions = ET.SubElement(outer, f"{{{P_NS}}}stCondLst")
    ET.SubElement(conditions, f"{{{P_NS}}}cond", {"delay": delay_ms})
    text_build = options["text_build"]
    if text_build in _ITERATE_TYPES:
        iterate = ET.SubElement(outer, f"{{{P_NS}}}iterate", {"type": _ITERATE_TYPES[text_build]})
        ET.SubElement(
            iterate,
            f"{{{P_NS}}}tmPct",
            {"val": str(round(options["build_delay"] * 1000))},
        )
    children = ET.SubElement(outer, f"{{{P_NS}}}childTnLst")
    if behaviors is not None:
        for behavior in behaviors:
            append_behavior(children, behavior, shape_id, duration_ms, alloc_id)
    elif animation_class == "entrance":
        _append_visibility_set(children, shape_id, "visible", "0", alloc_id)
    if behaviors is not None or effect == "appear":
        pass
    elif animation_class == "emphasis":
        _append_emphasis(children, effect, options, shape_id, duration_ms, alloc_id)
    elif effect in EFFECT_FILTERS:
        anim = ET.SubElement(
            children,
            f"{{{P_NS}}}animEffect",
            {
                "transition": "in" if animation_class == "entrance" else "out",
                "filter": f"wipe({options['direction']})"
                if effect == "wipe" and options["direction"] is not None
                else EFFECT_FILTERS[effect],
            },
        )
        _append_common_behavior(anim, shape_id, duration_ms, alloc_id)
    elif effect == "zoom":
        scale = ET.SubElement(children, f"{{{P_NS}}}animScale")
        _append_common_behavior(scale, shape_id, duration_ms, alloc_id)
        start_scale, end_scale = (
            ("0", "100000") if animation_class == "entrance" else ("100000", "0")
        )
        ET.SubElement(scale, f"{{{P_NS}}}from", {"x": start_scale, "y": start_scale})
        ET.SubElement(scale, f"{{{P_NS}}}to", {"x": end_scale, "y": end_scale})
    elif effect == "fly":
        _append_fly(
            children,
            shape_id,
            duration_ms,
            animation_class == "entrance",
            alloc_id,
            options["direction"] or "down",
        )
    else:
        if animation_class == "motion_path":
            points = _coerce_motion_coordinates(effect_data.get("path"))
        else:
            # Bounce out mirrors bounce in, leaving through the bottom edge.
            entrance_points = ((0.0, 1.0), (0.0, -0.1), (0.0, 0.05), (0.0, 0.0))
            points = (
                entrance_points
                if animation_class == "entrance"
                else tuple(reversed(entrance_points))
            )
        _append_motion(children, shape_id, duration_ms, points, alloc_id)
    if animation_class == "exit" and behaviors is None:
        _append_visibility_set(
            children, shape_id, "hidden", str(max(int(duration_ms) - 1, 0)), alloc_id
        )
    _append_after_animation(outer, options, shape_id, alloc_id)
    return group, options


def _coerce_effect_order(value: Any) -> list[int] | None:
    """Validate a requested supported-effect order before touching the tree."""
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise SlideAnimationRefusalError("Animation effect_order must be a sequence of timing IDs")
    order: list[int] = []
    for timing_id in value:
        if isinstance(timing_id, bool) or not isinstance(timing_id, int) or timing_id < 1:
            raise SlideAnimationRefusalError(
                f"Animation effect_order entry {timing_id!r} is not a positive timing ID"
            )
        order.append(timing_id)
    if len(set(order)) != len(order):
        raise SlideAnimationRefusalError("Animation effect_order must not repeat a timing ID")
    return order


def _reorder_supported_units(units: list[_SequenceUnit], order: list[int]) -> None:
    """Place supported effects in ``order`` within the slots they already occupy.

    Foreign / unsupported units keep their positions; supported effects are
    permuted among the slots supported effects already occupy. Each effect
    keeps its own ``nodeType`` trigger, so click groups follow from the new
    order. Refuses when ``order`` does not name exactly the supported effects.
    """
    slots = [index for index, unit in enumerate(units) if unit.supported]
    by_id = {units[index].info["timing_id"]: units[index] for index in slots}
    if set(order) != set(by_id):
        raise SlideAnimationRefusalError(
            "Animation effect_order does not match the supported main-sequence "
            f"effects (requested {order}, found {sorted(by_id)})"
        )
    for slot, timing_id in zip(slots, order, strict=True):
        units[slot] = by_id[timing_id]


def _effect_span_ms(c_tn: ET.Element) -> int:
    """Milliseconds from a time node's parent start to its end (delay included)."""
    delay = 0
    cond = c_tn.find(f"{{{P_NS}}}stCondLst/{{{P_NS}}}cond")
    if cond is not None and (raw_delay := cond.get("delay")) and raw_delay.isdigit():
        delay = int(raw_delay)
    raw_duration = c_tn.get("dur")
    if raw_duration and raw_duration.isdigit():
        duration = int(raw_duration)
    else:
        duration = 0
        child_tn_lst = c_tn.find(f"{{{P_NS}}}childTnLst")
        for child in child_tn_lst if child_tn_lst is not None else ():
            nested = child.find(f"{{{P_NS}}}cTn")
            if nested is None:
                nested = child.find(f"{{{P_NS}}}cBhvr/{{{P_NS}}}cTn")
            if nested is None:
                nested = child.find(f"{{{P_NS}}}cMediaNode/{{{P_NS}}}cTn")
            if nested is not None:
                duration = max(duration, _effect_span_ms(nested))
    raw_repeat = c_tn.get("repeatCount")
    if raw_repeat and raw_repeat.isdigit():
        duration = duration * int(raw_repeat) // 1000
    if (c_tn.get("autoRev") or "").casefold() in {"1", "true"}:
        duration *= 2
    return delay + duration


def _build_click_group(
    sub_groups: list[list[ET.Element]],
    auto_start: bool,
    main_seq_id: str,
    alloc_id: Any,
) -> ET.Element:
    """Wrap effect pars as PowerPoint writes one click step.

    The click group waits for the next click (``delay="indefinite"``) unless
    it is the slide's automatic first step, which also begins with the main
    sequence. Each sub-group starts when the previous one ends, which is how
    PowerPoint schedules ``after_previous`` effects.
    """
    group = ET.Element(f"{{{P_NS}}}par")
    c_tn = ET.SubElement(group, f"{{{P_NS}}}cTn", {"id": str(alloc_id()), "fill": "hold"})
    conditions = ET.SubElement(c_tn, f"{{{P_NS}}}stCondLst")
    ET.SubElement(conditions, f"{{{P_NS}}}cond", {"delay": "indefinite"})
    if auto_start:
        begin = ET.SubElement(conditions, f"{{{P_NS}}}cond", {"evt": "onBegin", "delay": "0"})
        ET.SubElement(begin, f"{{{P_NS}}}tn", {"val": main_seq_id})
    children = ET.SubElement(c_tn, f"{{{P_NS}}}childTnLst")
    offset = 0
    for effects in sub_groups:
        sub_group = ET.SubElement(children, f"{{{P_NS}}}par")
        sub_tn = ET.SubElement(sub_group, f"{{{P_NS}}}cTn", {"id": str(alloc_id()), "fill": "hold"})
        sub_conditions = ET.SubElement(sub_tn, f"{{{P_NS}}}stCondLst")
        ET.SubElement(sub_conditions, f"{{{P_NS}}}cond", {"delay": str(offset)})
        ET.SubElement(sub_tn, f"{{{P_NS}}}childTnLst").extend(effects)
        offset += max(_effect_span_ms(effect.find(f"{{{P_NS}}}cTn")) for effect in effects)
    return group


def _write_main_sequence(
    main_child_tn_lst: ET.Element,
    units: list[_SequenceUnit],
    main_seq_id: str | None,
    alloc_id: Any,
) -> None:
    """Rewrite the main sequence as PowerPoint click groups.

    An ``on_click`` effect opens a click group, ``after_previous`` opens a
    sub-group, and ``with_previous`` joins the current sub-group. Opaque
    foreign nodes stay at the main-sequence level and end the current group.
    A loaded click group whose partition and trigger are unchanged is kept
    as the same element, so its timing IDs and bytes survive the edit.
    """
    plan: list[ET.Element | list[list[_SequenceUnit]]] = []
    current: list[list[_SequenceUnit]] | None = None
    for unit in units:
        if not unit.is_effect:
            plan.append(unit.element)
            current = None
        elif current is None or unit.node_type == "clickEffect":
            current = [[unit]]
            plan.append(current)
        elif unit.node_type == "withEffect":
            current[-1].append(unit)
        else:
            current.append([unit])

    reused: set[int] = set()
    reuse_flags: list[bool] = []
    for index, entry in enumerate(plan):
        if isinstance(entry, ET.Element):
            reuse_flags.append(False)
            continue
        first = entry[0][0]
        auto_start = index == 0 and main_seq_id is not None and first.node_type != "clickEffect"
        layout = tuple(tuple(id(unit.element) for unit in sub) for sub in entry)
        keep = (
            first.click_group is not None
            and first.layout == layout
            and _is_auto_start_group(first.click_group) == auto_start
            and id(first.click_group) not in reused
        )
        if keep and first.click_group is not None:
            reused.add(id(first.click_group))
        reuse_flags.append(keep)

    # Wrapper IDs of dropped click groups are recycled before new ones are
    # allocated, so a pure reorder keeps the slide's set of timing IDs.
    recycled: list[int] = []
    dropped: set[int] = set()
    for unit in units:
        group = unit.click_group
        if group is None or id(group) in reused or id(group) in dropped:
            continue
        dropped.add(id(group))
        wrappers = [group[0]] + [sub[0] for sub in group[0].find(f"{{{P_NS}}}childTnLst")]
        recycled.extend(int(raw) for node in wrappers if (raw := node.get("id", "")).isdigit())
    recycled.sort(reverse=True)

    def next_wrapper_id() -> int:
        return recycled.pop() if recycled else alloc_id()

    children: list[ET.Element] = []
    for index, (entry, keep) in enumerate(zip(plan, reuse_flags, strict=True)):
        if isinstance(entry, ET.Element):
            children.append(entry)
            continue
        first = entry[0][0]
        if keep and first.click_group is not None:
            children.append(first.click_group)
            continue
        auto_start = index == 0 and main_seq_id is not None and first.node_type != "clickEffect"
        children.append(
            _build_click_group(
                [[unit.element for unit in sub] for sub in entry],
                auto_start,
                main_seq_id or "",
                next_wrapper_id,
            )
        )
    for child in list(main_child_tn_lst):
        main_child_tn_lst.remove(child)
    main_child_tn_lst.extend(children)


def _effect_build_key(c_tn: ET.Element) -> tuple[str, str] | None:
    """(spid, grpId) of an effect time node that targets exactly one shape."""
    grp_id = c_tn.get("grpId")
    spids = {spid for target in c_tn.iter(f"{{{P_NS}}}spTgt") if (spid := target.get("spid"))}
    if grp_id is None or len(spids) != 1:
        return None
    return next(iter(spids)), grp_id


def _used_group_ids(timing_el: ET.Element) -> dict[str, set[int]]:
    """Build group IDs already taken per shape by effects and build entries."""
    used: dict[str, set[int]] = {}
    for c_tn in timing_el.iter(f"{{{P_NS}}}cTn"):
        if c_tn.get("presetClass") is None:
            continue
        key = _effect_build_key(c_tn)
        if key is not None and key[1].isdigit():
            used.setdefault(key[0], set()).add(int(key[1]))
    bld_lst = timing_el.find(f"{{{P_NS}}}bldLst")
    for entry in bld_lst if bld_lst is not None else ():
        spid, grp_id = entry.get("spid"), entry.get("grpId")
        if spid and grp_id and grp_id.isdigit():
            used.setdefault(spid, set()).add(int(grp_id))
    return used


def _next_group_id(used: dict[str, set[int]], spid: str) -> int:
    """Allocate PowerPoint's next build group ID for another effect on ``spid``."""
    taken = used.setdefault(spid, set())
    grp_id = max(taken) + 1 if taken else 0
    taken.add(grp_id)
    return grp_id


def _separate_duplicate_group_ids(units: list[_SequenceUnit], used: dict[str, set[int]]) -> bool:
    """Give each supported effect its own (spid, grpId) build pair.

    Earlier WolfPPT saves wrote ``grpId="0"`` for every effect; PowerPoint
    requires a distinct build group per effect on the same shape.
    """
    seen: set[tuple[str, str]] = set()
    changed = False
    for unit in units:
        c_tn = unit.element.find(f"{{{P_NS}}}cTn") if unit.is_effect else None
        nodes = [c_tn] if c_tn is not None else list(unit.element.iter(f"{{{P_NS}}}cTn"))
        for node in nodes:
            if node.get("presetClass") is None:
                continue
            key = _effect_build_key(node)
            if key is None:
                continue
            if key in seen and unit.supported:
                node.set("grpId", str(_next_group_id(used, key[0])))
                key = (key[0], node.get("grpId", ""))
                changed = True
            seen.add(key)
    return changed


def set_slide_animation_xml(slide_root: ET.Element, spec: Any) -> None:
    """Apply additions/removals/order and timing/build patches, retaining foreign XML."""
    # 1. Discover all shape IDs on the slide
    slide_shape_ids: set[str] = set()
    for elem in slide_root.iter():
        if elem.tag.endswith("cNvPr"):
            sid = elem.get("id")
            if sid:
                slide_shape_ids.add(str(sid))

    # 2. Validate added targets exist on the slide
    added_effects = getattr(spec, "added_effects", []) or []
    for eff in added_effects:
        target_str = str(eff["shape_id"])
        if target_str not in slide_shape_ids:
            raise SlideAnimationRefusalError(
                f"Target shape ID {target_str} not found on slide (stale or deleted shape target)"
            )
        # Validate privately before writing any timing/build entries.
        preview_id = 0

        def preview_alloc_id() -> int:
            nonlocal preview_id
            preview_id += 1
            return preview_id

        _build_animation_group(eff, preview_alloc_id, 1, slide_root)

    timing_updates = getattr(spec, "timing_updates", {}) or {}
    if not isinstance(timing_updates, dict):
        raise SlideAnimationRefusalError("Animation timing_updates must be a mapping")
    build_updates = getattr(spec, "build_updates", {}) or {}
    if not isinstance(build_updates, dict):
        raise SlideAnimationRefusalError("Animation build_updates must be a mapping")
    saved_effects = (
        {
            info["timing_id"]: info
            for info in read_slide_animation_xml(slide_root)["supported_effects"]
        }
        if timing_updates or build_updates
        else {}
    )
    validated_updates: list[tuple[ET.Element, dict[str, str | None]]] = []
    for timing_id, updates in timing_updates.items():
        if (
            isinstance(timing_id, bool)
            or not isinstance(timing_id, int)
            or timing_id not in saved_effects
        ):
            raise SlideAnimationRefusalError(
                f"Cannot edit unsupported/foreign animation timing ID {timing_id!r}"
            )
        if not isinstance(updates, dict) or not set(updates) <= {
            "restart",
            "autoRev",
            "accel",
            "decel",
            "fill",
        }:
            raise SlideAnimationRefusalError("Unsupported animation timing update")
        if "restart" in updates:
            coerce_restart(updates["restart"])
        if "fill" in updates:
            coerce_fill(updates["fill"])
        if "autoRev" in updates and updates["autoRev"] not in (None, "0", "1"):
            raise SlideAnimationRefusalError("Invalid animation autoRev update")
        group = saved_effects[timing_id]["group_element"]
        node = group.find(f"{{{P_NS}}}cTn")
        if node is None:
            raise SlideAnimationRefusalError(
                "Cannot edit Strict animation timing; inspection is read-only"
            )
        _read_easing(node, updates)
        validated_updates.append((node, updates))
    validated_builds = []
    for timing_id, value in build_updates.items():
        if (
            isinstance(timing_id, bool)
            or not isinstance(timing_id, int)
            or timing_id not in saved_effects
        ):
            raise SlideAnimationRefusalError("Cannot edit unsupported paragraph build")
        if value is not None and (not isinstance(value, str) or value not in PARAGRAPH_BUILD_TYPES):
            raise SlideAnimationRefusalError(f"Invalid paragraph_build: {value!r}")
        info = saved_effects[timing_id]
        if info["text_build"] in _ITERATE_TYPES:
            raise SlideAnimationRefusalError("paragraph_build conflicts with iteration")
        key = _effect_build_key(info["group_element"].find(f"{{{P_NS}}}cTn"))
        entries = [
            entry
            for entry in slide_root.findall(f"{{{P_NS}}}timing/{{{P_NS}}}bldLst/{{{P_NS}}}bldP")
            if (entry.get("spid"), entry.get("grpId")) == key
        ]
        if (
            len(entries) != 1
            or getattr(spec, "clear_supported", False)
            or timing_id in (getattr(spec, "removed_timing_ids", []) or [])
        ):
            raise SlideAnimationRefusalError("paragraph_build needs one retained p:bldP entry")
        validated_builds.append((entries[0], value))

    effect_order = _coerce_effect_order(getattr(spec, "effect_order", None))
    order_applied = False
    removed_timing_ids = set(getattr(spec, "removed_timing_ids", []) or [])
    existing_timing_ids = {
        int(raw_id)
        for c_tn in slide_root.iter(f"{{{P_NS}}}cTn")
        if (raw_id := c_tn.get("id")) and raw_id.isdigit()
    }
    requested_timing_ids: set[int] = set()
    for effect_data in added_effects:
        timing_id = effect_data.get("timing_id")
        if timing_id is None:
            continue
        if (
            isinstance(timing_id, bool)
            or not isinstance(timing_id, int)
            or timing_id < 1
            or (timing_id in existing_timing_ids and timing_id not in removed_timing_ids)
            or timing_id in requested_timing_ids
        ):
            raise SlideAnimationRefusalError(
                f"Animation timing_id {timing_id!r} is invalid or already in use"
            )
        requested_timing_ids.add(timing_id)
    for node, _updates in validated_updates:
        if int(node.get("id")) in removed_timing_ids or getattr(spec, "clear_supported", False):
            raise SlideAnimationRefusalError(
                "Cannot update and remove the same animation timing node"
            )
    for entry, value in validated_builds:
        if value is None:
            entry.attrib.pop("build", None)
        else:
            entry.set("build", value)
        if value == "p":
            entry.set("bldLvl", entry.get("bldLvl", "1"))
    for node, updates in validated_updates:
        for name, value in updates.items():
            if value is None:
                node.attrib.pop(name, None)
            else:
                node.set(name, value)

    # 3. Allocate above existing IDs while reserving all facade-assigned outer IDs.
    # Nested behavior IDs must never consume a future effect's outer cTn ID.
    allocated_id = max(
        max_timing_id(slide_root),
        max((move.sequence_id for move in getattr(spec, "sequence_moves", ())), default=0),
    )

    def alloc_id() -> int:
        nonlocal allocated_id
        allocated_id += 1
        while allocated_id in requested_timing_ids:
            allocated_id += 1
        return allocated_id

    timing_el = slide_root.find(f"{{{P_NS}}}timing")
    clear_supported = getattr(spec, "clear_supported", False)

    if timing_el is None:
        if not added_effects:
            # No timing element and no new effects to author
            if effect_order:
                raise SlideAnimationRefusalError(
                    "Animation effect_order names effects but the slide has no timing"
                )
            return
        timing_el = ET.Element(f"{{{P_NS}}}timing")
        _insert_slide_timing_element(slide_root, timing_el)

    # Locate or create <p:tnLst>
    tn_lst = timing_el.find(f"{{{P_NS}}}tnLst")
    if tn_lst is None:
        tn_lst = ET.Element(f"{{{P_NS}}}tnLst")
        timing_el.insert(0, tn_lst)

    par_root, c_tn_root = _find_tm_root(tn_lst)
    if (par_root is None or c_tn_root is None) and added_effects:
        par_root = ET.SubElement(tn_lst, f"{{{P_NS}}}par")
        c_tn_root = ET.SubElement(
            par_root,
            f"{{{P_NS}}}cTn",
            {
                "id": str(alloc_id()),
                "dur": "indefinite",
                "restart": "never",
                "nodeType": "tmRoot",
            },
        )
    removed_build_keys: set[tuple[str, str]] = set()
    final_units: list[_SequenceUnit] = []
    rewrite = False
    seq_el: ET.Element | None = None
    main_c_tn: ET.Element | None = None

    if c_tn_root is not None:
        child_tn_lst = c_tn_root.find(f"{{{P_NS}}}childTnLst")
        if child_tn_lst is None and added_effects:
            child_tn_lst = ET.Element(f"{{{P_NS}}}childTnLst")
            c_tn_root.append(child_tn_lst)

        if child_tn_lst is not None:
            seq_el, main_c_tn = _find_main_seq(child_tn_lst)

    if seq_el is None and added_effects:
        seq_el = ET.Element(
            f"{{{P_NS}}}seq",
            {
                "concurrent": "1",
                "nextAc": "seek",
            },
        )
        main_c_tn = ET.SubElement(
            seq_el,
            f"{{{P_NS}}}cTn",
            {
                "id": str(alloc_id()),
                "dur": "indefinite",
                "nodeType": "mainSeq",
            },
        )
        ET.SubElement(main_c_tn, f"{{{P_NS}}}childTnLst")

        # Standard condition lists for main sequence
        prev_cond = ET.SubElement(seq_el, f"{{{P_NS}}}prevCondLst")
        c_prev = ET.SubElement(prev_cond, f"{{{P_NS}}}cond", {"evt": "onPrev", "delay": "0"})
        tgt_prev = ET.SubElement(c_prev, f"{{{P_NS}}}tgtEl")
        ET.SubElement(tgt_prev, f"{{{P_NS}}}sldTgt")

        next_cond = ET.SubElement(seq_el, f"{{{P_NS}}}nextCondLst")
        c_next = ET.SubElement(next_cond, f"{{{P_NS}}}cond", {"evt": "onNext", "delay": "0"})
        tgt_next = ET.SubElement(c_next, f"{{{P_NS}}}tgtEl")
        ET.SubElement(tgt_next, f"{{{P_NS}}}sldTgt")

        # Insert seq before any media nodes in child_tn_lst
        child_tn_lst.insert(0, seq_el)

    if seq_el is not None:
        main_c_tn = seq_el.find(f"{{{P_NS}}}cTn")
        main_child_tn_lst = (
            main_c_tn.find(f"{{{P_NS}}}childTnLst") if main_c_tn is not None else None
        )
        if main_child_tn_lst is None and main_c_tn is not None:
            main_child_tn_lst = ET.Element(f"{{{P_NS}}}childTnLst")
            main_c_tn.append(main_child_tn_lst)

        if main_child_tn_lst is not None:
            # 4. Remove / clear supported effects
            units = _sequence_units(main_child_tn_lst)
            original_order = [id(unit.element) for unit in units]
            used_group_ids = _used_group_ids(timing_el)
            removed_by_timing_id: dict[int, tuple[str, str]] = {}
            for unit in units:
                grp_timing_id = unit.info.get("timing_id")
                if not unit.supported:
                    if grp_timing_id is not None and grp_timing_id in removed_timing_ids:
                        raise SlideAnimationRefusalError(
                            "Cannot remove foreign/unsupported animation group "
                            f"(timing ID {grp_timing_id})"
                        )
                    final_units.append(unit)
                    continue

                # Supported effect: remove if cleared or explicitly removed
                if clear_supported or grp_timing_id in removed_timing_ids:
                    key = _effect_build_key(unit.element.find(f"{{{P_NS}}}cTn"))
                    if key is not None:
                        removed_by_timing_id[grp_timing_id] = key
                    rewrite = True
                    continue
                final_units.append(unit)
            # 5. Append new supported effects without reusing a timing identifier.
            # A re-added effect (an edit of a saved one) keeps its build group.
            for effect_data in added_effects:
                requested_id = effect_data.get("timing_id")
                if requested_id is not None:
                    allocated_id = max(allocated_id, requested_id)
                spid = str(effect_data["shape_id"])
                previous = removed_by_timing_id.get(requested_id)
                if previous is not None and previous[0] == spid:
                    del removed_by_timing_id[requested_id]
                    grp_id = int(previous[1])
                else:
                    grp_id = _next_group_id(used_group_ids, spid)
                group, options = _build_animation_group(effect_data, alloc_id, grp_id, slide_root)
                supported, info = _inspect_effect_group(group)
                unit = _SequenceUnit(group, True, supported, info)
                unit.build_request = options
                final_units.append(unit)
                rewrite = True
            removed_build_keys = set(removed_by_timing_id.values())
            if effect_order is not None:
                _reorder_supported_units(final_units, effect_order)
                order_applied = True
            rewrite = rewrite or [id(unit.element) for unit in final_units] != (original_order)
            # Timing-only patches must retain the legacy build-group repair.
            # Leave already-distinct groups intact without rewriting their timing.
            if rewrite or validated_updates:
                groups_changed = _separate_duplicate_group_ids(final_units, used_group_ids)
                rewrite = rewrite or groups_changed
            if rewrite:
                main_seq_id = main_c_tn.get("id") if main_c_tn is not None else None
                _write_main_sequence(
                    main_child_tn_lst,
                    final_units,
                    main_seq_id if main_seq_id and main_seq_id.isdigit() else None,
                    alloc_id,
                )

    if effect_order and not order_applied:
        raise SlideAnimationRefusalError(
            "Animation effect_order names effects but the slide has no main sequence"
        )

    if seq_el is not None and main_c_tn is not None and c_tn_root is not None:
        child_tn_lst = c_tn_root.find(f"{{{P_NS}}}childTnLst")
        main_child_tn_lst = main_c_tn.find(f"{{{P_NS}}}childTnLst")
        if (
            child_tn_lst is not None
            and main_child_tn_lst is not None
            and len(main_child_tn_lst) == 0
        ):
            child_tn_lst.remove(seq_el)

    bld_lst = timing_el.find(f"{{{P_NS}}}bldLst")
    remaining_build_keys = {
        key
        for c_tn in timing_el.iter(f"{{{P_NS}}}cTn")
        if c_tn.get("presetClass") is not None and (key := _effect_build_key(c_tn)) is not None
    }
    stale_build_keys = removed_build_keys - remaining_build_keys
    if stale_build_keys and bld_lst is not None:
        for entry in list(bld_lst):
            if (entry.get("spid"), entry.get("grpId")) in stale_build_keys:
                bld_lst.remove(entry)

    if rewrite:
        build_attributes = _shape_build_attributes(slide_root)
        requested: dict[tuple[str, str], dict[str, Any]] = {}
        for unit in final_units:
            if unit.supported and unit.build_request is not None:
                key = _effect_build_key(unit.element.find(f"{{{P_NS}}}cTn"))
                if key is not None:
                    requested[key] = unit.build_request
        for entry in list(bld_lst) if bld_lst is not None and requested else ():
            if (entry.get("spid"), entry.get("grpId")) in requested:
                bld_lst.remove(entry)
        present_build_keys = {
            (entry.get("spid"), entry.get("grpId"))
            for entry in (bld_lst if bld_lst is not None else ())
            if _xml_local_name(entry.tag) in _BUILD_ENTRY_TAGS
        }
        for unit in final_units:
            if not unit.supported:
                continue
            key = _effect_build_key(unit.element.find(f"{{{P_NS}}}cTn"))
            if key is None or key in present_build_keys:
                continue
            request = requested.get(key)
            if request is not None and request.get("_build_markup") is not None:
                entry = ET.fromstring(request["_build_markup"])
                entry.set("spid", key[0])
                entry.set("grpId", key[1])
            else:
                entry = _build_entry(key, build_attributes, request)
            if entry is None:
                continue
            if request is not None and entry.tag == f"{{{P_NS}}}bldP":
                for name, attribute in PARAGRAPH_BUILD_OPTIONS.items():
                    if name in request:
                        entry.set(attribute, "1" if request[name] else "0")
            if bld_lst is None:
                bld_lst = ET.Element(f"{{{P_NS}}}bldLst")
                tn_idx = list(timing_el).index(tn_lst) if tn_lst in list(timing_el) else 0
                timing_el.insert(tn_idx + 1, bld_lst)
            bld_lst.append(entry)
            present_build_keys.add(key)

    if bld_lst is not None and len(bld_lst) == 0:
        timing_el.remove(bld_lst)

    if _can_remove_timing(timing_el):
        slide_root.remove(timing_el)
