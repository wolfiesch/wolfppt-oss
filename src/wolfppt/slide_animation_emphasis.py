"""Emphasis/build helpers and compatible read-only property snapshots.

AnimationKeyframe is shared with editable PropertyBehavior; snapshot reads
retain unrecognized values/formulas unchanged, including fly preset strings.
Authoring validation belongs to the behaviour model, not these permissive
inspection records.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from xml.etree import ElementTree as ET

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
# Emphasis presets as PowerPoint 16 writes them (presetClass="emph").
EMPHASIS_PRESET_IDS = {
    "spin": 8,
    "grow_shrink": 6,
    "transparency": 9,
    "pulse": 26,
    "teeter": 32,
}
# Colour change is one effect over three PowerPoint presets, by changed property.
COLOR_CHANGE_PRESET_IDS = {"fill": 1, "font": 3, "line": 7}
_COLOR_CHANGE_ATTRIBUTES = {
    "fill": "fillcolor",
    "font": "style.color",
    "line": "stroke.color",
}
_COLOR_CHANGE_SWITCHES: dict[str, tuple[tuple[str, str], ...]] = {
    "fill": (("fill.type", "solid"), ("fill.on", "true")),
    "font": (),
    "line": (("stroke.on", "true"),),
}
EMPHASIS_EFFECTS = frozenset({*EMPHASIS_PRESET_IDS, "color_change"})
EMPHASIS_DEFAULT_DURATIONS = {
    "spin": 2.0,
    "grow_shrink": 2.0,
    "transparency": 2.0,
    "color_change": 2.0,
    "pulse": 0.5,
    "teeter": 1.0,
}
EMPHASIS_DEFAULT_AMOUNTS = {"spin": 360.0, "grow_shrink": 150.0, "transparency": 50.0}
# Teeter's five rotations as (by, duration, start) per 1000 ms of effect time.
_TEETER_STEPS = (
    (120000, 100, 0),
    (-240000, 200, 200),
    (240000, 200, 400),
    (-240000, 200, 600),
    (120000, 200, 800),
)
_PULSE_TIME_FILTER = "0, 0; .2, .5; .8, .5; 1, 0"
TEXT_BUILDS = ("as_one", "by_paragraph", "by_word", "by_letter")


class ParagraphBuildType(StrEnum):
    """Saved paragraph build declarations; custom builds need a template for playback."""

    ALL_AT_ONCE = "allAtOnce"
    PARAGRAPH = "p"
    WHOLE = "whole"
    CUSTOM = "cust"


PARAGRAPH_BUILD_TYPES = tuple(choice.value for choice in ParagraphBuildType)
_ITERATE_TYPES = {"by_word": "wd", "by_letter": "lt"}
AFTER_ANIMATIONS = ("none", "dim", "hide", "hide_on_next_click")
CHART_BUILDS = (
    "as_one",
    "by_series",
    "by_category",
    "by_element_in_series",
    "by_element_in_category",
)
_CHART_BUILD_STEPS = {
    "by_series": "series",
    "by_category": "category",
    "by_element_in_series": "seriesEl",
    "by_element_in_category": "categoryEl",
}
_CHART_BUILD_BY_STEP = {step: build for build, step in _CHART_BUILD_STEPS.items()}
_SCHEME_COLORS = frozenset(
    {
        "bg1",
        "tx1",
        "bg2",
        "tx2",
        "accent1",
        "accent2",
        "accent3",
        "accent4",
        "accent5",
        "accent6",
        "hlink",
        "folHlink",
        "dk1",
        "lt1",
        "dk2",
        "lt2",
    }
)


def _xml_local_name(tag: str) -> str:
    """Return local name without XML namespace prefix."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


