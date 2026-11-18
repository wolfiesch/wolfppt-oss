"""Placeholder collection facades and placeholder content insertion."""

from __future__ import annotations

import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.parsers import expat

from .facade_values import coerce_positive_int as _coerce_positive_int
from .image_inputs import InMemoryImage
from .image_inputs import image_source_for_queue as _image_source_for_queue
from .package_parts import (
    PackagePart,
    XmlElementProxy,
)
from .package_parts import (
    copy_package_with_replacements as _copy_package_with_replacements,
)
from .package_parts import (
    package_xml_element as _package_xml_element,
)
from .shape_core_facade import MasterShape, Shape
from .shape_inspection import (
    PictureImage,
    _next_placeholder_name,
    _next_shape_id,
    _placeholder_basename,
    _placeholder_raw_value,
    _placeholder_type_xml,
)
from .table_adds import _presentation_slide_parts, _table_shape_xml, table_grid_extents

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

# python-pptx sizes a placeholder table at 0.4 inch per row.
_TABLE_ROW_HEIGHT_EMU = 370840
_CROP_SCALE = 100000


class PlaceholderCollection(Sequence[Shape]):
    def __init__(self, slide: Any, shapes: Sequence[Any]) -> None:
        self._slide = slide
        self._placeholders = [shape for shape in shapes if shape.is_placeholder]

    def __getitem__(self, idx: int) -> Shape:
        for shape in self._placeholders:
            if shape.placeholder_format.idx == idx:
                return shape
        raise KeyError(f"no placeholder on this slide with idx == {idx}")

    def __contains__(self, item: object) -> bool:
        if isinstance(item, int) and not isinstance(item, bool):
            return any(shape.placeholder_format.idx == item for shape in self._placeholders)
        return any(shape is item or shape == item for shape in self._placeholders)

    def get(self, idx: int, default: Any = None) -> Shape | Any:
        try:
            return self[idx]
        except KeyError:
            return default

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

    def remove(self, shape: MasterShape) -> None:
        """Remove one saved shape from the notes master; other masters are unsupported."""
        from .notes_page_semantics import remove_notes_shape
        from .presentation_slides import NotesMaster

        if not isinstance(self._master, NotesMaster):
            raise NotImplementedError("removing shapes is supported only on the notes master")
        remove_notes_shape(self._master, shape, self)

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


def insert_placeholder_picture(placeholder: Shape, image_file: Any) -> Shape:
    """Fill an unfilled slide placeholder with an image cropped to fit.

    Mirrors python-pptx ``PicturePlaceholder.insert_picture``: the picture
    keeps the placeholder's shape ID, name, and ``p:ph`` binding, and the
    image is center-cropped so its aspect ratio survives the frame extents.
    """
    position = _insertion_position(placeholder, "picture")
    if isinstance(image_file, (bytes, bytearray, memoryview)):
        image_source: Any = InMemoryImage(bytes(image_file))
    else:
        image_source = _image_source_for_queue(image_file)
        if not isinstance(image_source, InMemoryImage):
            image_source = Path(image_source).resolve()
    image = PictureImage.from_image_input(image_source)
    crop = _fill_cropping(image.size, (placeholder.width, placeholder.height))
    slide = placeholder._slide
    slide._presentation._shape_adds.append(
        (
            "placeholder_picture",
            (
                slide._index,
                str(placeholder.shape_id),
                _placeholder_idx(placeholder),
                image_source,
                image.filename,
                crop,
            ),
        )
    )
    payload = {
        **_placeholder_identity(placeholder),
        "kind": "picture",
        "text": "",
        "paragraphs": [],
        "has_picture": True,
        "_image_file": image_source,
        "crop": {key: value / _CROP_SCALE for key, value in zip("ltrb", crop, strict=False)},
    }
    return _replace_placeholder(placeholder, position, payload)


