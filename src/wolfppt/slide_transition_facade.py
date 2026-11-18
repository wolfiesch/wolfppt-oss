"""Slide transition inspection and authoring facade."""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .slide_transition_edits import TransitionSpec
from .slide_transition_xml import (
    TRANSITION_KINDS,
    TransitionRefusal,
    TransitionSoundAction,
    compatible_transition_options,
    decode_transition_field,
    encode_transition_field,
    normalize_built_in_sound_name,
    normalize_transition_options,
    read_transition_sound_data,
    synthesize_transition_tone,
    transition_field,
    transition_fields,
    validate_wav_bytes,
)
from .slide_transition_xml import (
    normalize_advance_after as _normalize_advance_after,
)
from .slide_transition_xml import (
    normalize_advance_on_click as _normalize_advance_on_click,
)
from .slide_transition_xml import (
    normalize_morph_option as _normalize_morph_option,
)
from .slide_transition_xml import (
    normalize_transition_duration as _normalize_transition_duration,
)
from .slide_transition_xml import (
    normalize_transition_speed as _normalize_transition_speed,
)
from .slide_transition_xml import (
    normalize_transition_type as _normalize_transition_type,
)
from .slide_transition_xml import (
    read_slide_transition_xml as _read_slide_transition_xml,
)


@dataclass
class SlideTransitionSpec(TransitionSpec):
    """Transition edit including the p:sndAc sound action.

    sound: The sound action to write, or None to remove p:sndAc.
    sound_specified: Whether the sound action was explicitly set by the caller.
    """

    sound: TransitionSoundAction | None = None
    sound_specified: bool = False


def _get_slide_xml_root(slide: Any) -> ET.Element | None:
    """Extract XML root Element from a Slide instance or its package."""
    # 1. Try slide.element proxy
    try:
        element_proxy = getattr(slide, "element", None)
        if element_proxy is not None:
            raw = getattr(element_proxy, "_element", None)
            if isinstance(raw, ET.Element):
                return raw
    except (AttributeError, TypeError):
        pass

    # 2. Try loading from presentation package directly
    prs = getattr(slide, "_presentation", None)
    partname = getattr(slide, "partname", None)
    if prs is not None and partname:
        prs_path = getattr(prs, "path", None)
        if prs_path is not None:
            norm_part = str(partname).lstrip("/")
            try:
                with zipfile.ZipFile(prs_path) as package:
                    return ET.fromstring(package.read(norm_part))
            except (
                KeyError,
                FileNotFoundError,
                zipfile.BadZipFile,
                ET.ParseError,
                OSError,
            ):
                pass
    return None


def _read_slide_sound_data(slide: Any, rel_id: str) -> bytes | None:
    """Read embedded transition WAV bytes from the slide's source package."""
    prs = getattr(slide, "_presentation", None)
    partname = getattr(slide, "partname", None)
    prs_path = getattr(prs, "path", None) if prs is not None else None
    if prs_path is None or not partname:
        return None
    try:
        with zipfile.ZipFile(prs_path) as package:
            return read_transition_sound_data(package, str(partname), rel_id)
    except (FileNotFoundError, zipfile.BadZipFile, OSError):
        return None


