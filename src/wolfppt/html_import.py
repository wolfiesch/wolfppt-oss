"""Offline, editable HTML-subset import. See docs/features/html-import.md."""

from __future__ import annotations

import io
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from .dml.color import RGBColor
from .enum.text import PP_ALIGN
from .shape_picture_inspection import PictureImage
from .util import Pt

if TYPE_CHECKING:
    from .presentation_slides import Slide, SlideCollection


class HtmlImportError(ValueError):
    """Unsupported markup, resource, or unrepresentable HTML layout."""


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[_Node | str] = field(default_factory=list)


_INLINE = {"span", "b", "strong", "i", "em", "u", "br"}
_PARAGRAPHS = {"p", "h1", "h2", "h3", "h4", "h5", "h6"}
_CONTAINERS = {"root", "html", "body", "div", "section"}
_TABLE = {"table", "thead", "tbody", "tfoot", "tr", "td", "th"}
_TAGS = _INLINE | _PARAGRAPHS | _CONTAINERS | _TABLE | {"img"}
_VOID = {"img", "br"}
_MARGIN = 36.0
_GAP = 8.0


class _Parser(HTMLParser):
    def __init__(self, html: str):
        super().__init__(convert_charrefs=False)
        self.root = _Node("root")
        self.stack = [self.root]
        self.count = 0
        self.feed(html)
        self.close()
        if len(self.stack) != 1:
            raise HtmlImportError(f"unclosed <{self.stack[-1].tag}>")

    def handle_starttag(self, tag, attrs):
        if tag not in _TAGS or tag == "root":
            raise HtmlImportError(f"unsupported HTML element <{tag}>")
        self.count += 1
        if self.count > 10000 or len(self.stack) > 64:
            raise HtmlImportError("HTML exceeds 10000 elements or 64 nesting levels")
        values = {}
        allowed = {"style"} | ({"src", "width", "height"} if tag == "img" else set())
        for key, value in attrs:
            if key not in allowed or key in values or value is None:
                raise HtmlImportError(f"unsupported or duplicate attribute {key!r} on <{tag}>")
            values[key] = value
        parent = self.stack[-1].tag
        if tag in {"thead", "tbody", "tfoot"}:
            valid = parent == "table"
        elif tag == "tr":
            valid = parent in {"table", "thead", "tbody", "tfoot"}
        elif tag in {"td", "th"}:
            valid = parent == "tr"
        elif parent in {"table", "thead", "tbody", "tfoot", "tr"}:
            valid = False
        elif tag in _INLINE:
            valid = parent in _CONTAINERS | _PARAGRAPHS | _INLINE | {"td", "th"}
        elif tag in _PARAGRAPHS:
            valid = parent in _CONTAINERS | {"td", "th"}
        else:
            valid = parent in _CONTAINERS
        if not valid:
            raise HtmlImportError(f"unsupported nesting <{tag}> inside <{parent}>")
        node = _Node(tag, values)
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if len(self.stack) == 1 or self.stack[-1].tag != tag:
            raise HtmlImportError(f"mismatched closing tag </{tag}>")
        self.stack.pop()

    def handle_data(self, data):
        if any(ord(c) < 32 and c not in "\t\r\n" for c in data):
            raise HtmlImportError("HTML contains unsupported control characters")
        if self.stack[-1].tag in {"table", "thead", "tbody", "tfoot", "tr"} and data.strip():
            raise HtmlImportError("text outside a table cell")
        self.stack[-1].children.append(data)

    def handle_entityref(self, name):
        self.handle_data(unescape(f"&{name};"))

    def handle_charref(self, name):
        try:
            value = int(name[1:], 16) if name.lower().startswith("x") else int(name)
        except ValueError as exc:
            raise HtmlImportError("unsupported numeric character reference") from exc
        if not (
            value in {9, 10, 13}
            or 0x20 <= value <= 0xD7FF
            or 0xE000 <= value <= 0xFFFD
            or 0x10000 <= value <= 0x10FFFF
        ):
            raise HtmlImportError("character reference is unsupported by XML presentation text")
        self.handle_data(chr(value))

    def handle_decl(self, decl):
        if decl.lower() != "doctype html":
            raise HtmlImportError("only <!DOCTYPE html> is supported")

    def handle_pi(self, data):
        raise HtmlImportError("processing instructions are unsupported")

    def unknown_decl(self, data):
        raise HtmlImportError("unsupported HTML declaration")


