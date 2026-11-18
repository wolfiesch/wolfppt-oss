"""Effect behaviours, editable property keyframes, and motion paths.

An effect's ``p:childTnLst`` holds its behaviours. These kinds are modelled
for read, edit, and authoring:

* :class:`ColorBehavior` (``p:animClr``): colour space, direction, offset
  (``p:by``), and from/to colours.
* :class:`MotionBehavior` (``p:animMotion``): a :class:`MotionPath`, origin,
  path edit mode, rotation, and from/to/by points.
* :class:`RotationBehavior` (``p:animRot``) and :class:`ScaleBehavior`
  (``p:animScale``).
* :class:`SetBehavior` (``p:set``): a property list and the value it sets.
* :class:`CommandBehavior` (``p:cmd``): command type and command string.
* :class:`FilterBehavior` (``p:animEffect``): transition and filter.
* :class:`PropertyBehavior` (``p:anim``): numeric keyframes, linear/discrete
  interpolation, safe arithmetic formulas, and from/to/by values.

Every modelled behaviour also carries its ``p:cBhvr`` composition
(``accumulate``, ``additive``), animated property list, and local ``p:cTn``
timing. The string enums :class:`AccumulateMode`, :class:`AdditiveMode`,
:class:`FillMode`, and :class:`RestartMode` name the same choices as the
accepted literal strings. Local ``restart`` is a restart policy, not a repeat
count. ``acceleration`` and ``deceleration`` are optional fractions in 0..1
whose sum cannot exceed 1, rounded to XML's 1/100000 precision; None omits
the corresponding timing attribute. Anything else (media or markup outside
this model), including malformed local easing, is listed as a read-only
:class:`RawBehavior`. Fly presets retain their raw property behaviours and
the compatible :class:`PropertyAnimation` inspection snapshot.

Units: angles are degrees, scale sizes and colour offsets are percentages,
and motion coordinates and points are fractions of the slide (1.0 = 100%).
"""

from __future__ import annotations

import ast
import copy
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar
from xml.etree import ElementTree as ET

from .render_refusals import RenderRefusal
from .slide_animation_emphasis import (
    _SCHEME_COLORS,
    A_NS,
    P_NS,
    AnimationKeyframe,
    _append_behavior,
    _append_color,
    _color_value,
    _xml_local_name,
)


class SlideAnimationRefusalError(ValueError):
    """Raised when an animation edit cannot be safely performed."""


class AnimationFrameRefusal(RenderRefusal, SlideAnimationRefusalError):
    """A named playback refusal catchable by either rendering or animation APIs.

    It lives beside the editor's animation refusal so Community modules that
    validate playback inputs can raise it without importing the renderer.
    """


class RestartMode(StrEnum):
    """Local time-node restart policy, independent of repeat controls."""

    ALWAYS = "always"
    WHEN_NOT_ACTIVE = "whenNotActive"
    NEVER = "never"


class AccumulateMode(StrEnum):
    """Whether repeated behaviour values accumulate."""

    NONE = "none"
    ALWAYS = "always"


class AdditiveMode(StrEnum):
    """How a behaviour composes with its underlying property value."""

    BASE = "base"
    SUM = "sum"
    REPL = "repl"
    MULT = "mult"
    NONE = "none"


class FillMode(StrEnum):
    """Time-node fill choices; None separately means an omitted attribute."""

    REMOVE = "remove"
    FREEZE = "freeze"
    HOLD = "hold"
    TRANSITION = "transition"
    AUTO = "auto"
    DEFAULT = "default"


ACCUMULATE_MODES = ("none", "always")
ADDITIVE_MODES = ("base", "sum", "repl", "mult", "none")
BEHAVIOR_FILL_MODES = ("remove", "freeze", "hold", "transition", "auto", "default")
COLOR_SPACES = ("rgb", "hsl")
COLOR_DIRECTIONS = ("cw", "ccw")
MOTION_ORIGINS = ("parent", "layout")
MOTION_EDIT_MODES = ("relative", "fixed")
COMMAND_TYPES = ("event", "call", "verb")
# ST_TLCommandType spells the event type ``evt``.
_COMMAND_TYPE_XML = {"event": "evt", "call": "call", "verb": "verb"}
_COMMAND_TYPE_BY_XML = {value: key for key, value in _COMMAND_TYPE_XML.items()}
FILTER_TRANSITIONS = ("in", "out", "none")
PROPERTY_CALC_MODES = ("lin", "discr", "fmla")
RESTART_MODES = ("always", "whenNotActive", "never")
PROPERTY_VALUE_TYPES = ("num", "clr", "str")
MOTION_COMMANDS = ("move", "line", "curve", "close")
# ``ptsTypes`` codes: upper case is followed by a line, lower case by a curve.
POINTS_TYPES = {
    "auto": "A",
    "corner": "F",
    "straight": "T",
    "smooth": "S",
    "curve_auto": "a",
    "curve_corner": "f",
    "curve_straight": "t",
    "curve_smooth": "s",
}
_POINTS_TYPE_BY_CODE = {code: name for name, code in POINTS_TYPES.items()}
_COMMAND_LETTERS = {"move": "M", "line": "L", "curve": "C", "close": "Z"}
_COMMAND_BY_LETTER = {letter: kind for kind, letter in _COMMAND_LETTERS.items()}
_COMMAND_POINT_COUNTS = {"move": 1, "line": 1, "curve": 3, "close": 0}
_PATH_TOKEN = re.compile(r"\s*(?:,\s*)?(?:([A-Za-z])|([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?))")
_ANGLE_UNITS = 60000.0  # ST_Angle units per degree
_PERCENT_UNITS = 1000.0  # ST_Percentage units per percent
_POINT_UNITS = 100000.0  # CT_TLPoint units per slide fraction


def _refuse(message: str) -> SlideAnimationRefusalError:
    return SlideAnimationRefusalError(message)


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _refuse(f"Invalid {name}: {value!r} (must be a finite number)")
    return float(value)


def _optional_number(value: Any, name: str) -> float | None:
    return None if value is None else _number(value, name)


