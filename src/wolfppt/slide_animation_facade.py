"""Slide animation inspection and queued timing/build authoring facade.

PropertyAnimation remains a read-only saved-markup snapshot. Editable
PropertyBehavior objects are replaced through effect.behaviors; unsupported
markup is retained raw. Restart, fill and auto-reverse edits patch timing
options without rebuilding saved effects. AnimationEffect.paragraph_build
patches only its paragraph build entry and retains unrelated timing markup.
"""

from __future__ import annotations

import itertools
import math
import zipfile
from collections.abc import Sequence
from typing import Any
from xml.etree import ElementTree as ET

from .slide_animation_behaviors import (
    AnimationBehavior,
    Behavior,
    BehaviorFactory,
    MotionBehavior,
    MotionPath,
    RawBehavior,
    coerce_acceleration_deceleration,
    coerce_behaviors,
    coerce_fill,
    coerce_restart,
    is_authorable,
    parse_behaviors,
)
from .slide_animation_edits import AnimationSpec, apply_animation_spec
from .slide_animation_emphasis import PARAGRAPH_BUILD_TYPES, ParagraphBuildType
from .slide_animation_sequences import (
    InteractiveSequence,
    SequenceMove,
    add_triggered_sequence,
    interactive_sequences,
    restore_sequence_moves,
)
from .slide_animation_xml import (
    _DEFAULT_OPTIONS,
    EMPHASIS_DEFAULT_DURATIONS,
    EMPHASIS_EFFECTS,
    P_NS,
    PARAGRAPH_BUILD_OPTIONS,
    PropertyAnimation,
    SlideAnimationRefusalError,
    _build_animation_group,
    coerce_effect_options,
    coerce_repeat_duration,
    shape_build_kind,
)
from .slide_animation_xml import (
    read_slide_animation_xml as _read_slide_animation_xml,
)

VALID_ENTRANCE_EFFECTS = {
    "appear",
    "fade",
    "fly",
    "wipe",
    "zoom",
    "wheel",
    "dissolve",
    "bounce",
}
VALID_EXIT_EFFECTS = {
    "fade",
    "fly",
    "wipe",
    "zoom",
    "wheel",
    "dissolve",
    "bounce",
}
# Retained for callers that previously imported the original effect allow-list.
VALID_EFFECTS = VALID_ENTRANCE_EFFECTS | VALID_EXIT_EFFECTS
VALID_EMPHASIS_EFFECTS = set(EMPHASIS_EFFECTS)
_EFFECTS_BY_CLASS = {
    "entrance": VALID_ENTRANCE_EFFECTS,
    "exit": VALID_EXIT_EFFECTS,
    "emphasis": VALID_EMPHASIS_EFFECTS,
}
VALID_STARTS = {"on_click", "with_previous", "after_previous"}
VALID_CUSTOM_CLASSES = ("entrance", "exit", "emphasis", "motion_path")
_SAVE_FIRST_MESSAGE = (
    "Animation authoring requires a saved slide; call Presentation.save() "
    "before inspecting or editing slide animations"
)


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _get_slide_xml_root(slide: Any) -> ET.Element:
    """Read animation state from the current saved presentation package.

    Animation state comes from the package on disk, so a slide that has never
    been saved (for example one created by ``Presentation()`` plus
    ``add_slide``) is refused until ``Presentation.save()`` has run.
    """
    prs = getattr(slide, "_presentation", None)
    partname = getattr(slide, "partname", None)
    if prs is None or not partname:
        raise SlideAnimationRefusalError(_SAVE_FIRST_MESSAGE)
    try:
        with zipfile.ZipFile(prs.path) as package:
            return ET.fromstring(package.read(str(partname).lstrip("/")))
    except (KeyError, zipfile.BadZipFile, ET.ParseError, OSError) as exc:
        raise SlideAnimationRefusalError("Cannot read saved slide animation state") from exc


def _extract_shape_id(shape_or_id: Any) -> int | str:
    """Extract shape ID from a Shape object or raw identifier."""
    if hasattr(shape_or_id, "shape_id"):
        sid = shape_or_id.shape_id
    elif hasattr(shape_or_id, "id"):
        sid = shape_or_id.id
    else:
        sid = shape_or_id

    if sid is None:
        raise SlideAnimationRefusalError("Target shape has no shape_id")
    if isinstance(sid, int):
        return sid
    if isinstance(sid, str):
        if sid.isdigit():
            return int(sid)
        return sid
    raise SlideAnimationRefusalError(
        f"Target shape ID must be int or str, got {type(sid).__name__}"
    )


def _is_shape_id_on_slide(slide: Any, shape_id: int | str) -> bool:
    """Check whether shape_id exists on the slide."""
    target_str = str(shape_id)

    # 1. Check slide.shapes collection if available
    shapes = getattr(slide, "shapes", None)
    if shapes is not None:
        try:
            for s in shapes:
                if getattr(s, "_deleted", False):
                    continue
                sid = getattr(s, "shape_id", None)
                if sid is not None and str(sid) == target_str:
                    return True
        except (AttributeError, TypeError):
            pass

    # 2. Check slide XML root
    root = _get_slide_xml_root(slide)
    if root is not None:
        for elem in root.iter():
            if elem.tag.endswith("cNvPr"):
                sid = elem.get("id")
                if sid and str(sid) == target_str:
                    return True

    # 3. Fallback if no shapes collection or XML is bound
    return shapes is None and root is None


