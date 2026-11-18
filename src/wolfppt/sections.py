"""Presentation sections facade collection and section models.

Implements Presentation.sections collection conforming to OpenXML CT_SectionLst / CT_Section.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from .presentation_slides import Slide

from .section_edits import (
    SectionEditsSnapshot,
    SectionRefusalError,
    SectionSpec,
)
from .section_xml import (
    generate_section_id,
    read_presentation_slide_ids,
    read_sections_from_element,
)
from .slide_zoom_targets import section_zoom_hosts


class Section:
    """A presentation section partitioning a contiguous sequence of slides."""

    def __init__(
        self,
        collection: SectionCollection,
        id: str,
        name: str,
        slide_ids: list[int] | None = None,
        start_index: int = 0,
    ) -> None:
        self._collection = collection
        self._id = id
        self._name = name
        self._slide_ids: list[int] = list(slide_ids or [])
        self._start_index = start_index

    @property
    def id(self) -> str:
        """The persistent unique GUID of this section."""
        return self._id

    @property
    def name(self) -> str:
        """The display name of this section."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"section name must be a string, got {type(value).__name__}"
            )
        self._name = value
        self._collection._queue_edit()

    @property
    def slide_ids(self) -> tuple[int, ...]:
        """Tuple of integer slide IDs belonging to this section."""
        self._collection._settle()
        presentation_slides = self._collection._presentation.slides
        if presentation_slides:
            slide_id_set = set(self._slide_ids)
            return tuple(
                s.slide_id for s in presentation_slides if s.slide_id in slide_id_set
            )
        return tuple(self._slide_ids)

    @property
    def slides(self) -> list[Slide]:
        """List of Slide objects belonging to this section in presentation order."""
        self._collection._settle()
        presentation_slides = self._collection._presentation.slides
        slide_id_set = set(self._slide_ids)
        return [s for s in presentation_slides if s.slide_id in slide_id_set]

    @property
    def slide_count(self) -> int:
        """Number of slides currently belonging to this section."""
        return len(self.slides)

    def remove(self) -> None:
        """Remove this section from the presentation."""
        self._collection.remove(self)

    def move(self, new_index: int | Section | str) -> None:
        """Move this section to a new index or target section."""
        self._collection.move(self, new_index)

    def __len__(self) -> int:
        return len(self.slides)

    def __contains__(self, item: Any) -> bool:
        active_ids = self.slide_ids
        if hasattr(item, "slide_id"):
            return item.slide_id in active_ids
        if isinstance(item, int):
            return item in active_ids
        if isinstance(item, str) and item.isdigit():
            return int(item) in active_ids
        return False

    def __repr__(self) -> str:
        return f"<Section name={self.name!r} id={self.id!r} slides={len(self.slides)}>"


class _SettledSectionEdits(SectionEditsSnapshot):
    """Section edits that settle membership when the save reads them.

    Slides added after the last section edit still join a section, because the
    save sees the collection as it stands rather than as it stood when queued.
    """

    def __init__(self, collection: SectionCollection) -> None:
        self._collection = collection

    @property  # type: ignore[override]
    def sections(self) -> list[SectionSpec]:
        return self._collection._snapshot().sections

    @property  # type: ignore[override]
    def known_slide_ids(self) -> set[int]:
        return self._collection._snapshot().known_slide_ids

    @property  # type: ignore[override]
    def cleared(self) -> bool:
        return not self._collection._sections


