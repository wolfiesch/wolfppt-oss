"""Semantic accessors and shape removal for notes slides and the notes master.

Readers resolve the saved package afresh, so they report the bytes a reopen would
see. A notes part that only exists as a queued edit is refused with
``NotesPageRefusal``; save first. ``remove_notes_shape`` is an immediate, atomic
package rewrite: the facade is rebased onto the result, so reacquire notes handles
afterwards. A shape that references package relationships (pictures, charts,
hyperlinks, OLE) is refused rather than leaving orphaned relationship targets.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .package_parts import open_package_source
from .presentation_save_state import _element_spans
from .render_theme import color_map_from
from .xml_helpers import find_ooxml

if TYPE_CHECKING:
    from .presentation_slides import NotesMaster, NotesSlide

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

__all__ = [
    "NotesMasterSemantics",
    "NotesPageRefusal",
    "NotesSlideSemantics",
    "NotesSlideShapeRemoval",
    "notes_color_map",
    "notes_color_map_override",
    "notes_show_master_shapes",
    "remove_notes_shape",
]


class NotesPageRefusal(ValueError):
    """A notes page read or shape removal cannot be answered or preserved safely."""


def _root(owner: NotesSlide | NotesMaster, expected: str) -> ET.Element:
    part = owner.partname.lstrip("/")
    try:
        with open_package_source(owner._presentation._source_path) as package:
            payload = package.read(part)
    except KeyError as exc:
        raise NotesPageRefusal(f"notes part {part} is not saved in the package") from exc
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise NotesPageRefusal(f"notes part {part} is not well-formed XML") from exc
    if root.tag != f"{{{P_NS}}}{expected}":
        raise NotesPageRefusal(f"notes part {part} root is not p:{expected}")
    return root


def notes_color_map(master: NotesMaster) -> dict[str, str]:
    """Slot to theme-colour mapping declared by the notes master's ``p:clrMap``."""
    mapping = color_map_from(find_ooxml(_root(master, "notesMaster"), f"{{{P_NS}}}clrMap"))
    return dict(mapping or {})


def notes_color_map_override(notes: NotesSlide) -> dict[str, str] | None:
    """The notes slide's ``a:overrideClrMapping`` slots, or ``None`` when it inherits.

    ``None`` covers an explicit ``a:masterClrMapping`` and an absent ``p:clrMapOvr``.
    """
    override = find_ooxml(_root(notes, "notes"), f"{{{P_NS}}}clrMapOvr")
    if override is None:
        return None
    explicit = find_ooxml(override, f"{{{A_NS}}}overrideClrMapping")
    if explicit is None:
        return None
    return dict(color_map_from(explicit) or {})


def notes_show_master_shapes(notes: NotesSlide) -> bool:
    """``p:notes/@showMasterSp``; true when absent."""
    raw = _root(notes, "notes").get("showMasterSp", "true")
    if raw not in {"0", "1", "false", "true"}:
        raise NotesPageRefusal(f"invalid notes showMasterSp value {raw!r}")
    return raw in {"1", "true"}


