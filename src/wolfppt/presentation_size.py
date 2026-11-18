"""Slide and notes page dimensions, including atomic saved-deck notes edits.

Notes dimensions are integral EMU. Changing them changes the notes page canvas,
not the notes master's authored shape geometry. Save queued facade edits first;
package mutations rebase the presentation, so reacquire shape handles afterwards.
"""

from __future__ import annotations

import zipfile
from numbers import Integral
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .chart_workbook import serialize_xml_preserving_namespaces
from .package_parts import (
    InMemoryPackageSource,
    copy_package_with_replacements,
    open_package_source,
)
from .slide_metadata import presentation_partname
from .xml_helpers import (
    STRICT_P_NS,
    find_ooxml,
    findall_ooxml,
    ooxml_namespace,
)

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
MIN_SLIDE_SIZE_EMU = 914400
MAX_SLIDE_SIZE_EMU = 51206400
DEFAULT_SLIDE_SIZE = {"cx": 9144000, "cy": 6858000}
MAX_PAGE_COORDINATE_EMU = 27273042316900


class PresentationSizeRefusal(ValueError):
    """A page dimension edit or read cannot be performed safely."""


def notes_page_size(presentation: Any) -> dict[str, int]:
    """Read the saved notes canvas as ``{"cx": width, "cy": height}`` in EMU.

    Both Transitional and Strict PresentationML retain their namespace profile.
    A missing or malformed notes canvas is a named refusal, not a guessed size.
    """
    _require_size_presentation(presentation)
    with presentation._mutation_lock:
        if presentation._disposed:
            raise PresentationSizeRefusal("presentation is disposed")
        try:
            with open_package_source(presentation._source_path) as package:
                part = presentation_partname(presentation._source_path)
                root = _page_presentation_root(package.read(part))
            element = _unique_page_size_element(root, "notesSz")
            if element is None:
                raise PresentationSizeRefusal("saved presentation has no notesSz")
            return _page_size_values(element, "notesSz")
        except (KeyError, OSError, zipfile.BadZipFile) as exc:
            raise PresentationSizeRefusal("saved notes page size is unavailable") from exc


def set_notes_page_size(presentation: Any, width: Any, height: Any) -> None:
    """Atomically set the saved notes canvas; call ``presentation.save`` to publish.

    Positive integral EMU within the DrawingML coordinate range are accepted.
    Notes slides, notes masters, relationships, and all other part payloads are
    preserved. Unsupported XML and pending edits are refused before any write.
    """
    _require_size_presentation(presentation)
    cx = _coerce_page_coordinate(width, "notes width")
    cy = _coerce_page_coordinate(height, "notes height")
    with presentation._mutation_lock:
        _require_saved_size(presentation, "changing the notes page size")
        part = presentation_partname(presentation._source_path)

        def plan(package: Any) -> tuple[dict[str, bytes], set[str], None]:
            try:
                source = package.read(part)
            except KeyError as exc:
                raise PresentationSizeRefusal("presentation main part is unavailable") from exc
            root = _page_presentation_root(source)
            element = _unique_page_size_element(root, "notesSz")
            if element is not None:
                previous = _page_size_values(element, "notesSz")
                if previous == {"cx": cx, "cy": cy}:
                    return {}, set(), None
            else:
                element = ET.Element(f"{{{ooxml_namespace(root, P_NS)}}}notesSz")
                insert_at = len(root)
                for index, child in enumerate(root):
                    if isinstance(child.tag, str) and _xml_local_name(child.tag) in {
                        "smartTags",
                        "embeddedFontLst",
                        "custShowLst",
                        "photoAlbum",
                        "custDataLst",
                        "kinsoku",
                        "defaultTextStyle",
                        "modifyVerifier",
                        "extLst",
                    }:
                        insert_at = index
                        break
                root.insert(insert_at, element)
            element.set("cx", str(cx))
            element.set("cy", str(cy))
            return (
                {
                    part: serialize_xml_preserving_namespaces(root, source),
                },
                set(),
                None,
            )

        presentation._rewrite_package("changing the notes page size", plan)


def _require_size_presentation(presentation: Any) -> None:
    from .presentation import Presentation

    if not isinstance(presentation, Presentation):
        raise PresentationSizeRefusal("target must be a Presentation")


def _require_saved_size(presentation: Any, operation: str) -> None:
    try:
        presentation._require_saved_package(operation)
    except (ValueError, RuntimeError) as exc:
        raise PresentationSizeRefusal(str(exc)) from exc


