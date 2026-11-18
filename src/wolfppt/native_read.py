"""Native binding wrappers split from wolfppt.native."""

from __future__ import annotations

import json
import math
import re
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .native_binding import NATIVE_INSTALL_HINT
from .native_results import (
    NativeInspectResult,
    NativePresentationSummary,
)
from .package_parts import InMemoryPackageSource

_RELATIONSHIP_GROUPS = {
    "image_relationships": ("/image",),
    "chart_relationships": ("/chart",),
    "comment_relationships": ("/comments", "/comment"),
    "media_relationships": ("/audio", "/media", "/video"),
    "ole_relationships": ("/oleObject", "/package"),
}
# Namespaces a native summary ``mc:Choice`` may require (wolfppt-core
# ``summary_text_extract.inc.rs`` ``MC_SUPPORTED_NAMESPACE_URIS``).
_NATIVE_MC_SUPPORTED_NAMESPACE_URIS = frozenset(
    {
        "http://schemas.openxmlformats.org/presentationml/2006/main",
        "http://schemas.openxmlformats.org/drawingml/2006/main",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "http://purl.oclc.org/ooxml/presentationml/main",
        "http://purl.oclc.org/ooxml/drawingml/main",
        "http://purl.oclc.org/ooxml/officeDocument/relationships",
        "http://schemas.openxmlformats.org/drawingml/2006/chart",
    }
)
# XML whitespace, which native trims from ``*:t`` texts; ``str.strip()`` would
# also drop Unicode spaces such as the no-break space PowerPoint writes.
_XML_WHITESPACE = " \t\r\n"
_NATIVE_BOOLEANS = {"1": True, "true": True, "on": True, "0": False, "false": False, "off": False}
_INTEGER = re.compile(r"[+-]?[0-9]+")
_ASCII_UPPER = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
# DrawingML colour elements native summarizes as a run colour
# (wolfppt-core ``RunColorKind``); any other element is no colour.
_NATIVE_RUN_COLOR_KINDS = {
    "srgbClr": "srgb",
    "prstClr": "preset",
    "sysClr": "system",
    "scrgbClr": "scrgb",
    "schemeClr": "scheme",
    "hslClr": "hsl",
}


def inspect(path: str | Path) -> NativeInspectResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(wolfppt_native.inspect_package_json(str(path)))
    parts = list(payload["parts"])
    return NativeInspectResult(
        path=payload["path"],
        part_count=len(parts),
        has_vba=any(part["kind"] == "vba" for part in parts),
        parts=parts,
    )


def summarize(path: str | Path) -> NativePresentationSummary:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(wolfppt_native.summarize_presentation_json(str(path)))
    return NativePresentationSummary(
        path=payload["path"],
        slide_count=int(payload["slide_count"]),
        has_vba=bool(payload["has_vba"]),
        slides=list(payload["slides"]),
    )


def summarize_slide(source: str | Path | InMemoryPackageSource, slide_index: int) -> dict[str, Any]:
    """Summarize one slide; owned in-memory packages never touch the filesystem.

    The native binding reads only filesystem paths, so an
    :class:`InMemoryPackageSource` is summarized from its package XML into the
    same payload schema.
    """
    if isinstance(source, InMemoryPackageSource):
        return _summarize_in_memory_slide(source, slide_index)
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    return dict(json.loads(wolfppt_native.summarize_slide_at_index_json(str(source), slide_index)))


