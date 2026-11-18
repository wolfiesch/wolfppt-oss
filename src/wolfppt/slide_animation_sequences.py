"""Lossless shape-triggered animation sequences and bounded activation events.

The authoring helper moves existing supported main-sequence effects; it does
not rebuild their behaviours or build declarations. Playback is deliberately
single-activation: one explicit shape click per sequence, no later click steps,
no wrapper repeats, media dispatch, or unmodelled timing controls.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from xml.etree import ElementTree as ET

from .slide_animation_xml import (
    A_NS,
    P_NS,
    SlideAnimationRefusalError,
    _attach_listing,
    _click_group_layout,
    _effect_build_key,
    _effect_span_ms,
    _find_main_seq,
    _find_tm_root,
    _markup,
    _next_group_id,
    _sequence_units,
    _used_group_ids,
    _write_main_sequence,
    max_timing_id,
    read_slide_animation_xml,
)
from .xml_helpers import STRICT_A_NS, STRICT_P_NS

__all__ = [
    "AnimationSequenceEffect",
    "InteractiveSequence",
    "ShapeTriggerEvent",
    "SequenceMove",
    "add_triggered_sequence",
    "interactive_sequences",
    "read_interactive_sequences",
    "prepare_interactive_playback",
]

MAX_SHAPE_EVENTS = 10000


def _refuse(detail: str) -> SlideAnimationRefusalError:
    return SlideAnimationRefusalError(f"Animation 'interactiveSeq': {detail}")


def _runtime_refuse(detail: str) -> Exception:
    from .slide_animation_behaviors import AnimationFrameRefusal

    return AnimationFrameRefusal(f"Animation 'interactiveSeq': {detail}")


def _shape_id(value: Any) -> str:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, str))
        or not str(value).isascii()
        or not str(value).isdigit()
        or not str(value).lstrip("0")
    ):
        raise _refuse("shape identifier must be a positive slide shape ID")
    return str(value)


def _shape_ids(root: ET.Element) -> set[str]:
    metadata_paths = {
        "sp": "nvSpPr",
        "pic": "nvPicPr",
        "graphicFrame": "nvGraphicFramePr",
        "grpSp": "nvGrpSpPr",
        "cxnSp": "nvCxnSpPr",
    }
    result: set[str] = set()
    for tag, metadata in metadata_paths.items():
        for shape in root.iter(f"{{{P_NS}}}{tag}"):
            node = shape.find(f"{{{P_NS}}}{metadata}/{{{P_NS}}}cNvPr")
            if node is not None and node.get("id"):
                result.add(node.get("id"))
    return result


def _positive_id(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _refuse(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class ShapeTriggerEvent:
    """One explicit shape click at slide-relative finite non-negative seconds."""

    time: float
    shape_id: str | int
    event: str = "click"

    def __post_init__(self) -> None:
        try:
            shape = _shape_id(self.shape_id)
        except SlideAnimationRefusalError as exc:
            raise _runtime_refuse(str(exc)) from exc
        if isinstance(self.time, bool) or not isinstance(self.time, (int, float)):
            raise _runtime_refuse("shape event time must be finite non-negative seconds")
        try:
            time = float(self.time)
        except OverflowError as exc:
            raise _runtime_refuse("shape event time must be finite non-negative seconds") from exc
        if not math.isfinite(time) or time < 0:
            raise _runtime_refuse("shape event time must be finite non-negative seconds")
        if self.event != "click":
            raise _runtime_refuse("only explicit shape click events are supported")
        object.__setattr__(self, "shape_id", shape)
        object.__setattr__(self, "time", time)


@dataclass(frozen=True)
class AnimationSequenceEffect:
    """Immutable effect listing with the same read fields as a main effect.

    XML elements are excluded from the public snapshot. ``timing_markup`` and
    ``build_markup`` retain serialized saved markup; behaviours remain immutable
    behaviour objects. Editing uses main-sequence handles before moving them.
    """

    _info: Mapping[str, Any]

    def __getattr__(self, name: str) -> Any:
        try:
            return self._info[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


@dataclass(frozen=True)
class InteractiveSequence:
    """Read-only saved or queued sequence and its exact shape-click target."""

    sequence_id: int
    trigger_shape_id: str
    effects: tuple[AnimationSequenceEffect, ...]
    timing_markup: str


@dataclass(frozen=True)
class SequenceMove:
    """Queued move, with saved effect fingerprints for stale-state refusal."""

    sequence_id: int
    trigger_shape_id: str
    timing_ids: tuple[int, ...]
    expected_markup: tuple[tuple[int, str], ...] = ()


def sequence_moves(facade: Any) -> list[SequenceMove]:
    """Return the facade's cumulative move queue for AnimationSpec construction."""
    return list(getattr(facade, "_sequence_moves", ()))


