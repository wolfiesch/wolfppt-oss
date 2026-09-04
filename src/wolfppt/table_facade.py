"""Table facade classes and helpers for python-pptx-compatible access."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from .facade_values import (
    centipoints_to_emu as _centipoints_to_emu,
    coerce_paragraph_level as _coerce_paragraph_level,
    emu_value as _emu_value,
    normalize_line_spacing as _normalize_line_spacing,
    normalize_paragraph_alignment as _normalize_paragraph_alignment,
    normalize_paragraph_spacing_length as _normalize_paragraph_spacing_length,
    normalize_text_frame_auto_size as _normalize_text_frame_auto_size,
    normalize_text_frame_vertical_anchor as _normalize_text_frame_vertical_anchor,
    normalize_text_frame_word_wrap as _normalize_text_frame_word_wrap,
    paragraph_alignment_value as _paragraph_alignment_value,
    text_frame_vertical_anchor_value as _text_frame_vertical_anchor_value,
)
from .package_parts import PackagePart
from .table_cell_fill_facade import (
    TableCellColorFormat,
    TableCellFillFormat,
    TableCellGradientStop,
    TableCellGradientStopColorFormat,
    TableCellGradientStops,
)
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
    _table_column_widths,
    _table_cell_fill_pattern,
    _table_cell_fill_type,
    _table_cell_margin,
    _table_cell_pattern_rgb,
    _table_cell_property_payload,
    _table_cell_solid_rgb,
    _table_cell_span,
    _table_cell_text_frame_auto_size,
    _table_cell_text_frame_paragraph_alignment,
    _table_cell_text_frame_paragraph_level,
    _table_cell_text_frame_paragraph_runs,
    _table_cell_text_frame_paragraph_spacing,
    _table_cell_text_frame_margin,
    _table_cell_text_frame_paragraph_texts,
    _table_cell_text_frame_vertical_anchor,
    _table_cell_text_frame_word_wrap,
    _table_cell_vertical_anchor,
    _table_row_heights,
    _table_style_flag,
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


class Table:
    def __init__(self, slide: Slide, table_index: int, payload: dict[str, Any]) -> None:
        self._slide = slide
        self._table_index = table_index
        self._payload = payload
        self._rows = _normalize_table_rows(payload)

    @property
    def part(self) -> PackagePart:
        return self._slide.part

    @property
    def rows(self) -> "TableRowCollection":
        return TableRowCollection(self)

    @property
    def columns(self) -> "TableColumnCollection":
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

    def cell(self, row_idx: int, col_idx: int) -> "TableCell":
        self._validate_cell(row_idx, col_idx)
        return TableCell(self, row_idx, col_idx)

    def iter_cells(self) -> Iterator["TableCell"]:
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


class TableRowCollection(Sequence["TableRow"]):
    def __init__(self, table: Table) -> None:
        self._table = table

    @property
    def part(self) -> PackagePart:
        return self._table.part

    def __getitem__(self, index: int | slice) -> "TableRow | list[TableRow]":
        if isinstance(index, slice):
            return [
                TableRow(self._table, row_index)
                for row_index in range(*index.indices(len(self)))
            ]
        if index < 0:
            index += len(self)
        self._table._validate_cell(index, 0)
        return TableRow(self._table, index)

    def __iter__(self) -> Iterator["TableRow"]:
        for index in range(len(self)):
            yield TableRow(self._table, index)

    def __len__(self) -> int:
        return len(self._table._rows)

    def notify_height_changed(self) -> None:
        return None

    def insert(self, index: int) -> "TableRow":
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

    def __getitem__(self, index: int | slice) -> "TableColumn | list[TableColumn]":
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

    def __iter__(self) -> Iterator["TableColumn"]:
        for index in range(len(self)):
            yield TableColumn(self._table, index)

    def __len__(self) -> int:
        return max((len(row) for row in self._table._rows), default=0)

    def notify_width_changed(self) -> None:
        return None

    def insert(self, index: int) -> "TableColumn":
        return _insert_table_column(self._table, index)

    def remove(self, index: int) -> None:
        _delete_table_column(self._table, index)

    def delete(self, index: int) -> None:
        _delete_table_column(self._table, index)

    def __delitem__(self, index: int) -> None:
        _delete_table_column(self._table, index)


class TableRow:
    def __init__(self, table: Table, index: int) -> None:
        self._table = table
        self._index = index

    @property
    def part(self) -> PackagePart:
        return self._table.part

    @property
    def cells(self) -> list["TableCell"]:
        return [
            TableCell(self._table, self._index, col_idx)
            for col_idx in range(len(self._table._rows[self._index]))
        ]

    @property
    def height(self) -> int:
        return _table_row_heights(self._table)[self._index]

    @height.setter
    def height(self, value: Any) -> None:
        _set_table_row_height(self, value)


class TableColumn:
    def __init__(self, table: Table, index: int) -> None:
        self._table = table
        self._index = index

    @property
    def part(self) -> PackagePart:
        return self._table.part

    @property
    def cells(self) -> list["TableCell"]:
        return [
            TableCell(self._table, row_idx, self._index)
            for row_idx, row in enumerate(self._table._rows)
            if self._index < len(row)
        ]

    @property
    def width(self) -> int:
        return _table_column_widths(self._table)[self._index]

    @width.setter
    def width(self, value: Any) -> None:
        _set_table_column_width(self, value)


class TableCell:
    def __init__(self, table: Table, row_idx: int, col_idx: int) -> None:
        self._table = table
        self._row_idx = row_idx
        self._col_idx = col_idx

    @property
    def part(self) -> PackagePart:
        return self._table.part

    @property
    def text_frame(self) -> "TableCellTextFrame":
        return TableCellTextFrame(self)

    @property
    def fill(self) -> "TableCellFillFormat":
        return TableCellFillFormat(self)

    @property
    def is_merge_origin(self) -> bool:
        payload = _table_cell_property_payload(self)
        return (
            not bool(payload.get("h_merge"))
            and not bool(payload.get("v_merge"))
            and (self.span_width > 1 or self.span_height > 1)
        )

    @property
    def is_spanned(self) -> bool:
        payload = _table_cell_property_payload(self)
        return bool(payload.get("h_merge")) or bool(payload.get("v_merge"))

    @property
    def span_width(self) -> int:
        return _table_cell_span(self, "grid_span")

    @property
    def span_height(self) -> int:
        return _table_cell_span(self, "row_span")

    @property
    def text(self) -> str:
        return self._table._rows[self._row_idx][self._col_idx]

    @text.setter
    def text(self, value: str) -> None:
        text = str(value)
        if text == self.text:
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

    def merge(self, other_cell: "TableCell") -> None:
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
    def paragraphs(self) -> "TableCellParagraphCollection":
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
        return _text_frame_vertical_anchor_value(
            _table_cell_text_frame_vertical_anchor(self._cell)
        )

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
        self._cell._table._slide._presentation._queue_table_cell_text_frame_auto_size(
            self._cell._table._slide._index,
            self._cell._table._table_index,
            self._cell._row_idx,
            self._cell._col_idx,
            auto_size,
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
        try:
            max_point_size = int(max_size)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"max_size must be an integer, got {max_size!r}") from exc
        if max_point_size < 1:
            raise ValueError("max_size must be greater than zero")
        size_emu = _centipoints_to_emu(max_point_size * 100)
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

    def add_paragraph(self) -> "TableCellTextParagraph":
        paragraphs = list(_table_cell_text_frame_paragraph_texts(self._cell))
        paragraphs.append("")
        _set_table_cell_text_frame_paragraphs(self._cell, paragraphs)
        return TableCellTextParagraph(self._cell, len(paragraphs) - 1)


class TableCellParagraphCollection(Sequence["TableCellTextParagraph"]):
    def __init__(self, cell: TableCell) -> None:
        self._cell = cell

    def __getitem__(
        self,
        index: int | slice,
    ) -> "TableCellTextParagraph | list[TableCellTextParagraph]":
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

    def __iter__(self) -> Iterator["TableCellTextParagraph"]:
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
    def font(self) -> "TableCellTextParagraphFont":
        return TableCellTextParagraphFont(self)

    @property
    def runs(self) -> "TableCellTextRunCollection":
        return TableCellTextRunCollection(self)

    def add_run(self) -> "TableCellTextRun":
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

    def clear(self) -> "TableCellTextParagraph":
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

    def __getitem__(
        self,
        index: int | slice,
    ) -> "TableCellTextRun | list[TableCellTextRun]":
        runs = _table_cell_text_frame_paragraph_runs(self._paragraph._cell)[
            self._paragraph._index
        ]
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

    def __iter__(self) -> Iterator["TableCellTextRun"]:
        for index in range(len(self)):
            yield TableCellTextRun(self._paragraph, index)

    def __len__(self) -> int:
        return len(
            _table_cell_text_frame_paragraph_runs(self._paragraph._cell)[
                self._paragraph._index
            ]
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return [run.text for run in self] == other
        return super().__eq__(other)


class TableCellTextRun:
    def __init__(self, paragraph: TableCellTextParagraph, index: int) -> None:
        self._paragraph = paragraph
        self._index = index

    @property
    def part(self) -> PackagePart:
        return self._paragraph.part

    @property
    def font(self) -> "TableCellTextRunFont":
        return TableCellTextRunFont(self)

    @property
    def hyperlink(self) -> "TableCellTextRunHyperlink":
        return TableCellTextRunHyperlink(self)

    @property
    def text(self) -> str:
        return _table_cell_text_frame_paragraph_runs(self._paragraph._cell)[
            self._paragraph._index
        ][self._index]

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
