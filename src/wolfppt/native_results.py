"""Result objects returned by optional native binding wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NativeInspectResult:
    path: str
    part_count: int
    has_vba: bool
    parts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
            "parts": self.parts,
        }


@dataclass(frozen=True)
class NativePresentationSummary:
    path: str
    slide_count: int
    has_vba: bool
    slides: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_count": self.slide_count,
            "has_vba": self.has_vba,
            "slides": self.slides,
        }


@dataclass(frozen=True)
class NativeTextReplacementResult:
    path: str
    replacements: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeTextRunReplacementResult:
    path: str
    slide_index: int
    run_index: int
    replacements: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "run_index": self.run_index,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeShapeTextSetResult:
    path: str
    slide_index: int
    shape_index: int
    replacements: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "shape_index": self.shape_index,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeParagraphTextSetResult:
    path: str
    slide_index: int
    shape_index: int
    paragraph_index: int
    replacements: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "shape_index": self.shape_index,
            "paragraph_index": self.paragraph_index,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeSlideAddResult:
    path: str
    slide_part: str
    relationship_id: str
    layout_target: str
    slide_id: int
    slide_count: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_part": self.slide_part,
            "relationship_id": self.relationship_id,
            "layout_target": self.layout_target,
            "slide_id": self.slide_id,
            "slide_count": self.slide_count,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }

@dataclass(frozen=True)
class NativeSlideDeleteResult:
    path: str
    deleted_slide_parts: list[str]
    deleted_relationship_ids: list[str]
    survivor_count: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "deleted_slide_parts": list(self.deleted_slide_parts),
            "deleted_relationship_ids": list(self.deleted_relationship_ids),
            "survivor_count": self.survivor_count,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeImageReplacementResult:
    path: str
    relationship_id: str
    replacements: int
    replaced_parts: list[str]
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "relationship_id": self.relationship_id,
            "replacements": self.replacements,
            "replaced_parts": self.replaced_parts,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeImageAddResult:
    path: str
    slide_index: int
    slide_part: str
    relationship_id: str
    image_part: str
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "relationship_id": self.relationship_id,
            "image_part": self.image_part,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeMovieAddResult:
    path: str
    slide_index: int
    slide_part: str
    media_relationship_id: str
    video_relationship_id: str
    poster_relationship_id: str
    media_part: str
    poster_part: str
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "media_relationship_id": self.media_relationship_id,
            "video_relationship_id": self.video_relationship_id,
            "poster_relationship_id": self.poster_relationship_id,
            "media_part": self.media_part,
            "poster_part": self.poster_part,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeOleObjectAddResult:
    path: str
    slide_index: int
    slide_part: str
    ole_relationship_id: str
    icon_relationship_id: str
    ole_part: str
    icon_part: str
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "ole_relationship_id": self.ole_relationship_id,
            "icon_relationship_id": self.icon_relationship_id,
            "ole_part": self.ole_part,
            "icon_part": self.icon_part,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeTableCellReplacementResult:
    path: str
    slide_index: int
    table_index: int
    row_index: int
    col_index: int
    replacements: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "table_index": self.table_index,
            "row_index": self.row_index,
            "col_index": self.col_index,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeTableAddResult:
    path: str
    slide_index: int
    slide_part: str
    table_index: int
    shape_id: int
    rows: int
    cols: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "table_index": self.table_index,
            "shape_id": self.shape_id,
            "rows": self.rows,
            "cols": self.cols,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeTextBoxAddResult:
    path: str
    slide_index: int
    slide_part: str
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeGroupShapeAddResult:
    path: str
    slide_index: int
    slide_part: str
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeFreeformShapeAddResult:
    path: str
    slide_index: int
    slide_part: str
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativePlaceholderShapeAddResult:
    path: str
    slide_index: int
    slide_part: str
    placeholder_type: str | None
    placeholder_idx: str | None
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "placeholder_type": self.placeholder_type,
            "placeholder_idx": self.placeholder_idx,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativePlaceholderShapeBatchAddResult:
    path: str
    slide_index: int
    slide_part: str
    shape_ids: list[int]
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "shape_ids": list(self.shape_ids),
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeAutoShapeAddResult:
    path: str
    slide_index: int
    slide_part: str
    preset_geometry: str
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "preset_geometry": self.preset_geometry,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeConnectorAddResult:
    path: str
    slide_index: int
    slide_part: str
    preset_geometry: str
    shape_id: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "slide_index": self.slide_index,
            "slide_part": self.slide_part,
            "preset_geometry": self.preset_geometry,
            "shape_id": self.shape_id,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }


@dataclass(frozen=True)
class NativeEditBatchResult:
    path: str
    edits: int
    replacements: int
    part_count: int
    has_vba: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "edits": self.edits,
            "replacements": self.replacements,
            "part_count": self.part_count,
            "has_vba": self.has_vba,
        }
