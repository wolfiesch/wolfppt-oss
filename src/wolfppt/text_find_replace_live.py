"""Find and replace through live facades when a presentation has queued edits.

The package-level byte-splice engine remains the clean-session path. This
planner reads current run handles and applies setters only after every match
and replacement has been validated, without saving or reloading the session.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from .package_parts import open_package_source
from .shape_xml import _shape_xml_element
from .text_facade_xml_inspection import _paragraph_edit_source
from .text_find_replace import (
    A_NS,
    P_NS,
    TextFindReplaceError,
    TextMatch,
    TextReplaceResult,
    _expander,
    compile_search,
)


@dataclass(frozen=True)
class _Target:
    paragraph: Any
    part: str
    scope: str
    slide_index: int
    shape_id: int | None
    shape_name: str
    groups: tuple[int, ...]
    cell: tuple[int, int] | None
    paragraph_index: int
    source: ET.Element | None
    replace_refusal: str | None = None


@dataclass(frozen=True)
class _Piece:
    run: Any
    text: str
    start: int
    receipt_index: int


def _part_root(presentation: Any, part: str) -> ET.Element | None:
    if not part:
        return None
    cache = presentation._facade_xml_root_cache
    if part not in cache:
        with open_package_source(presentation._source_path) as package:
            try:
                cache[part] = ET.fromstring(package.read(part))
            except KeyError:
                return None
    return cache[part]


def _paragraph_source(
    presentation: Any, shape: Any, index: int, element: ET.Element | None
) -> ET.Element | None:
    replaced, prefix, key = _paragraph_edit_source(shape, index)
    if replaced or any(
        key in getattr(presentation, f"{prefix}_paragraph_{kind}_edits")
        for kind in ("text", "clear")
    ):
        return None
    if element is None:
        return None
    paragraphs = element.findall(f"{{{P_NS}}}txBody/{{{A_NS}}}p")
    return paragraphs[index] if index < len(paragraphs) else None


def _targets(presentation: Any) -> Iterator[_Target]:
    for slide_index, slide in enumerate(presentation.slides):
        owners = [(slide, "slide")]
        if slide.has_notes_slide:
            owners.append((slide.notes_slide, "notes"))
        for owner, scope in owners:
            root = _part_root(presentation, owner.partname)
            table_ordinals: dict[int, int] = {}
            if root is not None:
                tables = {
                    id(table): index for index, table in enumerate(root.iter(f"{{{A_NS}}}tbl"))
                }
                for frame in root.iter(f"{{{P_NS}}}graphicFrame"):
                    nv = frame.find(f"{{{P_NS}}}nvGraphicFramePr/{{{P_NS}}}cNvPr")
                    table = frame.find(f".//{{{A_NS}}}tbl")
                    if nv is not None and table is not None:
                        table_ordinals[int(nv.get("id", "0"))] = tables[id(table)]

            def table_ids(shapes: Any) -> Iterator[int]:
                for shape in shapes:
                    if shape._payload.get("kind") == "group":
                        yield from table_ids(shape.shapes)
                    elif shape.has_table and shape.shape_id is not None:
                        yield int(shape.shape_id)

            live_tables = set(table_ids(owner.shapes))
            removed_ordinals = {
                ordinal
                for shape_id, ordinal in table_ordinals.items()
                if shape_id not in live_tables
            }

            def walk(
                shape: Any,
                groups: tuple[int, ...],
                *,
                root: ET.Element | None = root,
                owner: Any = owner,
                scope: str = scope,
                slide_index: int = slide_index,
                table_ordinals: dict[int, int] = table_ordinals,
                removed_ordinals: set[int] = removed_ordinals,
            ) -> Iterator[_Target]:
                if shape._payload.get("kind") == "group":
                    group_id = shape.shape_id
                    nested = groups if group_id is None else (*groups, int(group_id))
                    for child in shape.shapes:
                        yield from walk(child, nested)
                    # Native group payloads aggregate descendant tables/text.
                    return
                element = None
                if root is not None:
                    # Newly authored shapes have no source element yet.
                    with suppress(AttributeError):
                        element = _shape_xml_element(root, shape._payload)
                if shape.has_text_frame:
                    for index, paragraph in enumerate(shape.text_frame.paragraphs):
                        yield _Target(
                            paragraph,
                            owner.partname,
                            scope,
                            slide_index,
                            shape.shape_id,
                            shape.name,
                            groups,
                            None,
                            index,
                            _paragraph_source(presentation, shape, index, element),
                        )
                if shape.has_table:
                    # Table writers address all tables in a part by document
                    # ordinal, including those inside nested groups. Source
                    # ordinals read the source while deletions are still queued.
                    if shape.shape_id in table_ordinals:
                        shape._table_index = table_ordinals[shape.shape_id]
                    source_rows = (
                        [] if element is None else element.findall(f".//{{{A_NS}}}tbl/{{{A_NS}}}tr")
                    )
                    for row_index, row in enumerate(shape.table.rows):
                        for col_index, cell in enumerate(row.cells):
                            source_paragraphs = []
                            if row_index < len(source_rows):
                                source_cells = source_rows[row_index].findall(f"{{{A_NS}}}tc")
                                if col_index < len(source_cells):
                                    source_paragraphs = source_cells[col_index].findall(
                                        f"{{{A_NS}}}txBody/{{{A_NS}}}p"
                                    )
                            for index, paragraph in enumerate(cell.text_frame.paragraphs):
                                source = (
                                    source_paragraphs[index]
                                    if index < len(source_paragraphs)
                                    else None
                                )
                                cell_key = (
                                    slide_index,
                                    shape._table_index,
                                    row_index,
                                    col_index,
                                )
                                if (
                                    cell_key in presentation._table_cell_edits
                                    or cell_key in presentation._table_cell_text_frame_content_edits
                                ):
                                    source = None
                                yield _Target(
                                    paragraph,
                                    owner.partname,
                                    scope,
                                    slide_index,
                                    shape.shape_id,
                                    shape.name,
                                    groups,
                                    (row_index, col_index),
                                    index,
                                    source,
                                    (
                                        "save pending edits before replacing notes table text"
                                        if scope == "notes"
                                        else (
                                            "save pending table deletions before replacing "
                                            "text in affected tables"
                                            if any(
                                                ordinal < shape._table_index
                                                for ordinal in removed_ordinals
                                            )
                                            else None
                                        )
                                    ),
                                )

            for shape in owner.shapes:
                yield from walk(shape, ())


def _pending_break_slots(target: _Target) -> Counter[int]:
    paragraph = target.paragraph
    if target.cell is None:
        shape = paragraph._shape
        presentation = shape._slide._presentation
        _, prefix, key = _paragraph_edit_source(shape, target.paragraph_index)
    else:
        cell = paragraph._cell
        presentation = cell._table._slide._presentation
        prefix = "_table_cell_text_frame"
        key = (
            cell._table._slide._index,
            cell._table._table_index,
            cell._row_idx,
            cell._col_idx,
            target.paragraph_index,
        )
    return Counter(
        record[-1]
        for record in getattr(presentation, f"{prefix}_paragraph_line_break_edits")
        if record[:-1] == key
    )


def _segments(target: _Target) -> Iterator[list[_Piece]]:
    runs = list(target.paragraph.runs)
    source = target.source
    if source is not None and source.find(f"{{{A_NS}}}fld") is not None:
        # Field text belongs to PowerPoint and forms a matching barrier. Shape
        # facades expose field text as a slot; table facades expose only a:r.
        pieces: list[_Piece] = []
        position = handle_index = ordinary_index = 0
        pending_breaks = _pending_break_slots(target)
        for child in source:
            if child.tag in {f"{{{A_NS}}}r", f"{{{A_NS}}}fld"}:
                added_breaks = pending_breaks.pop(handle_index, 0)
                if added_breaks:
                    if pieces:
                        yield pieces
                    pieces = []
                    position += added_breaks
            if child.tag == f"{{{A_NS}}}br":
                if pieces:
                    yield pieces
                pieces = []
                position += 1
            elif child.tag == f"{{{A_NS}}}fld":
                if pieces:
                    yield pieces
                pieces = []
                text = child.find(f"{{{A_NS}}}t")
                field_text = "" if text is None else text.text or ""
                if target.cell is None and text is not None:
                    if handle_index < len(runs):
                        field_text = runs[handle_index].text
                    handle_index += 1
                position += len(field_text)
            elif child.tag == f"{{{A_NS}}}r":
                if child.find(f"{{{A_NS}}}t") is not None and handle_index < len(runs):
                    run = runs[handle_index]
                    pieces.append(_Piece(run, run.text, position, ordinary_index))
                    position += len(run.text)
                    handle_index += 1
                ordinary_index += 1
        for run in runs[handle_index:]:
            added_breaks = pending_breaks.pop(handle_index, 0)
            if added_breaks:
                if pieces:
                    yield pieces
                pieces = []
                position += added_breaks
            pieces.append(_Piece(run, run.text, position, ordinary_index))
            position += len(run.text)
            ordinary_index += 1
            handle_index += 1
        if pieces:
            yield pieces
        return

    # Live paragraph text includes newly queued soft breaks. Segment before
    # running regex so a greedy cross-break match cannot hide valid local ones.
    text = target.paragraph.text
    cursor = 0
    pieces = []
    for index, run in enumerate(runs):
        start = text.find(run.text, cursor)
        if start < 0:
            raise TextFindReplaceError("paragraph text and run text disagree")
        if "\v" in text[cursor:start] and pieces:
            yield pieces
            pieces = []
        pieces.append(_Piece(run, run.text, start, index))
        cursor = start + len(run.text)
    if pieces:
        yield pieces


def _valid_xml_text(value: str) -> bool:
    return all(
        char in "\t\n\r"
        or " " <= char <= "\ud7ff"
        or "\ue000" <= char <= "\ufffd"
        or "\U00010000" <= char <= "\U0010ffff"
        for char in value
    )


def _plan(
    presentation: Any, search: str, replacement: str, **options: bool
) -> tuple[tuple[TextMatch, ...], list[tuple[Any, str, str, str | None]]]:
    pattern = compile_search(search, **options)
    if not isinstance(replacement, str):
        raise TextFindReplaceError("replacement must be a string")
    if options.get("regex"):
        try:
            pattern.sub(replacement, "")  # Validate templates even with no matches.
        except (ValueError, IndexError, re.error) as exc:
            raise TextFindReplaceError(f"invalid replacement template: {exc}") from exc
    expand = _expander(replacement, options.get("regex", False))
    matches: list[TextMatch] = []
    edits: list[tuple[Any, str, str, str | None]] = []
    for target in _targets(presentation):
        for pieces in _segments(target):
            text = "".join(piece.text for piece in pieces)
            base = pieces[0].start
            found = []
            for match in pattern.finditer(text):
                start, end = match.span()
                if start == end:  # Retain the package engine's zero-width policy.
                    continue
                expanded = expand(match)
                if not _valid_xml_text(expanded):
                    raise TextFindReplaceError("replacement contains characters XML cannot carry")
                touched = tuple(
                    index
                    for index, piece in enumerate(pieces)
                    if piece.start - base < end and piece.start - base + len(piece.text) > start
                )
                found.append((start, end, expanded, touched))
                matches.append(
                    TextMatch(
                        part=target.part,
                        scope=target.scope,
                        slide_index=target.slide_index,
                        shape_id=target.shape_id,
                        shape_name=target.shape_name,
                        group_path=target.groups,
                        table_cell=target.cell,
                        paragraph_index=target.paragraph_index,
                        start=base + start,
                        end=base + end,
                        runs=tuple(pieces[index].receipt_index for index in touched),
                        text=match.group(),
                        replacement=expanded,
                    )
                )
            updated = [piece.text for piece in pieces]
            for start, end, expanded, touched in reversed(found):
                if expanded == text[start:end]:
                    continue
                for position, index in enumerate(touched):
                    piece = pieces[index]
                    left = piece.start - base
                    local_start = max(0, start - left)
                    local_end = min(len(piece.text), end - left)
                    inserted = expanded if position == 0 else ""
                    updated[index] = (
                        updated[index][:local_start] + inserted + updated[index][local_end:]
                    )
            for piece, value in zip(pieces, updated, strict=False):
                if piece.text != value:
                    edits.append((piece.run, value, target.part, target.replace_refusal))
    return tuple(matches), edits


def find_in_live_presentation(
    presentation: Any, search: str, **options: bool
) -> tuple[TextMatch, ...]:
    matches, _ = _plan(presentation, search, "", **options)
    return matches


def replace_in_live_presentation(
    presentation: Any, search: str, replacement: str, *, dry_run: bool, **options: bool
) -> TextReplaceResult:
    matches, edits = _plan(presentation, search, replacement, **options)
    if not dry_run:
        refusal = next((reason for _, _, _, reason in edits if reason is not None), None)
        if refusal is not None:
            raise TextFindReplaceError(refusal)
        from .shape_locks import check_text_edit_lock

        # Table cell runs belong to graphic frames, which carry no no_text_edit flag.
        owners = {id(run._shape): run._shape for run, *_ in edits if hasattr(run, "_shape")}
        for owner in owners.values():
            check_text_edit_lock(owner)
        for run, value, _, _ in edits:
            run.text = value
    return TextReplaceResult(matches, tuple(sorted({part for _, _, part, _ in edits})), dry_run)
