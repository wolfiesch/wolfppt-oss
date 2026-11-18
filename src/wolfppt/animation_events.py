"""Explicit, bounded command authorization and side-effect-free playback events.

Saved command strings are identities only: no evaluation, shell, or network
execution is provided. Rendering never dispatches; the caller advances a bound
session explicitly with ``dispatch_until(seconds)``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .slide_animation_behaviors import CommandBehavior

__all__ = ["CommandEvent", "CommandDispatchContext", "CommandTimeline"]

MAX_COMMAND_EVENTS = 10000


def _refuse(detail: str) -> Exception:
    # The refusal stays importable in Community; the renderer is not.
    from .slide_animation_behaviors import AnimationFrameRefusal

    return AnimationFrameRefusal(f"Animation 'command': {detail}")


def _time(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _refuse("event time must be finite non-negative seconds")
    try:
        number = float(value)
    except OverflowError as exc:
        raise _refuse("event time must be finite non-negative seconds") from exc
    if not math.isfinite(number) or number < 0:
        raise _refuse("event time must be finite non-negative seconds")
    return number


def _key(shape_id: Any, command_type: Any, command: Any) -> tuple[str, str, str]:
    if (
        isinstance(shape_id, bool)
        or not isinstance(shape_id, (int, str))
        or not str(shape_id).isascii()
        or not str(shape_id).isdigit()
        or not str(shape_id).lstrip("0")
    ):
        raise _refuse("shape_id must be a positive slide shape identifier")
    if not isinstance(command_type, str) or command_type not in ("event", "call", "verb"):
        raise _refuse("command_type must be event, call, or verb")
    if not isinstance(command, str):
        raise _refuse("command must be an exact string identity")
    return str(shape_id), command_type, command


@dataclass(frozen=True)
class CommandEvent:
    """Immutable scheduled command identity, in slide-relative seconds."""

    time: float
    shape_id: str | int
    command_type: str
    command: str

    def __post_init__(self) -> None:
        shape, kind, command = _key(self.shape_id, self.command_type, self.command)
        object.__setattr__(self, "time", _time(self.time))
        object.__setattr__(self, "shape_id", shape)
        object.__setattr__(self, "command_type", kind)
        object.__setattr__(self, "command", command)


class CommandDispatchContext:
    """Exact (shape, type, command) callback registrations; no wildcard grants.

    A context may bind multiple independent generators. Binding snapshots all
    authorizations before dispatch, so later registrations cannot change a
    generator's approved timeline. Duplicate registrations refuse rather than
    silently replacing a caller's authorization.
    """

    def __init__(self) -> None:
        self._callbacks: dict[tuple[str, str, str], Callable[[CommandEvent], Any]] = {}

    def register(
        self,
        shape_id: str | int,
        command_type: str,
        command: str,
        callback: Callable[[CommandEvent], Any],
    ) -> None:
        key = _key(shape_id, command_type, command)
        if not callable(callback):
            raise _refuse("registered callback must be callable")
        if key in self._callbacks:
            raise _refuse(f"duplicate registration for shape {key[0]!r} and command identity")
        if len(self._callbacks) >= MAX_COMMAND_EVENTS:
            raise _refuse("command registration limit exceeded")
        self._callbacks[key] = callback

    def authorize(self, shape_id: str | int, behavior: CommandBehavior) -> None:
        """Preflight one track without calling any callback."""
        if not isinstance(behavior, CommandBehavior):
            raise _refuse("authorization requires a CommandBehavior")
        key = _key(shape_id, behavior.command_type, behavior.command)
        if key not in self._callbacks:
            raise _refuse(f"unauthorized command identity on shape {key[0]!r}")

    def bind(self, events: Iterable[CommandEvent]) -> CommandTimeline:
        """Validate the entire bounded timeline and freeze its callback snapshot."""
        snapshot = dict(self._callbacks)
        approved: list[tuple[CommandEvent, Callable[[CommandEvent], Any]]] = []
        for event in events:
            if len(approved) >= MAX_COMMAND_EVENTS:
                raise _refuse("command timeline limit exceeded")
            if not isinstance(event, CommandEvent):
                raise _refuse("command timeline entries must be immutable CommandEvent objects")
            key = _key(event.shape_id, event.command_type, event.command)
            if key not in snapshot:
                raise _refuse(f"unauthorized command identity on shape {key[0]!r}")
            approved.append((event, snapshot[key]))
        approved.sort(key=lambda item: item[0].time)
        return CommandTimeline(tuple(approved))


class CommandTimeline:
    """Per-generator exactly-once session returned by context.bind().

    Events are consumed before invoking callbacks: a failed callback is not
    retried. Its exception becomes a named playback refusal; subsequent explicit
    advancement may dispatch the remaining events. Reentrant dispatch refuses.
    """

    def __init__(
        self, approved: tuple[tuple[CommandEvent, Callable[[CommandEvent], Any]], ...]
    ) -> None:
        self._approved = approved
        self._cursor = 0
        self._time = -1.0
        self._dispatching = False

    @property
    def events(self) -> tuple[CommandEvent, ...]:
        return tuple(event for event, _callback in self._approved)

    def dispatch_until(self, time: float) -> tuple[CommandEvent, ...]:
        """Dispatch pending events through time inclusive, without rendering."""
        number = _time(time)
        if self._dispatching:
            raise _refuse("reentrant dispatch is unsupported")
        if number < self._time:
            raise _refuse("dispatch time must advance monotonically")
        self._time = number
        delivered: list[CommandEvent] = []
        self._dispatching = True
        try:
            while self._cursor < len(self._approved):
                event, callback = self._approved[self._cursor]
                if event.time > number:
                    break
                self._cursor += 1
                try:
                    callback(event)
                except Exception as exc:
                    raise _refuse(f"callback failed for shape {event.shape_id!r}") from exc
                delivered.append(event)
        finally:
            self._dispatching = False
        return tuple(delivered)


def bind_command_timeline(
    effects: Iterable[Any], context: CommandDispatchContext | None
) -> CommandTimeline:
    """Bind validated frame tracks without dispatching any command.

    Commands have one activation, no repeats/reversal/easing/time remapping,
    and must start within their effect's active interval. Inactive triggered
    sequences are authorized too, but do not produce dispatchable events.
    """
    if context is not None and not isinstance(context, CommandDispatchContext):
        raise _refuse("command_context must be a CommandDispatchContext")
    events: list[CommandEvent] = []
    command_count = 0
    for effect in effects:
        for track in effect.tracks:
            behavior = track.behavior
            if not isinstance(behavior, CommandBehavior):
                continue
            command_count += 1
            if command_count > MAX_COMMAND_EVENTS:
                raise _refuse("command timeline limit exceeded")
            if context is None:
                raise _refuse("no command execution context or command authorization")
            context.authorize(effect.target, behavior)
            if (
                effect.repeat != 1
                or effect.reverse
                or effect.acceleration
                or effect.deceleration
                or track.repeat != 1
                or track.reverse
                or track.time_filter
                or behavior.acceleration
                or behavior.deceleration
            ):
                raise _refuse("command repeats, reversal, easing, or time remapping unsupported")
            delay = _time(track.delay)
            cycle = _time(effect.cycle)
            if delay > cycle:
                raise _refuse("command delay exceeds its effect interval")
            if effect.start == math.inf:
                continue
            start = _time(effect.start)
            events.append(
                CommandEvent(start + delay, effect.target, behavior.command_type, behavior.command)
            )
    return (context or CommandDispatchContext()).bind(events)
