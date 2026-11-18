"""Shape adjustment, placeholder, and click-action facade helpers."""

from __future__ import annotations

import posixpath
import re
from collections.abc import Sequence
from numbers import Number
from typing import Any

from .enum.action import PP_ACTION
from .enum.shapes import PlaceholderSize
from .package_parts import PackagePart, XmlElementProxy
from .part_placeholder_edits import placeholder_size, set_placeholder_size
from .shape_action_inspection import (
    SHOW_JUMP_ACTIONS,
    _shape_click_action_name,
    _shape_has_click_action,
    _shape_hyperlink_color_source,
    _shape_hyperlink_screentip,
    _shape_hyperlink_sub_address,
    _shape_show_jump_name,
)
from .shape_edit_refs import (
    ShapeEditRef,
)
from .shape_edit_refs import (
    shape_edit_ref as _shape_edit_ref,
)
from .shape_inspection import (
    _placeholder_type_value,
    _placeholder_type_xml,
    _shape_adjustment_guides,
    _shape_click_action_value,
    _shape_hyperlink_address,
    _shape_target_slide,
)
from .shape_xml import (
    HyperlinkColorSourceRefusal,
    hyperlink_color_source_member,
    hyperlink_color_source_xml,
    queued_hyperlink_address,
)
from .xml_helpers import P_NS, find_ooxml

_SLIDE_PART_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_SHOW_JUMP_BY_ACTION = {name: jump for jump, name in SHOW_JUMP_ACTIONS.items()}


class _ShowJumpAction(str):
    """Queued ``ppaction://hlinkshowjump`` click action.

    It is a plain ``str`` in the hyperlink edit queue, so queue bookkeeping keeps
    working; the writer emits it as an ``a:hlinkClick`` action with no
    relationship.
    """

    @property
    def show_jump_action(self) -> str:
        return str(self)


def _shape_action_ref(shape: Any) -> ShapeEditRef:
    return _shape_edit_ref(shape)


class AdjustmentCollection(Sequence[float]):
    """python-pptx-style adjustment handle values for an auto shape."""

    def __init__(self, shape: Any) -> None:
        self._shape = shape

    def __getitem__(self, index: int) -> float:
        return _shape_adjustment_guides(self._shape)[index][1] / 100000.0

    def __setitem__(self, index: int, value: float) -> None:
        if not isinstance(value, Number):
            raise ValueError(f"adjustment value must be numeric, got {value!r}")
        guides = _shape_adjustment_guides(self._shape)
        name, current = guides[index]
        adjusted = int(value * 100000.0)
        if current == adjusted:
            return
        from .shape_locks import check_shape_locks

        check_shape_locks(self._shape, "adjustment edit", "no_adjust_handles")
        guides[index] = (name, adjusted)
        self._shape._payload["adjustment_guides"] = list(guides)
        self._shape._slide._presentation._queue_shape_adjustments(
            self._shape._slide._index,
            _shape_action_ref(self._shape),
            guides,
        )

    def __len__(self) -> int:
        return len(_shape_adjustment_guides(self._shape))


class PlaceholderFormat:
    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def idx(self) -> int:
        raw = self._shape._payload.get("placeholder_idx")
        if raw in (None, ""):
            return 0
        return int(raw)

    @property
    def type(self) -> Any:
        return _placeholder_type_value(_placeholder_type_xml(self._shape))

    @property
    def size(self) -> PlaceholderSize:
        """Local ``p:ph/@sz`` class, default FULL; not the shape's geometry."""
        return placeholder_size(self._shape)

    @size.setter
    def size(self, value: PlaceholderSize | str | None) -> None:
        """Set or clear saved metadata; save pending edits and reacquire handles."""
        set_placeholder_size(self._shape, value)

    @property
    def element(self) -> XmlElementProxy:
        element = find_ooxml(self._shape.element._element, f".//{{{P_NS}}}ph")
        if element is None:
            raise AttributeError("placeholder XML element is unavailable")
        return XmlElementProxy(element)