class SlideSummaryReaders:
    """Per-presentation slide summaries that index each source package once.

    The native ``SlideSummaryReader`` parses a package's ZIP central directory
    and slide order once per file identity; every read opens the file, checks
    its identity, and closes it before returning, so no handle outlives a call
    and a file replaced on disk is re-indexed rather than read stale. A new
    source path (after a save or staged edit) gets a new reader. Owned
    in-memory packages keep their filesystem-free summary. Copies and pickles
    start empty.
    """

    __slots__ = ("_lock", "_path", "_reader")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._path: str | None = None
        self._reader: Any = None

    @property
    def package_loads(self) -> int:
        """Package index parses by the current reader (0 before the first read)."""
        with self._lock:
            return 0 if self._reader is None else int(self._reader.package_loads)

    def summarize_slide(
        self, source: str | Path | InMemoryPackageSource, slide_index: int
    ) -> dict[str, Any]:
        if isinstance(source, InMemoryPackageSource):
            return _summarize_in_memory_slide(source, slide_index)
        try:
            import wolfppt_native
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(NATIVE_INSTALL_HINT) from exc

        path = str(source)
        with self._lock:
            if self._reader is None or self._path != path:
                self._reader = wolfppt_native.SlideSummaryReader(path)
                self._path = path
            payload = self._reader.summarize_slide_json(slide_index)
        return dict(json.loads(payload))

    def __copy__(self) -> SlideSummaryReaders:
        return SlideSummaryReaders()

    def __deepcopy__(self, memo: dict[int, Any]) -> SlideSummaryReaders:
        return SlideSummaryReaders()

    def __reduce__(self) -> tuple[type[SlideSummaryReaders], tuple[()]]:
        return (SlideSummaryReaders, ())


def _summarize_in_memory_slide(source: InMemoryPackageSource, slide_index: int) -> dict[str, Any]:
    from . import extractor
    from .package_parts import rels_part_for_package_part, resolve_package_target
    from .slide_metadata import read_presentation_slide_metadata
    from .slide_payloads import _slide_media_playback_payloads

    slide_parts = list(read_presentation_slide_metadata(source))
    if not 0 <= slide_index < len(slide_parts):
        raise RuntimeError(f"invalid input: slide index {slide_index} was not found")
    part = slide_parts[slide_index]
    with source.open() as package:
        try:
            slide_xml = package.read(part)
        except KeyError as exc:
            raise RuntimeError(f"slide part {part} was not found") from exc
        try:
            root = _parse_native_effective_xml(slide_xml)
        except ET.ParseError:
            # Native summarizes unparseable slide XML as an empty slide.
            root = ET.Element(f"{{{extractor.P_NS}}}sld")
        relationships = _relationships(package, rels_part_for_package_part(part))
        notes: list[str] = []
        notes_rel = next(
            (rel for rel in relationships if rel["relationship_type"].endswith("/notesSlide")),
            None,
        )
        if notes_rel is not None:
            notes_part = resolve_package_target(part, notes_rel["target"])
            try:
                notes = _text_runs(_parse_native_effective_xml(package.read(notes_part)))
            except (KeyError, ET.ParseError):
                notes = []
    media_playback = _slide_media_playback_payloads(root)
    shape_elements = extractor._shape_elements(root)
    payload: dict[str, Any] = {
        "part": part,
        "texts": _text_runs(root),
        "tables": [
            _table_payload(extractor._extract_table(table))
            for table in root.iter(f"{{{extractor.A_NS}}}tbl")
        ],
        "shapes": _in_memory_shape_payloads(
            shape_elements,
            [extractor._extract_shape(element) for element in shape_elements],
            media_playback,
        ),
        "notes": notes,
        "relationships": relationships,
    }
    for key, suffixes in _RELATIONSHIP_GROUPS.items():
        payload[key] = [rel for rel in relationships if rel["relationship_type"].endswith(suffixes)]
    payload["has_transition"] = root.find(f".//{{{extractor.P_NS}}}transition") is not None
    payload["has_timing"] = root.find(f".//{{{extractor.P_NS}}}timing") is not None
    return payload


def _relationships(package: Any, rels_part: str) -> list[dict[str, Any]]:
    """Relationship records sorted by ``(Id, Target)``, as native reports them."""
    try:
        rels_root = ET.fromstring(package.read(rels_part))
    except (KeyError, ET.ParseError):
        return []
    relationships = [
        {
            "id": rel.attrib.get("Id", ""),
            "relationship_type": rel.attrib.get("Type", ""),
            "target": rel.attrib.get("Target", ""),
            "target_mode": rel.attrib.get("TargetMode"),
        }
        for rel in rels_root.iter()
        if rel.tag.rpartition("}")[2] == "Relationship"
    ]
    relationships.sort(key=lambda rel: (rel["id"], rel["target"]))
    return relationships


