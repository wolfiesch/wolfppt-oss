"""Slide selection through the presentation's existing save transaction.

Use ``set_slide_range(presentation, (start, end))`` for 1-based inclusive bounds,
``set_slide_range(presentation, None)`` for all slides, and ``get_slide_range``
for the queued or saved range (custom shows are refused as numeric ranges).
Select a live custom show with ``presentation.slide_show.custom_show``; assign
None to select all slides. Configure modes, looping, narration and animation
with the same settings facade. Save to publish the mutually exclusive choice
and sibling settings together. Playback setup does not filter static exports.

ECMA-376 CT_ShowProperties: EG_ShowType, EG_SlideList (sldAll / sldRg / custShow),
penClr, extLst. Untouched package parts and unrelated show children are retained.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .package_parts import P_NS, R_NS, open_package_source
from .presentation_slides import (
    _PRES_PROPS_CONTENT_TYPE,
    _apply_show_edits,
    _resolve_pres_props,
    _show_child,
)
from .presentation_tags import LifecycleRefusal, add_part
from .slide_metadata import presentation_partname
from .xml_helpers import ooxml_namespace, ooxml_path

if TYPE_CHECKING:
    from .custom_shows import CustomShow


class SlideshowSettingsRefusal(LifecycleRefusal):
    """A slide selection cannot be represented or preserved safely."""


def _bounds(presentation: Any, value: Any) -> tuple[int, int] | None:
    if presentation._disposed:
        raise RuntimeError("presentation is disposed")
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != 2 or any(type(n) is not int for n in value):
        raise SlideshowSettingsRefusal("slide range requires an (int, int) tuple or None")
    start, end = value
    if not 1 <= start <= end <= len(presentation.slides):
        raise SlideshowSettingsRefusal(
            f"slide range must satisfy 1 <= start <= end <= {len(presentation.slides)}, got {value}"
        )
    return value


def _selection(show: ET.Element | None) -> tuple[str, ET.Element] | None:
    if show is None:
        return None
    try:
        choices = [
            (name, child)
            for name in ("sldAll", "sldRg", "custShow")
            if (child := _show_child(show, name)) is not None
        ]
    except LifecycleRefusal as exc:
        raise SlideshowSettingsRefusal(str(exc)) from exc
    if len(choices) > 1:
        raise SlideshowSettingsRefusal("ambiguous slide selection in showPr")
    return choices[0] if choices else None


def _pending(presentation: Any) -> _SlideSelectionEdit | None:
    view = presentation._lifecycle_view_state
    if view is None:
        return None
    return next(
        (op for op in view.pending_operations() if isinstance(op, _SlideSelectionEdit)), None
    )


def _show_id(raw: str | None) -> int:
    if raw is None or not raw.isascii() or not raw.isdecimal():
        raise SlideshowSettingsRefusal("invalid stored custom show id")
    try:
        value = int(raw)
    except ValueError as exc:
        raise SlideshowSettingsRefusal("invalid stored custom show id") from exc
    if not 1 <= value <= 0xFFFFFFFF:
        raise SlideshowSettingsRefusal("invalid stored custom show id")
    return value


def _stored_selection(presentation: Any, *, validate_custom: bool = True) -> tuple[str, Any]:
    if presentation._disposed:
        raise RuntimeError("presentation is disposed")
    source = presentation._source_path
    with open_package_source(source) as package:
        roots: dict = {}
        owner = presentation_partname(source)
        try:
            _, root = _resolve_pres_props(package, owner, roots, read_only=True)
            selection = _selection(None if root is None else _show_child(root, "showPr"))
            if selection is None or selection[0] == "sldAll":
                return "sldAll", None
            kind, element = selection
            if kind == "custShow":
                if not validate_custom:
                    return kind, element.get("id")
                show_id = _show_id(element.get("id"))
                shows = _show_child(roots[owner], "custShowLst")
                matches = (
                    []
                    if shows is None
                    else [
                        child
                        for child in shows
                        if child.tag == ooxml_path(shows, f"{{{P_NS}}}custShow")
                        and _show_id(child.get("id")) == show_id
                    ]
                )
                if len(matches) != 1:
                    raise SlideshowSettingsRefusal("unknown or ambiguous stored custom show id")
                return kind, show_id
        except LifecycleRefusal as exc:
            if isinstance(exc, SlideshowSettingsRefusal):
                raise
            raise SlideshowSettingsRefusal(str(exc)) from exc
    try:
        bounds = (int(element.get("st", "")), int(element.get("end", "")))
    except ValueError as exc:
        raise SlideshowSettingsRefusal("invalid stored slide range bounds") from exc
    return kind, _bounds(presentation, bounds)


def _live_show(presentation: Any, show: Any) -> CustomShow:
    from .custom_shows import CustomShow, CustomShowRefusal

    if presentation._disposed:
        raise RuntimeError("presentation is disposed")
    if not isinstance(show, CustomShow) or show._collection._presentation is not presentation:
        raise SlideshowSettingsRefusal(
            "custom show belongs to another presentation or is not a show"
        )
    try:
        matches = [candidate for candidate in presentation.custom_shows if candidate.id == show.id]
    except CustomShowRefusal as exc:
        raise SlideshowSettingsRefusal(str(exc)) from exc
    if len(matches) != 1 or matches[0] is not show:
        raise SlideshowSettingsRefusal("custom show is deleted or its id is ambiguous")
    _show_id(str(show.id))
    return show


def _current_selection(presentation: Any, *, resolve_custom: bool = True) -> tuple[str, Any]:
    pending = _pending(presentation)
    if pending is not None:
        pending.validate()
        return pending.kind, pending.value
    kind, value = _stored_selection(presentation, validate_custom=resolve_custom)
    if kind == "custShow" and resolve_custom:
        from .custom_shows import CustomShowRefusal

        try:
            matches = [show for show in presentation.custom_shows if show.id == value]
        except CustomShowRefusal as exc:
            raise SlideshowSettingsRefusal(str(exc)) from exc
        if len(matches) != 1:
            raise SlideshowSettingsRefusal("selected custom show is deleted or its id is ambiguous")
        value = _live_show(presentation, matches[0])
    return kind, value


def get_custom_show(presentation: Any) -> CustomShow | None:
    """Read the live selected show, or None for all slides or a numeric range."""
    kind, value = _current_selection(presentation)
    return value if kind == "custShow" else None


def get_slide_range(presentation: Any) -> tuple[int, int] | None:
    """Read queued or stored inclusive bounds; refuse custom-show selections."""
    kind, value = _current_selection(presentation, resolve_custom=False)
    if kind == "custShow":
        raise SlideshowSettingsRefusal("custom show selection is not a slide range")
    return value if kind == "sldRg" else None


@dataclass(frozen=True, eq=False)
class _SlideSelectionEdit:
    presentation: Any
    kind: str
    value: Any

    def validate(self) -> None:
        if self.kind == "custShow":
            _live_show(self.presentation, self.value)
        else:
            _bounds(self.presentation, self.value)

    def apply(self, package: Any, roots: dict, source: str) -> None:
        self.validate()
        part, root = _resolve_pres_props(package, source, roots)
        if root is None:
            owner = roots[source]
            root = ET.Element(f"{{{ooxml_namespace(owner, P_NS)}}}presentationPr")
            part, _ = add_part(
                package,
                roots,
                source,
                "ppt/presProps",
                ooxml_namespace(owner, R_NS) + "/presProps",
                _PRES_PROPS_CONTENT_TYPE,
                root,
            )
        _apply_show_edits(root, {})
        show = _show_child(root, "showPr")
        selection = _selection(show)
        kind = self.kind
        if selection is not None and selection[0] == kind:
            element = selection[1]
        else:
            if selection is not None:
                show.remove(selection[1])
            element = ET.Element(ooxml_path(show, f"{{{P_NS}}}{kind}"))
            successors = {ooxml_path(show, f"{{{P_NS}}}{local}") for local in ("penClr", "extLst")}
            show.insert(
                next((i for i, child in enumerate(show) if child.tag in successors), len(show)),
                element,
            )
        if kind == "sldRg":
            element.set("st", str(self.value[0]))
            element.set("end", str(self.value[1]))
        elif kind == "custShow":
            element.set("id", str(self.value.id))
        roots[part] = root


def set_slide_range(presentation: Any, bounds: tuple[int, int] | None) -> None:
    """Queue inclusive slide bounds or all slides; publish with Presentation.save.

    An explicit selection replaces a stored custom-show selection. Validate
    before changing the queue, and again before save if slide count changed.
    A failed save retains the operation for retry. Repeated calls replace the
    queued range rather than appending conflicting selections.
    """
    normalized = _bounds(presentation, bounds)
    _queue_selection(
        presentation,
        "sldAll" if normalized is None else "sldRg",
        normalized,
        validate_custom=False,
    )


def set_custom_show(presentation: Any, show: CustomShow | None) -> None:
    """Select a live same-presentation show, or all slides with None.

    Validate before replacing queued selection; save failures retain it for retry.
    """
    if show is not None:
        _live_show(presentation, show)
    _queue_selection(presentation, "sldAll" if show is None else "custShow", show)


def _queue_selection(
    presentation: Any, kind: str, value: Any, *, validate_custom: bool = True
) -> None:
    # Validate the original graph even when replacing a previously queued choice.
    # A show removed in memory can be repaired by choosing all slides or a range.
    _stored_selection(presentation, validate_custom=validate_custom)
    view = presentation.view_state
    pending = _pending(presentation)
    operation = _SlideSelectionEdit(presentation, kind, value)
    if pending is None:
        view.stage_package_operation(operation)
    else:
        view.replace_pending_operation(pending, operation)