def restore_sequence_moves(facade: Any, spec: Any) -> None:
    """Restore pending moves after a facade reload, retaining main queue state."""
    moves = list(getattr(spec, "sequence_moves", ()))
    facade._sequence_moves = moves
    moved = {timing_id for move in moves for timing_id in move.timing_ids}
    facade._effects = [effect for effect in facade._effects if effect.timing_id not in moved]
    facade._next_alloc_id = max(
        facade._next_alloc_id, max((move.sequence_id for move in moves), default=0)
    )


def _timing_containers(
    root: ET.Element,
) -> tuple[ET.Element | None, ET.Element | None, ET.Element | None]:
    timing = root.find(f"{{{P_NS}}}timing")
    nodes = timing.find(f"{{{P_NS}}}tnLst") if timing is not None else None
    _par, time_node = _find_tm_root(nodes) if nodes is not None else (None, None)
    children = time_node.find(f"{{{P_NS}}}childTnLst") if time_node is not None else None
    return timing, time_node, children


def _normalize(root: ET.Element) -> ET.Element:
    normalized = copy.deepcopy(root)
    namespaces = {STRICT_P_NS: P_NS, STRICT_A_NS: A_NS}
    for node in normalized.iter():
        for original, target in namespaces.items():
            prefix = f"{{{original}}}"
            if node.tag.startswith(prefix):
                node.tag = f"{{{target}}}" + node.tag[len(prefix) :]
            for key in list(node.attrib):
                if key.startswith(prefix):
                    node.set(f"{{{target}}}" + key[len(prefix) :], node.attrib.pop(key))
    return normalized


def _interactive_nodes(root: ET.Element) -> list[ET.Element]:
    _timing, _time_node, children = _timing_containers(root)
    result = []
    if children is not None:
        for child in children:
            node = child.find(f"{{{P_NS}}}cTn")
            if node is not None and node.get("nodeType") == "interactiveSeq":
                result.append(child)
    found = {id(node) for sequence in result for node in sequence.findall(f"{{{P_NS}}}cTn")}
    for node in root.iter(f"{{{P_NS}}}cTn"):
        if node.get("nodeType") == "interactiveSeq" and id(node) not in found:
            raise _refuse("nested or foreign interactive sequence wrapper is unsupported")
        if node.get("nodeType") == "interactiveEffect":
            raise _refuse("interactiveEffect timing is unsupported")
    return result