_EMPHASIS_BY_PRESET = {str(value): key for key, value in EMPHASIS_PRESET_IDS.items()}
_COLOR_TARGET_BY_PRESET = {str(value): key for key, value in COLOR_CHANGE_PRESET_IDS.items()}
_DEFAULT_OPTIONS: dict[str, Any] = {
    "text_build": "as_one",
    "build_level": None,
    "build_delay": None,
    "chart_build": "as_one",
    "after_animation": "none",
    "dim_color": None,
    "amount": None,
    "color": None,
    "color_target": None,
}
_AFTER_EFFECT_ATTRIBUTES = {
    "dur": "1",
    "fill": "hold",
    "afterEffect": "1",
    "nodeType": "afterEffect",
}
# PowerPoint 16 reads a dim or hide-after-animation only in its own form: a
# childStyle override, display="0" and no nodeType. Hide fires at the end of
# the effect's time node; dim is released on the next click.
_POWERPOINT_AFTER_EFFECT_ATTRIBUTES = {
    "dur": "1",
    "fill": "hold",
    "display": "0",
    "afterEffect": "1",
}


@dataclass(frozen=True)
class AnimationKeyframe:
    """One ``p:tav`` snapshot or editable key: 0..1 time (None = indefinite).

    ``value`` and ``formula`` retain XML strings (colour values use RRGGBB
    or scheme names). ``value=None`` also represents a formula-only key.
    PropertyBehavior validates editable keys; numeric snapshots are unchanged.
    """

    time: float | None
    value: str | None
    formula: str | None


@dataclass(frozen=True)
class PropertyAnimation:
    """Read-only, unvalidated view of ``p:anim``, including foreign markup.

    Use PropertyBehavior for authoring; this snapshot contract remains intact.
    """

    timing_id: int | None
    shape_id: str | None
    attributes: tuple[str, ...]
    calc_mode: str | None
    value_type: str | None
    duration: str | None
    from_value: str | None
    to_value: str | None
    by_value: str | None
    keyframes: tuple[AnimationKeyframe, ...]


def _attribute_names(element: ET.Element) -> list[str]:
    return [
        attr.text or ""
        for attr in element.findall(f"{{{P_NS}}}cBhvr/{{{P_NS}}}attrNameLst/{{{P_NS}}}attrName")
    ]


def _color_value(container: ET.Element | None) -> str | None:
    """``RRGGBB`` for an srgbClr, the scheme name for a schemeClr, else None."""
    if container is None or len(container) != 1 or len(container[0]) != 0:
        return None
    color = container[0]
    name = _xml_local_name(color.tag)
    if name == "srgbClr":
        return (color.get("val") or "").upper() or None
    if name == "schemeClr":
        return color.get("val")
    return None


def _value_text(val: ET.Element | None) -> str | None:
    if val is None or len(val) != 1:
        return None
    if _xml_local_name(val[0].tag) == "clrVal":
        return _color_value(val[0])
    return val[0].get("val")


def _property_animations(element: ET.Element) -> tuple[PropertyAnimation, ...]:
    """Every ``p:anim`` below ``element`` with its keyframes, in document order."""
    animations: list[PropertyAnimation] = []
    for anim in element.iter(f"{{{P_NS}}}anim"):
        c_tn = anim.find(f"{{{P_NS}}}cBhvr/{{{P_NS}}}cTn")
        raw_id = c_tn.get("id") if c_tn is not None else None
        target = anim.find(f"{{{P_NS}}}cBhvr/{{{P_NS}}}tgtEl/{{{P_NS}}}spTgt")
        keyframes: list[AnimationKeyframe] = []
        for tav in anim.findall(f"{{{P_NS}}}tavLst/{{{P_NS}}}tav"):
            raw_tm = tav.get("tm")
            time = int(raw_tm) / 100000.0 if raw_tm is not None and raw_tm.isdigit() else None
            keyframes.append(
                AnimationKeyframe(time, _value_text(tav.find(f"{{{P_NS}}}val")), tav.get("fmla"))
            )
        animations.append(
            PropertyAnimation(
                timing_id=int(raw_id) if raw_id and raw_id.isdigit() else None,
                shape_id=target.get("spid") if target is not None else None,
                attributes=tuple(_attribute_names(anim)),
                calc_mode=anim.get("calcmode"),
                value_type=anim.get("valueType"),
                duration=c_tn.get("dur") if c_tn is not None else None,
                from_value=anim.get("from"),
                to_value=anim.get("to"),
                by_value=anim.get("by"),
                keyframes=tuple(keyframes),
            )
        )
    return tuple(animations)