def remove_notes_shape(
    owner: NotesSlide | NotesMaster, shape: Any, collection: Sequence[Any]
) -> None:
    """Remove one top-level shape from a saved notes slide or notes master.

    Only the shape's own bytes are cut; every other byte of the part is kept.
    """
    if not any(candidate is shape for candidate in collection):
        raise ValueError(f"{shape!r} is not in this shape collection")
    if getattr(shape, "_payload", {}).get("_pending_shape"):
        raise NotesPageRefusal("an unsaved shape cannot be removed")
    shape_id = str(shape.shape_id)
    part = owner.partname.lstrip("/")
    presentation = owner._presentation
    try:
        presentation._require_saved_package("removing a notes shape")
    except (ValueError, RuntimeError) as exc:
        raise NotesPageRefusal(str(exc)) from exc

    def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
        try:
            payload = package.read(part)
        except KeyError as exc:
            raise NotesPageRefusal(f"notes part {part} is not saved in the package") from exc
        try:
            nodes = _element_spans(payload)
        except Exception as exc:  # expat.ExpatError on malformed XML
            raise NotesPageRefusal(f"notes part {part} is not well-formed XML") from exc
        tree = next(
            (
                index
                for index, node in enumerate(nodes)
                if node["tag"] == f"{{{P_NS}}}spTree"
                and node["parent"] is not None
                and nodes[node["parent"]]["tag"] == f"{{{P_NS}}}cSld"
            ),
            None,
        )
        if tree is None:
            raise NotesPageRefusal(f"notes part {part} has no shape tree")
        matches = []
        for index, node in enumerate(nodes):
            if node["parent"] != tree or node["tag"].rsplit("}", 1)[-1] in {
                "nvGrpSpPr",
                "grpSpPr",
                "extLst",
            }:
                continue
            identity = next(
                (
                    inner
                    for inner in nodes[index + 1 :]
                    if inner["start"] < node["end"] and inner["tag"] == f"{{{P_NS}}}cNvPr"
                ),
                None,
            )
            if identity is not None and identity["attrib"].get("id") == shape_id:
                matches.append((index, node))
        if len(matches) != 1:
            raise NotesPageRefusal(f"notes shape id {shape_id} is missing or ambiguous")
        index, target = matches[0]
        for inner in nodes[index:]:
            if inner["start"] >= target["end"]:
                break
            if any(key.startswith(f"{R_NS}}}") for key in inner["attrib"]):
                raise NotesPageRefusal(
                    "notes shape references package relationships and cannot be removed"
                )
        edited = payload[: target["start"]] + payload[target["end"] :]
        try:
            ET.fromstring(edited)
        except ET.ParseError as exc:
            raise NotesPageRefusal("shape removal would leave malformed XML") from exc
        return {part: edited}, set(), None

    presentation._rewrite_package("removing a notes shape", plan)
    # The facade now reads the rewritten package; keep this collection consistent
    # for callers that still hold it.
    shape._payload["_deleted"] = True
    members = getattr(collection, "_shapes", None)
    if members is not None:
        members[:] = [member for member in members if member is not shape]
    placeholders = getattr(owner, "placeholders", None)
    if placeholders is not None:
        placeholders._placeholders[:] = [
            member for member in placeholders._placeholders if member is not shape
        ]


class NotesSlideSemantics:
    """Semantic accessors mixed into ``NotesSlide``."""

    @property
    def header_footer(self) -> Any:
        """Header/footer manager of this saved notes slide."""
        from .header_footer_facade import header_footer_manager

        return header_footer_manager(self)

    @property
    def show_master_shapes(self) -> bool:
        """Whether the notes master's non-placeholder shapes show (``showMasterSp``)."""
        return notes_show_master_shapes(self)  # type: ignore[arg-type]

    @property
    def color_map_override(self) -> dict[str, str] | None:
        """``a:overrideClrMapping`` slots, or ``None`` when the master mapping applies."""
        return notes_color_map_override(self)  # type: ignore[arg-type]


class NotesMasterSemantics:
    """Semantic accessors mixed into ``NotesMaster``."""

    @property
    def header_footer(self) -> Any:
        """Header/footer manager of this saved notes master."""
        from .header_footer_facade import header_footer_manager

        return header_footer_manager(self)

    @property
    def color_map(self) -> dict[str, str]:
        """Slot to theme-colour mapping of the master's ``p:clrMap``."""
        return notes_color_map(self)  # type: ignore[arg-type]


class NotesSlideShapeRemoval:
    """``remove`` mixed into ``NotesSlideShapes``."""

    def remove(self, shape: Any) -> None:
        """Remove one saved top-level shape and rebase the presentation on the result."""
        remove_notes_shape(self._notes_slide, shape, self)  # type: ignore[attr-defined]
