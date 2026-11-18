"""Shape lock protection metadata facade and typed proxy for DrawingML / PresentationML.

Read and set family-specific flags through ``Shape.locks``. Set
``Presentation.enforce_shape_locks = True`` to refuse operation-relevant locked
edits before mutation. The default remains metadata-only editing. ``no_select``
and ``no_drilldown`` remain metadata, with no selection or drilldown behavior.
No claim is made about enforcement by a particular desktop editor.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .package_parts import package_xml_element as _package_xml_element
from .shape_edit_refs import shape_edit_ref as _shape_edit_ref
from .shape_xml import (
    _shape_xml_element,
)
from .shape_xml import (
    parse_ooxml_bool as _parse_ooxml_bool,
)
from .xml_helpers import find_ooxml

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


class ShapeLockRefusal(ValueError):
    """Base exception for shape lock lifecycle refusals."""


class ShapeLockUnsupportedError(ShapeLockRefusal, AttributeError):
    """Raised when a lock property or operation is unsupported for the shape kind or master."""


class ShapeLockStaleTargetError(ShapeLockRefusal):
    """Raised when operating on a stale, deleted, or detached shape target."""


class ShapeLockValueError(ShapeLockRefusal, TypeError):
    """Refuse malformed lock flags before queueing edits or writing a package.

    Catch ``ShapeLockRefusal`` for all lock refusals, or ``TypeError`` for
    compatibility with strict-bool callers.
    """


class ShapeLockedEditError(ShapeLockRefusal):
    """An edit refused by a set lock while ``Presentation.enforce_shape_locks`` is True.

    Raised before any facade state changes or any edit is queued. ``lock`` names
    the lock property, ``shape_name`` the refusing shape and ``operation`` the edit.
    """

    def __init__(self, shape_name: str, lock: str, operation: str) -> None:
        super().__init__(f"shape {shape_name!r}: {operation} refused by the {lock} lock")
        self.shape_name = shape_name
        self.lock = lock
        self.operation = operation


LOCK_PROPERTY_TO_XML_ATTR: dict[str, str] = {
    "no_move": "noMove",
    "no_resize": "noResize",
    "no_rotate": "noRot",
    "no_select": "noSelect",
    "no_group": "noGrp",
    "no_ungroup": "noUngrp",
    "no_change_aspect": "noChangeAspect",
    "no_edit_points": "noEditPoints",
    "no_adjust_handles": "noAdjustHandles",
    "no_change_shape_type": "noChangeShapeType",
    "no_text_edit": "noTextEdit",
    "no_crop": "noCrop",
    "no_change_arrowheads": "noChangeArrowheads",
    "no_drilldown": "noDrilldown",
}

XML_ATTR_TO_LOCK_PROPERTY: dict[str, str] = {v: k for k, v in LOCK_PROPERTY_TO_XML_ATTR.items()}

_SHAPE_LOCK_PROPERTIES = frozenset(
    {
        "no_move",
        "no_resize",
        "no_rotate",
        "no_select",
        "no_group",
        "no_change_aspect",
        "no_edit_points",
        "no_adjust_handles",
        "no_change_arrowheads",
        "no_change_shape_type",
        "no_text_edit",
    }
)

_PICTURE_LOCK_PROPERTIES = frozenset(
    {
        "no_move",
        "no_resize",
        "no_rotate",
        "no_select",
        "no_group",
        "no_change_aspect",
        "no_edit_points",
        "no_adjust_handles",
        "no_change_arrowheads",
        "no_change_shape_type",
        "no_crop",
    }
)

_CONNECTOR_LOCK_PROPERTIES = frozenset(
    {
        "no_move",
        "no_resize",
        "no_rotate",
        "no_select",
        "no_group",
        "no_change_aspect",
        "no_edit_points",
        "no_adjust_handles",
        "no_change_arrowheads",
        "no_change_shape_type",
    }
)

_GROUP_LOCK_PROPERTIES = frozenset(
    {
        "no_move",
        "no_resize",
        "no_rotate",
        "no_select",
        "no_group",
        "no_ungroup",
        "no_change_aspect",
    }
)

_GRAPHIC_FRAME_LOCK_PROPERTIES = frozenset(
    {
        "no_move",
        "no_resize",
        "no_select",
        "no_group",
        "no_change_aspect",
        "no_drilldown",
    }
)

VALID_LOCK_PROPERTIES_BY_KIND: dict[str, frozenset[str]] = {
    "shape": _SHAPE_LOCK_PROPERTIES,
    "freeform": _SHAPE_LOCK_PROPERTIES,
    "text_box": _SHAPE_LOCK_PROPERTIES,
    "picture": _PICTURE_LOCK_PROPERTIES,
    "connector": _CONNECTOR_LOCK_PROPERTIES,
    "group": _GROUP_LOCK_PROPERTIES,
    "graphic_frame": _GRAPHIC_FRAME_LOCK_PROPERTIES,
}

LOCK_TAG_BY_KIND: dict[str, str] = {
    "shape": f"{{{A_NS}}}spLocks",
    "freeform": f"{{{A_NS}}}spLocks",
    "text_box": f"{{{A_NS}}}spLocks",
    "picture": f"{{{A_NS}}}picLocks",
    "connector": f"{{{A_NS}}}cxnSpLocks",
    "group": f"{{{A_NS}}}grpSpLocks",
    "graphic_frame": f"{{{A_NS}}}graphicFrameLocks",
}

NON_VISUAL_TAG_BY_KIND: dict[str, str] = {
    "shape": f"{{{P_NS}}}cNvSpPr",
    "freeform": f"{{{P_NS}}}cNvSpPr",
    "text_box": f"{{{P_NS}}}cNvSpPr",
    "picture": f"{{{P_NS}}}cNvPicPr",
    "connector": f"{{{P_NS}}}cNvCxnSpPr",
    "group": f"{{{P_NS}}}cNvGrpSpPr",
    "graphic_frame": f"{{{P_NS}}}cNvGraphicFramePr",
}

NV_CONTAINER_TAG_BY_KIND: dict[str, str] = {
    "shape": f"{{{P_NS}}}nvSpPr",
    "freeform": f"{{{P_NS}}}nvSpPr",
    "text_box": f"{{{P_NS}}}nvSpPr",
    "picture": f"{{{P_NS}}}nvPicPr",
    "connector": f"{{{P_NS}}}nvCxnSpPr",
    "group": f"{{{P_NS}}}nvGrpSpPr",
    "graphic_frame": f"{{{P_NS}}}nvGraphicFramePr",
}


def _shape_lock_kind(shape: Any) -> str:
    payload = getattr(shape, "_payload", None)
    if not isinstance(payload, dict):
        raise TypeError("expected a Shape instance with internal payload")
    kind = payload.get("kind")
    if not isinstance(kind, str):
        raise TypeError("shape payload is missing a valid kind")
    return kind


def _validate_shape_lock_target(shape: Any, *, for_mutation: bool = False) -> None:
    if shape is None:
        raise TypeError("shape cannot be None")
    payload = getattr(shape, "_payload", None)
    if not isinstance(payload, dict):
        raise TypeError("expected a Shape instance with internal payload")

    kind = payload.get("kind")
    if kind not in VALID_LOCK_PROPERTIES_BY_KIND:
        raise ShapeLockUnsupportedError(f"shape kind {kind!r} does not support shape locks")

    if hasattr(shape, "_master"):
        if for_mutation:
            raise ShapeLockUnsupportedError("master shape locks cannot be mutated")
        return

    if payload.get("_deleted") or getattr(shape, "_deleted", False):
        raise ShapeLockStaleTargetError("cannot edit or read locks of a deleted shape")
    if payload.get("_stale"):
        raise ShapeLockStaleTargetError("cannot edit or read locks of a stale shape")

    slide = getattr(shape, "_slide", None)
    if slide is None:
        raise ShapeLockStaleTargetError("shape is detached from any slide")
    if getattr(slide, "_deleted", False):
        raise ShapeLockStaleTargetError("cannot edit or read locks on a deleted slide")

    prs = getattr(slide, "_presentation", None)
    if prs is not None:
        slides = getattr(prs, "_slides", None)
        if slides is not None and slide not in slides:
            raise ShapeLockStaleTargetError("cannot edit or read locks on a deleted slide")
        slide_deletions = getattr(prs, "_slide_deletions", None)
        if slide_deletions and getattr(slide, "partname", None) in slide_deletions:
            raise ShapeLockStaleTargetError("cannot edit or read locks on a deleted slide")
        shape_deletes = getattr(prs, "_shape_deletes", None)
        shape_index = getattr(shape, "_index", None)
        slide_index = getattr(slide, "_index", None)
        if (
            shape_deletes
            and slide_index is not None
            and shape_index is not None
            and (slide_index, shape_index) in shape_deletes
        ):
            raise ShapeLockStaleTargetError("cannot edit or read locks of a deleted shape")
        group_child_deletes = getattr(prs, "_group_child_shape_deletes", None)
        if (
            group_child_deletes
            and slide_index is not None
            and shape_index is not None
            and (slide_index, shape_index) in group_child_deletes
        ):
            raise ShapeLockStaleTargetError("cannot edit or read locks of a deleted shape")

    shapes_col = getattr(slide, "_shapes", None)
    if shapes_col is not None and not payload.get("_group_child") and shape not in shapes_col:
        shape_id = getattr(shape, "shape_id", None)
        raise ShapeLockStaleTargetError(
            f"stale shape target: shape {shape_id} is no longer present in slide shapes"
        )


def _read_shape_lock(shape: Any, prop_name: str) -> bool:
    _validate_shape_lock_target(shape, for_mutation=False)
    kind = _shape_lock_kind(shape)
    valid_props = VALID_LOCK_PROPERTIES_BY_KIND.get(kind, frozenset())
    if prop_name not in valid_props:
        raise ShapeLockUnsupportedError(
            f"property {prop_name!r} is not supported for {kind} shapes"
        )

    # 1. Check pending edits in presentation edit queue:
    slide = getattr(shape, "_slide", None)
    prs = getattr(slide, "_presentation", None) if slide else None
    if prs is not None:
        shape_lock_edits = getattr(prs, "_shape_lock_edits", None)
        if isinstance(shape_lock_edits, dict):
            key = (shape._slide._index, _shape_edit_ref(shape))
            queued = shape_lock_edits.get(key)
            if queued is not None and prop_name in queued:
                return bool(queued[prop_name])

    # 2. Check cached locks dict in payload:
    payload_locks = shape._payload.get("locks")
    if isinstance(payload_locks, dict) and prop_name in payload_locks:
        return bool(payload_locks[prop_name])

    # 3. Check legitimate unsaved defaults:
    owner_part = getattr(slide, "partname", None) or (
        getattr(shape._master, "partname", None) if hasattr(shape, "_master") else None
    )
    payload = shape._payload
    is_unsaved = (
        payload.get("_pending_shape")
        or payload.get("_pending_group_child")
        or payload.get("_pending_creation")
        or not owner_part
    )
    if is_unsaved:
        return False

    # 4. Read from package XML:
    xml_attr = LOCK_PROPERTY_TO_XML_ATTR[prop_name]
    if hasattr(shape, "_master"):
        pkg_path = shape._master._presentation.path
        partname = shape._master.partname
    else:
        pkg_path = shape._slide._presentation.path
        partname = shape._slide.partname

    root = _package_xml_element(pkg_path, partname)
    try:
        shape_element = _shape_xml_element(root._element, shape._payload)
    except AttributeError as exc:
        raise ShapeLockStaleTargetError(f"shape XML element is unavailable: {exc}") from exc

    nv_tag = NV_CONTAINER_TAG_BY_KIND.get(kind)
    cnv_tag = NON_VISUAL_TAG_BY_KIND.get(kind)
    lock_tag = LOCK_TAG_BY_KIND.get(kind)
    if nv_tag is None or cnv_tag is None or lock_tag is None:
        return False

    nv = find_ooxml(shape_element, f"./{nv_tag}")
    if nv is None:
        return False
    cnv = find_ooxml(nv, f"./{cnv_tag}")
    if cnv is None:
        return False
    lock_elem = find_ooxml(cnv, f"./{lock_tag}")
    if lock_elem is None:
        return False
    raw = lock_elem.attrib.get(xml_attr)
    if raw is None:
        return False
    val = _parse_ooxml_bool(raw)
    if "locks" not in shape._payload or not isinstance(shape._payload["locks"], dict):
        shape._payload["locks"] = {}
    shape._payload["locks"][prop_name] = val
    return val


def _write_shape_lock(shape: Any, prop_name: str, value: bool) -> None:
    _validate_shape_lock_target(shape, for_mutation=True)
    kind = _shape_lock_kind(shape)
    valid_props = VALID_LOCK_PROPERTIES_BY_KIND.get(kind, frozenset())
    if prop_name not in valid_props:
        raise ShapeLockUnsupportedError(
            f"property {prop_name!r} is not supported for {kind} shapes"
        )
    if type(value) is not bool:
        raise ShapeLockValueError(f"{prop_name} must be a bool, got {type(value).__name__}")

    current = _read_shape_lock(shape, prop_name)
    if current == value:
        return

    # Queue edit in presentation FIRST:
    prs = shape._slide._presentation
    prs._queue_shape_lock(
        shape._slide._index,
        _shape_edit_ref(shape),
        prop_name,
        value,
    )

    # Update payload cache only AFTER successful queuing:
    if "locks" not in shape._payload or not isinstance(shape._payload["locks"], dict):
        shape._payload["locks"] = {}
    shape._payload["locks"][prop_name] = value


def shape_locks_enforced(shape: Any) -> bool:
    """Whether the presentation owning ``shape`` opted into lock enforcement."""
    owner = getattr(shape, "_slide", None) or getattr(shape, "_master", None)
    presentation = getattr(owner, "_presentation", None)
    return getattr(presentation, "enforce_shape_locks", False) is True


def check_shape_locks(shape: Any, operation: str, *properties: str) -> None:
    """Refuse ``operation`` when one of ``properties`` is set and enforcement is on.

    Shape kinds without lock support carry no flags to honour. Flags a kind does not
    support are ignored, so callers name every flag relevant to the operation.
    Notes-slide shapes are outside ``Shape.locks`` and stay unchecked.
    """
    if not properties or not shape_locks_enforced(shape):
        return
    if getattr(getattr(shape, "_slide", None), "_is_notes_slide", False):
        return
    payload = getattr(shape, "_payload", None)
    kind = payload.get("kind") if isinstance(payload, dict) else None
    supported = VALID_LOCK_PROPERTIES_BY_KIND.get(kind)
    if supported is None:
        return
    _validate_shape_lock_target(shape)
    for prop in properties:
        if prop in supported and _read_shape_lock(shape, prop):
            raise ShapeLockedEditError(str(payload.get("name") or ""), prop, operation)


def check_text_edit_lock(shape: Any) -> None:
    """Refuse a change to the characters, runs or paragraphs of ``shape``'s text."""
    check_shape_locks(shape, "text edit", "no_text_edit")