def _validate_timing_value(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise SlideAnimationRefusalError(
            f"Invalid {name} value: {value!r} (booleans are not permitted)"
        )
    if not isinstance(value, (int, float)):
        raise SlideAnimationRefusalError(
            f"Invalid {name} value: {value!r} (must be a finite non-negative number)"
        )
    if math.isnan(value) or math.isinf(value):
        raise SlideAnimationRefusalError(
            f"Invalid {name} value: {value!r} (must be a finite number)"
        )
    if value < 0.0:
        raise SlideAnimationRefusalError(f"Invalid {name} value: {value!r} (must be non-negative)")
    return float(value)


def _normalize_effect(value: Any, animation_class: str) -> str:
    if not isinstance(value, str):
        raise SlideAnimationRefusalError(
            f"Invalid effect: {value!r} (must be a supported {animation_class} effect)"
        )
    clean = value.strip().lower()
    allowed = _EFFECTS_BY_CLASS[animation_class]
    if clean not in allowed:
        choices = ", ".join(f"'{name}'" for name in sorted(allowed))
        raise SlideAnimationRefusalError(
            f"Unsupported {animation_class} animation effect: {value!r}. "
            f"Supported effects are {choices}."
        )
    return clean


def _validate_repeat_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SlideAnimationRefusalError(
            f"Invalid repeat_count value: {value!r} (must be a positive integer)"
        )
    return value


def _validate_rewind(value: Any) -> bool:
    if not isinstance(value, bool):
        raise SlideAnimationRefusalError(f"Invalid rewind value: {value!r} (must be a boolean)")
    return value


def _validate_auto_reverse(value: Any) -> bool:
    if not isinstance(value, bool):
        raise SlideAnimationRefusalError(
            f"Invalid auto_reverse value: {value!r} (must be a boolean)"
        )
    return value


def _validate_path_coordinates(
    coordinates: Any,
) -> tuple[tuple[float, float], ...]:
    if isinstance(coordinates, (str, bytes)) or not isinstance(coordinates, Sequence):
        raise SlideAnimationRefusalError(
            "Motion path coordinates must be a sequence of two-item coordinate pairs"
        )
    if len(coordinates) < 2:
        raise SlideAnimationRefusalError(
            "Motion path coordinates must contain at least two coordinate pairs"
        )

    normalized: list[tuple[float, float]] = []
    for index, coordinate in enumerate(coordinates):
        if (
            isinstance(coordinate, (str, bytes))
            or not isinstance(coordinate, Sequence)
            or len(coordinate) != 2
        ):
            raise SlideAnimationRefusalError(
                f"Invalid motion path coordinate at index {index}: "
                "expected a two-item coordinate pair"
            )
        x, y = coordinate
        if (
            isinstance(x, bool)
            or isinstance(y, bool)
            or not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
            or math.isnan(x)
            or math.isinf(x)
            or math.isnan(y)
            or math.isinf(y)
        ):
            raise SlideAnimationRefusalError(
                f"Invalid motion path coordinate at index {index}: "
                "coordinates must be finite numbers"
            )
        normalized.append((float(x), float(y)))
    return tuple(normalized)


def _normalize_start(value: Any) -> str:
    if not isinstance(value, str):
        raise SlideAnimationRefusalError(
            f"Invalid start condition: {value!r} "
            "(must be 'on_click', 'with_previous', or 'after_previous')"
        )
    clean = value.strip().lower()
    if clean not in VALID_STARTS:
        raise SlideAnimationRefusalError(
            f"Unsupported start condition: {value!r}. Supported start conditions "
            "are 'on_click', 'with_previous', 'after_previous'."
        )
    return clean


def _is_motion_path(behaviors: Sequence[Behavior]) -> bool:
    return (
        len(behaviors) == 1
        and isinstance(behaviors[0], MotionBehavior)
        and behaviors[0].path is not None
    )


def _legacy_points(path: MotionPath) -> tuple[tuple[float, float], ...] | None:
    """Coordinate pairs of an absolute move-then-lines path, else None."""
    commands = path.commands
    if len(commands) < 2 or any(
        command.relative or command.kind != ("move" if index == 0 else "line")
        for index, command in enumerate(commands)
    ):
        return None
    return tuple(command.points[0] for command in commands)


def _authored_behaviors(payload: dict[str, Any]) -> tuple[Behavior, ...]:
    """Build ``payload`` off-slide and list its behaviours (refuses bad input)."""
    group, _options = _build_animation_group(payload, itertools.count(1).__next__, 1)
    children = group.find(f"{{{P_NS}}}cTn/{{{P_NS}}}childTnLst")
    behaviors = parse_behaviors(children)
    if payload["effect"] == "fly" and children is not None:
        behaviors = tuple(
            RawBehavior("anim", ET.tostring(child, encoding="unicode"))
            if _xml_local_name(child.tag) == "anim"
            else behavior
            for child, behavior in zip(children, behaviors, strict=True)
        )
    return behaviors


class AnimationEffect:
    """Handle representing a supported slide animation effect.

    :attr:`behaviors` lists the effect's behaviours (see
    :mod:`wolfppt.slide_animation_behaviors`). Assign a new sequence, or call
    :meth:`set_behavior` or :meth:`add_behavior`, to edit them; the edit is
    written on the next save. An edited preset effect becomes a custom
    effect (``effect == "custom"``, PowerPoint preset ID 0) of the same
    class, except that a single motion behaviour keeps a motion path a
    motion path. Raw behaviours (foreign properties, media, and fly preset
    expressions) remain read-only.

    Strict and Transitional packages share inspection fields. ``preset_subtype``
    is an integer or None; ``repeat_duration`` retains XML milliseconds or
    ``indefinite``. ``acceleration`` and ``deceleration`` are fractional
    floats in 0..1 (None omits the attribute); their sum must not exceed 1.
    Set either property or use :meth:`SlideAnimation.set_acceleration_deceleration`
    for an atomic pair edit. ``direction`` is the fly edge or wipe sweep
    (left/right/up/down), None for nondirectional presets.
    ``animate_background``, ``reverse_order`` and ``auto_update_background``
    patch paragraph-build attributes; assign None to omit an attribute and use
    its XML default (False, False, True). ``restart`` accepts
    None, ``always``, ``whenNotActive``, or ``never`` and queues an edit.
    These policies coincide for a linear main sequence that
    activates each timing node once; repeat count is independent of restart.
    """

    def __init__(
        self,
        facade: SlideAnimation,
        timing_id: int,
        shape_id: int | str,
        effect: str,
        start: str,
        delay: float,
        duration: float,
        animation_class: str = "entrance",
        repeat_count: int = 1,
        rewind: bool = False,
        auto_reverse: bool = False,
        path: tuple[tuple[float, float], ...] | None = None,
        options: dict[str, Any] | None = None,
        timing_markup: str | None = None,
        build_markup: str | None = None,
        property_animations: tuple[PropertyAnimation, ...] = (),
        behaviors: tuple[Behavior, ...] = (),
    ) -> None:
        self._facade = facade
        self._behaviors = behaviors
        self.timing_id = timing_id
        self.shape_id = shape_id
        self._effect = effect
        self._start = start
        self._delay = delay
        self._duration = duration
        self._animation_class = animation_class
        self._repeat_count = repeat_count
        self._rewind = rewind
        self._auto_reverse = auto_reverse
        self.path = path
        self._text_build = "as_one"
        self._build_level: int | None = None
        self._build_delay: float | None = None
        self.chart_build = "as_one"
        self.after_animation = "none"
        self.dim_color: str | None = None
        self.amount: float | None = None
        self.color: str | None = None
        self.color_target: str | None = None
        self._apply_options(options)
        # Saved markup (None until the effect is written by a save).
        self.timing_markup = timing_markup
        self._edited_timing_markup: str | None = None
        self.build_markup = build_markup
        self.property_animations = property_animations

    def _apply_options(self, options: dict[str, Any] | None) -> None:
        for key, default in _DEFAULT_OPTIONS.items():
            setattr(
                self,
                f"_{key}" if key in {"text_build", "build_delay", "build_level"} else key,
                (options or {}).get(key, default),
            )
        values = options or {}
        self._preset_subtype: int | None = values.get("preset_subtype")
        self.repeat_duration: str | None = values.get("repeat_duration")
        self._acceleration: float | None = values.get("acceleration")
        self._deceleration: float | None = values.get("deceleration")
        self.direction: str | None = values.get("direction")
        self._restart: str | None = values.get("restart")
        self._fill: str | None = values.get("fill", "remove" if self.rewind else "hold")
        default_paragraph = (
            "p"
            if self.text_build == "by_paragraph"
            or (self.text_build in ("by_word", "by_letter") and self.build_level is not None)
            else None
        )
        self._paragraph_build: str | None = values.get("paragraph_build", default_paragraph)
        self._animate_background: bool = values.get("animate_background", False)
        self._reverse_order: bool = values.get("reverse_order", False)
        self._auto_update_background: bool = values.get("auto_update_background", True)

    def _option_values(self) -> dict[str, Any]:
        return {
            **{key: getattr(self, key) for key in _DEFAULT_OPTIONS},
            "direction": self.direction,
        }

    @property
    def effect(self) -> str:
        return self._effect

    @effect.setter
    def effect(self, value: str) -> None:
        self._facade._set_effect_property(self, "effect", value)

    @property
    def animation_class(self) -> str:
        return self._animation_class

    @animation_class.setter
    def animation_class(self, value: str) -> None:
        self._facade._set_effect_property(self, "animation_class", value)

    @property
    def duration(self) -> float:
        """Effect duration in seconds."""
        return self._duration

    @duration.setter
    def duration(self, value: float) -> None:
        self._facade._set_effect_property(self, "duration", value)

    @property
    def delay(self) -> float:
        """Trigger delay in seconds."""
        return self._delay

    @delay.setter
    def delay(self, value: float) -> None:
        self._facade._set_effect_property(self, "delay", value)

    @property
    def repeat_count(self) -> int:
        return self._repeat_count

    @repeat_count.setter
    def repeat_count(self, value: int) -> None:
        self._facade._set_effect_property(self, "repeat_count", value)

    @property
    def rewind(self) -> bool:
        return self._rewind

    @rewind.setter
    def rewind(self, value: bool) -> None:
        self._facade._set_effect_property(self, "rewind", value)

    @property
    def start(self) -> str:
        return self._start

    @start.setter
    def start(self, value: str) -> None:
        self._facade._set_effect_property(self, "start", value)

    @property
    def text_build(self) -> str:
        return self._text_build

    @text_build.setter
    def text_build(self, value: str) -> None:
        self._facade._set_effect_property(self, "text_build", value)

    @property
    def build_level(self) -> int | None:
        """Paragraph build level, from 1 through 5."""
        return self._build_level

    @build_level.setter
    def build_level(self, value: int | None) -> None:
        self._facade._set_effect_property(self, "build_level", value)

    @property
    def build_delay(self) -> float | None:
        """Word/letter iteration delay as a percentage, not seconds."""
        return self._build_delay

    @build_delay.setter
    def build_delay(self, value: float | None) -> None:
        self._facade._set_effect_property(self, "build_delay", value)

    @property
    def preset_subtype(self) -> int | None:
        return self._preset_subtype

    @preset_subtype.setter
    def preset_subtype(self, value: int | None) -> None:
        self._facade._set_effect_property(self, "preset_subtype", value)

    def _restore(self, info: dict[str, Any]) -> None:
        """Hydrate inspected state without invoking public mutation setters."""
        self.__init__(
            self._facade,
            info["timing_id"],
            info["shape_id"],
            info["effect"],
            info["start"],
            info["delay"],
            info["duration"],
            info["animation_class"],
            info["repeat_count"],
            info["rewind"],
            info["auto_reverse"],
            path=info.get("path"),
            options=info,
            timing_markup=info.get("timing_markup"),
            build_markup=info.get("build_markup"),
            property_animations=info.get("property_animations", ()),
            behaviors=info.get("behaviors", ()),
        )

    def _restore_preview(self, info: dict[str, Any]) -> None:
        saved_markup = self.timing_markup
        self._restore(info)
        self._edited_timing_markup = self.timing_markup
        # Sequence stale-handle checks compare this snapshot with saved bytes.
        self.timing_markup = saved_markup

    @property
    def restart(self) -> str | None:
        """Restart policy as an XML enum (None omits the attribute)."""
        return self._restart

    @restart.setter
    def restart(self, value: str | None) -> None:
        self._facade._set_effect_restart(self, value)

    @property
    def fill(self) -> str | None:
        """Effect FillMode/literal; None omits fill. Unsupported playback modes refuse."""
        return self._fill

    @fill.setter
    def fill(self, value: str | None) -> None:
        value = coerce_fill(value)
        facade = self._facade
        facade._ensure_loaded()
        if self not in facade._effects:
            raise SlideAnimationRefusalError("Animation effect not found on slide")
        facade._require_transitional_effect(self)
        self._fill = value
        self._rewind = value == "remove"
        facade._effect_updates.get(self.timing_id, {}).pop("rewind", None)
        facade._queue_timing_option(self, "fill", value)

    @property
    def paragraph_build(self) -> str | None:
        """ParagraphBuildType/literal from p:bldP; None omits build.

        Paragraph mode uses the existing text staging; whole/allAtOnce animate
        together. Custom declarations round-trip but bounded playback refuses.
        Word/letter iteration and non-text targets cannot take this edit.
        """
        return self._paragraph_build

    @paragraph_build.setter
    def paragraph_build(self, value: str | None) -> None:
        self._facade._set_paragraph_build(self, value)

    @property
    def animate_background(self) -> bool:
        """Whether to animate the shape background alongside its text."""
        return self._animate_background

    @animate_background.setter
    def animate_background(self, value: bool | None) -> None:
        self._facade._set_effect_property(self, "animate_background", value)

    @property
    def reverse_order(self) -> bool:
        """Whether to build paragraphs in reverse order."""
        return self._reverse_order

    @reverse_order.setter
    def reverse_order(self, value: bool | None) -> None:
        self._facade._set_effect_property(self, "reverse_order", value)

    @property
    def auto_update_background(self) -> bool:
        """Whether PowerPoint should update the background animation automatically."""
        return self._auto_update_background

    @auto_update_background.setter
    def auto_update_background(self, value: bool | None) -> None:
        self._facade._set_effect_property(self, "auto_update_background", value)

    @property
    def acceleration(self) -> float | None:
        """Fraction of the effect spent accelerating; None omits accel."""
        return self._acceleration

    @acceleration.setter
    def acceleration(self, value: float | None) -> None:
        self._facade._ensure_loaded()
        self._facade._set_effect_easing(self, value, self._deceleration)

    @property
    def deceleration(self) -> float | None:
        """Fraction of the effect spent decelerating; None omits decel."""
        return self._deceleration

    @deceleration.setter
    def deceleration(self, value: float | None) -> None:
        self._facade._ensure_loaded()
        self._facade._set_effect_easing(self, self._acceleration, value)

    @property
    def auto_reverse(self) -> bool:
        """Whether the effect reverses direction after each iteration."""
        return self._auto_reverse

    @auto_reverse.setter
    def auto_reverse(self, value: bool) -> None:
        self._facade._set_effect_auto_reverse(self, value)

    @property
    def behaviors(self) -> tuple[Behavior, ...]:
        """The effect's behaviours in timeline order."""
        return self._behaviors

    @behaviors.setter
    def behaviors(self, value: Sequence[AnimationBehavior]) -> None:
        self._facade._set_effect_behaviors(self, value)

    def set_behavior(self, index: int, behavior: AnimationBehavior) -> None:
        """Replace the behaviour at ``index``."""
        behaviors = list(self._behaviors)
        if isinstance(index, bool) or not isinstance(index, int):
            raise SlideAnimationRefusalError("Behaviour index must be an integer")
        try:
            behaviors[index] = behavior
        except IndexError as exc:
            raise SlideAnimationRefusalError(
                f"Behaviour index {index} is out of range for {len(behaviors)} behaviour(s)"
            ) from exc
        self.behaviors = behaviors

    def add_behavior(self, behavior: AnimationBehavior) -> None:
        """Append a behaviour (for example from :class:`BehaviorFactory`)."""
        self.behaviors = (*self._behaviors, behavior)

    @property
    def motion_path(self) -> MotionPath | None:
        """The command list of the effect's first motion behaviour, if any."""
        for behavior in self._behaviors:
            if isinstance(behavior, MotionBehavior) and behavior.path is not None:
                return behavior.path
        return None

    def remove(self) -> None:
        """Remove this animation effect from the slide."""
        self._facade.remove(self)

    def __repr__(self) -> str:
        return (
            f"AnimationEffect(timing_id={self.timing_id}, shape_id={self.shape_id!r}, "
            f"effect={self.effect!r}, animation_class={self.animation_class!r}, "
            f"start={self.start!r}, delay={self.delay}, duration={self.duration}, "
            f"repeat_count={self.repeat_count}, rewind={self.rewind}, "
            f"auto_reverse={self.auto_reverse}, path={self.path!r})"
        )


class UnsupportedAnimationEffect:
    """Handle representing an unsupported / foreign animation effect."""

    def __init__(
        self,
        facade: SlideAnimation,
        timing_id: int | None,
        shape_id: int | str | None,
        name: str,
        preset_class: str | None = None,
        preset_id: str | None = None,
        node_type: str | None = None,
        raw_element: Any = None,
        property_animations: tuple[PropertyAnimation, ...] = (),
        behaviors: tuple[Behavior, ...] = (),
    ) -> None:
        self._facade = facade
        self.timing_id = timing_id
        self.shape_id = shape_id
        self.name = name
        # Read-only: foreign groups are never rewritten.
        self.behaviors = behaviors
        self.preset_class = preset_class
        self.preset_id = preset_id
        self.node_type = node_type
        self.raw_element = raw_element
        self.property_animations = property_animations

    def remove(self) -> None:
        """Attempting to remove an unsupported animation raises SlideAnimationRefusalError."""
        raise SlideAnimationRefusalError(
            "Cannot remove unsupported/foreign animation effect "
            f"(timing_id={self.timing_id}, name={self.name!r})"
        )

    def __repr__(self) -> str:
        return (
            f"UnsupportedAnimationEffect(timing_id={self.timing_id}, shape_id={self.shape_id!r}, "
            f"name={self.name!r}, preset_class={self.preset_class!r}, preset_id={self.preset_id!r})"
        )


class SlideAnimation:
    """Slide animation facade for inspecting, authoring, reordering, and removing animations.

    Supports presets, custom property keyframes and motion paths, start triggers,
    delay, duration, repeat count, rewind, auto-reverse, restart and fractional
    acceleration/deceleration. Fly/wipe entrances and exits accept cardinal
    direction options. Set the timing properties on a handle to queue edits;
    :meth:`set_restart` also accepts a timing ID. Every ``add_*`` method accepts
    restart=None, ``always``, ``whenNotActive``, or ``never``. A main sequence
    activates each timing node once, so these policies have the same playback
    until reactivation exists; none means repeat. Call :meth:`move` to reorder.

    Save-first authoring: the facade reads timing state from the saved
    package, so call ``Presentation.save()`` after creating a presentation or
    adding a slide and before inspecting or editing that slide's animations.
    Unsaved slides raise ``SlideAnimationRefusalError``. Edits are queued and
    written on the next save; a saved presentation does not need reopening.

    Preserves unsupported animation groups and direct tmRoot media timing
    byte-for-byte. Never duplicates timing roots or IDs.
    """

    def __init__(self, slide: Any) -> None:
        self._slide = slide
        self._loaded: bool = False
        self._loaded_source_path: Any = None
        self._has_queued_edits: bool = False
        self._effects: list[AnimationEffect] = []
        self._unsupported_effects: list[UnsupportedAnimationEffect] = []
        self._has_timing: bool = False
        self._clear_supported: bool = False
        self._removed_timing_ids: set[int] = set()
        self._added_effects: list[dict[str, Any]] = []
        self._next_alloc_id: int = 0
        self._timing_updates: dict[int, dict[str, str | None]] = {}
        self._build_updates: dict[int, str | None] = {}
        self._effect_updates: dict[int, dict[str, Any]] = {}
        self._order_edited: bool = False
        self._sequence_moves: list[SequenceMove] = []

    def _slide_identifier(self) -> int | str:
        partname = getattr(self._slide, "partname", None)
        if partname:
            return str(partname)
        idx = getattr(self._slide, "_index", None)
        if idx is not None:
            return int(idx)
        raise SlideAnimationRefusalError(_SAVE_FIRST_MESSAGE)

    def _sync_state(self) -> None:
        if getattr(self._slide, "_deleted", False):
            raise SlideAnimationRefusalError("Cannot inspect or edit animations on a deleted slide")
        prs = getattr(self._slide, "_presentation", None)
        curr_path = getattr(prs, "_source_path", None) if prs is not None else None
        partname = self._slide_identifier()
        pending_edits = getattr(prs, "_slide_animation_edits", None) if prs is not None else None
        has_pending = isinstance(pending_edits, dict) and partname in pending_edits

        if not self._loaded:
            self._reload()
            return

        # Detect presentation save: source path updated or pending edits committed and cleared
        if curr_path != self._loaded_source_path or (self._has_queued_edits and not has_pending):
            self._reload()

    def _reload(self) -> None:
        prs = getattr(self._slide, "_presentation", None)
        self._loaded_source_path = getattr(prs, "_source_path", None) if prs is not None else None

        existing_handles: dict[int, AnimationEffect] = {
            e.timing_id: e for e in self._effects if isinstance(e.timing_id, int)
        }

        self._effects = []
        self._unsupported_effects = []
        self._added_effects = []
        self._removed_timing_ids = set()
        self._timing_updates = {}
        self._build_updates = {}
        self._effect_updates = {}
        self._clear_supported = False
        self._has_queued_edits = False
        self._order_edited = False
        self._sequence_moves = []

        root = _get_slide_xml_root(self._slide)
        max_id = 0
        has_tm_root = False
        has_main_seq = False

        if root is not None:
            info = _read_slide_animation_xml(root)
            self._has_timing = info.get("has_timing", False)
            max_id = info.get("max_timing_id", 0)
            has_tm_root = info.get("has_tm_root", False)
            has_main_seq = info.get("has_main_seq", False)

            for eff in info.get("supported_effects", []):
                tid = eff["timing_id"]
                handle = existing_handles.get(tid)
                if handle is not None:
                    handle._restore(eff)
                else:
                    handle = AnimationEffect(
                        facade=self,
                        timing_id=tid,
                        shape_id=eff["shape_id"],
                        effect=eff["effect"],
                        start=eff["start"],
                        delay=eff["delay"],
                        duration=eff["duration"],
                        animation_class=eff["animation_class"],
                        repeat_count=eff["repeat_count"],
                        rewind=eff["rewind"],
                        auto_reverse=eff["auto_reverse"],
                        path=eff.get("path"),
                        options=eff,
                        timing_markup=eff.get("timing_markup"),
                        build_markup=eff.get("build_markup"),
                        property_animations=eff.get("property_animations", ()),
                        behaviors=eff.get("behaviors", ()),
                    )
                self._effects.append(handle)

            for ueff in info.get("unsupported_effects", []):
                self._unsupported_effects.append(
                    UnsupportedAnimationEffect(
                        facade=self,
                        timing_id=ueff.get("timing_id"),
                        shape_id=ueff.get("shape_id"),
                        name=ueff.get("name", "unsupported"),
                        preset_class=ueff.get("preset_class"),
                        preset_id=ueff.get("preset_id"),
                        node_type=ueff.get("node_type"),
                        raw_element=ueff.get("raw_element"),
                        property_animations=ueff.get("property_animations", ()),
                        behaviors=ueff.get("behaviors", ()),
                    )
                )

        # Base next allocation id
        self._next_alloc_id = max_id
        if not has_tm_root:
            self._next_alloc_id += 1
        if not has_main_seq:
            self._next_alloc_id += 1

        # Check if presentation already holds pending edits for this slide part
        partname = self._slide_identifier()
        pending_edits = getattr(prs, "_slide_animation_edits", None) if prs is not None else None
        if isinstance(pending_edits, dict) and partname in pending_edits:
            spec = pending_edits[partname]
            if getattr(spec, "clear_supported", False):
                self._clear_supported = True
                self._effects.clear()
            if getattr(spec, "removed_timing_ids", None):
                rem_set = set(spec.removed_timing_ids)
                self._removed_timing_ids.update(rem_set)
                self._effects = [e for e in self._effects if e.timing_id not in rem_set]
            if getattr(spec, "added_effects", None):
                for eff_data in spec.added_effects:
                    tid = eff_data.get("timing_id")
                    if tid is None:
                        self._next_alloc_id += 1
                        tid = self._next_alloc_id
                        self._next_alloc_id += 1
                    else:
                        self._next_alloc_id = max(self._next_alloc_id, tid + 1)
                    handle = AnimationEffect(
                        facade=self,
                        timing_id=tid,
                        shape_id=eff_data["shape_id"],
                        effect=eff_data["effect"],
                        start=eff_data.get("start", "on_click"),
                        delay=float(eff_data.get("delay", 0.0)),
                        duration=float(eff_data.get("duration", 0.5)),
                        animation_class=eff_data.get("animation_class", "entrance"),
                        repeat_count=int(eff_data.get("repeat_count", 1)),
                        rewind=bool(eff_data.get("rewind", False)),
                        auto_reverse=bool(eff_data.get("auto_reverse", False)),
                        path=eff_data.get("path"),
                        options={
                            **eff_data,
                            "repeat_duration": coerce_repeat_duration(
                                eff_data.get("repeat_duration")
                            ),
                        },
                        behaviors=_authored_behaviors({**eff_data, "timing_id": tid}),
                    )
                    self._effects.append(handle)
                    self._added_effects.append(dict(eff_data))
            effect_order = getattr(spec, "effect_order", None)
            if effect_order is not None:
                rank = {tid: pos for pos, tid in enumerate(effect_order)}
                self._effects.sort(key=lambda e: rank.get(e.timing_id, len(rank)))
                self._order_edited = True
            for timing_id, updates in getattr(spec, "timing_updates", {}).items():
                handle = next((e for e in self._effects if e.timing_id == timing_id), None)
                if handle is not None:
                    if "restart" in updates:
                        handle._restart = updates["restart"]
                    if "autoRev" in updates:
                        handle._auto_reverse = updates["autoRev"] == "1"
                    if "fill" in updates:
                        handle._fill = updates["fill"]
                        handle._rewind = handle._fill == "remove"
                    if "accel" in updates:
                        handle._acceleration = (
                            None if updates["accel"] is None else int(updates["accel"]) / 100000
                        )
                    if "decel" in updates:
                        handle._deceleration = (
                            None if updates["decel"] is None else int(updates["decel"]) / 100000
                        )
                    self._timing_updates[timing_id] = dict(updates)
            for timing_id, value in getattr(spec, "build_updates", {}).items():
                handle = next((e for e in self._effects if e.timing_id == timing_id), None)
                if handle is not None:
                    self._apply_paragraph_build(handle, value)
                    self._build_updates[timing_id] = value
            self._has_queued_edits = True
            self._effect_updates = {
                key: dict(value) for key, value in getattr(spec, "effect_updates", {}).items()
            }
            if self._effect_updates:
                preview = _get_slide_xml_root(self._slide)
                apply_animation_spec(preview, spec)
                by_id = {e.timing_id: e for e in self._effects}
                for info in _read_slide_animation_xml(preview)["supported_effects"]:
                    if info["timing_id"] in by_id:
                        by_id[info["timing_id"]]._restore_preview(info)
            restore_sequence_moves(self, spec)

        self._loaded = True

    def _ensure_loaded(self) -> None:
        self._sync_state()

    def _spec(self) -> AnimationSpec:
        return AnimationSpec(
            clear_supported=self._clear_supported,
            removed_timing_ids=sorted(self._removed_timing_ids),
            added_effects=list(self._added_effects),
            effect_order=[e.timing_id for e in self._effects] if self._order_edited else None,
            timing_updates={key: dict(value) for key, value in self._timing_updates.items()},
            build_updates=dict(self._build_updates),
            effect_updates={key: dict(value) for key, value in self._effect_updates.items()},
            sequence_moves=list(self._sequence_moves),
        )

    def _queue(self) -> None:
        self._slide._presentation._queue_slide_animation(self._slide_identifier(), self._spec())
        self._has_queued_edits = True

    def _set_effect_property(self, effect: AnimationEffect, name: str, value: Any) -> None:
        """Preflight the full pending edit before changing live or queued state."""
        self._ensure_loaded()
        if effect not in self._effects:
            raise SlideAnimationRefusalError("Animation effect not found on slide")
        self._require_transitional_effect(effect)
        candidate = self._spec()
        candidate.effect_updates.setdefault(effect.timing_id, {})[name] = value
        preview = _get_slide_xml_root(self._slide)
        apply_animation_spec(preview, candidate)
        info = next(
            (
                entry
                for entry in _read_slide_animation_xml(preview)["supported_effects"]
                if entry["timing_id"] == effect.timing_id
            ),
            None,
        )
        if info is None:
            raise SlideAnimationRefusalError("Edit would make the animation unsupported")
        self._slide._presentation._queue_slide_animation(self._slide_identifier(), candidate)
        self._effect_updates = candidate.effect_updates
        self._has_queued_edits = True
        effect._restore_preview(info)

    @property
    def effects(self) -> tuple[AnimationEffect, ...]:
        """Supported animation effects on this slide in main-sequence order."""
        self._sync_state()
        return tuple(self._effects)

    @property
    def interactive_sequences(self) -> tuple[InteractiveSequence, ...]:
        """Read saved and queued single-activation shape-click sequences."""
        return interactive_sequences(self)

    def add_triggered_sequence(
        self, trigger_shape: Any, effects: Sequence[AnimationEffect]
    ) -> InteractiveSequence:
        """Move main effects into one shape-triggered sequence on the next save.

        The first effect starts on an explicit shape click. Later effects use
        with_previous or after_previous. Author/edit effects before moving them;
        interactive effect snapshots are read-only.
        """
        return add_triggered_sequence(self, trigger_shape, effects)

    @property
    def unsupported_effects(self) -> tuple[UnsupportedAnimationEffect, ...]:
        """Tuple of unsupported / foreign animation effect groups on this slide."""
        self._sync_state()
        return tuple(self._unsupported_effects)

    @property
    def has_animations(self) -> bool:
        """True if the slide has supported or foreign animation groups."""
        self._sync_state()
        return bool(self._effects or self._unsupported_effects or self.interactive_sequences)

    @property
    def property_animations(self) -> tuple[PropertyAnimation, ...]:
        """Read-only ``p:anim`` snapshots with keyframes and calculation mode.

        Lists supported effects first, then unsupported groups, each in
        main-sequence order. Author editable properties with PropertyBehavior
        through :meth:`add_custom`; this inspection snapshot is unchanged.
        """
        self._sync_state()
        return tuple(
            animation
            for effect in (*self._effects, *self._unsupported_effects)
            for animation in effect.property_animations
        )

    def _validate_target_shape(self, shape: Any) -> int | str:
        self._ensure_loaded()

        if getattr(self._slide, "_deleted", False):
            raise SlideAnimationRefusalError("Cannot add animation to deleted slide")
        if getattr(shape, "_deleted", False):
            raise SlideAnimationRefusalError("Cannot add animation to deleted shape")

        shape_slide = getattr(shape, "_slide", None)
        if shape_slide is not None and shape_slide is not self._slide:
            raise SlideAnimationRefusalError("Shape does not belong to this slide")

        shape_id = _extract_shape_id(shape)
        if not _is_shape_id_on_slide(self._slide, shape_id):
            raise SlideAnimationRefusalError(f"Target shape ID {shape_id} not found on slide")
        return shape_id

    def _add_effect(
        self,
        shape: Any,
        effect: str,
        animation_class: str,
        *,
        start: str,
        delay: float,
        duration: float,
        repeat_count: int,
        rewind: bool,
        auto_reverse: bool,
        restart: str | None = None,
        repeat_duration: float | str | None = None,
        acceleration: float | None = None,
        deceleration: float | None = None,
        path: Any = None,
        options: dict[str, Any] | None = None,
        behaviors: Sequence[AnimationBehavior] | None = None,
    ) -> AnimationEffect:
        shape_id = self._validate_target_shape(shape)
        norm_start = _normalize_start(start)
        norm_delay = _validate_timing_value("delay", delay)
        norm_duration = _validate_timing_value("duration", duration)
        norm_repeat_count = _validate_repeat_count(repeat_count)
        norm_rewind = _validate_rewind(rewind)
        norm_auto_reverse = _validate_auto_reverse(auto_reverse)
        norm_restart = coerce_restart(restart)
        norm_repeat_duration = coerce_repeat_duration(repeat_duration)
        norm_acceleration, norm_deceleration = coerce_acceleration_deceleration(
            acceleration, deceleration
        )

        norm_behaviors = None if behaviors is None else coerce_behaviors(behaviors)
        if effect == "custom":
            if animation_class not in VALID_CUSTOM_CLASSES:
                raise SlideAnimationRefusalError(
                    f"Invalid animation_class: {animation_class!r} (use one of "
                    f"{', '.join(VALID_CUSTOM_CLASSES)})"
                )
            norm_effect = "custom"
            norm_path = None
        elif animation_class == "motion_path":
            norm_effect = "motion_path"
            norm_path = path if norm_behaviors is not None else _validate_path_coordinates(path)
        else:
            norm_effect = _normalize_effect(effect, animation_class)
            norm_path = None
            if norm_effect == "appear":
                norm_duration = 0.0
        root = _get_slide_xml_root(self._slide)
        norm_options = coerce_effect_options(
            norm_effect,
            animation_class,
            options or {},
            shape_build_kind(root, shape_id) if root is not None else None,
        )

        payload: dict[str, Any] = {
            "effect": norm_effect,
            "shape_id": shape_id,
            "start": norm_start,
            "delay": norm_delay,
            "duration": norm_duration,
            "timing_id": self._next_alloc_id + 1,
            "animation_class": animation_class,
            "repeat_count": norm_repeat_count,
            "rewind": norm_rewind,
            "auto_reverse": norm_auto_reverse,
            "restart": norm_restart,
            "repeat_duration": repeat_duration,
            "acceleration": norm_acceleration,
            "deceleration": norm_deceleration,
            "path": norm_path,
            **norm_options,
        }
        if norm_behaviors is not None:
            payload["behaviors"] = norm_behaviors
        listed_behaviors = _authored_behaviors(payload)

        self._next_alloc_id += 1
        new_timing_id = self._next_alloc_id
        self._next_alloc_id += 1
        eff_handle = AnimationEffect(
            facade=self,
            timing_id=new_timing_id,
            shape_id=shape_id,
            effect=norm_effect,
            start=norm_start,
            delay=norm_delay,
            duration=norm_duration,
            animation_class=animation_class,
            repeat_count=norm_repeat_count,
            rewind=norm_rewind,
            auto_reverse=norm_auto_reverse,
            path=norm_path,
            options={
                **norm_options,
                "restart": norm_restart,
                "repeat_duration": norm_repeat_duration,
                "acceleration": norm_acceleration,
                "deceleration": norm_deceleration,
            },
            behaviors=listed_behaviors,
        )
        self._effects.append(eff_handle)
        self._added_effects.append(payload)
        self._queue()
        return eff_handle

    def add_entrance(
        self,
        shape: Any,
        effect: str = "appear",
        *,
        start: str = "on_click",
        delay: float = 0.0,
        duration: float = 0.5,
        repeat_count: int = 1,
        rewind: bool = False,
        auto_reverse: bool = False,
        restart: str | None = None,
        repeat_duration: float | str | None = None,
        acceleration: float | None = None,
        deceleration: float | None = None,
        direction: str | None = None,
        text_build: str = "as_one",
        build_level: int | None = None,
        build_delay: float | None = None,
        after_animation: str = "none",
        dim_color: str | None = None,
        chart_build: str = "as_one",
        animate_background: bool | None = None,
        reverse_order: bool | None = None,
        auto_update_background: bool | None = None,
    ) -> AnimationEffect:
        """Add an entrance animation with trigger and timing controls.

        ``effect`` accepts ``appear``, ``fade``, ``fly``, ``wipe``, ``zoom``,
        ``wheel``, ``dissolve``, and ``bounce``. ``delay`` is the trigger delay
        in seconds; ``repeat_count`` is a positive whole number. ``auto_reverse``
        controls reversal between iterations independently of ``rewind``.
        ``restart`` is None, ``always``, ``whenNotActive``, or ``never`` and
        controls reactivation, not repetition.
        ``repeat_duration`` is None (omit), ``"indefinite"``, or finite seconds
        in 0..2147483.647; it is independent of count, restart and reversal.
        ``acceleration`` and ``deceleration`` are 0..1 fractions, sum <=1.
        ``direction`` is left/right/up/down for fly (off-slide edge) and
        wipe (filter sweep); None preserves the established preset default.
        The effect is appended to the end of the main sequence; use
        :meth:`move` to reposition it.

        ``text_build`` (text shapes) is ``as_one``, ``by_paragraph`` (with
        ``build_level`` 1-5), ``by_word``, or ``by_letter`` (with
        ``build_delay``, the percentage delay between words or letters,
        default 10). Word/letter builds also accept ``build_level`` 1-5 for
        serial paragraph groups. ``after_animation`` is ``none``, ``dim`` (with
        ``dim_color`` as ``RRGGBB`` or a scheme colour name), ``hide``, or
        ``hide_on_next_click``. ``chart_build`` (chart frames) is ``as_one``,
        ``by_series``, ``by_category``, ``by_element_in_series``, or
        ``by_element_in_category``. Element builds author and reopen the chart's
        point grouping; playback raises ``AnimationFrameRefusal`` for these
        element-level modes.
        ``animate_background``, ``reverse_order`` and ``auto_update_background``
        accept booleans for text shapes. None preserves existing creation
        defaults, including background animation for non-placeholder shapes.

        Requires a saved slide: call ``Presentation.save()`` first, otherwise
        ``SlideAnimationRefusalError`` is raised.
        """
        return self._add_effect(
            shape,
            effect,
            "entrance",
            start=start,
            delay=delay,
            duration=duration,
            repeat_count=repeat_count,
            rewind=rewind,
            auto_reverse=auto_reverse,
            restart=restart,
            repeat_duration=repeat_duration,
            acceleration=acceleration,
            deceleration=deceleration,
            options={
                "text_build": text_build,
                "build_level": build_level,
                "build_delay": build_delay,
                "after_animation": after_animation,
                "dim_color": dim_color,
                "chart_build": chart_build,
                "direction": direction,
                "animate_background": animate_background,
                "reverse_order": reverse_order,
                "auto_update_background": auto_update_background,
            },
        )

    def add_exit(
        self,
        shape: Any,
        effect: str = "fade",
        *,
        start: str = "on_click",
        delay: float = 0.0,
        duration: float = 0.5,
        repeat_count: int = 1,
        rewind: bool = False,
        auto_reverse: bool = False,
        restart: str | None = None,
        repeat_duration: float | str | None = None,
        acceleration: float | None = None,
        deceleration: float | None = None,
        direction: str | None = None,
        text_build: str = "as_one",
        build_level: int | None = None,
        build_delay: float | None = None,
        after_animation: str = "none",
        dim_color: str | None = None,
        chart_build: str = "as_one",
    ) -> AnimationEffect:
        """Add an exit animation with trigger and timing controls.

        ``effect`` accepts ``fade``, ``fly``, ``wipe``, ``zoom``, ``wheel``,
        ``dissolve``, and ``bounce``. Text build, after-animation, and chart
        build options match :meth:`add_entrance`. The effect is appended to
        the end of the main sequence. Requires a saved slide: call
        ``Presentation.save()`` first, otherwise ``SlideAnimationRefusalError``
        is raised.
        """
        return self._add_effect(
            shape,
            effect,
            "exit",
            start=start,
            delay=delay,
            duration=duration,
            repeat_count=repeat_count,
            rewind=rewind,
            auto_reverse=auto_reverse,
            restart=restart,
            repeat_duration=repeat_duration,
            acceleration=acceleration,
            deceleration=deceleration,
            options={
                "text_build": text_build,
                "build_level": build_level,
                "build_delay": build_delay,
                "after_animation": after_animation,
                "dim_color": dim_color,
                "chart_build": chart_build,
                "direction": direction,
            },
        )

    def add_emphasis(
        self,
        shape: Any,
        effect: str,
        *,
        start: str = "on_click",
        delay: float = 0.0,
        duration: float | None = None,
        repeat_count: int = 1,
        rewind: bool = False,
        auto_reverse: bool = False,
        restart: str | None = None,
        repeat_duration: float | str | None = None,
        acceleration: float | None = None,
        deceleration: float | None = None,
        amount: float | None = None,
        color: str | None = None,
        color_target: str | None = None,
        text_build: str = "as_one",
        build_level: int | None = None,
        build_delay: float | None = None,
        after_animation: str = "none",
        dim_color: str | None = None,
    ) -> AnimationEffect:
        """Add an emphasis animation with trigger and timing controls.

        ``effect`` accepts ``spin`` (``amount`` in degrees, default 360),
        ``grow_shrink`` (``amount`` as a size percentage, default 150),
        ``transparency`` (``amount`` as a transparency percentage, default
        50), ``color_change`` (``color`` as ``RRGGBB`` or a scheme colour name;
        ``color_target`` ``fill``, ``font``, or ``line``, default ``fill``),
        ``pulse``, and ``teeter``. ``duration`` defaults to PowerPoint's
        preset duration. Text build and after-animation options match
        :meth:`add_entrance`. Requires a saved slide.
        """
        norm_effect = _normalize_effect(effect, "emphasis")
        return self._add_effect(
            shape,
            norm_effect,
            "emphasis",
            start=start,
            delay=delay,
            duration=EMPHASIS_DEFAULT_DURATIONS[norm_effect] if duration is None else duration,
            repeat_count=repeat_count,
            rewind=rewind,
            auto_reverse=auto_reverse,
            restart=restart,
            repeat_duration=repeat_duration,
            acceleration=acceleration,
            deceleration=deceleration,
            options={
                "amount": amount,
                "color": color,
                "color_target": color_target,
                "text_build": text_build,
                "build_level": build_level,
                "build_delay": build_delay,
                "after_animation": after_animation,
                "dim_color": dim_color,
            },
        )

    def add_motion_path(
        self,
        shape: Any,
        coordinates: Sequence[Sequence[float]] | MotionPath,
        *,
        origin: str = "layout",
        edit_mode: str = "relative",
        start: str = "on_click",
        delay: float = 0.0,
        duration: float = 0.5,
        repeat_count: int = 1,
        rewind: bool = False,
        auto_reverse: bool = False,
        restart: str | None = None,
        repeat_duration: float | str | None = None,
        acceleration: float | None = None,
        deceleration: float | None = None,
    ) -> AnimationEffect:
        """Move a shape along a path.

        ``coordinates`` is either at least two coordinate pairs (a move then
        straight lines) or a :class:`MotionPath` built from move, line,
        curve, and close commands with per-vertex points types. ``origin``
        is ``layout`` or ``parent``; ``edit_mode`` is ``relative`` or
        ``fixed``. The saved path reads back through :attr:`AnimationEffect.motion_path`
        as the same command list; ``AnimationEffect.path`` holds the pairs
        when the path is an absolute move followed by lines.
        ``repeat_duration`` uses seconds, ``"indefinite"``, or None as in
        :meth:`add_entrance`.

        The effect is appended to the end of the main sequence. Requires a
        saved slide: call ``Presentation.save()`` first, otherwise
        ``SlideAnimationRefusalError`` is raised.
        """
        behaviors = None
        path: Any = coordinates
        if isinstance(coordinates, MotionPath) or (origin, edit_mode) != (
            "layout",
            "relative",
        ):
            if isinstance(coordinates, MotionPath):
                motion_path = coordinates
            else:
                points = _validate_path_coordinates(coordinates)
                motion_path = MotionPath().move_to(*points[0])
                for x, y in points[1:]:
                    motion_path = motion_path.line_to(x, y)
            behaviors = (
                BehaviorFactory().create_motion(motion_path, origin=origin, edit_mode=edit_mode),
            )
            path = _legacy_points(motion_path)
        return self._add_effect(
            shape,
            "motion_path",
            "motion_path",
            start=start,
            delay=delay,
            duration=duration,
            repeat_count=repeat_count,
            rewind=rewind,
            auto_reverse=auto_reverse,
            restart=restart,
            repeat_duration=repeat_duration,
            acceleration=acceleration,
            deceleration=deceleration,
            path=path,
            behaviors=behaviors,
        )

    @property
    def behavior_factory(self) -> BehaviorFactory:
        """Factory for behaviours to pass to :meth:`add_custom` or ``add_behavior``."""
        return BehaviorFactory()

    def add_custom(
        self,
        shape: Any,
        behaviors: Sequence[AnimationBehavior],
        *,
        animation_class: str = "emphasis",
        start: str = "on_click",
        delay: float = 0.0,
        duration: float = 0.5,
        repeat_count: int = 1,
        rewind: bool = False,
        auto_reverse: bool = False,
        restart: str | None = None,
        acceleration: float | None = None,
        deceleration: float | None = None,
    ) -> AnimationEffect:
        """Add a custom effect made of ``behaviors``.

        Build behaviours with :attr:`behavior_factory` (colour, motion,
        rotation, scale, set, command, filter, and property), each with its
        ``accumulate`` and ``additive`` modes. ``animation_class`` is
        ``entrance``, ``exit``, ``emphasis``, or ``motion_path``; the effect
        is written with PowerPoint's custom preset (ID 0) of that class, and
        a behaviour without its own ``duration`` takes the effect's.
        Requires a saved slide.
        """
        return self._add_effect(
            shape,
            "custom",
            animation_class,
            start=start,
            delay=delay,
            duration=duration,
            repeat_count=repeat_count,
            rewind=rewind,
            auto_reverse=auto_reverse,
            restart=restart,
            acceleration=acceleration,
            deceleration=deceleration,
            behaviors=behaviors,
        )

    def _set_effect_auto_reverse(self, effect: AnimationEffect, auto_reverse: Any) -> None:
        """Apply an auto-reverse edit to one supported effect handle."""
        value = _validate_auto_reverse(auto_reverse)
        self._ensure_loaded()
        if effect not in self._effects:
            raise SlideAnimationRefusalError(f"Animation effect {effect!r} not found on slide")
        if effect.auto_reverse == value:
            return

        self._require_transitional_effect(effect)
        effect._auto_reverse = value
        self._queue_timing_option(effect, "autoRev", "1" if value else None)

    def _set_effect_restart(self, effect: AnimationEffect, restart: Any) -> None:
        """Validate and queue an in-place restart edit on a supported effect."""
        value = coerce_restart(restart)
        self._ensure_loaded()
        if effect not in self._effects:
            raise SlideAnimationRefusalError(f"Animation effect {effect!r} not found on slide")
        if effect.restart == value:
            return
        self._require_transitional_effect(effect)
        effect._restart = value
        self._queue_timing_option(effect, "restart", value)

    def _set_effect_easing(
        self, effect: AnimationEffect, acceleration: Any, deceleration: Any
    ) -> None:
        """Validate the pair before changing a handle, pending payload, or queue."""
        acceleration, deceleration = coerce_acceleration_deceleration(acceleration, deceleration)
        self._ensure_loaded()
        if effect not in self._effects:
            raise SlideAnimationRefusalError(f"Animation effect {effect!r} not found on slide")
        if (effect.acceleration, effect.deceleration) == (acceleration, deceleration):
            return
        self._require_transitional_effect(effect)
        for payload in self._added_effects:
            if payload.get("timing_id") == effect.timing_id:
                payload.update(acceleration=acceleration, deceleration=deceleration)
                break
        else:
            updates = self._timing_updates.setdefault(effect.timing_id, {})
            updates.update(
                {
                    name: None if value is None else str(round(value * 100000))
                    for name, value in (("accel", acceleration), ("decel", deceleration))
                }
            )
        effect._acceleration, effect._deceleration = acceleration, deceleration
        self._queue()

    def set_acceleration_deceleration(
        self,
        effect_or_timing_id: AnimationEffect | int | str,
        acceleration: float | None,
        deceleration: float | None,
    ) -> AnimationEffect:
        """Set fractional effect easing atomically by handle or timing ID."""
        acceleration, deceleration = coerce_acceleration_deceleration(acceleration, deceleration)
        self._ensure_loaded()
        effect = self._resolve_supported_effect(effect_or_timing_id)
        self._set_effect_easing(effect, acceleration, deceleration)
        return effect

    def _require_transitional_effect(self, effect: AnimationEffect) -> None:
        """Refuse Strict timing writes before changing a handle or queue."""
        if effect.timing_markup is not None:
            group = ET.fromstring(effect.timing_markup)
            if group.find(f"{{{P_NS}}}cTn") is None:
                raise SlideAnimationRefusalError(
                    "Cannot edit Strict animation timing; inspection is read-only"
                )

    def _queue_timing_option(self, effect: AnimationEffect, name: str, value: str | None) -> None:
        """Patch saved time nodes; adjust pending authored payloads in place."""
        for payload in self._added_effects:
            if payload.get("timing_id") == effect.timing_id:
                if name == "restart":
                    payload["restart"] = value
                elif name == "fill":
                    payload["fill"] = value
                    payload["rewind"] = value == "remove"
                else:
                    payload["auto_reverse"] = value == "1"
                break
        else:
            self._timing_updates.setdefault(effect.timing_id, {})[name] = value
        self._queue()

    def _effect_payload(self, effect: AnimationEffect) -> dict[str, Any]:
        """The authoring payload that rewrites ``effect`` as it now stands."""
        payload: dict[str, Any] = {
            "effect": effect.effect,
            "shape_id": effect.shape_id,
            "start": effect.start,
            "delay": effect.delay,
            "duration": effect.duration,
            "timing_id": effect.timing_id,
            "animation_class": effect.animation_class,
            "repeat_count": effect.repeat_count,
            "rewind": effect.rewind,
            "auto_reverse": effect.auto_reverse,
            "restart": effect.restart,
            "acceleration": effect.acceleration,
            "deceleration": effect.deceleration,
            "fill": effect.fill,
            "path": effect.path,
            **effect._option_values(),
            "timing_markup": effect._edited_timing_markup or effect.timing_markup,
            "build_markup": effect.build_markup,
        }
        if effect.build_markup is None:
            for pending in self._added_effects:
                if pending.get("timing_id") == effect.timing_id:
                    payload.update(
                        {name: pending[name] for name in PARAGRAPH_BUILD_OPTIONS if name in pending}
                    )
                    break
        if payload["timing_markup"] is None:
            payload["repeat_duration"] = next(
                (
                    pending.get("repeat_duration")
                    for pending in self._added_effects
                    if pending.get("timing_id") == effect.timing_id
                ),
                None,
            )
        if effect.paragraph_build is not None:
            payload["paragraph_build"] = effect.paragraph_build
        if effect.effect == "custom" or (
            effect.effect == "motion_path"
            and _is_motion_path(effect.behaviors)
            and is_authorable(effect.behaviors)
        ):
            payload["behaviors"] = effect.behaviors
        return payload

    def _requeue_effect(self, effect: AnimationEffect, payload: dict[str, Any]) -> None:
        """Queue ``payload`` as the new form of ``effect``, keeping its position."""
        for index, pending in enumerate(self._added_effects):
            if pending.get("timing_id") == effect.timing_id:
                self._added_effects[index] = payload
                break
        else:
            # Re-adding a saved group appends it; keep its sequence position.
            self._order_edited = True
            self._removed_timing_ids.add(effect.timing_id)
            self._added_effects.append(payload)
        self._timing_updates.pop(effect.timing_id, None)
        self._build_updates.pop(effect.timing_id, None)
        self._effect_updates.pop(effect.timing_id, None)
        self._queue()

    @staticmethod
    def _apply_paragraph_build(effect: AnimationEffect, value: str | None) -> None:
        effect._paragraph_build = value
        effect._text_build = "by_paragraph" if value == "p" else "as_one"
        effect._build_level = (effect.build_level or 1) if value == "p" else None
        if effect.build_markup is not None:
            entry = ET.fromstring(effect.build_markup)
            if value is None:
                entry.attrib.pop("build", None)
            else:
                entry.set("build", value)
            if value == "p":
                entry.set("bldLvl", str(effect.build_level))
            effect.build_markup = ET.tostring(entry, encoding="unicode")

    def _set_paragraph_build(self, effect: AnimationEffect, value: Any) -> None:
        if value is not None and (not isinstance(value, str) or value not in PARAGRAPH_BUILD_TYPES):
            raise SlideAnimationRefusalError(f"Invalid paragraph_build: {value!r}")
        value = value.value if isinstance(value, ParagraphBuildType) else value
        self._ensure_loaded()
        if effect not in self._effects:
            raise SlideAnimationRefusalError("Animation effect not found on slide")
        self._require_transitional_effect(effect)
        root = _get_slide_xml_root(self._slide)
        if root is None or shape_build_kind(root, effect.shape_id) != "text":
            raise SlideAnimationRefusalError("paragraph_build needs a shape with text")
        if effect.text_build in ("by_word", "by_letter") or effect.chart_build != "as_one":
            raise SlideAnimationRefusalError("paragraph_build conflicts with iteration/chart build")
        pending = next(
            (p for p in self._added_effects if p.get("timing_id") == effect.timing_id), None
        )
        if pending is None and effect.build_markup is None:
            raise SlideAnimationRefusalError("paragraph_build needs an existing p:bldP entry")
        updates = self._effect_updates.get(effect.timing_id, {})
        updates.pop("text_build", None)
        updates.pop("build_delay", None)
        updates.pop("build_level", None)
        self._apply_paragraph_build(effect, value)
        if pending is not None:
            pending.update(
                paragraph_build=value,
                text_build=effect.text_build,
                build_level=effect.build_level,
                build_markup=effect.build_markup,
            )
        else:
            self._build_updates[effect.timing_id] = value
        self._queue()

    def _set_effect_behaviors(self, effect: AnimationEffect, value: Any) -> None:
        """Replace one supported effect's behaviours (see :class:`AnimationEffect`)."""
        behaviors = coerce_behaviors(value)
        self._ensure_loaded()
        if effect not in self._effects:
            raise SlideAnimationRefusalError(f"Animation effect {effect!r} not found on slide")
        options = effect._option_values()
        options["direction"] = None
        if effect.animation_class == "motion_path" and _is_motion_path(behaviors):
            name = "motion_path"
            path = _legacy_points(behaviors[0].path)  # type: ignore[union-attr]
        else:
            name = "custom"
            path = None
            options.update(amount=None, color=None, color_target=None)
        payload = {
            **self._effect_payload(effect),
            "effect": name,
            "path": path,
            **options,
            "behaviors": behaviors,
        }
        # A behaviour edit changes the preset identity, not unrelated timing.
        payload["preserve_preset_subtype"] = name == effect.effect
        listed = _authored_behaviors(payload)
        effect._effect = name
        effect.path = path
        for key, value in options.items():
            setattr(
                effect,
                f"_{key}" if key in {"text_build", "build_delay", "build_level"} else key,
                value,
            )
        effect._behaviors = listed
        self._requeue_effect(effect, payload)

    def set_auto_reverse(
        self, effect_or_timing_id: AnimationEffect | int | str, auto_reverse: bool
    ) -> AnimationEffect:
        """Set auto-reverse on one supported effect selected by handle or timing ID."""
        self._ensure_loaded()
        value = _validate_auto_reverse(auto_reverse)
        effect = self._resolve_supported_effect(effect_or_timing_id)
        self._set_effect_auto_reverse(effect, value)
        return effect

    def set_restart(
        self, effect_or_timing_id: AnimationEffect | int | str, restart: str | None
    ) -> AnimationEffect:
        """Set restart by effect handle or timing ID; invalid values never queue."""
        value = coerce_restart(restart)
        self._ensure_loaded()
        effect = self._resolve_supported_effect(effect_or_timing_id)
        self._set_effect_restart(effect, value)
        return effect

    def _resolve_supported_effect(
        self, effect_or_timing_id: AnimationEffect | int | str
    ) -> AnimationEffect:
        """Return the supported effect named by handle or timing ID, or refuse."""
        for effect in self._effects:
            if effect is effect_or_timing_id or (
                effect.timing_id == effect_or_timing_id
                or str(effect.timing_id) == effect_or_timing_id
            ):
                return effect
        for unsupported in self._unsupported_effects:
            if isinstance(effect_or_timing_id, UnsupportedAnimationEffect) or (
                unsupported.timing_id == effect_or_timing_id
                or str(unsupported.timing_id) == effect_or_timing_id
            ):
                raise SlideAnimationRefusalError(
                    "Cannot edit unsupported/foreign animation group "
                    f"(timing ID {unsupported.timing_id})"
                )
        raise SlideAnimationRefusalError(
            f"Animation effect {effect_or_timing_id!r} not found on slide"
        )

    def move(
        self, effect_or_timing_id: AnimationEffect | int | str, new_index: int
    ) -> AnimationEffect:
        """Move one supported effect to ``new_index`` in the main sequence.

        Select the effect by handle or timing ID (an integer is a timing ID,
        matching :meth:`remove` and :meth:`set_auto_reverse`); use
        ``animation.effects[i]`` to select by position. ``new_index`` is a
        position in :attr:`effects` after the move and accepts negative
        indexes like a sequence. Out-of-range or non-integer indexes and
        unsupported/foreign groups raise ``SlideAnimationRefusalError`` without
        queuing any edit.

        Timing IDs, build-list entries, and each effect's own ``start``
        trigger are unchanged, so click groups are recomputed from the new
        order: an ``on_click`` effect opens a click step and the following
        ``with_previous`` / ``after_previous`` effects join it. Foreign groups
        keep their positions; supported effects are permuted around them.

        Requires a saved slide: call ``Presentation.save()`` first. The new
        order is written on the next save.
        """
        self._ensure_loaded()
        effect = self._resolve_supported_effect(effect_or_timing_id)
        count = len(self._effects)
        if (
            isinstance(new_index, bool)
            or not isinstance(new_index, int)
            or not -count <= new_index < count
        ):
            raise SlideAnimationRefusalError(
                f"Animation move index {new_index!r} is out of range for "
                f"{count} supported effect(s)"
            )
        target = new_index % count
        current = self._effects.index(effect)
        if current == target:
            return effect
        self._effects.insert(target, self._effects.pop(current))
        self._order_edited = True
        self._queue()
        return effect

    def remove(self, effect_or_timing_id: Any) -> None:
        """Remove an animation effect from this slide.

        Accepts an AnimationEffect handle, a timing ID, or target shape.
        Refuses removal of foreign / unsupported animation groups.
        """
        self._ensure_loaded()

        if isinstance(effect_or_timing_id, UnsupportedAnimationEffect):
            raise SlideAnimationRefusalError(
                "Cannot remove unsupported/foreign animation group "
                f"(timing ID {effect_or_timing_id.timing_id})"
            )

        # Check if matches an unsupported effect
        for ueff in self._unsupported_effects:
            if ueff.timing_id is not None and (
                ueff.timing_id == effect_or_timing_id
                or str(ueff.timing_id) == str(effect_or_timing_id)
            ):
                raise SlideAnimationRefusalError(
                    "Cannot remove unsupported/foreign animation group "
                    f"(timing ID {ueff.timing_id})"
                )

        matching: list[AnimationEffect] = []

        if isinstance(effect_or_timing_id, AnimationEffect):
            if effect_or_timing_id in self._effects:
                matching.append(effect_or_timing_id)
        elif isinstance(effect_or_timing_id, int):
            # Raw integer must resolve ONLY timing_id, never shape fallback!
            for eff in self._effects:
                if eff.timing_id == effect_or_timing_id:
                    matching.append(eff)
        elif isinstance(effect_or_timing_id, str):
            # Raw string must resolve ONLY timing_id, never shape fallback!
            for eff in self._effects:
                if str(eff.timing_id) == effect_or_timing_id:
                    matching.append(eff)
        else:
            # Shape object fallback (hasattr shape_id)
            target_shape_id = getattr(effect_or_timing_id, "shape_id", None)
            if target_shape_id is not None:
                for eff in self._effects:
                    if str(eff.shape_id) == str(target_shape_id):
                        matching.append(eff)

        if not matching:
            raise SlideAnimationRefusalError(
                f"Animation effect {effect_or_timing_id!r} not found on slide"
            )

        for eff in matching:
            self._effects.remove(eff)
            self._timing_updates.pop(eff.timing_id, None)
            self._build_updates.pop(eff.timing_id, None)
            self._effect_updates.pop(eff.timing_id, None)
            was_pending = False
            for a in list(self._added_effects):
                if a.get("timing_id") == eff.timing_id:
                    self._added_effects.remove(a)
                    was_pending = True
            if not was_pending:
                self._removed_timing_ids.add(eff.timing_id)
        self._queue()

    def clear(self) -> None:
        """Clear all supported animation effects from this slide.

        Preserves unsupported/foreign animation groups and media timing under tmRoot.
        """
        self._sync_state()
        if self._sequence_moves:
            raise SlideAnimationRefusalError(
                "Cannot clear main effects while triggered sequence moves are pending"
            )
        for eff in self._effects:
            is_pending = any(a.get("timing_id") == eff.timing_id for a in self._added_effects)
            if not is_pending:
                self._removed_timing_ids.add(eff.timing_id)
        self._effects.clear()
        self._added_effects.clear()
        self._timing_updates.clear()
        self._build_updates.clear()
        self._effect_updates.clear()
        self._clear_supported = True
        self._queue()