def _coerce_page_coordinate(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise PresentationSizeRefusal(f"{name} must be an integral EMU value")
    result = int(value)
    if not 0 < result <= MAX_PAGE_COORDINATE_EMU:
        raise PresentationSizeRefusal(f"{name} is outside the positive coordinate range")
    return result


def _page_presentation_root(source: bytes) -> ET.Element:
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        root = ET.fromstring(source, parser=parser)
    except ET.ParseError as exc:
        raise PresentationSizeRefusal("presentation main XML is malformed") from exc
    if root.tag not in {f"{{{P_NS}}}presentation", f"{{{STRICT_P_NS}}}presentation"}:
        raise PresentationSizeRefusal("main part is not supported PresentationML")
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if (
            node.tag
            == "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"
        ):
            raise PresentationSizeRefusal("alternate page-size XML is unsupported")
        if _xml_local_name(node.tag) in {"notesSz", "sldSz"}:
            if node.tag not in {
                f"{{{ooxml_namespace(root, P_NS)}}}notesSz",
                f"{{{ooxml_namespace(root, P_NS)}}}sldSz",
            }:
                raise PresentationSizeRefusal("mixed or unsupported page size namespace")
            if node not in list(root) or len(node):
                raise PresentationSizeRefusal("nested page-size XML is unsupported")
    return root


def _unique_page_size_element(root: ET.Element, name: str) -> ET.Element | None:
    elements = findall_ooxml(root, f"{{{P_NS}}}{name}")
    if len(elements) > 1:
        raise PresentationSizeRefusal(f"presentation has ambiguous {name} elements")
    return elements[0] if elements else None


def _page_size_values(element: ET.Element, name: str) -> dict[str, int]:
    result = {}
    for attribute in ("cx", "cy"):
        raw = element.get(attribute, "")
        try:
            value = int(raw)
        except ValueError as exc:
            raise PresentationSizeRefusal(f"{name} has invalid {attribute}") from exc
        result[attribute] = _coerce_page_coordinate(value, f"{name} {attribute}")
    return result


def presentation_slide_size(presentation: Any) -> dict[str, int]:
    if presentation._slide_size is not None:
        return dict(presentation._slide_size)
    size = read_presentation_slide_size(presentation._source_path)
    presentation._slide_size = size
    return dict(size)


def read_presentation_slide_size(path: Path | InMemoryPackageSource) -> dict[str, int]:
    try:
        with open_package_source(path) as package:
            root = ET.fromstring(package.read(presentation_partname(path)))
    except (
        FileNotFoundError,
        KeyError,
        ET.ParseError,
        zipfile.BadZipFile,
    ):
        return dict(DEFAULT_SLIDE_SIZE)
    slide_size = find_ooxml(root, f"{{{P_NS}}}sldSz")
    if slide_size is None:
        return dict(DEFAULT_SLIDE_SIZE)
    return {
        "cx": int(slide_size.attrib.get("cx", str(DEFAULT_SLIDE_SIZE["cx"]))),
        "cy": int(slide_size.attrib.get("cy", str(DEFAULT_SLIDE_SIZE["cy"]))),
    }


def coerce_slide_size_emu(value: Any, name: str) -> int:
    if not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integral EMU value")
    emu = int(value)
    if not MIN_SLIDE_SIZE_EMU <= emu <= MAX_SLIDE_SIZE_EMU:
        raise ValueError(
            f"{name} must be in range({MIN_SLIDE_SIZE_EMU}, {MAX_SLIDE_SIZE_EMU}), got {emu}"
        )
    return emu


def apply_presentation_size_edits(
    input_path: Path,
    output_path: Path,
    size_edits: dict[str, int],
) -> None:
    presentation_part = presentation_partname(input_path)
    with open_package_source(input_path) as package:
        source = package.read(presentation_part)
        root = _page_presentation_root(source)
    slide_size = presentation_slide_size_element(root)
    for attr in ("cx", "cy"):
        if attr in size_edits:
            slide_size.set(attr, str(size_edits[attr]))
    copy_package_with_replacements(
        input_path,
        output_path,
        {presentation_part: serialize_xml_preserving_namespaces(root, source)},
    )


def presentation_slide_size_element(root: ET.Element) -> ET.Element:
    slide_size = _unique_page_size_element(root, "sldSz")
    if slide_size is not None:
        return slide_size
    slide_size = ET.Element(
        f"{{{ooxml_namespace(root, P_NS)}}}sldSz",
        {"cx": "9144000", "cy": "6858000", "type": "screen4x3"},
    )
    children = list(root)
    insert_at = len(children)
    for index, child in enumerate(children):
        if not isinstance(child.tag, str):
            continue
        local_name = _xml_local_name(child.tag)
        if local_name in {"notesSz", "smartTags", "embeddedFontLst", "custShowLst"}:
            insert_at = index
            break
    root.insert(insert_at, slide_size)
    return slide_size


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
