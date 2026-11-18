"""Slide, layout, master, and notes facade collections."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from functools import cached_property
from operator import index as _index
from pathlib import Path
from typing import TYPE_CHECKING, Any, overload
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from .comment_edits import SlideComments
    from .custom_shows import CustomShow
    from .presentation import Presentation
    from .slide_designer_metadata import DesignerMetadata
    from .text_facade import TextFrame
    from .vml_drawings import VmlDrawing

from .background_facade import Background
from .html_import import HtmlImportMixin
from .native_read import SlideSummaryReaders
from .notes_page_semantics import NotesMasterSemantics, NotesSlideSemantics, NotesSlideShapeRemoval
from .package_parts import InMemoryPackageSource, PackagePart, XmlElementProxy
from .package_parts import (
    package_xml_element as _package_xml_element,
)
from .presentation_extension_flags import PresentationExtensionFlags
from .presentation_slide_insert import SlideInsertMixin, _require_open_presentation
from .shape_facade import (
    BaseShapePlaceholderCollection,
    MasterPlaceholderCollection,
    MasterShape,
    MasterShapeCollection,
    PlaceholderCollection,
    Shape,
    ShapeCollection,
    _notes_placeholder_basename,
    _placeholder_type_xml,
)
from .shape_inspection import _next_shape_id, _placeholder_raw_value
from .slide_metadata import (
    first_slide_master_partname as _first_slide_master_partname,
)
from .slide_metadata import (
    part_common_slide_name_from_path as _part_common_slide_name_from_path,
)
from .slide_metadata import (
    presentation_partname as _presentation_partname,
)
from .slide_metadata import (
    slide_hidden as _slide_hidden,
)
from .slide_metadata import (
    slide_metadata as _slide_metadata,
)
from .slide_metadata import (
    slide_name as _slide_name,
)
from .slide_metadata import (
    slide_notes_partname as _slide_notes_partname,
)
from .slide_metadata import (
    slide_notes_partname_for_part as _slide_notes_partname_for_part,
)
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
)
from .slide_payloads import (
    load_slide_layout_placeholder_payloads as _load_slide_layout_placeholder_payloads,
)
from .text_facade_inspection import _shape_run_count_payload

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _slide_summary_readers(presentation: Any) -> SlideSummaryReaders:
    """The presentation's slide-summary readers, created on the first lazy shape read."""
    if (readers := getattr(presentation, "_slide_summary_readers", None)) is None:
        readers = presentation._slide_summary_readers = SlideSummaryReaders()
    return readers


class SlideLayoutCollection(Sequence["SlideLayout"]):
    def __init__(
        self,
        presentation: Presentation,
        layouts: list[SlideLayout],
        partname: str | None = None,
        parent: SlideMaster | None = None,
    ) -> None:
        self._presentation = presentation
        self._layouts = layouts
        self._partname = partname
        self._parent = parent

    @overload
    def __getitem__(self, index: int) -> SlideLayout: ...

    @overload
    def __getitem__(self, index: slice) -> list[SlideLayout]: ...

    def __getitem__(self, index: int | slice) -> SlideLayout | list[SlideLayout]:
        return self._layouts[index]

    def __iter__(self) -> Iterator[SlideLayout]:
        return iter(self._layouts)

    def __len__(self) -> int:
        return len(self._layouts)

    def index(self, slide_layout: SlideLayout) -> int:
        for index, layout in enumerate(self._layouts):
            if layout is slide_layout:
                return index
        raise ValueError("layout not in this SlideLayouts collection")

    def get_by_name(self, name: str, default: SlideLayout | None = None) -> SlideLayout | None:
        for layout in self._layouts:
            if layout.name == name:
                return layout
        return default

    def add(self, name: str, *, title: bool = True, body: bool = True) -> SlideLayout:
        """Synthesize a title/body layout below this collection's slide master."""
        if self._parent is None:
            raise ValueError("create layouts through a slide master's slide_layouts collection")
        from .slide_master_facade import queue_layout_add

        payload = queue_layout_add(self._presentation, self._parent, name, title=title, body=body)
        layouts = self._presentation.slide_layouts._layouts
        layout = SlideLayout(self._presentation, len(layouts), payload)
        layout._parent = self._parent
        layouts.append(layout)
        if self._layouts is not layouts:
            self._layouts.append(layout)
        return layout

    def clone(self, source: SlideLayout, name: str) -> SlideLayout:
        """Clone a layout, importing its owning master context when foreign."""
        if self._parent is None:
            raise ValueError("clone layouts through a slide master's slide_layouts collection")
        if source._presentation is not self._presentation:
            from .slide_master_facade import _required_name, queue_master_clone

            name = _required_name(name, "layout")
            source_master = source.slide_master
            source_index = source_master.slide_layouts.index(source)
            payload = queue_master_clone(self._presentation, source_master, name)
            payload["_layout_payloads"][source_index]["name"] = name
            request = self._presentation._slide_master_authoring_requests[-1]
            payload["name"] = source_master.name
            request["name"] = source_master.name
            request["layouts"][source_index]["name"] = name
            imported_master = SlideMaster(
                self._presentation, len(self._presentation.slide_masters), payload
            )
            self._presentation.slide_masters._masters.append(imported_master)
            layouts = self._presentation.slide_layouts._layouts
            imported_layouts: list[SlideLayout] = []
            for layout_payload in payload["_layout_payloads"]:
                imported = SlideLayout(self._presentation, len(layouts), layout_payload)
                imported._parent = imported_master
                layouts.append(imported)
                imported_layouts.append(imported)
            return imported_layouts[source_index]
        from .slide_master_facade import queue_layout_clone

        payload = queue_layout_clone(self._presentation, self._parent, source, name)
        layouts = self._presentation.slide_layouts._layouts
        layout = SlideLayout(self._presentation, len(layouts), payload)
        layout._parent = self._parent
        layouts.append(layout)
        if self._layouts is not layouts:
            self._layouts.append(layout)
        return layout

    def remove(self, slide_layout: SlideLayout) -> None:
        if slide_layout.used_by_slides:
            raise ValueError("cannot remove slide-layout in use by one or more slides")
        self.index(slide_layout)
        self._layouts.remove(slide_layout)
        slide_layout._deleted = True
        self._presentation._queue_slide_layout_remove(slide_layout.partname)

    @property
    def part(self) -> PackagePart:
        partname = self._partname
        if partname is None:
            partname = _first_slide_master_partname(self._presentation.path)
        return PackagePart(
            self._presentation,
            partname,
            name="",
        )

    @property
    def parent(self) -> SlideMaster:
        if self._parent is not None:
            return self._parent
        return self._presentation.slide_master

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._presentation.path,
            self.part.partname,
        )
        element = root.find(f"{{{P_NS}}}sldLayoutIdLst")
        if element is None:
            raise AttributeError("slide layout id list XML element is unavailable")
        return element


