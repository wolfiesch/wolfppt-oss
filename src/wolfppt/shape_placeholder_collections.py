"""Placeholder and master shape collection facades."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from .package_parts import (
    PackagePart,
    XmlElementProxy,
    package_xml_element as _package_xml_element,
)
from .shape_core_facade import MasterShape, Shape
from .shape_inspection import (
    _next_placeholder_name,
    _next_shape_id,
    _placeholder_basename,
    _placeholder_raw_value,
    _placeholder_type_xml,
)

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


class PlaceholderCollection(Sequence[Shape]):
    def __init__(self, slide: Any, shapes: Sequence[Any]) -> None:
        self._slide = slide
        self._placeholders = [shape for shape in shapes if shape.is_placeholder]

    def __getitem__(self, idx: int) -> Shape:
        for shape in self._placeholders:
            if shape.placeholder_format.idx == idx:
                return shape
        raise KeyError(f"no placeholder on this slide with idx == {idx}")

    def __iter__(self) -> Iterator[Shape]:
        return iter(self._placeholders)

    def __len__(self) -> int:
        return len(self._placeholders)

    @property
    def part(self) -> PackagePart:
        return self._slide.part

    @property
    def parent(self) -> Any:
        return self._slide

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._slide._presentation.path,
            self._slide.partname,
        )
        element = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
        if element is None:
            raise AttributeError("placeholder XML element is unavailable")
        return element


class BaseShapePlaceholderCollection(PlaceholderCollection):
    def __init__(self, slide: Any, shapes: Sequence[Any]) -> None:
        super().__init__(slide, shapes)
        self._turbo_add_enabled = False

    @property
    def turbo_add_enabled(self) -> bool:
        return self._turbo_add_enabled

    @turbo_add_enabled.setter
    def turbo_add_enabled(self, value: Any) -> None:
        self._turbo_add_enabled = bool(value)

    def get(self, idx: int, default: Any = None) -> Shape | Any:
        try:
            return self[idx]
        except KeyError:
            return default

    def ph_basename(self, ph_type: Any) -> str:
        return _placeholder_basename(ph_type)

    def clone_placeholder(self, placeholder: Any) -> None:
        self._slide.shapes.clone_placeholder(placeholder)


class MasterPlaceholderCollection(BaseShapePlaceholderCollection):
    def get(self, ph_type: int, default: Any = None) -> Shape | Any:
        for shape in self._placeholders:
            if int(shape.placeholder_format.type) == ph_type:
                return shape
        return default


class MasterShapeCollection(Sequence[MasterShape]):
    def __init__(self, master: Any, shapes: list[MasterShape]) -> None:
        self._master = master
        self._shapes = shapes
        self._turbo_add_enabled = False

    def __getitem__(self, index: int | slice) -> MasterShape | list[MasterShape]:
        return self._shapes[index]

    def __iter__(self) -> Iterator[MasterShape]:
        return iter(self._shapes)

    def __len__(self) -> int:
        return len(self._shapes)

    @property
    def part(self) -> PackagePart:
        return self._master.part

    @property
    def element(self) -> XmlElementProxy:
        root = _package_xml_element(
            self._master._presentation.path,
            self._master.partname,
        )
        element = root.find(f"{{{P_NS}}}cSld/{{{P_NS}}}spTree")
        if element is None:
            raise AttributeError("shape tree XML element is unavailable")
        return element

    @property
    def parent(self) -> Any:
        return self._master

    @property
    def turbo_add_enabled(self) -> bool:
        return self._turbo_add_enabled

    @turbo_add_enabled.setter
    def turbo_add_enabled(self, value: Any) -> None:
        self._turbo_add_enabled = bool(value)

    def ph_basename(self, ph_type: Any) -> str:
        return _placeholder_basename(ph_type)

    def clone_placeholder(self, placeholder: Any) -> None:
        spec = self._append_placeholder_clone(placeholder)
        self._master._presentation._queue_part_placeholder_add(
            self._master.partname,
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
        name = _next_placeholder_name(
            self._shapes,
            shape_id,
            placeholder_type,
            placeholder_orient,
        )
        shape_index = len(self._shapes)
        latent_types = {"dt", "ftr", "sldNum"}
        payload = {
            "id": str(shape_id),
            "name": name,
            "kind": "shape",
            "text": "",
            "paragraphs": [] if placeholder_type in latent_types else [""],
            "paragraph_runs": [] if placeholder_type in latent_types else [[]],
            "is_placeholder": True,
            "placeholder_type": placeholder_type,
            "placeholder_idx": placeholder_idx,
            "placeholder_orient": placeholder_orient,
            "placeholder_size": placeholder_size,
        }
        shape = MasterShape(self._master, shape_index, payload)
        self._shapes.append(shape)
        self._master.placeholders._placeholders.append(shape)
        return {
            "id": str(shape_id),
            "name": name,
            "placeholder_type": placeholder_type,
            "placeholder_orient": placeholder_orient,
            "placeholder_size": placeholder_size,
            "placeholder_idx": placeholder_idx,
            "has_text_body": placeholder_type not in latent_types,
        }
