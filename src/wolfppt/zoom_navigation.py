"""Play slide, section and summary zoom navigation from explicit activation events.

Static rendering draws a zoom frame as its thumbnail. Playback adds the
navigation a presenter triggers by clicking that frame. Supply the clicks as a
finite tuple of :class:`ZoomActivation` events through
``GifOptions(zoom_activations=...)``; :func:`plan_zoom_navigation` returns the
same route as data without rendering.

Playback starts at the first rendered slide and follows slide order. After a
slide's animation and dwell, the next pending event hosted on that slide fires:

* a slide zoom zooms into its destination slide;
* a section zoom, or one summary zoom entry, zooms into the section's first
  rendered slide and traverses the section's rendered slides in order, with
  their ordinary transitions between them;
* with ``return_to_parent`` the last destination slide zooms back out to the
  host, which shows its finished state; further events on the host fire next,
  then playback continues after the host;
* without ``return_to_parent`` playback continues in slide order from the
  destination slide (for a section, through the rest of the section and on).

The zoom transition lasts the frame's stored ``transition_duration``
(milliseconds). ``None`` uses destination timing: the destination slide's
authored transition duration, else ``GifOptions.transition_duration``. A zero
duration cuts. Each zoom frame moves the viewport linearly from the whole host
slide to the frame bounds while the destination fades in over the frame;
returning plays the same frames in reverse.

Malformed zoom metadata keeps raising ``ZoomFrameRefusal`` and destinations
that do not exist or are not rendered keep raising ``ZoomTargetError``.
:class:`ZoomPlaybackRefusal` names playback this module does not model: events
on slides playback never reaches, events fired inside a returning zoom (nested
navigation), summary zooms whose entry is not named or not placed, grouped,
rotated or flipped frames (ambiguous composite mappings), and event sources that
are not finite tuples or whose route exceeds the playback step bound (unbounded
event cycles).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .render_model import DeckScene
from .render_package import Package, read_package, resolve_target
from .render_refusals import RenderRefusal
from .section_xml import read_sections_from_element
from .shape_xml import A_NS, MC_NS, P166_NS, P_NS, R_NS
from .slide_zoom_targets import ZoomTargetError
from .zoom_frames import ZoomFrame, _parse, _properties, _read, _select

#: Largest number of activation events one playback admits.
MAX_ZOOM_ACTIVATIONS = 256
#: Largest number of shown slides and zoom transitions one playback admits.
MAX_PLAYBACK_STEPS = 4096
_PRESENTATION = "ppt/presentation.xml"


class ZoomPlaybackRefusal(RenderRefusal):
    """Zoom navigation the player does not model; nothing is rendered or written."""


@dataclass(frozen=True)
class ZoomActivation:
    """One click on a zoom frame.

    ``slide_number`` is the host slide's 1-based position in the deck and
    ``shape_id`` the zoom frame's shape id. ``entry`` selects one section of a
    summary zoom by index; it is required when the summary has several entries.
    """

    slide_number: int
    shape_id: int
    entry: int | None = None

    def __post_init__(self) -> None:
        for name, minimum in (("slide_number", 1), ("shape_id", 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ZoomPlaybackRefusal(f"zoom activation {name} must be an integer >= {minimum}")
        if self.entry is not None and (
            isinstance(self.entry, bool) or not isinstance(self.entry, int) or self.entry < 0
        ):
            raise ZoomPlaybackRefusal("zoom activation entry must be None or an integer >= 0")


@dataclass(frozen=True)
class ZoomNavigationStep:
    """One step of a zoom playback route.

    ``action`` is ``"show"`` (a slide is on screen), ``"zoom_in"`` or
    ``"zoom_return"``; ``slide_number`` is the slide on screen when the step ends.
    ``via`` says how a shown slide was reached: ``start``, ``advance`` (slide
    order), ``section`` (section traversal), ``zoom`` (end of a zoom-in) or
    ``return`` (the host after a return). Zoom steps carry the activation, the
    activated frame bounds on the host slide in EMU ``(x, y, cx, cy)``, the
    stored duration in milliseconds (``None`` for destination timing), and the
    destination slide that times a ``None`` duration.
    """

    action: str
    slide_number: int
    via: str = ""
    activation: ZoomActivation | None = None
    bounds: tuple[int, int, int, int] | None = None
    duration_ms: Decimal | None = None
    timing_slide_number: int | None = None


@dataclass(frozen=True)
class _Route:
    bounds: tuple[int, int, int, int]
    destinations: tuple[int, ...]
    return_to_parent: bool
    duration_ms: Decimal | None


def admit_zoom_activations(value: Any) -> tuple[ZoomActivation, ...]:
    """Return the events as a tuple, refusing open-ended or malformed sources."""
    if not isinstance(value, (tuple, list)):
        raise ZoomPlaybackRefusal(
            "zoom_activations must be a finite tuple or list of ZoomActivation events; "
            f"{type(value).__name__} is an unbounded event source"
        )
    if len(value) > MAX_ZOOM_ACTIVATIONS:
        raise ZoomPlaybackRefusal(
            f"zoom_activations holds {len(value)} events; at most "
            f"{MAX_ZOOM_ACTIVATIONS} bound one playback"
        )
    for event in value:
        if not isinstance(event, ZoomActivation):
            raise ZoomPlaybackRefusal("zoom_activations entries must be ZoomActivation")
    return tuple(value)


def plan_zoom_navigation(
    deck: DeckScene, activations: Any, *, package: Package | None = None
) -> tuple[ZoomNavigationStep, ...]:
    """Return the playback route for ``activations`` over the deck's rendered slides."""
    events = admit_zoom_activations(activations)
    if package is None:
        package = read_package(Path(deck.source))
    if package.digest != deck.source_digest:
        raise ZoomPlaybackRefusal("zoom playback source package changed since scene resolution")
    order = [slide.number for slide in deck.slides]
    if not order:
        raise ZoomPlaybackRefusal("zoom playback requires at least one rendered slide")
    index_of = {number: index for index, number in enumerate(order)}
    for event in events:
        if event.slide_number not in index_of:
            raise ZoomPlaybackRefusal(
                f"zoom activation on slide {event.slide_number} shape {event.shape_id} names "
                "a slide that is not rendered"
            )
    resolver = _Resolver(package, deck)
    steps: list[ZoomNavigationStep] = []

    def add(step: ZoomNavigationStep) -> None:
        if len(steps) >= MAX_PLAYBACK_STEPS:
            raise ZoomPlaybackRefusal(
                f"zoom playback exceeds {MAX_PLAYBACK_STEPS} steps; the events form an "
                "unbounded event cycle"
            )
        steps.append(step)

    cursor = 0
    position = 0
    via = "start"
    while position < len(order):
        host = order[position]
        add(ZoomNavigationStep("show", host, via))
        jumped = False
        while cursor < len(events) and events[cursor].slide_number == host:
            event = events[cursor]
            cursor += 1
            route = resolver.route(event)
            first = route.destinations[0]
            zoom = {
                "activation": event,
                "bounds": route.bounds,
                "duration_ms": route.duration_ms,
                "timing_slide_number": first,
            }
            add(ZoomNavigationStep("zoom_in", first, **zoom))
            if not route.return_to_parent:
                position, via, jumped = index_of[first], "zoom", True
                break
            for offset, destination in enumerate(route.destinations):
                add(ZoomNavigationStep("show", destination, "section" if offset else "zoom"))
                pending = events[cursor] if cursor < len(events) else None
                if pending is not None and pending.slide_number == destination != host:
                    raise ZoomPlaybackRefusal(
                        f"zoom activation on slide {destination} fires inside the returning "
                        f"zoom from slide {host} shape {event.shape_id}; nested zoom "
                        "navigation is unsupported"
                    )
            add(ZoomNavigationStep("zoom_return", host, **zoom))
            add(ZoomNavigationStep("show", host, "return"))
        if not jumped:
            position += 1
            via = "advance"
    if cursor < len(events):
        event = events[cursor]
        raise ZoomPlaybackRefusal(
            f"zoom activation on slide {event.slide_number} shape {event.shape_id} is never "
            "reached: events must follow playback order on rendered slides"
        )
    return tuple(steps)