class SlideLayout:
    def __init__(self, presentation: Presentation, index: int, payload: dict[str, Any]) -> None:
        self._presentation = presentation
        self._index = index
        self._payload = payload
        self._shapes: MasterShapeCollection | None = None
        self._placeholders: BaseShapePlaceholderCollection | None = None
        self._deleted: bool = False

    @property
    def index(self) -> int:
        return self._index

    @property
    def partname(self) -> str:
        return str(self._payload.get("part", ""))

    @property
    def part(self) -> PackagePart:
        return PackagePart(self._presentation, self.partname, name=self.name)

    @property
    def name(self) -> str:
        return str(self._payload.get("name") or "")

    @name.setter
    def name(self, value: str | None) -> None:
        from .slide_layout_edits import _stage_layout_master_rename

        _stage_layout_master_rename(self, value)

    @property
    def slide_master(self) -> SlideMaster:
        parent = getattr(self, "_parent", None)
        if parent is not None:
            return parent
        for master in self._presentation.slide_masters:
            layout_parts = list(master._payload.get("layout_parts") or [])
            if not layout_parts or self.partname in layout_parts:
                return master
        return self._presentation.slide_master

    @property
    def used_by_slides(self) -> tuple[Slide, ...]:
        target_norm = self.partname.lstrip("/")
        return tuple(
            slide
            for slide in self._presentation.slides
            if slide.slide_layout.partname.lstrip("/") == target_norm
        )

    @property
    def element(self) -> XmlElementProxy:
        from .slide_master_facade import _master_layout_element

        return _master_layout_element(self._presentation, self.partname)

    @property
    def background(self) -> Background:
        return Background(self._presentation, self.partname)

    @property
    def shapes(self) -> MasterShapeCollection:
        self._ensure_shape_collections()
        assert self._shapes is not None
        return self._shapes

    @property
    def placeholders(self) -> BaseShapePlaceholderCollection:
        self._ensure_shape_collections()
        assert self._placeholders is not None
        return self._placeholders

    def iter_cloneable_placeholders(self) -> Iterator[MasterShape]:
        latent_types = {"dt", "ftr", "sldNum"}
        for placeholder in self.placeholders:
            if _placeholder_type_xml(placeholder) not in latent_types:
                yield placeholder

    def _cloneable_placeholder_payloads(self) -> list[dict[str, Any]]:
        staged = self._payload.get("_placeholder_payloads")
        if staged is not None:
            return deepcopy(staged)
        return _load_slide_layout_placeholder_payloads(
            self._presentation.path,
            self.partname,
        )

    def _ensure_shape_collections(self) -> None:
        if self._shapes is not None and self._placeholders is not None:
            return
        shape_payloads = self._payload.get("shapes")
        if shape_payloads is None:
            shape_payloads = _load_shape_payloads(self._presentation.path, self.partname)
            self._payload["shapes"] = shape_payloads
        shapes = [
            MasterShape(self, shape_index, shape)
            for shape_index, shape in enumerate(shape_payloads)
        ]
        self._shapes = MasterShapeCollection(self, shapes)
        self._placeholders = BaseShapePlaceholderCollection(self, shapes)


class SlideMasterCollection(Sequence["SlideMaster"]):
    def __init__(self, presentation: Presentation, masters: list[SlideMaster]) -> None:
        self._presentation = presentation
        self._masters = masters

    @overload
    def __getitem__(self, index: int) -> SlideMaster: ...

    @overload
    def __getitem__(self, index: slice) -> list[SlideMaster]: ...

    def __getitem__(self, index: int) -> SlideMaster:
        return self._masters[index]

    def __iter__(self) -> Iterator[SlideMaster]:
        return iter(self._masters)

    def __len__(self) -> int:
        return len(self._masters)

    def add(self, name: str) -> SlideMaster:
        """Create a blank, themed slide master that can receive custom layouts."""
        from .slide_master_facade import queue_master_add

        payload = queue_master_add(self._presentation, name)
        master = SlideMaster(self._presentation, len(self._masters), payload)
        self._masters.append(master)
        return master

    def clone(self, source: SlideMaster, name: str) -> SlideMaster:
        """Clone a master and its layouts into independently addressable parts."""
        if not isinstance(source, SlideMaster):
            raise TypeError("source must be a SlideMaster")
        from .slide_master_facade import queue_master_clone

        payload = queue_master_clone(self._presentation, source, name)
        master = SlideMaster(self._presentation, len(self._masters), payload)
        self._masters.append(master)
        layouts = self._presentation.slide_layouts._layouts
        for layout_payload in payload["_layout_payloads"]:
            layout = SlideLayout(self._presentation, len(layouts), layout_payload)
            layout._parent = master
            layouts.append(layout)
        return master

    @property
    def part(self) -> PackagePart:
        return self._presentation.part

    @property
    def parent(self) -> Presentation:
        return self._presentation

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._presentation.path,
            _presentation_partname(self._presentation.path),
        )
        element = root.find(f"{{{P_NS}}}sldMasterIdLst")
        if element is None:
            raise AttributeError("slide master id list XML element is unavailable")
        return element


class SlideMaster:
    def __init__(self, presentation: Presentation, index: int, payload: dict[str, Any]) -> None:
        self._presentation = presentation
        self._index = index
        self._payload = payload
        shapes = [
            MasterShape(self, shape_index, shape)
            for shape_index, shape in enumerate(payload.get("shapes", []))
        ]
        self.shapes = MasterShapeCollection(self, shapes)
        self.placeholders = MasterPlaceholderCollection(self, shapes)

    @property
    def partname(self) -> str:
        return str(self._payload.get("part", ""))

    @property
    def part(self) -> PackagePart:
        return PackagePart(self._presentation, self.partname, name="")

    @property
    def element(self) -> XmlElementProxy:
        from .slide_master_facade import _master_layout_element

        return _master_layout_element(self._presentation, self.partname)

    @property
    def background(self) -> Background:
        return Background(self._presentation, self.partname)

    @property
    def name(self) -> str:
        return str(self._payload.get("name") or "")

    @name.setter
    def name(self, value: str | None) -> None:
        from .slide_layout_edits import _stage_layout_master_rename

        _stage_layout_master_rename(self, value)

    @property
    def slide_layouts(self) -> SlideLayoutCollection:
        layout_parts = list(self._payload.get("layout_parts") or [])
        layouts = [
            layout
            for layout in self._presentation.slide_layouts
            if (
                layout.partname in layout_parts
                or (not layout_parts and not self._payload.get("_layout_parts_explicit", False))
            )
        ]
        return SlideLayoutCollection(
            self._presentation,
            layouts,
            partname=self.partname,
            parent=self,
        )

    def add_layout(self, name: str, *, title: bool = True, body: bool = True) -> SlideLayout:
        """Synthesize a custom layout containing title and/or body placeholders."""
        return self.slide_layouts.add(name, title=title, body=body)

    def clone_layout(self, source: SlideLayout, name: str) -> SlideLayout:
        """Clone ``source`` into this master with a distinct layout part."""
        return self.slide_layouts.clone(source, name)