def _validate_click_wrapper(sequence: ET.Element, sequence_id: int) -> None:
    """Accept only the recognized single click-group layout, never opaque delays."""
    children = sequence.find(f"{{{P_NS}}}cTn/{{{P_NS}}}childTnLst")
    wrappers = [child for child in children if _click_group_layout(child) is not None]
    if wrappers and (len(wrappers) != 1 or len(children) != 1):
        raise _refuse("multiple click wrappers require unsupported continuation events")
    for wrapper in wrappers:
        node = wrapper[0]
        if set(node.attrib) - {"id", "fill", "nodeType"}:
            raise _refuse("unsupported click-wrapper timing controls")
        if node.get("fill") not in (None, "hold", "freeze"):
            raise _refuse("unsupported click-wrapper fill")
        conditions = node.find(f"{{{P_NS}}}stCondLst")
        if conditions is None or len(conditions) not in (1, 2):
            raise _refuse("unsupported click-wrapper start conditions")
        first = conditions[0]
        if first.attrib != {"delay": "indefinite"} or len(first):
            raise _refuse("unsupported click-wrapper activation condition")
        if len(conditions) == 2:
            begin = conditions[1]
            if (
                begin.attrib != {"evt": "onBegin", "delay": "0"}
                or len(begin) != 1
                or begin[0].tag != f"{{{P_NS}}}tn"
                or begin[0].attrib != {"val": str(sequence_id)}
                or len(begin[0])
            ):
                raise _refuse("unsupported click-wrapper begin condition")
        offset = 0
        layout = _click_group_layout(wrapper)
        for subgroup, effects in zip(node.find(f"{{{P_NS}}}childTnLst"), layout, strict=True):
            subnode = subgroup[0]
            if set(subnode.attrib) - {"id", "fill", "nodeType"}:
                raise _refuse("unsupported subgroup timing controls")
            if subnode.get("fill") not in (None, "hold", "freeze"):
                raise _refuse("unsupported subgroup fill")
            conds = subnode.find(f"{{{P_NS}}}stCondLst")
            if (
                conds is None
                or len(conds) != 1
                or conds[0].attrib != {"delay": str(offset)}
                or len(conds[0])
            ):
                raise _refuse("unsupported subgroup start condition")
            offset += max(_effect_span_ms(effect.find(f"{{{P_NS}}}cTn")) for effect in effects)


def _inspect_sequence(root: ET.Element, sequence: ET.Element) -> dict[str, Any]:
    if sequence.tag != f"{{{P_NS}}}seq" or set(sequence.attrib) - {"concurrent", "nextAc"}:
        raise _refuse("unsupported interactive sequence element or controls")
    if sequence.get("concurrent") not in (None, "1", "true"):
        raise _refuse("non-concurrent sequence controls are unsupported")
    if sequence.get("nextAc") not in (None, "seek"):
        raise _refuse("unsupported next-action control")
    if len(sequence) != 1 or sequence[0].tag != f"{{{P_NS}}}cTn":
        raise _refuse("unsupported interactive sequence children")
    node = sequence[0]
    if node.get("nodeType") != "interactiveSeq":
        raise _refuse("sequence is not a supported interactiveSeq wrapper")
    raw_id = node.get("id", "")
    if not raw_id.isdigit() or int(raw_id) < 1:
        raise _refuse("interactive sequence needs a positive timing ID")
    sequence_id = int(raw_id)
    if set(node.attrib) - {"id", "nodeType", "dur", "restart", "fill"}:
        raise _refuse("unsupported sequence repeat/reversal/timing controls")
    if node.get("dur") not in (None, "indefinite"):
        raise _refuse("finite sequence duration is unsupported")
    if node.get("restart") not in (None, "always", "whenNotActive", "never"):
        raise _refuse("unsupported sequence restart policy")
    if node.get("fill") not in (None, "hold", "freeze"):
        raise _refuse("unsupported sequence fill")
    if [child.tag for child in node] != [f"{{{P_NS}}}stCondLst", f"{{{P_NS}}}childTnLst"]:
        raise _refuse("unsupported sequence timing children")
    conditions = node[0]
    if len(conditions) != 1:
        raise _refuse("one explicit shape-click condition is required")
    condition = conditions[0]
    if condition.tag != f"{{{P_NS}}}cond" or condition.attrib != {"evt": "onClick", "delay": "0"}:
        raise _refuse("only a zero-delay shape-click activation is supported")
    if (
        len(condition) != 1
        or condition[0].tag != f"{{{P_NS}}}tgtEl"
        or condition[0].attrib
        or len(condition[0]) != 1
        or condition[0][0].tag != f"{{{P_NS}}}spTgt"
        or set(condition[0][0].attrib) != {"spid"}
        or len(condition[0][0])
    ):
        raise _refuse("unsupported or foreign trigger target")
    trigger = _shape_id(condition[0][0].get("spid"))
    if trigger not in _shape_ids(root):
        raise _refuse(f"trigger shape {trigger!r} is missing or stale")
    _validate_click_wrapper(sequence, sequence_id)
    units = _sequence_units(node[1])
    if not units or any(not unit.supported for unit in units):
        raise _refuse("sequence contains unsupported or foreign effect wrappers")
    effects = [unit.info for unit in units]
    if any(info["start"] == "on_click" for info in effects[1:]):
        raise _refuse("additional click steps require unsupported continuation events")
    if any(str(info["shape_id"]) not in _shape_ids(root) for info in effects):
        raise _refuse("sequence has a stale or missing effect shape")
    timing, _root_node, _children = _timing_containers(root)
    _attach_listing(timing, effects, [])
    return {
        "sequence_id": sequence_id,
        "trigger_shape_id": trigger,
        "effects": effects,
        "sequence_element": sequence,
    }