def insert_placeholder_table(placeholder: Shape, rows: Any, cols: Any) -> Shape:
    """Fill an unfilled slide placeholder with an empty ``rows`` x ``cols`` table.

    Mirrors python-pptx ``TablePlaceholder.insert_table``: the table takes the
    placeholder's left, top, and width, a height of 0.4 inch per row, and the
    placeholder's ID, name, and ``p:ph`` binding.
    """
    position = _insertion_position(placeholder, "table")
    row_count = _coerce_positive_int(rows, "rows")
    col_count = _coerce_positive_int(cols, "cols")
    slide = placeholder._slide
    if any(shape._payload.get("tables") for shape in slide.shapes[position + 1 :]):
        raise NotImplementedError(
            "insert_table() cannot fill a placeholder that precedes another table "
            "on the same slide: table edits address tables by slide order"
        )
    frame = {
        "x": placeholder.left,
        "y": placeholder.top,
        "cx": placeholder.width,
        "cy": row_count * _TABLE_ROW_HEIGHT_EMU,
    }
    slide._presentation._shape_adds.append(
        (
            "placeholder_table",
            (
                slide._index,
                str(placeholder.shape_id),
                _placeholder_idx(placeholder),
                row_count,
                col_count,
                frame["x"],
                frame["y"],
                frame["cx"],
                frame["cy"],
            ),
        )
    )
    payload = {
        **_placeholder_identity(placeholder),
        "kind": "graphic_frame",
        "text": "",
        "paragraphs": [],
        "transform": frame,
        "tables": [
            {
                "rows": [["" for _ in range(col_count)] for _ in range(row_count)],
                "row_count": row_count,
                "col_count": col_count,
                # The table is absent from the package until save; report the
                # grid the writer emits instead of reading zeros from disk.
                "_column_widths": table_grid_extents(frame["cx"], col_count),
                "_row_heights": table_grid_extents(frame["cy"], row_count),
            }
        ],
    }
    return _replace_placeholder(placeholder, position, payload)


def _insertion_position(placeholder: Shape, content: str) -> int:
    slide = placeholder._slide
    if not (
        placeholder.is_placeholder
        and placeholder._payload.get("kind") == "shape"
        and not placeholder._payload.get("_group_child")
        and not getattr(slide, "_is_notes_slide", False)
    ):
        raise AttributeError(
            f"insert_{content}() requires an unfilled slide placeholder; this shape is not one"
        )
    for position, shape in enumerate(slide.shapes):
        if shape is placeholder:
            return position
    raise ValueError("placeholder is no longer part of its slide")


def _placeholder_idx(placeholder: Shape) -> str:
    return str(placeholder._payload.get("placeholder_idx") or "0")


def _placeholder_identity(placeholder: Shape) -> dict[str, Any]:
    identity = {
        key: value
        for key, value in placeholder._payload.items()
        if key in {"id", "name", "is_placeholder", "transform"} or key.startswith("placeholder_")
    }
    identity["is_placeholder"] = True
    return identity


def _replace_placeholder(placeholder: Shape, position: int, payload: dict[str, Any]) -> Shape:
    slide = placeholder._slide
    replacement = Shape(slide, position, payload)
    slide.shapes._shapes[position] = replacement
    placeholders = slide.placeholders._placeholders
    placeholders[placeholders.index(placeholder)] = replacement
    slide._rebase_live_indices(slide._index)
    return replacement


