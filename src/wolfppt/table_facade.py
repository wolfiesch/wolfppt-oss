"""Table facade classes and helpers for python-pptx-compatible access."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any, overload

if TYPE_CHECKING:
    from .presentation_slides import Slide

from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
)
from .facade_values import (
    coerce_paragraph_level as _coerce_paragraph_level,
)
from .facade_values import (
    emu_value as _emu_value,
)
from .facade_values import (
    normalize_line_spacing as _normalize_line_spacing,
)
from .facade_values import (
    normalize_paragraph_alignment as _normalize_paragraph_alignment,
)
from .facade_values import (
    normalize_paragraph_indent as _normalize_paragraph_indent,
)
from .facade_values import (
    normalize_paragraph_spacing_length as _normalize_paragraph_spacing_length,
)
from .facade_values import (
    normalize_text_frame_auto_size as _normalize_text_frame_auto_size,
)
from .facade_values import (
    normalize_text_frame_vertical_anchor as _normalize_text_frame_vertical_anchor,
)
from .facade_values import (
    normalize_text_frame_word_wrap as _normalize_text_frame_word_wrap,
)
from .facade_values import (
    paragraph_alignment_value as _paragraph_alignment_value,
)
from .facade_values import (
    text_frame_vertical_anchor_value as _text_frame_vertical_anchor_value,
)
from .package_parts import PackagePart
from .table_adds import table_grid_extents
from .table_cell_fill_facade import (
    TableCellColorFormat,
    TableCellFillFormat,
    TableCellGradientStop,
    TableCellGradientStopColorFormat,
    TableCellGradientStops,
)
from .table_facade_cell_state import _table_cell_text_frame_autofit_scale
from .table_facade_layout_state import _table_is_unsaved
from .table_facade_state import (
    _delete_table_column,
    _delete_table_row,
    _insert_table_column,
    _insert_table_row,
    _merge_table_cells,
    _normalize_table_rows,
    _set_table_cell_margin,
    _set_table_cell_text_frame_margin,
    _set_table_cell_text_frame_paragraph_alignment,
    _set_table_cell_text_frame_paragraph_level,
    _set_table_cell_text_frame_paragraph_line_break,
    _set_table_cell_text_frame_paragraph_runs,
    _set_table_cell_text_frame_paragraph_spacing,
    _set_table_cell_text_frame_paragraphs,
    _set_table_cell_text_frame_text,
    _set_table_column_width,
    _set_table_row_height,
    _set_table_style_flag,
    _split_table_cell,
    _table_cell_fill_pattern,
    _table_cell_fill_type,
    _table_cell_margin,
    _table_cell_pattern_rgb,
    _table_cell_property_payload,
    _table_cell_solid_rgb,
    _table_cell_span,
    _table_cell_text_frame_auto_size,
    _table_cell_text_frame_margin,
    _table_cell_text_frame_paragraph_alignment,
    _table_cell_text_frame_paragraph_level,
    _table_cell_text_frame_paragraph_runs,
    _table_cell_text_frame_paragraph_spacing,
    _table_cell_text_frame_paragraph_texts,
    _table_cell_text_frame_vertical_anchor,
    _table_cell_text_frame_word_wrap,
    _table_cell_vertical_anchor,
    _table_column_widths,
    _table_row_heights,
    _table_style_flag,
)
from .table_facade_text_content_state import (
    _set_table_cell_text_frame_paragraph_attribute,
    _table_cell_text_frame_paragraph_attribute,
)
from .table_style_presets import (
    _set_table_style_id,
    _set_table_style_name,
    _table_style_id,
    _table_style_name,
    available_table_styles,
    lookup_table_style_id,
    lookup_table_style_name,
    normalize_table_style_id,
)
from .table_text_font_facade import (
    TableCellTextParagraphFont,
    TableCellTextParagraphFontColorFormat,
    TableCellTextParagraphFontFillFormat,
    TableCellTextRunFont,
    TableCellTextRunFontColorFormat,
    TableCellTextRunFontFillFormat,
    TableCellTextRunHyperlink,
)
from .text_autofit import TextAutofitScale
from .text_facade_inspection import _best_fit_font_size

__all__ = [
    "Table",
    "TableCell",
    "TableCellColorFormat",
    "TableCellFillFormat",
    "TableCellGradientStop",
    "TableCellGradientStopColorFormat",
    "TableCellGradientStops",
    "TableCellParagraphCollection",
    "TableCellTextFrame",
    "TableCellTextParagraph",
    "TableCellTextParagraphFont",
    "TableCellTextParagraphFontColorFormat",
    "TableCellTextParagraphFontFillFormat",
    "TableCellTextRun",
    "TableCellTextRunCollection",
    "TableCellTextRunFont",
    "TableCellTextRunFontColorFormat",
    "TableCellTextRunFontFillFormat",
    "TableCellTextRunHyperlink",
    "TableColumn",
    "TableColumnCollection",
    "TableRow",
    "TableRowCollection",
    "_table_cell_fill_pattern",
    "_table_cell_fill_type",
    "_table_cell_pattern_rgb",
    "_table_cell_solid_rgb",
    "available_table_styles",
    "lookup_table_style_id",
    "lookup_table_style_name",
]


class Table:
    def __init__(self, slide: Slide, table_index: int, payload: dict[str, Any]) -> None:
        self._slide = slide
        self._table_index = table_index
        self._payload = payload
        self._rows = _normalize_table_rows(payload)
        _seed_queued_table_grid(self)

    @property
    def part(self) -> PackagePart:
        return self._slide.part

    @property
    def rows(self) -> TableRowCollection:
        return TableRowCollection(self)

    @property
    def columns(self) -> TableColumnCollection:
        return TableColumnCollection(self)

    @property
    def first_col(self) -> bool:
        return _table_style_flag(self, "first_col")

    @first_col.setter
    def first_col(self, value: Any) -> None:
        _set_table_style_flag(self, "first_col", value)

    @property
    def first_row(self) -> bool:
        return _table_style_flag(self, "first_row")

    @first_row.setter
    def first_row(self, value: Any) -> None:
        _set_table_style_flag(self, "first_row", value)

    @property
    def horz_banding(self) -> bool:
        return _table_style_flag(self, "horz_banding")

    @horz_banding.setter
    def horz_banding(self, value: Any) -> None:
        _set_table_style_flag(self, "horz_banding", value)

    @property
    def last_col(self) -> bool:
        return _table_style_flag(self, "last_col")

    @last_col.setter
    def last_col(self, value: Any) -> None:
        _set_table_style_flag(self, "last_col", value)

    @property
    def last_row(self) -> bool:
        return _table_style_flag(self, "last_row")

    @last_row.setter
    def last_row(self, value: Any) -> None:
        _set_table_style_flag(self, "last_row", value)

    @property
    def vert_banding(self) -> bool:
        return _table_style_flag(self, "vert_banding")

    @vert_banding.setter
    def vert_banding(self, value: Any) -> None:
        _set_table_style_flag(self, "vert_banding", value)

    @property
    def right_to_left(self) -> bool:
        """Whether the table displays its logical columns right-to-left."""
        return _table_style_flag(self, "right_to_left")

    @right_to_left.setter
    def right_to_left(self, value: Any) -> None:
        _set_table_style_flag(self, "right_to_left", value)

    @property
    def style_id(self) -> str | None:
        return _table_style_id(self)

    @style_id.setter
    def style_id(self, value: Any) -> None:
        _set_table_style_id(self, value)

    @property
    def style_name(self) -> str | None:
        return _table_style_name(self)

    @style_name.setter
    def style_name(self, value: Any) -> None:
        _set_table_style_name(self, value)

    def apply_style(self, style: str) -> None:
        """Apply a built-in or package table style by GUID or style name.

        A GUID may omit its braces and is stored as the canonical uppercase
        ``{GUID}``. Any other string is resolved case-insensitively against the
        built-in and package ``tableStyles`` names. An unknown name or
        malformed GUID raises ``ValueError`` and leaves the table unchanged.
        """
        if not isinstance(style, str):
            raise TypeError(
                f"table style must be a GUID or style name string, got {type(style).__name__}"
            )
        cleaned = style.strip()
        try:
            style_id = normalize_table_style_id(cleaned)
        except ValueError:
            if cleaned.startswith("{") or cleaned.endswith("}"):
                raise
            style_id = lookup_table_style_id(cleaned, getattr(self._slide, "_presentation", None))
            if style_id is None:
                raise ValueError(
                    f"table style {style!r} is neither a style GUID nor a known style name"
                ) from None
        _set_table_style_id(self, style_id)

    def cell(self, row_idx: int, col_idx: int) -> TableCell:
        self._validate_cell(row_idx, col_idx)
        return TableCell(self, row_idx, col_idx)

    def iter_cells(self) -> Iterator[TableCell]:
        for row_idx, row in enumerate(self._rows):
            for col_idx in range(len(row)):
                yield TableCell(self, row_idx, col_idx)

    def notify_height_changed(self) -> None:
        return None

    def notify_width_changed(self) -> None:
        return None

    def _validate_cell(self, row_idx: int, col_idx: int) -> None:
        if row_idx < 0 or row_idx >= len(self._rows):
            raise IndexError("table row index out of range")
        if col_idx < 0 or col_idx >= len(self._rows[row_idx]):
            raise IndexError("table column index out of range")


def _seed_queued_table_grid(table: Table) -> None:
    """Seed an unsaved ``add_table`` grid with the extents save will write.

    The table is absent from the saved package until save, so the layout
    helpers' disk read would report zeros (or another table's grid). The
    queued add, not the frame transform, carries the writer's source extents:
    resizing the unsaved frame leaves the written grid unchanged.
    """
    payload = table._payload
    if "_column_widths" in payload and "_row_heights" in payload:
        return
    slide = table._slide
    slide_index = getattr(slide, "_index", None)
    presentation = getattr(slide, "_presentation", None)
    for kind, args in getattr(presentation, "_shape_adds", ()):
        if kind != "table" or args[:2] != (slide_index, table._table_index):
            continue
        if not _table_is_unsaved(table):
            return
        _slide_index, _table_index, rows, cols, _x, _y, cx, cy = args
        # Mirrors the writer's python-pptx split of the queued frame extents.
        payload.setdefault("_column_widths", table_grid_extents(cx, cols))
        payload.setdefault("_row_heights", table_grid_extents(cy, rows))
        return


class TableRowCollection(Sequence["TableRow"]):
    def __init__(self, table: Table) -> None:
        self._table = table

    @property
    def part(self) -> PackagePart:
        return self._table.part

    @overload
    def __getitem__(self, index: int) -> TableRow: ...

    @overload
    def __getitem__(self, index: slice) -> list[TableRow]: ...

    def __getitem__(self, index: int | slice) -> TableRow | list[TableRow]:
        if isinstance(index, slice):
            return [
                TableRow(self._table, row_index) for row_index in range(*index.indices(len(self)))
            ]
        if index < 0:
            index += len(self)
        self._table._validate_cell(index, 0)
        return TableRow(self._table, index)

    def __iter__(self) -> Iterator[TableRow]:
        for index in range(len(self)):
            yield TableRow(self._table, index)

    def __len__(self) -> int:
        return len(self._table._rows)

    def notify_height_changed(self) -> None:
        return None

    def insert(self, index: int) -> TableRow:
        return _insert_table_row(self._table, index)

    def remove(self, index: int) -> None:
        _delete_table_row(self._table, index)

    def delete(self, index: int) -> None:
        _delete_table_row(self._table, index)

    def __delitem__(self, index: int) -> None:
        _delete_table_row(self._table, index)


class TableColumnCollection(Sequence["TableColumn"]):
    def __init__(self, table: Table) -> None:
        self._table = table

    @property
    def part(self) -> PackagePart:
        return self._table.part

    @overload
    def __getitem__(self, index: int) -> TableColumn: ...

    @overload
    def __getitem__(self, index: slice) -> list[TableColumn]: ...

    def __getitem__(self, index: int | slice) -> TableColumn | list[TableColumn]:
        if isinstance(index, slice):
            return [
                TableColumn(self._table, column_index)
                for column_index in range(*index.indices(len(self)))
            ]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError("table column index out of range")
        return TableColumn(self._table, index)

    def __iter__(self) -> Iterator[TableColumn]:
        for index in range(len(self)):
            yield TableColumn(self._table, index)

    def __len__(self) -> int:
        return max((len(row) for row in self._table._rows), default=0)

    def notify_width_changed(self) -> None:
        return None

    def insert(self, index: int) -> TableColumn:
        return _insert_table_column(self._table, index)

    def remove(self, index: int) -> None:
        _delete_table_column(self._table, index)

    def delete(self, index: int) -> None:
        _delete_table_column(self._table, index)

    def __delitem__(self, index: int) -> None:
        _delete_table_column(self._table, index)


class TableRow(Sequence["TableCell"]):
    """A table row; indexing, iteration, and ``len`` cover its cells."""

    def __init__(self, table: Table, index: int) -> None:
        self._table = table
        self._index = index

    @property
    def part(self) -> PackagePart:
        return self._table.part

    @property
    def cells(self) -> list[TableCell]:
        return [
            TableCell(self._table, self._index, col_idx)
            for col_idx in range(len(self._table._rows[self._index]))
        ]

    @overload
    def __getitem__(self, index: int) -> TableCell: ...

    @overload
    def __getitem__(self, index: slice) -> list[TableCell]: ...

    def __getitem__(self, index: int | slice) -> TableCell | list[TableCell]:
        if isinstance(index, slice):
            return [
                TableCell(self._table, self._index, col_idx)
                for col_idx in range(*index.indices(len(self)))
            ]
        count = len(self)
        if index < 0:
            index += count
        if index < 0 or index >= count:
            raise IndexError("table row cell index out of range")
        return TableCell(self._table, self._index, index)

    def __iter__(self) -> Iterator[TableCell]:
        for col_idx in range(len(self)):
            yield TableCell(self._table, self._index, col_idx)

    def __len__(self) -> int:
        return len(self._table._rows[self._index])

    @property
    def height(self) -> int:
        return _table_row_heights(self._table)[self._index]

    @height.setter
    def height(self, value: Any) -> None:
        _set_table_row_height(self, value)


class TableColumn(Sequence["TableCell"]):
    """A table column; indexing, iteration, and ``len`` cover its cells."""

    def __init__(self, table: Table, index: int) -> None:
        self._table = table
        self._index = index

    @property
    def part(self) -> PackagePart:
        return self._table.part

    @property
    def cells(self) -> list[TableCell]:
        return [
            TableCell(self._table, row_idx, self._index)
            for row_idx, row in enumerate(self._table._rows)
            if self._index < len(row)
        ]

    @overload
    def __getitem__(self, index: int) -> TableCell: ...

    @overload
    def __getitem__(self, index: slice) -> list[TableCell]: ...

    def __getitem__(self, index: int | slice) -> TableCell | list[TableCell]:
        return self.cells[index]

    def __iter__(self) -> Iterator[TableCell]:
        for row_idx, row in enumerate(self._table._rows):
            if self._index < len(row):
                yield TableCell(self._table, row_idx, self._index)

    def __len__(self) -> int:
        return sum(1 for row in self._table._rows if self._index < len(row))

    @property
    def width(self) -> int:
        return _table_column_widths(self._table)[self._index]

    @width.setter
    def width(self, value: Any) -> None:
        _set_table_column_width(self, value)


class _Cell:
    """OOXML cell identity and merge/span inspection, without an upstream engine.

    Standalone element construction qualifies these read contracts only. Editing
    and package ownership are provided by the presentation-backed TableCell.
    """

    def __init__(self, tc: Any, parent: Any) -> None:
        self._tc = tc
        self._parent = parent

    def _merge_properties(self) -> dict[str, Any]:
        from .table_facade_cell_state import _table_cell_properties_from_xml

        return _table_cell_properties_from_xml(self._tc)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _Cell):
            return NotImplemented
        if isinstance(self, TableCell) or isinstance(other, TableCell):
            return (
                isinstance(self, TableCell)
                and isinstance(other, TableCell)
                and self._table is other._table
                and self._row_idx == other._row_idx
                and self._col_idx == other._col_idx
            )
        return self._tc is other._tc

    @property
    def is_merge_origin(self) -> bool:
        properties = self._merge_properties()
        return (
            not properties.get("h_merge", False)
            and not properties.get("v_merge", False)
            and (self.span_width > 1 or self.span_height > 1)
        )

    @property
    def is_spanned(self) -> bool:
        properties = self._merge_properties()
        return bool(properties.get("h_merge") or properties.get("v_merge"))

    @property
    def span_width(self) -> int:
        return int(self._merge_properties().get("grid_span", 1))

    @property
    def span_height(self) -> int:
        return int(self._merge_properties().get("row_span", 1))


class TableCell(_Cell):
    def __init__(self, table: Table, row_idx: int, col_idx: int) -> None:
        self._table = table
        self._row_idx = row_idx
        self._col_idx = col_idx

    @property
    def span_width(self) -> int:
        return _table_cell_span(self, "grid_span")

    @property
    def span_height(self) -> int:
        return _table_cell_span(self, "row_span")

    def get_effective(self) -> Any:
        """Return this cell's effective fill and text formatting and their
        sources (commercial edition; see
        :func:`wolfppt.effective_format_readback.table_cell_effective`)."""
        from .editions import commercial_module

        readback = commercial_module("effective_format_readback", "Reading effective formatting")
        return readback.table_cell_effective(self)

    @property
    def part(self) -> PackagePart:
        return self._table.part

    @property
    def text_frame(self) -> TableCellTextFrame:
        return TableCellTextFrame(self)

    @property
    def fill(self) -> TableCellFillFormat:
        return TableCellFillFormat(self)

    @property
    def borders(self) -> Any:
        """Return the public rectangular and diagonal cell-border facade."""
        from .table_cell_border_edits import TableCellBorders

        return TableCellBorders(self)

    def _merge_properties(self) -> dict[str, Any]:
        return _table_cell_property_payload(self)

    @property
    def text(self) -> str:
        return self._table._rows[self._row_idx][self._col_idx]

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        current = self.text
        if text == current:
            return
        # The scalar queue preserves one-paragraph structure and native edit
        # batching. Changes to paragraph/soft-break topology need the existing
        # structured text-frame writer, including when removing old breaks.
        if any(mark in text or mark in current for mark in ("\n", "\v")):
            _set_table_cell_text_frame_text(self, text)
            return
        self._table._rows[self._row_idx][self._col_idx] = text
        self._table._payload["rows"] = self._table._rows
        self._table._slide._presentation._queue_table_cell_text(
            self._table._slide._index,
            self._table._table_index,
            self._row_idx,
            self._col_idx,
            text,
        )

    @property
    def margin_left(self) -> Any:
        return _emu_value(_table_cell_margin(self, "marL"))

    @margin_left.setter
    def margin_left(self, value: Any) -> None:
        _set_table_cell_margin(self, "marL", value)

    @property
    def margin_right(self) -> Any:
        return _emu_value(_table_cell_margin(self, "marR"))

    @margin_right.setter
    def margin_right(self, value: Any) -> None:
        _set_table_cell_margin(self, "marR", value)

    @property
    def margin_top(self) -> Any:
        return _emu_value(_table_cell_margin(self, "marT"))

    @margin_top.setter
    def margin_top(self, value: Any) -> None:
        _set_table_cell_margin(self, "marT", value)

    @property
    def margin_bottom(self) -> Any:
        return _emu_value(_table_cell_margin(self, "marB"))

    @margin_bottom.setter
    def margin_bottom(self, value: Any) -> None:
        _set_table_cell_margin(self, "marB", value)

    @property
    def vertical_anchor(self) -> Any:
        return _text_frame_vertical_anchor_value(_table_cell_vertical_anchor(self))

    @vertical_anchor.setter
    def vertical_anchor(self, value: Any) -> None:
        anchor = _normalize_text_frame_vertical_anchor(value)
        if anchor == _table_cell_vertical_anchor(self):
            return
        _table_cell_property_payload(self)["vertical_anchor"] = anchor
        self._table._slide._presentation._queue_table_cell_vertical_anchor(
            self._table._slide._index,
            self._table._table_index,
            self._row_idx,
            self._col_idx,
            anchor,
        )

    def merge(self, other_cell: TableCell) -> None:
        _merge_table_cells(self, other_cell)

    def split(self) -> None:
        _split_table_cell(self)


class TableCellTextFrame:
    def __init__(self, cell: TableCell) -> None:
        self._cell = cell

    @property
    def part(self) -> PackagePart:
        return self._cell.part

    @property
    def text(self) -> str:
        return "\n".join(_table_cell_text_frame_paragraph_texts(self._cell))

    @text.setter
    def text(self, value: str) -> None:
        _set_table_cell_text_frame_text(self._cell, str(value))

    @property
    def paragraphs(self) -> TableCellParagraphCollection:
        return TableCellParagraphCollection(self._cell)

    @property
    def margin_left(self) -> Any:
        return _emu_value(_table_cell_text_frame_margin(self._cell, "lIns"))

    @margin_left.setter
    def margin_left(self, value: Any) -> None:
        _set_table_cell_text_frame_margin(self._cell, "lIns", value)

    @property
    def margin_right(self) -> Any:
        return _emu_value(_table_cell_text_frame_margin(self._cell, "rIns"))

    @margin_right.setter
    def margin_right(self, value: Any) -> None:
        _set_table_cell_text_frame_margin(self._cell, "rIns", value)

    @property
    def margin_top(self) -> Any:
        return _emu_value(_table_cell_text_frame_margin(self._cell, "tIns"))

    @margin_top.setter
    def margin_top(self, value: Any) -> None:
        _set_table_cell_text_frame_margin(self._cell, "tIns", value)

    @property
    def margin_bottom(self) -> Any:
        return _emu_value(_table_cell_text_frame_margin(self._cell, "bIns"))

    @margin_bottom.setter
    def margin_bottom(self, value: Any) -> None:
        _set_table_cell_text_frame_margin(self._cell, "bIns", value)

    @property
    def vertical_anchor(self) -> Any:
        return _text_frame_vertical_anchor_value(_table_cell_text_frame_vertical_anchor(self._cell))

    @vertical_anchor.setter
    def vertical_anchor(self, value: Any) -> None:
        anchor = _normalize_text_frame_vertical_anchor(value)
        if anchor == _table_cell_text_frame_vertical_anchor(self._cell):
            return
        _table_cell_property_payload(self._cell)["text_frame_vertical_anchor"] = anchor
        self._cell._table._slide._presentation._queue_table_cell_text_frame_vertical_anchor(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            anchor,
        )

    @property
    def word_wrap(self) -> bool | None:
        return _table_cell_text_frame_word_wrap(self._cell)

    @word_wrap.setter
    def word_wrap(self, value: Any) -> None:
        word_wrap = _normalize_text_frame_word_wrap(value)
        if word_wrap == _table_cell_text_frame_word_wrap(self._cell):
            return
        _table_cell_property_payload(self._cell)["text_frame_word_wrap"] = word_wrap
        self._cell._table._slide._presentation._queue_table_cell_text_frame_word_wrap(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            word_wrap,
        )

    @property
    def auto_size(self) -> Any:
        return _table_cell_text_frame_auto_size(self._cell)

    @auto_size.setter
    def auto_size(self, value: Any) -> None:
        auto_size = _normalize_text_frame_auto_size(value)
        payload = _table_cell_property_payload(self._cell)
        if auto_size == payload.get("text_frame_auto_size"):
            return
        payload["text_frame_auto_size"] = auto_size
        payload["text_frame_autofit_scale"] = None
        self._cell._table._slide._presentation._queue_table_cell_text_frame_auto_size(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            auto_size,
        )

    @property
    def autofit_scale(self) -> TextAutofitScale | None:
        return _table_cell_text_frame_autofit_scale(self._cell)

    def set_autofit_scale(
        self,
        font_scale: float,
        line_spacing_reduction: float = 0.0,
    ) -> None:
        scale = TextAutofitScale(font_scale, line_spacing_reduction)
        current_scale = _table_cell_text_frame_autofit_scale(self._cell)
        current_mode = _table_cell_text_frame_auto_size(self._cell)
        if current_mode == "normAutofit" and current_scale == scale:
            return
        payload = _table_cell_property_payload(self._cell)
        payload["text_frame_auto_size"] = "normAutofit"
        payload["text_frame_autofit_scale"] = scale
        scale_dict = {
            "font_scale": scale.font_scale,
            "line_spacing_reduction": scale.line_spacing_reduction,
        }
        self._cell._table._slide._presentation._queue_table_cell_text_frame_auto_size(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            "normAutofit",
            autofit_scale=scale_dict,
        )

    def clear_autofit_scale(self) -> None:
        current_scale = _table_cell_text_frame_autofit_scale(self._cell)
        if current_scale is None:
            return
        payload = _table_cell_property_payload(self._cell)
        current_mode = payload.get("text_frame_auto_size")
        payload["text_frame_autofit_scale"] = None
        clear_dict = {"font_scale": None, "line_spacing_reduction": None}
        self._cell._table._slide._presentation._queue_table_cell_text_frame_auto_size(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            current_mode,
            autofit_scale=clear_dict,
        )

    def fit_text(
        self,
        font_family: str = "Calibri",
        max_size: int = 18,
        bold: bool = False,
        italic: bool = False,
        font_file: str | None = None,
    ) -> None:
        if self.text == "":
            return
        point_size = _best_fit_font_size(
            self.text,
            _table_cell_text_frame_extents(self._cell),
            font_family,
            max_size,
            bool(bold),
            bool(italic),
            font_file,
        )
        size_emu = _centipoints_to_emu(point_size * 100)
        payload = _table_cell_property_payload(self._cell)
        payload["text_frame_word_wrap"] = True
        payload["text_frame_auto_size"] = "noAutofit"
        fit = {
            "font_family": str(font_family),
            "size": size_emu,
            "bold": bool(bold),
            "italic": bool(italic),
        }
        self._cell._table._slide._presentation._queue_table_cell_text_frame_fit(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            fit,
        )

    def clear(self) -> None:
        _set_table_cell_text_frame_paragraphs(self._cell, [""])

    def add_paragraph(self) -> TableCellTextParagraph:
        paragraphs = list(_table_cell_text_frame_paragraph_texts(self._cell))
        paragraphs.append("")
        _set_table_cell_text_frame_paragraphs(self._cell, paragraphs)
        return TableCellTextParagraph(self._cell, len(paragraphs) - 1)


def _table_cell_text_frame_extents(cell: TableCell) -> tuple[int, int]:
    """Return the available cell rectangle, excluding the cell text margins."""
    widths = _table_column_widths(cell._table)
    heights = _table_row_heights(cell._table)
    try:
        width = widths[cell._col_idx]
        height = heights[cell._row_idx]
    except IndexError as exc:
        raise RuntimeError("table cell dimensions are unavailable for text fitting") from exc
    return (
        max(
            0,
            width
            - _table_cell_text_frame_margin(cell, "lIns")
            - _table_cell_text_frame_margin(cell, "rIns"),
        ),
        max(
            0,
            height
            - _table_cell_text_frame_margin(cell, "tIns")
            - _table_cell_text_frame_margin(cell, "bIns"),
        ),
    )


class TableCellParagraphCollection(Sequence["TableCellTextParagraph"]):
    def __init__(self, cell: TableCell) -> None:
        self._cell = cell

    @overload
    def __getitem__(self, index: int) -> TableCellTextParagraph: ...

    @overload
    def __getitem__(self, index: slice) -> list[TableCellTextParagraph]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> TableCellTextParagraph | list[TableCellTextParagraph]:
        paragraphs = _table_cell_text_frame_paragraph_texts(self._cell)
        if isinstance(index, slice):
            return [
                TableCellTextParagraph(self._cell, paragraph_index)
                for paragraph_index in range(*index.indices(len(paragraphs)))
            ]
        if index < 0:
            index += len(paragraphs)
        if index < 0 or index >= len(paragraphs):
            raise IndexError("paragraph index out of range")
        return TableCellTextParagraph(self._cell, index)

    def __iter__(self) -> Iterator[TableCellTextParagraph]:
        for index in range(len(self)):
            yield TableCellTextParagraph(self._cell, index)

    def __len__(self) -> int:
        return len(_table_cell_text_frame_paragraph_texts(self._cell))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return [paragraph.text for paragraph in self] == other
        return super().__eq__(other)


class TableCellTextParagraph:
    def __init__(self, cell: TableCell, index: int) -> None:
        self._cell = cell
        self._index = index

    def get_effective(self) -> Any:
        """Return this cell paragraph's effective formatting and its sources
        (commercial edition)."""
        return self._cell.get_effective().text_frame.paragraphs[self._index]

    @property
    def part(self) -> PackagePart:
        return self._cell.part

    @property
    def text(self) -> str:
        return _table_cell_text_frame_paragraph_texts(self._cell)[self._index]

    @text.setter
    def text(self, value: str) -> None:
        paragraphs = list(_table_cell_text_frame_paragraph_texts(self._cell))
        paragraphs[self._index] = str(value)
        _set_table_cell_text_frame_paragraphs(self._cell, paragraphs)

    @property
    def font(self) -> TableCellTextParagraphFont:
        return TableCellTextParagraphFont(self)

    @property
    def runs(self) -> TableCellTextRunCollection:
        return TableCellTextRunCollection(self)

    def add_run(self) -> TableCellTextRun:
        paragraph_runs = _table_cell_text_frame_paragraph_runs(self._cell)
        if self._index < 0 or self._index >= len(paragraph_runs):
            raise IndexError("paragraph index out of range")
        runs = list(paragraph_runs[self._index])
        runs.append("")
        _set_table_cell_text_frame_paragraph_runs(self._cell, self._index, runs)
        return TableCellTextRun(self, len(runs) - 1)

    @property
    def alignment(self) -> Any:
        return _paragraph_alignment_value(
            _table_cell_text_frame_paragraph_alignment(self._cell, self._index)
        )

    @alignment.setter
    def alignment(self, value: Any) -> None:
        alignment = _normalize_paragraph_alignment(value)
        if alignment == _table_cell_text_frame_paragraph_alignment(
            self._cell,
            self._index,
        ):
            return
        _set_table_cell_text_frame_paragraph_alignment(
            self._cell,
            self._index,
            alignment,
        )

    @property
    def level(self) -> int:
        return _table_cell_text_frame_paragraph_level(self._cell, self._index)

    @level.setter
    def level(self, value: Any) -> None:
        level = _coerce_paragraph_level(value)
        if level == self.level:
            return
        _set_table_cell_text_frame_paragraph_level(self._cell, self._index, level)

    @property
    def rtl(self) -> bool | None:
        """Right-to-left paragraph direction (``a:pPr/@rtl``); None when inherited."""
        return _table_cell_text_frame_paragraph_attribute(
            self._cell,
            self._index,
            "rtl",
        )

    @rtl.setter
    def rtl(self, value: bool | None) -> None:
        if value is not None and not isinstance(value, bool):
            raise TypeError(f"rtl must be bool or None, got {type(value).__name__}")
        _set_table_cell_text_frame_paragraph_attribute(
            self._cell,
            self._index,
            "rtl",
            value,
        )

    @property
    def margin_left(self) -> Any:
        value = _table_cell_text_frame_paragraph_attribute(
            self._cell,
            self._index,
            "margin_left",
        )
        return None if value is None else _emu_value(int(value))

    @margin_left.setter
    def margin_left(self, value: Any) -> None:
        _set_table_cell_text_frame_paragraph_attribute(
            self._cell,
            self._index,
            "margin_left",
            _normalize_paragraph_indent(value, "margin_left"),
        )

    @property
    def margin_right(self) -> Any:
        value = _table_cell_text_frame_paragraph_attribute(
            self._cell,
            self._index,
            "margin_right",
        )
        return None if value is None else _emu_value(int(value))

    @margin_right.setter
    def margin_right(self, value: Any) -> None:
        _set_table_cell_text_frame_paragraph_attribute(
            self._cell,
            self._index,
            "margin_right",
            _normalize_paragraph_indent(value, "margin_right"),
        )

    @property
    def space_before(self) -> Any:
        return _table_cell_text_frame_paragraph_spacing(
            self._cell,
            self._index,
            "space_before",
        )

    @space_before.setter
    def space_before(self, value: Any) -> None:
        spacing = _normalize_paragraph_spacing_length(value, "space_before")
        _set_table_cell_text_frame_paragraph_spacing(
            self._cell,
            self._index,
            "space_before",
            spacing,
        )

    @property
    def space_after(self) -> Any:
        return _table_cell_text_frame_paragraph_spacing(
            self._cell,
            self._index,
            "space_after",
        )

    @space_after.setter
    def space_after(self, value: Any) -> None:
        spacing = _normalize_paragraph_spacing_length(value, "space_after")
        _set_table_cell_text_frame_paragraph_spacing(
            self._cell,
            self._index,
            "space_after",
            spacing,
        )

    @property
    def line_spacing(self) -> Any:
        return _table_cell_text_frame_paragraph_spacing(
            self._cell,
            self._index,
            "line_spacing",
        )

    @line_spacing.setter
    def line_spacing(self, value: Any) -> None:
        spacing = _normalize_line_spacing(value)
        _set_table_cell_text_frame_paragraph_spacing(
            self._cell,
            self._index,
            "line_spacing",
            spacing,
        )

    def clear(self) -> TableCellTextParagraph:
        self.text = ""
        return self

    def add_line_break(self) -> None:
        paragraph_runs = _table_cell_text_frame_paragraph_runs(self._cell)
        if self._index < 0 or self._index >= len(paragraph_runs):
            raise IndexError("paragraph index out of range")
        _set_table_cell_text_frame_paragraph_line_break(
            self._cell,
            self._index,
            len(paragraph_runs[self._index]),
        )


class TableCellTextRunCollection(Sequence["TableCellTextRun"]):
    def __init__(self, paragraph: TableCellTextParagraph) -> None:
        self._paragraph = paragraph

    @overload
    def __getitem__(self, index: int) -> TableCellTextRun: ...

    @overload
    def __getitem__(self, index: slice) -> list[TableCellTextRun]: ...

    def __getitem__(
        self,
        index: int | slice,
    ) -> TableCellTextRun | list[TableCellTextRun]:
        runs = _table_cell_text_frame_paragraph_runs(self._paragraph._cell)[self._paragraph._index]
        if isinstance(index, slice):
            return [
                TableCellTextRun(self._paragraph, run_index)
                for run_index in range(*index.indices(len(runs)))
            ]
        if index < 0:
            index += len(runs)
        if index < 0 or index >= len(runs):
            raise IndexError("run index out of range")
        return TableCellTextRun(self._paragraph, index)

    def __iter__(self) -> Iterator[TableCellTextRun]:
        for index in range(len(self)):
            yield TableCellTextRun(self._paragraph, index)

    def __len__(self) -> int:
        return len(
            _table_cell_text_frame_paragraph_runs(self._paragraph._cell)[self._paragraph._index]
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return [run.text for run in self] == other
        return super().__eq__(other)


class TableCellTextRun:
    def __init__(self, paragraph: TableCellTextParagraph, index: int) -> None:
        self._paragraph = paragraph
        self._index = index

    def get_effective(self) -> Any:
        """Return this cell run's effective character formatting and its
        sources (commercial edition; see
        :func:`wolfppt.effective_format_readback.table_cell_run_effective`)."""
        from .editions import commercial_module

        readback = commercial_module("effective_format_readback", "Reading effective formatting")
        return readback.table_cell_run_effective(self)

    @property
    def part(self) -> PackagePart:
        return self._paragraph.part

    @property
    def font(self) -> TableCellTextRunFont:
        return TableCellTextRunFont(self)

    @property
    def hyperlink(self) -> TableCellTextRunHyperlink:
        return TableCellTextRunHyperlink(self)

    @property
    def text(self) -> str:
        return _table_cell_text_frame_paragraph_runs(self._paragraph._cell)[self._paragraph._index][
            self._index
        ]

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
            return
        paragraph_runs = _table_cell_text_frame_paragraph_runs(self._paragraph._cell)
        runs = list(paragraph_runs[self._paragraph._index])
        runs[self._index] = text
        _set_table_cell_text_frame_paragraph_runs(
            self._paragraph._cell,
            self._paragraph._index,
            runs,
        )