def _snapshot(info: dict[str, Any], markup: str | None = None) -> InteractiveSequence:
    effects = tuple(
        AnimationSequenceEffect(
            MappingProxyType(
                {key: value for key, value in effect.items() if key != "group_element"}
            )
        )
        for effect in info["effects"]
    )
    return InteractiveSequence(
        info["sequence_id"],
        info["trigger_shape_id"],
        effects,
        markup if markup is not None else _markup(info["sequence_element"]),
    )


def read_interactive_sequences(root: ET.Element) -> tuple[InteractiveSequence, ...]:
    """Read supported shape-triggered sequences without mutating saved XML.

    Unsupported wrappers refuse by name instead of silently losing sequences.
    Strict markup is normalized privately for inspection and retained in the
    sequence's public timing_markup.
    """
    try:
        normalized = _normalize(root)
        originals = dict(zip(normalized.iter(), root.iter(), strict=True))
        return tuple(
            _snapshot(_inspect_sequence(normalized, sequence), _markup(originals[sequence]))
            for sequence in _interactive_nodes(normalized)
        )
    except (ValueError, OverflowError) as exc:
        raise _refuse(f"invalid interactive timing markup: {exc}") from exc


def preflight_sequence_moves(root: ET.Element, spec: Any) -> tuple[SequenceMove, ...]:
    """Validate every queued trigger/effect and stale fingerprint before save writes."""
    moves = getattr(spec, "sequence_moves", ())
    if not isinstance(moves, (list, tuple)):
        raise _refuse("sequence_moves must be a finite list or tuple")
    if not moves:
        return ()
    if root.tag.startswith(f"{{{STRICT_P_NS}}}"):
        raise _refuse("Strict sequence authoring is read-only")
    saved = {
        info["timing_id"]: info for info in read_slide_animation_xml(root)["supported_effects"]
    }
    added = {effect.get("timing_id"): effect for effect in getattr(spec, "added_effects", ())}
    removed = set(getattr(spec, "removed_timing_ids", ()))
    raw_ids = [node.get("id") for node in root.iter(f"{{{P_NS}}}cTn")]
    if len(raw_ids) != len(set(raw_ids)) or any(
        not value or not value.isascii() or not value.isdigit() or not value.lstrip("0")
        for value in raw_ids
    ):
        raise _refuse("saved timing IDs must be present, unique positive integers")
    current_ids = set(raw_ids)
    shapes = _shape_ids(root)
    sequences: set[int] = set()
    selected: set[int] = set()
    for move in moves:
        if not isinstance(move, SequenceMove):
            raise _refuse("sequence_moves entries must be SequenceMove objects")
        sequence_id = _positive_id(move.sequence_id, "sequence_id")
        if str(sequence_id) in current_ids or sequence_id in sequences or sequence_id in added:
            raise _refuse("sequence timing ID is already in use")
        sequences.add(sequence_id)
        trigger = _shape_id(move.trigger_shape_id)
        if trigger not in shapes:
            raise _refuse(f"trigger shape {trigger!r} is missing or stale")
        if not isinstance(move.timing_ids, tuple) or not move.timing_ids:
            raise _refuse("a sequence must move a non-empty tuple of supported effects")
        expected = dict(move.expected_markup)
        for index, timing_id in enumerate(move.timing_ids):
            _positive_id(timing_id, "effect timing ID")
            if timing_id in selected:
                raise _refuse("an effect cannot be moved into multiple sequences")
            selected.add(timing_id)
            if timing_id in added:
                effect = added[timing_id]
            elif (
                timing_id in saved
                and timing_id not in removed
                and not getattr(spec, "clear_supported", False)
            ):
                effect = saved[timing_id]
            else:
                raise _refuse(f"effect timing ID {timing_id!r} is stale, missing, or unsupported")
            if timing_id in expected and (
                timing_id not in saved or saved[timing_id]["timing_markup"] != expected[timing_id]
            ):
                raise _refuse(f"effect timing ID {timing_id!r} changed since sequence authoring")
            if str(effect.get("shape_id")) not in shapes:
                raise _refuse("effect target shape is missing or stale")
            if index and effect.get("start", "on_click") == "on_click":
                raise _refuse("additional click steps require unsupported continuation events")
    if sequences & selected:
        raise _refuse("sequence and effect timing IDs must be distinct")
    return tuple(moves)


