"""Slide, layout, master, and notes facade collections."""


from __future__ import annotations
from collections.abc import Iterator, Sequence
from copy import deepcopy
from operator import index as _index
from typing import Any, overload
from .background_facade import Background
from .package_parts import (
    PackagePart,
    XmlElementProxy,
    package_xml_element as _package_xml_element,
)
from .shape_facade import (
    BaseShapePlaceholderCollection,
    MasterShape,
    MasterShapeCollection,
    MasterPlaceholderCollection,
    PlaceholderCollection,
    Shape,
    ShapeCollection,
    _notes_placeholder_basename,
    _placeholder_type_xml,
)
from .shape_inspection import (
    _next_shape_id,
    _placeholder_raw_value,
)
from .slide_metadata import (
    first_slide_master_partname as _first_slide_master_partname,
    part_common_slide_name_from_path as _part_common_slide_name_from_path,
    presentation_partname as _presentation_partname,
    slide_metadata as _slide_metadata,
    slide_name as _slide_name,
    slide_notes_partname as _slide_notes_partname,
    slide_notes_partname_for_part as _slide_notes_partname_for_part,
)
from .slide_payloads import (
    load_shape_payloads as _load_shape_payloads,
    load_slide_layout_placeholder_payloads as _load_slide_layout_placeholder_payloads,
)
from .text_facade_inspection import _shape_run_count_payload

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"

class SlideLayoutCollection(Sequence["SlideLayout"]):
    def __init__(
        self,
        presentation: Presentation,
        layouts: list["SlideLayout"],
        partname: str | None = None,
        parent: "SlideMaster | None" = None,
    ) -> None:
        self._presentation = presentation
        self._layouts = layouts
        self._partname = partname
        self._parent = parent

    def __getitem__(self, index: int | slice) -> "SlideLayout | list[SlideLayout]":
        return self._layouts[index]

    def __iter__(self) -> Iterator["SlideLayout"]:
        return iter(self._layouts)

    def __len__(self) -> int:
        return len(self._layouts)

    def index(self, slide_layout: "SlideLayout") -> int:
        for index, layout in enumerate(self._layouts):
            if layout is slide_layout:
                return index
        raise ValueError("layout not in this SlideLayouts collection")

    def get_by_name(self, name: str) -> "SlideLayout | None":
        for layout in self._layouts:
            if layout.name == name:
                return layout
        return None

    def remove(self, slide_layout: "SlideLayout") -> None:
        if slide_layout.used_by_slides:
            raise ValueError("cannot remove slide-layout in use by one or more slides")
        self.index(slide_layout)
        self._layouts.remove(slide_layout)
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
    def parent(self) -> "SlideMaster":
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

    @property
    def slide_master(self) -> "SlideMaster":
        parent = getattr(self, "_parent", None)
        if parent is not None:
            return parent
        for master in self._presentation.slide_masters:
            layout_parts = list(master._payload.get("layout_parts") or [])
            if not layout_parts or self.partname in layout_parts:
                return master
        return self._presentation.slide_master

    @property
    def used_by_slides(self) -> tuple["Slide", ...]:
        return tuple(
            slide
            for slide in self._presentation.slides
            if slide.slide_layout.partname == self.partname
        )

    @property
    def element(self) -> XmlElementProxy:
        return _package_xml_element(self._presentation.path, self.partname)

    @property
    def background(self) -> "Background":
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
    def __init__(self, presentation: Presentation, masters: list["SlideMaster"]) -> None:
        self._presentation = presentation
        self._masters = masters

    def __getitem__(self, index: int) -> "SlideMaster":
        return self._masters[index]

    def __iter__(self) -> Iterator["SlideMaster"]:
        return iter(self._masters)

    def __len__(self) -> int:
        return len(self._masters)

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
        return _package_xml_element(self._presentation.path, self.partname)

    @property
    def background(self) -> "Background":
        return Background(self._presentation, self.partname)

    @property
    def name(self) -> str:
        return str(self._payload.get("name") or "")

    @property
    def slide_layouts(self) -> SlideLayoutCollection:
        layout_parts = list(self._payload.get("layout_parts") or [])
        layouts = [
            layout
            for layout in self._presentation.slide_layouts
            if not layout_parts or layout.partname in layout_parts
        ]
        return SlideLayoutCollection(
            self._presentation,
            layouts,
            partname=self.partname,
            parent=self,
        )