class SlideCollection(HtmlImportMixin, SlideInsertMixin, Sequence["Slide"]):
    def __init__(self, presentation: Presentation, slides: list[Slide]) -> None:
        self._presentation = presentation
        self._slides = slides
        self._detached_slides: list[Slide] = []
        self._dropped_rel_slides: list[Slide] = []

    @overload
    def __getitem__(self, index: int) -> Slide: ...

    @overload
    def __getitem__(self, index: slice) -> list[Slide]: ...

    def __getitem__(self, index: int | slice) -> Slide | list[Slide]:
        return self._slides[index]

    def __iter__(self) -> Iterator[Slide]:
        return iter(self._slides)

    def __len__(self) -> int:
        return len(self._slides)

    def index(self, slide: Slide) -> int:
        for index, candidate in enumerate(self._slides):
            if candidate is slide:
                return index
        raise ValueError(f"{slide!r} is not in slide collection")

    @property
    def part(self) -> PackagePart:
        return self._presentation.part

    @property
    def parent(self) -> Presentation:
        return self._presentation

    @property
    def element(self) -> XmlElementProxy:
        source = self._presentation._source_path
        root = _package_xml_element(source, _presentation_partname(source))
        element = root.find(f"{{{P_NS}}}sldIdLst")
        if element is None:
            raise AttributeError("slide id list XML element is unavailable")
        return element

    @property
    def _sldIdLst(self) -> _SlideIdList:
        """python-pptx-compatible live ``p:sldIdLst`` view of this collection."""
        return _SlideIdList(self)

    def _require_attached(self, allowed: Slide | None = None) -> None:
        if any(slide is not allowed for slide in self._detached_slides):
            raise ValueError(
                "slides._sldIdLst has detached entries; re-insert them with "
                "insert() or append(), or delete their slides with slides.remove()"
            )

    def get(self, slide_id: int, default: Any = None) -> Slide | Any:
        for slide in self._slides:
            if slide.slide_id == slide_id:
                return slide
        return default

    def move(self, old_index: int, new_index: int) -> None:
        """Move one slide while preserving its package and relationship identity."""
        with self._presentation._mutation_lock:
            self._require_attached()
            self._move_slide(old_index, new_index)

    def _move_slide(self, old_index: int, new_index: int) -> None:
        old_index = _normalize_collection_index(
            old_index,
            len(self._slides),
            "old_index",
        )
        new_index = _normalize_collection_index(
            new_index,
            len(self._slides),
            "new_index",
        )
        if old_index == new_index:
            return
        slide = self._slides.pop(old_index)
        self._slides.insert(new_index, slide)
        self._presentation._queue_slide_reorder([candidate._index for candidate in self._slides])

    def add_slide(self, slide_layout: SlideLayout) -> Slide:
        with self._presentation._mutation_lock:
            self._require_attached()
            if not isinstance(slide_layout, SlideLayout):
                raise TypeError("slide_layout must be a wolfppt SlideLayout")
            if slide_layout._presentation is not self._presentation:
                raise ValueError("slide_layout belongs to a different presentation")
            if self._presentation._slide_order is not None:
                self._presentation._slide_order.append(len(self._slides))
            token = object()
            self._presentation._queue_slide_add(slide_layout, token=token)
            slide = Slide(
                self._presentation,
                len(self._slides),
                {
                    "part": "",
                    "texts": [],
                    "shapes": [],
                    "layout_index": slide_layout.index,
                    "_pending_creation": True,
                    "_creation_token": token,
                },
            )
            for placeholder_payload in slide_layout._cloneable_placeholder_payloads():
                slide.shapes._append_placeholder_clone_payload(placeholder_payload)
            self._slides.append(slide)
            return slide

    def duplicate(self, source: Slide) -> Slide:
        """Append a deep copy of ``source`` while sharing only safe package parts."""
        with self._presentation._mutation_lock:
            self._require_attached()
            if not isinstance(source, Slide):
                raise TypeError("source must be a wolfppt Slide")
            if source._presentation is not self._presentation:
                raise ValueError("slide does not belong to this presentation")
            if source._payload.get("_pending_creation"):
                return self._duplicate_pending(source)
            source_partname = source.partname
            if not source_partname:
                raise ValueError("slide does not belong to this presentation")
            source._ensure_shape_collections()
            if self._presentation._slide_order is not None:
                self._presentation._slide_order.append(len(self._slides))
            token = object()
            self._presentation._queue_slide_duplicate(source_partname, token=token)
            payload = {
                "part": source_partname,
                "texts": list(source._payload.get("texts", [])),
                "shapes": [deepcopy(item) for item in source._payload.get("shapes", [])],
                "_pending_creation": True,
                "_creation_token": token,
                "_source_part": source_partname,
                "layout_index": getattr(source.slide_layout, "index", None),
            }
            slide = Slide(self._presentation, len(self._slides), payload)
            self._slides.append(slide)
            return slide

    def _duplicate_pending(self, source: Slide) -> Slide:
        """Duplicate a slide created in this session before it has a package part.

        The copy replays the source's queued creation under a new token, then
        clones every edit queued against the source so that the saved copy
        carries the same shapes, text, and slide properties.
        """
        presentation = self._presentation
        source_token = source._payload.get("_creation_token")
        creation = next(
            (
                item
                for item in presentation._slide_creations
                if len(item) > 2 and item[2] is source_token
            ),
            None,
        )
        if source_token is None or creation is None:
            raise ValueError("slide does not belong to this presentation")
        if source._index in presentation._notes_slide_adds:
            raise ValueError(
                "cannot duplicate an unsaved new slide that has a pending notes "
                "slide; save and reopen the presentation before duplicating it"
            )
        # A pending slide's shapes live on its collection, not its payload list.
        shape_payloads = [deepcopy(shape._payload) for shape in source.shapes]
        kind, creation_payload = creation[0], creation[1]
        target_index = len(self._slides)
        if presentation._slide_order is not None:
            presentation._slide_order.append(target_index)
        token = object()
        presentation._slide_creations.append((kind, creation_payload, token))
        _clone_pending_slide_edits(
            presentation,
            source._index,
            target_index,
            source_token,
            token,
        )
        payload: dict[str, Any] = {
            "part": source.partname,
            "texts": list(source._payload.get("texts", [])),
            "shapes": shape_payloads,
            "layout_index": getattr(source.slide_layout, "index", None),
            "_pending_creation": True,
            "_creation_token": token,
        }
        if "_source_part" in source._payload:
            payload["_source_part"] = source._payload["_source_part"]
        for key in ("name", "hidden"):
            if key in source._payload:
                payload[key] = source._payload[key]
        slide = Slide(presentation, target_index, payload)
        self._slides.append(slide)
        return slide

    def remove(self, slide: Slide) -> None:
        """Remove a slide from the collection and queue package deletion."""
        with self._presentation._mutation_lock:
            if not isinstance(slide, Slide):
                raise TypeError("slide must be a wolfppt Slide")
            if slide._presentation is not self._presentation:
                raise ValueError("slide does not belong to this presentation")
            if getattr(slide, "_deleted", False):
                raise ValueError("cannot delete already-deleted slide")
            if slide not in self._slides:
                raise ValueError(f"{slide!r} is not in slide collection")
            if len(self._slides) <= 1:
                raise ValueError("cannot delete the only slide in the presentation")
            if not any(slide is s for s in self._detached_slides):
                self._require_attached()
            self._detached_slides = [s for s in self._detached_slides if s is not slide]
            is_pending = not bool(slide.partname) or bool(slide._payload.get("_pending_creation"))
            deleted_index = self._slides.index(slide)
            deleted_slide_index = slide._index
            slide._deleted = True
            self._slides.pop(deleted_index)

            if is_pending:
                token = slide._payload.get("_creation_token")
                creation_index = None
                if token is not None:
                    self._presentation._background_fill_solid_edits.discard(token)
                    self._presentation._background_fill_background_edits.discard(token)
                    self._presentation._background_fill_color_edits.pop(token, None)
                    self._presentation._slide_name_edits.pop(token, None)
                    self._presentation._slide_hidden_edits.pop(token, None)
                    changes = getattr(self._presentation, "_slide_layout_changes", None)
                    if changes is not None:
                        changes.pop(token, None)
                        if slide.partname:
                            changes.pop(slide.partname, None)
                            changes.pop(slide.partname.lstrip("/"), None)
                            changes.pop("/" + slide.partname.lstrip("/"), None)
                    for i, item in enumerate(self._presentation._slide_creations):
                        if len(item) > 2 and item[2] is token:
                            creation_index = i
                            break
                if creation_index is None:
                    # Fallback to positional matching if no token exists
                    pending_slides = [
                        s
                        for s in self._slides[:deleted_index]
                        if not s.partname or s._payload.get("_pending_creation")
                    ]
                    idx = len(pending_slides)
                    if 0 <= idx < len(self._presentation._slide_creations):
                        creation_index = idx
                if creation_index is None or not (
                    0 <= creation_index < len(self._presentation._slide_creations)
                ):
                    raise RuntimeError(
                        f"no matching creation entry found for pending slide {slide!r} "
                        f"(token={token!r}, creations={len(self._presentation._slide_creations)})"
                    )
                self._presentation._slide_creations.pop(creation_index)
                if self._presentation._slide_order is not None:
                    if deleted_slide_index in self._presentation._slide_order:
                        self._presentation._slide_order.remove(deleted_slide_index)
                    # If any remaining entries were greater than deleted_slide_index, decrement them
                    self._presentation._slide_order = [
                        idx - 1 if idx > deleted_slide_index else idx
                        for idx in self._presentation._slide_order
                    ]
                    if self._presentation._slide_order == list(range(len(self._slides))):
                        self._presentation._slide_order = None
                self._presentation._pending_slide_delete_in_progress = True
            index_remap = {
                survivor._index: new_index for new_index, survivor in enumerate(self._slides)
            }
            try:
                _rebase_pending_edits_after_slide_delete(
                    self._presentation,
                    deleted_index,
                    index_remap=index_remap,
                    deleted_slide_index=deleted_slide_index,
                )
            finally:
                if is_pending:
                    self._presentation._pending_slide_delete_in_progress = False
            for new_index, survivor in enumerate(self._slides):
                survivor._rebase_live_indices(new_index)
            if not is_pending:
                self._presentation._queue_slide_delete(slide.partname)
                self._presentation._slide_name_edits.pop(slide.partname.lstrip("/"), None)
                self._presentation._slide_hidden_edits.pop(slide.partname.lstrip("/"), None)
                changes = getattr(self._presentation, "_slide_layout_changes", None)
                if changes is not None:
                    changes.pop(slide.partname, None)
                    changes.pop(slide.partname.lstrip("/"), None)
                    changes.pop("/" + slide.partname.lstrip("/"), None)
            custom_shows = getattr(self._presentation, "_custom_shows", None)
            if custom_shows is not None:
                custom_shows._discard_slide(slide)

    def __delitem__(self, index: int | slice) -> None:
        """Delete a slide by integer index from the collection."""
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self._slides))
            target_indices = list(range(start, stop, step))
            if not target_indices:
                return
            if len(target_indices) >= len(self._slides):
                if len(self._slides) <= 1:
                    raise ValueError("cannot delete the only slide in the presentation")
                raise ValueError("cannot delete every slide in the presentation")
            targets = [self._slides[i] for i in sorted(target_indices, reverse=True)]
            for slide in targets:
                self.remove(slide)
            return
        normalized = _normalize_collection_index(index, len(self._slides), "slide index")
        slide = self._slides[normalized]
        self.remove(slide)