def _parse_native_effective_xml(xml: bytes) -> ET.Element:
    """Parse part XML with the markup-compatibility semantics native summaries use.

    Native resolves ``mc:AlternateContent`` only, with no ``mc:Ignorable``,
    ``mc:ProcessContent`` or ``mc:MustUnderstand`` processing, so ignorable
    extension markup such as the ``a14:m`` equation a text paragraph holds stays
    in the tree; the semantic extractor's full processing drops it as markup of
    a namespace that extractor does not understand.
    """
    from .extractor import _parse_with_namespace_scopes

    root, namespace_scopes = _parse_with_namespace_scopes(xml)
    _select_native_mc_branches(root, namespace_scopes)
    return root


def _select_native_mc_branches(
    parent: ET.Element, namespace_scopes: dict[int, dict[str, str]]
) -> None:
    from .extractor import MC_NS

    children: list[ET.Element] = []
    for child in list(parent):
        if child.tag == f"{{{MC_NS}}}AlternateContent":
            branch = _native_mc_branch(child, namespace_scopes)
            if branch is not None:
                _select_native_mc_branches(branch, namespace_scopes)
                children.extend(branch)
            continue
        _select_native_mc_branches(child, namespace_scopes)
        children.append(child)
    parent[:] = children


def _native_mc_branch(
    alternate: ET.Element, namespace_scopes: dict[int, dict[str, str]]
) -> ET.Element | None:
    """The first supported ``mc:Choice``, else the ``mc:Fallback``, as native picks.

    A ``mc:Choice`` requiring an unbound prefix drops the whole wrapper.
    """
    from .extractor import MC_NS

    choices = [
        (choice, choice.get("Requires"), namespace_scopes.get(id(choice), {}))
        for choice in alternate
        if choice.tag == f"{{{MC_NS}}}Choice"
    ]
    if any(
        requires is not None and any(prefix not in scope for prefix in requires.split())
        for _, requires, scope in choices
    ):
        return None
    for choice, requires, scope in choices:
        if requires is not None and all(
            scope[prefix] in _NATIVE_MC_SUPPORTED_NAMESPACE_URIS for prefix in requires.split()
        ):
            return choice
    return alternate.find(f"{{{MC_NS}}}Fallback")


def _text_runs(root: ET.Element) -> list[str]:
    """Non-empty trimmed ``*:t`` texts in document order, as native reports them."""
    texts: list[str] = []
    for element in root.iter():
        if element.tag.rpartition("}")[2] == "t":
            text = (element.text or "").strip(_XML_WHITESPACE)
            if text:
                texts.append(text)
    return texts


def _in_memory_shape_payloads(
    elements: list[ET.Element],
    semantics: list[Any],
    media_playback: dict[str, dict[str, bool | int]],
) -> list[dict[str, Any]]:
    from . import extractor
    from .slide_payloads import _shape_payload_from_xml, _transform_payload

    shapes: list[dict[str, Any]] = []
    for element, semantic in zip(elements, semantics, strict=True):
        xml_payload = _shape_payload_from_xml(element)
        if xml_payload is None:
            # Foreign-namespace look-alikes are not shape-tree elements.
            continue
        kind = xml_payload["kind"]
        is_frame = extractor._local_name(element.tag) == "graphicFrame"
        payload: dict[str, Any] = {
            "id": semantic.id,
            "name": semantic.name,
            "kind": kind,
        }
        if semantic.id in media_playback:
            payload["media_playback"] = media_playback[semantic.id]
        payload["is_placeholder"] = bool(xml_payload["is_placeholder"])
        payload["placeholder_type"] = xml_payload.get("placeholder_type")
        payload["placeholder_idx"] = xml_payload.get("placeholder_idx")
        payload.update(_native_shape_text_payload(element))
        payload["tables"] = [_table_payload(table) for table in semantic.tables]
        payload["relationship_ids"] = list(semantic.relationship_ids)
        # Only a graphic frame hosts a chart; a group holding one is a group.
        payload["has_chart"] = is_frame and any(
            extractor._local_name(node.tag) == "chart" for node in element.iter()
        )
        payload["has_picture"] = kind == "picture"
        payload["has_group"] = semantic.has_group
        payload["transform"] = _transform_payload(semantic.transform)
        payload["effective_transform"] = _transform_payload(semantic.effective_transform)
        payload["children"] = _in_memory_shape_payloads(
            extractor._shape_child_elements(element),
            list(semantic.children),
            media_playback,
        )
        shapes.append(payload)
    return shapes