class TransitionSound:
    """A transition sound action (p:sndAc).

    Build one with :meth:`from_wav` (embedded WAV), :meth:`built_in` (a
    PowerPoint built-in sound name) or :meth:`stop_previous` (p:endSnd), and
    assign it to :attr:`SlideTransition.sound`.
    """

    def __init__(
        self,
        action: TransitionSoundAction,
        data_loader: Callable[[], bytes | None] | None = None,
    ) -> None:
        self._action = action
        self._data_loader = data_loader

    @classmethod
    def from_wav(
        cls, data: bytes | str | Path, *, name: str | None = None, loop: bool = False
    ) -> TransitionSound:
        """Embed a WAV file (bytes or path); ``loop`` repeats until the next sound."""
        if isinstance(data, str | Path):
            path = Path(data)
            payload = validate_wav_bytes(path.read_bytes())
            default_name = path.name
        else:
            payload = validate_wav_bytes(data)
            default_name = "sound.wav"
        sound_name = default_name if name is None else name
        if not isinstance(sound_name, str):
            raise TypeError("transition sound name must be a string")
        return cls(
            TransitionSoundAction(
                mode="start",
                name=sound_name,
                loop=_require_bool(loop, "loop"),
                data=payload,
            )
        )

    @classmethod
    def built_in(
        cls, name: str, *, data: bytes | None = None, loop: bool = False
    ) -> TransitionSound:
        """Use a PowerPoint built-in sound (e.g. ``"applause"``, ``"cash register"``).

        The schema requires embedded audio for every start sound, so ``data``
        (WAV bytes) is embedded; without it a short generated tone is embedded
        and the builtIn flag plus name let PowerPoint resolve its own sound.
        """
        payload = validate_wav_bytes(data) if data is not None else synthesize_transition_tone()
        return cls(
            TransitionSoundAction(
                mode="start",
                name=normalize_built_in_sound_name(name),
                built_in=True,
                loop=_require_bool(loop, "loop"),
                data=payload,
            )
        )

    @classmethod
    def stop_previous(cls) -> TransitionSound:
        """Stop any sound still playing from a previous transition (p:endSnd)."""
        return cls(TransitionSoundAction(mode="stop_previous"))

    @property
    def mode(self) -> str:
        """``start`` (play a sound) or ``stop_previous`` (stop the previous sound)."""
        return self._action.mode

    @property
    def name(self) -> str:
        """Sound name stored on p:snd (empty for stop_previous)."""
        return self._action.name

    @property
    def is_built_in(self) -> bool:
        """True when p:snd marks the sound as a built-in application sound."""
        return self._action.built_in

    @property
    def loop(self) -> bool:
        """True when the sound loops until the next sound starts."""
        return self._action.loop

    @property
    def data(self) -> bytes | None:
        """Embedded WAV bytes, or None for stop_previous or an unreadable part."""
        if self._action.data is not None:
            return self._action.data
        if self._data_loader is not None:
            return self._data_loader()
        return None

    def __repr__(self) -> str:
        return (
            f"TransitionSound(mode={self.mode!r}, name={self.name!r}, "
            f"is_built_in={self.is_built_in!r}, loop={self.loop!r})"
        )


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"transition sound {name} must be a boolean")
    return value


def _value_field(name: str, doc: str) -> property:
    def getter(self: TransitionValue) -> Any:
        return self._transition._value_get(self._kind, name)

    def setter(self: TransitionValue, value: Any) -> None:
        self._transition._value_set(self._kind, name, value)

    return property(getter, setter, doc=doc)


class TransitionValue:
    """Typed view of the current transition effect's options.

    Fields read the stored attribute (or its schema default) and setting a
    field validates the value and queues the edit for the next save.
    """

    family = "empty"

    def __init__(self, transition: SlideTransition, kind: str) -> None:
        self._transition = transition
        self._kind = kind

    @property
    def kind(self) -> str:
        """Canonical transition kind (Open XML element local name)."""
        return self._kind

    @property
    def fields(self) -> tuple[str, ...]:
        """Public option field names of this value family."""
        return tuple(field.name for field in transition_fields(self._kind))

    def to_dict(self) -> dict[str, Any]:
        """Return every option field with its current typed value."""
        return {name: getattr(self, name) for name in self.fields}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(kind={self._kind!r}, {self.to_dict()!r})"


class EmptyTransitionValue(TransitionValue):
    """Effects without options (circle, diamond, dissolve, honeycomb, flash, ...)."""

    family = "empty"


class CornerDirectionTransitionValue(TransitionValue):
    """Corner-direction effects (strips): direction lu, ru, ld or rd."""

    family = "corner"
    direction = _value_field("direction", "Corner direction: lu, ru, ld or rd.")


class EightDirectionTransitionValue(TransitionValue):
    """Eight-direction effects (cover, pull): side or corner direction."""

    family = "eight_direction"
    direction = _value_field("direction", "Direction: l, u, r, d, lu, ru, ld or rd.")


class SideDirectionTransitionValue(TransitionValue):
    """Side-direction effects (push, wipe, vortex, pan)."""

    family = "side"
    direction = _value_field("direction", "Side direction: l, u, r or d.")