@dataclass(frozen=True)
class _Style:
    size: float = 18.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: str = "000000"
    align: str = "left"


def _length(value: str, *, pixels: bool = False) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(pt|px)?", value.strip())
    if not match or (not pixels and not match[2]):
        raise HtmlImportError(f"unsupported length {value!r}; use positive pt or px")
    result = float(match[1]) * (0.75 if match[2] == "px" or (pixels and not match[2]) else 1)
    if not math.isfinite(result) or result <= 0:
        raise HtmlImportError(f"invalid positive length {value!r}")
    return result


def _style(node: _Node, inherited: _Style) -> tuple[_Style, bool, bool]:
    style = inherited
    if node.tag in {"b", "strong", "th"}:
        style = replace(style, bold=True)
    if node.tag in {"i", "em"}:
        style = replace(style, italic=True)
    if node.tag == "u":
        style = replace(style, underline=True)
    if node.tag.startswith("h") and node.tag in _PARAGRAPHS:
        style = replace(
            style,
            size={"h1": 32, "h2": 28, "h3": 24, "h4": 22, "h5": 20, "h6": 18}[node.tag],
            bold=True,
        )
    before = after = False
    for declaration in node.attrs.get("style", "").split(";"):
        if not declaration.strip():
            continue
        key, sep, value = declaration.partition(":")
        key, value = key.strip().lower(), value.strip().lower()
        if not sep:
            raise HtmlImportError(f"invalid CSS declaration {declaration!r}")
        if key in {"page-break-before", "page-break-after"}:
            if node.tag in _INLINE | {"td", "th", "tr", "thead", "tbody", "tfoot"} or value not in {
                "always",
                "auto",
            }:
                raise HtmlImportError(f"unsupported {key}: {value}")
            if key == "page-break-before":
                before = value == "always"
            else:
                after = value == "always"
        elif key == "font-size":
            size = _length(value)
            if size < 1 or size > 400:
                raise HtmlImportError("font-size must be between 1pt and 400pt")
            style = replace(style, size=size)
        elif key == "font-weight" and value in {"normal", "bold"}:
            style = replace(style, bold=value == "bold")
        elif key == "font-style" and value in {"normal", "italic"}:
            style = replace(style, italic=value == "italic")
        elif key == "text-decoration" and value in {"none", "underline"}:
            style = replace(style, underline=value == "underline")
        elif key == "color" and re.fullmatch(r"#[0-9a-f]{6}", value):
            style = replace(style, color=value[1:].upper())
        elif (
            key == "text-align"
            and value in {"left", "center", "right", "justify"}
            and node.tag not in _INLINE
        ):
            style = replace(style, align=value)
        else:
            raise HtmlImportError(f"unsupported CSS {key}: {value}")
    return style, before, after


@dataclass
class _Paragraph:
    runs: list[tuple[str, _Style]]
    style: _Style


def _inline(children, style):
    runs = []
    for child in children:
        if isinstance(child, str):
            text = re.sub(r"[ \t\r\n\f]+", " ", child)
            if text:
                runs.append((text, style))
        else:
            current, _, _ = _style(child, style)
            if child.tag not in _INLINE:
                raise HtmlImportError(f"unsupported inline element <{child.tag}>")
            if child.tag == "br":
                runs.append(("\n", current))
            else:
                runs.extend(_inline(child.children, current))
    return runs