class _Resolver:
    def __init__(self, package: Package, deck: DeckScene) -> None:
        self.package = package
        self.deck = deck
        self.rendered = {slide.part: slide.number for slide in deck.slides}
        self.parts = {slide.number: slide.part for slide in deck.slides}
        self.presentation = package.xml(_PRESENTATION)
        relationships = {
            relationship.identifier: resolve_target(_PRESENTATION, relationship.target)
            for relationship in package.part_rels(_PRESENTATION)
            if not relationship.external
        }
        self.slide_parts: dict[str, str] = {}
        listing = self.presentation.find(f"{{{P_NS}}}sldIdLst")
        for entry in [] if listing is None else listing.findall(f"{{{P_NS}}}sldId"):
            part = relationships.get(entry.get(f"{{{R_NS}}}id", ""))
            if part is not None and entry.get("id"):
                self.slide_parts[entry.get("id", "")] = part

    def route(self, event: ZoomActivation) -> _Route:
        label = f"zoom activation on slide {event.slide_number} shape {event.shape_id}"
        part = self.parts[event.slide_number]
        root, _spans = _parse(self.package.read(part))
        kind, container, nodes = _select(root, event.shape_id)
        frame = _read(kind, container, nodes)
        bounds = _frame_bounds(root, event.shape_id, label)
        index = self._entry(frame, event, label)
        if kind == "summary":
            bounds = _entry_bounds(bounds, _properties(kind, nodes[index]), label)
        obj = frame.objects[index]
        if kind == "slide":
            destinations: tuple[int, ...] = (self._slide(obj.target, label),)
        else:
            destinations = self._section(obj.target, label)
        return _Route(bounds, destinations, obj.return_to_parent, obj.transition_duration)

    @staticmethod
    def _entry(frame: ZoomFrame, event: ZoomActivation, label: str) -> int:
        if frame.kind != "summary":
            if event.entry not in (None, 0):
                raise ZoomPlaybackRefusal(f"{label}: only summary zooms have entries")
            return 0
        if event.entry is None:
            if len(frame.objects) != 1:
                raise ZoomPlaybackRefusal(
                    f"{label}: summary zoom has {len(frame.objects)} sections; name the entry "
                    "to resolve the ambiguous composite mapping"
                )
            return 0
        if event.entry >= len(frame.objects):
            raise ZoomPlaybackRefusal(
                f"{label}: summary zoom has no entry {event.entry} ({len(frame.objects)} sections)"
            )
        return event.entry

    def _slide(self, slide_id: str, label: str) -> int:
        part = self.slide_parts.get(slide_id.strip())
        if part is None:
            raise ZoomTargetError(f"{label} targets missing slide id {slide_id}")
        number = self.rendered.get(part)
        if number is None:
            raise ZoomTargetError(
                f"{label} targets slide id {slide_id}, which is not rendered; hidden "
                "destinations require show_hidden_slides=True"
            )
        return number

    def _section(self, section_id: str, label: str) -> tuple[int, ...]:
        wanted = section_id.strip().upper()
        sections = read_sections_from_element(self.presentation)
        section = next((item for item in sections if item.id.strip().upper() == wanted), None)
        if section is None:
            raise ZoomTargetError(f"{label} targets missing section {section_id}")
        members = {str(slide_id) for slide_id in section.slide_ids}
        numbers = tuple(
            self.rendered[part]
            for slide_id, part in self.slide_parts.items()
            if slide_id in members and part in self.rendered
        )
        if not numbers:
            raise ZoomTargetError(f"{label} targets section {section_id} with no rendered slides")
        return tuple(sorted(numbers))