class LeftRightDirectionTransitionValue(TransitionValue):
    """Left/right effects (switch, flip, ferris, gallery, conveyor)."""

    family = "left_right"
    direction = _value_field("direction", "Direction l or r; None when unset.")


class InOutTransitionValue(TransitionValue):
    """In/out effects (zoom, warp)."""

    family = "in_out"
    direction = _value_field("direction", "Direction: in or out.")


class OrientationTransitionValue(TransitionValue):
    """Orientation effects (blinds, checker, comb, randomBar, doors, window)."""

    family = "orientation"
    direction = _value_field("direction", "Orientation: horz or vert.")


class OptionalBlackTransitionValue(TransitionValue):
    """Effects that can pass through black (fade, cut)."""

    family = "optional_black"
    through_black = _value_field("through_black", "True to transition through black.")


class SplitTransitionValue(TransitionValue):
    """Split effect: orientation and in/out direction."""

    family = "split"
    orientation = _value_field("orientation", "Orientation: horz or vert.")
    direction = _value_field("direction", "Direction: in or out.")


class WheelTransitionValue(TransitionValue):
    """Wheel effects (wheel, wheelReverse): spoke count."""

    family = "wheel"
    spokes = _value_field("spokes", "Number of spokes (positive integer).")


class RevealTransitionValue(TransitionValue):
    """Reveal effect: through-black option and left/right direction."""

    family = "reveal"
    through_black = _value_field("through_black", "True to reveal through black.")
    direction = _value_field("direction", "Direction: l or r.")


class RippleTransitionValue(TransitionValue):
    """Ripple effect: center or corner origin."""

    family = "ripple"
    direction = _value_field("direction", "Origin: center, lu, ru, ld or rd.")


class ShredTransitionValue(TransitionValue):
    """Shred effect: pattern and in/out direction."""

    family = "shred"
    pattern = _value_field("pattern", "Pattern: strip or rectangle.")
    direction = _value_field("direction", "Direction: in or out.")


class GlitterTransitionValue(TransitionValue):
    """Glitter effect: side direction and pattern."""

    family = "glitter"
    direction = _value_field("direction", "Side direction: l, u, r or d.")
    pattern = _value_field("pattern", "Pattern: diamond or hexagon.")


class FlyThroughTransitionValue(TransitionValue):
    """Fly-through effect: in/out direction and bounce."""

    family = "fly_through"
    direction = _value_field("direction", "Direction: in or out.")
    has_bounce = _value_field("has_bounce", "True to bounce at the end.")


class PrismTransitionValue(TransitionValue):
    """Prism effect: side direction, content and inverted options."""

    family = "prism"
    direction = _value_field("direction", "Side direction: l, u, r or d.")
    is_content = _value_field("is_content", "True to rotate only the content.")
    is_inverted = _value_field("is_inverted", "True to invert the prism.")


class MorphTransitionValue(TransitionValue):
    """Morph effect: matching mode."""

    family = "morph"
    morph_type = _value_field("morph_type", "Matching mode: by_object, by_word or by_char.")


class PresetTransitionValue(TransitionValue):
    """PowerPoint 2013 preset effects (fallOver, drape, curtains, ...)."""

    family = "preset"
    preset = _value_field("preset", "Preset name, e.g. fallOver, curtains, origami.")
    invert_x = _value_field("invert_x", "True to mirror the preset horizontally.")
    invert_y = _value_field("invert_y", "True to mirror the preset vertically.")


TRANSITION_VALUE_TYPES: dict[str, type[TransitionValue]] = {
    cls.family: cls
    for cls in (
        EmptyTransitionValue,
        CornerDirectionTransitionValue,
        EightDirectionTransitionValue,
        SideDirectionTransitionValue,
        LeftRightDirectionTransitionValue,
        InOutTransitionValue,
        OrientationTransitionValue,
        OptionalBlackTransitionValue,
        SplitTransitionValue,
        WheelTransitionValue,
        RevealTransitionValue,
        RippleTransitionValue,
        ShredTransitionValue,
        GlitterTransitionValue,
        FlyThroughTransitionValue,
        PrismTransitionValue,
        MorphTransitionValue,
        PresetTransitionValue,
    )
}


