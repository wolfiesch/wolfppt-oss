"""Presentation export to Markdown and chunked JSON for LLM consumption.

Each slide becomes one Markdown section and one chunk, so the Markdown is
exactly the concatenation of the chunk ``markdown`` fields in index order.

A section opens with a ``<!-- Slide N -->`` separator and the slide title as a
level-one heading (``Slide N`` when the slide has no title). Shapes follow in
PowerPoint's reading order, the shape tree order its Reading Order pane exposes,
with the title hoisted first. Body text becomes paragraphs or lists (bullets
resolved through the slide, layout and master text styles). Tables use GFM pipe
syntax by default or escaped HTML in CommonMark. Speaker notes close the
section under a labelled fenced block.

Visibility uses the labels of ``wolf extract``: a slide with ``show="0"`` is
``hidden_slide``, a shape whose ``cNvPr`` has ``hidden="1"`` is ``hidden_shape``,
and a top-level shape placed entirely outside the slide is ``off_canvas``. With
``hidden="label"`` (the default) that content stays in the output and is
labelled; with ``hidden="exclude"`` it is left out and listed under
``excluded``. Shapes Markdown cannot express (pictures, charts, SmartArt, OLE
objects) are listed under ``omissions`` rather than dropped silently.

Image-saving callbacks are opt-in and receive the original package bytes, MIME
type and suggested name. Return a Markdown destination (renamed or redirected),
or ``None`` to suppress it. The callback owns saving; this exporter never writes
files. Without callbacks, pictures remain in the existing omission channel.

``style="sequential"`` preserves that historical reading order and byte output.
``text-only`` keeps text, tables and notes but never calls image handlers.
``visual`` replaces the visible body with a full-slide native PNG, using only
the explicitly admitted ``fonts``. A general image handler can save that PNG;
without one it is a data URI. Hidden labelled text and notes remain readable
outside the image. Source constructs not separately expressible as Markdown
keep their omission records; native rendering omissions are also reported.
All visual slides are rendered before any image-saving callback runs.

``dialect="gfm"`` and ``whitespace="trim"`` retain the historical byte output.
``dialect="commonmark"`` uses HTML tables because CommonMark has no pipe-table
syntax. ``whitespace="preserve"`` keeps spaces, tabs, empty paragraphs and line
breaks: paragraph text is fenced (inside list items where appropriate), titles
are escaped pre-wrapped HTML headings, notes remain literal fenced text, and
table cells are escaped HTML ``pre`` elements. GFM cells encode newlines and
pipes so their content cannot split a table row. HTML-capable Markdown readers
are required for titles and tables; readers that sanitize HTML may omit them.
Paragraph boundaries remain separate blocks; DrawingML soft breaks become
literal line breaks. The selected ``newline`` still governs the entire export.

Strict PresentationML, DrawingML and relationship names are normalized only in
the exporter's private XML cache. Original package and callback media bytes are
unchanged.
"""

from __future__ import annotations

import base64
import json
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from html import escape as _escape_html
from pathlib import Path
from typing import Any, Literal
from xml.etree import ElementTree as ET

from .export_options import ExportOptionsRefusal
from .extractor import (
    NS,
    Table,
    _extract_relationships,
    _extract_table,
    _local_name,
    _ordered_slide_parts,
    _paragraph_text,
    _parse_effective_xml,
    _resolve_target,
    _shape_child_elements,
    _shape_elements,
)
from .package_parts import InMemoryPackageSource, open_package_source
from .render_refusals import RenderRefusal
from .results import LoadSaveWarning, WarningAction, observe_warnings
from .xml_helpers import STRICT_A_NS, STRICT_P_NS, STRICT_R_NS

CHUNKS_SCHEMA = "wolfppt.markdown.chunks.v1"
HiddenMode = Literal["label", "exclude"]
HIDDEN_MODES: tuple[str, ...] = ("label", "exclude")

HIDDEN_SLIDE = "hidden_slide"
HIDDEN_SHAPE = "hidden_shape"
OFF_CANVAS = "off_canvas"

_TITLE_TYPES = frozenset({"title", "ctrTitle"})
_OTHER_TYPES = frozenset({"dt", "ftr", "sldNum", "hdr"})
_BULLET_KINDS = {
    "buNone": None,
    "buChar": "bullet",
    "buBlip": "bullet",
    "buAutoNum": "ordered",
}
_GRAPHIC_KINDS = {
    "http://schemas.openxmlformats.org/drawingml/2006/chart": "chart",
    "http://schemas.openxmlformats.org/drawingml/2006/diagram": "diagram",
    "http://schemas.openxmlformats.org/presentationml/2006/ole": "ole_object",
}
_STRICT_NAMES = {
    f"{{{strict}}}": f"{{{NS[prefix]}}}"
    for prefix, strict in (("p", STRICT_P_NS), ("a", STRICT_A_NS), ("r", STRICT_R_NS))
}
_STRICT_GRAPHIC_KINDS = {
    "http://purl.oclc.org/ooxml/drawingml/chart": "chart",
    "http://purl.oclc.org/ooxml/drawingml/diagram": "diagram",
    "http://purl.oclc.org/ooxml/presentationml/ole": "ole_object",
}
_INLINE_SPECIALS = re.compile(r"([\\`*_\[\]<>])")
_ENTITY = re.compile(r"&(?=#?\w+;)")
_LINE_START_MARKER = re.compile(r"^([#+=-]|\d+[.)])")