def _paragraph(children, style):
    # Collapse HTML whitespace across element boundaries, preserving explicit br.
    result = []
    previous = ""
    for text, current in _inline(children, style):
        if previous in {"", " ", "\n"}:
            text = text.lstrip(" ")
        if not text:
            continue
        result.append((text, current))
        previous = text[-1]
    while result and result[-1][0].endswith(" "):
        text, current = result.pop()
        if text.rstrip(" "):
            result.append((text.rstrip(" "), current))
    return _Paragraph(result, replace(style, size=max([style.size] + [s.size for _, s in result])))


def _blocks(node, inherited):
    style, before, after = _style(node, inherited)
    if before:
        yield None
    pending = []
    for child in node.children:
        if isinstance(child, str) or child.tag in _INLINE:
            pending.append(child)
            continue
        paragraph = _paragraph(pending, style)
        if paragraph.runs:
            yield paragraph
        pending = []
        if child.tag in _CONTAINERS:
            yield from _blocks(child, style)
        elif child.tag in _PARAGRAPHS:
            current, first, last = _style(child, style)
            if first:
                yield None
            yield _paragraph(child.children, current)
            if last:
                yield None
        elif child.tag in {"img", "table"}:
            current, first, last = _style(child, style)
            if first:
                yield None
            yield (child, current)
            if last:
                yield None
        else:
            raise HtmlImportError(f"unexpected <{child.tag}>")
    paragraph = _paragraph(pending, style)
    if paragraph.runs:
        yield paragraph
    if after:
        yield None


def _lines(paragraph: _Paragraph, width: float):
    """Conservative one-em advances, explicit soft wrapping, no font lookup."""
    lines = [[]]
    used = 0.0
    for text, style in paragraph.runs:
        for char in text:
            if char == "\n":
                lines.append([])
                used = 0
                continue
            if style.size > width:
                raise HtmlImportError("text character exceeds available width")
            if used + style.size > width and lines[-1]:
                lines.append([])
                used = 0
            line = lines[-1]
            if line and line[-1][1] == style:
                line[-1] = (line[-1][0] + char, style)
            else:
                line.append((char, style))
            used += style.size
    return lines


def _line_height(line, style):
    return max([style.size] + [run_style.size for _, run_style in line]) * 1.25


def _table_rows(node, inherited, width):
    rows = []
    columns = None

    def visit(parent, style):
        for child in parent.children:
            if isinstance(child, str):
                continue
            current, _, _ = _style(child, style)
            if child.tag in {"thead", "tbody", "tfoot"}:
                yield from visit(child, current)
            else:
                yield child, current

    for row, row_style in visit(node, inherited):
        cells = [c for c in row.children if isinstance(c, _Node)]
        if not cells or (columns is not None and len(cells) != columns):
            raise HtmlImportError("tables must have nonempty rectangular rows")
        columns = len(cells)
        planned = []
        height = 0.0
        for cell in cells:
            cell_style, _, _ = _style(cell, row_style)
            paragraphs = list(_blocks(cell, cell_style))
            if not paragraphs:
                paragraphs = [_Paragraph([], cell_style)]
            if not all(isinstance(p, _Paragraph) for p in paragraphs):
                raise HtmlImportError("table cells support text paragraphs only")
            wrapped = [(p, _lines(p, width / columns - 8)) for p in paragraphs]
            height = max(
                height,
                sum(_line_height(line, p.style) for p, lines in wrapped for line in lines) + 8,
            )
            planned.append(wrapped)
        rows.append((planned, height))
    if not rows:
        raise HtmlImportError("empty tables are unsupported")
    return rows


