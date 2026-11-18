"""Queued text operations for the presentation facade."""

from __future__ import annotations

from typing import Any

from .presentation_edit_queue_text_coalescing import remove_paragraph_run_edits
from .presentation_text_queue import clear_group_text_edits
from .shape_edit_refs import ShapeEditRef
from .shape_payloads import _invalidate_shape_text_cache


class PresentationTextQueueMixin:
    def _queue_text_run(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        run_index: int,
        text: str,
    ) -> None:
        if (slide_index, shape_index) in self._shape_text_edits:
            return
        if (slide_index, shape_index, paragraph_index) in self._paragraph_text_edits:
            return
        self._text_run_edits[(slide_index, run_index)] = (
            shape_index,
            paragraph_index,
            text,
        )

    def _queue_text_run_bold(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        run_index: int,
        bold: bool | None,
    ) -> None:
        self._text_run_bold_edits[(slide_index, run_index)] = (
            shape_index,
            paragraph_index,
            paragraph_run_index,
            bold,
        )

    def _queue_text_run_italic(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        run_index: int,
        italic: bool | None,
    ) -> None:
        self._text_run_italic_edits[(slide_index, run_index)] = (
            shape_index,
            paragraph_index,
            paragraph_run_index,
            italic,
        )

    def _queue_text_run_underline(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        run_index: int,
        underline: bool | None,
    ) -> None:
        self._text_run_underline_edits[(slide_index, run_index)] = (
            shape_index,
            paragraph_index,
            paragraph_run_index,
            underline,
        )

    def _queue_text_run_strike(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        run_index: int,
        strike: bool | None,
    ) -> None:
        self._text_run_strike_edits[(slide_index, run_index)] = (
            shape_index,
            paragraph_index,
            paragraph_run_index,
            strike,
        )

    def _queue_text_run_font_size(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        run_index: int,
        size: int | None,
    ) -> None:
        self._text_run_font_size_edits[(slide_index, run_index)] = (
            shape_index,
            paragraph_index,
            paragraph_run_index,
            size,
        )

    def _queue_text_run_font_name(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        run_index: int,
        name: str | None,
    ) -> None:
        self._text_run_font_name_edits[(slide_index, run_index)] = (
            shape_index,
            paragraph_index,
            paragraph_run_index,
            name,
        )

    def _queue_text_run_font_color(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        run_index: int,
        color: Any,
    ) -> None:
        self._text_run_font_color_edits[
            (slide_index, shape_index, paragraph_index, paragraph_run_index)
        ] = (run_index, color)
        self._text_run_font_fill_type_edits.pop(
            (slide_index, shape_index, paragraph_index, paragraph_run_index),
            None,
        )

    def _queue_text_run_font_fill_type(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        fill_type: Any,
    ) -> None:
        key = (slide_index, shape_index, paragraph_index, paragraph_run_index)
        self._text_run_font_fill_type_edits[key] = fill_type
        self._text_run_font_color_edits.pop(key, None)

    def _queue_text_run_font_language(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        paragraph_run_index: int,
        value: str | None,
    ) -> None:
        self._text_run_font_language_edits[
            (slide_index, shape_index, paragraph_index, paragraph_run_index)
        ] = value

    def _queue_text_run_advanced(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        run_index: int,
        attr: str,
        value: Any,
    ) -> None:
        self._text_run_advanced_edits.setdefault(
            (slide_index, shape_index, paragraph_index, run_index), {}
        )[attr] = value

    def _queue_text_run_append(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        run_index: int,
        text: str,
    ) -> None:
        if (slide_index, shape_index) in self._shape_text_edits:
            return
        if (slide_index, shape_index, paragraph_index) in self._paragraph_text_edits:
            return
        self._text_run_appends[(slide_index, shape_index, paragraph_index, run_index)] = text

    def _queue_paragraph_text(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        text: str,
    ) -> None:
        if (slide_index, shape_index) in self._shape_text_edits:
            return
        self._paragraph_clear_edits.discard((slide_index, shape_index, paragraph_index))
        self._remove_paragraph_line_break_edits(slide_index, shape_index, paragraph_index)
        self._paragraph_text_edits[(slide_index, shape_index, paragraph_index)] = text
        remove_paragraph_run_edits(self, slide_index, shape_index, paragraph_index)

    def _queue_paragraph_clear(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
    ) -> None:
        if (slide_index, shape_index) in self._shape_text_edits:
            return
        key = (slide_index, shape_index, paragraph_index)
        self._paragraph_clear_edits.add(key)
        self._remove_paragraph_line_break_edits(slide_index, shape_index, paragraph_index)
        self._paragraph_text_edits.pop(key, None)
        self._paragraph_appends.pop(key, None)
        remove_paragraph_run_edits(self, slide_index, shape_index, paragraph_index)

    def _queue_paragraph_line_break(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        run_slot: int,
    ) -> None:
        if (slide_index, shape_index) in self._shape_text_edits:
            return
        self._paragraph_line_break_edits.append(
            (slide_index, shape_index, paragraph_index, run_slot)
        )

    def _remove_paragraph_line_break_edits(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int | None = None,
    ) -> None:
        self._paragraph_line_break_edits = [
            edit
            for edit in self._paragraph_line_break_edits
            if not (
                edit[0] == slide_index
                and edit[1] == shape_index
                and (paragraph_index is None or edit[2] == paragraph_index)
            )
        ]

    def _queue_paragraph_append(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        text: str,
    ) -> None:
        if (slide_index, shape_index) in self._shape_text_edits:
            return
        self._paragraph_appends[(slide_index, shape_index, paragraph_index)] = text
        for key in list(self._text_run_appends):
            if key[:3] == (slide_index, shape_index, paragraph_index):
                del self._text_run_appends[key]

    def _queue_paragraph_alignment(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        alignment: str | None,
    ) -> None:
        self._paragraph_alignment_edits[(slide_index, shape_index, paragraph_index)] = alignment

    def _queue_paragraph_level(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        level: int,
    ) -> None:
        self._paragraph_level_edits[(slide_index, shape_index, paragraph_index)] = level

    def _queue_paragraph_spacing(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        attr: str,
        value: float | str | None,
    ) -> None:
        self._paragraph_spacing_edits.setdefault(
            (slide_index, shape_index, paragraph_index),
            {},
        )[attr] = value

    def _queue_paragraph_font(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        attr: str,
        value: Any,
    ) -> None:
        key = (slide_index, shape_index, paragraph_index)
        edits = self._paragraph_font_edits.setdefault(key, {})
        edits[attr] = value
        if attr == "color":
            edits.pop("fill_type", None)
        elif attr == "fill_type":
            edits.pop("color", None)

    def _queue_paragraph_bullet(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        bullet: dict[str, Any] | None,
    ) -> None:
        self._paragraph_bullet_edits[(slide_index, shape_index, paragraph_index)] = bullet

    def _queue_shape_text(
        self,
        slide_index: int,
        shape_index: int,
        text: str,
        clear_formatting: bool = True,
    ) -> None:
        self._shape_text_edits[(slide_index, shape_index)] = text
        for key in list(self._paragraph_text_edits):
            if key[:2] == (slide_index, shape_index):
                del self._paragraph_text_edits[key]
        for key in list(self._paragraph_clear_edits):
            if key[:2] == (slide_index, shape_index):
                self._paragraph_clear_edits.remove(key)
        self._remove_paragraph_line_break_edits(slide_index, shape_index)
        if not clear_formatting:
            return
        for key, (queued_shape_index, _, _) in list(self._text_run_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_bold_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_bold_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_italic_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_italic_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_underline_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_underline_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_strike_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_strike_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_font_size_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_font_size_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_font_name_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_font_name_edits[key]
        for key in list(self._text_run_font_color_edits):
            if key[:2] == (slide_index, shape_index):
                del self._text_run_font_color_edits[key]
        for key in list(self._text_run_font_fill_type_edits):
            if key[:2] == (slide_index, shape_index):
                del self._text_run_font_fill_type_edits[key]
        for key in list(self._text_run_font_language_edits):
            if key[:2] == (slide_index, shape_index):
                del self._text_run_font_language_edits[key]
        for pending in (
            self._paragraph_tab_stop_edits,
            self._text_run_hyperlink_edits,
            self._text_run_advanced_edits,
        ):
            for key in list(pending):
                if key[:2] == (slide_index, shape_index):
                    del pending[key]
        for key in list(self._paragraph_appends):
            if key[:2] == (slide_index, shape_index):
                del self._paragraph_appends[key]
        for key in list(self._paragraph_alignment_edits):
            if key[:2] == (slide_index, shape_index):
                del self._paragraph_alignment_edits[key]
        for key in list(self._paragraph_level_edits):
            if key[:2] == (slide_index, shape_index):
                del self._paragraph_level_edits[key]
        for key in list(self._paragraph_spacing_edits):
            if key[:2] == (slide_index, shape_index):
                del self._paragraph_spacing_edits[key]
        for key in list(self._paragraph_font_edits):
            if key[:2] == (slide_index, shape_index):
                del self._paragraph_font_edits[key]
        for key in list(self._paragraph_bullet_edits):
            if key[:2] == (slide_index, shape_index):
                del self._paragraph_bullet_edits[key]
        for key in list(self._text_run_appends):
            if key[:2] == (slide_index, shape_index):
                del self._text_run_appends[key]

    def _queue_shape_text_with_appended_runs(
        self,
        slide_index: int,
        shape_index: int,
        text: str,
        appended_runs: list[tuple[int, int, str]],
    ) -> None:
        """Re-queue pending whole-shape text without merging later runs.

        The whole-shape writer emits one run per paragraph; each run added after
        it is replayed as its own appended run so run-indexed formatting and
        hyperlinks still resolve to the intended run.
        """
        self._queue_shape_text(slide_index, shape_index, text, clear_formatting=False)
        for key in list(self._text_run_appends):
            if key[:2] == (slide_index, shape_index):
                del self._text_run_appends[key]
        for paragraph_index, run_index, run_text in appended_runs:
            self._text_run_appends[(slide_index, shape_index, paragraph_index, run_index)] = (
                run_text
            )

    def _queue_shape_text_for_shape(self, shape: Any, text: str) -> None:
        # Whole-text writers replace every run, including its rPr. Old run
        # properties must not suppress a later setter as an apparent no-op.
        for key in tuple(shape._payload):
            if key.startswith("paragraph_run_"):
                del shape._payload[key]
        _invalidate_shape_text_cache(shape)
        slide = shape._slide
        if getattr(slide, "_is_notes_slide", False):
            self._queue_part_shape_text(slide.partname, shape._index, text)
        elif shape._payload.get("_deep_nested_group_child"):
            self._queue_deeper_group_child_text(
                slide._index,
                int(shape._payload["_group_index"]),
                int(shape._payload["_nested_group_child_index"]),
                int(shape._payload["_deeper_group_child_index"]),
                int(shape._payload["_group_child_index"]),
                text,
            )
        elif shape._payload.get("_nested_group_child"):
            self._queue_nested_group_child_text(
                slide._index,
                int(shape._payload["_group_index"]),
                int(shape._payload["_nested_group_child_index"]),
                int(shape._payload["_group_child_index"]),
                text,
            )
        elif shape._payload.get("_group_child"):
            self._queue_group_child_text(
                slide._index,
                int(shape._payload["_group_index"]),
                int(shape._payload["_group_child_index"]),
                text,
            )
        else:
            self._queue_shape_text(slide._index, shape._index, text)

    def _queue_part_shape_text(
        self,
        partname: str,
        shape_index: int,
        text: str,
    ) -> None:
        self._part_shape_text_edits[(str(partname), shape_index)] = text
        for pending in (
            self._part_paragraph_text_edits,
            self._part_run_text_edits,
            self._part_run_font_edits,
            self._part_run_hyperlink_edits,
            self._part_paragraph_alignment_edits,
            self._part_paragraph_level_edits,
            self._part_paragraph_spacing_edits,
            self._part_paragraph_font_edits,
            self._part_paragraph_bullet_edits,
            self._part_paragraph_tab_stop_edits,
        ):
            for key in list(pending):
                if key[:2] == (str(partname), shape_index):
                    del pending[key]
        prefix = (str(partname), shape_index)
        self._part_paragraph_clear_edits.difference_update(
            key for key in tuple(self._part_paragraph_clear_edits) if key[:2] == prefix
        )
        self._part_paragraph_line_break_edits = [
            key for key in self._part_paragraph_line_break_edits if key[:2] != prefix
        ]

    def _remove_part_paragraph_content_edits(
        self, partname: str, shape_index: int, paragraph_index: int
    ) -> None:
        prefix = (str(partname), shape_index, paragraph_index)
        for pending in (
            self._part_run_text_edits,
            self._part_run_font_edits,
            self._part_run_hyperlink_edits,
        ):
            for key in list(pending):
                if key[:3] == prefix:
                    del pending[key]
        self._part_paragraph_line_break_edits = [
            key for key in self._part_paragraph_line_break_edits if key[:3] != prefix
        ]

    def _queue_part_paragraph_text(
        self, partname: str, shape_index: int, paragraph_index: int, text: str
    ) -> None:
        key = (str(partname), shape_index, paragraph_index)
        self._remove_part_paragraph_content_edits(*key)
        self._part_paragraph_clear_edits.discard(key)
        self._part_paragraph_text_edits[key] = text

    def _queue_part_paragraph_clear(
        self, partname: str, shape_index: int, paragraph_index: int
    ) -> None:
        key = (str(partname), shape_index, paragraph_index)
        self._remove_part_paragraph_content_edits(*key)
        if key in self._part_paragraph_text_edits:
            # Retain creation of an appended paragraph before clearing its content.
            self._part_paragraph_text_edits[key] = ""
        self._part_paragraph_clear_edits.add(key)

    def _queue_part_paragraph_line_break(
        self, partname: str, shape_index: int, paragraph_index: int, run_slot: int
    ) -> None:
        self._part_paragraph_line_break_edits.append(
            (str(partname), shape_index, paragraph_index, run_slot)
        )

    def _queue_part_run_text(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        run_index: int,
        text: str,
    ) -> None:
        self._part_run_text_edits[(str(partname), shape_index, paragraph_index, run_index)] = text

    def _queue_part_paragraph_alignment(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        alignment: str | None,
    ) -> None:
        self._part_paragraph_alignment_edits[(str(partname), shape_index, paragraph_index)] = (
            alignment
        )

    def _queue_part_paragraph_level(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        level: int,
    ) -> None:
        self._part_paragraph_level_edits[(str(partname), shape_index, paragraph_index)] = level

    def _queue_part_paragraph_spacing(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        attr: str,
        value: float | str | None,
    ) -> None:
        self._part_paragraph_spacing_edits.setdefault(
            (str(partname), shape_index, paragraph_index),
            {},
        )[attr] = value

    def _queue_part_paragraph_font(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        attr: str,
        value: Any,
    ) -> None:
        edits = self._part_paragraph_font_edits.setdefault(
            (str(partname), shape_index, paragraph_index),
            {},
        )
        edits[attr] = value
        if attr == "color":
            edits.pop("fill_type", None)
        elif attr == "fill_type":
            edits.pop("color", None)

    def _queue_part_paragraph_bullet(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        bullet: dict[str, Any] | None,
    ) -> None:
        self._part_paragraph_bullet_edits[(str(partname), shape_index, paragraph_index)] = bullet

    def _queue_part_text_frame_margin(
        self,
        partname: str,
        shape_index: int,
        attr: str,
        value: int,
    ) -> None:
        self._part_text_frame_margin_edits.setdefault(
            (str(partname), shape_index),
            {},
        )[attr] = value

    def _queue_part_text_frame_word_wrap(
        self,
        partname: str,
        shape_index: int,
        value: bool | None,
    ) -> None:
        self._part_text_frame_word_wrap_edits[(str(partname), shape_index)] = value

    def _queue_part_text_frame_vertical_anchor(
        self,
        partname: str,
        shape_index: int,
        value: str | None,
    ) -> None:
        self._part_text_frame_vertical_anchor_edits[(str(partname), shape_index)] = value

    def _queue_part_text_frame_auto_size(
        self,
        partname: str,
        shape_index: int,
        value: str | None,
        autofit_scale: dict[str, float | None] | None = None,
    ) -> None:
        self._part_text_frame_auto_size_edits[(str(partname), shape_index)] = (
            value,
            autofit_scale,
        )

    def _queue_group_child_text(
        self,
        slide_index: int,
        group_index: int,
        child_index: int,
        text: str,
    ) -> None:
        clear_group_text_edits(self, slide_index, group_index, (child_index,))
        self._group_child_text_edits[(slide_index, group_index, child_index)] = text

    def _queue_nested_group_child_text(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        child_index: int,
        text: str,
    ) -> None:
        clear_group_text_edits(
            self, slide_index, group_index, (nested_group_child_index, child_index)
        )
        self._nested_group_child_text_edits[
            (slide_index, group_index, nested_group_child_index, child_index)
        ] = text

    def _queue_deeper_group_child_text(
        self,
        slide_index: int,
        group_index: int,
        nested_group_child_index: int,
        deeper_group_child_index: int,
        child_index: int,
        text: str,
    ) -> None:
        clear_group_text_edits(
            self,
            slide_index,
            group_index,
            (nested_group_child_index, deeper_group_child_index, child_index),
        )
        self._deeper_group_child_text_edits[
            (
                slide_index,
                group_index,
                nested_group_child_index,
                deeper_group_child_index,
                child_index,
            )
        ] = text

    def _queue_group_child_paragraph_text(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        text: str,
    ) -> None:
        self._group_child_paragraph_text_edits[
            (slide_index, group_index, child_index, paragraph_index)
        ] = text
        for key in list(self._group_child_run_text_edits):
            if key[:4] == (slide_index, group_index, child_index, paragraph_index):
                del self._group_child_run_text_edits[key]
        for key in list(self._group_child_run_font_edits):
            if key[:4] == (slide_index, group_index, child_index, paragraph_index):
                del self._group_child_run_font_edits[key]
        for key in list(self._group_child_run_hyperlink_edits):
            if key[:4] == (slide_index, group_index, child_index, paragraph_index):
                del self._group_child_run_hyperlink_edits[key]
        self._group_child_paragraph_clear_edits.discard(
            (slide_index, group_index, child_index, paragraph_index)
        )
        for key in list(self._group_child_paragraph_line_break_edits):
            if key[:4] == (slide_index, group_index, child_index, paragraph_index):
                self._group_child_paragraph_line_break_edits.discard(key)

    def _queue_group_child_paragraph_clear(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
    ) -> None:
        key = (slide_index, group_index, child_index, paragraph_index)
        self._group_child_paragraph_clear_edits.add(key)
        self._group_child_paragraph_text_edits.pop(key, None)
        for queued_key in list(self._group_child_paragraph_line_break_edits):
            if queued_key[:4] == key:
                self._group_child_paragraph_line_break_edits.discard(queued_key)
        for queued_key in list(self._group_child_run_text_edits):
            if queued_key[:4] == key:
                del self._group_child_run_text_edits[queued_key]
        for queued_key in list(self._group_child_run_font_edits):
            if queued_key[:4] == key:
                del self._group_child_run_font_edits[queued_key]
        for queued_key in list(self._group_child_run_hyperlink_edits):
            if queued_key[:4] == key:
                del self._group_child_run_hyperlink_edits[queued_key]

    def _queue_group_child_paragraph_line_break(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        run_slot: int,
    ) -> None:
        self._group_child_paragraph_line_break_edits.add(
            (slide_index, group_index, child_index, paragraph_index, run_slot)
        )

    def _queue_paragraph_tab_stops(
        self,
        slide_index: int,
        shape_index: int,
        paragraph_index: int,
        stops: list[dict[str, Any]],
    ) -> None:
        self._paragraph_tab_stop_edits[(slide_index, shape_index, paragraph_index)] = [
            dict(stop) for stop in stops
        ]

    def _queue_group_child_paragraph_tab_stops(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        stops: list[dict[str, Any]],
    ) -> None:
        self._group_child_paragraph_tab_stop_edits[
            (slide_index, group_index, child_index, paragraph_index)
        ] = [dict(stop) for stop in stops]

    def _queue_part_paragraph_tab_stops(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        stops: list[dict[str, Any]],
    ) -> None:
        self._part_paragraph_tab_stop_edits[(str(partname), shape_index, paragraph_index)] = [
            dict(stop) for stop in stops
        ]

    def _queue_group_child_paragraph_alignment(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        alignment: str | None,
    ) -> None:
        self._group_child_paragraph_alignment_edits[
            (slide_index, group_index, child_index, paragraph_index)
        ] = alignment

    def _queue_group_child_paragraph_level(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        level: int,
    ) -> None:
        self._group_child_paragraph_level_edits[
            (slide_index, group_index, child_index, paragraph_index)
        ] = level

    def _queue_group_child_paragraph_spacing(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        attr: str,
        value: float | str | None,
    ) -> None:
        self._group_child_paragraph_spacing_edits.setdefault(
            (slide_index, group_index, child_index, paragraph_index),
            {},
        )[attr] = value

    def _queue_group_child_paragraph_font(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        attr: str,
        value: Any,
    ) -> None:
        edits = self._group_child_paragraph_font_edits.setdefault(
            (slide_index, group_index, child_index, paragraph_index),
            {},
        )
        edits[attr] = value
        if attr == "color":
            edits.pop("fill_type", None)
        elif attr == "fill_type":
            edits.pop("color", None)

    def _queue_group_child_paragraph_bullet(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        bullet: dict[str, Any] | None,
    ) -> None:
        self._group_child_paragraph_bullet_edits[
            (slide_index, group_index, child_index, paragraph_index)
        ] = bullet

    def _queue_group_child_run_text(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        run_index: int,
        text: str,
    ) -> None:
        self._group_child_run_text_edits[
            (slide_index, group_index, child_index, paragraph_index, run_index)
        ] = text

    def _queue_group_child_run_font(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        run_index: int,
        attr: str,
        value: Any,
    ) -> None:
        edits = self._group_child_run_font_edits.setdefault(
            (slide_index, group_index, child_index, paragraph_index, run_index),
            {},
        )
        edits[attr] = value
        if attr == "color":
            edits.pop("fill_type", None)
        elif attr == "fill_type":
            edits.pop("color", None)

    def _queue_group_child_run_hyperlink(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        paragraph_index: int,
        run_index: int,
        address: str | None,
    ) -> None:
        self._group_child_run_hyperlink_edits[
            (slide_index, group_index, child_index, paragraph_index, run_index)
        ] = address

    def _queue_part_run_font(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        run_index: int,
        attr: str,
        value: Any,
    ) -> None:
        edits = self._part_run_font_edits.setdefault(
            (str(partname), shape_index, paragraph_index, run_index),
            {},
        )
        edits[attr] = value
        if attr == "color":
            edits.pop("fill_type", None)
        elif attr == "fill_type":
            edits.pop("color", None)

    def _queue_part_run_hyperlink(
        self,
        partname: str,
        shape_index: int,
        paragraph_index: int,
        run_index: int,
        address: str | None,
    ) -> None:
        self._part_run_hyperlink_edits[(str(partname), shape_index, paragraph_index, run_index)] = (
            address
        )

    def _queue_text_frame_advanced(
        self,
        slide_index: int,
        shape_index: int,
        attr: str,
        value: Any,
    ) -> None:
        self._text_frame_advanced_edits.setdefault((slide_index, shape_index), {})[attr] = value

    def _queue_group_child_text_frame_advanced(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        attr: str,
        value: Any,
    ) -> None:
        self._group_child_text_frame_advanced_edits.setdefault(
            (slide_index, group_index, child_index), {}
        )[attr] = value

    def _queue_part_text_frame_advanced(
        self, partname: str, shape_index: int, attr: str, value: Any
    ) -> None:
        self._part_text_frame_advanced_edits.setdefault((str(partname), shape_index), {})[attr] = (
            value
        )

    def _queue_text_frame_margin(
        self,
        slide_index: int,
        shape_index: int,
        attr: str,
        value: int,
    ) -> None:
        self._text_frame_margin_edits.setdefault((slide_index, shape_index), {})[attr] = value

    def _queue_group_child_text_frame_margin(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        attr: str,
        value: int,
    ) -> None:
        self._group_child_text_frame_margin_edits.setdefault(
            (slide_index, group_index, child_index),
            {},
        )[attr] = value

    def _queue_text_frame_word_wrap(
        self,
        slide_index: int,
        shape_index: int,
        value: bool | None,
    ) -> None:
        self._text_frame_word_wrap_edits[(slide_index, shape_index)] = value

    def _queue_group_child_text_frame_word_wrap(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        value: bool | None,
    ) -> None:
        self._group_child_text_frame_word_wrap_edits[(slide_index, group_index, child_index)] = (
            value
        )

    def _queue_text_frame_vertical_anchor(
        self,
        slide_index: int,
        shape_index: int,
        value: str | None,
    ) -> None:
        self._text_frame_vertical_anchor_edits[(slide_index, shape_index)] = value

    def _queue_group_child_text_frame_vertical_anchor(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        value: str | None,
    ) -> None:
        self._group_child_text_frame_vertical_anchor_edits[
            (slide_index, group_index, child_index)
        ] = value

    def _queue_text_frame_auto_size(
        self,
        slide_index: int,
        shape_index: int,
        value: str | None,
        autofit_scale: dict[str, float | None] | None = None,
    ) -> None:
        self._text_frame_auto_size_edits[(slide_index, shape_index)] = (
            value,
            autofit_scale,
        )

    def _queue_group_child_text_frame_auto_size(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        value: str | None,
        autofit_scale: dict[str, float | None] | None = None,
    ) -> None:
        self._group_child_text_frame_auto_size_edits[(slide_index, group_index, child_index)] = (
            value,
            autofit_scale,
        )

    def _queue_group_child_text_frame_fit(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
        fit: dict[str, Any],
    ) -> None:
        key = (slide_index, group_index, child_index)
        self._group_child_text_frame_word_wrap_edits.pop(key, None)
        self._group_child_text_frame_auto_size_edits.pop(key, None)
        self._group_child_text_frame_fit_edits[key] = dict(fit)
        self._remove_group_child_run_font_edits(slide_index, group_index, child_index)

    def _queue_text_frame_fit(
        self,
        slide_index: int,
        shape_index: int,
        fit: dict[str, Any],
    ) -> None:
        key = (slide_index, shape_index)
        self._text_frame_word_wrap_edits.pop(key, None)
        self._text_frame_auto_size_edits.pop(key, None)
        self._text_frame_fit_edits[key] = dict(fit)
        self._remove_text_run_font_edits(slide_index, shape_index)

    def _remove_group_child_run_font_edits(
        self,
        slide_index: int,
        group_index: ShapeEditRef,
        child_index: int,
    ) -> None:
        prefix = (slide_index, group_index, child_index)
        for key in list(self._group_child_run_font_edits):
            if key[:3] == prefix:
                del self._group_child_run_font_edits[key]

    def _remove_text_run_font_edits(
        self,
        slide_index: int,
        shape_index: int,
    ) -> None:
        for key, (queued_shape_index, _, _, _) in list(self._text_run_bold_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_bold_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_italic_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_italic_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_font_size_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_font_size_edits[key]
        for key, (queued_shape_index, _, _, _) in list(self._text_run_font_name_edits.items()):
            if key[0] == slide_index and queued_shape_index == shape_index:
                del self._text_run_font_name_edits[key]