def _string_to(element: ET.Element) -> str | None:
    value = element.find(f"{{{P_NS}}}to/{{{P_NS}}}strVal")
    return value.get("val") if value is not None else None


def _inspect_emphasis(
    preset_id: str | None, child_tn_lst: ET.Element
) -> tuple[str, dict[str, Any]] | None:
    """Name and options of an emphasis preset written the way WolfPPT writes it."""
    kids = list(child_tn_lst)
    tags = [_xml_local_name(kid.tag) for kid in kids]
    if preset_id in _COLOR_TARGET_BY_PRESET:
        target = _COLOR_TARGET_BY_PRESET[preset_id or ""]
        switches = _COLOR_CHANGE_SWITCHES[target]
        if tags != ["animClr", *("set" for _ in switches)] or _attribute_names(kids[0]) != [
            _COLOR_CHANGE_ATTRIBUTES[target]
        ]:
            return None
        for kid, (attr, value) in zip(kids[1:], switches, strict=True):
            if _attribute_names(kid) != [attr] or _string_to(kid) != value:
                return None
        color = _color_value(kids[0].find(f"{{{P_NS}}}to"))
        if color is None:
            return None
        return "color_change", {"color": color, "color_target": target}
    effect = _EMPHASIS_BY_PRESET.get(preset_id or "")
    if effect == "spin":
        by = kids[0].get("by", "") if tags == ["animRot"] else ""
        if not by.lstrip("-").isdigit() or _attribute_names(kids[0]) != ["r"]:
            return None
        return effect, {"amount": int(by) / 60000.0}
    if effect == "grow_shrink":
        by_el = kids[0].find(f"{{{P_NS}}}by") if tags == ["animScale"] else None
        x = by_el.get("x", "") if by_el is not None else ""
        if by_el is None or not x.isdigit() or by_el.get("y") != x:
            return None
        return effect, {"amount": int(x) / 1000.0}
    if effect == "transparency":
        if tags != ["set", "animEffect"] or _attribute_names(kids[0]) != ["style.opacity"]:
            return None
        try:
            opacity = float(_string_to(kids[0]) or "")
        except ValueError:
            return None
        if kids[1].get("filter") != "image" or not 0.0 <= opacity <= 1.0:
            return None
        return effect, {"amount": round((1.0 - opacity) * 100.0, 6)}
    if effect == "pulse":
        return (effect, {}) if tags == ["animEffect", "animScale"] else None
    if effect == "teeter":
        if tags != ["animRot"] * len(_TEETER_STEPS) or any(
            _attribute_names(kid) != ["r"] for kid in kids
        ):
            return None
        return effect, {}
    return None