class _SlideIdEntry:
    """Live ``p:sldId`` entry for one slide, like python-pptx ``CT_SlideId``."""

    tag = f"{{{P_NS}}}sldId"

    def __init__(self, slide: Slide) -> None:
        self._slide = slide

    @property
    def attrib(self) -> dict[str, str]:
        """Saved ``id``/``r:id`` values; an unsaved slide has none yet."""
        metadata = _slide_metadata(self._slide)
        attrib: dict[str, str] = {}
        if metadata.get("slide_id") is not None:
            attrib["id"] = str(metadata["slide_id"])
        if metadata.get("relationship_id") is not None:
            attrib[f"{{{_R_NS}}}id"] = str(metadata["relationship_id"])
        return attrib

    def get(self, key: str, default: Any = None) -> Any:
        return self.attrib.get(key, default)

    @property
    def id(self) -> int:
        return int(self._saved_attribute("id"))

    @property
    def rId(self) -> str:
        return self._saved_attribute(f"{{{_R_NS}}}id")

    def _saved_attribute(self, key: str) -> str:
        value = self.attrib.get(key)
        if value is None:
            raise AttributeError(
                "slide id and relationship id are assigned when the new slide is saved"
            )
        return value

    def __repr__(self) -> str:
        return f"<_SlideIdEntry attrib={self.attrib!r}>"


def _slide_id_entry(slide: Slide) -> _SlideIdEntry:
    entry = slide._sld_id_entry
    if entry is None:
        entry = slide._sld_id_entry = _SlideIdEntry(slide)
    return entry


class _SlideIdList:
    """Live python-pptx ``p:sldIdLst`` view over :class:`SlideCollection` order.

    ``remove`` detaches an entry and ``insert``/``append`` reattach it through
    the collection move path, so the collection stays the only order source.
    A detached entry whose slide relationship was dropped with
    ``prs.part.drop_rel`` is deleted through :meth:`SlideCollection.remove`;
    saving deletes any other still-detached entry, like python-pptx. Other
    collection mutations refuse while entries are detached. Foreign elements
    and entries already in the list are refused.
    """

    tag = f"{{{P_NS}}}sldIdLst"

    def __init__(self, slides: SlideCollection) -> None:
        self._slides = slides

    def _attached(self) -> list[Slide]:
        detached = self._slides._detached_slides
        return [
            slide
            for slide in self._slides._slides
            if not any(slide is candidate for candidate in detached)
        ]

    def __len__(self) -> int:
        return len(self._attached())

    def __iter__(self) -> Iterator[_SlideIdEntry]:
        return iter([_slide_id_entry(slide) for slide in self._attached()])

    def __getitem__(self, index: int | slice) -> _SlideIdEntry | list[_SlideIdEntry]:
        attached = self._attached()
        if isinstance(index, slice):
            return [_slide_id_entry(slide) for slide in attached[index]]
        return _slide_id_entry(attached[index])

    def index(self, entry: _SlideIdEntry) -> int:
        slide = self._entry_slide(entry)
        for position, candidate in enumerate(self._attached()):
            if candidate is slide:
                return position
        raise ValueError(f"{entry!r} is not in the slide id list")

    def remove(self, entry: _SlideIdEntry) -> None:
        """Detach ``entry`` so a following ``insert``/``append`` can move it."""
        with self._slides._presentation._mutation_lock:
            slide = self._entry_slide(entry)
            if not any(slide is candidate for candidate in self._attached()):
                raise ValueError(f"{entry!r} is not in the slide id list")
            self._slides._detached_slides.append(slide)
            if any(slide is s for s in self._slides._dropped_rel_slides):
                try:
                    self._slides.remove(slide)
                except ValueError:
                    self._slides._detached_slides.pop()
                    raise

    def insert(self, index: int, entry: _SlideIdEntry) -> None:
        """Reattach a detached ``entry`` before ``index`` with lxml semantics."""
        with self._slides._presentation._mutation_lock:
            slide = self._entry_slide(entry)
            collection = self._slides
            if not any(slide is candidate for candidate in collection._detached_slides):
                raise ValueError(f"{entry!r} is already in the slide id list; remove it first")
            attached = self._attached()
            position = _index(index)
            if position < 0:
                position += len(attached)
            if not 0 <= position <= len(attached):
                position = len(attached)  # lxml appends out-of-range positions
            others = [candidate for candidate in collection._slides if candidate is not slide]
            new_index = len(others)
            if position < len(attached):
                anchor = attached[position]
                new_index = next(i for i, s in enumerate(others) if s is anchor)
            old_index = next(i for i, s in enumerate(collection._slides) if s is slide)
            collection._move_slide(old_index, new_index)
            collection._detached_slides = [
                candidate for candidate in collection._detached_slides if candidate is not slide
            ]

    def append(self, entry: _SlideIdEntry) -> None:
        self.insert(len(self), entry)

    def _entry_slide(self, entry: object) -> Slide:
        if not isinstance(entry, _SlideIdEntry):
            raise TypeError(
                f"slides._sldIdLst accepts only its own p:sldId entries, got {type(entry).__name__}"
            )
        slide = entry._slide
        if slide._presentation is not self._slides._presentation:
            raise ValueError(f"{entry!r} belongs to a different presentation")
        if slide._deleted:
            raise ValueError(f"{entry!r} belongs to a deleted slide")
        return slide

    def __repr__(self) -> str:
        return f"<_SlideIdList entries={len(self)}>"


def _rebase_pending_edits_after_slide_delete(
    presentation: Any,
    deleted_index: int | None = None,
    *,
    index_remap: dict[int, int] | None = None,
    deleted_slide_index: int | None = None,
) -> None:
    from .presentation_slide_delete_rebase import (
        rebase_presentation_edits_after_slide_delete,
    )

    rebase_presentation_edits_after_slide_delete(
        presentation,
        deleted_index,
        index_remap=index_remap,
        deleted_slide_index=deleted_slide_index,
    )


def _clone_pending_slide_edits(
    presentation: Any,
    source_index: int,
    target_index: int,
    source_token: Any,
    target_token: Any,
) -> None:
    """Copy edits queued against one pending slide onto a new pending slide.

    Slide-index-keyed queues are cloned by rewriting the leading slide index;
    creation-token-keyed queues (name, hidden, background) by swapping tokens.
    Values are deep-copied because several queues merge later edits in place.
    """
    from .presentation_slide_delete_rebase import (
        SLIDE_INDEX_DICT_FIELDS,
        SLIDE_INDEX_SET_FIELDS,
        SLIDE_INDEX_TUPLE_LIST_FIELDS,
    )

    def retarget(key: Any) -> Any:
        if key is source_token:
            return target_token
        if type(key) is int and key == source_index:
            return target_index
        if isinstance(key, tuple) and key and type(key[0]) is int and key[0] == source_index:
            return (target_index,) + key[1:]
        return None

    for attr in (
        *SLIDE_INDEX_DICT_FIELDS,
        "_shape_target_slide_edits",
        "_background_fill_color_edits",
    ):
        queue = getattr(presentation, attr, None)
        if isinstance(queue, dict):
            for key, value in list(queue.items()):
                cloned_key = retarget(key)
                if cloned_key is not None:
                    queue[cloned_key] = deepcopy(value)

    for attr in (
        *SLIDE_INDEX_SET_FIELDS,
        "_background_fill_solid_edits",
        "_background_fill_background_edits",
    ):
        queue = getattr(presentation, attr, None)
        if isinstance(queue, set):
            clones = {retarget(item) for item in queue} - {None}
            queue.update(clones)

    for attr in SLIDE_INDEX_TUPLE_LIST_FIELDS:
        queue = getattr(presentation, attr, None)
        if isinstance(queue, list):
            queue.extend(
                deepcopy((target_index,) + item[1:])
                for item in list(queue)
                if retarget(item) is not None and isinstance(item, tuple)
            )
    shape_adds = presentation._shape_adds
    shape_adds.extend(
        (kind, (target_index,) + deepcopy(args[1:]))
        for kind, args in list(shape_adds)
        if isinstance(args, tuple) and retarget(args) is not None
    )

    for attr in ("_table_row_column_edits", "_table_cell_merge_edits"):
        queue = getattr(presentation, attr, None)
        if isinstance(queue, list):
            queue.extend(
                {**deepcopy(edit), "slide_index": target_index}
                for edit in list(queue)
                if isinstance(edit, dict) and retarget(edit.get("slide_index")) is not None
            )


