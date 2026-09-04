"""Table text run and paragraph font facade helpers."""

from __future__ import annotations

from typing import Any

from .facade_values import (
    fill_type_value as _fill_type_value,
    language_id_value as _language_id_value,
    normalize_language_id as _normalize_language_id,
    normalize_rgb as _normalize_rgb,
    normalize_theme_color as _normalize_theme_color,
    rgb_value as _rgb_value,
    theme_color_value as _theme_color_value,
)
from .table_facade_state import (
    _set_table_cell_text_frame_paragraph_font,
    _set_table_cell_text_frame_paragraph_run_font,
    _set_table_cell_text_frame_paragraph_run_hyperlink_address,
    _table_cell_text_frame_paragraph_font_value,
    _table_cell_text_frame_paragraph_run_font_value,
    _table_cell_text_frame_paragraph_run_hyperlink_address,
)


class TableCellTextRunHyperlink:
    def __init__(self, run: Any) -> None:
        self._run = run

    @property
    def address(self) -> str | None:
        return _table_cell_text_frame_paragraph_run_hyperlink_address(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
        )

    @property
    def part(self) -> Any:
        return self._run.part

    @address.setter
    def address(self, value: str | None) -> None:
        address = str(value) if value else None
        if address == self.address:
            return
        _set_table_cell_text_frame_paragraph_run_hyperlink_address(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            address,
        )


class TableCellTextRunFont:
    def __init__(self, run: Any) -> None:
        self._run = run

    @property
    def bold(self) -> bool | None:
        return self._value("bold")

    @bold.setter
    def bold(self, value: bool | None) -> None:
        self._set("bold", None if value is None else bool(value))

    @property
    def italic(self) -> bool | None:
        return self._value("italic")

    @italic.setter
    def italic(self, value: bool | None) -> None:
        self._set("italic", None if value is None else bool(value))

    @property
    def underline(self) -> bool | None:
        return self._value("underline")

    @underline.setter
    def underline(self, value: bool | None) -> None:
        self._set("underline", None if value is None else bool(value))

    @property
    def size(self) -> int | None:
        return self._value("size")

    @size.setter
    def size(self, value: int | None) -> None:
        self._set("size", None if value is None else int(value))

    @property
    def name(self) -> str | None:
        return self._value("name")

    @name.setter
    def name(self, value: str | None) -> None:
        self._set("name", None if value is None else str(value))

    @property
    def color(self) -> "TableCellTextRunFontColorFormat":
        return TableCellTextRunFontColorFormat(self._run)

    @property
    def fill(self) -> "TableCellTextRunFontFillFormat":
        return TableCellTextRunFontFillFormat(self._run)

    @property
    def language_id(self) -> Any:
        return _language_id_value(self._value("language_id"))

    @language_id.setter
    def language_id(self, value: Any) -> None:
        self._set("language_id", _normalize_language_id(value))

    def _value(self, attr: str) -> Any:
        return _table_cell_text_frame_paragraph_run_font_value(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            attr,
        )

    def _set(self, attr: str, value: Any) -> None:
        if value == self._value(attr):
            return
        _set_table_cell_text_frame_paragraph_run_font(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            attr,
            value,
        )


class TableCellTextRunFontFillFormat:
    def __init__(self, run: Any) -> None:
        self._run = run

    def solid(self) -> None:
        if self._value("fill_type") == "solid":
            return
        self._set("fill_type", "solid")

    def background(self) -> None:
        if self._value("fill_type") == "background":
            return
        self._set("fill_type", "background")

    @property
    def type(self) -> Any:
        return _fill_type_value(self._value("fill_type"))

    @property
    def fore_color(self) -> "TableCellTextRunFontColorFormat":
        return TableCellTextRunFontColorFormat(self._run)

    def _value(self, attr: str) -> Any:
        return _table_cell_text_frame_paragraph_run_font_value(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            attr,
        )

    def _set(self, attr: str, value: Any) -> None:
        _set_table_cell_text_frame_paragraph_run_font(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            attr,
            value,
        )


class TableCellTextRunFontColorFormat:
    def __init__(self, run: Any) -> None:
        self._run = run

    @property
    def rgb(self) -> Any:
        rgb = _table_cell_text_frame_paragraph_run_font_value(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            "color",
        )
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if (
            _table_cell_text_frame_paragraph_run_font_value(
                self._run._paragraph._cell,
                self._run._paragraph._index,
                self._run._index,
                "color",
            )
            == rgb
            and _table_cell_text_frame_paragraph_run_font_value(
                self._run._paragraph._cell,
                self._run._paragraph._index,
                self._run._index,
                "fill_type",
            )
            == "solid"
        ):
            return
        _set_table_cell_text_frame_paragraph_run_font(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            "color",
            rgb,
        )

    @property
    def theme_color(self) -> Any:
        value = _table_cell_text_frame_paragraph_run_font_value(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            "theme_color",
        )
        return _theme_color_value("" if value is None else value)

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        theme_color = _normalize_theme_color(value)
        if (
            _table_cell_text_frame_paragraph_run_font_value(
                self._run._paragraph._cell,
                self._run._paragraph._index,
                self._run._index,
                "theme_color",
            )
            == theme_color
            and _table_cell_text_frame_paragraph_run_font_value(
                self._run._paragraph._cell,
                self._run._paragraph._index,
                self._run._index,
                "fill_type",
            )
            == "solid"
        ):
            return
        _set_table_cell_text_frame_paragraph_run_font(
            self._run._paragraph._cell,
            self._run._paragraph._index,
            self._run._index,
            "theme_color",
            theme_color,
        )