def geometry_lock_properties(current: Mapping[str, int], new: Mapping[str, int]) -> list[str]:
    """Lock properties a change from ``current`` to ``new`` (x, y, cx, cy) touches."""
    flags = []
    if new["x"] != current["x"] or new["y"] != current["y"]:
        flags.append("no_move")
    if new["cx"] != current["cx"] or new["cy"] != current["cy"]:
        flags.append("no_resize")
        if new["cx"] * current["cy"] != new["cy"] * current["cx"]:
            flags.append("no_change_aspect")
    return flags


def check_shape_geometry_locks(shape: Any, geometry: Mapping[str, int]) -> None:
    """Refuse a move, resize or aspect change of ``shape`` to ``geometry``."""
    if not shape_locks_enforced(shape):
        return
    from .shape_payloads import _shape_transform

    flags = geometry_lock_properties(_shape_transform(shape), geometry)
    check_shape_locks(shape, "geometry edit", *flags)


class ShapeLocks:
    """Strict-bool lock proxy; opt in through ``Presentation.enforce_shape_locks``."""

    def __init__(self, shape: Any) -> None:
        _validate_shape_lock_target(shape, for_mutation=False)
        self._shape = shape

    def _kind(self) -> str:
        return _shape_lock_kind(self._shape)

    def _supported_properties(self) -> frozenset[str]:
        return VALID_LOCK_PROPERTIES_BY_KIND.get(self._kind(), frozenset())

    @property
    def no_move(self) -> bool:
        return _read_shape_lock(self._shape, "no_move")

    @no_move.setter
    def no_move(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_move", value)

    @property
    def no_resize(self) -> bool:
        return _read_shape_lock(self._shape, "no_resize")

    @no_resize.setter
    def no_resize(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_resize", value)

    @property
    def no_rotate(self) -> bool:
        return _read_shape_lock(self._shape, "no_rotate")

    @no_rotate.setter
    def no_rotate(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_rotate", value)

    @property
    def no_select(self) -> bool:
        return _read_shape_lock(self._shape, "no_select")

    @no_select.setter
    def no_select(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_select", value)

    @property
    def no_group(self) -> bool:
        return _read_shape_lock(self._shape, "no_group")

    @no_group.setter
    def no_group(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_group", value)

    @property
    def no_ungroup(self) -> bool:
        return _read_shape_lock(self._shape, "no_ungroup")

    @no_ungroup.setter
    def no_ungroup(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_ungroup", value)

    @property
    def no_change_aspect(self) -> bool:
        return _read_shape_lock(self._shape, "no_change_aspect")

    @no_change_aspect.setter
    def no_change_aspect(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_change_aspect", value)

    @property
    def no_edit_points(self) -> bool:
        return _read_shape_lock(self._shape, "no_edit_points")

    @no_edit_points.setter
    def no_edit_points(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_edit_points", value)

    @property
    def no_adjust_handles(self) -> bool:
        return _read_shape_lock(self._shape, "no_adjust_handles")

    @no_adjust_handles.setter
    def no_adjust_handles(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_adjust_handles", value)

    @property
    def no_change_shape_type(self) -> bool:
        return _read_shape_lock(self._shape, "no_change_shape_type")

    @no_change_shape_type.setter
    def no_change_shape_type(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_change_shape_type", value)

    @property
    def no_text_edit(self) -> bool:
        return _read_shape_lock(self._shape, "no_text_edit")

    @no_text_edit.setter
    def no_text_edit(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_text_edit", value)

    @property
    def no_crop(self) -> bool:
        return _read_shape_lock(self._shape, "no_crop")

    @no_crop.setter
    def no_crop(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_crop", value)

    @property
    def no_change_arrowheads(self) -> bool:
        return _read_shape_lock(self._shape, "no_change_arrowheads")

    @no_change_arrowheads.setter
    def no_change_arrowheads(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_change_arrowheads", value)

    @property
    def no_drilldown(self) -> bool:
        """Read whether desktop UI selection within a graphic frame is disallowed."""
        return _read_shape_lock(self._shape, "no_drilldown")

    @no_drilldown.setter
    def no_drilldown(self, value: bool) -> None:
        _write_shape_lock(self._shape, "no_drilldown", value)

    def to_dict(self) -> dict[str, bool]:
        """Return dict of supported lock properties and their current boolean values."""
        return {prop: getattr(self, prop) for prop in sorted(self._supported_properties())}

    def __getattr__(self, name: str) -> Any:
        if name in LOCK_PROPERTY_TO_XML_ATTR:
            raise ShapeLockUnsupportedError(
                f"property {name!r} is not supported for {self._kind()} shapes"
            )
        raise AttributeError(f"'ShapeLocks' object has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_shape":
            super().__setattr__(name, value)
            return
        if name in LOCK_PROPERTY_TO_XML_ATTR:
            prop = getattr(type(self), name, None)
            if prop and hasattr(prop, "fset"):
                prop.fset(self, value)
                return
            raise ShapeLockUnsupportedError(
                f"property {name!r} is not supported for {self._kind()} shapes"
            )
        raise AttributeError(f"'ShapeLocks' object has no attribute {name!r}")

    def __dir__(self) -> list[str]:
        base_dir = set(super().__dir__())
        # Remove properties not supported for this specific kind:
        supported = self._supported_properties()
        all_lock_props = set(LOCK_PROPERTY_TO_XML_ATTR.keys())
        filtered = (base_dir - all_lock_props) | supported
        return sorted(filtered)

    def __repr__(self) -> str:
        kind = self._kind()
        flags = " ".join(f"{k}={v}" for k, v in self.to_dict().items())
        return f"<ShapeLocks kind={kind!r} {flags}>"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ShapeLocks):
            return self.to_dict() == other.to_dict()
        if isinstance(other, Mapping):
            return self.to_dict() == dict(other)
        return False