@dataclass(frozen=True)
class MarkdownImage:
    """One image occurrence, in reading order, for an image-saving handler."""

    data: bytes
    content_type: str
    suggested_name: str
    part: str
    slide: int
    shape_id: str | None


@dataclass(frozen=True)
class MarkdownSaveOptions:
    """Callbacks return a destination or ``None``; exceptions propagate.

    SVG images use ``svg_image_saving_handler`` when supplied, otherwise the
    general handler. Excluded images do not call either handler. ``newline`` is
    exactly ``"LF"`` (default), ``"CRLF"`` or ``"CR"``; every Markdown line break,
    including text, tables, notes and inter-slide separators, uses that sequence.
    Chunks concatenate byte-for-byte to the aggregate Markdown. Invalid options
    raise :class:`ExportOptionsRefusal` before any image callback runs.
    ``dialect`` is ``"gfm"`` (default) or ``"commonmark"``; the latter emits
    escaped HTML tables instead of unsupported pipe-table syntax.
    ``whitespace`` is ``"trim"`` (default, historical normalization) or
    ``"preserve"`` (literal fenced paragraphs, pre-wrapped HTML titles and
    preformatted table cells, with empty paragraphs and note boundaries intact).
    Both controls apply to sequential/text-only output and to the readable
    titles, labelled hidden text and notes accompanying visual output.
    ``style`` is ``"sequential"`` (default), ``"text-only"`` or ``"visual"``.
    Visual output requires ``fonts`` in the renderer's ``Family[:style]=path``
    format and the commercial renderer; it never substitutes platform fonts.
    ``diagnostic_callback`` receives typed omission/refusal warnings and must
    return WarningAction.CONTINUE or ABORT. Decisions precede every image-saving
    callback. Continuation cannot waive a hard visual-rendering refusal.
    """

    image_saving_handler: Callable[[MarkdownImage], str | None] | None = None
    svg_image_saving_handler: Callable[[MarkdownImage], str | None] | None = None
    newline: Literal["LF", "CRLF", "CR"] = "LF"
    style: Literal["sequential", "text-only", "visual"] = "sequential"
    fonts: tuple[str, ...] = ()
    diagnostic_callback: Callable[[LoadSaveWarning], WarningAction] | None = None
    dialect: Literal["gfm", "commonmark"] = "gfm"
    whitespace: Literal["trim", "preserve"] = "trim"


def _validate_options(options: MarkdownSaveOptions | None) -> str:
    if options is None:
        return "\n"
    if not isinstance(options, MarkdownSaveOptions):
        raise ExportOptionsRefusal("options must be MarkdownSaveOptions or None")
    if options.newline not in ("LF", "CRLF", "CR"):
        raise ExportOptionsRefusal("Markdown newline must be 'LF', 'CRLF' or 'CR'")
    if options.dialect not in ("gfm", "commonmark"):
        raise ExportOptionsRefusal("Markdown dialect must be 'gfm' or 'commonmark'")
    if options.whitespace not in ("trim", "preserve"):
        raise ExportOptionsRefusal("Markdown whitespace must be 'trim' or 'preserve'")
    if options.style not in ("sequential", "text-only", "visual"):
        raise ExportOptionsRefusal("Markdown style must be 'sequential', 'text-only' or 'visual'")
    if not isinstance(options.fonts, tuple) or any(
        not isinstance(spec, str) or not spec for spec in options.fonts
    ):
        raise ExportOptionsRefusal("Markdown fonts must be a tuple of font specification strings")
    if options.fonts and options.style != "visual":
        raise ExportOptionsRefusal("Markdown fonts requires style='visual'")
    if options.style == "visual" and not options.fonts:
        raise ExportOptionsRefusal("Markdown visual style requires admitted fonts")
    for name in ("image_saving_handler", "svg_image_saving_handler", "diagnostic_callback"):
        handler = getattr(options, name)
        if handler is not None and not callable(handler):
            raise ExportOptionsRefusal(f"{name} must be callable or None")
    return {"LF": "\n", "CRLF": "\r\n", "CR": "\r"}[options.newline]


def pptx_to_markdown(
    path: str | Path | InMemoryPackageSource,
    *,
    hidden: HiddenMode = "label",
    options: MarkdownSaveOptions | None = None,
) -> str:
    """Export a PPTX-family package to Markdown, one section per slide."""

    return "".join(
        chunk["markdown"]
        for chunk in pptx_to_chunks(path, hidden=hidden, options=options)["chunks"]
    )