def apply_sequence_moves(root: ET.Element, moves: Sequence[SequenceMove]) -> None:
    """Apply preflighted moves on private XML, preserving every unrelated sequence."""
    if not moves:
        return
    timing, _root_node, children = _timing_containers(root)
    _sequence, main_node = _find_main_seq(children) if children is not None else (None, None)
    main_children = main_node.find(f"{{{P_NS}}}childTnLst") if main_node is not None else None
    if main_children is None:
        raise _refuse("no supported main sequence to move effects from")
    units = _sequence_units(main_children)
    by_id = {unit.info["timing_id"]: unit for unit in units if unit.supported}
    requested = {timing_id for move in moves for timing_id in move.timing_ids}
    if not requested <= set(by_id):
        raise _refuse("queued effects disappeared during main-sequence edits")
    used_groups = _used_group_ids(timing)
    pair_counts: dict[tuple[str, str], int] = {}
    for node in timing.iter(f"{{{P_NS}}}cTn"):
        if node.get("presetClass") is not None and (key := _effect_build_key(node)) is not None:
            pair_counts[key] = pair_counts.get(key, 0) + 1
    builds = timing.find(f"{{{P_NS}}}bldLst")
    for move in moves:
        for timing_id in move.timing_ids:
            node = by_id[timing_id].element.find(f"{{{P_NS}}}cTn")
            key = _effect_build_key(node)
            if key is None or pair_counts.get(key, 0) <= 1:
                continue
            # Repair only the moved effect's ambiguous legacy build pair.
            # Copy its declaration verbatim; unrelated effects/groups stay put.
            new_group = str(_next_group_id(used_groups, key[0]))
            node.set("grpId", new_group)
            pair_counts[key] -= 1
            if builds is not None:
                for entry in list(builds):
                    if (entry.get("spid"), entry.get("grpId")) == key:
                        clone = copy.deepcopy(entry)
                        clone.set("grpId", new_group)
                        builds.append(clone)
    allocated = max(max_timing_id(root), max(move.sequence_id for move in moves))

    def alloc_id() -> int:
        nonlocal allocated
        allocated += 1
        return allocated

    for move in moves:
        if any(node.get("id") == str(move.sequence_id) for node in root.iter(f"{{{P_NS}}}cTn")):
            raise _refuse("queued sequence timing ID collided with a saved timing node")
        sequence = ET.Element(f"{{{P_NS}}}seq", {"concurrent": "1", "nextAc": "seek"})
        node = ET.SubElement(
            sequence,
            f"{{{P_NS}}}cTn",
            {
                "id": str(move.sequence_id),
                "nodeType": "interactiveSeq",
                "dur": "indefinite",
                "restart": "whenNotActive",
                "fill": "hold",
            },
        )
        conditions = ET.SubElement(node, f"{{{P_NS}}}stCondLst")
        condition = ET.SubElement(conditions, f"{{{P_NS}}}cond", {"evt": "onClick", "delay": "0"})
        target = ET.SubElement(condition, f"{{{P_NS}}}tgtEl")
        ET.SubElement(target, f"{{{P_NS}}}spTgt", {"spid": move.trigger_shape_id})
        effect_children = ET.SubElement(node, f"{{{P_NS}}}childTnLst")
        effect_children.extend(by_id[timing_id].element for timing_id in move.timing_ids)
        children.append(sequence)
    _write_main_sequence(
        main_children,
        [unit for unit in units if not unit.supported or unit.info["timing_id"] not in requested],
        main_node.get("id"),
        alloc_id,
    )
    # Build declarations stay paired to their unchanged effect shape/grpId.
    if timing is None:
        raise _refuse("timing disappeared during sequence edits")