def _fill_cropping(
    image_size: tuple[int, int], view_size: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Return python-pptx's (left, top, right, bottom) fill crop in 1/100000ths."""
    (image_width, image_height), (view_width, view_height) = image_size, view_size
    if min(image_width, image_height, view_width, view_height) <= 0:
        raise ValueError("picture placeholder needs positive image and frame extents")
    view_ratio = view_width / view_height
    image_ratio = image_width / image_height
    crop = (0.0, 0.0, 0.0, 0.0)
    if view_ratio < image_ratio:
        side = (1.0 - view_ratio / image_ratio) / 2.0
        crop = (side, 0.0, side, 0.0)
    elif view_ratio > image_ratio:
        side = (1.0 - image_ratio / view_ratio) / 2.0
        crop = (0.0, side, 0.0, side)
    left, top, right, bottom = (int(round(value * _CROP_SCALE)) for value in crop)
    return (left, top, right, bottom)


def apply_placeholder_insert(
    add_kind: str, args: tuple[Any, ...], current: Path, step: Path
) -> bool:
    """Apply a queued placeholder fill to the staged package, in place."""
    if add_kind == "placeholder_picture":
        _apply_placeholder_picture(current, step, *args)
        return True
    if add_kind == "placeholder_table":
        _apply_placeholder_table(current, step, *args)
        return True
    return False


@dataclass
class _TreeChild:
    """Byte spans of one top-level ``p:spTree`` child in raw slide XML."""

    tag: str
    start: int
    end: int = 0
    shape_id: str | None = None
    name: str = ""
    ph_idx: str | None = None
    ph: tuple[int, int] | None = None
    xfrm: tuple[int, int] | None = None
    blip: tuple[int, int] | None = None


def _shape_tree_children(xml: bytes) -> list[_TreeChild]:
    """Locate spTree children by byte offset so untouched markup stays verbatim."""
    parser = expat.ParserCreate(namespace_separator="}")
    path: list[str] = []
    starts: list[int] = []
    # Whether each open element has seen content; expat reports an
    # empty-element tag's end just past its "/>", not at an end tag.
    has_content: list[bool] = []
    children: list[_TreeChild] = []
    tree = [f"{P_NS}}}cSld", f"{P_NS}}}spTree"]

    def in_tree_child() -> bool:
        return len(path) >= 4 and path[1:3] == tree

    def on_content(_data: str) -> None:
        if has_content:
            has_content[-1] = True

    def on_start(name: str, attrs: dict[str, str]) -> None:
        on_content("")
        path.append(name)
        starts.append(parser.CurrentByteIndex)
        has_content.append(False)
        if not in_tree_child():
            return
        depth = len(path)
        if depth == 4:
            children.append(_TreeChild(name.rsplit("}", 1)[-1], starts[-1]))
        elif depth == 6 and name == f"{P_NS}}}cNvPr":
            children[-1].shape_id = attrs.get("id")
            children[-1].name = attrs.get("name", "")
        elif depth == 7 and name == f"{P_NS}}}ph":
            children[-1].ph_idx = attrs.get("idx", "0")

    def on_end(name: str) -> None:
        start, index = starts.pop(), parser.CurrentByteIndex
        empty = not has_content.pop() and xml[start:index].endswith(b"/>")
        span = (start, index if empty else xml.index(b">", index) + 1)
        if in_tree_child():
            depth = len(path)
            child = children[-1]
            if depth == 4:
                child.end = span[1]
            elif depth == 7 and name == f"{P_NS}}}ph":
                child.ph = span
            elif depth == 6 and name == f"{A_NS}}}xfrm" and path[4] == f"{P_NS}}}spPr":
                child.xfrm = span
            elif depth == 6 and name == f"{A_NS}}}blip":
                child.blip = span
        path.pop()

    parser.StartElementHandler = on_start
    parser.EndElementHandler = on_end
    parser.CharacterDataHandler = on_content
    parser.Parse(xml, True)
    return children


def _slide_part(package: zipfile.ZipFile, slide_index: int) -> str:
    try:
        return _presentation_slide_parts(package)[slide_index]
    except IndexError as exc:
        raise IndexError("slide index out of range") from exc


def _placeholder_target(
    children: list[_TreeChild], shape_id: str, placeholder_idx: str
) -> _TreeChild:
    candidates = [
        child for child in children if child.tag == "sp" and child.ph_idx == placeholder_idx
    ]
    if len(candidates) > 1:
        candidates = [child for child in candidates if child.shape_id == shape_id]
    if len(candidates) != 1 or candidates[0].ph is None:
        raise ValueError(
            f"slide placeholder idx={placeholder_idx} is missing or ambiguous; it cannot be filled"
        )
    return candidates[0]


def _splice(xml: bytes, edits: list[tuple[int, int, bytes]]) -> bytes:
    for start, end, replacement in sorted(edits, reverse=True):
        xml = xml[:start] + replacement + xml[end:]
    return xml


def _attr(value: str) -> str:
    from xml.sax.saxutils import escape

    return escape(value, {'"': "&quot;"})


def _apply_placeholder_picture(
    current: Path,
    step: Path,
    slide_index: int,
    shape_id: str,
    placeholder_idx: str,
    image_source: Any,
    descr: str,
    crop: tuple[int, int, int, int],
) -> None:
    from . import native

    if isinstance(image_source, InMemoryImage):
        image_source = image_source.materialize(step.parent, f"{step.stem}-image")
    with zipfile.ZipFile(current) as package:
        slide_part = _slide_part(package, slide_index)
        existing_ids = {child.shape_id for child in _shape_tree_children(package.read(slide_part))}
    # The native image add owns media dedup, content types, and the slide
    # relationship; its temporary picture only donates the related blip.
    staged = step.with_name(f"{step.stem}-placeholder-image{step.suffix}")
    native.add_image(current, staged, slide_index, image_source, 0, 0, 914400, 914400)
    try:
        with zipfile.ZipFile(staged) as package:
            xml = package.read(slide_part)
        children = _shape_tree_children(xml)
        target = _placeholder_target(children, shape_id, placeholder_idx)
        donors = [child for child in children if child.shape_id not in existing_ids]
        if len(donors) != 1 or donors[0].blip is None:
            raise RuntimeError("native image add did not produce one picture")
        donor = donors[0]
        src_rect = "".join(
            f' {key}="{value}"' for key, value in zip("ltrb", crop, strict=False) if value
        )
        # Keep an authored frame; otherwise inherit bounds from the layout.
        shape_properties = (
            b"<p:spPr>" + xml[target.xfrm[0] : target.xfrm[1]] + b"</p:spPr>"
            if target.xfrm
            else b"<p:spPr/>"
        )
        picture = b"".join(
            (
                f'<p:pic><p:nvPicPr><p:cNvPr id="{_attr(target.shape_id or "")}" '
                f'name="{_attr(target.name)}" descr="{_attr(descr)}"/>'
                '<p:cNvPicPr><a:picLocks noGrp="1" noChangeAspect="1"/>'
                "</p:cNvPicPr><p:nvPr>".encode(),
                xml[target.ph[0] : target.ph[1]],
                b"</p:nvPr></p:nvPicPr><p:blipFill>",
                xml[donor.blip[0] : donor.blip[1]],
                f"<a:srcRect{src_rect}/><a:stretch><a:fillRect/></a:stretch>".encode(),
                b"</p:blipFill>",
                shape_properties,
                b"</p:pic>",
            )
        )
        updated = _splice(
            xml,
            [(target.start, target.end, picture), (donor.start, donor.end, b"")],
        )
        _copy_package_with_replacements(staged, step, {slide_part: updated})
    finally:
        staged.unlink(missing_ok=True)


def _apply_placeholder_table(
    current: Path,
    step: Path,
    slide_index: int,
    shape_id: str,
    placeholder_idx: str,
    rows: int,
    cols: int,
    x_emu: int,
    y_emu: int,
    cx_emu: int,
    cy_emu: int,
) -> None:
    with zipfile.ZipFile(current) as package:
        slide_part = _slide_part(package, slide_index)
        xml = package.read(slide_part)
    target = _placeholder_target(_shape_tree_children(xml), shape_id, placeholder_idx)
    frame_id = int(target.shape_id or 0)
    table = _table_shape_xml(frame_id, rows, cols, x_emu, y_emu, cx_emu, cy_emu, [])
    placeholder_binding = xml[target.ph[0] : target.ph[1]].decode("utf-8")
    table = table.replace(f'name="Table {frame_id}"', f'name="{_attr(target.name)}"', 1).replace(
        "<p:nvPr/>", f"<p:nvPr>{placeholder_binding}</p:nvPr>", 1
    )
    updated = _splice(xml, [(target.start, target.end, table.encode("utf-8"))])
    _copy_package_with_replacements(current, step, {slide_part: updated})