def _normalize_collection_index(value: int, length: int, name: str) -> int:
    try:
        normalized = _index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer") from exc
    if normalized < 0:
        normalized += length
    if normalized < 0 or normalized >= length:
        raise IndexError(f"{name} out of range")
    return normalized


class Slide:
    def __init__(self, presentation: Presentation, index: int, payload: dict[str, Any]) -> None:
        self._presentation = presentation
        self._index = index
        self._payload = payload
        self._deleted: bool = False
        self._sld_id_entry: _SlideIdEntry | None = None
        self._shapes: ShapeCollection | None = None
        self._placeholders: PlaceholderCollection | None = None
        self._comments: SlideComments | None = None
        self._transition_facade: Any | None = None
        self._animation_facade: Any | None = None
        self._notes_slide: NotesSlide | None = None
        if "shapes" in payload:
            self._set_shape_payloads(list(payload.get("shapes") or []))

    @property
    def shapes(self) -> ShapeCollection:
        _require_open_presentation(self._presentation)
        self._ensure_shape_collections()
        assert self._shapes is not None
        return self._shapes

    @property
    def signature_lines(self) -> Any:
        """DrawingML picture and slide-related VML signature-line metadata."""
        from .signature_lines import SignatureLines

        return SignatureLines(self)

    @property
    def designer_metadata(self) -> tuple[DesignerMetadata, ...]:
        """Read-only designer ``p:ext`` payload elements from the source package."""
        from .slide_designer_metadata import read_designer_metadata

        return read_designer_metadata(self)

    @property
    def vml_drawings(self) -> tuple[VmlDrawing, ...]:
        """Read-only legacy VML drawings."""
        from .vml_drawings import read_slide_vml_drawings

        return read_slide_vml_drawings(self)

    @property
    def placeholders(self) -> PlaceholderCollection:
        self._ensure_shape_collections()
        assert self._placeholders is not None
        return self._placeholders

    @property
    def comments(self) -> SlideComments:
        """The slide's legacy comments, discovered from the source package.

        Reads come from the source package and mutations are queued on the
        presentation, so nothing is written until :meth:`Presentation.save`.
        """
        if self._comments is None:
            from .comment_edits import SlideComments

            self._comments = SlideComments(self)
        return self._comments

    @property
    def transition(self) -> Any:
        """The slide transition facade, discovered from the source package.

        Reads come from the source package and mutations are queued on the
        presentation, so nothing is written until :meth:`Presentation.save`.
        """
        facade = getattr(self, "_transition_facade", None)
        if facade is None:
            from .slide_transition_facade import SlideTransition

            facade = SlideTransition(self)
            self._transition_facade = facade
        return facade

    @property
    def animation(self) -> Any:
        """The slide animation facade, discovered from the source package.

        Reads come from the source package and mutations are queued on the
        presentation, so nothing is written until :meth:`Presentation.save`.
        """
        facade = getattr(self, "_animation_facade", None)
        if facade is None:
            from .slide_animation_facade import SlideAnimation

            facade = SlideAnimation(self)
            self._animation_facade = facade
        return facade

    def _ensure_shape_collections(self) -> None:
        if self._shapes is not None and self._placeholders is not None:
            return
        shape_payloads = self._payload.get("shapes")
        if shape_payloads is None:
            from . import native

            source = self._presentation._source_path
            try:
                slide_payload = _slide_summary_readers(self._presentation).summarize_slide(
                    source, self._index
                )
            except RuntimeError:
                if isinstance(source, InMemoryPackageSource):
                    raise
                slide_payload = dict(native.summarize(source).slides[self._index])
            self._payload.update(slide_payload)
            shape_payloads = list(slide_payload.get("shapes") or [])
        self._set_shape_payloads(list(shape_payloads or []), _native=True)

    def _set_shape_payloads(
        self, shape_payloads: list[dict[str, Any]], *, _native: bool = False
    ) -> None:
        self._payload["shapes"] = shape_payloads
        shapes: list[Shape] = []
        table_index = 0
        run_start = 0
        for shape_index, shape in enumerate(shape_payloads):
            shapes.append(Shape(self, shape_index, shape, table_index, run_start, _native=_native))
            table_index += len(shape.get("tables", []))
            run_start += _shape_run_count_payload(shape)
        self._shapes = ShapeCollection(self, shapes)
        self._placeholders = PlaceholderCollection(self, shapes)

    def _rebase_live_indices(self, slide_index: int) -> None:
        self._index = slide_index
        if self._notes_slide is not None:
            self._notes_slide._index = slide_index
        if self._shapes is None:
            return
        table_index = 0
        run_start_index = 0
        for shape_index, shape in enumerate(self._shapes):
            shape._index = shape_index
            shape._table_index = table_index
            shape._run_start_index = run_start_index
            table_index += len(shape._payload.get("tables", []))
            run_start_index += _shape_run_count_payload(shape._payload)

    def _materialize_pending_creation(self, partname: str) -> None:
        previous_partname = self.partname
        norm = partname.lstrip("/")
        self._payload["part"] = norm
        self._payload.pop("_pending_creation", None)
        self._payload.pop("_creation_token", None)
        if not previous_partname and self._presentation._slide_metadata is not None:
            metadata = self._presentation._slide_metadata.pop("", None)
            if metadata is not None:
                self._presentation._slide_metadata[norm] = metadata

    @property
    def partname(self) -> str:
        return str(self._payload.get("part", ""))

    @property
    def slide_id(self) -> int:
        metadata = _slide_metadata(self)
        slide_id = metadata.get("slide_id")
        if slide_id is not None:
            return int(slide_id)
        return 256 + self._index

    @property
    def name(self) -> str:
        if "name" not in self._payload:
            self._payload["name"] = _slide_name(self)
        return str(self._payload.get("name") or "")

    @name.setter
    def name(self, value: str | None) -> None:
        name = "" if value is None else str(value)
        if name == self.name:
            return
        self._payload["name"] = name
        self._presentation._queue_slide_name(self, name)

    @property
    def hidden(self) -> bool:
        if "hidden" not in self._payload:
            self._payload["hidden"] = _slide_hidden(self)
        return bool(self._payload.get("hidden", False))

    @hidden.setter
    def hidden(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError(f"hidden must be a bool, got {type(value).__name__}")
        if value == self.hidden:
            return
        self._payload["hidden"] = value
        self._presentation._queue_slide_hidden(self, value)

    @property
    def slide_layout(self) -> SlideLayout:
        changes = getattr(self._presentation, "_slide_layout_changes", None)
        if changes:
            target_part = (
                changes.get(self.partname)
                or changes.get(self.partname.lstrip("/"))
                or changes.get("/" + self.partname.lstrip("/"))
            )
            if target_part:
                target_norm = target_part.lstrip("/")
                for layout in self._presentation.slide_layouts:
                    if layout.partname.lstrip("/") == target_norm:
                        return layout
        layout_part = self._payload.get("layout_part")
        if layout_part:
            lp_norm = str(layout_part).lstrip("/")
            for layout in self._presentation.slide_layouts:
                if layout.partname.lstrip("/") == lp_norm:
                    return layout
        layout_index = self._payload.get("layout_index")
        if isinstance(layout_index, int) and 0 <= layout_index < len(
            self._presentation.slide_layouts
        ):
            return self._presentation.slide_layouts[layout_index]
        layout_part = _slide_metadata(self).get("layout_part")
        if not layout_part:
            layout_index = _slide_metadata(self).get("layout_index")
            if isinstance(layout_index, int) and 0 <= layout_index < len(
                self._presentation.slide_layouts
            ):
                return self._presentation.slide_layouts[layout_index]
        if layout_part:
            lp_norm = str(layout_part).lstrip("/")
            for layout in self._presentation.slide_layouts:
                if layout.partname.lstrip("/") == lp_norm:
                    return layout
        raise AttributeError("slide layout relationship is unavailable")

    @slide_layout.setter
    def slide_layout(self, value: SlideLayout) -> None:
        from .slide_layout_edits import validate_slide_layout_assignment

        validate_slide_layout_assignment(self, value)

        # Call registered queue method directly BEFORE changing live metadata.
        # If queue method raises or refuses, live metadata and payload remain untouched.
        self._presentation._queue_slide_layout_change(self.partname, value.partname)

        # Update live payload and metadata only after queueing succeeds
        self._payload["layout_index"] = value.index
        self._payload["layout_part"] = value.partname
        slide_meta = getattr(self._presentation, "_slide_metadata", None)
        if slide_meta is not None:
            meta = slide_meta.setdefault(self.partname, {})
            meta["layout_part"] = value.partname
            meta["layout_index"] = value.index

    @property
    def follow_master_background(self) -> bool:
        return bool(_slide_metadata(self).get("follow_master_background", True))

    @property
    def has_notes_slide(self) -> bool:
        if self._index in self._presentation._notes_slide_adds:
            return True
        return bool(_slide_metadata(self).get("has_notes_slide", False))

    @property
    def notes_slide(self) -> NotesSlide:
        if self._notes_slide is None:
            if not self.partname:
                partname = self._presentation._ensure_notes_slide_for_slide(self)
            else:
                try:
                    partname = _slide_notes_partname_for_part(
                        self._presentation.path,
                        self.partname,
                    )
                except AttributeError:
                    try:
                        partname = _slide_notes_partname(self)
                    except AttributeError:
                        partname = self._presentation._ensure_notes_slide_for_slide(self)
            self._notes_slide = NotesSlide(self, partname)
        return self._notes_slide

    @property
    def background(self) -> Background:
        return Background(self._presentation, self.partname, slide=self)

    @property
    def part(self) -> PackagePart:
        return PackagePart(self._presentation, self.partname, name="")

    @property
    def element(self) -> XmlElementProxy:
        return _package_xml_element(self._presentation.path, self.partname)

    @property
    def texts(self) -> list[str]:
        if "texts" not in self._payload or "shapes" not in self._payload:
            self._ensure_shape_collections()
        return list(self._payload.get("texts", []))


class NotesSlide(NotesSlideSemantics):
    def __init__(self, slide: Slide, partname: str) -> None:
        self._slide = slide
        self._presentation = slide._presentation
        self._index = slide._index
        self._partname = partname
        self._is_notes_slide = True
        shape_payloads = self._presentation._pending_notes_slide_payloads.get(partname)
        if shape_payloads is None:
            shape_payloads = _load_shape_payloads(self._presentation.path, partname)
        self._presentation._part_shape_payload_cache[partname] = shape_payloads
        shapes: list[Shape] = []
        for shape_index, shape in enumerate(shape_payloads):
            shapes.append(Shape(self, shape_index, shape))
        self.shapes = NotesSlideShapes(self, shapes)
        self.placeholders = PlaceholderCollection(self, shapes)

    @property
    def partname(self) -> str:
        return self._partname

    @property
    def part(self) -> PackagePart:
        return PackagePart(self._presentation, self.partname, name="")

    @property
    def element(self) -> XmlElementProxy:
        return _package_xml_element(self._presentation.path, self.partname)

    @property
    def background(self) -> Background:
        return Background(self._presentation, self.partname)

    @property
    def name(self) -> str:
        return _part_common_slide_name_from_path(self._presentation.path, self.partname)

    @cached_property
    def notes_master(self) -> NotesMaster | None:
        from .package_parts import open_package_source, resolve_package_target
        from .slide_metadata import package_relationships

        with open_package_source(self._presentation.path) as package:
            relationships = package_relationships(package, self.partname)
        for relationship in relationships.values():
            if (
                relationship.get("Type", "").endswith("/notesMaster")
                and relationship.get("TargetMode") != "External"
            ):
                return NotesMaster(
                    self._presentation,
                    resolve_package_target(self.partname, relationship.get("Target", "")),
                )
        # A newly created notes part has not yet acquired serialized rels.
        if self.partname in self._presentation._pending_notes_slide_payloads:
            return self._presentation.notes_master
        return None

    @property
    def notes_placeholder(self) -> Shape | None:
        for shape in self.shapes:
            if _placeholder_type_xml(shape) == "body":
                return shape
        return None

    @property
    def notes_text_frame(self) -> TextFrame | None:
        placeholder = self.notes_placeholder
        return None if placeholder is None else placeholder.text_frame

    def clone_master_placeholders(self, notes_master: Any) -> None:
        cloneable = [
            placeholder
            for placeholder in getattr(notes_master, "placeholders", ())
            if _placeholder_type_xml(placeholder) not in {"hdr", "dt", "ftr"}
        ]
        for placeholder in cloneable:
            self.shapes.clone_placeholder(placeholder)


class NotesSlideShapes(NotesSlideShapeRemoval, Sequence["Shape"]):
    def __init__(self, notes_slide: NotesSlide, shapes: list[Shape]) -> None:
        self._notes_slide = notes_slide
        self._shapes = shapes
        self._turbo_add_enabled = False

    @overload
    def __getitem__(self, index: int) -> Shape: ...

    @overload
    def __getitem__(self, index: slice) -> list[Shape]: ...

    def __getitem__(self, index: int | slice) -> Shape | list[Shape]:
        return self._shapes[index]

    def __iter__(self) -> Iterator[Shape]:
        return iter(self._shapes)

    def __len__(self) -> int:
        return len(self._shapes)

    @property
    def part(self) -> PackagePart:
        return self._notes_slide.part

    @property
    def parent(self) -> NotesSlide:
        return self._notes_slide

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._notes_slide._presentation.path,
            self._notes_slide.partname,
        )
        element = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
        if element is None:
            raise AttributeError("notes shape tree XML element is unavailable")
        return element

    @property
    def turbo_add_enabled(self) -> bool:
        return self._turbo_add_enabled

    @turbo_add_enabled.setter
    def turbo_add_enabled(self, value: Any) -> None:
        self._turbo_add_enabled = bool(value)

    def ph_basename(self, ph_type: Any) -> str:
        return _notes_placeholder_basename(ph_type)

    def clone_placeholder(self, placeholder: Any) -> None:
        if not getattr(placeholder, "is_placeholder", False):
            raise ValueError("clone_placeholder requires a placeholder shape")
        spec = self._append_placeholder_clone(placeholder)
        notes = self._notes_slide
        notes._presentation._queue_part_placeholder_add(notes.partname, spec)

    def _append_placeholder_clone(
        self,
        placeholder: Any,
    ) -> dict[str, str | bool | None]:
        placeholder_type = _placeholder_type_xml(placeholder)
        placeholder_orient = _placeholder_raw_value(placeholder, "placeholder_orient")
        placeholder_size = _placeholder_raw_value(placeholder, "placeholder_size")
        placeholder_idx = _placeholder_raw_value(placeholder, "placeholder_idx")
        shape_id = _next_shape_id(self._shapes)
        name = _next_notes_placeholder_name(
            self._shapes,
            shape_id,
            placeholder_type,
            placeholder_orient,
        )
        shape_index = len(self._shapes)
        payload = {
            "id": str(shape_id),
            "name": name,
            "kind": "shape",
            "text": "",
            "paragraphs": [""],
            "paragraph_runs": [[]],
            "is_placeholder": True,
            "placeholder_type": placeholder_type,
            "placeholder_idx": placeholder_idx,
            "placeholder_orient": placeholder_orient,
            "placeholder_size": placeholder_size,
        }
        shape = Shape(self._notes_slide, shape_index, payload)
        self._shapes.append(shape)
        self._notes_slide.placeholders._placeholders.append(shape)
        return {
            "id": str(shape_id),
            "name": name,
            "placeholder_type": placeholder_type,
            "placeholder_orient": placeholder_orient,
            "placeholder_size": placeholder_size,
            "placeholder_idx": placeholder_idx,
            "has_text_body": True,
        }