def _native_shape_text_payload(element: ET.Element) -> dict[str, Any]:
    """A shape's text fields as native ``summarize_shape_block`` reads them.

    Native matches local names in any namespace: each ``t`` inside a ``p`` is
    paragraph text and each ``t`` with text inside an ``r`` is a run, so the
    ``m:r``/``m:t`` runs of an equation count like ``a:r``/``a:t`` runs, with
    the formatting of the ``a:rPr`` they hold.
    """
    events = list(_xml_events(element))
    paragraphs = _native_paragraph_texts(events)

    def raw(holder: str, attribute: str) -> list[list[str | None]]:
        return _native_paragraph_run_values(events, holder, attribute)

    def mapped(attribute: str, convert: Any) -> list[list[Any]]:
        return [[convert(value) for value in runs] for runs in raw("rPr", attribute)]

    return {
        "text": "\n".join(paragraphs),
        "paragraphs": paragraphs,
        "paragraph_runs": _native_paragraph_runs(events),
        "paragraph_line_breaks": _native_paragraph_line_breaks(events),
        "paragraph_run_bold": mapped("b", _NATIVE_BOOLEANS.get),
        "paragraph_run_italic": mapped("i", _NATIVE_BOOLEANS.get),
        "paragraph_run_underline": mapped("u", lambda value: _native_toggle(value, "none")),
        "paragraph_run_strike": mapped("strike", lambda value: _native_toggle(value, "noStrike")),
        "paragraph_run_font_size": mapped("sz", _native_font_size),
        "paragraph_run_font_name": raw("latin", "typeface"),
        "paragraph_run_color": _native_paragraph_run_colors(events),
    }


def _xml_events(element: ET.Element) -> Iterator[tuple[str, Any]]:
    """Start, text and end events of ``element``, as a streaming reader sees them."""
    yield "start", element
    if element.text:
        yield "text", element.text
    for child in element:
        yield from _xml_events(child)
        if child.tail:
            yield "text", child.tail
    yield "end", element


def _local(element: ET.Element) -> str:
    return element.tag.rpartition("}")[2]


def _native_paragraph_texts(events: list[tuple[str, Any]]) -> list[str]:
    paragraphs: list[str] = []
    parts: list[str] = []
    in_paragraph = in_text = False
    for kind, value in events:
        if kind == "text":
            if in_paragraph and in_text:
                parts.append(value)
            continue
        name = _local(value)
        if kind == "start":
            if name == "p":
                in_paragraph = True
                parts = []
            elif name == "br" and in_paragraph:
                parts.append("\v")
            elif name == "t" and in_paragraph:
                in_text = True
        elif name == "t":
            in_text = False
        elif name == "p" and in_paragraph:
            paragraphs.append("".join(parts))
            in_paragraph = False
    return paragraphs


def _native_paragraph_runs(events: list[tuple[str, Any]]) -> list[list[str]]:
    paragraphs: list[list[str]] = []
    runs: list[str] = []
    text: list[str] = []
    in_paragraph = in_text = False
    for kind, value in events:
        if kind == "text":
            if in_paragraph and in_text:
                text.append(value)
            continue
        name = _local(value)
        if kind == "start":
            if name == "p":
                in_paragraph = True
                runs = []
            elif name == "t" and in_paragraph:
                in_text = True
                text = []
        elif name == "t":
            if text:
                runs.append("".join(text))
                text = []
            in_text = False
        elif name == "p" and in_paragraph:
            paragraphs.append(runs)
            in_paragraph = False
    return paragraphs