def _inspect_text_and_after(c_tn: ET.Element) -> dict[str, Any] | None:
    """Word/letter iteration and after-animation action, or None if foreign."""
    options: dict[str, Any] = {}
    iterate = c_tn.find(f"{{{P_NS}}}iterate")
    if iterate is not None:
        kind = {"wd": "by_word", "lt": "by_letter"}.get(iterate.get("type", ""))
        percent = iterate.find(f"{{{P_NS}}}tmPct")
        raw = percent.get("val", "") if percent is not None else ""
        if (
            kind is None
            or len(iterate) != 1
            or not raw.isdigit()
            or iterate.get("backwards") not in {None, "0", "false"}
        ):
            return None
        options.update(text_build=kind, build_delay=int(raw) / 1000.0)
    sub_tn_lst = c_tn.find(f"{{{P_NS}}}subTnLst")
    if sub_tn_lst is None:
        return options
    if len(sub_tn_lst) != 1:
        return None
    action = sub_tn_lst[0]
    behavior = action.find(f"{{{P_NS}}}cBhvr")
    node = behavior.find(f"{{{P_NS}}}cTn") if behavior is not None else None
    if node is None:
        return None
    tag = _xml_local_name(action.tag)
    master = node.get("masterRel")
    powerpoint_form = behavior.get("override") == "childStyle" and all(
        node.get(name) == value for name, value in _POWERPOINT_AFTER_EFFECT_ATTRIBUTES.items()
    )
    if powerpoint_form and node.get("nodeType") is None:
        if tag == "animClr" and master == "nextClick":
            color = _color_value(action.find(f"{{{P_NS}}}to"))
            if _attribute_names(action) != ["ppt_c"] or color is None:
                return None
            options.update(after_animation="dim", dim_color=color)
            return options
        if (
            tag == "set"
            and master == "sameClick"
            and _attribute_names(action) == ["style.visibility"]
            and _string_to(action) == "hidden"
            and _ends_with_effect(node, c_tn)
        ):
            options["after_animation"] = "hide"
            return options
        return None
    if any(node.get(name) != value for name, value in _AFTER_EFFECT_ATTRIBUTES.items()):
        return None
    if (
        tag == "set"
        and _attribute_names(action) == ["style.visibility"]
        and _string_to(action) == "hidden"
        and master == "nextClick"
    ):
        options["after_animation"] = "hide_on_next_click"
        return options
    return None


def _ends_with_effect(node: ET.Element, effect_c_tn: ET.Element) -> bool:
    """True when ``node`` starts at the end of the effect's own time node."""
    conds = node.findall(f"{{{P_NS}}}stCondLst/{{{P_NS}}}cond")
    if len(conds) != 1 or conds[0].get("evt") != "end" or conds[0].get("delay") != "0":
        return False
    target = conds[0].find(f"{{{P_NS}}}tn")
    return target is not None and target.get("val") == effect_c_tn.get("id")


def _format_decimal(value: float) -> str:
    rendered = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _append_color(parent: ET.Element, color: str) -> None:
    tag = "schemeClr" if color in _SCHEME_COLORS else "srgbClr"
    ET.SubElement(parent, f"{{{A_NS}}}{tag}", {"val": color})


def _append_behavior(
    parent: ET.Element,
    tag: str,
    shape_id: str,
    alloc_id: Any,
    timing: dict[str, str],
    *,
    attr_names: tuple[str, ...] = (),
    attributes: dict[str, str] | None = None,
    behavior: dict[str, str] | None = None,
    delay: str | None = None,
) -> ET.Element:
    """One animation behavior (``tag``) with its cBhvr time node and target."""
    element = ET.SubElement(parent, f"{{{P_NS}}}{tag}", attributes or {})
    common = ET.SubElement(element, f"{{{P_NS}}}cBhvr", behavior or {})
    c_tn = ET.SubElement(common, f"{{{P_NS}}}cTn", {"id": str(alloc_id()), **timing})
    if delay is not None:
        conditions = ET.SubElement(c_tn, f"{{{P_NS}}}stCondLst")
        ET.SubElement(conditions, f"{{{P_NS}}}cond", {"delay": delay})
    target = ET.SubElement(common, f"{{{P_NS}}}tgtEl")
    ET.SubElement(target, f"{{{P_NS}}}spTgt", {"spid": shape_id})
    if attr_names:
        attr_list = ET.SubElement(common, f"{{{P_NS}}}attrNameLst")
        for attr_name in attr_names:
            ET.SubElement(attr_list, f"{{{P_NS}}}attrName").text = attr_name
    return element