class SectionCollection:
    """Collection of presentation sections."""

    def __init__(self, presentation: Any) -> None:
        self._presentation = presentation
        self._sections: list[Section] = []
        self._loaded: bool = False
        self._known_slide_ids: set[int] = set()
        self._load()

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        source_path = getattr(self._presentation, "_source_path", None)
        if source_path is None or not Path(source_path).is_file():
            # Initial slides if available
            slides = getattr(self._presentation, "slides", [])
            for s in slides:
                self._known_slide_ids.add(s.slide_id)
            return

        pres_slide_ids: list[int] = []
        try:
            with zipfile.ZipFile(source_path) as pkg:
                xml_bytes = pkg.read("ppt/presentation.xml")
            root = ET.fromstring(xml_bytes)
            records = read_sections_from_element(root)
            pres_slide_ids = read_presentation_slide_ids(root)
            self._known_slide_ids.update(pres_slide_ids)
        except (KeyError, FileNotFoundError, ET.ParseError, zipfile.BadZipFile):
            records = []

        # An empty section starts where the previous section ended.
        position = {slide_id: index for index, slide_id in enumerate(pres_slide_ids)}
        cursor = 0
        for rec in records:
            self._known_slide_ids.update(rec.slide_ids)
            indices = [position[sid] for sid in rec.slide_ids if sid in position]
            start = min(indices) if indices else cursor
            cursor = max(indices) + 1 if indices else cursor
            sec = Section(
                collection=self,
                id=rec.id,
                name=rec.name,
                slide_ids=list(rec.slide_ids),
                start_index=start,
            )
            self._sections.append(sec)

    def _section_start_index(self, sec: Section) -> int:
        slides = self._presentation.slides
        for i, s in enumerate(slides):
            if s.slide_id in sec._slide_ids:
                return i
        return getattr(sec, "_start_index", len(slides))

    def _adopt_new_slides(self) -> bool:
        """Give every slide added since the collection last looked a section.

        A new slide joins the section just before the one owning the next
        sectioned slide, or the last section when none follows: appended slides
        land in the final section, and an empty section keeps the slides added
        where it starts. Returns whether any slide was adopted.
        """
        slides = list(self._presentation.slides)
        fresh = [
            pos
            for pos, slide in enumerate(slides)
            if slide.slide_id not in self._known_slide_ids
        ]
        self._known_slide_ids.update(slide.slide_id for slide in slides)
        if not fresh or not self._sections:
            return False
        owner = {
            sid: index
            for index, sec in enumerate(self._sections)
            for sid in sec._slide_ids
        }
        for pos in fresh:
            following = next(
                (owner[s.slide_id] for s in slides[pos + 1 :] if s.slide_id in owner),
                None,
            )
            target = len(self._sections) - 1 if following is None else following - 1
            self._sections[max(target, 0)]._slide_ids.append(slides[pos].slide_id)
        return True

    def _settle(self) -> None:
        """Adopt new slides and queue the membership change for save."""
        if self._adopt_new_slides():
            self._queue_edit()

    def _snapshot(self) -> SectionEditsSnapshot:
        self._adopt_new_slides()
        slides = self._presentation.slides
        specs: list[SectionSpec] = []
        for sec in self._sections:
            active_slides = [s for s in slides if s.slide_id in sec._slide_ids]
            indices = []
            for s in active_slides:
                try:
                    indices.append(slides.index(s))
                except (ValueError, AttributeError):
                    pass
            sids = [s.slide_id for s in active_slides]
            self._known_slide_ids.update(sids)
            specs.append(
                SectionSpec(
                    id=sec.id,
                    name=sec.name,
                    slide_ids=sids,
                    slide_indices=indices,
                )
            )
        return SectionEditsSnapshot(
            sections=specs,
            known_slide_ids=set(self._known_slide_ids),
            cleared=(len(self._sections) == 0),
        )

    def _queue_edit(self) -> None:
        snapshot = _SettledSectionEdits(self)
        queue_fn = getattr(self._presentation, "_queue_section_edits", None)
        if callable(queue_fn):
            queue_fn(snapshot)
        else:
            self._presentation._section_edits = snapshot

    def __len__(self) -> int:
        return len(self._sections)

    def __iter__(self) -> Iterator[Section]:
        return iter(self._sections)

    def __getitem__(self, key: int | slice | str) -> Section | list[Section]:
        if isinstance(key, int):
            return self._sections[key]
        if isinstance(key, slice):
            return self._sections[key]
        if isinstance(key, str):
            norm_key = key.strip().upper()
            for sec in self._sections:
                if sec.name == key or sec.id.upper() == norm_key:
                    return sec
            raise KeyError(f"no section named or identified by {key!r}")
        raise TypeError(f"section index must be int or str, got {type(key).__name__}")

    def get(self, key: str, default: Any = None) -> Section | Any:
        """Find section by name or GUID identifier, returning default if not found."""
        try:
            return self[key]
        except (KeyError, TypeError):
            return default

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, Section):
            return item in self._sections
        if isinstance(item, str):
            return self.get(item) is not None
        return False

    def add(self, name: str | None = None, slide_index: int = 0) -> Section:
        """Add a new section starting at slide_index.

        Partitions slides into contiguous sections in presentation order.
        """
        self._settle()
        slides = self._presentation.slides
        n_slides = len(slides)

        if not isinstance(slide_index, int):
            raise TypeError(
                f"slide_index must be an integer, got {type(slide_index).__name__}"
            )
        if slide_index < 0:
            slide_index = n_slides + slide_index
        if slide_index < 0 or slide_index > n_slides:
            raise IndexError(f"slide_index {slide_index} out of range (0..{n_slides})")

        if name is None:
            name = f"Section {len(self._sections) + 1}"

        new_sec = Section(
            collection=self,
            id=generate_section_id(),
            name=name,
        )
        new_sec._start_index = slide_index

        # Determine insertion position among ordered sections
        insert_pos = 0
        for i, s in enumerate(self._sections):
            s_start = self._section_start_index(s)
            if slide_index < s_start:
                insert_pos = i
                break
            insert_pos = i + 1

        self._sections.insert(insert_pos, new_sec)

        # Repartition slides contiguously across sections
        starts = [
            slide_index if s is new_sec else self._section_start_index(s)
            for s in self._sections
        ]

        for i, s in enumerate(self._sections):
            st = starts[i]
            en = starts[i + 1] if i + 1 < len(starts) else n_slides
            sec_slides = slides[st:en]
            s._slide_ids = [sl.slide_id for sl in sec_slides]
            s._start_index = st
            self._known_slide_ids.update(s._slide_ids)

        self._queue_edit()
        return new_sec

    def remove(self, section: Section | int | str) -> None:
        """Remove a section, merging its slides into the preceding or following section."""
        if isinstance(section, int):
            sec = self._sections[section]
        elif isinstance(section, str):
            res = self.get(section)
            if res is None:
                raise KeyError(f"no section {section!r}")
            sec = res
        elif isinstance(section, Section):
            sec = section
        else:
            raise TypeError(f"cannot remove section of type {type(section).__name__}")

        self._settle()
        self._refuse_zoom_targets([sec])
        idx = self._sections.index(sec)
        self._sections.remove(sec)

        if self._sections:
            # Merge slides into preceding section (or following if first)
            merge_target = self._sections[idx - 1] if idx > 0 else self._sections[0]
            presentation_slides = self._presentation.slides
            combined = [
                s.slide_id
                for s in presentation_slides
                if s.slide_id in sec._slide_ids or s.slide_id in merge_target._slide_ids
            ]
            merge_target._slide_ids = combined
            merge_target._start_index = self._section_start_index(merge_target)
            self._known_slide_ids.update(combined)

        self._queue_edit()

    def move(
        self,
        section: Section | int | str,
        new_index: int | Section | str,
    ) -> None:
        """Move a section and its slides to a new index or target section position.

        Moves the section together with all its contiguous slides while preserving
        stable slide identities, membership, unrelated parts, save/reopen, and
        same-object repeated-save semantics.
        Refuses invalid targets without mutating state.
        """
        self._settle()
        n_sections = len(self._sections)
        if n_sections == 0:
            raise IndexError("cannot move section in empty collection")

        # 1. Resolve source section and its current index
        if isinstance(section, bool):
            raise TypeError("section must be an int, str, or Section, not bool")
        elif isinstance(section, int):
            norm_old = section if section >= 0 else n_sections + section
            if norm_old < 0 or norm_old >= n_sections:
                raise IndexError(
                    f"section index {section} out of range (0..{n_sections - 1})"
                )
            old_index = norm_old
            sec = self._sections[old_index]
        elif isinstance(section, str):
            res = self.get(section)
            if res is None:
                raise KeyError(f"no section named or identified by {section!r}")
            sec = res
            old_index = self._sections.index(sec)
        elif isinstance(section, Section):
            if section not in self._sections:
                raise ValueError(
                    f"section {section!r} does not belong to this presentation"
                )
            sec = section
            old_index = self._sections.index(sec)
        else:
            raise TypeError(
                f"expected Section, int, or str for section, got {type(section).__name__}"
            )

        # 2. Resolve destination target_index
        if isinstance(new_index, bool):
            raise TypeError("new_index must be an int, str, or Section, not bool")
        elif isinstance(new_index, int):
            norm_new = new_index if new_index >= 0 else n_sections + new_index
            if norm_new < 0 or norm_new >= n_sections:
                raise IndexError(
                    f"new_index {new_index} out of range (0..{n_sections - 1})"
                )
            target_index = norm_new
        elif isinstance(new_index, str):
            target_sec = self.get(new_index)
            if target_sec is None:
                raise KeyError(f"no section named or identified by {new_index!r}")
            target_index = self._sections.index(target_sec)
        elif isinstance(new_index, Section):
            if new_index not in self._sections:
                raise ValueError(
                    f"section {new_index!r} does not belong to this presentation"
                )
            target_index = self._sections.index(new_index)
        else:
            raise TypeError(
                f"expected Section, int, or str for new_index, got {type(new_index).__name__}"
            )

        # 3. No-op check
        if old_index == target_index:
            return

        # 4. Validate slide contiguity across all sections before state mutation
        presentation_slides = self._presentation.slides
        slides_list = getattr(presentation_slides, "_slides", None)
        active_slides_by_sec: dict[str, list[Any]] = {}
        for s in self._sections:
            sec_slides = [
                sl for sl in presentation_slides if sl.slide_id in s._slide_ids
            ]
            if sec_slides:
                positions = [presentation_slides.index(sl) for sl in sec_slides]
                expected = list(range(positions[0], positions[0] + len(positions)))
                if positions != expected:
                    raise SectionRefusalError(
                        f"section {s.name!r} has non-contiguous slides in presentation order: "
                        f"slide ids {s.slide_ids}"
                    )
            active_slides_by_sec[s.id] = sec_slides

        # 5. Reorder the sections list
        moved_sec = self._sections.pop(old_index)
        self._sections.insert(target_index, moved_sec)

        # 6. Reorder slides in presentation to match the new section layout
        if slides_list is not None:
            moving_slides = active_slides_by_sec[moved_sec.id]
            if moving_slides:
                moving_set = set(moving_slides)
                remaining_slides = [sl for sl in slides_list if sl not in moving_set]

                # Determine insertion position among remaining_slides
                if target_index == 0:
                    insert_at = None
                    for next_sec in self._sections[1:]:
                        next_slides = active_slides_by_sec[next_sec.id]
                        if next_slides:
                            for idx, sl in enumerate(remaining_slides):
                                if sl is next_slides[0]:
                                    insert_at = idx
                                    break
                            if insert_at is not None:
                                break
                    if insert_at is None:
                        insert_at = 0
                else:
                    insert_at = None
                    for prev_sec in reversed(self._sections[:target_index]):
                        prev_slides = active_slides_by_sec[prev_sec.id]
                        if prev_slides:
                            for idx, sl in enumerate(remaining_slides):
                                if sl is prev_slides[-1]:
                                    insert_at = idx + 1
                                    break
                            if insert_at is not None:
                                break
                    if insert_at is None:
                        for next_sec in self._sections[target_index + 1 :]:
                            next_slides = active_slides_by_sec[next_sec.id]
                            if next_slides:
                                for idx, sl in enumerate(remaining_slides):
                                    if sl is next_slides[0]:
                                        insert_at = idx
                                        break
                                if insert_at is not None:
                                    break
                        if insert_at is None:
                            insert_at = len(remaining_slides)

                new_slides = (
                    remaining_slides[:insert_at]
                    + moving_slides
                    + remaining_slides[insert_at:]
                )
                slides_list[:] = new_slides

                # Queue slide reorder on presentation
                new_order = [s._index for s in slides_list]
                if new_order == list(range(len(slides_list))):
                    self._presentation._slide_order = None
                else:
                    self._presentation._queue_slide_reorder(new_order)

        # 7. Update _start_index for each section
        for s in self._sections:
            s._start_index = self._section_start_index(s)

        # 8. Queue section edits for save
        self._queue_edit()

    def clear(self) -> None:
        """Remove all sections from the presentation."""
        self._refuse_zoom_targets(self._sections)
        self._sections.clear()
        self._queue_edit()

    def _refuse_zoom_targets(self, doomed: list[Section]) -> None:
        """Refuse, before any state changes, to delete a section a zoom opens."""
        source_path = getattr(self._presentation, "_source_path", None)
        if not doomed or source_path is None or not Path(source_path).is_file():
            return
        live_parts = [
            slide.partname.lstrip("/")
            for slide in self._presentation.slides
            if slide.partname and not slide._payload.get("_pending_creation")
        ]
        with zipfile.ZipFile(source_path) as pkg:
            hosts = section_zoom_hosts(pkg, live_parts)
        for sec in doomed:
            hosting = hosts.get(sec.id.strip().upper())
            if hosting:
                raise SectionRefusalError(
                    f"section {sec.name!r} is the target of a section zoom on "
                    f"{', '.join(hosting)}; remove the zoom before the section"
                )

    def __repr__(self) -> str:
        return f"<SectionCollection len={len(self._sections)}>"


__all__ = [
    "Section",
    "SectionCollection",
    "SectionRefusalError",
]