def _integer(element: ET.Element | None, name: str, label: str) -> int:
    raw = None if element is None else element.get(name)
    if raw is None or not raw.lstrip("-").isdigit():
        raise ZoomPlaybackRefusal(f"{label}: zoom frame placement {name!r} is missing or invalid")
    return int(raw)


def _frame_bounds(root: ET.Element, shape_id: int, label: str) -> tuple[int, int, int, int]:
    parents = {child: parent for parent in root.iter() for child in parent}
    for alternate in root.iter(f"{{{MC_NS}}}AlternateContent"):
        frame = alternate.find(f"{{{MC_NS}}}Choice/{{{P_NS}}}graphicFrame")
        identity = None if frame is None else frame.find(f".//{{{P_NS}}}cNvPr")
        if identity is None or identity.get("id") != str(shape_id):
            continue
        parent = parents.get(alternate)
        while parent is not None:
            if parent.tag == f"{{{P_NS}}}grpSp":
                raise ZoomPlaybackRefusal(
                    f"{label}: grouped zoom frames are an ambiguous composite mapping for playback"
                )
            parent = parents.get(parent)
        transform = frame.find(f"{{{P_NS}}}xfrm")
        if transform is None:
            raise ZoomPlaybackRefusal(f"{label}: zoom frame has no placement")
        return _placement(transform, label)
    raise ZoomPlaybackRefusal(f"{label}: zoom frame placement is unavailable")