def _choice(value: Any, name: str, choices: Sequence[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise _refuse(f"Invalid {name}: {value!r} (use one of {', '.join(choices)})")
    return str.__str__(value)


def _optional_choice(value: Any, name: str, choices: Sequence[str]) -> str | None:
    return None if value is None else _choice(value, name, choices)


def coerce_fill(value: Any) -> str | None:
    """Validate an optional fill literal or :class:`FillMode` without aliases."""
    return _optional_choice(value, "fill", BEHAVIOR_FILL_MODES)


def coerce_restart(value: Any) -> str | None:
    """Validate an optional ST_TLTimeNodeRestartType value without aliases."""
    return _optional_choice(value, "restart", RESTART_MODES)


def coerce_acceleration_deceleration(
    acceleration: Any, deceleration: Any
) -> tuple[float | None, float | None]:
    """Validate fractional effect or behaviour easing before changing data or XML."""
    values: list[float | None] = []
    for name, value in (("acceleration", acceleration), ("deceleration", deceleration)):
        try:
            value = _optional_number(value, name)
        except OverflowError as exc:
            raise _refuse(f"Invalid {name}: must be within 0..1") from exc
        if value is not None and not 0 <= value <= 1:
            raise _refuse(f"Invalid {name}: {value!r} (must be within 0..1)")
        values.append(value)
    if (values[0] or 0) + (values[1] or 0) > 1:
        raise _refuse("Effect acceleration + deceleration must not exceed 1")
    ticks = [None if value is None else round(value * 100000) for value in values]
    if (ticks[0] or 0) + (ticks[1] or 0) > 100000:
        raise _refuse("Effect acceleration + deceleration exceeds 1 at XML precision")
    return (
        None if ticks[0] is None else ticks[0] / 100000,
        None if ticks[1] is None else ticks[1] / 100000,
    )


def _numbers(value: Any, name: str, count: int) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != count:
        raise _refuse(f"Invalid {name}: {value!r} (must be {count} numbers)")
    return tuple(_number(item, name) for item in value)


def _optional_pair(value: Any, name: str) -> tuple[float, float] | None:
    if value is None:
        return None
    x, y = _numbers(value, name, 2)
    return (x, y)


def _optional_color(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        clean = value.strip().removeprefix("#")
        if clean in _SCHEME_COLORS:
            return clean
        if len(clean) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in clean):
            return clean.upper()
    raise _refuse(
        f"Invalid {name}: {value!r} (use RRGGBB hex or a scheme colour name such as 'accent2')"
    )


def _units(value: float, scale: float) -> str:
    return str(round(value * scale))


def _from_units(raw: str | None, scale: float) -> float | None:
    if raw is None:
        return None
    return int(raw) / scale


def _format_coordinate(value: float) -> str:
    rendered = f"{value:.12f}".rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _seconds(raw: str | None) -> float | None:
    if raw is None:
        return None
    if not raw.isdigit():
        raise ValueError(raw)
    return int(raw) / 1000.0


def _milliseconds(seconds: float) -> str:
    return str(round(seconds * 1000.0))


@dataclass(frozen=True)
class MotionCommand:
    """One motion path command: move, line, curve, or close.

    ``points`` holds one (x, y) pair for move and line, three for a curve
    (two control points, then the end point), and none for close.
    ``points_type`` names the editing type of the vertex the command ends
    on (see :data:`POINTS_TYPES`); ``relative`` writes the lower-case
    command, whose points are offsets from the current point.
    """

    kind: str
    points: tuple[tuple[float, float], ...] = ()
    points_type: str | None = None
    relative: bool = False

    def __post_init__(self) -> None:
        kind = _choice(self.kind, "motion command", MOTION_COMMANDS)
        if isinstance(self.points, (str, bytes)) or not isinstance(self.points, Sequence):
            raise _refuse("Motion command points must be a sequence of (x, y) pairs")
        points = tuple(_numbers(point, "motion path point", 2) for point in self.points)
        if len(points) != _COMMAND_POINT_COUNTS[kind]:
            raise _refuse(
                f"A {kind} command takes {_COMMAND_POINT_COUNTS[kind]} point(s), not {len(points)}"
            )
        points_type = _optional_choice(self.points_type, "points_type", tuple(POINTS_TYPES))
        if kind == "close" and points_type is not None:
            raise _refuse("A close command has no vertex and takes no points_type")
        if not isinstance(self.relative, bool):
            raise _refuse("Motion command relative must be a boolean")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "points_type", points_type)


@dataclass(frozen=True)
class MotionPath:
    """An immutable motion path built from move, line, curve, and close commands.

    Build one by chaining: ``MotionPath().move_to(0, 0).line_to(0.25, 0)
    .curve_to((0.3, 0.1), (0.4, 0.2), (0.5, 0.2)).close()``. Each call
    returns a new path. The path must start with a move command.
    """

    commands: tuple[MotionCommand, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.commands, (str, bytes)) or not isinstance(self.commands, Sequence):
            raise _refuse("Motion path commands must be a sequence of MotionCommand")
        commands = tuple(self.commands)
        if not all(isinstance(command, MotionCommand) for command in commands):
            raise _refuse("Motion path commands must be MotionCommand instances")
        if commands and commands[0].kind != "move":
            raise _refuse("A motion path starts with a move command")
        typed = [c.points_type for c in commands if c.kind != "close"]
        if None in typed and any(t is not None for t in typed[typed.index(None) :]):
            raise _refuse(
                "Set points_type on every vertex up to the last typed one "
                "(PowerPoint maps ptsTypes to vertices in order)"
            )
        object.__setattr__(self, "commands", commands)

    def _then(self, command: MotionCommand) -> MotionPath:
        return MotionPath((*self.commands, command))

    def move_to(
        self,
        x: float,
        y: float,
        *,
        points_type: str | None = None,
        relative: bool = False,
    ) -> MotionPath:
        """Start a sub-path at (x, y)."""
        return self._then(MotionCommand("move", ((x, y),), points_type, relative))

    def line_to(
        self,
        x: float,
        y: float,
        *,
        points_type: str | None = None,
        relative: bool = False,
    ) -> MotionPath:
        """Draw a straight segment to (x, y)."""
        return self._then(MotionCommand("line", ((x, y),), points_type, relative))

    def curve_to(
        self,
        control1: Sequence[float],
        control2: Sequence[float],
        end: Sequence[float],
        *,
        points_type: str | None = None,
        relative: bool = False,
    ) -> MotionPath:
        """Draw a cubic Bezier segment through two control points to ``end``."""
        return self._then(
            MotionCommand(
                "curve",
                (tuple(control1), tuple(control2), tuple(end)),  # type: ignore[arg-type]
                points_type,
                relative,
            )
        )

    def close(self, *, relative: bool = False) -> MotionPath:
        """Close the current sub-path back to its start point."""
        return self._then(MotionCommand("close", (), None, relative))

    def to_path(self) -> str:
        """The ``path`` attribute: commands, then ``E`` unless the path closes."""
        tokens: list[str] = []
        for command in self.commands:
            letter = _COMMAND_LETTERS[command.kind]
            tokens.append(letter.lower() if command.relative else letter)
            for x, y in command.points:
                tokens.extend((_format_coordinate(x), _format_coordinate(y)))
        if not self.commands or self.commands[-1].kind != "close":
            tokens.append("E")
        return " ".join(tokens)

    def points_types(self) -> str | None:
        """The ``ptsTypes`` attribute, or None when no vertex is typed."""
        codes = [
            POINTS_TYPES[c.points_type]
            for c in self.commands
            if c.kind != "close" and c.points_type is not None
        ]
        return "".join(codes) or None

    def bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Bounding box of every absolute point: ((min x, min y), (max x, max y))."""
        xs: list[float] = []
        ys: list[float] = []
        current = start = (0.0, 0.0)
        for command in self.commands:
            if command.kind == "close":
                current = start
                continue
            for x, y in command.points:
                point = (current[0] + x, current[1] + y) if command.relative else (x, y)
                xs.append(point[0])
                ys.append(point[1])
            # Relative curve points are all offsets from the segment's start.
            end = command.points[-1]
            current = (current[0] + end[0], current[1] + end[1]) if command.relative else end
            if command.kind == "move":
                start = current
        if not xs:
            raise _refuse("An empty motion path has no bounds")
        return (min(xs), min(ys)), (max(xs), max(ys))

    @classmethod
    def parse(cls, path: str, points_types: str | None = None) -> MotionPath:
        """Read a ``path`` attribute (and ``ptsTypes``) into commands.

        A trailing ``E`` ends the path and is not a command.
        """
        tokens: list[str] = []
        position = 0
        text = path.rstrip()
        while position < len(text):
            match = _PATH_TOKEN.match(text, position)
            if match is None or match.end() == position:
                raise _refuse(f"Invalid motion path: {path!r}")
            tokens.append(match.group(1) or match.group(2))
            position = match.end()
        if tokens and tokens[-1] in {"E", "e"}:
            tokens.pop()
        vertex_types = list(points_types or "")
        if any(code not in _POINTS_TYPE_BY_CODE for code in vertex_types):
            raise _refuse(f"Invalid ptsTypes: {points_types!r}")
        commands: list[MotionCommand] = []
        index = 0
        while index < len(tokens):
            letter = tokens[index]
            kind = _COMMAND_BY_LETTER.get(letter.upper())
            if kind is None:
                raise _refuse(f"Invalid motion path command {letter!r} in {path!r}")
            count = _COMMAND_POINT_COUNTS[kind] * 2
            values = tokens[index + 1 : index + 1 + count]
            if len(values) != count or any(v[0].isalpha() for v in values):
                raise _refuse(f"Motion path command {letter!r} needs {count} numbers")
            numbers = [float(value) for value in values]
            points = tuple((numbers[i], numbers[i + 1]) for i in range(0, len(numbers), 2))
            points_type = None
            if kind != "close" and vertex_types:
                points_type = _POINTS_TYPE_BY_CODE[vertex_types.pop(0)]
            commands.append(MotionCommand(kind, points, points_type, letter.islower()))
            index += 1 + count
        if vertex_types:
            raise _refuse("ptsTypes names more vertices than the path has")
        return cls(tuple(commands))


@dataclass(frozen=True)
class RawBehavior:
    """Read-only behaviour outside the editable model, kept as markup."""

    tag: str
    markup: str


@dataclass(frozen=True, kw_only=True)
class AnimationBehavior:
    """Common ``p:cBhvr`` data of one effect behaviour.

    ``attributes`` is the animated property list (``p:attrNameLst``).
    ``accumulate`` is ``none`` or ``always``; ``additive`` is ``base``,
    ``sum``, ``repl``, ``mult``, or ``none``. ``duration`` and ``delay`` are
    seconds; a None duration takes the effect's duration when written.
    ``fill`` accepts :class:`FillMode` or ``remove``, ``freeze``, ``hold``,
    ``transition``, ``auto``, or ``default``; it defaults to ``hold``.
    ``restart`` accepts :class:`RestartMode` or ``always``, ``whenNotActive``,
    or ``never`` and does not set repeat counts. ``acceleration`` and
    ``deceleration`` are fractions in 0..1 with a combined maximum of 1,
    normalised to 1/100000 XML precision. None omits each optional attribute.
    Instances are immutable; ``dataclasses.replace`` validates edits.
    """

    attributes: tuple[str, ...] = ()
    accumulate: str | None = None
    additive: str | None = None
    duration: float | None = None
    delay: float | None = None
    fill: str | None = "hold"
    restart: str | None = None
    acceleration: float | None = None
    deceleration: float | None = None

    tag: ClassVar[str] = ""
    _child_tags: ClassVar[tuple[str, ...]] = ()
    _element_attributes: ClassVar[frozenset[str]] = frozenset()

    def __post_init__(self) -> None:
        if isinstance(self.attributes, (str, bytes)) or not isinstance(self.attributes, Sequence):
            raise _refuse("Behaviour attributes must be a sequence of property names")
        attributes = tuple(self.attributes)
        if not all(isinstance(name, str) and name.strip() for name in attributes):
            raise _refuse("Behaviour attribute names must be non-empty strings")
        accumulate = _optional_choice(self.accumulate, "accumulate", ACCUMULATE_MODES)
        additive = _optional_choice(self.additive, "additive", ADDITIVE_MODES)
        fill = coerce_fill(self.fill)
        restart = coerce_restart(self.restart)
        acceleration, deceleration = coerce_acceleration_deceleration(
            self.acceleration, self.deceleration
        )
        timing: dict[str, float | None] = {}
        for name in ("duration", "delay"):
            value = _optional_number(getattr(self, name), name)
            if value is not None and value < 0:
                raise _refuse(f"Behaviour {name} must not be negative")
            timing[name] = value
        object.__setattr__(self, "attributes", attributes)
        object.__setattr__(self, "accumulate", accumulate)
        object.__setattr__(self, "additive", additive)
        object.__setattr__(self, "fill", fill)
        object.__setattr__(self, "restart", restart)
        object.__setattr__(self, "acceleration", acceleration)
        object.__setattr__(self, "deceleration", deceleration)
        for name, value in timing.items():
            object.__setattr__(self, name, value)
        self._validate()

    def _validate(self) -> None:
        """Normalise and check the behaviour-specific fields."""

    def _xml_attributes(self) -> dict[str, str]:
        return {}

    def _append_children(self, element: ET.Element) -> None:
        """Write the children that follow ``p:cBhvr``."""

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        """Behaviour-specific fields from markup; raise ValueError if foreign."""
        return {}


def _point_element(parent: ET.Element, tag: str, point: tuple[float, float], scale: float) -> None:
    ET.SubElement(
        parent,
        f"{{{P_NS}}}{tag}",
        {"x": _units(point[0], scale), "y": _units(point[1], scale)},
    )


def _parse_point(element: ET.Element, tag: str, scale: float) -> tuple[float, float] | None:
    child = element.find(f"{{{P_NS}}}{tag}")
    if child is None:
        return None
    if set(child.attrib) != {"x", "y"} or len(child):
        raise ValueError(tag)
    return (int(child.get("x", "")) / scale, int(child.get("y", "")) / scale)


def _parse_angle(element: ET.Element, name: str) -> float | None:
    return _from_units(element.get(name), _ANGLE_UNITS)


@dataclass(frozen=True, kw_only=True)
class ColorBehavior(AnimationBehavior):
    """Colour animation (``p:animClr``).

    ``color_space`` is ``rgb`` or ``hsl``; ``direction`` (``cw``/``ccw``) is
    the way round the hue wheel an HSL animation turns. ``offset`` is the
    ``p:by`` change: (r, g, b) percentages for RGB, or (hue degrees,
    saturation %, lightness %) for HSL. Colours are ``RRGGBB`` or scheme
    names.
    """

    color_space: str | None = "rgb"
    direction: str | None = "cw"
    offset: tuple[float, float, float] | None = None
    from_color: str | None = None
    to_color: str | None = None

    tag: ClassVar[str] = "animClr"
    _child_tags: ClassVar[tuple[str, ...]] = ("by", "from", "to")
    _element_attributes: ClassVar[frozenset[str]] = frozenset({"clrSpc", "dir"})

    def _validate(self) -> None:
        _optional_choice(self.color_space, "color_space", COLOR_SPACES)
        _optional_choice(self.direction, "direction", COLOR_DIRECTIONS)
        if self.offset is not None:
            offset = _numbers(self.offset, "colour offset", 3)
            if self.color_space == "hsl":
                limits = ((-math.inf, math.inf), (-100.0, 100.0), (-100.0, 100.0))
            else:
                limits = ((-100.0, 100.0),) * 3
            if not all(low <= v <= high for v, (low, high) in zip(offset, limits, strict=True)):
                raise _refuse(f"Colour offset {self.offset!r} is out of range")
            object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "from_color", _optional_color(self.from_color, "from_color"))
        object.__setattr__(self, "to_color", _optional_color(self.to_color, "to_color"))

    def _xml_attributes(self) -> dict[str, str]:
        attributes = {}
        if self.color_space is not None:
            attributes["clrSpc"] = self.color_space
        if self.direction is not None:
            attributes["dir"] = self.direction
        return attributes

    def _append_children(self, element: ET.Element) -> None:
        if self.offset is not None:
            by = ET.SubElement(element, f"{{{P_NS}}}by")
            first, second, third = self.offset
            if self.color_space == "hsl":
                ET.SubElement(
                    by,
                    f"{{{P_NS}}}hsl",
                    {
                        "h": _units(first, _ANGLE_UNITS),
                        "s": _units(second, _PERCENT_UNITS),
                        "l": _units(third, _PERCENT_UNITS),
                    },
                )
            else:
                ET.SubElement(
                    by,
                    f"{{{P_NS}}}rgb",
                    {
                        "r": _units(first, _PERCENT_UNITS),
                        "g": _units(second, _PERCENT_UNITS),
                        "b": _units(third, _PERCENT_UNITS),
                    },
                )
        for tag, color in (("from", self.from_color), ("to", self.to_color)):
            if color is not None:
                _append_color(ET.SubElement(element, f"{{{P_NS}}}{tag}"), color)

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        space = element.get("clrSpc")
        offset = None
        by = element.find(f"{{{P_NS}}}by")
        if by is not None:
            if len(by) != 1:
                raise ValueError("by")
            transform = by[0]
            name = _xml_local_name(transform.tag)
            keys = {"rgb": ("r", "g", "b"), "hsl": ("h", "s", "l")}.get(name)
            if keys is None or set(transform.attrib) != set(keys) or name != (space or "rgb"):
                raise ValueError("by")
            scales = (
                (_ANGLE_UNITS, _PERCENT_UNITS, _PERCENT_UNITS)
                if name == "hsl"
                else (_PERCENT_UNITS,) * 3
            )
            offset = tuple(
                int(transform.get(key, "")) / scale for key, scale in zip(keys, scales, strict=True)
            )
        colors: dict[str, str | None] = {}
        for tag in ("from", "to"):
            container = element.find(f"{{{P_NS}}}{tag}")
            colors[tag] = _color_value(container) if container is not None else None
            if container is not None and colors[tag] is None:
                raise ValueError(tag)
        return {
            "color_space": space,
            "direction": element.get("dir"),
            "offset": offset,
            "from_color": colors["from"],
            "to_color": colors["to"],
        }


@dataclass(frozen=True, kw_only=True)
class MotionBehavior(AnimationBehavior):
    """Motion along a path (``p:animMotion``).

    ``origin`` is ``parent`` or ``layout``; ``edit_mode`` (``pathEditMode``)
    is ``relative`` or ``fixed``. ``rotation_angle`` is degrees,
    ``rotation_center`` and the from/to/by points are slide fractions.
    """

    path: MotionPath | None = None
    origin: str | None = "layout"
    edit_mode: str | None = "relative"
    rotation_angle: float | None = 0.0
    rotation_center: tuple[float, float] | None = None
    by_point: tuple[float, float] | None = None
    from_point: tuple[float, float] | None = None
    to_point: tuple[float, float] | None = None

    tag: ClassVar[str] = "animMotion"
    _child_tags: ClassVar[tuple[str, ...]] = ("by", "from", "to", "rCtr")
    _element_attributes: ClassVar[frozenset[str]] = frozenset(
        {"origin", "path", "pathEditMode", "rAng", "ptsTypes"}
    )

    def _validate(self) -> None:
        if self.path is not None:
            if not isinstance(self.path, MotionPath):
                raise _refuse("Motion behaviour path must be a MotionPath")
            if len(self.path.commands) < 2:
                raise _refuse("A motion path needs a move and at least one more command")
        _optional_choice(self.origin, "origin", MOTION_ORIGINS)
        _optional_choice(self.edit_mode, "edit_mode", MOTION_EDIT_MODES)
        object.__setattr__(
            self,
            "rotation_angle",
            _optional_number(self.rotation_angle, "rotation_angle"),
        )
        for name in ("rotation_center", "by_point", "from_point", "to_point"):
            object.__setattr__(self, name, _optional_pair(getattr(self, name), name))

    def _xml_attributes(self) -> dict[str, str]:
        attributes = {}
        if self.origin is not None:
            attributes["origin"] = self.origin
        if self.path is not None:
            attributes["path"] = self.path.to_path()
        if self.edit_mode is not None:
            attributes["pathEditMode"] = self.edit_mode
        if self.rotation_angle is not None:
            attributes["rAng"] = _units(self.rotation_angle, _ANGLE_UNITS)
        if self.path is not None and (codes := self.path.points_types()) is not None:
            attributes["ptsTypes"] = codes
        return attributes

    def _append_children(self, element: ET.Element) -> None:
        for tag, point in (
            ("by", self.by_point),
            ("from", self.from_point),
            ("to", self.to_point),
            ("rCtr", self.rotation_center),
        ):
            if point is not None:
                _point_element(element, tag, point, _POINT_UNITS)

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        raw_path = element.get("path")
        return {
            "path": MotionPath.parse(raw_path, element.get("ptsTypes"))
            if raw_path is not None
            else None,
            "origin": element.get("origin"),
            "edit_mode": element.get("pathEditMode"),
            "rotation_angle": _parse_angle(element, "rAng"),
            "rotation_center": _parse_point(element, "rCtr", _POINT_UNITS),
            "by_point": _parse_point(element, "by", _POINT_UNITS),
            "from_point": _parse_point(element, "from", _POINT_UNITS),
            "to_point": _parse_point(element, "to", _POINT_UNITS),
        }


@dataclass(frozen=True, kw_only=True)
class RotationBehavior(AnimationBehavior):
    """Rotation (``p:animRot``): by, from, and to angles in degrees."""

    by_value: float | None = None
    from_value: float | None = None
    to_value: float | None = None

    tag: ClassVar[str] = "animRot"
    _element_attributes: ClassVar[frozenset[str]] = frozenset({"by", "from", "to"})

    def _validate(self) -> None:
        for name in ("by_value", "from_value", "to_value"):
            object.__setattr__(self, name, _optional_number(getattr(self, name), name))

    def _xml_attributes(self) -> dict[str, str]:
        return {
            name: _units(value, _ANGLE_UNITS)
            for name, value in (
                ("by", self.by_value),
                ("from", self.from_value),
                ("to", self.to_value),
            )
            if value is not None
        }

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        return {
            "by_value": _parse_angle(element, "by"),
            "from_value": _parse_angle(element, "from"),
            "to_value": _parse_angle(element, "to"),
        }


@dataclass(frozen=True, kw_only=True)
class ScaleBehavior(AnimationBehavior):
    """Scale (``p:animScale``): by, from, and to (width %, height %) sizes."""

    by_value: tuple[float, float] | None = None
    from_value: tuple[float, float] | None = None
    to_value: tuple[float, float] | None = None
    zoom_contents: bool | None = None

    tag: ClassVar[str] = "animScale"
    _child_tags: ClassVar[tuple[str, ...]] = ("by", "from", "to")
    _element_attributes: ClassVar[frozenset[str]] = frozenset({"zoomContents"})

    def _validate(self) -> None:
        for name in ("by_value", "from_value", "to_value"):
            object.__setattr__(self, name, _optional_pair(getattr(self, name), name))
        if self.zoom_contents is not None and not isinstance(self.zoom_contents, bool):
            raise _refuse("zoom_contents must be a boolean")

    def _xml_attributes(self) -> dict[str, str]:
        if self.zoom_contents is None:
            return {}
        return {"zoomContents": "1" if self.zoom_contents else "0"}

    def _append_children(self, element: ET.Element) -> None:
        for tag, size in (
            ("by", self.by_value),
            ("from", self.from_value),
            ("to", self.to_value),
        ):
            if size is not None:
                _point_element(element, tag, size, _PERCENT_UNITS)

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        zoom = element.get("zoomContents")
        if zoom not in {None, "0", "1", "true", "false"}:
            raise ValueError(zoom)
        return {
            "by_value": _parse_point(element, "by", _PERCENT_UNITS),
            "from_value": _parse_point(element, "from", _PERCENT_UNITS),
            "to_value": _parse_point(element, "to", _PERCENT_UNITS),
            "zoom_contents": None if zoom is None else zoom in {"1", "true"},
        }


_VARIANT_TAGS = {bool: "boolVal", int: "intVal", float: "fltVal", str: "strVal"}


def _property_expression(value: Any, name: str, *, formula: bool = False) -> str:
    """Validate a finite scalar or the arithmetic subset of tav formulas.

    The only variables are ppt_x/y/w/h (optionally prefixed with ``#``).
    In an interval formula, ``$`` is the interpolated input value; it is
    not elapsed time. Calls, powers, comparisons, and formula lists are
    intentionally refused rather than assigned invented semantics.
    """
    if type(value) in (int, float):
        try:
            finite = math.isfinite(value)
        except OverflowError as exc:
            raise _refuse(f"Invalid property {name}: must be finite") from exc
        if not finite:
            raise _refuse(f"Invalid property {name}: must be finite")
        return str(value)
    if not isinstance(value, str) or not value.strip():
        raise _refuse(f"Invalid property {name}: needs a numeric value or safe expression")
    expression = re.sub(r"#(?=ppt_[xywh]\b)", "", value.strip())
    if "#" in expression or "__input" in expression:
        raise _refuse(f"Unsupported property {name} expression: {value!r}")
    if formula:
        expression = expression.replace("$", "__input")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise _refuse(f"Unsupported property {name} expression: {value!r}") from exc
    variables = {"ppt_x", "ppt_y", "ppt_w", "ppt_h"}
    if formula:
        variables.add("__input")

    def visit(node: ast.AST) -> float | None:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            result = float(node.value)
        elif isinstance(node, ast.Name) and node.id in variables:
            return None
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = visit(node.operand)
            result = (
                None if operand is None else operand * (-1 if isinstance(node.op, ast.USub) else 1)
            )
        elif isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
        ):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise _refuse(f"Invalid property {name} expression: division by zero")
            if left is None or right is None:
                return None
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            else:
                result = left / right
        else:
            raise _refuse(f"Unsupported property {name} expression: {value!r}")
        if result is not None and not math.isfinite(result):
            raise _refuse(f"Invalid property {name} expression: must be finite")
        return result

    try:
        visit(tree)
    except (OverflowError, RecursionError) as exc:
        raise _refuse(f"Invalid property {name} expression: {value!r}") from exc
    return value


def _property_value(value: Any, name: str, value_type: str) -> str:
    if value_type == "num":
        return _property_expression(value, name)
    if value_type == "clr":
        color = _optional_color(value, f"property {name}")
        if color is None:
            raise _refuse(f"Invalid property {name}: needs a colour value")
        return color
    if not isinstance(value, str) or any(
        not (
            ch in "\t\n\r"
            or "\x20" <= ch <= "\ud7ff"
            or "\ue000" <= ch <= "\ufffd"
            or "\U00010000" <= ch <= "\U0010ffff"
        )
        for ch in value
    ):
        raise _refuse(f"Invalid property {name}: needs an XML-safe literal string")
    return value


@dataclass(frozen=True, kw_only=True)
class PropertyBehavior(AnimationBehavior):
    """Editable ``p:anim`` with numeric, colour, or literal string values.

    ``value_type`` is ``num``, ``clr`` (RRGGBB or scheme colour), or ``str``.
    ``calc_mode`` is ``lin`` or ``discr``; strings require ``discr``, serialized
    using the schema spelling ``discrete``. Numeric keys retain safe ppt
    arithmetic expressions. A starting key's optional
    formula transforms the interpolated input ``$`` until the next key.

    ``fmla`` is formula-only: numeric keys have ``value=None``, every starting
    key has a formula, and the terminal key has no formula. ``$`` is normalized
    interval progress, including 1 for the last interval's terminal result.
    The XML omits the optional ``p:val``. Arithmetic is unary +/- and binary
    +,-,*,/ over finite literals and ppt_x/y/w/h; calls, powers, comparisons,
    formula lists, and other variables are named refusals.
    CT_TLTimeAnimateValue permits absent val; MS-OE376 defines formula input
    as progress:
    https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/981b17ff-5594-42cf-ad8d-7cb39e653afa

    Numeric endpoints support from+to, from+by, to-only, or by-only, starting
    at zero for to/by-only. Colour/string endpoints support from+to or to-only;
    additive by values and nonnumeric formulas are not supported. Endpoints
    cannot accompany keyframes. Replace this immutable object through
    ``AnimationEffect.set_behavior`` to edit saved keys.
    """

    calc_mode: str = "lin"
    value_type: str = "num"
    keyframes: tuple[AnimationKeyframe, ...] = ()
    from_value: str | None = None
    to_value: str | None = None
    by_value: str | None = None

    tag: ClassVar[str] = "anim"
    _child_tags: ClassVar[tuple[str, ...]] = ("tavLst",)
    _element_attributes: ClassVar[frozenset[str]] = frozenset(
        {"calcmode", "valueType", "from", "to", "by"}
    )

    def _validate(self) -> None:
        if len(self.attributes) != 1:
            raise _refuse("A property behaviour needs exactly one animated attribute")
        _choice(self.calc_mode, "property calc_mode", PROPERTY_CALC_MODES)
        _choice(self.value_type, "property value_type", PROPERTY_VALUE_TYPES)
        if self.value_type == "str" and self.calc_mode != "discr":
            raise _refuse("Unsupported string property interpolation: use calc_mode 'discr'")
        if self.calc_mode == "fmla" and self.value_type != "num":
            raise _refuse("Unsupported formula-only property value_type: use num")
        if isinstance(self.keyframes, (str, bytes)) or not isinstance(self.keyframes, Sequence):
            raise _refuse("Property keyframes must be a sequence of AnimationKeyframe objects")
        keys: list[AnimationKeyframe] = []
        last_tick = -1
        for index, key in enumerate(self.keyframes):
            if not isinstance(key, AnimationKeyframe):
                raise _refuse(f"Invalid property keyframe {index}: needs AnimationKeyframe")
            try:
                time = _number(key.time, f"property keyframe {index} time")
            except OverflowError as exc:
                raise _refuse(
                    f"Invalid property keyframe {index} time: must be within 0..1"
                ) from exc
            if not 0 <= time <= 1:
                raise _refuse(f"Invalid property keyframe {index} time: must be within 0..1")
            tick = round(time * 100000)
            if tick <= last_tick:
                raise _refuse(
                    "Property keyframe times must increase strictly within 0..1 at XML precision"
                )
            if self.calc_mode == "fmla":
                if key.value is not None:
                    raise _refuse("Formula-only property keyframes must have value=None")
                value = None
                if index < len(self.keyframes) - 1 and key.formula is None:
                    raise _refuse("Formula-only property intervals each need a formula")
            else:
                value = _property_value(key.value, f"keyframe {index} value", self.value_type)
            formula = None
            if key.formula is not None:
                if self.value_type != "num":
                    raise _refuse("Unsupported property formulas for colour/string values")
                if not isinstance(key.formula, str):
                    raise _refuse(f"Invalid property keyframe {index} formula: needs a string")
                formula = _property_expression(
                    key.formula, f"keyframe {index} formula", formula=True
                )
            keys.append(AnimationKeyframe(tick / 100000, value, formula))
            last_tick = tick
        if keys and (len(keys) < 2 or keys[-1].formula is not None):
            raise _refuse(
                "Property keyframes need at least two keys and no formula on the final key"
            )
        object.__setattr__(self, "keyframes", tuple(keys))
        for name in ("from_value", "to_value", "by_value"):
            value = getattr(self, name)
            if value is not None:
                if self.calc_mode == "fmla":
                    raise _refuse("Formula-only properties cannot use from/to/by values")
                if name == "by_value" and self.value_type != "num":
                    raise _refuse(
                        "Unsupported colour/string property by_value: use keys or to_value"
                    )
                object.__setattr__(self, name, _property_value(value, name, self.value_type))
        if keys:
            if any(value is not None for value in (self.from_value, self.to_value, self.by_value)):
                raise _refuse("Property keyframes cannot be combined with from/to/by values")
        elif self.calc_mode == "fmla":
            raise _refuse("Formula-only properties need at least two keyframes")
        elif (self.to_value is None and self.by_value is None) or (
            self.to_value is not None and self.by_value is not None
        ):
            raise _refuse("Property values require from+to, from+by, to-only, or by-only")

    def _xml_attributes(self) -> dict[str, str]:
        attributes = {
            "calcmode": "discrete" if self.calc_mode == "discr" else self.calc_mode,
            "valueType": self.value_type,
        }
        for name in ("from", "to", "by"):
            value = getattr(self, f"{name}_value")
            if value is not None:
                attributes[name] = value
        return attributes

    def _append_children(self, element: ET.Element) -> None:
        if not self.keyframes:
            return
        values = ET.SubElement(element, f"{{{P_NS}}}tavLst")
        for key in self.keyframes:
            attributes = {"tm": str(round(key.time * 100000))}
            if key.formula is not None:
                attributes["fmla"] = key.formula
            tav = ET.SubElement(values, f"{{{P_NS}}}tav", attributes)
            if key.value is not None:
                value = ET.SubElement(tav, f"{{{P_NS}}}val")
                if self.value_type == "clr":
                    _append_color(ET.SubElement(value, f"{{{P_NS}}}clrVal"), key.value)
                else:
                    ET.SubElement(value, f"{{{P_NS}}}strVal", {"val": key.value})

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        value_type = element.get("valueType", "num")
        if any(
            not node.tag.startswith(f"{{{P_NS}}}")
            and node.tag not in {f"{{{A_NS}}}srgbClr", f"{{{A_NS}}}schemeClr"}
            for node in element.iter()
        ):
            raise ValueError("property namespaces")
        for node in element.iter():
            if node.text and node.text.strip() and node.tag != f"{{{P_NS}}}attrName":
                raise ValueError("property element text")
            if node.tail and node.tail.strip():
                raise ValueError("property tail text")
            if (
                node.tag in {f"{{{P_NS}}}{tag}" for tag in ("tgtEl", "attrNameLst", "stCondLst")}
                and node.attrib
            ):
                raise ValueError("property container attributes")
        keys = []
        values = element.find(f"{{{P_NS}}}tavLst")
        if values is not None:
            if values.attrib or not len(values):
                raise ValueError("tavLst")
            for tav in values:
                raw_time = tav.get("tm", "")
                if (
                    tav.tag != f"{{{P_NS}}}tav"
                    or not set(tav.attrib) <= {"tm", "fmla"}
                    or not raw_time.isdigit()
                    or len(tav) > 1
                ):
                    raise ValueError("tav")
                tick = int(raw_time)
                if not 0 <= tick <= 100000:
                    raise ValueError("property time")
                raw_value = None
                if len(tav):
                    container = tav[0]
                    if container.tag != f"{{{P_NS}}}val" or container.attrib or len(container) != 1:
                        raise ValueError("property value container")
                    variant = container[0]
                    if value_type == "clr":
                        if (
                            variant.tag != f"{{{P_NS}}}clrVal"
                            or variant.attrib
                            or len(variant) != 1
                            or variant[0].tag not in {f"{{{A_NS}}}srgbClr", f"{{{A_NS}}}schemeClr"}
                            or set(variant[0].attrib) != {"val"}
                        ):
                            raise ValueError("property colour variant")
                        raw_value = _color_value(variant)
                        if raw_value is None:
                            raise ValueError("property colour")
                    else:
                        tags = (
                            ("strVal", "fltVal", "intVal") if value_type == "num" else ("strVal",)
                        )
                        if (
                            variant.tag not in {f"{{{P_NS}}}{tag}" for tag in tags}
                            or set(variant.attrib) != {"val"}
                            or len(variant)
                        ):
                            raise ValueError("property variant")
                        raw_value = variant.get("val")
                        if variant.tag == f"{{{P_NS}}}intVal":
                            int(raw_value)
                        elif variant.tag == f"{{{P_NS}}}fltVal":
                            float(raw_value)
                keys.append(AnimationKeyframe(tick / 100000, raw_value, tav.get("fmla")))
        return {
            "calc_mode": "discr"
            if element.get("calcmode") == "discrete"
            else element.get("calcmode", "lin"),
            "value_type": element.get("valueType", "num"),
            "keyframes": tuple(keys),
            "from_value": element.get("from"),
            "to_value": element.get("to"),
            "by_value": element.get("by"),
        }


@dataclass(frozen=True, kw_only=True)
class SetBehavior(AnimationBehavior):
    """Set the properties in ``attributes`` to ``value`` (``p:set``).

    ``value`` is a string, boolean, integer, or float and is written as the
    matching ``p:strVal``/``p:boolVal``/``p:intVal``/``p:fltVal``.
    """

    value: str | bool | int | float | None = None

    tag: ClassVar[str] = "set"
    _child_tags: ClassVar[tuple[str, ...]] = ("to",)

    def _validate(self) -> None:
        if not self.attributes:
            raise _refuse("A set behaviour needs a property list (attributes)")
        if self.value is not None and type(self.value) not in _VARIANT_TAGS:
            raise _refuse(f"Invalid set value: {self.value!r} (use str, bool, int, or float)")
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise _refuse("A set value must be a finite number")

    def _append_children(self, element: ET.Element) -> None:
        if self.value is None:
            return
        to_el = ET.SubElement(element, f"{{{P_NS}}}to")
        value = self.value
        if isinstance(value, bool):
            text = "1" if value else "0"
        elif isinstance(value, float):
            text = _format_coordinate(value)
        else:
            text = str(value)
        ET.SubElement(to_el, f"{{{P_NS}}}{_VARIANT_TAGS[type(value)]}", {"val": text})

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        to_el = element.find(f"{{{P_NS}}}to")
        if to_el is None:
            return {"value": None}
        if len(to_el) != 1 or set(to_el[0].attrib) != {"val"} or len(to_el[0]):
            raise ValueError("to")
        name = _xml_local_name(to_el[0].tag)
        raw = to_el[0].get("val", "")
        if name == "strVal":
            return {"value": raw}
        if name == "boolVal":
            if raw not in {"0", "1", "true", "false"}:
                raise ValueError(raw)
            return {"value": raw in {"1", "true"}}
        if name == "intVal":
            return {"value": int(raw)}
        if name == "fltVal":
            return {"value": float(raw)}
        raise ValueError(name)


@dataclass(frozen=True, kw_only=True)
class CommandBehavior(AnimationBehavior):
    """A command (``p:cmd``): ``command_type`` event, call, or verb, and its string."""

    command_type: str = "call"
    command: str = ""

    tag: ClassVar[str] = "cmd"
    _element_attributes: ClassVar[frozenset[str]] = frozenset({"type", "cmd"})

    def _validate(self) -> None:
        _choice(self.command_type, "command_type", COMMAND_TYPES)
        if not isinstance(self.command, str):
            raise _refuse("A command behaviour's command must be a string")

    def _xml_attributes(self) -> dict[str, str]:
        return {"type": _COMMAND_TYPE_XML[self.command_type], "cmd": self.command}

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        command_type = _COMMAND_TYPE_BY_XML.get(element.get("type", ""))
        command = element.get("cmd")
        if command_type is None or command is None:
            raise ValueError("cmd")
        return {"command_type": command_type, "command": command}


@dataclass(frozen=True, kw_only=True)
class FilterBehavior(AnimationBehavior):
    """A filter transition (``p:animEffect``), such as ``fade`` or ``wipe(down)``."""

    transition: str | None = "in"
    filter: str | None = None
    properties: str | None = None

    tag: ClassVar[str] = "animEffect"
    _element_attributes: ClassVar[frozenset[str]] = frozenset({"transition", "filter", "prLst"})

    def _validate(self) -> None:
        _optional_choice(self.transition, "transition", FILTER_TRANSITIONS)
        for name in ("filter", "properties"):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), str):
                raise _refuse(f"Filter behaviour {name} must be a string")

    def _xml_attributes(self) -> dict[str, str]:
        attributes = {}
        for key, value in (
            ("transition", self.transition),
            ("filter", self.filter),
            ("prLst", self.properties),
        ):
            if value is not None:
                attributes[key] = value
        return attributes

    @classmethod
    def _parse_fields(cls, element: ET.Element) -> dict[str, Any]:
        return {
            "transition": element.get("transition"),
            "filter": element.get("filter"),
            "properties": element.get("prLst"),
        }


Behavior = AnimationBehavior | RawBehavior
_BEHAVIOR_CLASSES: dict[str, type[AnimationBehavior]] = {
    cls.tag: cls
    for cls in (
        ColorBehavior,
        MotionBehavior,
        RotationBehavior,
        ScaleBehavior,
        SetBehavior,
        PropertyBehavior,
        CommandBehavior,
        FilterBehavior,
    )
}
_COMMON_TIMING_ATTRIBUTES = frozenset({"id", "dur", "fill", "restart", "accel", "decel"})


def _markup(element: ET.Element) -> str:
    clone = copy.copy(element)
    clone.tail = None
    return ET.tostring(clone, encoding="unicode")


def _parse_common(element: ET.Element, child_tags: tuple[str, ...]) -> dict[str, Any]:
    """``p:cBhvr`` fields; raise ValueError for markup outside the model."""
    kids = list(element)
    tags = [_xml_local_name(kid.tag) for kid in kids]
    if not tags or tags[0] != "cBhvr":
        raise ValueError("cBhvr")
    expected = [tag for tag in child_tags if tag in tags[1:]]
    if tags[1:] != expected:
        raise ValueError("children")
    behavior = kids[0]
    if not set(behavior.attrib) <= {"accumulate", "additive"}:
        raise ValueError("cBhvr attributes")
    parts = [_xml_local_name(kid.tag) for kid in behavior]
    if parts not in (["cTn", "tgtEl"], ["cTn", "tgtEl", "attrNameLst"]):
        raise ValueError("cBhvr children")
    c_tn, target = behavior[0], behavior[1]
    if not set(c_tn.attrib) <= _COMMON_TIMING_ATTRIBUTES:
        raise ValueError("cTn attributes")
    easing: list[float | None] = []
    for name in ("accel", "decel"):
        raw = c_tn.get(name)
        if raw is not None and re.fullmatch(r"[+-]?[0-9]+", raw.strip()) is None:
            raise ValueError(name)
        try:
            easing.append(_from_units(raw, _POINT_UNITS))
        except OverflowError as exc:
            raise ValueError(name) from exc
    acceleration, deceleration = coerce_acceleration_deceleration(*easing)
    delay = None
    if len(c_tn):
        conditions = c_tn[0]
        if (
            len(c_tn) != 1
            or _xml_local_name(conditions.tag) != "stCondLst"
            or len(conditions) != 1
            or set(conditions[0].attrib) != {"delay"}
            or len(conditions[0])
        ):
            raise ValueError("stCondLst")
        delay = _seconds(conditions[0].get("delay"))
    if (
        len(target) != 1
        or _xml_local_name(target[0].tag) != "spTgt"
        or set(target[0].attrib) != {"spid"}
        or len(target[0])
    ):
        raise ValueError("tgtEl")
    names: list[str] = []
    if len(parts) == 3:
        for attr in behavior[2]:
            if _xml_local_name(attr.tag) != "attrName" or attr.attrib or len(attr):
                raise ValueError("attrName")
            names.append(attr.text or "")
    return {
        "attributes": tuple(names),
        "accumulate": behavior.get("accumulate"),
        "additive": behavior.get("additive"),
        "duration": _seconds(c_tn.get("dur")),
        "delay": delay,
        "fill": c_tn.get("fill"),
        "restart": coerce_restart(c_tn.get("restart")),
        "acceleration": acceleration,
        "deceleration": deceleration,
    }


def parse_behavior(element: ET.Element) -> Behavior:
    """The modelled behaviour for ``element``, else a :class:`RawBehavior`."""
    tag = _xml_local_name(element.tag)
    cls = _BEHAVIOR_CLASSES.get(tag)
    if cls is not None and set(element.attrib) <= cls._element_attributes:
        try:
            return cls(**_parse_common(element, cls._child_tags), **cls._parse_fields(element))
        except ValueError:
            pass  # SlideAnimationRefusalError included: outside the model.
    return RawBehavior(tag, _markup(element))


def parse_behaviors(child_tn_lst: ET.Element | None) -> tuple[Behavior, ...]:
    """Every behaviour in an effect's ``p:childTnLst``, in document order."""
    if child_tn_lst is None:
        return ()
    return tuple(parse_behavior(child) for child in child_tn_lst)


def is_authorable(behaviors: Sequence[Behavior]) -> bool:
    """True when every behaviour is modelled (none is raw markup)."""
    return bool(behaviors) and all(
        isinstance(behavior, AnimationBehavior) for behavior in behaviors
    )


def coerce_behaviors(value: Any) -> tuple[AnimationBehavior, ...]:
    """Validate a behaviour list for authoring."""
    if isinstance(value, (str, bytes, AnimationBehavior)) or not isinstance(value, Sequence):
        raise _refuse("Behaviours must be a sequence of behaviour objects")
    behaviors = tuple(value)
    if not behaviors:
        raise _refuse("An effect needs at least one behaviour")
    for behavior in behaviors:
        if isinstance(behavior, RawBehavior):
            raise _refuse(f"Behaviour <p:{behavior.tag}> is read-only and cannot be authored")
        if not isinstance(behavior, AnimationBehavior):
            raise _refuse(f"Not an animation behaviour: {behavior!r}")
    return behaviors


def append_behavior(
    parent: ET.Element,
    behavior: AnimationBehavior,
    shape_id: str,
    duration_ms: str,
    alloc_id: Any,
) -> ET.Element:
    """Write one behaviour targeting ``shape_id`` under ``parent``."""
    fill = coerce_fill(behavior.fill)
    restart = coerce_restart(behavior.restart)
    acceleration, deceleration = coerce_acceleration_deceleration(
        behavior.acceleration, behavior.deceleration
    )
    timing = {"dur": duration_ms if behavior.duration is None else _milliseconds(behavior.duration)}
    if fill is not None:
        timing["fill"] = fill
    if restart is not None:
        timing["restart"] = restart
    for name, value in (("accel", acceleration), ("decel", deceleration)):
        if value is not None:
            timing[name] = _units(value, _POINT_UNITS)
    composition = {
        key: value
        for key, value in (
            ("accumulate", behavior.accumulate),
            ("additive", behavior.additive),
        )
        if value is not None
    }
    element = _append_behavior(
        parent,
        behavior.tag,
        shape_id,
        alloc_id,
        timing,
        attr_names=behavior.attributes,
        attributes=behavior._xml_attributes(),
        behavior=composition or None,
        delay=None if behavior.delay is None else _milliseconds(behavior.delay),
    )
    behavior._append_children(element)
    return element


class BehaviorFactory:
    """Creates behaviours for custom effects.

    Every ``create_*`` method forwards common keyword arguments:
    ``accumulate`` (:class:`AccumulateMode`), ``additive`` (:class:`AdditiveMode`),
    ``duration`` and ``delay`` in seconds, ``fill`` (:class:`FillMode`), and
    ``restart`` (:class:`RestartMode`), plus fractional ``acceleration`` and
    ``deceleration``. Literal strings remain accepted for named choices.
    Timing is local to the behaviour; None omits the corresponding attribute
    except that a None duration inherits the effect's duration when written.
    Add the immutable result to an effect with ``AnimationEffect.add_behavior``
    or pass a list to ``SlideAnimation.add_custom``.
    """

    def create_property(
        self,
        attributes: Sequence[str],
        *,
        keyframes: Sequence[AnimationKeyframe] = (),
        calc_mode: str = "lin",
        value_type: str = "num",
        from_value: str | float | int | None = None,
        to_value: str | float | int | None = None,
        by_value: str | float | int | None = None,
        **common: Any,
    ) -> PropertyBehavior:
        """Animate one numeric, colour, or discrete literal string property."""
        return PropertyBehavior(
            attributes=attributes,
            keyframes=keyframes,
            calc_mode=calc_mode,
            value_type=value_type,
            from_value=from_value,
            to_value=to_value,
            by_value=by_value,
            **common,
        )

    def create_color(
        self,
        *,
        to_color: str | None = None,
        from_color: str | None = None,
        offset: Sequence[float] | None = None,
        color_space: str = "rgb",
        direction: str = "cw",
        attributes: Sequence[str] = ("fillcolor",),
        **common: Any,
    ) -> ColorBehavior:
        """Animate a colour property (fill colour by default)."""
        return ColorBehavior(
            to_color=to_color,
            from_color=from_color,
            offset=offset,  # type: ignore[arg-type]
            color_space=color_space,
            direction=direction,
            attributes=tuple(attributes),
            **common,
        )

    def create_motion(
        self,
        path: MotionPath,
        *,
        origin: str = "layout",
        edit_mode: str = "relative",
        rotation_angle: float = 0.0,
        rotation_center: Sequence[float] | None = None,
        attributes: Sequence[str] = ("ppt_x", "ppt_y"),
        **common: Any,
    ) -> MotionBehavior:
        """Move along ``path``; the rotation centre defaults to its bounding-box midpoint."""
        if not isinstance(path, MotionPath):
            raise _refuse("create_motion needs a MotionPath")
        if rotation_center is None and len(path.commands) >= 2:
            (min_x, min_y), (max_x, max_y) = path.bounds()
            # Snap to CT_TLPoint units so the saved centre reads back equal.
            rotation_center = (
                round((min_x + max_x) * _POINT_UNITS / 2) / _POINT_UNITS,
                round((min_y + max_y) * _POINT_UNITS / 2) / _POINT_UNITS,
            )
        return MotionBehavior(
            path=path,
            origin=origin,
            edit_mode=edit_mode,
            rotation_angle=rotation_angle,
            rotation_center=rotation_center,  # type: ignore[arg-type]
            attributes=tuple(attributes),
            **common,
        )

    def create_rotation(
        self,
        *,
        by_value: float | None = None,
        from_value: float | None = None,
        to_value: float | None = None,
        attributes: Sequence[str] = ("r",),
        **common: Any,
    ) -> RotationBehavior:
        """Rotate by, from, or to an angle in degrees."""
        return RotationBehavior(
            by_value=by_value,
            from_value=from_value,
            to_value=to_value,
            attributes=tuple(attributes),
            **common,
        )

    def create_scale(
        self,
        *,
        by_value: Sequence[float] | None = None,
        from_value: Sequence[float] | None = None,
        to_value: Sequence[float] | None = None,
        zoom_contents: bool | None = None,
        **common: Any,
    ) -> ScaleBehavior:
        """Scale by, from, or to (width %, height %)."""
        return ScaleBehavior(
            by_value=by_value,  # type: ignore[arg-type]
            from_value=from_value,  # type: ignore[arg-type]
            to_value=to_value,  # type: ignore[arg-type]
            zoom_contents=zoom_contents,
            **common,
        )

    def create_set(
        self,
        attributes: Sequence[str],
        value: str | bool | int | float,
        **common: Any,
    ) -> SetBehavior:
        """Set every property in ``attributes`` to ``value``."""
        return SetBehavior(attributes=tuple(attributes), value=value, **common)

    def create_command(self, command_type: str, command: str, **common: Any) -> CommandBehavior:
        """Issue a command: ``event``, ``call`` (e.g. ``togglePause``), or ``verb``."""
        return CommandBehavior(command_type=command_type, command=command, **common)

    def create_filter(
        self,
        filter: str,
        *,
        transition: str = "in",
        properties: str | None = None,
        **common: Any,
    ) -> FilterBehavior:
        """Apply a filter transition such as ``fade`` or ``wipe(down)``."""
        return FilterBehavior(filter=filter, transition=transition, properties=properties, **common)