def default_handout_master_shape_payloads() -> list[dict[str, Any]]:
    return [
        _handout_master_placeholder_payload("2", "Header Placeholder 1", "hdr", "0"),
        _handout_master_placeholder_payload("3", "Date Placeholder 2", "dt", "1"),
        _handout_master_placeholder_payload("4", "Footer Placeholder 3", "ftr", "2"),
        _handout_master_placeholder_payload("5", "Slide Number Placeholder 4", "sldNum", "3"),
    ]


def _handout_master_placeholder_payload(
    shape_id: str,
    name: str,
    placeholder_type: str,
    placeholder_idx: str,
) -> dict[str, Any]:
    return {
        "id": shape_id,
        "name": name,
        "kind": "shape",
        "text": "",
        "paragraphs": [""],
        "paragraph_runs": [[]],
        "is_placeholder": True,
        "placeholder_type": placeholder_type,
        "placeholder_idx": placeholder_idx,
        "placeholder_orient": None,
        "placeholder_size": None,
    }


class HandoutMaster:
    def __init__(
        self,
        presentation: Presentation,
        partname: str,
        shape_payloads: list[dict[str, Any]] | None = None,
    ) -> None:
        self._presentation = presentation
        self._partname = partname
        payloads = (
            shape_payloads
            if shape_payloads is not None
            else _load_shape_payloads(presentation.path, partname)
        )
        shapes = [
            MasterShape(self, shape_index, shape) for shape_index, shape in enumerate(payloads)
        ]
        self.shapes = MasterShapeCollection(self, shapes)
        self.placeholders = MasterPlaceholderCollection(self, shapes)

    @property
    def partname(self) -> str:
        return self._partname

    @property
    def part(self) -> PackagePart:
        return PackagePart(self._presentation, self.partname, name="")

    @property
    def element(self) -> XmlElementProxy:
        return _package_xml_element(self._presentation.path, self.partname)

    @property
    def background(self) -> Background:
        return Background(self._presentation, self.partname)

    @property
    def name(self) -> str:
        return _part_common_slide_name_from_path(self._presentation.path, self.partname)