def pptx_to_chunks(
    path: str | Path | InMemoryPackageSource,
    *,
    hidden: HiddenMode = "label",
    options: MarkdownSaveOptions | None = None,
) -> dict[str, Any]:
    """Export a PPTX-family package to per-slide Markdown chunks.

    Each chunk records ``index``, ``slide`` (1-based presentation order),
    ``part``, ``title``, ``markdown``, ``shape_ids`` (shapes that contributed
    Markdown, in reading order), ``hidden_shapes`` (labelled shapes with their
    reason), ``visible`` and ``reason``.
    """

    newline = _validate_options(options)
    if hidden not in HIDDEN_MODES:
        raise ValueError(f"hidden must be one of {HIDDEN_MODES}, got {hidden!r}")
    visual = options is not None and options.style == "visual"
    if visual and not isinstance(path, InMemoryPackageSource):
        path = InMemoryPackageSource(Path(path).read_bytes())
    with open_package_source(Path(path) if isinstance(path, str) else path) as zf:
        package = _Package(zf)
        slide_parts = _ordered_slide_parts(zf, sorted(package.names))
        size = _slide_size(package.xml("ppt/presentation.xml"))
        visual_slides = _visual_slides(path, slide_parts, size, hidden, options) if visual else {}
        chunks: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        omissions: list[dict[str, Any]] = []
        if options is not None and options.diagnostic_callback is not None:
            planned_omissions: list[dict[str, Any]] = []
            for number, part in enumerate(slide_parts, start=1):
                _slide_chunk(
                    package,
                    part,
                    number,
                    size,
                    hidden,
                    [],
                    planned_omissions,
                    options,
                    visual_slides.get(part),
                    preflight=True,
                )
            observe_warnings(
                _omission_warnings(planned_omissions, slide_parts), options.diagnostic_callback
            )
        for number, part in enumerate(slide_parts, start=1):
            chunk = _slide_chunk(
                package,
                part,
                number,
                size,
                hidden,
                excluded,
                omissions,
                options,
                visual_slides.get(part),
            )
            if chunk is None:
                continue
            if chunks:
                chunk["markdown"] = "\n" + chunk["markdown"]
            chunk["markdown"] = (
                chunk["markdown"].replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
            )
            chunk["index"] = len(chunks)
            chunks.append(chunk)
    return {
        "schema": CHUNKS_SCHEMA,
        "hidden": hidden,
        "slide_count": len(slide_parts),
        "chunks": chunks,
        "excluded": excluded,
        "omissions": omissions,
        "diagnostics": [warning.row() for warning in _omission_warnings(omissions, slide_parts)],
    }


def pptx_to_chunks_json(
    path: str | Path | InMemoryPackageSource,
    *,
    hidden: HiddenMode = "label",
    options: MarkdownSaveOptions | None = None,
) -> str:
    """Return :func:`pptx_to_chunks` as deterministic JSON."""

    return json.dumps(
        pptx_to_chunks(path, hidden=hidden, options=options), indent=2, sort_keys=True
    )


def _omission_warnings(
    omissions: list[dict[str, Any]], slide_parts: list[str]
) -> list[LoadSaveWarning]:
    return [
        LoadSaveWarning(
            "markdown",
            "unsupported_feature",
            f"Slide {row['slide']} shape {row['shape_id']}: "
            f"{row.get('detail', row['kind'])} omitted from Markdown",
            slide_parts[row["slide"] - 1],
        )
        for row in omissions
    ]