class ActionSetting:
    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def action(self) -> Any:
        return _shape_click_action_value(self._shape)

    @action.setter
    def action(self, value: Any) -> None:
        requested = _click_action_request_name(value)
        if requested == "NONE":
            if _shape_has_click_action(self._shape):
                _queue_shape_hyperlink_address(self._shape, None)
            return
        if requested == _shape_click_action_name(self._shape):
            return
        if requested == "HYPERLINK":
            raise ValueError(
                "PP_ACTION.HYPERLINK needs a target address; assign "
                "click_action.hyperlink.address instead"
            )
        if requested == "NAMED_SLIDE":
            raise ValueError(
                "PP_ACTION.NAMED_SLIDE needs a target slide; assign "
                "click_action.target_slide instead"
            )
        jump = _SHOW_JUMP_BY_ACTION.get(requested)
        if jump is None:
            raise ValueError(
                f"click action PP_ACTION.{requested} is not supported; assign None or "
                "PP_ACTION.NONE to clear, or set click_action.hyperlink.address or "
                "click_action.target_slide"
            )
        _queue_shape_hyperlink_address(
            self._shape, _ShowJumpAction(f"ppaction://hlinkshowjump?jump={jump}")
        )
        # The jump is an ``a:hlinkClick`` action with no hyperlink address.
        self._shape._payload["hyperlink_address"] = None
        self._shape._payload["show_jump_action"] = requested

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @property
    def hyperlink(self) -> Hyperlink:
        return Hyperlink(self._shape)

    @property
    def target_slide(self) -> Any | None:
        return _shape_target_slide(self._shape)

    @target_slide.setter
    def target_slide(self, value: Any | None) -> None:
        if value is None:
            if self.target_slide is None and self.hyperlink.address is None:
                return
            target_index = None
            target_ref = None
        else:
            from .presentation import Slide

            if not isinstance(value, Slide):
                raise TypeError("target_slide must be a wolfppt Slide or None")
            if value._presentation is not self._shape._slide._presentation:
                raise ValueError("target_slide belongs to a different presentation")
            target_index = value._index
            if self.target_slide == value:
                return
            target_partname = _resolved_slide_partname(value)
            target_ref = posixpath.relpath(
                target_partname,
                posixpath.dirname(self._shape._slide.partname),
            )
        self._shape._payload["target_slide_index"] = target_index
        if target_index is None:
            # Removing the click action removes its color source with it.
            self._shape._payload["hyperlink_color_source_edit"] = None
        else:
            # The jump rewrite keeps saved extension entries untouched.
            self._shape._payload.pop("hyperlink_color_source_edit", None)
        self._shape._payload["hyperlink_address"] = target_ref
        self._shape._payload["show_jump_action"] = None
        # Slide-jump edits rewrite ``a:hlinkClick`` without a tooltip.
        self._shape._payload["hyperlink_screentip"] = None
        self._shape._slide._presentation._queue_shape_target_slide(
            self._shape._slide._index,
            _shape_action_ref(self._shape),
            target_index,
        )


def _resolved_slide_partname(slide: Any) -> str:
    if slide.partname:
        return slide.partname
    next_slide_number = _next_pending_slide_number(slide)
    for pending_slide in slide._presentation.slides:
        if pending_slide.partname:
            continue
        if pending_slide is slide:
            return f"ppt/slides/slide{next_slide_number}.xml"
        next_slide_number += 1
    raise ValueError("target_slide is not in this presentation")


def _next_pending_slide_number(slide: Any) -> int:
    existing_numbers = []
    for candidate in slide._presentation.slides:
        match = _SLIDE_PART_RE.match(candidate.partname)
        if match is not None:
            existing_numbers.append(int(match.group(1)))
    return max(existing_numbers, default=0) + 1