def _native_paragraph_line_breaks(events: list[tuple[str, Any]]) -> list[list[int]]:
    """Run counts before each ``br``; only runs with text are counted."""
    paragraphs: list[list[int]] = []
    breaks: list[int] = []
    run_count = 0
    in_paragraph = in_run = in_text = run_has_text = False
    for kind, value in events:
        if kind == "text":
            if in_run and in_text:
                run_has_text = True
            continue
        name = _local(value)
        if kind == "start":
            if name == "p":
                in_paragraph = True
                run_count = 0
                breaks = []
            elif name == "r" and in_paragraph:
                in_run = True
                run_has_text = False
            elif name == "br" and in_paragraph:
                breaks.append(run_count)
            elif name == "t" and in_run:
                in_text = True
        elif name == "t":
            in_text = False
        elif name == "r" and in_run:
            if run_has_text:
                run_count += 1
            in_run = run_has_text = False
        elif name == "p" and in_paragraph:
            paragraphs.append(breaks)
            in_paragraph = False
    return paragraphs


def _native_paragraph_run_values(
    events: list[tuple[str, Any]], holder: str, attribute: str
) -> list[list[str | None]]:
    """Per run with text, ``attribute`` of the run's last ``holder`` element.

    Like native, the has-text flag is not reset at ``t`` end, so a later
    ``t`` outside any run repeats the value.
    """
    paragraphs: list[list[str | None]] = []
    values: list[str | None] = []
    current: str | None = None
    in_paragraph = in_run = in_text = has_text = False
    for kind, value in events:
        if kind == "text":
            if in_run and in_text:
                has_text = True
            continue
        name = _local(value)
        if kind == "start":
            if name == "p":
                in_paragraph = True
                values = []
            elif name == "r" and in_paragraph:
                in_run = True
                current = None
            elif name == holder and in_run:
                current = _native_attribute(value, attribute)
            elif name == "t" and in_run:
                in_text = True
                has_text = False
        elif name == "t":
            if has_text:
                values.append(current)
            in_text = False
        elif name == "r" and in_run:
            in_run = False
            current = None
        elif name == "p" and in_paragraph:
            paragraphs.append(values)
            in_paragraph = False
    return paragraphs


def _native_paragraph_run_colors(
    events: list[tuple[str, Any]],
) -> list[list[dict[str, Any] | None]]:
    """Per run with text, the colour element that is the direct child of the
    run's ``rPr/solidFill``, as native ``ParagraphRunAttributes`` reads it.

    Only an ``rPr`` opened outside another ``rPr`` scopes the run properties;
    every direct child of that ``solidFill`` replaces the colour, so a trailing
    non-colour element clears it. Fills nested deeper (``ln``, ``highlight``,
    ``gradFill``) are not the run colour.
    """
    paragraphs: list[list[dict[str, Any] | None]] = []
    values: list[dict[str, Any] | None] = []
    current: dict[str, Any] | None = None
    rpr_depth = 0  # element depth inside the run rPr; 1 = its direct children
    in_run_fill = in_paragraph = in_run = in_text = has_text = False
    for kind, value in events:
        if kind == "text":
            if in_run and in_text:
                has_text = True
            continue
        name = _local(value)
        if rpr_depth:
            if kind == "start":
                if rpr_depth == 1 and name == "solidFill":
                    in_run_fill = True
                elif rpr_depth == 2 and in_run_fill:
                    current = _native_run_color(value)
                rpr_depth += 1
            else:
                rpr_depth -= 1
                if rpr_depth <= 1:
                    in_run_fill = False
        if kind == "start":
            if name == "p":
                in_paragraph = True
                values = []
            elif name == "r" and in_paragraph:
                in_run = True
                rpr_depth = 0
                in_run_fill = False
                current = None
            elif name == "rPr" and in_run and rpr_depth == 0:
                rpr_depth = 1
            elif name == "t" and in_run:
                in_text = True
                has_text = False
        elif name == "t":
            if has_text:
                values.append(current)
            in_text = False
        elif name == "r" and in_run:
            in_run = False
            current = None
        elif name == "p" and in_paragraph:
            paragraphs.append(values)
            in_paragraph = False
    return paragraphs