class SlideTransition:
    """Slide transition facade for inspecting, authoring, and removing transitions.

    Supports every ECMA-376 transition effect plus the [MS-PPTX] PowerPoint
    2010 (p14), 2013 preset (p15) and Morph (p159) effects; :attr:`value`
    exposes the effect's typed options. Also supports speed, advance_on_click,
    advance_after (seconds, mapped to advTm milliseconds), p14:dur and the
    p:sndAc transition sound.

    Preserves unsupported transitions untouched until an explicit replacement or removal.
    Never reinterprets or loses p:timing.
    """

    def __init__(self, slide: Any) -> None:
        self._slide = slide
        self._loaded: bool = False
        self._has_transition: bool = False
        self._type: str | None = None
        self._speed: str | None = None
        self._advance_on_click: bool | None = True
        self._advance_after: float | None = None
        self._duration: int | None = None
        self._is_supported: bool = True
        self._effect_options: dict[str, Any] = {}
        self._sound: TransitionSoundAction | None = None
        self._remove: bool = False
        self._effect_specified: bool = False
        self._speed_specified: bool = False
        self._advance_on_click_specified: bool = False
        self._advance_after_specified: bool = False
        self._duration_specified: bool = False
        self._sound_specified: bool = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        root = _get_slide_xml_root(self._slide)
        if root is not None:
            info = _read_slide_transition_xml(root)
            self._has_transition = info["has_transition"]
            self._type = info["type"]
            self._speed = info["speed"]
            self._advance_on_click = info["advance_on_click"]
            self._advance_after = info["advance_after"]
            self._duration = info.get("duration")
            self._is_supported = info["is_supported"]
            self._effect_options = dict(info["effect_options"])
            self._sound = info.get("sound")
        self._loaded = True

    def _spec(self) -> SlideTransitionSpec:
        return SlideTransitionSpec(
            effect=self._type,
            speed=self._speed,
            advance_on_click=self._advance_on_click,
            advance_after=self._advance_after,
            duration=self._duration,
            effect_options=dict(self._effect_options),
            remove=self._remove,
            effect_specified=self._effect_specified,
            speed_specified=self._speed_specified,
            advance_on_click_specified=self._advance_on_click_specified,
            advance_after_specified=self._advance_after_specified,
            duration_specified=self._duration_specified,
            sound=self._sound,
            sound_specified=self._sound_specified,
        )

    def _queue(self) -> None:
        prs = getattr(self._slide, "_presentation", None)
        if prs is None:
            return
        spec = self._spec()
        partname = getattr(self._slide, "partname", None)
        slide_idx = getattr(self._slide, "_index", None)
        if partname:
            identifier: int | str = str(partname)
        elif slide_idx is not None:
            identifier = int(slide_idx)
        else:
            return

        queue_fn = getattr(prs, "_queue_slide_transition", None)
        if callable(queue_fn):
            queue_fn(identifier, spec)
        else:
            edits = getattr(prs, "_slide_transition_edits", None)
            if edits is None:
                edits = {}
                prs._slide_transition_edits = edits
            edits[identifier] = spec

    def _mark_present(self) -> None:
        self._remove = False
        self._has_transition = True

    @property
    def has_transition(self) -> bool:
        """True if this slide has an active transition element."""
        self._ensure_loaded()
        return self._has_transition and not self._remove

    @property
    def is_supported(self) -> bool:
        """True if the transition effect is in the standard supported family."""
        self._ensure_loaded()
        return self._is_supported

    @property
    def type(self) -> str | None:
        """Transition effect type (e.g. 'fade', 'push', 'vortex', 'morph') or None."""
        self._ensure_loaded()
        if self._remove:
            return None
        return self._type

    @type.setter
    def type(self, value: Any) -> None:
        self._ensure_loaded()
        canonical = _normalize_transition_type(value)
        if canonical is None:
            self.remove()
            return
        if canonical != self._type or not self._is_supported:
            self._effect_options = compatible_transition_options(canonical, self._effect_options)
        self._type = canonical
        self._is_supported = True
        self._effect_specified = True
        self._mark_present()
        self._queue()

    @property
    def value(self) -> TransitionValue | None:
        """Typed options of the current effect, or None without a supported effect.

        The returned object's fields (direction, pattern, spokes, ...) read the
        stored values and writes queue an edit. Changing :attr:`type` makes a
        previously returned value stale.
        """
        self._ensure_loaded()
        if self._remove or self._type is None or not self._is_supported:
            return None
        family = TRANSITION_KINDS[self._type].family
        return TRANSITION_VALUE_TYPES[family](self, self._type)

    def _require_current_kind(self, kind: str) -> None:
        self._ensure_loaded()
        if self._remove or self._type != kind or not self._is_supported:
            raise TransitionRefusal(
                f"transition value for {kind!r} is stale; the transition is now {self.type!r}"
            )

    def _value_get(self, kind: str, name: str) -> Any:
        self._require_current_kind(kind)
        field = transition_field(kind, name)
        return decode_transition_field(field, self._effect_options.get(field.attribute))

    def _value_set(self, kind: str, name: str, value: Any) -> None:
        self._require_current_kind(kind)
        field = transition_field(kind, name)
        options = dict(self._effect_options)
        if value is None:
            if field.kind == "morph":
                raise TransitionRefusal("morph_type cannot be cleared")
            options.pop(field.attribute, None)
        else:
            options[field.attribute] = encode_transition_field(kind, field, value)
        self._effect_options = options
        self._effect_specified = True
        self._mark_present()
        self._queue()

    @property
    def speed(self) -> str | None:
        """Transition speed ('slow', 'med', 'fast') or None."""
        self._ensure_loaded()
        if self._remove:
            return None
        return self._speed

    @speed.setter
    def speed(self, value: Any) -> None:
        self._ensure_loaded()
        norm_speed = _normalize_transition_speed(value)
        self._speed = norm_speed
        self._speed_specified = True
        self._mark_present()
        self._queue()

    @property
    def advance_on_click(self) -> bool | None:
        """Whether the slide advances on mouse click (default True)."""
        self._ensure_loaded()
        if self._remove:
            return True
        return self._advance_on_click

    @advance_on_click.setter
    def advance_on_click(self, value: Any) -> None:
        self._ensure_loaded()
        norm_adv_click = _normalize_advance_on_click(value)
        self._advance_on_click = norm_adv_click
        self._advance_on_click_specified = True
        self._mark_present()
        self._queue()

    @property
    def advance_after(self) -> float | None:
        """Automatic advance time in seconds (mapped to advTm in ms) or None."""
        self._ensure_loaded()
        if self._remove:
            return None
        return self._advance_after

    @advance_after.setter
    def advance_after(self, value: Any) -> None:
        self._ensure_loaded()
        norm_adv_after = _normalize_advance_after(value)
        self._advance_after = norm_adv_after
        self._advance_after_specified = True
        self._mark_present()
        self._queue()

    @property
    def duration(self) -> int | None:
        """Transition duration in milliseconds (mapped to p14:dur) or None."""
        self._ensure_loaded()
        if self._remove:
            return None
        return self._duration

    @duration.setter
    def duration(self, value: Any) -> None:
        self._ensure_loaded()
        norm_dur = _normalize_transition_duration(value)
        self._duration = norm_dur
        self._duration_specified = True
        self._mark_present()
        self._queue()

    def clear_duration(self) -> None:
        """Clear explicit transition duration, removing p14:dur attribute."""
        self._ensure_loaded()
        self._duration = None
        self._duration_specified = True
        self._queue()

    @property
    def effect_options(self) -> dict[str, Any]:
        """Dictionary of attributes configured on the transition effect element."""
        self._ensure_loaded()
        if self._remove:
            return {}
        return dict(self._effect_options)

    @property
    def morph_option(self) -> str | None:
        """Morph matching mode: by_object, by_word, or by_char."""
        self._ensure_loaded()
        if self._remove or self._type != "morph":
            return None
        value = self._effect_options.get("option", "byObject")
        return {
            "byObject": "by_object",
            "byWord": "by_word",
            "byChar": "by_char",
        }.get(value)

    @morph_option.setter
    def morph_option(self, value: Any) -> None:
        self._ensure_loaded()
        if self._type != "morph":
            raise TransitionRefusal("morph_option can only be set when type is 'morph'")
        self._effect_options = {"option": _normalize_morph_option(value)}
        self._effect_specified = True
        self._mark_present()
        self._queue()

    @property
    def sound(self) -> TransitionSound | None:
        """The transition sound action (p:sndAc), or None."""
        self._ensure_loaded()
        if self._remove or self._sound is None:
            return None
        action = self._sound
        loader = None
        if action.data is None and action.rel_id is not None:
            rel_id = action.rel_id

            def loader() -> bytes | None:
                return _read_slide_sound_data(self._slide, rel_id)

        return TransitionSound(action, loader)

    @sound.setter
    def sound(self, value: TransitionSound | None) -> None:
        self._ensure_loaded()
        if value is not None and not isinstance(value, TransitionSound):
            raise TypeError("transition sound must be a TransitionSound or None")
        self._set_sound_action(None if value is None else value._action)

    def _set_sound_action(self, action: TransitionSoundAction | None) -> None:
        self._sound = action
        self._sound_specified = True
        if action is not None:
            self._mark_present()
        self._queue()

    def _start_sound(self, field: str) -> TransitionSoundAction:
        self._ensure_loaded()
        if self._remove or self._sound is None or self._sound.mode != "start":
            raise TransitionRefusal(f"{field} needs a start sound; assign transition.sound first")
        return self._sound

    @property
    def sound_mode(self) -> str | None:
        """``start``, ``stop_previous`` or None when the transition has no sound action."""
        self._ensure_loaded()
        if self._remove or self._sound is None:
            return None
        return self._sound.mode

    @sound_mode.setter
    def sound_mode(self, value: str | None) -> None:
        self._ensure_loaded()
        if value is None:
            self._set_sound_action(None)
        elif value == "stop_previous":
            self._set_sound_action(TransitionSoundAction(mode="stop_previous"))
        elif value == "start":
            self._start_sound("sound_mode 'start'")
        else:
            raise TransitionRefusal("sound_mode must be 'start', 'stop_previous' or None")

    @property
    def sound_loop(self) -> bool:
        """True when the start sound loops until the next sound (p:stSnd loop)."""
        self._ensure_loaded()
        if self._remove or self._sound is None:
            return False
        return self._sound.loop

    @sound_loop.setter
    def sound_loop(self, value: bool) -> None:
        action = self._start_sound("sound_loop")
        self._set_sound_action(replace(action, loop=_require_bool(value, "loop")))

    @property
    def sound_name(self) -> str | None:
        """Name stored on the start sound's p:snd, or None without a start sound."""
        self._ensure_loaded()
        if self._remove or self._sound is None or self._sound.mode != "start":
            return None
        return self._sound.name

    @sound_name.setter
    def sound_name(self, value: str) -> None:
        action = self._start_sound("sound_name")
        if not isinstance(value, str):
            raise TypeError("transition sound name must be a string")
        self._set_sound_action(replace(action, name=value))

    @property
    def sound_is_built_in(self) -> bool:
        """True when the start sound is flagged as a built-in application sound."""
        self._ensure_loaded()
        if self._remove or self._sound is None:
            return False
        return self._sound.built_in

    @sound_is_built_in.setter
    def sound_is_built_in(self, value: bool) -> None:
        action = self._start_sound("sound_is_built_in")
        self._set_sound_action(replace(action, built_in=_require_bool(value, "built_in")))

    def remove(self) -> None:
        """Remove transition from the slide entirely."""
        self._ensure_loaded()
        self._remove = True
        self._has_transition = False
        self._type = None
        self._speed = None
        self._advance_after = None
        self._duration = None
        self._duration_specified = True
        self._advance_on_click = True
        self._effect_options = {}
        self._effect_specified = True
        self._sound = None
        self._sound_specified = True
        self._queue()

    def set(
        self,
        effect: str | None = None,
        speed: str | None = None,
        advance_on_click: bool | None = None,
        advance_after: float | None = None,
        duration: int | None = None,
        **options: Any,
    ) -> None:
        """Set multiple transition properties simultaneously.

        ``options`` are effect options by public field name (``direction``,
        ``pattern``, ``spokes``, ...) or Open XML attribute (``dir``, ``orient``,
        ``thruBlk``, ...); they are validated against the effect's value family.
        Supplying options requires an explicit ``effect``. Unsupported values
        raise ``TransitionRefusal`` before any queued state changes.
        """
        self._ensure_loaded()
        norm_duration: int | None = None
        if duration is not None:
            norm_duration = _normalize_transition_duration(duration)
        canonical = _normalize_transition_type(effect) if effect is not None else None
        norm_options: dict[str, str] | None = None
        if options and canonical is None:
            raise TransitionRefusal("transition options require an explicit effect")
        if canonical is not None:
            if canonical == "morph" and set(options) - {"option", "morph_type"}:
                raise TransitionRefusal("Morph accepts only the option setting")
            norm_options = normalize_transition_options(canonical, options)
        norm_speed = _normalize_transition_speed(speed) if speed is not None else None
        norm_click = (
            _normalize_advance_on_click(advance_on_click) if advance_on_click is not None else None
        )
        norm_after = _normalize_advance_after(advance_after) if advance_after is not None else None

        if canonical is not None and norm_options is not None:
            self._type = canonical
            self._effect_options = norm_options
            self._effect_specified = True
            self._is_supported = True

        if norm_speed is not None:
            self._speed = norm_speed
            self._speed_specified = True

        if norm_click is not None:
            self._advance_on_click = norm_click
            self._advance_on_click_specified = True

        if norm_after is not None:
            self._advance_after = norm_after
            self._advance_after_specified = True

        if duration is not None:
            self._duration = norm_duration
            self._duration_specified = True
        self._mark_present()
        self._queue()

    def set_morph(
        self,
        mode: str = "by_object",
        speed: str | None = None,
        advance_on_click: bool | None = None,
        advance_after: float | None = None,
        duration: int | None = None,
    ) -> None:
        """Configure a standards-compliant Morph transition and matching mode."""
        self.set(
            effect="morph",
            speed=speed,
            advance_on_click=advance_on_click,
            advance_after=advance_after,
            duration=duration,
            option=mode,
        )

    def set_fade(
        self,
        thru_black: bool = False,
        speed: str | None = None,
        advance_on_click: bool | None = None,
        advance_after: float | None = None,
        duration: int | None = None,
    ) -> None:
        """Configure a fade transition, optionally through black."""
        opts = {"thruBlk": "1"} if thru_black else {}
        self.set(
            effect="fade",
            speed=speed,
            advance_on_click=advance_on_click,
            advance_after=advance_after,
            duration=duration,
            **opts,
        )

    def set_push(
        self,
        direction: str = "l",
        speed: str | None = None,
        advance_on_click: bool | None = None,
        advance_after: float | None = None,
        duration: int | None = None,
    ) -> None:
        """Configure a push transition ('d', 'l', 'r', 'u')."""
        self.set(
            effect="push",
            speed=speed,
            advance_on_click=advance_on_click,
            advance_after=advance_after,
            duration=duration,
            dir=direction,
        )

    def set_wipe(
        self,
        direction: str = "r",
        speed: str | None = None,
        advance_on_click: bool | None = None,
        advance_after: float | None = None,
        duration: int | None = None,
    ) -> None:
        """Configure a wipe transition ('d', 'l', 'r', 'u')."""
        self.set(
            effect="wipe",
            speed=speed,
            advance_on_click=advance_on_click,
            advance_after=advance_after,
            duration=duration,
            dir=direction,
        )

    def set_cut(
        self,
        thru_black: bool = False,
        speed: str | None = None,
        advance_on_click: bool | None = None,
        advance_after: float | None = None,
        duration: int | None = None,
    ) -> None:
        """Configure a cut transition, optionally through black."""
        opts = {"thruBlk": "1"} if thru_black else {}
        self.set(
            effect="cut",
            speed=speed,
            advance_on_click=advance_on_click,
            advance_after=advance_after,
            duration=duration,
            **opts,
        )
