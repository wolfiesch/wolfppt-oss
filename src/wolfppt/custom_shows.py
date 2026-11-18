"""Public custom-show facade and PresentationML package mutation."""

from __future__ import annotations

import posixpath
import zipfile
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .package_parts import copy_package_with_replacements, resolve_package_target
from .slide_metadata import presentation_partname

if TYPE_CHECKING:
    from .presentation import Presentation
    from .presentation_slides import Slide

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"


class CustomShowRefusal(ValueError):
    """Raised when a custom-show mutation cannot be applied safely."""


@dataclass(frozen=True)
class CustomShowRecord:
    show_id: int
    name: str
    slides: tuple[Any, ...]


class CustomShow:
    def __init__(
        self,
        collection: CustomShowCollection,
        show_id: int,
        name: str,
        slides: Iterable[Slide],
    ) -> None:
        self._collection = collection
        self._id = show_id
        self._name = name
        self._slides = list(slides)

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        name = self._collection._validate_name(value, exclude=self)
        if name == self._name:
            return
        self._name = name
        self._collection._mark_dirty()

    @property
    def slides(self) -> tuple[Slide, ...]:
        return tuple(self._slides)

    @slides.setter
    def slides(self, value: Iterable[Slide]) -> None:
        slides = self._collection._validate_slides(value)
        if slides == self._slides:
            return
        self._slides = slides
        self._collection._mark_dirty()

    def add_slide(self, slide: Slide, index: int | None = None) -> None:
        self._collection._validate_slides((slide,))
        if index is None:
            index = len(self._slides)
        if not isinstance(index, int) or not 0 <= index <= len(self._slides):
            raise IndexError("custom-show insertion index out of range")
        self._slides.insert(index, slide)
        self._collection._mark_dirty()

    def remove_slide(self, slide: Slide) -> None:
        try:
            self._slides.remove(slide)
        except ValueError as exc:
            raise ValueError("slide is not in this custom show") from exc
        self._collection._mark_dirty()

    def move_slide(self, old_index: int, new_index: int) -> None:
        length = len(self._slides)
        if not isinstance(old_index, int) or not isinstance(new_index, int):
            raise TypeError("custom-show slide indexes must be integers")
        if not 0 <= old_index < length or not 0 <= new_index < length:
            raise IndexError("custom-show slide index out of range")
        if old_index == new_index:
            return
        slide = self._slides.pop(old_index)
        self._slides.insert(new_index, slide)
        self._collection._mark_dirty()


class CustomShowCollection(Sequence[CustomShow]):
    def __init__(
        self, presentation: Presentation, shows: Iterable[CustomShowRecord]
    ) -> None:
        self._presentation = presentation
        self._shows = [
            CustomShow(self, record.show_id, record.name, record.slides)
            for record in shows
        ]
        self._next_id = max((show.id for show in self._shows), default=0) + 1

    def __getitem__(self, index: int | slice) -> CustomShow | list[CustomShow]:
        return self._shows[index]

    def __iter__(self) -> Iterator[CustomShow]:
        return iter(self._shows)

    def __len__(self) -> int:
        return len(self._shows)

    def get_by_name(self, name: str) -> CustomShow | None:
        return next((show for show in self._shows if show.name == name), None)

    def add(self, name: str, slides: Iterable[Slide] = ()) -> CustomShow:
        normalized_name = self._validate_name(name)
        members = self._validate_slides(slides)
        show = CustomShow(self, self._next_id, normalized_name, members)
        self._next_id += 1
        self._shows.append(show)
        self._mark_dirty()
        return show

    def remove(self, show: CustomShow) -> None:
        try:
            self._shows.remove(show)
        except ValueError as exc:
            raise ValueError(
                "custom show does not belong to this presentation"
            ) from exc
        self._mark_dirty()

    def move(self, old_index: int, new_index: int) -> None:
        length = len(self._shows)
        if not isinstance(old_index, int) or not isinstance(new_index, int):
            raise TypeError("custom-show indexes must be integers")
        if not 0 <= old_index < length or not 0 <= new_index < length:
            raise IndexError("custom-show index out of range")
        if old_index == new_index:
            return
        show = self._shows.pop(old_index)
        self._shows.insert(new_index, show)
        self._mark_dirty()

    def _validate_name(self, value: Any, exclude: CustomShow | None = None) -> str:
        if not isinstance(value, str):
            raise TypeError("custom-show name must be a str")
        if not value:
            raise ValueError("custom-show name cannot be empty")
        if any(show is not exclude and show.name == value for show in self._shows):
            raise ValueError(f"custom-show name already exists: {value!r}")
        return value

    def _validate_slides(self, value: Iterable[Slide]) -> list[Slide]:
        try:
            slides = list(value)
        except TypeError as exc:
            raise TypeError("custom-show slides must be iterable") from exc
        for slide in slides:
            if getattr(slide, "_presentation", None) is not self._presentation:
                raise ValueError("custom-show slide belongs to another presentation")
            if (
                getattr(slide, "_deleted", False)
                or slide not in self._presentation.slides
            ):
                raise ValueError(
                    "custom-show slide is not available in this presentation"
                )
        return slides

    def _discard_slide(self, removed: Slide) -> None:
        changed = False
        for show in self._shows:
            remaining = [
                slide
                for slide in show._slides
                if slide is not removed
            ]
            if len(remaining) != len(show._slides):
                show._slides = remaining
                changed = True
        if changed:
            self._mark_dirty()

    def _records_for_save(self) -> list[CustomShowRecord]:
        return [
            CustomShowRecord(show.id, show.name, tuple(show.slides))
            for show in self._shows
        ]

    def _mark_dirty(self) -> None:
        self._presentation._queue_custom_show_edits(self._records_for_save())