def _preview(facade: Any, spec: Any) -> ET.Element:
    from .slide_animation_edits import apply_animation_spec
    from .slide_animation_facade import _get_slide_xml_root

    root = _get_slide_xml_root(facade._slide)
    apply_animation_spec(root, spec)
    return root


def interactive_sequences(facade: Any) -> tuple[InteractiveSequence, ...]:
    """Read saved sequences plus all pending main/sequence edits."""
    facade._ensure_loaded()
    return read_interactive_sequences(_preview(facade, facade._spec()))


def add_triggered_sequence(
    facade: Any, trigger_shape: Any, effects: Sequence[Any]
) -> InteractiveSequence:
    """Move supported main handles into one queued shape-click sequence atomically.

    The first effect anchors to the shape event, with its existing delay. Later
    effects must be with_previous or after_previous. Foreign/stale handles,
    deleted/foreign triggers, and unsupported saved wrappers refuse before the
    facade or presentation queue changes.
    """
    facade._ensure_loaded()
    trigger = _shape_id(facade._validate_target_shape(trigger_shape))
    if isinstance(effects, (str, bytes)) or not isinstance(effects, Sequence) or not effects:
        raise _refuse("effects must be a non-empty finite sequence of main-sequence handles")
    handles = tuple(effects)
    if len({id(effect) for effect in handles}) != len(handles):
        raise _refuse("duplicate effect handles are unsupported")
    for index, effect in enumerate(handles):
        if getattr(effect, "_facade", None) is not facade or effect not in facade._effects:
            raise _refuse("effect is foreign, unsupported, removed, or already moved")
        facade._require_transitional_effect(effect)
        if index and effect.start == "on_click":
            raise _refuse("additional click steps require unsupported continuation events")
    spec = facade._spec()
    root = _preview(facade, spec)
    existing = {
        info["timing_id"]: info for info in read_slide_animation_xml(root)["supported_effects"]
    }
    for effect in handles:
        if effect.timing_id not in existing:
            raise _refuse("effect is stale or its main-sequence wrapper is unsupported")
    from .slide_animation_facade import _get_slide_xml_root

    saved = {
        info["timing_id"]: info
        for info in read_slide_animation_xml(_get_slide_xml_root(facade._slide))[
            "supported_effects"
        ]
    }
    for effect in handles:
        if effect.timing_markup is not None and (
            effect.timing_id not in saved
            or effect.timing_markup != saved[effect.timing_id]["timing_markup"]
        ):
            raise _refuse("saved effect changed since its main-sequence handle was loaded")
    sequence_id = max(max_timing_id(root), facade._next_alloc_id) + 1
    move = SequenceMove(
        sequence_id,
        trigger,
        tuple(effect.timing_id for effect in handles),
        tuple(
            (effect.timing_id, saved[effect.timing_id]["timing_markup"])
            for effect in handles
            if effect.timing_id in saved
        ),
    )
    candidate = copy.copy(spec)
    candidate.sequence_moves = [*getattr(spec, "sequence_moves", ()), move]
    candidate_root = _preview(facade, candidate)
    _timing, _node, candidate_children = _timing_containers(candidate_root)
    sequence = next(
        sequence
        for sequence in candidate_children
        if (node := sequence.find(f"{{{P_NS}}}cTn")) is not None
        and node.get("id") == str(sequence_id)
    )
    result = _snapshot(_inspect_sequence(candidate_root, sequence))
    # Queue first. All validation and preview writes occurred on private XML.
    facade._slide._presentation._queue_slide_animation(facade._slide_identifier(), candidate)
    facade._sequence_moves = list(candidate.sequence_moves)
    moved = set(move.timing_ids)
    facade._effects = [effect for effect in facade._effects if effect.timing_id not in moved]
    facade._next_alloc_id = max(facade._next_alloc_id, max_timing_id(candidate_root))
    facade._has_queued_edits = True
    return result