class NotesMaster(NotesMasterSemantics):
    def __init__(self, presentation: Presentation, partname: str) -> None:
        self._presentation = presentation
        self._partname = partname
        shapes = [
            MasterShape(self, shape_index, shape)
            for shape_index, shape in enumerate(_load_shape_payloads(presentation.path, partname))
        ]
        self.shapes = MasterShapeCollection(self, shapes)
        self.placeholders = MasterPlaceholderCollection(self, shapes)

    @property
    def partname(self) -> str:
        return self._partname

    @property
    def part(self) -> PackagePart:
        return PackagePart(self._presentation, self.partname, name="")

    @property
    def element(self) -> XmlElementProxy:
        return _package_xml_element(self._presentation.path, self.partname)

    @property
    def background(self) -> Background:
        return Background(self._presentation, self.partname)

    @property
    def name(self) -> str:
        return _part_common_slide_name_from_path(self._presentation.path, self.partname)


def _next_notes_placeholder_name(
    shapes: Sequence[Any],
    shape_id: int,
    placeholder_type: str | None,
    placeholder_orient: str | None,
) -> str:
    basename = _notes_placeholder_basename_from_xml(placeholder_type)
    if placeholder_orient == "vert":
        basename = f"Vertical {basename}"
    existing_names = {getattr(shape, "name", "") for shape in shapes}
    suffix = shape_id - 1
    while True:
        name = f"{basename} {suffix}"
        if name not in existing_names:
            return name
        suffix += 1


def _notes_placeholder_basename_from_xml(placeholder_type: str | None) -> str:
    return {
        "body": "Notes Placeholder",
        "dt": "Date Placeholder",
        "ftr": "Footer Placeholder",
        "hdr": "Header Placeholder",
        "sldImg": "Slide Image Placeholder",
        "sldNum": "Slide Number Placeholder",
    }.get(placeholder_type, "Content Placeholder")


_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PRES_PROPS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"
)
# Public key -> CT_ShowProperties attribute and its ECMA-376 schema default.
_SHOW_FLAGS = {
    "loop_until_stopped": ("loop", False),
    "show_narration": ("showNarration", False),
    "show_animation": ("showAnimation", True),
    "use_timings": ("useTimings", True),
}
# Public show type -> EG_ShowType element; an absent choice means ``present``.
_SHOW_TYPES = {"speaker": "present", "browse": "browse", "kiosk": "kiosk"}
_KIOSK_RESTART_DEFAULT_MS = 300000
_UNSIGNED_INT_MAX = 0xFFFFFFFF
_UNLOADED = object()


def _xsd_bool(raw: str | None, default: bool) -> bool:
    if raw in ("1", "true"):
        return True
    if raw in ("0", "false"):
        return False
    return default


def _show_child(parent: ET.Element, local: str) -> ET.Element | None:
    from .presentation_tags import one

    return one(parent, f"{{{_P_NS}}}{local}")


def _stored_show_type(show: ET.Element | None) -> tuple[str, ET.Element | None]:
    if show is None:
        return "speaker", None
    found = [
        (name, element)
        for name, local in _SHOW_TYPES.items()
        if (element := _show_child(show, local)) is not None
    ]
    if len(found) > 1:
        from .presentation_tags import LifecycleRefusal

        raise LifecycleRefusal("ambiguous slide show type in p:showPr")
    return found[0] if found else ("speaker", None)


def _resolve_pres_props(
    package: Any, source: str, roots: dict, *, read_only: bool = False
) -> tuple[str | None, ET.Element | None]:
    from .presentation_tags import (
        LifecycleRefusal,
        parse_xml,
        relationship_target,
        relationships,
    )
    from .xml_helpers import ooxml_namespace, ooxml_path

    if source not in roots:
        roots[source] = parse_xml(package.read(source), read_only=read_only)
    part = relationship_target(
        package,
        source,
        relationships(package, source, roots, read_only=read_only),
        rel_type=ooxml_namespace(roots[source], _R_NS) + "/presProps",
    )
    if part is None:
        return None, None
    if part not in roots:
        roots[part] = parse_xml(package.read(part), read_only=read_only)
    root = roots[part]
    if root.tag != ooxml_path(root, f"{{{_P_NS}}}presentationPr"):
        raise LifecycleRefusal("invalid presentation properties root")
    return part, root


def _apply_show_edits(root: ET.Element, edits: dict[str, Any]) -> None:
    """Edit only the queued ``p:showPr`` values; keep every other node."""
    from .xml_helpers import ooxml_path

    show = _show_child(root, "showPr")
    if show is None:
        show = ET.Element(ooxml_path(root, f"{{{_P_NS}}}showPr"))
        successors = {ooxml_path(root, f"{{{_P_NS}}}{local}") for local in ("clrMru", "extLst")}
        root.insert(
            next((i for i, c in enumerate(root) if c.tag in successors), len(root)),
            show,
        )
    for name, (attr, _) in _SHOW_FLAGS.items():
        if name in edits:
            show.set(attr, "1" if edits[name] else "0")
    stored_type, element = _stored_show_type(show)
    target = edits.get("show_type", stored_type)
    if target != stored_type or (element is None and "show_type" in edits):
        if element is not None:
            show.remove(element)
        # EG_ShowType is the first choice in the CT_ShowProperties sequence.
        element = ET.Element(ooxml_path(show, f"{{{_P_NS}}}{_SHOW_TYPES[target]}"))
        show.insert(0, element)
    if "show_scrollbar" in edits:
        element.set("showScrollbar", "1" if edits["show_scrollbar"] else "0")
    if "kiosk_restart" in edits:
        element.set("restart", str(edits["kiosk_restart"]))


