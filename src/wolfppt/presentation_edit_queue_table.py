"""Queued table operations for the presentation facade."""

from __future__ import annotations

from typing import Any

class PresentationTableQueueMixin:
    def _queue_table_cell_text(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        text: str,
    ) -> None:
        self._table_cell_edits[(slide_index, table_index, row_index, col_index)] = text

    def _queue_table_row_insert(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
    ) -> None:
        self._table_row_column_edits.append(
            {
                "type": "insert_table_row",
                "slide_index": slide_index,
                "table_index": table_index,
                "row_index": row_index,
            }
        )

    def _queue_table_row_delete(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
    ) -> None:
        self._table_row_column_edits.append(
            {
                "type": "delete_table_row",
                "slide_index": slide_index,
                "table_index": table_index,
                "row_index": row_index,
            }
        )

    def _queue_table_column_insert(
        self,
        slide_index: int,
        table_index: int,
        col_index: int,
    ) -> None:
        self._table_row_column_edits.append(
            {
                "type": "insert_table_column",
                "slide_index": slide_index,
                "table_index": table_index,
                "col_index": col_index,
            }
        )

    def _queue_table_column_delete(
        self,
        slide_index: int,
        table_index: int,
        col_index: int,
    ) -> None:
        self._table_row_column_edits.append(
            {
                "type": "delete_table_column",
                "slide_index": slide_index,
                "table_index": table_index,
                "col_index": col_index,
            }
        )

    def _queue_table_row_height(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        height: int,
    ) -> None:
        self._table_row_height_edits[(slide_index, table_index, row_index)] = height

    def _queue_table_column_width(
        self,
        slide_index: int,
        table_index: int,
        col_index: int,
        width: int,
    ) -> None:
        self._table_column_width_edits[(slide_index, table_index, col_index)] = width

    def _queue_table_cell_margin(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        attr: str,
        value: int,
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_margin_edits.setdefault(key, {})[attr] = value

    def _queue_table_cell_vertical_anchor(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        value: str | None,
    ) -> None:
        self._table_cell_vertical_anchor_edits[
            (slide_index, table_index, row_index, col_index)
        ] = value

    def _queue_table_cell_text_frame_margin(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        attr: str,
        value: int,
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_text_frame_margin_edits.setdefault(key, {})[attr] = value

    def _queue_table_cell_text_frame_vertical_anchor(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        value: str | None,
    ) -> None:
        self._table_cell_text_frame_vertical_anchor_edits[
            (slide_index, table_index, row_index, col_index)
        ] = value

    def _queue_table_cell_text_frame_content(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraphs: list[str],
    ) -> None:
        self._table_cell_text_frame_content_edits[
            (slide_index, table_index, row_index, col_index)
        ] = list(paragraphs)

    def _queue_table_cell_text_frame_word_wrap(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        value: bool | None,
    ) -> None:
        self._table_cell_text_frame_word_wrap_edits[
            (slide_index, table_index, row_index, col_index)
        ] = value

    def _queue_table_cell_text_frame_auto_size(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        value: str | None,
    ) -> None:
        self._table_cell_text_frame_auto_size_edits[
            (slide_index, table_index, row_index, col_index)
        ] = value

    def _queue_table_cell_text_frame_fit(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        fit: dict[str, Any],
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_text_frame_word_wrap_edits.pop(key, None)
        self._table_cell_text_frame_auto_size_edits.pop(key, None)
        self._table_cell_text_frame_fit_edits[key] = dict(fit)

    def _queue_table_cell_text_frame_paragraph_alignment(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraph_index: int,
        alignment: str | None,
    ) -> None:
        self._table_cell_text_frame_paragraph_alignment_edits[
            (slide_index, table_index, row_index, col_index, paragraph_index)
        ] = alignment

    def _queue_table_cell_text_frame_paragraph_level(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraph_index: int,
        level: int,
    ) -> None:
        self._table_cell_text_frame_paragraph_level_edits[
            (slide_index, table_index, row_index, col_index, paragraph_index)
        ] = level

    def _queue_table_cell_text_frame_paragraph_spacing(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraph_index: int,
        attr: str,
        value: int | float | None,
    ) -> None:
        self._table_cell_text_frame_paragraph_spacing_edits.setdefault(
            (slide_index, table_index, row_index, col_index, paragraph_index),
            {},
        )[attr] = value

    def _queue_table_cell_text_frame_paragraph_font(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraph_index: int,
        edits: dict[str, Any],
    ) -> None:
        self._table_cell_text_frame_paragraph_font_edits.setdefault(
            (slide_index, table_index, row_index, col_index, paragraph_index),
            {},
        ).update(edits)

    def _queue_table_cell_text_frame_paragraph_runs(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraph_index: int,
        runs: list[str],
    ) -> None:
        self._table_cell_text_frame_paragraph_run_edits[
            (slide_index, table_index, row_index, col_index, paragraph_index)
        ] = list(runs)

    def _queue_table_cell_text_frame_paragraph_line_break(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraph_index: int,
        run_slot: int,
    ) -> None:
        self._table_cell_text_frame_paragraph_line_break_edits.append(
            (
                slide_index,
                table_index,
                row_index,
                col_index,
                paragraph_index,
                run_slot,
            )
        )

    def _queue_table_cell_text_frame_paragraph_run_font(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraph_index: int,
        run_index: int,
        edits: dict[str, Any],
    ) -> None:
        self._table_cell_text_frame_paragraph_run_font_edits.setdefault(
            (
                slide_index,
                table_index,
                row_index,
                col_index,
                paragraph_index,
                run_index,
            ),
            {},
        ).update(edits)

    def _queue_table_cell_text_frame_paragraph_run_hyperlink(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        paragraph_index: int,
        run_index: int,
        address: str | None,
    ) -> None:
        self._table_cell_text_frame_paragraph_run_hyperlink_edits[
            (
                slide_index,
                table_index,
                row_index,
                col_index,
                paragraph_index,
                run_index,
            )
        ] = address

    def _queue_table_cell_fill_solid(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_fill_color_edits.pop(key, None)
        self._table_cell_fill_background_edits.discard(key)
        self._table_cell_fill_pattern_edits.pop(key, None)
        self._table_cell_fill_pattern_fore_color_edits.pop(key, None)
        self._table_cell_fill_pattern_back_color_edits.pop(key, None)
        self._table_cell_fill_gradient_edits.pop(key, None)
        self._table_cell_fill_solid_edits.add(key)

    def _queue_table_cell_fill_background(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_fill_color_edits.pop(key, None)
        self._table_cell_fill_solid_edits.discard(key)
        self._table_cell_fill_pattern_edits.pop(key, None)
        self._table_cell_fill_pattern_fore_color_edits.pop(key, None)
        self._table_cell_fill_pattern_back_color_edits.pop(key, None)
        self._table_cell_fill_gradient_edits.pop(key, None)
        self._table_cell_fill_background_edits.add(key)

    def _queue_table_cell_fill_patterned(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        pattern: str | None,
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_fill_color_edits.pop(key, None)
        self._table_cell_fill_solid_edits.discard(key)
        self._table_cell_fill_background_edits.discard(key)
        self._table_cell_fill_gradient_edits.pop(key, None)
        self._table_cell_fill_pattern_edits[key] = pattern

    def _queue_table_cell_fill_pattern_fore_color(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        rgb: Any,
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_fill_color_edits.pop(key, None)
        self._table_cell_fill_solid_edits.discard(key)
        self._table_cell_fill_background_edits.discard(key)
        self._table_cell_fill_gradient_edits.pop(key, None)
        self._table_cell_fill_pattern_fore_color_edits[key] = rgb

    def _queue_table_cell_fill_pattern_back_color(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        rgb: Any,
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_fill_color_edits.pop(key, None)
        self._table_cell_fill_solid_edits.discard(key)
        self._table_cell_fill_background_edits.discard(key)
        self._table_cell_fill_gradient_edits.pop(key, None)
        self._table_cell_fill_pattern_back_color_edits[key] = rgb

    def _queue_table_cell_fill_color(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        rgb: Any,
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_fill_solid_edits.discard(key)
        self._table_cell_fill_background_edits.discard(key)
        self._table_cell_fill_pattern_edits.pop(key, None)
        self._table_cell_fill_pattern_fore_color_edits.pop(key, None)
        self._table_cell_fill_pattern_back_color_edits.pop(key, None)
        self._table_cell_fill_gradient_edits.pop(key, None)
        self._table_cell_fill_color_edits[key] = rgb

    def _queue_table_cell_fill_gradient(
        self,
        slide_index: int,
        table_index: int,
        row_index: int,
        col_index: int,
        gradient: dict[str, Any],
    ) -> None:
        key = (slide_index, table_index, row_index, col_index)
        self._table_cell_fill_color_edits.pop(key, None)
        self._table_cell_fill_solid_edits.discard(key)
        self._table_cell_fill_background_edits.discard(key)
        self._table_cell_fill_pattern_edits.pop(key, None)
        self._table_cell_fill_pattern_fore_color_edits.pop(key, None)
        self._table_cell_fill_pattern_back_color_edits.pop(key, None)
        self._table_cell_fill_gradient_edits[key] = dict(gradient)

    def _queue_table_cell_merge_edit(
        self,
        edit: dict[str, Any],
    ) -> None:
        self._table_cell_merge_edits.append(dict(edit))

    def _queue_table_style_flag(
        self,
        slide_index: int,
        table_index: int,
        attr: str,
        value: bool,
    ) -> None:
        self._table_style_edits.setdefault((slide_index, table_index), {})[
            attr
        ] = value