class MarkdownExportRefusal(ExportOptionsRefusal):
    """Hard visual export boundary, with a typed unsupported-feature diagnostic."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.diagnostic = LoadSaveWarning("markdown", "unsupported_feature", message)


def _visual_refusal(message: str, options: MarkdownSaveOptions) -> None:
    refusal = MarkdownExportRefusal(message)
    observe_warnings([refusal.diagnostic], options.diagnostic_callback, require_decision=False)
    raise refusal


def _markdown_xml(xml: bytes, part: str) -> ET.Element:
    """Normalize known Strict names in a read-only export tree, never package bytes."""
    root = _parse_effective_xml(xml, part)
    return _normalize_markdown_names(root)


def _normalize_markdown_names(root: ET.Element) -> ET.Element:
    """Normalize only known Strict names in a private, already selected tree."""
    for element in root.iter():
        namespace, separator, local = element.tag.partition("}")
        replacement = _STRICT_NAMES.get(namespace + separator)
        if replacement is not None:
            element.tag = replacement + local
        for name in tuple(element.attrib):
            namespace, separator, local = name.partition("}")
            replacement = _STRICT_NAMES.get(namespace + separator)
            if replacement is not None:
                element.set(replacement + local, element.attrib.pop(name))
    return root


class _Package:
    def __init__(self, zf: zipfile.ZipFile) -> None:
        self._zf = zf
        self.names = frozenset(zf.namelist())
        self._xml: dict[str, ET.Element | None] = {}

    def xml(self, part: str | None) -> ET.Element | None:
        if part is None or part not in self.names:
            return None
        if part not in self._xml:
            self._xml[part] = _markdown_xml(self._zf.read(part), part)
        return self._xml[part]

    def related(self, part: str, kind: str) -> str | None:
        directory, _, name = part.rpartition("/")
        rels_part = f"{directory}/_rels/{name}.rels"
        if rels_part not in self.names:
            return None
        for rel in _extract_relationships(self._zf, [rels_part]):
            if rel.type.endswith(f"/{kind}") and rel.target_mode != "External":
                return _resolve_target(part, rel.target)
        return None


@dataclass(frozen=True)
class _Placeholder:
    type: str
    idx: str | None


@dataclass(frozen=True)
class _Block:
    shape_id: str | None
    markdown: str
    reason: str | None


@dataclass(frozen=True)
class _VisualSlide:
    data: bytes
    shape_ids: tuple[str, ...]
    omissions: tuple[str, ...]


def _visual_slides(
    source: InMemoryPackageSource,
    slide_parts: list[str],
    size: tuple[int, int] | None,
    hidden: str,
    options: MarkdownSaveOptions,
) -> dict[str, _VisualSlide]:
    """Stage actual first-party pixels before exposing any saving callback."""
    from .editions import commercial_module

    feature = "Visual Markdown export"
    font_module = commercial_module("render_fonts", feature)
    package_module = commercial_module("render_package", feature)
    scene_module = commercial_module("render_scene", feature)
    raster_module = commercial_module("render_raster", feature)
    try:
        fonts = font_module.admit_font_specs(options.fonts)
    except RenderRefusal as exc:
        _visual_refusal(f"Markdown visual font admission: {exc}", options)

    selected_parts = frozenset(slide_parts)

    class VisualDeckBuilder(scene_module._DeckBuilder):
        def _renderer_xml(self, part: str) -> ET.Element:
            root = super()._renderer_xml(part)
            if part in selected_parts:
                # Select MC with the renderer's own capabilities first. Filtering
                # the private tree preserves lexical namespace admission and
                # removes excluded objects before geometry/font resolution.
                _normalize_markdown_names(root)
                for tree in root.findall(".//p:cSld/p:spTree", NS):
                    _remove_visual_exclusions(tree, size, top_level=True)
            return root

    try:
        package = package_module.read_package_bytes(
            Path("in-memory presentation"), source.read_bytes()
        )
        builder = VisualDeckBuilder(package, fonts, show_hidden_slides=hidden != "exclude")
        deck = builder.build()
        builder.log.raise_if_any()
        return {
            slide.part: _VisualSlide(
                raster_module.render_slide_png(slide, fonts),
                tuple(
                    dict.fromkeys(
                        primitive.source.shape_id
                        for primitive in slide.primitives
                        if primitive.source is not None
                        and primitive.source.part == slide.part
                        and primitive.source.shape_id is not None
                    )
                ),
                slide.omissions,
            )
            for slide in deck.slides
        }
    except RenderRefusal as exc:
        _visual_refusal(f"Markdown visual rendering: {exc}", options)


def _remove_visual_exclusions(
    tree: ET.Element, size: tuple[int, int] | None, *, top_level: bool
) -> None:
    """Draw slide-visible objects only; labelled hidden text stays outside PNG."""
    for element in _shape_child_elements(tree):
        props = element.find("./*/p:cNvPr", NS)
        if (props is not None and props.get("hidden") in {"1", "true", "on"}) or (
            top_level and _off_canvas(element, size)
        ):
            tree.remove(element)
        elif _local_name(element.tag) == "grpSp":
            _remove_visual_exclusions(element, size, top_level=False)


def _visual_markdown(
    data: bytes, part: str, number: int, heading: str, options: MarkdownSaveOptions
) -> str:
    handler = options.image_saving_handler
    if handler is None:
        destination = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    else:
        destination = handler(
            MarkdownImage(data, "image/png", f"slide-{number}.png", part, number, None)
        )
        if destination is None:
            return ""
        if not isinstance(destination, str):
            raise TypeError("an image-saving handler must return a destination string or None")
    from urllib.parse import quote

    destination = quote(destination, safe="/:#?&=%@+;,$!~*'()-._")
    alt = _escape_inline(heading)
    if options.whitespace == "preserve":
        alt = alt.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "&#10;")
    return f"![{alt}](<{destination}>)"


@dataclass
class _SlideWalk:
    package: _Package
    slide_number: int
    size: tuple[int, int] | None
    layout: ET.Element | None
    master: ET.Element | None
    hidden: str
    excluded: list[dict[str, Any]]
    omissions: list[dict[str, Any]]
    title: str | None = None
    title_id: str | None = None
    part: str = ""
    options: MarkdownSaveOptions | None = None
    preflight: bool = False
    visual_shape_ids: tuple[str, ...] = ()


def _slide_chunk(
    package: _Package,
    part: str,
    number: int,
    size: tuple[int, int] | None,
    hidden: str,
    excluded: list[dict[str, Any]],
    omissions: list[dict[str, Any]],
    options: MarkdownSaveOptions | None = None,
    visual_slide: _VisualSlide | None = None,
    *,
    preflight: bool = False,
) -> dict[str, Any] | None:
    root = package.xml(part)
    if root is None:
        raise ValueError(f"slide part {part} is missing from the package")
    slide_hidden = root.get("show") in {"0", "false"}
    if slide_hidden and hidden == "exclude":
        excluded.append({"slide": number, "shape_id": None, "reason": HIDDEN_SLIDE})
        return None

    layout_part = package.related(part, "slideLayout")
    master_part = package.related(layout_part, "slideMaster") if layout_part else None
    walk = _SlideWalk(
        package=package,
        slide_number=number,
        size=size,
        layout=package.xml(layout_part),
        master=package.xml(master_part),
        hidden=hidden,
        excluded=excluded,
        omissions=omissions,
        part=part,
        options=options,
        preflight=preflight,
        visual_shape_ids=visual_slide.shape_ids if visual_slide is not None else (),
    )
    blocks: list[_Block] = []
    _walk_shapes(
        walk,
        _shape_elements(root),
        True,
        HIDDEN_SLIDE if slide_hidden else None,
        blocks,
    )

    preserve = options is not None and options.whitespace == "preserve"
    if preserve and walk.title is not None:
        heading = f'<h1 style="white-space: pre-wrap">{_html_literal(walk.title)}</h1>'
    else:
        title = _escape_heading(walk.title) if walk.title else f"Slide {number}"
        heading = f"# {title}"
    sections = [f"<!-- Slide {number} -->\n{heading}"]
    if slide_hidden:
        sections.append(_label(HIDDEN_SLIDE))
    if visual_slide is not None and not preflight:
        image = _visual_markdown(
            visual_slide.data, part, number, walk.title or f"Slide {number}", options
        )
        if image:
            sections.append(image)
        for diagnostic in visual_slide.omissions:
            omissions.append(
                {"slide": number, "shape_id": None, "kind": "native_render", "detail": diagnostic}
            )
    elif visual_slide is not None:
        omissions.extend(
            {"slide": number, "shape_id": None, "kind": "native_render", "detail": diagnostic}
            for diagnostic in visual_slide.omissions
        )
    for block in blocks:
        if visual_slide is not None and block.reason in (None, HIDDEN_SLIDE):
            continue
        if block.reason in (None, HIDDEN_SLIDE):
            sections.append(block.markdown)
        else:
            sections.append(_blockquote(f"{_label(block.reason)}\n\n{block.markdown}"))
    notes = _speaker_notes(package, package.related(part, "notesSlide"), preserve=preserve)
    if notes or (preserve and notes is not None):
        sections.append(f"**Speaker notes:**\n\n{_fenced(notes)}")

    shape_ids = [walk.title_id] if walk.title is not None else []
    shape_ids += [block.shape_id for block in blocks]
    if visual_slide is not None and not preflight:
        shape_ids = list(
            dict.fromkeys(
                ([walk.title_id] if walk.title is not None else [])
                + (list(visual_slide.shape_ids) if image else [])
                + [block.shape_id for block in blocks if block.reason not in (None, HIDDEN_SLIDE)]
            )
        )
    return {
        "slide": number,
        "part": part,
        "title": walk.title,
        "markdown": "\n\n".join(sections) + "\n",
        "shape_ids": shape_ids,
        "hidden_shapes": [
            {"id": block.shape_id, "reason": block.reason}
            for block in blocks
            if block.reason not in (None, HIDDEN_SLIDE)
        ],
        "visible": not slide_hidden,
        "reason": HIDDEN_SLIDE if slide_hidden else "rendered",
    }


def _walk_shapes(
    walk: _SlideWalk,
    elements: list[ET.Element],
    top_level: bool,
    inherited: str | None,
    blocks: list[_Block],
) -> None:
    for el in elements:
        props = el.find("./*/p:cNvPr", NS)
        shape_id = props.get("id") if props is not None else None
        reason = inherited
        if (
            reason is None
            and props is not None
            and props.get("hidden")
            in {
                "1",
                "true",
                "on",
            }
        ):
            reason = HIDDEN_SHAPE
        if reason is None and top_level and _off_canvas(el, walk.size):
            reason = OFF_CANVAS
        if reason not in (None, HIDDEN_SLIDE) and walk.hidden == "exclude":
            walk.excluded.append(
                {"slide": walk.slide_number, "shape_id": shape_id, "reason": reason}
            )
            continue

        tag = _local_name(el.tag)
        if tag == "grpSp":
            _walk_shapes(walk, _shape_child_elements(el), False, reason, blocks)
            continue
        placeholder = _placeholder(el)
        if (
            placeholder is not None
            and placeholder.type in _TITLE_TYPES
            and walk.title is None
            and reason in (None, HIDDEN_SLIDE)
        ):
            preserve = walk.options is not None and walk.options.whitespace == "preserve"
            title = _title_text(el, preserve=preserve)
            if title or (preserve and el.find("./p:txBody/a:p", NS) is not None):
                walk.title, walk.title_id = title, shape_id
                continue
        markdown = _shape_markdown(walk, el, tag, placeholder, shape_id)
        if markdown:
            blocks.append(_Block(shape_id, markdown, reason))


def _shape_markdown(
    walk: _SlideWalk,
    el: ET.Element,
    tag: str,
    placeholder: _Placeholder | None,
    shape_id: str | None,
) -> str:
    if tag == "pic":
        if (
            walk.options is None
            or walk.options.style != "sequential"
            or (
                walk.options.image_saving_handler is None
                and walk.options.svg_image_saving_handler is None
            )
        ):
            _omit(walk, shape_id, "picture")
            return ""
        return _picture_markdown(walk, el, shape_id)
    if tag == "graphicFrame":
        tables = [_extract_table(tbl) for tbl in el.findall(".//a:tbl", NS)]
        if tables:
            return "\n\n".join(
                _table_markdown(table, walk.options) for table in tables if table.rows
            )
        data = el.find(".//a:graphicData", NS)
        uri = data.get("uri", "") if data is not None else ""
        _omit(
            walk, shape_id, _GRAPHIC_KINDS.get(uri, _STRICT_GRAPHIC_KINDS.get(uri, "graphic_frame"))
        )
        return ""
    body = el.find("./p:txBody", NS)
    if body is None:
        return ""
    return _text_body_markdown(
        body,
        _style_chain(walk, body, placeholder),
        preserve=walk.options is not None and walk.options.whitespace == "preserve",
    )


def _picture_markdown(walk: _SlideWalk, el: ET.Element, shape_id: str | None) -> str:
    blips = [node for node in el.iter() if _local_name(node.tag) == "svgBlip"]
    if not blips:
        blips = el.findall(".//a:blip", NS)
    embed = blips[0].get(f"{{{NS['r']}}}embed") if blips else None
    directory, _, name = walk.part.rpartition("/")
    rels_part = f"{directory}/_rels/{name}.rels"
    target = None
    if rels_part in walk.package.names:
        for rel in _extract_relationships(walk.package._zf, [rels_part]):
            if rel.id == embed and rel.type.endswith("/image") and rel.target_mode != "External":
                target = _resolve_target(walk.part, rel.target)
                break
    if target is None or target not in walk.package.names:
        _omit(walk, shape_id, "picture")
        return ""
    types = walk.package.xml("[Content_Types].xml")
    content_type = "application/octet-stream"
    if types is not None:
        extension = target.rsplit(".", 1)[-1].lower()
        for node in types:
            if (
                _local_name(node.tag) == "Override"
                and node.get("PartName", "").lstrip("/") == target
            ) or (
                _local_name(node.tag) == "Default"
                and node.get("Extension", "").lower() == extension
            ):
                content_type = node.get("ContentType", content_type)
    handler = walk.options.image_saving_handler
    if content_type == "image/svg+xml" and walk.options.svg_image_saving_handler is not None:
        handler = walk.options.svg_image_saving_handler
    if handler is None:
        _omit(walk, shape_id, "picture")
        return ""
    if walk.preflight:
        return ""
    image = MarkdownImage(
        walk.package._zf.read(target),
        content_type,
        f"slide-{walk.slide_number}-shape-{shape_id or 'unknown'}-{Path(target).name}",
        target,
        walk.slide_number,
        shape_id,
    )
    destination = handler(image)
    if destination is None:
        return ""
    if not isinstance(destination, str):
        raise TypeError("an image-saving handler must return a destination string or None")
    # Angle-bracket destinations support spaces; encode delimiter/control bytes.
    from urllib.parse import quote

    destination = quote(destination, safe="/:#?&=%@+;,$!~*'()-._")
    props = el.find("./*/p:cNvPr", NS)
    alt = props.get("descr", props.get("name", "")) if props is not None else ""
    return f"![{_escape_inline(alt)}](<{destination}>)"


def _omit(walk: _SlideWalk, shape_id: str | None, kind: str) -> None:
    if shape_id in walk.visual_shape_ids:
        return
    walk.omissions.append({"slide": walk.slide_number, "shape_id": shape_id, "kind": kind})


def _placeholder(el: ET.Element) -> _Placeholder | None:
    ph = el.find("./*/p:nvPr/p:ph", NS)
    if ph is None:
        return None
    return _Placeholder(type=ph.get("type", "obj"), idx=ph.get("idx"))


def _style_chain(
    walk: _SlideWalk, body: ET.Element, placeholder: _Placeholder | None
) -> list[ET.Element]:
    """List styles that supply paragraph defaults, nearest first."""

    chain = [body.find("./a:lstStyle", NS)]
    if placeholder is not None:
        layout_shape = _matching_placeholder(walk.layout, placeholder, by_idx=True)
        master_shape = _matching_placeholder(
            walk.master, _master_placeholder(placeholder), by_idx=False
        )
        for shape in (layout_shape, master_shape):
            if shape is not None:
                chain.append(shape.find("./p:txBody/a:lstStyle", NS))
    if walk.master is not None:
        if placeholder is None or placeholder.type in _OTHER_TYPES:
            style = "otherStyle"
        elif placeholder.type in _TITLE_TYPES:
            style = "titleStyle"
        else:
            style = "bodyStyle"
        chain.append(walk.master.find(f"./p:txStyles/p:{style}", NS))
    return [style for style in chain if style is not None]


def _master_placeholder(placeholder: _Placeholder) -> _Placeholder:
    if placeholder.type in _TITLE_TYPES:
        return _Placeholder("title", None)
    if placeholder.type in _OTHER_TYPES:
        return _Placeholder(placeholder.type, None)
    return _Placeholder("body", None)


def _matching_placeholder(
    root: ET.Element | None, placeholder: _Placeholder, *, by_idx: bool
) -> ET.Element | None:
    if root is None:
        return None
    candidates = [
        (shape, found)
        for shape in root.findall(".//p:cSld/p:spTree//p:sp", NS)
        if (found := _placeholder(shape)) is not None
    ]
    if by_idx and placeholder.idx is not None:
        for shape, found in candidates:
            if found.idx == placeholder.idx:
                return shape
    for shape, found in candidates:
        if found.type == placeholder.type:
            return shape
    return None


def _list_kind(
    paragraph: ET.Element, level: int, chain: list[ET.Element]
) -> tuple[str | None, int]:
    sources = [paragraph.find("./a:pPr", NS)]
    sources += [style.find(f"./a:lvl{level + 1}pPr", NS) for style in chain]
    for props in sources:
        if props is None:
            continue
        for child in props:
            name = _local_name(child.tag)
            if name in _BULLET_KINDS:
                start = int(child.get("startAt", "1")) if name == "buAutoNum" else 1
                return _BULLET_KINDS[name], start
    return None, 1


def _text_body_markdown(
    body: ET.Element, chain: list[ET.Element], *, preserve: bool = False
) -> str:
    segments: list[tuple[bool, str]] = []
    widths: list[int] = []
    counters: dict[int, int] = {}
    for paragraph in body.findall("./a:p", NS):
        text = _paragraph_text(paragraph)
        if not preserve and not text.strip():
            continue
        props = paragraph.find("./a:pPr", NS)
        level = min(max(int(props.get("lvl", "0")) if props is not None else 0, 0), 8)
        kind, start = _list_kind(paragraph, level, chain)
        if kind is None:
            widths, counters = [], {}
            segments.append((False, _escape_block(text, preserve=preserve)))
            continue
        depth = min(level, len(widths))
        counters = {key: value for key, value in counters.items() if key <= depth}
        if kind == "ordered":
            counters[depth] = counters.get(depth, start - 1) + 1
            marker = f"{counters[depth]}."
        else:
            counters.pop(depth, None)
            marker = "-"
        indent = sum(widths[:depth])
        widths = widths[:depth] + [len(marker) + 1]
        lines = _escape_block(text, preserve=preserve).split("\n")
        continuation = " " * (indent + len(marker) + 1)
        item = " " * indent + f"{marker} {lines[0]}"
        item += "".join(f"\n{continuation}{line}" for line in lines[1:])
        segments.append((True, item))
    out = ""
    for position, (is_item, text) in enumerate(segments):
        if position:
            out += "\n" if is_item and segments[position - 1][0] else "\n\n"
        out += text
    return out


def _title_text(el: ET.Element, *, preserve: bool = False) -> str:
    paragraphs = [_paragraph_text(paragraph) for paragraph in el.findall("./p:txBody/a:p", NS)]
    if preserve:
        return "\n".join(paragraphs).replace("\v", "\n")
    return " ".join(
        " ".join(paragraph.replace("\v", " ").split())
        for paragraph in paragraphs
        if paragraph.strip()
    )


def _table_markdown(table: Table, options: MarkdownSaveOptions | None) -> str:
    preserve = options is not None and options.whitespace == "preserve"
    if options is None or options.dialect == "gfm":
        return _pipe_table(table, preserve=preserve)
    width = max(table.col_count, 1)
    lines = ["<table>"]
    for index, row in enumerate(table.rows):
        tag = "th" if index == 0 else "td"
        cells = row + [""] * (width - len(row))
        content = "".join(f"<{tag}>{_html_cell(cell, preserve=preserve)}</{tag}>" for cell in cells)
        lines.append(f"<tr>{content}</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _html_literal(text: str) -> str:
    """Escape literal text onto one HTML line, without trimming user whitespace."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\v", "\n")
    return _escape_html(text, quote=False).replace("|", "&#124;").replace("\n", "&#10;")