class TableCellTextParagraphFont:
    def __init__(self, paragraph: Any) -> None:
        self._paragraph = paragraph

    @property
    def bold(self) -> bool | None:
        return _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            "bold",
        )

    @bold.setter
    def bold(self, value: bool | None) -> None:
        self._set("bold", None if value is None else bool(value))

    @property
    def italic(self) -> bool | None:
        return _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            "italic",
        )

    @italic.setter
    def italic(self, value: bool | None) -> None:
        self._set("italic", None if value is None else bool(value))

    @property
    def underline(self) -> bool | None:
        return _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            "underline",
        )

    @underline.setter
    def underline(self, value: bool | None) -> None:
        self._set("underline", None if value is None else bool(value))

    @property
    def size(self) -> int | None:
        return _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            "size",
        )

    @size.setter
    def size(self, value: int | None) -> None:
        self._set("size", None if value is None else int(value))

    @property
    def name(self) -> str | None:
        return _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            "name",
        )

    @name.setter
    def name(self, value: str | None) -> None:
        self._set("name", None if value is None else str(value))

    @property
    def color(self) -> "TableCellTextParagraphFontColorFormat":
        return TableCellTextParagraphFontColorFormat(self._paragraph)

    @property
    def fill(self) -> "TableCellTextParagraphFontFillFormat":
        return TableCellTextParagraphFontFillFormat(self._paragraph)

    @property
    def language_id(self) -> Any:
        return _language_id_value(
            _table_cell_text_frame_paragraph_font_value(
                self._paragraph._cell,
                self._paragraph._index,
                "language_id",
            )
        )

    @language_id.setter
    def language_id(self, value: Any) -> None:
        self._set("language_id", _normalize_language_id(value))

    def _set(self, attr: str, value: Any) -> None:
        if value == _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            attr,
        ):
            return
        _set_table_cell_text_frame_paragraph_font(
            self._paragraph._cell,
            self._paragraph._index,
            attr,
            value,
        )


class TableCellTextParagraphFontFillFormat:
    def __init__(self, paragraph: Any) -> None:
        self._paragraph = paragraph

    def solid(self) -> None:
        if (
            _table_cell_text_frame_paragraph_font_value(
                self._paragraph._cell,
                self._paragraph._index,
                "fill_type",
            )
            == "solid"
        ):
            return
        _set_table_cell_text_frame_paragraph_font(
            self._paragraph._cell,
            self._paragraph._index,
            "fill_type",
            "solid",
        )

    def background(self) -> None:
        if (
            _table_cell_text_frame_paragraph_font_value(
                self._paragraph._cell,
                self._paragraph._index,
                "fill_type",
            )
            == "background"
        ):
            return
        _set_table_cell_text_frame_paragraph_font(
            self._paragraph._cell,
            self._paragraph._index,
            "fill_type",
            "background",
        )

    @property
    def type(self) -> Any:
        return _fill_type_value(
            _table_cell_text_frame_paragraph_font_value(
                self._paragraph._cell,
                self._paragraph._index,
                "fill_type",
            )
        )

    @property
    def fore_color(self) -> "TableCellTextParagraphFontColorFormat":
        return TableCellTextParagraphFontColorFormat(self._paragraph)


class TableCellTextParagraphFontColorFormat:
    def __init__(self, paragraph: Any) -> None:
        self._paragraph = paragraph

    @property
    def rgb(self) -> Any:
        rgb = _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            "color",
        )
        return None if rgb is None else _rgb_value(rgb)

    @rgb.setter
    def rgb(self, value: Any) -> None:
        rgb = _normalize_rgb(value)
        if (
            _table_cell_text_frame_paragraph_font_value(
                self._paragraph._cell,
                self._paragraph._index,
                "color",
            )
            == rgb
            and _table_cell_text_frame_paragraph_font_value(
                self._paragraph._cell,
                self._paragraph._index,
                "fill_type",
            )
            == "solid"
        ):
            return
        _set_table_cell_text_frame_paragraph_font(
            self._paragraph._cell,
            self._paragraph._index,
            "color",
            rgb,
        )

    @property
    def theme_color(self) -> Any:
        value = _table_cell_text_frame_paragraph_font_value(
            self._paragraph._cell,
            self._paragraph._index,
            "theme_color",
        )
        return _theme_color_value("" if value is None else value)

    @theme_color.setter
    def theme_color(self, value: Any) -> None:
        theme_color = _normalize_theme_color(value)
        if (
            _table_cell_text_frame_paragraph_font_value(
                self._paragraph._cell,
                self._paragraph._index,
                "theme_color",
            )
            == theme_color
            and _table_cell_text_frame_paragraph_font_value(
                self._paragraph._cell,
                self._paragraph._index,
                "fill_type",
            )
            == "solid"
        ):
            return
        _set_table_cell_text_frame_paragraph_font(
            self._paragraph._cell,
            self._paragraph._index,
            "theme_color",
            theme_color,
        )