def _stage_slide_show_package(source: Any, output: Path, edits: dict) -> None:
    from .package_parts import copy_open_package_with_replacements, open_package_source
    from .presentation_tags import add_part, serialize_xml
    from .xml_helpers import ooxml_namespace

    with open_package_source(source) as package:
        roots: dict = {}
        presentation = _presentation_partname(source)
        part, root = _resolve_pres_props(package, presentation, roots)
        if root is None:
            owner = roots[presentation]
            root = ET.Element(f"{{{ooxml_namespace(owner, _P_NS)}}}presentationPr")
            part, _ = add_part(
                package,
                roots,
                presentation,
                "ppt/presProps",
                ooxml_namespace(owner, _R_NS) + "/presProps",
                _PRES_PROPS_CONTENT_TYPE,
                root,
            )
            changed = set(roots) - {presentation}
        else:
            changed = {part}
        _apply_show_edits(root, edits)
        copy_open_package_with_replacements(
            package, output, {name: serialize_xml(roots[name]) for name in changed}
        )


def _flag_property(name: str, doc: str) -> property:
    def getter(self: SlideShowSettings) -> bool:
        if name in self._edits:
            return self._edits[name]
        attr, default = _SHOW_FLAGS[name]
        show = self._show()
        return _xsd_bool(None if show is None else show.get(attr), default)

    def setter(self: SlideShowSettings, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a bool")
        self._show()
        self._edits[name] = value

    return property(getter, setter, doc=doc)


class SlideShowSettings(PresentationExtensionFlags):
    """Slide show setup stored in ``p:presentationPr/p:showPr``.

    The ``presentationPr`` element is the root of the presentation properties
    part (``ppt/presProps.xml``) related from ``ppt/presentation.xml``. Reads
    merge queued edits over stored values and ECMA-376 defaults; the next
    ``Presentation.save`` publishes the edits. Select an existing custom show
    through ``custom_show`` or assign None for all slides. Slide ranges,
    pen color, extensions and unknown attributes are preserved.
    """

    loop_until_stopped = _flag_property(
        "loop_until_stopped", "Loop continuously until Esc (``showPr@loop``)."
    )
    show_narration = _flag_property(
        "show_narration", "Play recorded narration (``showPr@showNarration``)."
    )
    show_animation = _flag_property(
        "show_animation", "Play slide animations (``showPr@showAnimation``)."
    )
    use_timings = _flag_property(
        "use_timings", "Advance slides by saved timings (``showPr@useTimings``)."
    )

    def __init__(self, presentation: Presentation) -> None:
        self._presentation = presentation
        self._edits: dict[str, Any] = {}
        self._stored: Any = _UNLOADED

    def _show(self) -> ET.Element | None:
        presentation = self._presentation
        if presentation._disposed:
            raise RuntimeError("presentation is disposed")
        if self._stored is _UNLOADED:
            from .package_parts import open_package_source

            source = presentation._source_path
            with open_package_source(source) as package:
                _, root = _resolve_pres_props(
                    package, _presentation_partname(source), {}, read_only=True
                )
            self._stored = None if root is None else _show_child(root, "showPr")
        return self._stored

    def _stored_type_element(self, show_type: str) -> ET.Element | None:
        stored_type, element = _stored_show_type(self._show())
        return element if stored_type == show_type else None

    @property
    def show_type(self) -> str:
        """``"speaker"`` (``p:present``), ``"browse"`` or ``"kiosk"``."""
        if "show_type" in self._edits:
            return self._edits["show_type"]
        return _stored_show_type(self._show())[0]

    @show_type.setter
    def show_type(self, value: str) -> None:
        if value not in _SHOW_TYPES:
            raise ValueError(f"show_type must be one of {sorted(_SHOW_TYPES)}")
        self._show()
        self._edits["show_type"] = value
        if value != "browse":
            self._edits.pop("show_scrollbar", None)
        if value != "kiosk":
            self._edits.pop("kiosk_restart", None)

    @property
    def browse_kiosk(self) -> bool:
        """Browsed at a kiosk (full screen, restarts after inactivity)."""
        return self.show_type == "kiosk"

    @browse_kiosk.setter
    def browse_kiosk(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("browse_kiosk must be a bool")
        if value:
            self.show_type = "kiosk"
        elif self.show_type == "kiosk":
            self.show_type = "speaker"

    @property
    def show_scrollbar(self) -> bool | None:
        """Browse-mode scrollbar (``p:browse@showScrollbar``); None otherwise."""
        if self.show_type != "browse":
            return None
        if "show_scrollbar" in self._edits:
            return self._edits["show_scrollbar"]
        element = self._stored_type_element("browse")
        raw = None if element is None else element.get("showScrollbar")
        return _xsd_bool(raw, True)

    @show_scrollbar.setter
    def show_scrollbar(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("show_scrollbar must be a bool")
        if self.show_type != "browse":
            raise ValueError('show_scrollbar requires show_type "browse"')
        self._edits["show_scrollbar"] = value

    @property
    def kiosk_restart(self) -> int | None:
        """Kiosk inactivity restart in milliseconds (``p:kiosk@restart``).

        None unless ``show_type`` is ``"kiosk"``.
        """
        if self.show_type != "kiosk":
            return None
        if "kiosk_restart" in self._edits:
            return self._edits["kiosk_restart"]
        element = self._stored_type_element("kiosk")
        raw = None if element is None else element.get("restart")
        if raw is None or not raw.isdigit():
            return _KIOSK_RESTART_DEFAULT_MS
        return int(raw)

    @kiosk_restart.setter
    def kiosk_restart(self, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("kiosk_restart must be an int of milliseconds")
        if not 0 <= value <= _UNSIGNED_INT_MAX:
            raise ValueError("kiosk_restart must fit xsd:unsignedInt")
        if self.show_type != "kiosk":
            raise ValueError('kiosk_restart requires show_type "kiosk"')
        self._edits["kiosk_restart"] = value

    @property
    def slide_range(self) -> tuple[int, int] | None:
        """Queued or stored bounds; None for all slides or a custom show."""
        from .slideshow_settings import _current_selection

        kind, value = _current_selection(self._presentation)
        return value if kind == "sldRg" else None

    @property
    def custom_show(self) -> CustomShow | None:
        """Live selected custom show; None for all slides or a numeric range.

        Unknown, malformed, ambiguous or deleted selections are refused. This
        stored playback setup does not filter static PDF or PNG exports.
        """
        from .slideshow_settings import get_custom_show

        return get_custom_show(self._presentation)

    @custom_show.setter
    def custom_show(self, value: CustomShow | None) -> None:
        from .slideshow_settings import set_custom_show

        set_custom_show(self._presentation, value)

    @property
    def dirty(self) -> bool:
        return bool(self._edits)

    @contextmanager
    def _staged_for_save(self) -> Iterator[None]:
        """Rebase onto a package carrying the queued edits for one save.

        The ordinary save transaction then publishes and rebases that package.
        A failed save restores the original source and keeps the edits queued.
        """
        from .slideshow_settings import _current_selection

        # Validate before staging or publishing even when only sibling edits
        # are queued. A deleted selected show must not become a dangling ID.
        _current_selection(self._presentation)
        if not self._edits:
            yield
            return
        presentation = self._presentation
        previous_source = presentation._source_path
        previous_tempdir = presentation._source_tempdir
        edits = dict(self._edits)
        staged_dir: tempfile.TemporaryDirectory[str] | None = tempfile.TemporaryDirectory(
            prefix="wolfppt-slide-show-"
        )
        try:
            staged: Any = Path(staged_dir.name) / "presentation.pptx"
            _stage_slide_show_package(previous_source, staged, edits)
            if isinstance(previous_source, InMemoryPackageSource):
                staged = InMemoryPackageSource(staged.read_bytes())
                staged_dir.cleanup()
                staged_dir = None
        except BaseException:
            if staged_dir is not None:
                staged_dir.cleanup()
            raise
        presentation._source_path = staged
        if staged_dir is not None:
            presentation._source_tempdir = staged_dir
        try:
            yield
        except BaseException:
            if presentation._source_path is staged:
                presentation._source_path = previous_source
                presentation._source_tempdir = previous_tempdir
                if staged_dir is not None:
                    staged_dir.cleanup()
            raise
        for name, value in edits.items():
            if name in self._edits and self._edits[name] == value:
                del self._edits[name]
        self._stored = _UNLOADED
        if previous_tempdir is not None and presentation._source_tempdir is not previous_tempdir:
            previous_tempdir.cleanup()