class Hyperlink:
    def __init__(self, shape: Any) -> None:
        self._shape = shape

    @property
    def address(self) -> str | None:
        return _shape_hyperlink_address(self._shape)

    @property
    def part(self) -> PackagePart:
        return self._shape.part

    @address.setter
    def address(self, value: str | None) -> None:
        address = str(value) if value else None
        if (
            address == self.address
            and _shape_target_slide(self._shape) is None
            and _shape_show_jump_name(self._shape) is None
        ):
            return
        # Retargeting a link keeps its tooltip; removing the link drops it.
        screentip = self.screentip if address is not None else None
        _queue_shape_hyperlink_address(self._shape, address, screentip)

    @property
    def screentip(self) -> str | None:
        """Tooltip shown on hover, stored as ``a:hlinkClick/@tooltip``."""
        return _shape_hyperlink_screentip(self._shape)

    @screentip.setter
    def screentip(self, value: str | None) -> None:
        screentip = None if value is None else str(value)
        if screentip == self.screentip:
            return
        if _shape_target_slide(self._shape) is not None:
            raise NotImplementedError(
                "screentip editing is not supported on slide-jump click actions; "
                "use click_action.hyperlink.address for a hyperlink with a screentip"
            )
        address = self.address
        if address is None:
            raise ValueError(
                "screentip requires a click hyperlink; assign click_action.hyperlink.address first"
            )
        _queue_shape_hyperlink_address(self._shape, address, screentip)

    @property
    def color_source(self) -> Any:
        """Where the link text takes its color, stored as ``hlinkClr/@val``.

        A ``PP_HYPERLINK_COLOR_SOURCE`` member, or ``None`` when the hyperlink
        carries no color source. A malformed saved value raises
        ``HyperlinkColorSourceRefusal``.
        """
        return hyperlink_color_source_member(_shape_hyperlink_color_source(self._shape))

    @color_source.setter
    def color_source(self, value: Any) -> None:
        requested = hyperlink_color_source_xml(value)
        if (
            _shape_target_slide(self._shape) is not None
            or _shape_show_jump_name(self._shape) is not None
        ):
            raise HyperlinkColorSourceRefusal(
                "color_source editing is not supported on slide-jump click actions; "
                "use click_action.hyperlink.address for a hyperlink with a color source"
            )
        address = self.address
        if address is None:
            raise HyperlinkColorSourceRefusal(
                "color_source requires a click hyperlink; assign click_action.hyperlink.address "
                "first"
            )
        try:
            unchanged = requested == _shape_hyperlink_color_source(self._shape)
        except HyperlinkColorSourceRefusal:
            unchanged = False  # an explicit edit replaces a malformed saved value
        if unchanged:
            return
        self._shape._payload["hyperlink_color_source_edit"] = requested
        _queue_shape_hyperlink_address(self._shape, address, self.screentip)

    @property
    def sub_address(self) -> str | None:
        """Location inside the click target.

        A jump to a slide in this presentation reports the slide target relative
        to the source slide, for example ``slide2.xml``; an external address
        reports its ``#`` fragment.
        """
        return _shape_hyperlink_sub_address(self._shape)

    @sub_address.setter
    def sub_address(self, value: str | None) -> None:
        sub_address = str(value) if value else None
        if sub_address == self.sub_address:
            return
        address = self.address
        if address is not None and _shape_target_slide(self._shape) is None:
            base = address.partition("#")[0]
            self.address = f"{base}#{sub_address}" if sub_address else base
            return
        # Without an external address the sub-address names a slide in this
        # presentation, authored as a ``ppaction://hlinksldjump`` click action.
        if getattr(self._shape._slide, "_is_notes_slide", False):
            raise NotImplementedError(
                "slide-jump sub_address is not supported on notes slide shapes"
            )
        action = ActionSetting(self._shape)
        if sub_address is None:
            action.target_slide = None
            return
        action.target_slide = _slide_for_sub_address(self._shape, sub_address)


def _slide_for_sub_address(shape: Any, sub_address: str) -> Any:
    """Resolve a slide target such as ``slide2.xml`` or ``/ppt/slides/slide2.xml``."""
    if sub_address.startswith("/"):
        wanted = posixpath.normpath(sub_address.lstrip("/"))
    else:
        source = _resolved_slide_partname(shape._slide)
        wanted = posixpath.normpath(posixpath.join(posixpath.dirname(source), sub_address))
    for slide in shape._slide._presentation.slides:
        if _resolved_slide_partname(slide) == wanted:
            return slide
    raise ValueError(f"sub_address {sub_address!r} does not name a slide in this presentation")


def _queue_shape_hyperlink_address(
    shape: Any, address: str | None, screentip: str | None = None
) -> None:
    """Queue a plain hyperlink (or, with ``None``, removal of ``a:hlinkClick``)."""
    shape._payload["hyperlink_address"] = address
    shape._payload["target_slide_index"] = None
    shape._payload["show_jump_action"] = None
    shape._payload["hyperlink_screentip"] = screentip if address is not None else None
    if address is None:
        shape._payload["hyperlink_color_source_edit"] = None
    elif isinstance(address, _ShowJumpAction):
        # The jump rewrite keeps saved extension entries untouched.
        shape._payload.pop("hyperlink_color_source_edit", None)
    color_edit = (
        (shape._payload["hyperlink_color_source_edit"],)
        if address is not None and "hyperlink_color_source_edit" in shape._payload
        else None
    )
    queued = (
        address
        if isinstance(address, _ShowJumpAction)
        else queued_hyperlink_address(address, screentip, color_edit)
    )
    if getattr(shape._slide, "_is_notes_slide", False):
        shape._slide._presentation._queue_part_shape_hyperlink(
            shape._slide.partname,
            shape._index,
            queued,
        )
    else:
        shape._slide._presentation._queue_shape_hyperlink(
            shape._slide._index,
            _shape_action_ref(shape),
            queued,
        )


def _click_action_request_name(value: Any) -> str:
    if value is None:
        return "NONE"
    if isinstance(value, PP_ACTION):
        return value.name
    if type(value).__name__ == PP_ACTION.__name__ and isinstance(value, int):
        # python-pptx PP_ACTION members carry the same integer values.
        return PP_ACTION(value).name
    raise TypeError(f"click action must be a PP_ACTION member or None, got {value!r}")
