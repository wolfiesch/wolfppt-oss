"""Editable offline Markdown import through the strict HTML-subset importer."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from .html_import import HtmlImportError, html_to_pptx, import_into_slides

if TYPE_CHECKING:
    from .presentation_slides import Slide, SlideCollection


def _markdown_html(markdown: str) -> str:
    if not isinstance(markdown, str):
        raise TypeError("markdown must be a string")
    # Validate before CommonMark normalizes NUL or builds its token tree.
    if re.search(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]", markdown):
        raise HtmlImportError("Markdown contains characters unsupported by XML presentation text")
    if len(markdown.encode("utf-8")) > 1048576:
        raise HtmlImportError("Markdown exceeds 1 MiB")
    try:
        from markdown_it import MarkdownIt
    except ModuleNotFoundError as exc:
        if exc.name != "markdown_it":
            raise
        raise ImportError(
            "Markdown import requires the markup extra; "
            "install with: python -m pip install 'wolfppt[markup]'"
        ) from exc
    # Keep raw HTML subject to the same strict importer, not silently escaped.
    # Unsupported CommonMark constructs render unsupported tags and are refused.
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    environment: dict = {}
    tokens = parser.parse(markdown, environment)
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    columns = None
    for token in tokens:
        if token.type == "table_open":
            columns = None
        elif token.type == "tr_open" and token.map is not None:
            # Match the 4.x table rule's escaped-pipe and optional-edge semantics.
            # Its default behavior silently truncates or pads ragged body rows.
            cells = re.split(r"(?<!\\)\|", lines[token.map[0]].strip())
            if cells and cells[0] == "":
                cells.pop(0)
            if cells and cells[-1] == "":
                cells.pop()
            if columns is not None and len(cells) != columns:
                raise HtmlImportError("Markdown table rows must be rectangular")
            columns = len(cells)
    return parser.renderer.render(tokens, parser.options, environment)


def import_markdown(
    slides: SlideCollection,
    markdown: str,
    *,
    resources: Mapping[str, bytes | Path] | None = None,
    index: int | None = None,
) -> tuple[Slide, ...]:
    """Insert the supported Markdown subset into an open slide collection.

    Headings, paragraphs, emphasis, hard breaks and rectangular pipe tables
    become editable slide content. Unsupported constructs raise HtmlImportError
    before any edit. See docs/markup-import.md for the complete boundary.
    """
    return import_into_slides(slides, _markdown_html(markdown), resources=resources, index=index)


def markdown_to_pptx(
    markdown: str,
    output: str | Path,
    *,
    resources: Mapping[str, bytes | Path] | None = None,
    source: str | Path | None = None,
    index: int | None = None,
) -> dict:
    """Create or insert editable Markdown content and atomically save a PPTX.

    Supply images through explicit resource keys in raw block HTML. No resource
    is fetched, and a refused conversion leaves any existing output unchanged.
    The optional markup extra is required only when importing Markdown.
    """
    return html_to_pptx(
        _markdown_html(markdown), output, resources=resources, source=source, index=index
    )