def prepare_interactive_playback(
    root: ET.Element, shape_events: Sequence[ShapeTriggerEvent] | None = None
) -> tuple[ET.Element, dict[str, Any]]:
    """Validate explicit single activations and provide a private runtime listing.

    Main effects come first, followed by each sequence contiguously. Interactive
    effect listings include sequence_id, trigger_shape_id and activation (infinity
    if no event exists in the explicit event context). Only recognized conditions are
    removed on the normalized copy so the common tree validator can still refuse
    every unowned/foreign timing node and all unsupported effect content.
    """
    try:
        normalized = _normalize(root)
        sequences = [_inspect_sequence(normalized, node) for node in _interactive_nodes(normalized)]
        if sequences and shape_events is None:
            raise _refuse("interactive sequences require an explicit shape event context")
        if sequences:
            ids = [node.get("id") for node in normalized.iter(f"{{{P_NS}}}cTn")]
            if len(ids) != len(set(ids)) or any(
                not value or not value.isdigit() or int(value) < 1 for value in ids
            ):
                raise _refuse("timing IDs must be present, unique positive integers")
        if shape_events is not None and (
            isinstance(shape_events, (str, bytes)) or not isinstance(shape_events, Sequence)
        ):
            raise _refuse("shape_events must be a finite sequence of ShapeTriggerEvent objects")
        events = tuple(shape_events or ())
        if len(events) > MAX_SHAPE_EVENTS:
            raise _refuse("shape event limit exceeded")
        known_shapes = _shape_ids(normalized)
        activations: dict[str, float] = {}
        previous = -1.0
        for event in events:
            if not isinstance(event, ShapeTriggerEvent):
                raise _refuse("shape_events entries must be immutable ShapeTriggerEvent objects")
            if event.time < previous:
                raise _refuse("shape events must be in non-decreasing time order")
            previous = event.time
            if event.shape_id not in known_shapes:
                raise _refuse(f"event shape {event.shape_id!r} is foreign or missing")
            if event.shape_id in activations:
                raise _refuse("repeated shape activation is unsupported")
            activations[event.shape_id] = event.time
        listing = read_slide_animation_xml(normalized)
        for effect in listing["supported_effects"]:
            effect.update(sequence_id=None, trigger_shape_id=None, activation=0.0)
        sequence_ids: set[int] = set()
        for sequence in sequences:
            sequence_id = sequence["sequence_id"]
            if sequence_id in sequence_ids:
                raise _refuse("duplicate sequence timing ID")
            sequence_ids.add(sequence_id)
            trigger = sequence["trigger_shape_id"]
            for effect in sequence["effects"]:
                effect.update(
                    sequence_id=sequence_id,
                    trigger_shape_id=trigger,
                    activation=activations.get(trigger, math.inf),
                )
            listing["supported_effects"].extend(sequence["effects"])
            node = sequence["sequence_element"][0]
            node.set("nodeType", "mainSeq")
            node.remove(node.find(f"{{{P_NS}}}stCondLst"))
        if sequences:
            listing["has_main_seq"] = True
            listing["has_animations"] = True
        return normalized, listing
    except (SlideAnimationRefusalError, ValueError, OverflowError) as exc:
        raise _runtime_refuse(str(exc)) from exc