def load_custom_shows(presentation: Presentation) -> CustomShowCollection:
    path = presentation.path
    try:
        with zipfile.ZipFile(path) as package:
            presentation_part = presentation_partname(path)
            root = ET.fromstring(package.read(presentation_part))
            rels = _presentation_slide_relationships(package, presentation_part)
    except (FileNotFoundError, KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise CustomShowRefusal("custom-show source package is unavailable") from exc
    slide_by_part = {
        str(slide.partname).lstrip("/"): slide
        for slide in presentation.slides
        if not slide._payload.get("_pending_creation") and not slide._deleted
    }
    shows: list[CustomShowRecord] = []
    list_element = root.find(f"{{{P_NS}}}custShowLst")
    if list_element is not None:
        for element in list_element.findall(f"{{{P_NS}}}custShow"):
            try:
                show_id = int(element.attrib["id"])
                name = element.attrib["name"]
            except (KeyError, ValueError) as exc:
                raise CustomShowRefusal(
                    "custom show is missing a valid id or name"
                ) from exc
            if show_id <= 0 or not name:
                raise CustomShowRefusal("custom show has an invalid id or name")
            members = []
            for member in element.findall(f"{{{P_NS}}}sldLst/{{{P_NS}}}sld"):
                relationship_id = member.attrib.get(f"{{{R_NS}}}id")
                target = rels.get(relationship_id or "")
                slide = None if target is None else slide_by_part.get(target)
                if slide is not None:
                    members.append(slide)
            shows.append(CustomShowRecord(show_id, name, tuple(members)))
    return CustomShowCollection(presentation, shows)


def apply_custom_show_edits(
    input_path: Path,
    output_path: Path,
    records: list[CustomShowRecord] | None,
    staged_slide_parts: dict[Any, str] | None = None,
) -> None:
    with zipfile.ZipFile(input_path) as package:
        presentation_part = presentation_partname(input_path)
        root = ET.fromstring(package.read(presentation_part))
        relationships = _presentation_slide_relationships(package, presentation_part)
        if records is None:
            if not _prune_deleted_show_members(root, relationships):
                copy_package_with_replacements(input_path, output_path, {})
                return
        else:
            _replace_custom_show_list(
                root, records, relationships, staged_slide_parts or {}
            )
        ET.register_namespace(
            "a", "http://schemas.openxmlformats.org/drawingml/2006/main"
        )
        ET.register_namespace("p", P_NS)
        ET.register_namespace("r", R_NS)
        replacement = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    copy_package_with_replacements(
        input_path,
        output_path,
        {presentation_part: replacement},
    )


def _presentation_slide_relationships(
    package: zipfile.ZipFile,
    presentation_part: str,
) -> dict[str, str]:
    rels_part = f"{posixpath.dirname(presentation_part)}/_rels/{Path(presentation_part).name}.rels"
    root = ET.fromstring(package.read(rels_part))
    return {
        relationship.attrib["Id"]: resolve_package_target(
            presentation_part, relationship.attrib.get("Target", "")
        )
        for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship")
        if relationship.attrib.get("Type") == REL_SLIDE
        and relationship.attrib.get("Id")
    }


def _prune_deleted_show_members(
    root: ET.Element, relationships: dict[str, str]
) -> bool:
    changed = False
    list_element = root.find(f"{{{P_NS}}}custShowLst")
    if list_element is None:
        return False
    for member in list_element.findall(f".//{{{P_NS}}}sld"):
        relationship_id = member.attrib.get(f"{{{R_NS}}}id")
        if relationship_id not in relationships:
            parent = next(
                (
                    candidate
                    for candidate in list_element.iter()
                    if member in list(candidate)
                ),
                None,
            )
            if parent is not None:
                parent.remove(member)
                changed = True
    return changed


def _replace_custom_show_list(
    root: ET.Element,
    records: list[CustomShowRecord],
    relationships: dict[str, str],
    staged_slide_parts: dict[Any, str],
) -> None:
    existing = root.find(f"{{{P_NS}}}custShowLst")
    if existing is not None:
        root.remove(existing)
    relationship_ids = {
        target: relationship_id for relationship_id, target in relationships.items()
    }
    show_list = ET.Element(f"{{{P_NS}}}custShowLst")
    for record in records:
        show = ET.SubElement(
            show_list,
            f"{{{P_NS}}}custShow",
            {"name": record.name, "id": str(record.show_id)},
        )
        slide_list = ET.SubElement(show, f"{{{P_NS}}}sldLst")
        for slide in record.slides:
            if slide._deleted:
                raise CustomShowRefusal("custom-show member has been deleted")
            if slide._payload.get("_pending_creation"):
                # A pending duplicate's partname is its copy source, not its
                # identity. Resolve the save-local creation without mutating it.
                partname = staged_slide_parts.get(
                    slide._payload.get("_creation_token"), ""
                ).lstrip("/")
            else:
                partname = str(slide.partname).lstrip("/")
            relationship_id = relationship_ids.get(partname)
            if relationship_id is None:
                raise CustomShowRefusal(
                    "custom-show member has no materialized slide relationship"
                )
            ET.SubElement(
                slide_list,
                f"{{{P_NS}}}sld",
                {f"{{{R_NS}}}id": relationship_id},
            )
    trailing_tags = {
        f"{{{P_NS}}}{name}"
        for name in (
            "photoAlbum",
            "custDataLst",
            "kinsoku",
            "defaultTextStyle",
            "modifyVerifier",
            "extLst",
        )
    }
    insertion_index = next(
        (index for index, child in enumerate(root) if child.tag in trailing_tags),
        len(root),
    )
    root.insert(insertion_index, show_list)
