"""Read-only access to legacy VML drawings related to a slide."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import open_package_source, rels_part_for_package_part, resolve_package_target

O_NS = "urn:schemas-microsoft-com:office:office"
V_NS = "urn:schemas-microsoft-com:vml"
_VML_RELATIONSHIP = "/vmlDrawing"


class VmlDrawingError(ValueError):
    """Atomic VML read refusal; ``code`` identifies the failed precondition."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class VmlImageData:
    """A ``v:imagedata`` child; absent attributes read as ``None``."""

    relid: str | None
    """``o:relid``: relationship ID resolved against the VML part's own relationships."""
    title: str | None
    """``o:title``."""


@dataclass(frozen=True)
class VmlShape:
    """A ``v:shape`` element of a VML drawing; absent attributes read as ``None``."""

    id: str | None
    """``v:shape/@id``."""
    alt: str | None
    """``v:shape/@alt``: the legacy alternative text."""
    spid: str | None
    """``v:shape/@o:spid``."""
    imagedata: tuple[VmlImageData, ...]
    """Descendant ``v:imagedata`` elements in document order."""


class VmlDrawing(Sequence[VmlShape]):
    """One VML drawing part and its ``v:shape`` elements in document order."""

    def __init__(self, partname: str, shapes: Sequence[VmlShape]) -> None:
        self.partname = partname
        self._shapes = tuple(shapes)

    def __len__(self) -> int:
        return len(self._shapes)

    def __getitem__(self, index: int | slice) -> Any:
        return self._shapes[index]

    def __iter__(self) -> Iterator[VmlShape]:
        return iter(self._shapes)

    def __repr__(self) -> str:
        return f"VmlDrawing(partname={self.partname!r}, shapes={len(self._shapes)})"


def _shape(element: ET.Element) -> VmlShape:
    return VmlShape(
        id=element.get("id"),
        alt=element.get("alt"),
        spid=element.get(f"{{{O_NS}}}spid"),
        imagedata=tuple(
            VmlImageData(relid=data.get(f"{{{O_NS}}}relid"), title=data.get(f"{{{O_NS}}}title"))
            for data in element.iter(f"{{{V_NS}}}imagedata")
        ),
    )


def read_vml_drawings(presentation: Any, slide_part: str) -> tuple[VmlDrawing, ...]:
    """Read the VML drawings internally related to ``slide_part`` from the source package.

    External relationship targets are not followed. A missing or malformed target raises
    :class:`VmlDrawingError` and nothing is returned.
    """
    slide_part = slide_part.lstrip("/")
    if not slide_part:
        raise VmlDrawingError("unsaved_slide", "save the slide before VML drawing access")
    drawings: list[VmlDrawing] = []
    with open_package_source(presentation.path) as package:
        names = set(package.namelist())
        rels = rels_part_for_package_part(slide_part)
        if rels not in names:
            return ()
        seen: set[str] = set()
        for rel in ET.fromstring(package.read(rels)):
            if not rel.get("Type", "").endswith(_VML_RELATIONSHIP):
                continue
            if rel.get("TargetMode") == "External":
                continue
            part = resolve_package_target(slide_part, rel.get("Target", ""))
            if part in seen:
                continue
            seen.add(part)
            if part not in names:
                raise VmlDrawingError("missing_vml", part)
            try:
                root = ET.fromstring(package.read(part))
            except ET.ParseError as exc:
                raise VmlDrawingError("malformed_vml", f"{part}: {exc}") from exc
            drawings.append(VmlDrawing(part, [_shape(el) for el in root.iter(f"{{{V_NS}}}shape")]))
    return tuple(drawings)


def read_slide_vml_drawings(slide: Any) -> tuple[VmlDrawing, ...]:
    """VML drawings internally related to ``slide``; see :func:`read_vml_drawings`."""
    if getattr(slide, "_deleted", False):
        raise VmlDrawingError("unsaved_slide", "save the slide before VML drawing access")
    return read_vml_drawings(slide._presentation, str(slide.partname))