def _image(node, resources, width, height):
    src = node.attrs.get("src", "")
    parsed = urlsplit(src)
    if (
        not src
        or parsed.scheme
        or parsed.netloc
        or src.startswith(("/", "\\"))
        or src not in resources
    ):
        raise HtmlImportError(f"image src {src!r} requires an explicit local resource key")
    resource = resources[src]
    if isinstance(resource, bytes):
        blob = resource
    elif isinstance(resource, Path):
        try:
            blob = Path(resource).read_bytes()
        except OSError as exc:
            raise HtmlImportError(f"cannot read supplied resource {src!r}") from exc
    else:
        raise HtmlImportError("resources must contain PNG/JPEG bytes or local paths")
    try:
        image = PictureImage.from_blob(blob)
        if image.ext not in {"png", "jpg", "jpeg"}:
            raise ValueError("only PNG and JPEG are supported")
        px, py = image.size
        if px <= 0 or py <= 0:
            raise ValueError("empty image")
    except (ValueError, OSError) as exc:
        raise HtmlImportError(f"unsupported or corrupt image {src!r}") from exc
    w = _length(node.attrs["width"], pixels=True) if "width" in node.attrs else None
    h = _length(node.attrs["height"], pixels=True) if "height" in node.attrs else None
    if w is None and h is None:
        scale = min(0.75, width / px, height / py)
        w, h = px * scale, py * scale
    elif w is None:
        w = h * px / py
    elif h is None:
        h = w * py / px
    if w > width or h > height:
        raise HtmlImportError("image exceeds slide content area")
    return blob, w, h


def _plan(html, resources, width, height):
    if not isinstance(html, str):
        raise TypeError("html must be a string")
    if re.search(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]", html):
        raise HtmlImportError("HTML contains characters unsupported by XML presentation text")
    if len(html.encode("utf-8")) > 1048576:
        raise HtmlImportError("HTML exceeds 1 MiB")
    if width <= 0 or height <= 0:
        raise HtmlImportError("slide must be larger than the 36pt margins")
    root = _Parser(html).root
    pages = [[]]
    y = 0.0

    def page_break():
        nonlocal y
        if pages[-1]:
            pages.append([])
        y = 0

    def place(kind, data, size):
        nonlocal y
        if size > height:
            raise HtmlImportError(f"{kind} exceeds slide content height")
        if y + size > height:
            page_break()
        pages[-1].append((kind, y, size, data))
        y += size + _GAP

    for block in _blocks(root, _Style()):
        if block is None:
            page_break()
        elif isinstance(block, _Paragraph):
            lines = _lines(block, width)
            segment, total = [], 0.0
            for line in lines:
                size = _line_height(line, block.style)
                if size > height:
                    raise HtmlImportError("text line exceeds slide content height")
                if y + total + size > height:
                    if segment:
                        place("text", (block, segment), total)
                        segment, total = [], 0
                    page_break()
                segment.append(line)
                total += size
            if segment:
                place("text", (block, segment), total)
        else:
            node, style = block
            if node.tag == "img":
                blob, w, h = _image(node, resources, width, height)
                place("image", (blob, w, h), h)
            else:
                rows = _table_rows(node, style, width)
                segment, total = [], 0.0
                for cells, size in rows:
                    if size > height:
                        raise HtmlImportError("table row exceeds slide content height")
                    if y + total + size > height:
                        if segment:
                            place("table", segment, total)
                            segment, total = [], 0
                        page_break()
                    segment.append((cells, size))
                    total += size
                if segment:
                    place("table", segment, total)
    if not pages[-1]:
        pages.pop()
    return pages


def _write_paragraph(paragraph, spec, lines):
    paragraph.alignment = {
        "left": PP_ALIGN.LEFT,
        "center": PP_ALIGN.CENTER,
        "right": PP_ALIGN.RIGHT,
        "justify": PP_ALIGN.JUSTIFY,
    }[spec.style.align]
    paragraph.space_before = Pt(0)
    paragraph.space_after = Pt(0)
    paragraph.line_spacing = Pt(max(_line_height(line, spec.style) for line in lines))
    for index, line in enumerate(lines):
        if index:
            paragraph.add_line_break()
        for text, style in line:
            run = paragraph.add_run()
            run.text = text
            run.font.size = Pt(style.size)
            run.font.bold = style.bold
            run.font.italic = style.italic
            run.font.underline = style.underline
            run.font.color.rgb = RGBColor.from_string(style.color)