class SlideCollection(Sequence["Slide"]):
    def __init__(self, presentation: Presentation, slides: list["Slide"]) -> None:
        self._presentation = presentation
        self._slides = slides

    @overload
    def __getitem__(self, index: int) -> "Slide":
        ...

    @overload
    def __getitem__(self, index: slice) -> list["Slide"]:
        ...

    def __getitem__(self, index: int | slice) -> "Slide | list[Slide]":
        return self._slides[index]

    def __iter__(self) -> Iterator["Slide"]:
        return iter(self._slides)

    def __len__(self) -> int:
        return len(self._slides)

    def index(self, slide: "Slide") -> int:
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
        root = _package_xml_element(
            self._presentation.path,
            _presentation_partname(self._presentation.path),
        )
        element = root.find(f"{{{P_NS}}}sldIdLst")
        if element is None:
            raise AttributeError("slide id list XML element is unavailable")
        return element

    def get(self, slide_id: int, default: Any = None) -> "Slide | Any":
        for slide in self._slides:
            if slide.slide_id == slide_id:
                return slide
        return default

    def move(self, old_index: int, new_index: int) -> None:
        """Move one slide while preserving its package and relationship identity."""
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
        self._presentation._queue_slide_reorder(
            [candidate._index for candidate in self._slides]
        )

    def add_slide(self, slide_layout: SlideLayout) -> "Slide":
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

    def duplicate(self, source: "Slide") -> "Slide":
        """Append a deep copy of ``source`` while sharing only safe package parts."""
        if not isinstance(source, Slide):
            raise TypeError("source must be a wolfppt Slide")
        if source._presentation is not self._presentation:
            raise ValueError("slide does not belong to this presentation")
        source_partname = source.partname
        if not source_partname:
            raise ValueError("slide does not belong to this presentation")
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
        }
        slide = Slide(self._presentation, len(self._slides), payload)
        self._slides.append(slide)
        return slide
    def remove(self, slide: "Slide") -> None:
        """Remove a slide from the collection and queue package deletion."""
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
        is_pending = not bool(slide.partname) or bool(slide._payload.get("_pending_creation"))
        deleted_index = self._slides.index(slide)
        deleted_slide_index = slide._index
        slide._deleted = True
        self._slides.pop(deleted_index)

        if is_pending:
            token = slide._payload.get("_creation_token")
            creation_index = None
            if token is not None:
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
            if creation_index is None or not (0 <= creation_index < len(self._presentation._slide_creations)):
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
            survivor._index: new_index
            for new_index, survivor in enumerate(self._slides)
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
        self._shapes: ShapeCollection | None = None
        self._placeholders: PlaceholderCollection | None = None
        if "shapes" in payload:
            self._set_shape_payloads(list(payload.get("shapes") or []))

    @property
    def shapes(self) -> ShapeCollection:
        self._ensure_shape_collections()
        assert self._shapes is not None
        return self._shapes

    @property
    def placeholders(self) -> PlaceholderCollection:
        self._ensure_shape_collections()
        assert self._placeholders is not None
        return self._placeholders

    def _ensure_shape_collections(self) -> None:
        if self._shapes is not None and self._placeholders is not None:
            return
        shape_payloads = self._payload.get("shapes")
        if shape_payloads is None:
            from . import native

            try:
                slide_payload = native.summarize_slide(self._presentation.path, self._index)
            except RuntimeError:
                slide_payload = dict(native.summarize(self._presentation.path).slides[self._index])
            self._payload.update(slide_payload)
            shape_payloads = list(slide_payload.get("shapes") or [])
        self._set_shape_payloads(list(shape_payloads or []))

    def _set_shape_payloads(self, shape_payloads: list[dict[str, Any]]) -> None:
        self._payload["shapes"] = shape_payloads
        shapes: list[Shape] = []
        table_index = 0
        run_start_index = 0
        for shape_index, shape in enumerate(shape_payloads):
            shapes.append(Shape(self, shape_index, shape, table_index, run_start_index))
            table_index += len(shape.get("tables", []))
            run_start_index += _shape_run_count_payload(shape)
        self._shapes = ShapeCollection(self, shapes)
        self._placeholders = PlaceholderCollection(self, shapes)

    def _rebase_live_indices(self, slide_index: int) -> None:
        self._index = slide_index
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
        self._presentation._queue_slide_name(self._index, name)

    @property
    def slide_layout(self) -> SlideLayout:
        layout_index = self._payload.get("layout_index")
        if isinstance(layout_index, int):
            return self._presentation.slide_layouts[layout_index]
        layout_part = _slide_metadata(self).get("layout_part")
        if not layout_part:
            raise AttributeError("slide layout relationship is unavailable")
        for layout in self._presentation.slide_layouts:
            if layout.partname == layout_part:
                return layout
        raise AttributeError("slide layout relationship is unavailable")

    @property
    def follow_master_background(self) -> bool:
        return bool(_slide_metadata(self).get("follow_master_background", True))

    @property
    def has_notes_slide(self) -> bool:
        if self._index in self._presentation._notes_slide_adds:
            return True
        return bool(_slide_metadata(self).get("has_notes_slide", False))

    @property
    def notes_slide(self) -> "NotesSlide":
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
        return NotesSlide(self, partname)

    @property
    def background(self) -> "Background":
        return Background(self._presentation, self.partname)

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


class NotesSlide:
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
    def background(self) -> "Background":
        return Background(self._presentation, self.partname)

    @property
    def name(self) -> str:
        return _part_common_slide_name_from_path(self._presentation.path, self.partname)

    @property
    def notes_placeholder(self) -> "Shape":
        for shape in self.shapes:
            if _placeholder_type_xml(shape) == "body":
                return shape
        raise AttributeError("notes placeholder is unavailable")

    @property
    def notes_text_frame(self) -> "TextFrame":
        return self.notes_placeholder.text_frame

    def clone_master_placeholders(self, notes_master: Any) -> None:
        cloneable = [
            placeholder
            for placeholder in getattr(notes_master, "placeholders", ())
            if _placeholder_type_xml(placeholder) not in {"hdr", "dt", "ftr"}
        ]
        for placeholder in cloneable:
            self.shapes.clone_placeholder(placeholder)


class NotesSlideShapes(Sequence["Shape"]):
    def __init__(self, notes_slide: NotesSlide, shapes: list["Shape"]) -> None:
        self._notes_slide = notes_slide
        self._shapes = shapes
        self._turbo_add_enabled = False

    def __getitem__(self, index: int | slice) -> "Shape | list[Shape]":
        return self._shapes[index]

    def __iter__(self) -> Iterator["Shape"]:
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
        spec = self._append_placeholder_clone(placeholder)
        self._notes_slide._presentation._queue_part_placeholder_add(
            self._notes_slide.partname,
            spec,
        )

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


class NotesMaster:
    def __init__(self, presentation: Presentation, partname: str) -> None:
        self._presentation = presentation
        self._partname = partname
        shapes = [
            MasterShape(self, shape_index, shape)
            for shape_index, shape in enumerate(
                _load_shape_payloads(presentation.path, partname)
            )
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
    def background(self) -> "Background":
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