def _html_cell(text: str, *, preserve: bool) -> str:
    if preserve:
        # An empty span prevents HTML's initial-newline removal in a pre element.
        return f"<pre><span></span>{_html_literal(text)}</pre>"
    lines = [line.strip() for line in re.split(r"[\n\v]", text)]
    return "<br>".join(_html_literal(line) for line in lines if line)


def _pipe_table(table: Table, *, preserve: bool = False) -> str:
    width = max(table.col_count, 1)
    rows = [row + [""] * (width - len(row)) for row in table.rows]
    lines = [_table_row(rows[0], preserve=preserve), "| " + " | ".join(["---"] * width) + " |"]
    lines += [_table_row(row, preserve=preserve) for row in rows[1:]]
    return "\n".join(lines)


def _table_row(cells: list[str], *, preserve: bool = False) -> str:
    return "| " + " | ".join(_escape_cell(cell, preserve=preserve) for cell in cells) + " |"


def _escape_inline(text: str) -> str:
    return _ENTITY.sub(r"\\&", _INLINE_SPECIALS.sub(r"\\\1", text))


def _escape_block(text: str, *, preserve: bool = False) -> str:
    """Escape a trimmed paragraph or fence its literal text, including empty text."""

    if preserve:
        return _fenced(text.replace("\v", "\n"))

    lines = [line.strip() for line in text.split("\v")]
    escaped = [
        _LINE_START_MARKER.sub(_escape_marker, _escape_inline(line)) for line in lines if line
    ]
    return "\\\n".join(escaped)