def _write_frame(frame, paragraphs, margin):
    frame.clear()
    frame.word_wrap = False
    frame.margin_left = frame.margin_right = Pt(margin)
    frame.margin_top = frame.margin_bottom = Pt(margin)
    for index, (spec, lines) in enumerate(paragraphs):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        _write_paragraph(paragraph, spec, lines)


class HtmlImportMixin:
    def import_html(
        self,
        html: str,
        *,
        resources: Mapping[str, bytes | Path] | None = None,
        index: int | None = None,
    ) -> tuple[Slide, ...]:
        """Insert editable offline HTML-subset slides, appending by default.

        Supply each image explicitly in ``resources``. Unsupported markup,
        styles, and unrepresentable layouts raise ``HtmlImportError`` before
        slide edits are queued. See ``docs/features/html-import.md``.
        """
        return import_into_slides(self, html, resources=resources, index=index)


def import_into_slides(
    slides: SlideCollection,
    html: str,
    *,
    resources: Mapping[str, bytes | Path] | None = None,
    index: int | None = None,
) -> tuple[Slide, ...]:
    """Plan all input before queueing ordinary Wolf slide objects."""
    from .presentation_slide_insert import _normalize_insert_index, _require_open_presentation

    prs = slides._presentation
    with prs._mutation_lock:
        _require_open_presentation(prs)
        slides._require_attached()
        position = len(slides) if index is None else _normalize_insert_index(index, len(slides))
        width, height = prs.slide_width / 12700 - 72, prs.slide_height / 12700 - 72
        pages = _plan(html, resources or {}, width, height)
        # Use a placeholder-free layout, irrespective of its ordinal in a template.
        layout = next(
            (
                layout
                for layout in prs.slide_layouts
                if not layout._cloneable_placeholder_payloads()
            ),
            None,
        )
        if layout is None:
            raise HtmlImportError("HTML import requires a placeholder-free slide layout")
        result = []
        for offset, page in enumerate(pages):
            slide = slides.insert(position + offset, layout)
            for kind, y, size, data in page:
                x, top = Pt(_MARGIN), Pt(_MARGIN + y)
                if kind == "text":
                    shape = slide.shapes.add_textbox(x, top, Pt(width), Pt(size))
                    _write_frame(shape.text_frame, [data], 0)
                elif kind == "image":
                    blob, w, h = data
                    slide.shapes.add_picture(io.BytesIO(blob), x, top, Pt(w), Pt(h))
                else:
                    columns = len(data[0][0])
                    table = slide.shapes.add_table(
                        len(data), columns, x, top, Pt(width), Pt(size)
                    ).table
                    for row_index, (cells, row_height) in enumerate(data):
                        table.rows[row_index].height = Pt(row_height)
                        for col_index, paragraphs in enumerate(cells):
                            _write_frame(table.cell(row_index, col_index).text_frame, paragraphs, 4)
            result.append(slide)
        return tuple(result)


def html_to_pptx(
    html: str,
    output: str | Path,
    *,
    resources: Mapping[str, bytes | Path] | None = None,
    source: str | Path | None = None,
    index: int | None = None,
) -> dict:
    """Create or insert editable HTML content and atomically save a PPTX path.

    Existing slides retain their identities. No source URL is ever fetched.
    A failure leaves any previous destination file unchanged.
    """
    from .presentation import Presentation

    output = Path(output)
    if output.suffix.lower() != ".pptx":
        raise HtmlImportError("HTML import output must have a .pptx suffix")
    prs = Presentation() if source is None else Presentation(source)
    try:
        added = prs.slides.import_html(html, resources=resources, index=index)
        prs.save(output)
        return {"slides_added": len(added), "image_only": False}
    finally:
        prs.close()