def _append_emphasis(
    children: ET.Element,
    effect: str,
    options: dict[str, Any],
    shape_id: str,
    duration_ms: str,
    alloc_id: Any,
) -> None:
    """Behaviors of an emphasis preset as PowerPoint 16 writes them."""
    hold = {"dur": duration_ms, "fill": "hold"}
    amount = options.get("amount")
    if effect == "spin":
        _append_behavior(
            children,
            "animRot",
            shape_id,
            alloc_id,
            hold,
            attr_names=("r",),
            attributes={"by": str(round(amount * 60000))},
        )
    elif effect == "grow_shrink":
        scale = _append_behavior(children, "animScale", shape_id, alloc_id, hold)
        factor = str(round(amount * 1000))
        ET.SubElement(scale, f"{{{P_NS}}}by", {"x": factor, "y": factor})
    elif effect == "transparency":
        opacity = _format_decimal(1.0 - amount / 100.0)
        opacity_set = _append_behavior(
            children, "set", shape_id, alloc_id, hold, attr_names=("style.opacity",)
        )
        to_el = ET.SubElement(opacity_set, f"{{{P_NS}}}to")
        ET.SubElement(to_el, f"{{{P_NS}}}strVal", {"val": opacity})
        _append_behavior(
            children,
            "animEffect",
            shape_id,
            alloc_id,
            hold,
            attributes={"filter": "image", "prLst": f"opacity: {opacity}"},
            behavior={"rctx": "IE"},
        )
    elif effect == "color_change":
        target = options["color_target"]
        color_anim = _append_behavior(
            children,
            "animClr",
            shape_id,
            alloc_id,
            hold,
            attr_names=(_COLOR_CHANGE_ATTRIBUTES[target],),
            attributes={"clrSpc": "rgb", "dir": "cw"},
            behavior={"override": "childStyle"} if target == "font" else None,
        )
        _append_color(ET.SubElement(color_anim, f"{{{P_NS}}}to"), options["color"])
        for attr_name, value in _COLOR_CHANGE_SWITCHES[target]:
            switch = _append_behavior(
                children, "set", shape_id, alloc_id, hold, attr_names=(attr_name,)
            )
            to_el = ET.SubElement(switch, f"{{{P_NS}}}to")
            ET.SubElement(to_el, f"{{{P_NS}}}strVal", {"val": value})
    elif effect == "pulse":
        _append_behavior(
            children,
            "animEffect",
            shape_id,
            alloc_id,
            {"dur": duration_ms, "tmFilter": _PULSE_TIME_FILTER},
            attributes={"transition": "out", "filter": "fade"},
        )
        scale = _append_behavior(
            children,
            "animScale",
            shape_id,
            alloc_id,
            {"dur": str(int(duration_ms) // 2), "autoRev": "1", "fill": "hold"},
        )
        ET.SubElement(scale, f"{{{P_NS}}}by", {"x": "105000", "y": "105000"})
    else:  # teeter
        span = int(duration_ms) / 1000.0
        for by, step_ms, start_ms in _TEETER_STEPS:
            _append_behavior(
                children,
                "animRot",
                shape_id,
                alloc_id,
                {"dur": str(round(step_ms * span)), "fill": "hold"},
                attr_names=("r",),
                attributes={"by": str(by)},
                delay=str(round(start_ms * span)),
            )


def _append_after_animation(
    outer: ET.Element, options: dict[str, Any], shape_id: str, alloc_id: Any
) -> None:
    """Dim or hide the shape once the effect ends (``p:subTnLst``)."""
    after = options["after_animation"]
    if after == "none":
        return
    sub_tn_lst = ET.SubElement(outer, f"{{{P_NS}}}subTnLst")
    if after == "dim":
        dim = _append_behavior(
            sub_tn_lst,
            "animClr",
            shape_id,
            alloc_id,
            {**_POWERPOINT_AFTER_EFFECT_ATTRIBUTES, "masterRel": "nextClick"},
            attr_names=("ppt_c",),
            attributes={"clrSpc": "rgb", "dir": "cw"},
            behavior={"override": "childStyle"},
        )
        _append_color(ET.SubElement(dim, f"{{{P_NS}}}to"), options["dim_color"])
        return
    if after == "hide":
        hide = _append_behavior(
            sub_tn_lst,
            "set",
            shape_id,
            alloc_id,
            {**_POWERPOINT_AFTER_EFFECT_ATTRIBUTES, "masterRel": "sameClick"},
            attr_names=("style.visibility",),
            behavior={"override": "childStyle"},
        )
        node = hide.find(f"{{{P_NS}}}cBhvr/{{{P_NS}}}cTn")
        conditions = ET.SubElement(node, f"{{{P_NS}}}stCondLst")
        end = ET.SubElement(conditions, f"{{{P_NS}}}cond", {"evt": "end", "delay": "0"})
        ET.SubElement(end, f"{{{P_NS}}}tn", {"val": outer.get("id", "")})
    else:
        hide = _append_behavior(
            sub_tn_lst,
            "set",
            shape_id,
            alloc_id,
            {**_AFTER_EFFECT_ATTRIBUTES, "masterRel": "nextClick"},
            attr_names=("style.visibility",),
            delay="0",
        )
    to_el = ET.SubElement(hide, f"{{{P_NS}}}to")
    ET.SubElement(to_el, f"{{{P_NS}}}strVal", {"val": "hidden"})


def _shape_build_attributes(slide_root: ET.Element) -> dict[str, dict[str, str]]:
    """Extra <p:bldP> attributes per shape ID for shapes PowerPoint builds.

    PowerPoint writes a paragraph build entry for ``p:sp`` shapes only, with
    ``animBg="1"`` when the shape is not a placeholder.
    """
    attributes: dict[str, dict[str, str]] = {}
    for element in slide_root.iter():
        if _xml_local_name(element.tag) != "sp":
            continue
        non_visual = element.find(f"{{{P_NS}}}nvSpPr")
        c_nv_pr = non_visual.find(f"{{{P_NS}}}cNvPr") if non_visual is not None else None
        if c_nv_pr is None or not c_nv_pr.get("id"):
            continue
        placeholder = non_visual.find(f"{{{P_NS}}}nvPr/{{{P_NS}}}ph")
        attributes[c_nv_pr.get("id", "")] = {} if placeholder is not None else {"animBg": "1"}
    return attributes


def _build_entry(
    key: tuple[str, str],
    build_attributes: dict[str, dict[str, str]],
    request: dict[str, Any] | None,
) -> ET.Element | None:
    """The ``p:bldP`` / ``p:bldGraphic`` entry for one effect's build group."""
    spid, grp_id = key
    request = request or _DEFAULT_OPTIONS
    chart_build = request.get("chart_build", "as_one")
    if chart_build in _CHART_BUILD_STEPS:
        entry = ET.Element(f"{{{P_NS}}}bldGraphic", {"spid": spid, "grpId": grp_id})
        sub = ET.SubElement(entry, f"{{{P_NS}}}bldSub")
        ET.SubElement(
            sub,
            f"{{{A_NS}}}bldChart",
            {"bld": _CHART_BUILD_STEPS[chart_build], "animBg": "1"},
        )
        return entry
    if spid not in build_attributes:
        return None
    attributes = {"spid": spid, "grpId": grp_id, **build_attributes[spid]}
    text_build = request.get("text_build", "as_one")
    if text_build == "by_paragraph":
        attributes.update(build="p", bldLvl=str(request["build_level"]))
    elif text_build in _ITERATE_TYPES:
        attributes["build"] = "allAtOnce"
    if "paragraph_build" in request:
        value = request["paragraph_build"]
        if value is None:
            attributes.pop("build", None)
        else:
            attributes["build"] = value
    return ET.Element(f"{{{P_NS}}}bldP", attributes)