def _native_run_color(element: ET.Element) -> dict[str, Any] | None:
    """A DrawingML colour element as native ``RunColorSummary``; all fields present."""
    kind = _NATIVE_RUN_COLOR_KINDS.get(_local(element))
    if kind is None:
        return None
    summary: dict[str, Any] = {
        "kind": kind,
        "value": None,
        "r": None,
        "g": None,
        "b": None,
        "last_color": None,
        "rgb_hex": None,
    }
    if kind == "srgb":
        summary["value"] = summary["rgb_hex"] = _ascii_upper(_native_attribute(element, "val"))
    elif kind in ("preset", "scheme"):
        summary["value"] = _native_attribute(element, "val")
    elif kind == "system":
        summary["value"] = _native_attribute(element, "val")
        summary["last_color"] = summary["rgb_hex"] = _ascii_upper(
            _native_attribute(element, "lastClr")
        )
    elif kind == "scrgb":
        channels = [_native_i64(_native_attribute(element, channel)) for channel in "rgb"]
        summary["r"], summary["g"], summary["b"] = channels
        if None not in channels:
            summary["rgb_hex"] = "".join(
                f"{_srgb_companded_byte(channel):02X}" for channel in channels
            )
    return summary


def _srgb_companded_byte(channel: int) -> int:
    """IEC 61966-2-1 companding of a linear scRGB channel in 1/1000 percent."""
    linear = min(max(channel / 100_000.0, 0.0), 1.0)
    companded = 12.92 * linear if linear <= 0.0031308 else 1.055 * linear ** (1.0 / 2.4) - 0.055
    scaled = 255.0 * companded
    # Rust ``f64::round`` rounds half away from zero; ``round`` would round half to even.
    rounded = math.floor(scaled)
    if scaled - rounded >= 0.5:
        rounded += 1
    return min(max(rounded, 0), 255)


def _native_attribute(element: ET.Element, name: str) -> str | None:
    """The first attribute with local name ``name``, as native ``drawingml_attribute``."""
    return next(
        (value for key, value in element.attrib.items() if key.rpartition("}")[2] == name),
        None,
    )


def _native_i64(value: str | None) -> int | None:
    """``value`` as Rust ``str::parse::<i64>`` accepts it, else ``None``."""
    if value is None or _INTEGER.fullmatch(value) is None:
        return None
    number = int(value)
    return number if -(2**63) <= number < 2**63 else None


def _ascii_upper(value: str | None) -> str | None:
    return None if value is None else value.translate(_ASCII_UPPER)


def _native_toggle(value: str | None, off: str) -> bool | None:
    return None if value is None else value != off


def _native_font_size(value: str | None) -> int | None:
    if value is None or _INTEGER.fullmatch(value) is None:
        return None
    return int(value) * 127


def _table_payload(table: Any) -> dict[str, Any]:
    return {
        "rows": [list(row) for row in table.rows],
        "row_count": table.row_count,
        "col_count": table.col_count,
    }


def roundtrip(input_path: str | Path, output_path: str | Path) -> NativeInspectResult:
    try:
        import wolfppt_native
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(NATIVE_INSTALL_HINT) from exc

    payload = json.loads(wolfppt_native.roundtrip_package_json(str(input_path), str(output_path)))
    parts = list(payload["parts"])
    return NativeInspectResult(
        path=payload["path"],
        part_count=len(parts),
        has_vba=any(part["kind"] == "vba" for part in parts),
        parts=parts,
    )