def _escape_marker(match: re.Match[str]) -> str:
    marker = match.group(1)
    return f"{marker[:-1]}\\{marker[-1]}"


def _escape_heading(text: str) -> str:
    escaped = _escape_inline(text)
    return re.sub(r"#", r"\\#", escaped) if escaped.endswith("#") else escaped


def _escape_cell(text: str, *, preserve: bool = False) -> str:
    if preserve:
        return _html_cell(text, preserve=True)
    lines = [line.strip() for line in re.split(r"[\n\v]", text)]
    return "<br>".join(_escape_inline(line).replace("|", "\\|") for line in lines if line)


def _label(reason: str) -> str:
    return f"*[hidden: {reason}]*"


def _blockquote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.split("\n"))


def _fenced(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def _speaker_notes(
    package: _Package, notes_part: str | None, *, preserve: bool = False
) -> str | None:
    root = package.xml(notes_part)
    if root is None:
        return None
    for shape in root.iter(f"{{{NS['p']}}}sp"):
        ph = shape.find(".//p:ph", NS)
        if ph is not None and ph.get("type") == "body":
            lines = [
                _paragraph_text(paragraph).replace("\v", "\n")
                for paragraph in shape.findall(".//a:p", NS)
            ]
            notes = "\n".join(lines)
            return notes if preserve else notes.strip("\n")
    return None


def _slide_size(presentation: ET.Element | None) -> tuple[int, int] | None:
    size = presentation.find("./p:sldSz", NS) if presentation is not None else None
    if size is None:
        return None
    try:
        return int(size.get("cx", "")), int(size.get("cy", ""))
    except ValueError:
        return None


def _off_canvas(el: ET.Element, size: tuple[int, int] | None) -> bool:
    """Mirror ``wolf extract``: own transform only, entirely outside the slide."""

    if size is None:
        return False
    tag = _local_name(el.tag)
    if tag == "graphicFrame":
        xfrm = el.find("./p:xfrm", NS)
    elif tag == "grpSp":
        xfrm = el.find("./p:grpSpPr/a:xfrm", NS)
    else:
        xfrm = el.find("./p:spPr/a:xfrm", NS)
    off = xfrm.find("./a:off", NS) if xfrm is not None else None
    if off is None:
        return False
    try:
        x, y = int(off.get("x", "")), int(off.get("y", ""))
    except ValueError:
        return False
    ext = xfrm.find("./a:ext", NS)
    cx = _int_or_zero(ext.get("cx") if ext is not None else None)
    cy = _int_or_zero(ext.get("cy") if ext is not None else None)
    width, height = size
    return x + cx <= 0 or y + cy <= 0 or x >= width or y >= height


def _int_or_zero(value: str | None) -> int:
    try:
        return int(value or "")
    except ValueError:
        return 0