def _placement(transform: ET.Element, label: str) -> tuple[int, int, int, int]:
    if transform.get("rot", "0") != "0" or any(
        transform.get(flip, "0") not in ("0", "false") for flip in ("flipH", "flipV")
    ):
        raise ZoomPlaybackRefusal(
            f"{label}: rotated or flipped zoom frames are an ambiguous composite mapping"
        )
    offset = transform.find(f"{{{A_NS}}}off")
    extent = transform.find(f"{{{A_NS}}}ext")
    bounds = (
        _integer(offset, "x", label),
        _integer(offset, "y", label),
        _integer(extent, "cx", label),
        _integer(extent, "cy", label),
    )
    if bounds[2] <= 0 or bounds[3] <= 0:
        raise ZoomPlaybackRefusal(f"{label}: zoom frame extent must be positive")
    return bounds


def _entry_bounds(
    frame: tuple[int, int, int, int], properties: ET.Element, label: str
) -> tuple[int, int, int, int]:
    transform = properties.find(f"{{{P166_NS}}}spPr/{{{A_NS}}}xfrm")
    if transform is None:
        raise ZoomPlaybackRefusal(
            f"{label}: summary entry has no placement inside its frame; ambiguous composite mapping"
        )
    x, y, cx, cy = _placement(transform, label)
    return frame[0] + x, frame[1] + y, cx, cy


def zoom_frame(
    host: Any,
    destination: Any,
    bounds: tuple[float, float, float, float],
    progress: float,
    Image: Any,
) -> Any:
    """Composite one zoom frame: ``progress`` 0 is the host, 1 the destination.

    ``bounds`` are the frame's pixel ``(x, y, width, height)`` on the host. The
    viewport moves linearly from the whole host to those bounds while the
    destination fades in over the frame's projected rectangle.
    """
    width, height = host.size
    if progress <= 0:
        return host.copy()
    x, y, w, h = bounds
    left, top = x * progress, y * progress
    right = width + (x + w - width) * progress
    bottom = height + (y + h - height) * progress
    if progress >= 1:
        view = Image.new(host.mode, host.size)
    else:
        view = host.transform(
            (width, height),
            Image.Transform.EXTENT,
            (left, top, right, bottom),
            Image.Resampling.BILINEAR,
        )
    scale_x, scale_y = width / (right - left), height / (bottom - top)
    box = (
        round((x - left) * scale_x),
        round((y - top) * scale_y),
        round((x + w - left) * scale_x),
        round((y + h - top) * scale_y),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return view
    incoming = destination.resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.BILINEAR)
    clip = (max(0, box[0]), max(0, box[1]), min(width, box[2]), min(height, box[3]))
    if clip[2] <= clip[0] or clip[3] <= clip[1]:
        return view
    incoming = incoming.crop(
        (clip[0] - box[0], clip[1] - box[1], clip[2] - box[0], clip[3] - box[1])
    )
    if progress < 1:
        incoming = Image.blend(view.crop(clip), incoming, progress)
    view.paste(incoming, clip[:2])
    return view


__all__ = [
    "MAX_PLAYBACK_STEPS",
    "MAX_ZOOM_ACTIVATIONS",
    "ZoomActivation",
    "ZoomNavigationStep",
    "ZoomPlaybackRefusal",
    "admit_zoom_activations",
    "plan_zoom_navigation",
    "zoom_frame",
]
